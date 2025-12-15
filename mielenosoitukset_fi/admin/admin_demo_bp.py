import sys
import bson
from flask import abort, current_app
import requests

from datetime import date, datetime
from bson.objectid import ObjectId
import logging
from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from flask_babel import _

from mielenosoitukset_fi.utils.classes import Demonstration, Organizer
from mielenosoitukset_fi.utils.demo_cancellation import cancel_demo, queue_cancellation_links_for_demo
from mielenosoitukset_fi.utils.s3 import upload_image_fileobj
from mielenosoitukset_fi.utils.admin.demonstration import collect_tags
from mielenosoitukset_fi.utils.database import DEMO_FILTER
from mielenosoitukset_fi.utils.flashing import flash_message
from mielenosoitukset_fi.utils.variables import CITY_LIST
from mielenosoitukset_fi.utils.wrappers import admin_required, permission_required
from .utils import mongo, log_admin_action_V2, AdminActParser, _ADMIN_TEMPLATE_FOLDER

from mielenosoitukset_fi.utils.database import stringify_object_ids

from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature


# Secret key for generating tokens
SECRET_KEY = "your_secret_key"

GEOCODE_API_KEY = "66df12ce96495339674278ivnc82595"  # your API key

serializer = URLSafeTimedSerializer(SECRET_KEY)
admin_demo_bp = Blueprint("admin_demo", __name__, url_prefix="/admin/demo")

from mielenosoitukset_fi.emailer.EmailSender import EmailSender
from mielenosoitukset_fi.utils.flashing import flash_message
from mielenosoitukset_fi.utils.logger import logger

email_sender = EmailSender()

@admin_demo_bp.before_request
def log_request_info():
    """Log request information before handling it."""
    log_admin_action_V2(
        AdminActParser().log_request_info(request.__dict__, current_user)
    )

@admin_demo_bp.route("/recommend_demo/<demo_id>", methods=["POST"])
@login_required
@admin_required
def recommend_demo(demo_id):
    """Recommend a demonstration (superuser only).

    Adds the demo to the recommended_demos collection with a recommend_till date.

    Parameters
    ----------
    demo_id : str
        The ID of the demonstration to recommend.

    Returns
    -------
    flask.Response
        JSON response with operation status.
    """
    # Only allow global admins (superusers)
    if not getattr(current_user, "global_admin", False):
        return jsonify({"status": "ERROR", "message": _(u"Vain ylläpitäjät voivat suositella mielenosoituksia.")}), 403

    # Fetch the demonstration to get its date
    demo_data = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
    if not demo_data:
        return jsonify({"status": "ERROR", "message": _(u"Mielenosoitusta ei löytynyt.")}), 404

    # Use the demo's date as recommend_till
    recommend_till = demo_data.get("date")
    if not recommend_till:
        return jsonify({"status": "ERROR", "message": _(u"Mielenosoituksen päivämäärä puuttuu.")}), 400

    # Insert or update recommendation
    mongo.recommended_demos.update_one(
        {"demo_id": str(demo_id)},
        {"$set": {"demo_id": str(demo_id), "recommend_till": recommend_till}},
        upsert=True
    )
    return jsonify({"status": "OK", "message": _(u"Mielenosoitus suositeltu.")})


@admin_demo_bp.route("/edit_history/<demo_id>", methods=["GET"])
@login_required
@admin_required
@permission_required("EDIT_DEMO")
def demo_edit_history(demo_id):
    """
    View the edit history for a demonstration.

    Parameters
    ----------
    demo_id : str
        The ID of the demonstration.

    Returns
    -------
    flask.Response
        Renders the edit history page.
    """
    history = list(mongo.demo_edit_history.find({"demo_id": str(demo_id)}).sort("edited_at", -1))
    demo = Demonstration.load_by_id(ObjectId(demo_id))
    demo_name = demo.title
    current_demo_data = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
    
    return render_template(
        "admin/demonstrations/edit_history.html",
        history=history,
        demo_id=demo_id,
        demo_name=demo_name,
    current_demo_data=current_demo_data  # <-- pass current demo JSON   
        
    )


@admin_demo_bp.route('/suggestions')
@login_required
@admin_required
@permission_required('EDIT_DEMO')
def suggestions_list():
    """
    List incoming demo suggestions for admin review.
    """
    suggestions = list(mongo.demo_suggestions.find({}).sort('created_at', -1).limit(200))
    return render_template('admin/suggestions_list.html', suggestions=suggestions)


@admin_demo_bp.route('/suggestions/<suggestion_id>')
@login_required
@admin_required
@permission_required('EDIT_DEMO')
def suggestion_view(suggestion_id):
    """
    View a single suggestion and offer apply/reject actions.
    """
    try:
        s = mongo.demo_suggestions.find_one({'_id': ObjectId(suggestion_id)})
    except Exception:
        s = None
    if not s:
        flash_message('Ehdotusta ei löytynyt.', 'error')
        return redirect(url_for('admin_demo.suggestions_list'))

    demo = None
    try:
        demo = mongo.demonstrations.find_one({'_id': ObjectId(s.get('demo_id'))})
    except Exception:
        demo = None

    return render_template('admin/suggestion_view.html', suggestion=s, demo=demo)


@admin_demo_bp.route('/suggestions/<suggestion_id>/apply', methods=['POST'])
@login_required
@admin_required
@permission_required('EDIT_DEMO')
def suggestion_apply(suggestion_id):
    """
    Apply selected suggested fields from a suggestion to the demo.
    Expects form input 'apply_field' (multiple) naming the fields to apply.
    """
    try:
        s = mongo.demo_suggestions.find_one({'_id': ObjectId(suggestion_id)})
    except Exception:
        s = None
    if not s:
        flash_message('Ehdotusta ei löytynyt.', 'error')
        return redirect(url_for('admin_demo.suggestions_list'))

    demo_id = s.get('demo_id')
    try:
        demo_doc = mongo.demonstrations.find_one({'_id': ObjectId(demo_id)})
    except Exception:
        demo_doc = None

    if not demo_doc:
        flash_message('Mielenosoitusta ei löytynyt.', 'error')
        return redirect(url_for('admin_demo.suggestions_list'))

    # fields selected by admin
    selected = request.form.getlist('apply_field') or []
    suggested = s.get('suggested_fields', {})
    update = {}
    for f in selected:
        if f in suggested:
            update[f] = suggested[f]

    if not update:
        flash_message('Valitse vähintään yksi kenttä päivitettäväksi.', 'error')
        return redirect(url_for('admin_demo.suggestion_view', suggestion_id=suggestion_id))

    # Save edit history
    try:
        mongo.demo_edit_history.insert_one({
            'demo_id': demo_id,
            'edited_by': str(getattr(current_user, '_id', 'unknown')),
            'edited_at': datetime.utcnow(),
            'old_demo': demo_doc,
            'new_demo': {**demo_doc, **update},
        })
    except Exception:
        logger.exception('Failed to write demo_edit_history for suggestion apply')

    # Apply update
    try:
        mongo.demonstrations.update_one({'_id': ObjectId(demo_id)}, {'$set': update})
        mongo.demo_suggestions.update_one({'_id': ObjectId(suggestion_id)}, {'$set': {'status': 'applied', 'applied_fields': selected, 'applied_by': str(getattr(current_user, '_id', 'unknown')), 'applied_at': datetime.utcnow()}})
        flash_message('Ehdotuksen valitut kentät on päivitetty.', 'success')
    except Exception:
        logger.exception('Failed to apply suggestion to demo')
        flash_message('Päivitys epäonnistui.', 'error')

    return redirect(url_for('admin_demo.suggestions_list'))


@admin_demo_bp.route('/suggestions/<suggestion_id>/status', methods=['POST'])
@login_required
@admin_required
@permission_required('EDIT_DEMO')
def suggestion_status_update(suggestion_id):
    """
    Update suggestion status (e.g., reject). Expects form 'status' param.
    """
    status = request.form.get('status')
    if status not in ('rejected', 'closed'):
        flash_message('Tuntematon tila.', 'error')
        return redirect(url_for('admin_demo.suggestion_view', suggestion_id=suggestion_id))
    try:
        mongo.demo_suggestions.update_one({'_id': ObjectId(suggestion_id)}, {'$set': {'status': status, 'reviewed_by': str(getattr(current_user, '_id', 'unknown')), 'reviewed_at': datetime.utcnow()}})
        flash_message('Ehdotuksen tila päivitetty.', 'success')
    except Exception:
        logger.exception('Failed to update suggestion status')
        flash_message('Tilapäivitys epäonnistui.', 'error')
    return redirect(url_for('admin_demo.suggestions_list'))
    
@admin_demo_bp.route("/trigger_screenshot/<demo_id>")
@login_required
@admin_required
@permission_required("EDIT_DEMO")
def trigger_ss(demo_id):
    from mielenosoitukset_fi.utils.screenshot import trigger_screenshot
    with current_app.app_context():
        success, msg = trigger_screenshot(demo_id)

    if success:
        return jsonify({"status": "ok", "message": msg}), 200
    else:
        return jsonify({"status": "error", "message": msg}), 500

@admin_demo_bp.route("/view_demo_diff/<history_id>", methods=["GET"])
@login_required
@admin_required
@permission_required("EDIT_DEMO")
def view_demo_diff(history_id):
    """
    View the diff for a specific historical demonstration edit.

    Parameters
    ----------
    history_id : str
        The ID of the history entry.

    Returns
    -------
    flask.Response
        Renders the diff page.
    """
    from bson.objectid import ObjectId as BsonObjectId
    import difflib
    from markupsafe import Markup

    # Fetch the history entry
    hist = mongo.demo_edit_history.find_one({"_id": BsonObjectId(history_id)})
    if not hist:
        abort(404)

    old = hist.get("old_demo", {})
    new = hist.get("new_demo", {})

    # Utility: character-level diff
    def diff_chars(a, b):
        if a == b:
            return f'<span class="diff-unchanged">{Markup.escape(a)}</span>'
        result = []
        sm = difflib.SequenceMatcher(None, str(a), str(b))
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                result.append(f'<span class="diff-unchanged">{Markup.escape(str(a)[i1:i2])}</span>')
            elif tag == "replace":
                result.append(f'<span class="diff-remove">{Markup.escape(str(a)[i1:i2])}</span>')
                result.append(f'<span class="diff-add">{Markup.escape(str(b)[j1:j2])}</span>')
            elif tag == "delete":
                result.append(f'<span class="diff-remove">{Markup.escape(str(a)[i1:i2])}</span>')
            elif tag == "insert":
                result.append(f'<span class="diff-add">{Markup.escape(str(b)[j1:j2])}</span>')
        return "".join(result)

    # Utility: line-level + character-level diff
    def html_diff(a, b):
        a_lines = str(a).splitlines() or [""]
        b_lines = str(b).splitlines() or [""]
        html = []
        sm = difflib.SequenceMatcher(None, a_lines, b_lines)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                for line in a_lines[i1:i2]:
                    html.append(f'<span class="diff-unchanged">{line}</span>')
            elif tag == "replace":
                if (i2 - i1) == (j2 - j1):
                    for idx in range(i2 - i1):
                        html.append('<span class="diff-line">')
                        html.append(diff_chars(a_lines[i1 + idx], b_lines[j1 + idx]))
                        html.append('</span>')
                else:
                    for line in a_lines[i1:i2]:
                        html.append(f'<span class="diff-remove">{line}</span>')
                    for line in b_lines[j1:j2]:
                        html.append(f'<span class="diff-add">{line}</span>')
            elif tag == "delete":
                for line in a_lines[i1:i2]:
                    html.append(f'<span class="diff-remove">{line}</span>')
            elif tag == "insert":
                for line in b_lines[j1:j2]:
                    html.append(f'<span class="diff-add">{line}</span>')
        return Markup("".join(html))

    # Compute diffs for each field
    diffs = {}
    all_fields = set(old.keys()) | set(new.keys())
    for field in all_fields:
        old_val = old.get(field, "")
        new_val = new.get(field, "")
        if old_val != new_val:
            diffs[field] = {
                "old": old_val,
                "new": new_val,
                "diff_html": html_diff(old_val, new_val)
            }

    return render_template(
        "admin/demonstrations/demo_diff.html",
        diffs=diffs,
        edited_by=hist.get("edited_by"),
        edited_at=hist.get("edited_at"),
        demo_id=hist.get("demo_id"),
        history_id=history_id
    )
@admin_demo_bp.route("/rollback_demo/<history_id>", methods=["POST"])
@login_required
@admin_required
@permission_required("EDIT_DEMO")
def rollback_demo(history_id):
    """
    Roll back a demonstration to a previous state from edit history.
    Tracks the rollback for easy future undo.
    """
   

    hist = mongo.demo_edit_history.find_one({"_id": BsonObjectId(history_id)})
    if not hist:
        abort(404)

    demo_id = hist.get("demo_id")
    old_data = hist.get("old_demo")
    if not demo_id or not old_data:
        flash_message("Rollback epäonnistui: historia ei sisällä tietoja.", "error")
        return redirect(url_for("admin_demo.demo_edit_history", demo_id=demo_id))

    # Fetch current demo
    current_demo = mongo.demonstrations.find_one({"_id": BsonObjectId(demo_id)})
    if not current_demo:
        abort(404)

    # Merge old data into current to avoid losing fields
#    restored_data = _deep_merge(current_demo, old_data)


    # Save rollback in history with rollback origin
    mongo.demo_edit_history.insert_one({
        "demo_id": demo_id,
        "edited_by": str(getattr(current_user, "_id", "unknown")),
        "edited_at": datetime.utcnow(),
        "old_demo": current_demo,
        "new_demo": old_data,
        "diff": None,  # can compute later
        "rollbacked_from": BsonObjectId(history_id),  # track origin
    })

    # Replace current demo
    mongo.demonstrations.replace_one({"_id": BsonObjectId(demo_id)}, old_data)

    flash_message("Mielenosoitus palautettu valittuun versioon.", "success")
    return redirect(url_for("admin_demo.demo_edit_history", demo_id=demo_id))

# -----------------------------------------------------------------------------
# PREVIEW, ACCEPT, REJECT WITH TOKEN (MAGIC LINKS)

# --- SECURITY HARDENED MAGIC LINK SYSTEM --------------------------------------
# Requirements / assumptions:
# - `serializer`: itsdangerous.URLSafeTimedSerializer instance
# - `mongo`: PyMongo db handle
# - CSRF protection enabled (e.g., flask-wtf) for POST handlers rendering forms
# - app config has PROXIES_COUNT if behind reverse proxy
# - templates available: confirm_action.html, detail.html

import hashlib
from datetime import datetime, timedelta, timezone
from flask import request, redirect, url_for, render_template, abort, jsonify
from itsdangerous import BadSignature, SignatureExpired
from bson.objectid import ObjectId

MAGIC_TTL_SECONDS = 86400  # 24h, make configurable
MAGIC_COLLECTION = "magic_links"  # central registry

# Recommended: create TTL index (run once on startup/migration)
# mongo[MAGIC_COLLECTION].create_index("expires_at", expireAfterSeconds=0)
# Also add: mongo[MAGIC_COLLECTION].create_index([("token_hash", 1)], unique=True)

def _now_utc():
    return datetime.now(timezone.utc)

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def _client_ip() -> str:
    """
    Get the best-effort client IP.
    If behind a trusted proxy, prefer X-Forwarded-For first value.
    """
    # If you terminate TLS behind a proxy/load balancer, make sure you trust only known proxies
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        # XFF may be a list "client, proxy1, proxy2"
        return xff.split(",")[0].strip()
    return request.remote_addr or "0.0.0.0"

def _user_agent() -> str:
    return request.headers.get("User-Agent", "")[:512]

def _require_valid_objectid(oid: str) -> ObjectId:
    if not ObjectId.is_valid(oid):
        abort(400, "Invalid id")
    return ObjectId(oid)

def _registry_upsert_initial(token_hash: str, action: str, demo_id: str):
    """
    Create registry doc if missing. Do not bind IP yet (bind on first GET).
    """
    now = _now_utc()
    mongo[MAGIC_COLLECTION].update_one(
        {"token_hash": token_hash},
        {
            "$setOnInsert": {
                "action": action,                # "preview" | "approve" | "reject"
                "demo_id": str(demo_id),
                "created_at": now,
                "expires_at": now + timedelta(seconds=MAGIC_TTL_SECONDS),
                "bound_ip": None,
                "first_seen_at": None,
                "used_at": None,
                "revoked": False,
                "ua_first": None,
                "ua_last": None,
            }
        },
        upsert=True,
    )

def _check_and_bind(action: str, token: str) -> dict:
    """
    Validate token (signature + TTL), verify registry, bind IP on first use,
    enforce single-use and IP lock. Returns registry document.
    """
    try:
        payload = serializer.loads(token, salt=f"{action}-demo", max_age=MAGIC_TTL_SECONDS)
    except SignatureExpired:
        flash_message("Linkki on vanhentunut.", "error")
        abort(410)  # Gone
    except BadSignature:
        flash_message("Linkki on virheellinen.", "error")
        abort(400)

    # payload is the demo_id (string). You could also sign a dict with jti if you want.
    demo_id = str(payload)
    token_hash = _hash_token(token)
    doc = mongo[MAGIC_COLLECTION].find_one({"token_hash": token_hash})

    if not doc:
        # If missing (e.g., never inserted), reject: we require DB presence to prevent forged tokens.
        flash_message("Linkkiä ei tunnistettu.", "error")
        abort(400)

    # Validate action & demo match
    if doc.get("action") != action or doc.get("demo_id") != demo_id:
        flash_message("Linkkiä ei tunnistettu.", "error")
        abort(400)

    # TTL / revoked / used checks
    now = _now_utc()
    if doc.get("revoked"):
        flash_message("Linkki on mitätöity.", "error")
        abort(403)
    
    if doc.get("expires_at"):
        expires_at = doc["expires_at"].replace(tzinfo=timezone.utc)
        if now > expires_at:
            flash_message("Linkki on vanhentunut.", "error")
            abort(410)

    if doc.get("used_at") is not None:
        flash_message("Linkki on jo käytetty.", "warning")
        abort(409)

    # IP bind on first open
    ip = _client_ip()
    ua = _user_agent()

    updates = {"$set": {"ua_last": ua}}
    if not doc.get("bound_ip"):
        # First claimant → bind
        updates["$set"].update({"bound_ip": ip, "first_seen_at": now, "ua_first": ua})
    else:
        if doc["bound_ip"] != ip:
            flash_message("Tämä linkki on lukittu toiseen IP-osoitteeseen.", "error")
            abort(403)

    # Touch doc
    mongo[MAGIC_COLLECTION].update_one({"_id": doc["_id"]}, updates)
    # Refresh & return latest
    return mongo[MAGIC_COLLECTION].find_one({"_id": doc["_id"]})

def _mark_used(doc_id):
    mongo[MAGIC_COLLECTION].update_one({"_id": doc_id}, {"$set": {"used_at": _now_utc()}})

def _load_demo_or_bust(demo_id: str):
    demo = mongo.demonstrations.find_one({"_id": _require_valid_objectid(demo_id)})
    if not demo:
        flash_message("Mielenosoitusta ei löytynyt.", "error")
        abort(404)
    return demo

# ------------------------------------------------------------------------------
# GENERATION HELPERS (call these when creating links)
# ------------------------------------------------------------------------------

def generate_demo_preview_link(demo_id: str) -> str:
    # Create signed token and registry doc
    token = serializer.dumps(str(demo_id), salt="preview-demo")
    _registry_upsert_initial(_hash_token(token), "preview", str(demo_id))
    return url_for("admin_demo.preview_demo_with_token", token=token, _external=True)

def generate_demo_approve_link(demo_id: str) -> str:
    token = serializer.dumps(str(demo_id), salt="approve-demo")
    _registry_upsert_initial(_hash_token(token), "approve", str(demo_id))
    return url_for("admin_demo.approve_demo_with_token", token=token, _external=True)

def generate_demo_reject_link(demo_id: str) -> str:
    token = serializer.dumps(str(demo_id), salt="reject-demo")
    _registry_upsert_initial(_hash_token(token), "reject", str(demo_id))
    return url_for("admin_demo.reject_demo_with_token", token=token, _external=True)

# ------------------------------------------------------------------------------
# PREVIEW (read-only) – allow via GET (single-use still enforced & IP-bound)
# ------------------------------------------------------------------------------

@admin_demo_bp.route("/preview_demo_with_token/<token>", methods=["GET"])
def preview_demo_with_token(token):
    """
    Secure, single-use, IP-bound preview. GET is acceptable for read-only.
    """
    doc = _check_and_bind("preview", token)
    demo = _load_demo_or_bust(doc["demo_id"])

    # Single-use policy: mark used at first successful render.
    # If you prefer multi-view by same IP until expiry, move this to a POST confirm or omit.
    _mark_used(doc["_id"])

    # Make ObjectId JSON-friendly
    if isinstance(demo.get("_id"), ObjectId):
        demo["_id"] = str(demo["_id"])

    return render_template("detail.html", demo=stringify_object_ids(demo), preview_mode=True)

# ------------------------------------------------------------------------------
# APPROVE / REJECT – require POST confirm to avoid link prefetch/GET abuse
# ------------------------------------------------------------------------------

@admin_demo_bp.route("/approve_demo_with_token/<token>", methods=["GET", "POST"])
def approve_demo_with_token(token):
    """
    Two-step:
     - GET: validate/bind & show confirm page with a CSRF-protected POST.
     - POST: perform the action, mark token used.
    """
    if request.method == "GET":
        doc = _check_and_bind("approve", token)
        demo = _load_demo_or_bust(doc["demo_id"])
        return render_template("admin_V2/cc/confirm_action.html",
                               action="approve",
                               token=token,
                               demo=demo)

    # POST
    doc = _check_and_bind("approve", token)  # re-check before state change
    demo_id = doc["demo_id"]

    demo = _load_demo_or_bust(demo_id)
    if demo.get("approved"):
        flash_message("Mielenosoitus on jo hyväksytty.", "info")
        _mark_used(doc["_id"])  # still burn token
        return redirect(url_for("admin_demo.demo_control"))

    mongo.demonstrations.update_one(
        {"_id": _require_valid_objectid(demo_id)},
        {"$set": {"approved": True, "rejected": False}}
    )

    demo_url = url_for("demonstration_detail", demo_id=demo_id, _external=True)

    
    # Notify submitter
    submitter = mongo.submitters.find_one({"demonstration_id": _require_valid_objectid(demo_id)})
    if submitter and submitter.get("submitter_email"):
        email_sender.queue_email(
            template_name="demo_submitter_approved.html",
            subject="Mielenosoituksesi on hyväksytty",
            recipients=[submitter["submitter_email"]],
            context={
                "title": demo.get("title", ""),
                "date": demo.get("date", ""),
                "city": demo.get("city", ""),
                "address": demo.get("address", ""),
                "url": demo_url
            },
        )

    _mark_used(doc["_id"])
    flash_message("Mielenosoitus hyväksyttiin onnistuneesti!", "success")
    
    return redirect(demo_url)


@admin_demo_bp.route("/reject_demo_with_token/<token>", methods=["GET", "POST"])
def reject_demo_with_token(token):
    """
    Two-step:
     - GET: validate/bind & show confirm page with a CSRF-protected POST.
     - POST: perform the action, mark token used.
    """
    if request.method == "GET":
        doc = _check_and_bind("reject", token)
        demo = _load_demo_or_bust(doc["demo_id"])
        return render_template("admin_V2/cc/confirm_action.html",
                               action="reject",
                               token=token,
                               demo=demo)

    # POST
    doc = _check_and_bind("reject", token)  # re-check before state change
    demo_id = doc["demo_id"]

    demo = _load_demo_or_bust(demo_id)
    if demo.get("approved") is False and demo.get("rejected") is True:
        flash_message("Mielenosoitus on jo hylätty.", "info")
        _mark_used(doc["_id"])  # still burn token
        return redirect(url_for("admin_demo.demo_control"))

    mongo.demonstrations.update_one(
        {"_id": _require_valid_objectid(demo_id)},
        {"$set": {"approved": False, "rejected": True}}
    )

    # Notify submitter
    submitter = mongo.submitters.find_one({"demonstration_id": _require_valid_objectid(demo_id)})
    if submitter and submitter.get("submitter_email"):
        email_sender.queue_email(
            template_name="demo_submitter_rejected.html",
            subject="Mielenosoituksesi on hylätty",
            recipients=[submitter["submitter_email"]],
            context={
                "title": demo.get("title", ""),
                "date": demo.get("date", ""),
                "city": demo.get("city", ""),
                "address": demo.get("address", ""),
            },
        )

    _mark_used(doc["_id"])
    flash_message("Mielenosoitus hylättiin onnistuneesti!", "success")
    return redirect(url_for("index"))
from flask import request, render_template
from flask_login import login_required, current_user
from datetime import datetime, date
from bson.objectid import ObjectId as BsonObjectId

from flask import request, render_template
from flask_login import login_required, current_user
from bson.objectid import ObjectId as BsonObjectId
from datetime import datetime, date

from flask import request, render_template, session
from flask_login import login_required, current_user
from bson.objectid import ObjectId as BsonObjectId

from flask import request, render_template, session
from flask_login import login_required, current_user
from bson.objectid import ObjectId as BsonObjectId
from datetime import date

from flask import request, render_template
from flask_login import login_required, current_user
from bson.objectid import ObjectId as BsonObjectId

@admin_demo_bp.route("/")
@login_required
@admin_required
@permission_required("LIST_DEMOS")
def demo_control():
    # --- Query parameters ---
    search_query = request.args.get("search", "").lower()
    approved_only = request.args.get("approved", "false").lower() == "true"
    show_hidden = request.args.get("show_hidden", "false").lower() == "true"
    show_past = request.args.get("show_past", "false").lower() == "true"
    per_page = int(request.args.get("per_page", 20))
    page = int(request.args.get("page", 1))  # page numbers start at 1

    # --- Build filter ---
    filter_query = DEMO_FILTER.copy()
    filter_query.pop("approved", None)

    if approved_only:
        filter_query["approved"] = True
    if not show_hidden:
        filter_query["$or"] = [{"hide": False}, {"hide": {"$exists": False}}]

    if not show_past: # we have in_past
        filter_query["$or"] = [{"in_past": False}, {"in_past": {"$exists": False}}]

    # Search by title if provided
    if search_query:
        filter_query["title"] = {"$regex": search_query, "$options": "i"}  # case-insensitive search

    
    # Permissions
    if not current_user.global_admin:
        _where = current_user._perm_in("EDIT_DEMO")
        filter_query["$or"] = [
            {"organizers": {"$elemMatch": {"organization_id": {"$in": [BsonObjectId(org) for org in _where]}}}},
            {"editors": current_user.id}
        ]

    # --- Count total documents ---
    total_count = mongo.demonstrations.count_documents(filter_query)
    total_pages = (total_count + per_page - 1) // per_page  # ceil division
    # --- Fetch current page ---
    skip_count = (page - 1) * per_page

    #cursor = mongo.demonstrations.find(filter_query)
    if page == 1 and not approved_only:
        unapproved = list(mongo.demonstrations.find(
            {**filter_query, "approved": False, "hide": False}
        ).sort([("date", 1), ("_id", 1)]))

        approved = list(mongo.demonstrations.find(
            {**filter_query, "approved": True}
        ).sort([("date", 1), ("_id", 1)]))

        combined = unapproved + approved
        total_count = len(combined)

        start = 0
        end = per_page
        demos = combined[start:end]
        
        print(demos)

    else:
        # normal paging
        skip_count = (page - 1) * per_page
        demos_cursor = mongo.demonstrations.find(filter_query).sort([("date", 1), ("_id", 1)]) \
                                        .skip(skip_count).limit(per_page)
        demos = list(demos_cursor)



    # --- Determine next/previous pages ---
    prev_page = page - 1 if page > 1 else None
    next_page = page + 1 if page < total_pages else None

    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}demonstrations/dashboard.html",
        demonstrations=demos,
        search_query=search_query,
        approved_status=approved_only,
        show_hidden=show_hidden,
        per_page=per_page,
        current_page=page,
        total_pages=total_pages,
        prev_page=prev_page,
        next_page=next_page
    )

@admin_demo_bp.route("/duplicate/<demo_id>", methods=["POST"])
@login_required
@admin_required
@permission_required("CREATE_DEMO")
def duplicate_demo(demo_id):
    """
    Duplicate a demonstration. The duplicate will have 'approved' set to False.

    Parameters
    ----------
    demo_id : str
        The ID of the demonstration to duplicate.

    Returns
    -------
    flask.Response
        JSON response with new demo ID or error message.
    """
    from bson.objectid import ObjectId
    demo_data = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
    if not demo_data:
        return jsonify({"status": "ERROR", "message": _(u"Mielenosoitusta ei löytynyt.")}), 404

    # Remove unique fields and set approved to False
    demo_data.pop("_id", None)
    demo_data["approved"] = False
    demo_data["title"] = f"{demo_data['title']} (Kopio)"
    # Set created_datetime to current time for the new demo
    demo_data["created_datetime"] = datetime.utcnow()

        
    # If it was a recurring demo, turn it into a non-recurring one
    if demo_data.get("recurs", False):
        demo_data["recurs"] = False

    # Optionally, clear other fields (like editors, submitters, etc.) if needed

    new_demo = Demonstration.from_dict(demo_data)
    new_demo.save()

    return jsonify({"status": "OK", "new_demo_id": str(new_demo._id)})


def filter_demonstrations(query, search_query, show_past, today):
    """Fetch and filter demonstrations based on search criteria.

    Parameters
    ----------
    query : dict
        MongoDB query to filter demonstrations.
    search_query : str
        The search term to filter by (applies to title, city, topic, and address).
    show_past : bool
        Whether to include past demonstrations.
    today : date
        The current date for filtering future demonstrations.

    Returns
    -------


    """
    # Fetch demonstrations from MongoDB
    demonstrations = mongo.demonstrations.find(query)

    # Filter demonstrations based on the criteria
    filtered_demos = [
        demo
        for demo in demonstrations
        if (show_past or datetime.strptime(demo["date"], "%Y-%m-%d").date() >= today)
        and any(
            search_query in demo[field].lower()
            for field in ["title", "city", "address"]
        )
    ]
    
   
    
    # lets calculate the amount of which of those demos are in the past
    past_demos_count = sum(
        1 for demo in filtered_demos
        if datetime.strptime(demo["date"], "%Y-%m-%d").date() < today
    )
  

    return filtered_demos


@admin_demo_bp.route("/create_demo", methods=["GET", "POST"])
@login_required
@admin_required
@permission_required("CREATE_DEMO")
def create_demo():
    """Create a new demonstration.

    Renders the form for creating a demonstration or handles the form submission.

    Changelog:
    ----------
    v2.5.0:
    - Permission required to create a demonstration.

    Parameters
    ----------

    Returns
    -------


    """
    if request.method == "POST":
        # Handle form submission for creating a new demonstration
        return handle_demo_form(request, is_edit=False)

    # Fetch available organizations for the form
    organizations = mongo.organizations.find()

    # Render the demonstration creation form
    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}demonstrations/form.html",
        organizations=organizations,
        form_action=url_for("admin_demo.create_demo"),
        title="Luo mielenosoitus",
        submit_button_text="Luo",
        demo=None,
        city_list=CITY_LIST,
    )


@admin_demo_bp.route("/edit_demo/<demo_id>", methods=["GET", "POST"])
@login_required
@admin_required
@permission_required("EDIT_DEMO")
def edit_demo(demo_id):
    """Edit demonstration details.

    Fetches the demonstration data by ID for editing or processes the edit form submission.

    Parameters
    ----------
    demo_id :


    Returns
    -------


    """
    # Fetch demonstration data by ID
    demo_data = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
    if not demo_data:
        flash_message("Mielenosoitusta ei löytynyt.", "error")
        return redirect(url_for("admin_demo.demo_control"))

    case_id = request.args.get("case_id") or None
   
    if request.method == "POST":
        # Handle form submission for editing the demonstration
        return handle_demo_form(request, is_edit=True, demo_id=demo_id, case_id=case_id)

    # Convert demonstration data to a Demonstration object
    demonstration = Demonstration.from_dict(demo_data)
    
        
    # Render the edit form with pre-filled demonstration details
    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}demonstrations/form.html",
        demo=demonstration,
        form_action=url_for("admin_demo.edit_demo", demo_id=demo_id, case_id=case_id),
        title=_("Muokkaa mielenosoitusta"),
        submit_button_text=_("Tallenna muutokset"),
        city_list=CITY_LIST,
        all_organizations=mongo.organizations.find(),
        case_id=case_id
    )

@admin_demo_bp.route("/send_edit_link_email/<demo_id>", methods=["POST"])
@login_required
@admin_required
@permission_required("GENERATE_EDIT_LINK")
def send_edit_link(demo_id):
    """
    Send a secure edit link via email for a demonstration.

    This function generates a secure edit link for a demonstration and sends it
    to the provided email address.

    Parameters
    ----------
    demo_id : str
        The unique identifier of the demonstration.

    Returns
    -------
    flask.Response
        JSON response containing the edit link if successful, or an error message otherwise.
    """
    try:
        data = request.get_json() if request.is_json else request.form
        email = data.get("email")
        edit_link = data.get("edit_link")

        if not email:
            return jsonify(
                {"status": "ERROR", "message": "Email address is required."}
            ), 400

        demo = Demonstration.load_by_id(demo_id)
        email_sender.queue_email(
            template_name="demo_edit_link.html",
            subject=f"Muokkauslinkki mielenosoitukseen: {demo.title}",
            context={"edit_link": edit_link, "demo_id": demo_id},
            recipients=[email]
        )
        logging.info("Sending edit link to email: %s", email)

        return jsonify({"status": "OK", "message": "Email sent successfully."})

    except Exception as e:
        logging.error("Error sending edit link email: %s", str(e))
        return jsonify({"status": "ERROR", "message": "Internal server error."}), 500

@admin_demo_bp.route("/generate_edit_link/<demo_id>", methods=["POST"])
@login_required
@admin_required
@permission_required("GENERATE_EDIT_LINK")
def generate_edit_link(demo_id):
    """Generate a secure edit link for a demonstration.

    Parameters
    ----------
    demo_id : str
        The ID of the demonstration to generate the link for.

    Returns
    -------
    json
        JSON response containing the edit link or an error message.
    """
    try:
        token = serializer.dumps(demo_id, salt="edit-demo")
        edit_link = url_for(
            "admin_demo.edit_demo_with_token", token=token, _external=True
        )
        return jsonify({"status": "OK", "edit_link": edit_link})
    except Exception as e:
        logging.error("An error occurred while generating the edit link: %s", str(e))
        return (
            jsonify({"status": "ERROR", "message": "An internal error has occurred."}),
            500,
        )


@admin_demo_bp.route("/edit_demo_with_token/<token>", methods=["GET", "POST"])
def edit_demo_with_token(token):
    """Edit demonstration details using a secure token.

    Parameters
    ----------
    token : str
        The secure token for editing the demonstration.

    Returns
    -------
    response
        The rendered template or a redirect response.
    """
    try:
        demo_id = serializer.loads(token, salt="edit-demo", max_age=3600)
    except SignatureExpired:
        return jsonify({"status": "ERROR", "message": "The token has expired."}), 400
    except BadSignature:
        return jsonify({"status": "ERROR", "message": "Invalid token."}), 400

    # Fetch demonstration data by ID
    demo_data = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
    if not demo_data:
        flash_message("Mielenosoitusta ei löytynyt.", "error")
        return redirect(url_for("admin_demo.demo_control"))

    if request.method == "POST":
        # Handle form submission for editing the demonstration
        return handle_demo_form(request, is_edit=True, demo_id=demo_id)

    # Convert demonstration data to a Demonstration object
    demonstration = Demonstration.from_dict(demo_data)

    # Render the edit form with pre-filled demonstration details
    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}demonstrations/form.html",
        demo=demonstration,
        form_action=url_for("admin_demo.edit_demo_with_token", token=token),
        title=_("Muokkaa mielenosoitusta"),
        submit_button_text=_("Tallenna muutokset"),
        city_list=CITY_LIST,
        all_organizations=mongo.organizations.find(),
        edit_demo_with_token=True,
    )

def _deep_merge(old: dict, new: dict) -> dict:
    """
    Safely merge new data into old data without losing keys.
    - Only overwrite if new value is meaningful (not None, "", "None").
    - If both values are dicts, merge recursively.
    """
    merged = old.copy()
    for key, value in new.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged.get(key, {}), value)
        elif value not in (None, "", "None"):
            merged[key] = value
        # else: keep the old value
    return merged


def save_demo_history(demo_id, old_data, new_data, case_id=None):
    _i = mongo.demo_edit_history.insert_one({
        "demo_id": demo_id,
        "edited_by": str(getattr(current_user, "id", "unknown")),
        "edited_at": datetime.utcnow(),
        "old_demo": old_data,
        "new_demo": new_data,
        "diff": None,  # can be populated later by batch job,
        "rollbacked_from": None,
        "case_id": case_id or None
    })
    
    # lets return history id
    return _i.inserted_id or None


def handle_demo_form(request, is_edit=False, demo_id=None, case_id=None):
    """Handle form submission for creating or editing a demonstration.

    Parameters
    ----------
    request :
        The incoming request object containing form data.
    is_edit : bool
        Whether this is an edit operation. (Default value = False)
    demo_id : str
        The ID of the demonstration being edited, if applicable. (Default value = None)

    Returns
    -------


    """
    # Collect demonstration data from the form
    demonstration_data = collect_demo_data(request)
    case_id = request.args.get("case_id") or None
  

    from mielenosoitukset_fi.utils.admin.demonstration import fix_organizers

    demonstration_data = fix_organizers(demonstration_data)
    
    if demo_id and demonstration_data.get("_id") is None:
        demonstration_data["_id"] = ObjectId(demo_id)
        
    try:
        if is_edit and demo_id:
            # --- Save previous version to history ---
            prev_demo = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
            if prev_demo:
                merged_data = _deep_merge(prev_demo, demonstration_data)
                hist_id = save_demo_history(demo_id, prev_demo, merged_data, case_id=case_id)
                if not hist_id:
                    raise ValueError("Failed to save demonstration edit history.")
                
                if case_id:
                    from mielenosoitukset_fi.utils.classes import Case
                    case = Case.from_dict(mongo.cases.find_one({"_id": ObjectId(case_id)}))
                    case.add_action("edit_demo", current_user.username, note=f"More information can be found on history page: <a href='{url_for('admin_demo.view_demo_diff', history_id=hist_id)}'>link</a>")
                    
                    case._add_history_entry({
                        "timestamp": datetime.utcnow(),
                        "action": "Muokattu mielenosoitusta",
                        "user": current_user.username,
                        "mech_action": "edit_demo",
                        "metadata": {
                            "demo_id": demo_id,
                            "history_id": str(hist_id),
                            "reason": "Muokattu mielenosoitusta hallintapaneelista, lisätietoa: <a href='{}'>historia</a>".format(url_for('admin_demo.view_demo_diff', history_id=hist_id, _external=True))
                        },
                    })
                demo = Demonstration.from_dict(merged_data)
                demo.save()
            flash_message("Mielenosoitus päivitetty onnistuneesti.", "success")
        else:
            # Insert a new demonstration
            insert_result = mongo.demonstrations.insert_one(demonstration_data)
            try:
                demo_doc = demonstration_data.copy()
                demo_doc["_id"] = insert_result.inserted_id
                queue_cancellation_links_for_demo(demo_doc)
            except Exception:
                logger.exception("Failed to queue cancellation links for demo %s", insert_result.inserted_id)
            flash_message("Mielenosoitus luotu onnistuneesti.", "success")

        # Redirect to the demonstration control panel on success
        return redirect(url_for("admin_demo.demo_control"))

    except ValueError as e:
        flash_message(f"Virhe: {str(e)}", "error")

        # Redirect to the edit or create form based on operation type
        return redirect(
            url_for("admin_demo.edit_demo", demo_id=demo_id)
            if is_edit
            else url_for("admin_demo.create_demo")
        )

from flask import jsonify

# freeze a demo
@admin_demo_bp.route("/demo/<demo_id>/freeze", methods=["POST"])
@login_required
@admin_required
@permission_required("CREATE_DEMO")
def freeze_demo(demo_id):
    demo = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
    if not demo:
        return jsonify({"status": "ERROR", "message": "Mielenosoitusta ei löytynyt."}), 404

    parent = demo.get("parent")
    if not parent:
        return jsonify({"status": "ERROR", "message": "Vain alikokoukset voidaan jäädyttää."}), 400

    parent_demo = mongo.recu_demos.find_one({"_id": ObjectId(parent)})
    if not parent_demo:
        return jsonify({"status": "ERROR", "message": "Emokokousta ei löytynyt; jäädytys epäonnistui."}), 404

    mongo.recu_demos.update_one(
        {"_id": ObjectId(parent)},
        {"$addToSet": {"freezed_children": demo_id}}
    )

    return jsonify({"status": "OK", "message": "Mielenosoitus on nyt jäädytetty."})


# check frozen status
@admin_demo_bp.route("/demo/<demo_id>/is_frozen", methods=["GET"])
@login_required
@admin_required
@permission_required("VIEW_DEMO")
def is_demo_frozen(demo_id):
    demo = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
    if not demo:
        return jsonify({"status": "ERROR", "message": "Mielenosoitusta ei löytynyt."}), 404

    parent = demo.get("parent")
    if not parent:
        return jsonify({"status": "ERROR", "message": "Vain alikokoukset voidaan tarkistaa.", "MR_ERROR": "NO_RECUR"}), 400

    parent_demo = mongo.recu_demos.find_one({"_id": ObjectId(parent)})
    if not parent_demo:
        return jsonify({"status": "ERROR", "message": "Emokokousta ei löytynyt."}), 404

    is_frozen = demo_id in parent_demo.get("freezed_children", [])
    return jsonify({"status": "OK", "is_frozen": is_frozen})


# unfreeze a demo
@admin_demo_bp.route("/demo/<demo_id>/unfreeze", methods=["POST"])
@login_required
@admin_required
@permission_required("CREATE_DEMO")
def unfreeze_demo(demo_id):
    demo = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
    if not demo:
        return jsonify({"status": "ERROR", "message": "Mielenosoitusta ei löytynyt."}), 404

    parent = demo.get("parent")
    if not parent:
        return jsonify({"status": "ERROR", "message": "Vain alikokoukset voidaan jäädyttää tai vapauttaa."}), 400

    parent_demo = mongo.recu_demos.find_one({"_id": ObjectId(parent)})
    if not parent_demo:
        return jsonify({"status": "ERROR", "message": "Emokokousta ei löytynyt; vapautus epäonnistui."}), 404

    mongo.recu_demos.update_one(
        {"_id": ObjectId(parent)},
        {"$pull": {"freezed_children": demo_id}}
    )

    return jsonify({"status": "OK", "message": "Mielenosoitus on nyt vapautettu jäädytyksestä."})




def collect_demo_data(request):
    """
    Collect demonstration data from the request form, including cover picture support.

    This function extracts and returns relevant data from the submitted form, including
    handling a cover picture as a file upload or URL.

    Parameters
    ----------
    request : flask.Request
        The incoming request object containing form data and files.

    Returns
    -------
    dict
        Dictionary of demonstration data, including the cover_picture field if provided.
    """
    # Collect basic form data
    title = request.form.get("title")
    date = request.form.get("date")
    start_time = request.form.get("start_time")
    end_time = request.form.get("end_time")
    facebook = request.form.get("facebook")
    city = request.form.get("city")
    address = request.form.get("address")
    event_type = request.form.get("type")
    # Handle route as a list (route[] in form-data)
    route = request.form.getlist("route[]") or request.form.getlist("route")
    # Fallback: if route is a single string, wrap in list
    if not route:
        single_route = request.form.get("route")
        route = [single_route] if single_route else []
    approved = request.form.get("approved") == "on"

    # Validate required fields
    if not title or not date or not city:
        raise ValueError(_("Otsikko, päivämäärä ja kaupunki ovat pakollisia kenttiä."))

    # Process organizers and tags
    organizers = collect_organizers(request)
    tags = collect_tags(request)

    description = request.form.get("description")
    latitude = request.form.get("latitude")
    longitude = request.form.get("longitude")

    # Validate latitude and longitude if provided
    if latitude and not is_valid_latitude(latitude):
        latitude = None
        flash_message(_("Virheellinen leveysaste. Asetetaan leveysasteeksi: None."))
    if longitude and not is_valid_longitude(longitude):
        longitude = None
        flash_message(_("Virheellinen pituusaste.  Asetetaan pituusasteeksi: None."))

    # Handle cover picture (file upload or URL)
    cover_picture = request.form.get("cover_picture")
    file = request.files.get("cover_picture_file")
    if file and file.filename:
        from werkzeug.utils import secure_filename
        filename = secure_filename(file.filename)
        
        # get from config
        bucket_name = current_app.config.get("S3_BUCKET")
        s3_url = upload_image_fileobj(bucket_name, file.stream, filename, "demo_preview")
        if s3_url:
            # Use the S3 URL as cover picture
            cover_picture = s3_url
        else:
            logger.error("Failed to upload cover picture to S3; falling back to provided URL if any")

    return {
        "title": title,
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "facebook": facebook,
        "city": city,
        "address": address,
        "type": event_type,
        "route": route,
        "organizers": [org.to_dict() for org in organizers],
        "approved": approved,
        "tags": tags,
        "description": description,
        "latitude": latitude,
        "longitude": longitude,
        "cover_picture": cover_picture,  # Add cover_picture to output
    }


def is_valid_latitude(lat):
    """Validate latitude value.

    Parameters
    ----------
    lat :


    Returns
    -------


    """
    try:
        lat = float(lat)
        return -90 <= lat <= 90
    except ValueError:
        return False


def is_valid_longitude(lon):
    """Validate longitude value.

    Parameters
    ----------
    lon :


    Returns
    -------


    """
    try:
        lon = float(lon)
        return -180 <= lon <= 180
    except ValueError:
        return False


def collect_organizers(request):
    """Collect organizer data from the request form.

    This function extracts multiple organizers' information from the form and returns a list
    of Organizer objects.

    Parameters
    ----------
    request :
        The incoming request object containing form data.

    Returns
    -------


    """
    organizers = []
    i = 1

    while True:
        # Extract data for each organizer using a dynamic field naming pattern
        name = request.form.get(f"organizer_name_{i}")
        website = request.form.get(f"organizer_website_{i}")
        email = request.form.get(f"organizer_email_{i}")
        organizer_id = request.form.get(f"organizer_id_{i}")

        # Stop when no name and no organization ID is provided (end of organizers)
        if not name and not organizer_id:
            break

        # Create an Organizer object and append to the list
        if organizer_id:
            try:
                organizers.append(
                    Organizer(
                        name=name.strip() if name else "",
                        email=email.strip() if email else "",
                        website=website.strip() if website else "",
                        organization_id=ObjectId(organizer_id)
                    )
                )
            except bson.errors.InvalidId as e:
                organizers.append(
                    Organizer(
                        name=name.strip() if name else "",
                        email=email.strip() if email else "",
                        website=website.strip() if website else "",
                    )
                )
                
        else:
            organizers.append(
                Organizer(
                    name=name.strip() if name else "",
                    email=email.strip() if email else "",
                    website=website.strip() if website else "",
                )
            )

        i += 1  # Move to the next organizer field

    return organizers


@admin_demo_bp.route("/delete_demo", methods=["POST"])
@login_required
@admin_required
@permission_required("DELETE_DEMO")
def delete_demo():
    """Delete a demonstration from the database."""
    json_mode = request.headers.get("Content-Type") == "application/json"

    # Extract demo_id from either form data or JSON body
    demo_id = request.form.get("demo_id")
    if not demo_id and json_mode and request.json:
        demo_id = request.json.get("demo_id")

    if not demo_id:
        error_message = "Mielenosoituksen tunniste puuttuu."
        return (
            jsonify({"status": "ERROR", "message": error_message})
            if json_mode
            else redirect(url_for("admin_demo.demo_control"))
        )

    # Fetch the demonstration from the database
    demo_data = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})

    if not demo_data:
        error_message = "Mielenosoitusta ei löytynyt."
        if json_mode:
            return jsonify({"status": "ERROR", "message": error_message})
        else:
            flash_message(error_message)
            return redirect(url_for("admin_demo.demo_control"))

    # Perform deletion
    mongo.demonstrations.delete_one({"_id": ObjectId(demo_id)})

    success_message = "Mielenosoitus poistettu onnistuneesti."
    if json_mode:
        return jsonify({"status": "OK", "message": success_message})
    else:
        flash_message(success_message)
        return redirect(url_for("admin_demo.demo_control"))


@admin_demo_bp.route("/confirm_delete_demo/<demo_id>", methods=["GET"])
@login_required
@admin_required
@permission_required("DELETE_DEMO")
def confirm_delete_demo(demo_id):
    """Render a confirmation page before deleting a demonstration.

    Parameters
    ----------
    demo_id :


    Returns
    -------


    """
    # Fetch the demonstration data from the database
    demo_data = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})

    if not demo_data:
        flash_message("Mielenosoitusta ei löytynyt.")
        return redirect(url_for("admin_demo.demo_control"))

    # Create a Demonstration instance from the fetched data
    demonstration = Demonstration.from_dict(demo_data)

    # Render the confirmation template with the demonstration details
    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}demonstrations/confirm_delete.html", demo=demonstration
    )


@admin_demo_bp.route("/accept_demo/<demo_id>", methods=["POST"])
@login_required
@admin_required
@permission_required("ACCEPT_DEMO")
def accept_demo(demo_id):
    """Accept an existing demonstration by updating its status.

    Parameters
    ----------
    demo_id : str
        The ID of the demonstration to be accepted.

    Returns
    -------
    flask.Response
        A JSON response with the operation status.
    """
    if request.headers.get("Content-Type") != "application/json":
        return (
            jsonify(
                {
                    "status": "ERROR",
                    "message": "Invalid Content-Type. Expecting application/json.",
                }
            ),
            400,
        )

    # Get the JSON data
    request_data = request.get_json()

    # Validate that the demo ID exists
    demo_data = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
    if not demo_data:
        error_msg = _("Demonstration not found.")
        return jsonify({"status": "ERROR", "message": error_msg}), 404

    demo = Demonstration.from_dict(demo_data)

    try:
        demo.approved = True
        demo.save()

        # Notify submitter if possible (always, even if already approved)
        submitter = mongo.submitters.find_one({"demonstration_id": ObjectId(demo_id)})
        if submitter and submitter.get("submitter_email"):
            email_sender.queue_email(
                template_name="demo_submitter_approved.html",
                subject="Mielenosoituksesi on hyväksytty",
                recipients=[submitter["submitter_email"]],
                context={
                    "title": demo.title,
                    "date": demo.date,
                    "city": demo.city,
                    "address": demo.address,
                },
            )

        return jsonify({"status": "OK", "message": "Demonstration accepted successfully."}), 200
    except Exception as e:
        logging.error("An error occurred while accepting the demonstration: %s", str(e))
        return jsonify({"status": "ERROR", "message": "An internal error has occurred."}), 500

@admin_demo_bp.route("/get_submitter_info/<demo_id>", methods=["GET"])
@login_required
@admin_required
@permission_required("VIEW_DEMO")
def get_submitter_info(demo_id):
    """
    Get submitter information for a demonstration.

    Parameters
    ----------
    demo_id : str
        The ID of the demonstration.

    Returns
    -------
    flask.Response
        JSON response with submitter info or error message.
    """
    submitter = mongo.submitters.find_one({"demonstration_id": ObjectId(demo_id)})
    if not submitter:
        return jsonify({"status": "ERROR", "message": "Submitter not found."}), 404

    submitter_info = {
        "submitter_name": submitter.get("submitter_name", "-"),
        "submitter_email": submitter.get("submitter_email", "-"),
        "submitter_role": submitter.get("submitter_role", "-"),
        "accept_terms": submitter.get("accept_terms", False),
        "submitted_at": str(submitter.get("submitted_at", "-")),
    }
    return jsonify({"status": "OK", "submitter": submitter_info})

from flask import Blueprint, request, jsonify
from bson import ObjectId

admin_demo_api_bp = Blueprint("admin_demo_api", __name__) #URL: /api/admin/demo/

def _require_valid_objectid(id_str):
    # Validate ObjectId
    try:
        return ObjectId(id_str)
    except:
        raise ValueError("Invalid ID")


@admin_demo_api_bp.route("/geocode", methods=["POST"])
def geocode_address():
    """
    Accepts JSON: { "address": "...", "city": "..." }
    Returns JSON: { "latitude": "...", "longitude": "..." } or error
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON payload"}), 400

    address = data.get("address")
    city = data.get("city")

    if not address or not city:
        return jsonify({"error": "Missing 'address' or 'city'"}), 400

    full_query = f"{address}, {city}, Finland"
    api_url = f"https://geocode.maps.co/search?q={full_query}&api_key={GEOCODE_API_KEY}"

    try:
        response = requests.get(api_url)
        response.raise_for_status()
        geocode_data = response.json()

        if not geocode_data:
            return jsonify({"error": "No coordinates found"}), 404

        latitude = geocode_data[0].get("lat")
        longitude = geocode_data[0].get("lon")

        if not latitude or not longitude:
            return jsonify({"error": "Coordinates missing in API response"}), 500

        return jsonify({
            "latitude": latitude,
            "longitude": longitude
        })

    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 500

@admin_demo_api_bp.route("/<demo_id>/approve", methods=["POST"])
def approve_demo(demo_id):
    demo = mongo.demonstrations.find_one({"_id": _require_valid_objectid(demo_id)})
    if not demo:
        return jsonify({"success": False, "error": "Mielenosoitus ei löytynyt"}), 404

    if demo.get("approved"):
        return jsonify({"success": False, "message": "Mielenosoitus on jo hyväksytty"}), 200

    mongo.demonstrations.update_one(
        {"_id": _require_valid_objectid(demo_id)},
        {"$set": {"approved": True, "rejected": False}}
    )

    # Notify submitter
    submitter = mongo.submitters.find_one({"demonstration_id": _require_valid_objectid(demo_id)})
    if submitter and submitter.get("submitter_email"):
        demo_url = url_for("demonstration_detail", demo_id=demo_id, _external=True)
        email_sender.queue_email(
            template_name="demo_submitter_approved.html",
            subject="Mielenosoituksesi on hyväksytty",
            recipients=[submitter["submitter_email"]],
            context={
                "title": demo.get("title", ""),
                "date": demo.get("date", ""),
                "city": demo.get("city", ""),
                "address": demo.get("address", ""),
                "url": demo_url
            },
        )

    return jsonify({"success": True, "message": "Mielenosoitus hyväksyttiin!"})

@admin_demo_api_bp.route("/<demo_id>/deny", methods=["POST"])
def reject_demo(demo_id):
    demo = mongo.demonstrations.find_one({"_id": _require_valid_objectid(demo_id)})
    if not demo:
        return jsonify({"success": False, "error": "Mielenosoitus ei löytynyt"}), 404

    if demo.get("approved") is False and demo.get("rejected") is True:
        return jsonify({"success": False, "message": "Mielenosoitus on jo hylätty"}), 200

    mongo.demonstrations.update_one(
        {"_id": _require_valid_objectid(demo_id)},
        {"$set": {"approved": False, "rejected": True}}
    )

    # Notify submitter
    submitter = mongo.submitters.find_one({"demonstration_id": _require_valid_objectid(demo_id)})
    if submitter and submitter.get("submitter_email"):
        email_sender.queue_email(
            template_name="demo_submitter_rejected.html",
            subject="Mielenosoituksesi on hylätty",
            recipients=[submitter["submitter_email"]],
            context={
                "title": demo.get("title", ""),
                "date": demo.get("date", ""),
                "city": demo.get("city", ""),
                "address": demo.get("address", ""),
            },
        )

    return jsonify({"success": True, "message": "Mielenosoitus hylättiin!"})


@admin_demo_api_bp.route("/<demo_id>/cancel", methods=["POST"])
@login_required
@admin_required
@permission_required("EDIT_DEMO")
def admin_cancel_demo(demo_id):
    try:
        demo_oid = _require_valid_objectid(demo_id)
    except ValueError:
        return jsonify({"success": False, "error": "Virheellinen tunniste"}), 400

    demo = mongo.demonstrations.find_one({"_id": demo_oid})
    if not demo:
        return jsonify({"success": False, "error": "Mielenosoitus ei löytynyt"}), 404

    reason = None
    if request.is_json:
        reason = request.json.get("reason")
    else:
        reason = request.form.get("reason")

    cancelled = cancel_demo(
        demo,
        cancelled_by={
            "user_id": str(current_user.id),
            "source": "admin_api",
            "username": getattr(current_user, "username", None),
        },
        reason=reason,
    )

    if not cancelled:
        return jsonify({"success": False, "message": "Mielenosoitus on jo merkitty perutuksi."}), 200

    return jsonify({"success": True, "message": "Mielenosoitus merkitty perutuksi."})
