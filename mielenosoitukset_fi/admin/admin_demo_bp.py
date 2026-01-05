import sys
import re
import bson
from flask import abort, current_app
import requests
from copy import deepcopy

from datetime import date, datetime, timedelta
from bson.objectid import ObjectId
import logging
from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
    make_response,
    g,
    abort,
    has_request_context,
)
from flask_login import current_user, login_required
from pymongo import DESCENDING, ReturnDocument

from flask_babel import _
from urllib.parse import quote_plus

from mielenosoitukset_fi.utils.classes import Demonstration, Organizer, MemberShip, Case
from mielenosoitukset_fi.utils.demo_cancellation import cancel_demo, queue_cancellation_links_for_demo
from mielenosoitukset_fi.utils.s3 import upload_image_fileobj
from mielenosoitukset_fi.utils.admin.demonstration import collect_tags
from mielenosoitukset_fi.utils.database import DEMO_FILTER
from mielenosoitukset_fi.utils.flashing import flash_message
from mielenosoitukset_fi.utils.variables import CITY_LIST
from mielenosoitukset_fi.utils.wrappers import admin_required, permission_required
from mielenosoitukset_fi.users.models import User
from .utils import (
    mongo,
    log_admin_action_V2,
    AdminActParser,
    _ADMIN_TEMPLATE_FOLDER,
    capture_actor_context,
    capture_request_context,
    capture_process_context,
)

from mielenosoitukset_fi.utils.database import stringify_object_ids

from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from mielenosoitukset_fi.demonstrations.audit import (
    record_demo_change,
    log_demo_audit_entry,
    save_demo_history,
    log_super_audit,
)


# Secret key for generating tokens
SECRET_KEY = "your_secret_key"

GEOCODE_API_KEY = "66df12ce96495339674278ivnc82595"  # your API key

serializer = URLSafeTimedSerializer(SECRET_KEY)
admin_demo_bp = Blueprint("admin_demo", __name__, url_prefix="/admin/demo")

from mielenosoitukset_fi.emailer.EmailSender import EmailSender
from mielenosoitukset_fi.utils.flashing import flash_message
from mielenosoitukset_fi.utils.logger import logger

email_sender = EmailSender()

MERGE_FIELD_DEFINITIONS = [
    {"key": "title", "label": _("Otsikko"), "type": "text"},
    {"key": "description", "label": _("Kuvaus"), "type": "longtext"},
    {"key": "date", "label": _("Päivämäärä"), "type": "text"},
    {"key": "start_time", "label": _("Alkuaika"), "type": "text"},
    {"key": "end_time", "label": _("Loppuaika"), "type": "text"},
    {"key": "city", "label": _("Kaupunki"), "type": "text"},
    {"key": "address", "label": _("Osoite"), "type": "text"},
    {"key": "type", "label": _("Tapahtumatyyppi"), "type": "text"},
    {"key": "route", "label": _("Reitti"), "type": "list"},
    {"key": "organizers", "label": _("Järjestäjät"), "type": "organizers"},
    {"key": "tags", "label": _("Tunnisteet"), "type": "list"},
    {"key": "facebook", "label": _("Facebook-linkki"), "type": "text"},
    {"key": "cover_picture", "label": _("Kansikuva"), "type": "text"},
    {"key": "approved", "label": _("Hyväksytty"), "type": "bool"},
    {"key": "hide", "label": _("Piilotettu"), "type": "bool"},
    {"key": "slug", "label": _("Lyhytlinkki"), "type": "text"},
    {"key": "parent", "label": _("Toistuvan demon vanhempi"), "type": "objectid"},
    {"key": "recurs", "label": _("Merkitty toistuvaksi"), "type": "bool"},
]

MERGE_BOOL_FIELDS = {"recurs", "approved", "hide"}


MAX_MERGE_COUNT = 10


def _value_is_empty(value):
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _normalize_datetime(value):
    if isinstance(value, datetime):
        return value
    return datetime.min


def _score_demo_for_guided(doc, submitter=None):
    created = _normalize_datetime(doc.get("created_datetime"))
    if created is datetime.min:
        try:
            created = doc.get("_id").generation_time
        except Exception:
            created = datetime.min
    submitter_score = 0
    if submitter:
        if submitter.get("submitter_email"):
            submitter_score = 2
        elif submitter.get("submitter_name"):
            submitter_score = 1
    return (
        1 if doc.get("approved") else 0,
        1 if not doc.get("rejected") else 0,
        1 if not doc.get("cancelled") else 0,
        1 if not doc.get("hide") else 0,
        submitter_score,
        created.timestamp(),
    )


def _demo_status_meta(doc):
    if doc.get("approved"):
        return _("Hyväksytty"), "success", _("Tämä mielenosoitus on jo hyväksytty ja näkyy julkisesti.")
    if doc.get("rejected"):
        return _("Hylätty"), "danger", _("Tämä mielenosoitus on hylätty.")
    if doc.get("cancelled"):
        return _("Peruttu"), "warning", _("Tämä mielenosoitus on merkitty perutuksi.")
    if doc.get("hide"):
        return _("Piilotettu"), "secondary", _("Tämä mielenosoitus on piilotettu listauksista.")
    return _("Kesken"), "info", _("Tämä mielenosoitus odottaa käsittelyä.")


def _case_admin_username():
    try:
        return getattr(current_user, "username", None) or "system"
    except Exception:
        return "system"


def _add_case_log(case_doc, action_type, note=None, close_case=False, new_demo_id=None, close_reason=None, metadata=None):
    if not case_doc:
        return
    case_id = case_doc["_id"] if isinstance(case_doc, dict) else case_doc
    now = datetime.utcnow()
    log_entry = {
        "timestamp": now,
        "admin": _case_admin_username(),
        "action_type": action_type,
        "note": note,
    }
    history_entry = {
        "timestamp": now,
        "action": action_type,
        "user": _case_admin_username(),
        "metadata": metadata or {},
    }
    set_fields = {"updated_at": now}
    if new_demo_id:
        try:
            set_fields["demo_id"] = ObjectId(new_demo_id)
        except Exception:
            pass
    if close_case:
        set_fields["meta.closed"] = True
        set_fields["meta.closed_at"] = now
        if close_reason:
            set_fields["meta.closed_reason"] = close_reason
    update_doc = {
        "$push": {
            "action_logs": log_entry,
            "case_history": history_entry,
        },
        "$set": set_fields,
    }
    mongo.cases.update_one({"_id": case_id}, update_doc)


def _handle_cases_after_merge(primary_id, secondary_ids, doc_map):
    try:
        all_obj_ids = [ObjectId(primary_id)] + [ObjectId(sec_id) for sec_id in secondary_ids]
    except Exception:
        return
    case_docs = list(mongo.cases.find({"demo_id": {"$in": all_obj_ids}}))
    if not case_docs:
        return

    def _case_sort_key(doc):
        return doc.get("created_at") or getattr(doc.get("_id"), "generation_time", datetime.utcnow())

    open_cases = [doc for doc in case_docs if not ((doc.get("meta") or {}).get("closed"))]
    keep_case = min(open_cases, key=_case_sort_key) if open_cases else min(case_docs, key=_case_sort_key)

    primary_title = doc_map.get(primary_id, {}).get("title") or _("tuntematon")
    closed_case_labels = []

    for case_doc in case_docs:
        case_id = case_doc["_id"]
        if case_id == keep_case["_id"]:
            note = _(
                "Mielenosoitukset yhdistettiin. Tämä tapaus jatkaa päämielenosoituksen %(title)s (%(id)s) käsittelyä."
            ) % {"title": primary_title, "id": primary_id}
            _add_case_log(
                case_doc,
                "merge_demo",
                note=note,
                close_case=False,
                new_demo_id=primary_id,
                metadata={"primary_demo_id": primary_id},
            )
            continue

        note = _(
            "Tapaus suljettiin, koska siihen liittyvä mielenosoitus yhdistettiin päämielenosoitukseen %(title)s (%(id)s)."
        ) % {"title": primary_title, "id": primary_id}
        _add_case_log(
            case_doc,
            "merge_demo_close",
            note=note,
            close_case=True,
            close_reason="merged_demo",
            metadata={"primary_demo_id": primary_id},
        )
        label = case_doc.get("running_num") or str(case_id)
        closed_case_labels.append(str(label))

    if closed_case_labels:
        summary_note = _(
            "Seuraavat tapaukset suljettiin ja linkitettiin tähän: %(cases)s."
        ) % {"cases": ", ".join(closed_case_labels)}
        _add_case_log(
            keep_case,
            "merge_demo_summary",
            note=summary_note,
            close_case=False,
            new_demo_id=primary_id,
            metadata={"closed_cases": closed_case_labels},
        )


def _log_case_decision(demo_id, demo_title, action_key, close_reason):
    try:
        demo_obj_id = ObjectId(demo_id)
    except Exception:
        return
    case_docs = list(mongo.cases.find({"demo_id": demo_obj_id}))
    if not case_docs:
        return
    status_text = _("hyväksyttiin") if action_key == "approve_demo" else _("hylättiin")
    note = _(
        "Mielenosoitus %(title)s (%(id)s) %(status)s hallintapaneelista."
    ) % {"title": demo_title or _("tuntematon"), "id": demo_id, "status": status_text}
    for case_doc in case_docs:
        already_closed = bool((case_doc.get("meta") or {}).get("closed"))
        _add_case_log(
            case_doc,
            action_key,
            note=note,
            close_case=not already_closed,
            close_reason=close_reason if not already_closed else None,
            metadata={"decision": action_key},
        )


def _split_demo_ids(raw_ids):
    if not raw_ids:
        return []
    ids = []
    for part in str(raw_ids).split(","):
        clean = part.strip()
        if clean and clean not in ids:
            ids.append(clean)
    return ids


def _normalize_objectid(value):
    if isinstance(value, ObjectId):
        return value
    try:
        if value and ObjectId.is_valid(str(value)):
            return ObjectId(str(value))
    except Exception:
        return None
    return None


def _find_demo_with_alias_support(demo_id):
    if not demo_id:
        return None
    oid = None
    if ObjectId.is_valid(str(demo_id)):
        oid = ObjectId(str(demo_id))
        demo = mongo.demonstrations.find_one({"_id": oid})
        if demo:
            return demo
        alias_demo = mongo.demonstrations.find_one({"aliases": {"$in": [oid]}})
        if alias_demo:
            return alias_demo
    return None


def _deduplicate_demos(demo_list):
    seen = set()
    unique = []
    for demo in demo_list:
        demo_id = str(demo.get("_id"))
        if not demo_id or demo_id in seen:
            continue
        seen.add(demo_id)
        unique.append(demo)
    return unique


def _json_safe(value):
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return type(value)(_json_safe(v) for v in value)
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value

@admin_demo_bp.before_request
def log_request_info():
    """Log request information before handling it."""
    log_admin_action_V2(
        AdminActParser().log_request_info(request.__dict__, current_user)
    )
    g.audit_timeline_url = url_for("admin_demo.audit_timeline")

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
    annotated_demo = deepcopy(demo_data)
    annotated_demo["_audit_note"] = {
        "action": "recommend_demo",
        "recommend_till": recommend_till,
        "timestamp": datetime.utcnow(),
        "user": _get_actor_label(),
    }
    hist_id = save_demo_history(
        str(demo_id),
        demo_data,
        annotated_demo,
    )
    log_demo_audit_entry(
        demo_id,
        action="recommend_demo",
        message=_("%(user)s suositteli mielenosoituksen") % {"user": _get_actor_label()},
        details={"recommend_till": recommend_till, "history_id": str(hist_id) if hist_id else None},
    )
    return jsonify({"status": "OK", "message": _(u"Mielenosoitus suositeltu.")})


@admin_demo_bp.route("/unrecommend_demo/<demo_id>", methods=["POST"])
@login_required
@admin_required
def unrecommend_demo(demo_id):
    """Remove a recommendation from a demonstration."""
    if not getattr(current_user, "global_admin", False):
        return jsonify({"status": "ERROR", "message": _(u"Vain ylläpitäjät voivat poistaa suosituksia.")}), 403

    demo_data = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
    if not demo_data:
        return jsonify({"status": "ERROR", "message": _(u"Mielenosoitusta ei löytynyt.")}), 404

    result = mongo.recommended_demos.delete_one({"demo_id": str(demo_id)})
    if result.deleted_count == 0:
        return jsonify({"status": "ERROR", "message": _(u"Mielenosoitus ei ole suositeltu.")}), 400

    annotated_demo = deepcopy(demo_data)
    annotated_demo["_audit_note"] = {
        "action": "unrecommend_demo",
        "timestamp": datetime.utcnow(),
        "user": _get_actor_label(),
    }
    hist_id = save_demo_history(str(demo_id), demo_data, annotated_demo)
    log_demo_audit_entry(
        demo_id,
        action="unrecommend_demo",
        message=_("%(user)s poisti mielenosoituksen suosituksen") % {"user": _get_actor_label()},
        details={"history_id": str(hist_id) if hist_id else None},
    )
    return jsonify({"status": "OK", "message": _(u"Suositus poistettu.")})


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
    demo_data = _find_demo_with_alias_support(demo_id)
    if not demo_data:
        flash_message(_("Mielenosoitusta ei löytynyt."), "error")
        return redirect(url_for("admin_demo.demo_control"))

    history = list(
        mongo.demo_edit_history.find({"demo_id": str(demo_data["_id"])}).sort("edited_at", -1)
    )
    demo = Demonstration.from_dict(demo_data)
    demo_name = demo.title
    return render_template(
        "admin/demonstrations/edit_history.html",
        history=history,
        demo_id=str(demo_data["_id"]),
        demo_name=demo_name,
        current_demo_data=demo_data
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


def _token_payload(doc: dict | None) -> dict:
    if not doc:
        return {}
    payload = {
        "token_id": str(doc.get("_id")) if doc.get("_id") else None,
        "token_hash": doc.get("token_hash"),
        "action": doc.get("action"),
        "demo_id": doc.get("demo_id"),
        "created_at": doc.get("created_at"),
        "expires_at": doc.get("expires_at"),
        "created_by": doc.get("created_by"),
        "created_by_id": doc.get("created_by_id"),
        "created_by_role": doc.get("created_by_role"),
        "created_global_admin": doc.get("created_global_admin"),
        "created_permissions": doc.get("created_permissions"),
        "created_remote_addr": doc.get("created_remote_addr"),
        "created_request_path": doc.get("created_request_path"),
        "created_request_method": doc.get("created_request_method"),
        "created_user_agent": doc.get("created_user_agent"),
        "created_process": doc.get("created_process"),
        "created_actor": doc.get("created_actor"),
        "bound_ip": doc.get("bound_ip"),
        "first_seen_at": doc.get("first_seen_at"),
        "ua_first": doc.get("ua_first"),
        "ua_last": doc.get("ua_last"),
        "used_at": doc.get("used_at"),
        "revoked": doc.get("revoked"),
        "revoked_at": doc.get("revoked_at"),
    }
    return {k: v for k, v in payload.items() if v is not None}


def _log_token_event(
    doc: dict | None,
    event: str,
    *,
    message: str | None = None,
    extra: dict | None = None,
    include_demo: bool = True,
    demo_action: str | None = None,
):
    if not doc:
        return
    payload = _token_payload(doc)
    if extra:
        payload.update(_json_safe(extra))
    demo_id = payload.get("demo_id")
    tags = ["token"]
    if doc.get("action"):
        tags.append(str(doc.get("action")))
    if demo_id:
        tags.append(f"demo:{demo_id}")

    log_super_audit(
        event_type=f"token:{event}",
        payload=payload,
        entity={"type": "token", "id": payload.get("token_id"), "demo_id": demo_id},
        tags=tags,
    )

    if include_demo and demo_id:
        log_demo_audit_entry(
            demo_id,
            action=demo_action or f"token_{event}",
            message=message or f"Token {doc.get('action')} event '{event}'",
            details=_json_safe(payload),
        )

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

def _registry_upsert_initial(token_hash: str, action: str, demo_id: str, creator: str | None = None):
    """
    Create registry doc if missing. Do not bind IP yet (bind on first GET).
    """
    now = _now_utc()
    actor_ctx = capture_actor_context()
    req_ctx = capture_request_context() if has_request_context() else None
    proc_ctx = capture_process_context()
    if not creator:
        creator = actor_ctx.get("username") or actor_ctx.get("email") or actor_ctx.get("user_id") or "[system]"
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
                "created_by": creator,
                "created_by_id": actor_ctx.get("user_id"),
                "created_by_role": actor_ctx.get("role"),
                "created_global_admin": actor_ctx.get("global_admin"),
                "created_permissions": actor_ctx.get("global_permissions"),
                "created_remote_addr": req_ctx.get("remote_addr") if req_ctx else None,
                "created_request_path": req_ctx.get("path") if req_ctx else None,
                "created_request_method": req_ctx.get("method") if req_ctx else None,
                "created_user_agent": req_ctx.get("user_agent") if req_ctx else None,
                "created_process": proc_ctx,
                "created_actor": actor_ctx,
            }
        },
        upsert=True,
    )
    details = {
        "token_hash": token_hash,
        "action": action,
        "demo_id": str(demo_id),
        "created_by": creator,
        "actor": actor_ctx,
        "request": req_ctx,
        "process": proc_ctx,
    }
    log_super_audit(
        "token:create",
        details,
        actor=actor_ctx,
        entity={"type": "token", "id": token_hash, "demo_id": str(demo_id)},
        tags=["token", action],
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
    doc = mongo[MAGIC_COLLECTION].find_one_and_update(
        {"token_hash": token_hash},
        {
            "$set": {
                "last_accessed_at": _now_utc(),
                "last_accessed_ip": _client_ip(),
                "last_accessed_ua": _user_agent(),
            }
        },
        return_document=ReturnDocument.AFTER,
    )

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
        client_ip = _client_ip()
        log_admin_action_V2({
            "event": "token_reuse_attempt",
            "action": action,
            "demo_id": doc.get("demo_id"),
            "token_hash": doc.get("token_hash", ""),
            "ip": client_ip,
            "endpoint": request.path,
        })
        _log_token_event(
            doc,
            "reuse_attempt",
            message=_("Kertakäyttölinkkiä (%(action)s) yritettiin käyttää uudelleen IP-osoitteesta %(ip)s.")
            % {"action": action, "ip": client_ip or "unknown"},
            extra={
                "ip": client_ip,
                "endpoint": request.path,
                "reason": "already_used",
            },
            demo_action="token_reuse_attempt",
        )
        response = make_response(
            render_template("admin_V2/cc/link_already_used.html", action=action),
            200,
        )
        abort(response)

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
    refreshed = mongo[MAGIC_COLLECTION].find_one({"_id": doc["_id"]})
    if refreshed:
        event = "bound" if "bound_ip" in updates["$set"] else "touch"
        _log_token_event(
            refreshed,
            event,
            message=_("Kertakäyttölinkki käytettiin ensimmäisen kerran") if event == "bound" else None,
            demo_action="token_bound" if event == "bound" else None,
        )
    return refreshed

def _mark_used(doc_id):
    updated = mongo[MAGIC_COLLECTION].find_one_and_update(
        {"_id": doc_id},
        {
            "$set": {
                "used_at": _now_utc(),
                "used_by_ip": _client_ip() if has_request_context() else None,
                "used_user_agent": _user_agent() if has_request_context() else None,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if updated:
        _log_token_event(updated, "used", message=_("Kertakäyttölinkki käytettiin"))


def _revoke_tokens_for_demo(demo_id: str, actions: list[str]):
    if not demo_id or not actions:
        return
    now = _now_utc()
    revoked = list(
        mongo[MAGIC_COLLECTION].find(
            {
                "demo_id": str(demo_id),
                "action": {"$in": actions},
                "used_at": {"$exists": False},
                "revoked": {"$ne": True},
            }
        )
    )
    if not revoked:
        return
    mongo[MAGIC_COLLECTION].update_many(
        {"_id": {"$in": [doc["_id"] for doc in revoked]}},
        {"$set": {"revoked": True, "revoked_at": now}},
    )
    for doc in revoked:
        doc["revoked_at"] = now
        _log_token_event(doc, "revoked", message=_("Kertakäyttölinkki mitätöitiin"), demo_action="token_revoked")

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
    actor = _get_actor_label()
    _registry_upsert_initial(_hash_token(token), "preview", str(demo_id), actor)
    demo = _load_demo_or_bust(demo_id)
    log_demo_audit_entry(
        demo_id,
        action="token_created",
        message=_("%(user)s loi esikatselulinkin") % {"user": actor},
        details={"token_type": "preview", "demo_date": demo.get("date"), "demo_city": demo.get("city")},
    )
    return url_for("admin_demo.preview_demo_with_token", token=token, _external=True)

def generate_demo_approve_link(demo_id: str) -> str:
    token = serializer.dumps(str(demo_id), salt="approve-demo")
    actor = _get_actor_label()
    _registry_upsert_initial(_hash_token(token), "approve", str(demo_id), actor)
    demo = _load_demo_or_bust(demo_id)
    log_demo_audit_entry(
        demo_id,
        action="token_created",
        message=_("%(user)s loi hyväksyntälinkin") % {"user": actor},
        details={"token_type": "approve", "demo_date": demo.get("date"), "demo_city": demo.get("city")},
    )
    return url_for("admin_demo.approve_demo_with_token", token=token, _external=True)

def generate_demo_reject_link(demo_id: str) -> str:
    token = serializer.dumps(str(demo_id), salt="reject-demo")
    actor = _get_actor_label()
    _registry_upsert_initial(_hash_token(token), "reject", str(demo_id), actor)
    demo = _load_demo_or_bust(demo_id)
    log_demo_audit_entry(
        demo_id,
        action="token_created",
        message=_("%(user)s loi hylkäyslinkin") % {"user": actor},
        details={"token_type": "reject", "demo_date": demo.get("date"), "demo_city": demo.get("city")},
    )
    return url_for("admin_demo.reject_demo_with_token", token=token, _external=True)

def generate_demo_edit_link_token(demo_id: str) -> str:
    token = serializer.dumps(str(demo_id), salt="edit-demo")
    actor = _get_actor_label()
    _registry_upsert_initial(_hash_token(token), "edit", str(demo_id), actor)
    demo = _load_demo_or_bust(demo_id)
    log_demo_audit_entry(
        demo_id,
        action="token_created",
        message=_("%(user)s loi muokkauslinkin") % {"user": actor},
        details={"token_type": "edit", "demo_date": demo.get("date"), "demo_city": demo.get("city")},
    )
    return url_for("admin_demo.edit_demo_with_token", token=token, _external=True)

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
    _revoke_tokens_for_demo(demo_id, ["reject", "edit"])
    _revoke_tokens_for_demo(demo_id, ["reject"])

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
    _revoke_tokens_for_demo(demo_id, ["approve", "edit"])

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
    search_query = (request.args.get("search") or "").strip()
    approved_only = (request.args.get("approved") or "false").lower() == "true"
    show_hidden = (request.args.get("show_hidden") or "false").lower() == "true"
    show_past_param = (request.args.get("show_past") or "all").lower()
    show_cancelled = (request.args.get("show_cancelled") or "false").lower() == "true"
    per_page = int(request.args.get("per_page", 20))
    page = int(request.args.get("page", 1))  # page numbers start at 1

    # Determine how we treat past demonstrations based on the filter value
    if show_past_param not in {"true", "false"}:
        show_past_filter = "all"
    else:
        show_past_filter = show_past_param

    # --- Build filter clauses ---
    filter_clauses = [
        {"$or": [{"rejected": {"$exists": False}}, {"rejected": False}]},
    ]

    if not show_cancelled:
        filter_clauses.append({"cancelled": {"$ne": True}})

    if not show_hidden:
        filter_clauses.append({"$or": [{"hide": {"$exists": False}}, {"hide": False}]})

    if show_past_filter == "false":
        filter_clauses.append({"$or": [{"in_past": {"$exists": False}}, {"in_past": False}]})

    if approved_only:
        filter_clauses.append({"approved": True})

    if search_query:
        filter_clauses.append({"title": {"$regex": search_query, "$options": "i"}})

    # Permissions
    if not current_user.global_admin:
        _where = current_user._perm_in("EDIT_DEMO")
        filter_clauses.append({
            "$or": [
                {"organizers": {"$elemMatch": {"organization_id": {"$in": [BsonObjectId(org) for org in _where]}}}},
                {"editors": current_user.id},
            ]
        })

    def build_query(extra=None):
        clauses = list(filter_clauses)
        if extra:
            if isinstance(extra, list):
                clauses.extend(extra)
            else:
                clauses.append(extra)
        if not clauses:
            return {}
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    filter_query = build_query()

    # --- Count total documents ---
    total_count = mongo.demonstrations.count_documents(filter_query)
    total_pages = (total_count + per_page - 1) // per_page  # ceil division
    # --- Fetch current page ---
    skip_count = (page - 1) * per_page

    #cursor = mongo.demonstrations.find(filter_query)
    if page == 1 and not approved_only:
        unapproved = list(mongo.demonstrations.find(
            build_query({"approved": False, "hide": False})
        ).sort([("date", 1), ("_id", 1)]))

        approved = list(mongo.demonstrations.find(
            build_query({"approved": True})
        ).sort([("date", 1), ("_id", 1)]))

        combined = _deduplicate_demos(unapproved + approved)
        total_count = len(combined)
        total_pages = max((total_count + per_page - 1) // per_page, 1)

        start = 0
        end = per_page
        demos = combined[start:end]

    else:
        # normal paging
        skip_count = (page - 1) * per_page
        demos_cursor = mongo.demonstrations.find(filter_query).sort([("date", 1), ("_id", 1)]) \
                                        .skip(skip_count).limit(per_page)
        demos = _deduplicate_demos(list(demos_cursor))

    recommended_lookup = {
        doc.get("demo_id"): True for doc in mongo.recommended_demos.find({}, {"demo_id": 1})
    }

    for demo in demos:
        demo["is_recommended"] = recommended_lookup.get(str(demo.get("_id")), False)

    # --- Determine next/previous pages ---
    prev_page = page - 1 if page > 1 else None
    next_page = page + 1 if page < total_pages else None

    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}demonstrations/dashboard.html",
        demonstrations=demos,
        search_query=search_query,
        approved_status=approved_only,
        show_hidden=show_hidden,
        show_cancelled=show_cancelled,
        show_past_filter=show_past_filter,
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

    log_demo_audit_entry(
        new_demo._id,
        action="duplicate_demo",
        message=_("%(user)s kopioi mielenosoituksen") % {"user": _get_actor_label()},
        details={"source_demo_id": demo_id},
    )

    return jsonify({"status": "OK", "new_demo_id": str(new_demo._id)})


@admin_demo_bp.route("/merge", methods=["GET", "POST"])
@login_required
@admin_required
@permission_required("EDIT_DEMO")
def merge_demos():
    if not getattr(current_user, "global_admin", False):
        flash_message(_("Vain pääylläpitäjät voivat yhdistää mielenosoituksia."), "error")
        return redirect(url_for("admin_demo.demo_control"))

    if request.method == "GET":
        selected_ids = _split_demo_ids(request.args.get("ids"))
        if len(selected_ids) < 2:
            flash_message(_("Valitse vähintään kaksi mielenosoitusta yhdistämistä varten."), "warning")
            return redirect(url_for("admin_demo.demo_control"))
        if len(selected_ids) > MAX_MERGE_COUNT:
            flash_message(
                _("Voit yhdistää kerrallaan enintään %(count)s mielenosoitusta.", count=MAX_MERGE_COUNT),
                "warning",
            )
            return redirect(url_for("admin_demo.demo_control"))

        invalid = [demo_id for demo_id in selected_ids if not ObjectId.is_valid(demo_id)]
        if invalid:
            flash_message(_("Tuntematon mielenosoituksen tunniste: %(id)s", id=invalid[0]), "error")
            return redirect(url_for("admin_demo.demo_control"))

        docs = list(mongo.demonstrations.find({"_id": {"$in": [ObjectId(d) for d in selected_ids]}}))
        doc_map = {str(doc["_id"]): doc for doc in docs}
        ordered_docs = [doc_map[demo_id] for demo_id in selected_ids if demo_id in doc_map]
        if len(ordered_docs) < 2:
            flash_message(_("Kaikkia valittuja mielenosoituksia ei löytynyt."), "error")
            return redirect(url_for("admin_demo.demo_control"))

        recommended_map = {
            doc.get("demo_id"): doc
            for doc in mongo.recommended_demos.find({"demo_id": {"$in": selected_ids}})
        }

        submitter_docs = {
            str(doc.get("demonstration_id")): doc
            for doc in mongo.submitters.find(
                {"demonstration_id": {"$in": [ObjectId(d) for d in selected_ids]}}
            )
        }
        display_demos = []
        for doc in ordered_docs:
            serialized = stringify_object_ids(doc)
            serialized["id"] = str(doc["_id"])
            serialized["is_recommended"] = serialized["id"] in recommended_map
            rec_doc = recommended_map.get(serialized["id"])
            serialized["recommendation"] = stringify_object_ids(rec_doc) if rec_doc else None
            status_label, status_variant, status_hint = _demo_status_meta(doc)
            serialized["status_label"] = status_label
            serialized["status_variant"] = status_variant
            serialized["status_hint"] = status_hint
            submitter_info = submitter_docs.get(serialized["id"])
            if submitter_info:
                serialized["submitter"] = stringify_object_ids(
                    {
                        "name": submitter_info.get("submitter_name"),
                        "email": submitter_info.get("submitter_email"),
                        "role": submitter_info.get("submitter_role"),
                        "submitted_at": submitter_info.get("submitted_at"),
                    }
                )
            else:
                serialized["submitter"] = None
            display_demos.append(serialized)

        score_order = sorted(
            doc_map.keys(),
            key=lambda did: _score_demo_for_guided(doc_map[did], submitter_docs.get(did)),
            reverse=True,
        )
        recommended_primary_id = score_order[0] if score_order else display_demos[0]["id"]

        guided_sources = {}
        for field in MERGE_FIELD_DEFINITIONS:
            chosen = recommended_primary_id
            for demo_id in score_order:
                doc = doc_map.get(demo_id)
                if doc is None:
                    continue
                value = doc.get(field["key"])
                if not _value_is_empty(value):
                    chosen = demo_id
                    break
            guided_sources[field["key"]] = chosen

        guided_recommendation = next(
            (demo_id for demo_id in score_order if recommended_map.get(demo_id)),
            "none",
        )

        merge_warnings = []
        if any(doc.get("approved") for doc in ordered_docs) and not all(doc.get("approved") for doc in ordered_docs):
            merge_warnings.append(
                _("Osa valituista mielenosoituksista on jo hyväksytty. Suosittelemme käyttämään hyväksyttyä mielenosoitusta päätapahtumana.")
            )
        if any(doc.get("rejected") for doc in ordered_docs):
            merge_warnings.append(_("Mukana on hylättyjä mielenosoituksia. Varmista, ettet vahingossa palauta niitä julkisiksi."))
        if len({doc.get("city") for doc in ordered_docs if doc.get("city")}) > 1:
            merge_warnings.append(_("Valitut mielenosoitukset sijaitsevat eri kaupungeissa. Varmista, että yhdistäminen on tarkoituksellista."))
        if len({doc.get("date") for doc in ordered_docs if doc.get("date")}) > 1:
            merge_warnings.append(_("Mielenosoituksilla on eri päivämäärät. Tarkista, kumpi tieto halutaan säilyttää."))

        field_summary_keys = {"title", "date", "start_time", "address", "description", "organizers"}
        guided_field_summary = []
        for field in MERGE_FIELD_DEFINITIONS:
            if field["key"] not in field_summary_keys:
                continue
            source_id = guided_sources.get(field["key"], recommended_primary_id)
            guided_field_summary.append(
                {
                    "key": field["key"],
                    "label": field["label"],
                    "source_id": source_id,
                    "source_title": doc_map.get(source_id, {}).get("title"),
                }
            )

        demo_lookup = {demo["id"]: demo for demo in display_demos}

        submitter_groups = {}
        for demo_id, info in submitter_docs.items():
            key = info.get("submitter_email") or info.get("submitter_name") or _("Tuntematon ilmoittaja")
            submitter_groups.setdefault(key, []).append(demo_id)
        if len(submitter_groups) > 1:
            merge_warnings.append(_("Valituilla mielenosoituksilla on eri ilmoittajat. Tarkista, etteivät nämä ole toisistaan riippumattomia tapahtumia."))
        elif not submitter_groups:
            merge_warnings.append(_("Ilmoittajatietoja ei löytynyt kaikille mielenosoituksille. Varmista, että yhdistät oikeat tapahtumat."))

        submitter_summary = [
            {
                "label": label,
                "count": len(ids),
                "demo_titles": [doc_map.get(did, {}).get("title") for did in ids],
            }
            for label, ids in submitter_groups.items()
        ]

        return render_template(
            f"{_ADMIN_TEMPLATE_FOLDER}demonstrations/merge.html",
            demos=display_demos,
            merge_fields=MERGE_FIELD_DEFINITIONS,
            selected_ids=[demo["id"] for demo in display_demos],
            default_primary=recommended_primary_id,
            guided_recommendation=guided_recommendation,
            guided_sources=guided_sources,
            merge_warnings=merge_warnings,
            guided_field_summary=guided_field_summary,
            demo_lookup=demo_lookup,
            submitter_summary=submitter_summary,
        )

    # POST
    selected_ids = request.form.getlist("demo_ids")
    selected_ids = [demo_id for demo_id in selected_ids if demo_id]
    if len(selected_ids) < 2:
        flash_message(_("Valitse vähintään kaksi mielenosoitusta."), "error")
        return redirect(url_for("admin_demo.demo_control"))
    if len(selected_ids) > MAX_MERGE_COUNT:
        flash_message(
            _("Voit yhdistää kerrallaan enintään %(count)s mielenosoitusta.", count=MAX_MERGE_COUNT),
            "error",
        )
        return redirect(url_for("admin_demo.demo_control"))

    invalid = [demo_id for demo_id in selected_ids if not ObjectId.is_valid(demo_id)]
    if invalid:
        flash_message(_("Tuntematon mielenosoituksen tunniste: %(id)s", id=invalid[0]), "error")
        return redirect(url_for("admin_demo.demo_control"))

    docs = list(mongo.demonstrations.find({"_id": {"$in": [ObjectId(d) for d in selected_ids]}}))
    doc_map = {str(doc["_id"]): doc for doc in docs}
    if len(doc_map) < 2 or len(doc_map) < len(selected_ids):
        flash_message(_("Kaikkia valittuja mielenosoituksia ei löytynyt."), "error")
        return redirect(url_for("admin_demo.demo_control"))

    primary_id = request.form.get("primary_demo_id")
    if not primary_id or primary_id not in doc_map:
        flash_message(_("Valitse päivitettävä päätapahtuma."), "error")
        return redirect(url_for("admin_demo.demo_control"))

    secondary_ids = [demo_id for demo_id in selected_ids if demo_id != primary_id]
    if not secondary_ids:
        flash_message(_("Valitse ainakin yksi yhdistettävä mielenosoitus."), "error")
        return redirect(url_for("admin_demo.demo_control"))

    primary_doc = doc_map[primary_id]
    merged_doc = deepcopy(primary_doc)
    original_primary = deepcopy(primary_doc)

    for field in MERGE_FIELD_DEFINITIONS:
        key = field["key"]
        source_id = request.form.get(f"field_source[{key}]") or primary_id
        source_doc = doc_map.get(source_id)
        if source_doc is None:
            continue
        value = deepcopy(source_doc.get(key))
        if key in MERGE_BOOL_FIELDS:
            value = bool(source_doc.get(key))
        merged_doc[key] = value

    alias_values = _build_merged_aliases(doc_map, primary_id)
    merged_doc["aliases"] = alias_values
    merged_doc["merged_into"] = None
    merged_doc["last_modified"] = datetime.utcnow()

    mongo.demonstrations.replace_one({"_id": primary_doc["_id"]}, merged_doc)

    if secondary_ids:
        mongo.demonstrations.delete_many({"_id": {"$in": [ObjectId(d) for d in secondary_ids]}})

    backup_payload = {
        "primary_demo_id": primary_id,
        "secondary_demo_ids": secondary_ids,
        "selected_demo_ids": selected_ids,
        "created_at": datetime.utcnow(),
        "actor": {
            "user_id": str(getattr(current_user, "id", "")),
            "username": getattr(current_user, "username", None),
            "email": getattr(current_user, "email", None),
        },
        "demos": {demo_id: deepcopy(doc_map.get(demo_id)) for demo_id in selected_ids if demo_id in doc_map},
    }
    backup_result = mongo.demo_merge_backups.insert_one(backup_payload)
    backup_id = str(backup_result.inserted_id) if backup_result.inserted_id else None

    recommendation_source = request.form.get("recommendation_source")
    _apply_recommendation_choice(primary_id, secondary_ids, recommendation_source)
    _repoint_related_demo_data(primary_id, secondary_ids)
    _handle_cases_after_merge(primary_id, secondary_ids, doc_map)

    merge_links = [
        {
            "demo_id": demo_id,
            "title": doc_map.get(demo_id, {}).get("title"),
            "slug": doc_map.get(demo_id, {}).get("slug"),
            "edit_history_url": url_for("admin_demo.demo_edit_history", demo_id=demo_id),
            "audit_log_url": url_for("admin_demo.view_demo_audit_log", demo_id=demo_id),
        }
        for demo_id in secondary_ids
    ]

    record_demo_change(
        primary_id,
        original_primary,
        merged_doc,
        action="merge_demo",
        message=_("%(user)s yhdisti mielenosoituksia") % {"user": _get_actor_label()},
        extra_details={"merged_from": merge_links, "backup_id": backup_id},
    )

    flash_message(_("Mielenosoitukset yhdistettiin onnistuneesti."), "success")
    return redirect(url_for("admin_demo.edit_demo", demo_id=primary_id))


def _build_merged_aliases(doc_map, primary_id):
    primary_obj = ObjectId(primary_id)
    alias_ids = set()
    for doc in doc_map.values():
        doc_id = _normalize_objectid(doc.get("_id"))
        if doc_id and doc_id != primary_obj:
            alias_ids.add(doc_id)
        for alias in doc.get("aliases") or []:
            alias_id = _normalize_objectid(alias)
            if alias_id and alias_id != primary_obj:
                alias_ids.add(alias_id)
    return list(alias_ids)


def _apply_recommendation_choice(primary_id, secondary_ids, selected_source):
    secondary_ids = secondary_ids or []
    mongo.recommended_demos.delete_many({"demo_id": {"$in": secondary_ids}})

    if not selected_source or selected_source == "none":
        mongo.recommended_demos.delete_one({"demo_id": primary_id})
        return

    source_doc = mongo.recommended_demos.find_one({"demo_id": selected_source})
    if not source_doc:
        if selected_source != primary_id:
            mongo.recommended_demos.delete_one({"demo_id": primary_id})
        return

    mongo.recommended_demos.update_one(
        {"demo_id": primary_id},
        {"$set": {"demo_id": primary_id, "recommend_till": source_doc.get("recommend_till")}},
        upsert=True,
    )
    if selected_source != primary_id:
        mongo.recommended_demos.delete_one({"demo_id": selected_source})


def _repoint_related_demo_data(primary_id, secondary_ids):
    if not secondary_ids:
        return

    primary_obj = ObjectId(primary_id)
    secondary_obj_ids = [
        _normalize_objectid(demo_id) for demo_id in secondary_ids if ObjectId.is_valid(demo_id)
    ]
    secondary_obj_ids = [oid for oid in secondary_obj_ids if oid]

    if secondary_obj_ids:
        mongo.demo_attending.update_many(
            {"demo_id": {"$in": secondary_obj_ids}},
            {"$set": {"demo_id": primary_obj}},
        )
        mongo.demo_invites.update_many(
            {"demo_id": {"$in": secondary_obj_ids}},
            {"$set": {"demo_id": primary_obj}},
        )
        mongo.demo_likes.update_many(
            {"demo_id": {"$in": secondary_obj_ids}},
            {"$set": {"demo_id": primary_obj}},
        )
        mongo.demo_reminders.update_many(
            {"demonstration_id": {"$in": secondary_obj_ids}},
            {"$set": {"demonstration_id": primary_obj}},
        )
        mongo.submitters.update_many(
            {"demonstration_id": {"$in": secondary_obj_ids}},
            {"$set": {"demonstration_id": primary_obj}},
        )
        mongo.cases.update_many(
            {"demo_id": {"$in": secondary_obj_ids}},
            {"$set": {"demo_id": primary_obj}},
        )

    mongo.demo_edit_history.update_many(
        {"demo_id": {"$in": secondary_ids}},
        {"$set": {"demo_id": primary_id}},
    )
    mongo.demo_audit_logs.update_many(
        {"demo_id": {"$in": secondary_ids}},
        {"$set": {"demo_id": primary_id}},
    )
    mongo.posted_events.update_many(
        {"demo_id": {"$in": secondary_ids}},
        {"$set": {"demo_id": primary_id}},
    )
    _ensure_posted_event_link_aliases(primary_id)

    for demo_id in secondary_ids:
        mongo.notifications.update_many(
            {"link": f"/demonstration/{demo_id}"},
            {"$set": {"link": f"/demonstration/{primary_id}"}},
        )
        mongo.demo_invites.update_many(
            {"extra.demo_id": demo_id},
            {"$set": {"extra.demo_id": primary_id}},
        )


def _ensure_posted_event_link_aliases(primary_id: str) -> None:
    canonical_links = _build_canonical_demo_links(primary_id)
    if not canonical_links:
        return

    for doc in mongo.posted_events.find({"demo_id": primary_id}):
        existing_aliases = set(doc.get("link_aliases") or [])
        updated = False
        for link in canonical_links:
            if link not in existing_aliases and link != doc.get("link"):
                existing_aliases.add(link)
                updated = True
        if updated:
            mongo.posted_events.update_one(
                {"_id": doc["_id"]},
                {"$set": {"link_aliases": sorted(existing_aliases)}},
            )


def _build_canonical_demo_links(primary_id: str) -> list[str]:
    identifiers = {str(primary_id)}
    try:
        primary_obj = ObjectId(primary_id)
    except Exception:
        primary_obj = None

    if primary_obj:
        demo_doc = mongo.demonstrations.find_one(
            {"_id": primary_obj},
            {"slug": 1},
        )
        slug_value = demo_doc.get("slug") if demo_doc else None
        if slug_value:
            identifiers.add(str(slug_value))

    canonical_links = []
    for identifier in identifiers:
        link = None
        try:
            link = url_for("demonstration_detail", demo_id=identifier, _external=True)
        except Exception:
            link = f"https://mielenosoitukset.fi/demonstration/{identifier}"
        if link:
            canonical_links.append(link)
    return canonical_links

def _summarize_analytics_doc(analytics_doc: dict | None) -> dict:
    """Return high-level counters from the aggregated analytics doc."""
    summary = {"total": 0, "last_7d": 0, "last_24h": 0}
    if not isinstance(analytics_doc, dict):
        return summary

    analytics_map = analytics_doc.get("analytics") or {}
    if not isinstance(analytics_map, dict):
        return summary

    now = datetime.utcnow()
    for day_str, hours in analytics_map.items():
        if not isinstance(hours, dict):
            continue
        try:
            day_base = datetime.strptime(day_str, "%Y-%m-%d")
        except (TypeError, ValueError):
            continue
        for hour_str, minutes in hours.items():
            if not isinstance(minutes, dict):
                continue
            try:
                hour = int(hour_str)
            except (TypeError, ValueError):
                continue
            for minute_str, count in minutes.items():
                try:
                    minute = int(minute_str)
                    amount = int(count)
                except (TypeError, ValueError):
                    continue
                summary["total"] += max(amount, 0)
                stamp = day_base.replace(hour=hour, minute=minute)
                delta = now - stamp
                if timedelta(0) <= delta <= timedelta(days=1):
                    summary["last_24h"] += amount
                if timedelta(0) <= delta <= timedelta(days=7):
                    summary["last_7d"] += amount
    return summary

def _coerce_datetime(value):
    """Best-effort conversion of common date representations to datetime."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%fZ"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    return None


def _build_mastodon_status_url(status_id: str | None) -> str | None:
    if not status_id:
        return None
    base_url = (
        current_app.config.get("MASTODON_STATUS_BASE")
        or current_app.config.get("MASTODON_WEB_BASE")
        or current_app.config.get("MASTODON_API_BASE")
        or "https://mastodon.social"
    ).rstrip("/")
    handle = current_app.config.get("MASTODON_ACCOUNT_HANDLE", "").lstrip("@")
    if not handle:
        handle = "mielenosoitukset"
    return f"{base_url}/@{handle}/{status_id}"

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
        demo_edit_access={"explicit_editors": [], "organizations": []},
        show_demo_access_panel=False,
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
    demo_edit_access = gather_demo_edit_access_info(demo_data)
    show_demo_access_panel = _user_can_manage_demo_access(current_user, demo_data)
    
        
    # Render the edit form with pre-filled demonstration details
    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}demonstrations/form.html",
        demo=demonstration,
        form_action=url_for("admin_demo.edit_demo", demo_id=demo_id, case_id=case_id),
        title=_("Muokkaa mielenosoitusta"),
        submit_button_text=_("Tallenna muutokset"),
        city_list=CITY_LIST,
        all_organizations=mongo.organizations.find(),
        case_id=case_id,
        demo_edit_access=demo_edit_access,
        show_demo_access_panel=show_demo_access_panel,
    )

@admin_demo_bp.route("/command-center/<demo_id>")
@login_required
@admin_required
@permission_required("VIEW_DEMO")
def demo_command_center(demo_id):
    """Unified view for inspecting and acting on a single demonstration."""
    demo_data = _find_demo_with_alias_support(demo_id)
    if not demo_data:
        flash_message(_("Mielenosoitusta ei löytynyt."), "error")
        return redirect(url_for("admin_demo.demo_control"))

    demo = Demonstration.from_dict(demo_data)
    demo_id_str = str(demo_data["_id"])

    submitter = mongo.submitters.find_one({"demonstration_id": demo_data["_id"]})
    recommended_doc = mongo.recommended_demos.find_one({"demo_id": demo_id_str})
    if recommended_doc:
        coerced = _coerce_datetime(recommended_doc.get("recommend_till"))
        if coerced:
            recommended_doc["recommend_till"] = coerced
    analytics_doc = mongo.d_analytics.find_one({"_id": demo_data["_id"]})
    analytics_summary = _summarize_analytics_doc(analytics_doc)

    stats = {
        "attending": mongo.demo_attending.count_documents(
            {"demo_id": demo_data["_id"], "attending": True}
        ),
        "invites": mongo.demo_invites.count_documents({"demo_id": demo_data["_id"]}),
        "reminders": mongo.demo_reminders.count_documents(
            {"demonstration_id": demo_data["_id"]}
        ),
        "mastodon_reminders": mongo.mastobot_subscriptions.count_documents(
            {"demo_id": demo_id_str}
        ),
        "cases": mongo.cases.count_documents({"demo_id": demo_data["_id"]}),
        "children": mongo.demonstrations.count_documents({"parent": demo_data["_id"]}),
        "analytics": analytics_summary,
    }

    open_cases_count = mongo.cases.count_documents(
        {"demo_id": demo_data["_id"], "meta.closed": {"$ne": True}}
    )
    suggestion_filter = {"demo_id": demo_id_str}
    active_suggestion_filter = {
        "demo_id": demo_id_str,
        "status": {"$nin": ["closed", "rejected"]},
    }
    active_suggestion_count = mongo.demo_suggestions.count_documents(
        active_suggestion_filter
    )
    suggestions = list(
        mongo.demo_suggestions.find(suggestion_filter)
        .sort("created_at", -1)
        .limit(5)
    )

    linked_cases = []
    case_cursor = (
        mongo.cases.find({"demo_id": demo_data["_id"]})
        .sort("created_at", -1)
        .limit(6)
    )
    for case_doc in case_cursor:
        case = Case.from_dict(case_doc)
        actions = list(case_doc.get("action_logs") or [])
        linked_cases.append(
            {
                "id": str(case_doc["_id"]),
                "running_num": case.running_num,
                "type": case.case_type,
                "created_at": case.created_at,
                "updated_at": case.updated_at,
                "closed": bool((case.meta or {}).get("closed")),
                "urgency": (case.meta or {}).get("urgency"),
                "latest_action": actions[-1] if actions else None,
                "meta": case.meta or {},
                "submitter": case.submitter,
                "url": url_for("admin_case.single_case", case_id=str(case_doc["_id"])),
            }
        )

    organizer_cards = []
    for organizer in demo_data.get("organizers") or []:
        if isinstance(organizer, dict):
            org_dict = dict(organizer)
        else:
            try:
                org_dict = organizer.to_dict()
            except Exception:
                org_dict = {}
        if not org_dict:
            continue
        org_id = org_dict.get("organization_id")
        org_obj_id = _normalize_objectid(org_id)
        org_doc = mongo.organizations.find_one({"_id": org_obj_id}) if org_obj_id else None
        organizer_cards.append(
            {
                "name": org_dict.get("name"),
                "email": org_dict.get("email"),
                "phone": org_dict.get("phone"),
                "organization_id": str(org_obj_id) if org_obj_id else None,
                "organization": org_doc,
                "url": org_dict.get("url"),
                "website": org_dict.get("website"),
            }
        )

    audit_logs = list(
        mongo.demo_audit_logs.find({"demo_id": demo_id_str}).sort("timestamp", -1).limit(15)
    )
    for entry in audit_logs:
        entry["_id"] = str(entry.get("_id"))

    history_entries = list(
        mongo.demo_edit_history.find({"demo_id": demo_id_str})
        .sort("edited_at", -1)
        .limit(12)
    )
    for entry in history_entries:
        entry["_id"] = str(entry.get("_id"))

    posted_filters = [{"demo_id": demo_id_str}]
    slug_value = demo_data.get("slug")
    if slug_value:
        posted_filters.append({"slug": slug_value})
    posted_events = []
    if posted_filters:
        posted_events = list(
            mongo.posted_events.find({"$or": posted_filters})
            .sort("created_at", -1)
            .limit(5)
        )
        for event in posted_events:
            event["_id"] = str(event.get("_id"))
            status_url = _build_mastodon_status_url(event.get("status_id"))
            if status_url:
                event["status_url"] = status_url

    child_demos = []
    child_cursor = (
        mongo.demonstrations.find({"parent": demo_data["_id"]}, {"title": 1, "date": 1, "slug": 1})
        .sort("date", 1)
        .limit(5)
    )
    for child in child_cursor:
        child_demos.append(
            {
                "id": str(child.get("_id")),
                "title": child.get("title"),
                "date": child.get("date"),
                "slug": child.get("slug"),
            }
        )

    parent_demo = None
    parent_id = _normalize_objectid(demo_data.get("parent"))
    if parent_id:
        parent_doc = mongo.demonstrations.find_one(
            {"_id": parent_id}, {"title": 1, "date": 1, "slug": 1}
        )
        if parent_doc:
            parent_demo = {
                "id": str(parent_id),
                "title": parent_doc.get("title"),
                "date": parent_doc.get("date"),
                "slug": parent_doc.get("slug"),
            }

    aliases = [str(alias) for alias in demo_data.get("aliases") or []]
    edit_access = gather_demo_edit_access_info(demo_data)
    status_flags = {
        "approved": bool(demo_data.get("approved")),
        "rejected": bool(demo_data.get("rejected")),
        "hidden": bool(demo_data.get("hide")),
        "cancelled": bool(demo_data.get("cancelled")),
        "recurring": bool(demo_data.get("recurs")),
        "recommended": bool(recommended_doc),
        "needs_review": not demo_data.get("approved") and not demo_data.get("rejected"),
        "cancellation_requested": bool(demo_data.get("cancellation_requested")),
    }

    location_query = " ".join(
        part for part in [demo.address, demo.city if getattr(demo, "city", None) else None] if part
    )
    map_url = (
        f"https://www.google.com/maps/search/?api=1&query={quote_plus(location_query)}"
        if location_query
        else None
    )

    public_identifier = demo.slug or demo_id_str
    public_url = url_for("demonstration_detail", demo_id=public_identifier)

    action_endpoints = {
        "approve": {"url": url_for("admin_demo_api.approve_demo", demo_id=demo_id_str), "method": "POST"},
        "reject": {"url": url_for("admin_demo_api.reject_demo", demo_id=demo_id_str), "method": "POST"},
        "cancel": {"url": url_for("admin_demo_api.admin_cancel_demo", demo_id=demo_id_str), "method": "POST"},
        "recommend": {"url": url_for("admin_demo.recommend_demo", demo_id=demo_id_str), "method": "POST"},
        "unrecommend": {"url": url_for("admin_demo.unrecommend_demo", demo_id=demo_id_str), "method": "POST"},
        "duplicate": {"url": url_for("admin_demo.duplicate_demo", demo_id=demo_id_str), "method": "POST"},
        "screenshot": {"url": url_for("admin_demo.trigger_ss", demo_id=demo_id_str), "method": "GET"},
    }
    links = {
        "edit": url_for("admin_demo.edit_demo", demo_id=demo_id_str),
        "history": url_for("admin_demo.demo_edit_history", demo_id=demo_id_str),
        "audit": url_for("admin_demo.view_demo_audit_log", demo_id=demo_id_str),
        "analytics": url_for("admin.demo_analytics", demo_id=demo_id_str),
    }

    permissions = {
        "can_edit": current_user.has_permission("EDIT_DEMO"),
        "can_delete": current_user.has_permission("DELETE_DEMO"),
        "can_accept": current_user.has_permission("ACCEPT_DEMO"),
        "can_generate_link": current_user.has_permission("GENERATE_EDIT_LINK"),
        "can_recommend": getattr(current_user, "global_admin", False),
        "can_view_analytics": current_user.has_permission("VIEW_ANALYTICS"),
    }

    cancellation_context = {
        "requested": demo_data.get("cancellation_requested"),
        "requested_at": demo_data.get("cancellation_requested_at"),
        "reason": demo_data.get("cancellation_reason"),
        "requested_by": demo_data.get("cancellation_requested_by"),
        "cancelled_at": demo_data.get("cancelled_at"),
        "cancelled_by": demo_data.get("cancelled_by"),
    }

    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}demonstrations/command_center.html",
        demo=demo,
        demo_raw=demo_data,
        demo_id=demo_id_str,
        submitter=submitter,
        stats=stats,
        analytics_doc=analytics_doc or {},
        analytics_summary=analytics_summary,
        audit_logs=audit_logs,
        history_entries=history_entries,
        linked_cases=linked_cases,
        suggestions=suggestions,
        recommended=recommended_doc,
        organizer_cards=organizer_cards,
        edit_access=edit_access,
        show_access_panel=_user_can_manage_demo_access(current_user, demo_data),
        posted_events=posted_events,
        child_demos=child_demos,
        parent_demo=parent_demo,
        aliases=aliases,
        action_endpoints=action_endpoints,
        resource_links=links,
        permissions=permissions,
        status_flags=status_flags,
        public_url=public_url,
        map_url=map_url,
        cancellation_context=cancellation_context,
        open_cases_count=open_cases_count,
        active_suggestion_count=active_suggestion_count,
        public_identifier=public_identifier,
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
        edit_link = data.get("edit_link") or generate_demo_edit_link_token(demo_id)

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
        edit_link = generate_demo_edit_link_token(demo_id)
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
    demo_edit_access = gather_demo_edit_access_info(demo_data)

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
        demo_edit_access=demo_edit_access,
        show_demo_access_panel=False,
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


def _get_actor_label():
    return getattr(current_user, "username", None) or getattr(current_user, "email", None) or str(getattr(current_user, "id", "unknown"))


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
            prev_demo = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
            if prev_demo:
                merged_data = _deep_merge(prev_demo, demonstration_data)
                demo = Demonstration.from_dict(merged_data)
                demo.save()
                hist_id = record_demo_change(
                    demo_id,
                    prev_demo,
                    merged_data,
                    action="edit_demo",
                    message=_("%(user)s muokkasi mielenosoitusta") % {"user": _get_actor_label()},
                    case_id=case_id,
                )

                if case_id and hist_id:
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
            log_demo_audit_entry(
                insert_result.inserted_id,
                action="create_demo",
                message=_("%(user)s loi mielenosoituksen") % {"user": _get_actor_label()},
                details={"title": demonstration_data.get("title")}
            )
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

def gather_demo_edit_access_info(demo_doc: dict) -> dict:
    """Collect users who have edit permissions for a specific demo."""
    explicit_editors = []
    seen_explicit = set()

    def _format_user(user_obj, **extra):
        data = {
            "id": str(user_obj._id),
            "displayname": user_obj.displayname or user_obj.username,
            "username": user_obj.username,
            "email": user_obj.email,
            "role": user_obj.role,
        }
        data.update(extra)
        return data

    def _resolve_editor_id(raw):
        if isinstance(raw, dict):
            if "$oid" in raw:
                return raw["$oid"]
            if "_id" in raw:
                return raw["_id"]
            if "id" in raw:
                return raw["id"]
        return raw

    def _build_user(uid):
        oid = _normalize_objectid(_resolve_editor_id(uid))
        if not oid:
            return None
        try:
            user = User.from_OID(oid)
        except Exception:
            return None
        return user

    editors = demo_doc.get("editors") or []
    for editor in editors:
        user = _build_user(editor)
        if not user:
            continue
        user_id = str(user._id)
        if user_id in seen_explicit:
            continue
        seen_explicit.add(user_id)
        explicit_editors.append(_format_user(user))

    organizations = []
    seen_org_ids = set()
    for organizer in demo_doc.get("organizers") or []:
        org_id = None
        if isinstance(organizer, dict):
            org_id = organizer.get("organization_id")
        else:
            org_id = getattr(organizer, "organization_id", None)
        oid = _normalize_objectid(org_id)
        if not oid or str(oid) in seen_org_ids:
            continue
        seen_org_ids.add(str(oid))
        org_doc = mongo.organizations.find_one({"_id": oid}, {"name": 1})
        org_name = org_doc.get("name") if org_doc else str(oid)

        members = []
        seen_member_ids = set()
        for membership in MemberShip.all_in_organization(oid):
            if "EDIT_DEMO" not in membership.permissions:
                continue
            member_user = None
            try:
                member_user = User.from_OID(membership.user_id)
            except Exception:
                continue
            member_id = str(member_user._id)
            if member_id in seen_member_ids:
                continue
            seen_member_ids.add(member_id)
            members.append(
                _format_user(
                    member_user,
                    membership_role=membership.role,
                    membership_permissions=membership.permissions,
                )
            )

        if members:
            organizations.append(
                {
                    "organization_id": str(oid),
                    "name": org_name,
                    "members": members,
                }
            )

    return {"explicit_editors": explicit_editors, "organizations": organizations}


def _user_can_manage_demo_access(user, demo_doc: dict) -> bool:
    """Return True if user should see the access panel."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "global_admin", False):
        return True
    for organizer in demo_doc.get("organizers") or []:
        org_id = None
        if isinstance(organizer, dict):
            org_id = organizer.get("organization_id")
        else:
            org_id = getattr(organizer, "organization_id", None)
        if not org_id:
            continue
        membership = user.membership_for(org_id)
        if membership and membership.role == "owner":
            return True
    return False


@admin_demo_bp.route("/<demo_id>/editors/add", methods=["POST"])
@login_required
@admin_required
@permission_required("EDIT_DEMO")
def add_demo_editor(demo_id):
    """Allow inviting an existing user to become an explicit demo editor."""
    identifier = (request.form.get("identifier") or "").strip()
    if not identifier:
        flash_message(_("Syötä käyttäjänimi tai sähköpostiosoite."), "error")
        return redirect(request.referrer or url_for("admin_demo.edit_demo", demo_id=demo_id))

    demo_obj = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
    if not demo_obj:
        flash_message(_("Mielenosoitusta ei löytynyt."), "error")
        return redirect(request.referrer or url_for("admin_demo.demo_control"))

    user_doc = None
    if ObjectId.is_valid(identifier):
        user_doc = mongo.users.find_one({"_id": ObjectId(identifier)})
    if not user_doc:
        user_doc = mongo.users.find_one({"email": identifier})
    if not user_doc:
        user_doc = mongo.users.find_one({"username": identifier})
    if not user_doc:
        flash_message(_("Käyttäjää ei löytynyt."), "error")
        return redirect(request.referrer or url_for("admin_demo.edit_demo", demo_id=demo_id))

    user_id = str(user_doc["_id"])
    result = mongo.demonstrations.update_one(
        {"_id": ObjectId(demo_id)},
        {"$addToSet": {"editors": user_id}}
    )

    if result.modified_count:
        log_demo_audit_entry(
            demo_id,
            action="grant_editor",
            message=_("%(actor)s antoi muokkausoikeuden käyttäjälle %(target)s vierailevan muokkaajan roolissa.") % {
                "actor": _get_actor_label(),
                "target": user_doc.get("username") or user_doc.get("email") or user_id,
            },
            details={"user_id": user_id},
        )
        flash_message(_("Käyttäjä lisätty muokkaajaksi."), "success")
    else:
        flash_message(_("Käyttäjä on jo listalla."), "info")

    return redirect(request.referrer or url_for("admin_demo.edit_demo", demo_id=demo_id))


@admin_demo_bp.route("/<demo_id>/editors/remove", methods=["POST"])
@login_required
@admin_required
@permission_required("EDIT_DEMO")
def remove_demo_editor(demo_id):
    demo_obj = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
    if not demo_obj:
        flash_message(_("Mielenosoitusta ei löytynyt."), "error")
        return redirect(request.referrer or url_for("admin_demo.demo_control"))

    if not _user_can_manage_demo_access(current_user, demo_obj):
        flash_message(_("Sinulla ei ole oikeutta poistaa muokkaajia."), "error")
        return redirect(request.referrer or url_for("admin_demo.edit_demo", demo_id=demo_id))

    user_id = request.form.get("user_id")
    if not user_id:
        flash_message(_("Käyttäjän tunniste puuttuu."), "error")
        return redirect(request.referrer or url_for("admin_demo.edit_demo", demo_id=demo_id))

    result = mongo.demonstrations.update_one(
        {"_id": ObjectId(demo_id)},
        {"$pull": {"editors": user_id}}
    )
    if result.modified_count:
        log_demo_audit_entry(
            demo_id,
            action="revoke_editor",
            message=_("%(actor)s poisti muokkaajan %(target)s oikeudet.") % {
                "actor": _get_actor_label(),
                "target": user_id,
            },
            details={"user_id": user_id},
        )
        flash_message(_("Muokkaaja poistettu."), "success")
    else:
        flash_message(_("Käyttäjä ei ole muokkaajalistalla."), "info")

    return redirect(request.referrer or url_for("admin_demo.edit_demo", demo_id=demo_id))

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
        is_private = request.form.get(f"organizer_is_private_{i}") == "on"
        show_name_public = request.form.get(f"organizer_show_name_{i}") == "on"
        show_email_public = request.form.get(f"organizer_show_email_{i}") == "on"

        # Ensure non-private organizers keep their details visible unless explicitly hidden
        if not is_private and request.form.get(f"organizer_show_name_{i}") is None:
            show_name_public = True
        if not is_private and request.form.get(f"organizer_show_email_{i}") is None:
            show_email_public = True

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
                        organization_id=ObjectId(organizer_id),
                        is_private=False,
                        show_name_public=show_name_public,
                        show_email_public=show_email_public,
                    )
                )
            except bson.errors.InvalidId as e:
                organizers.append(
                    Organizer(
                        name=name.strip() if name else "",
                        email=email.strip() if email else "",
                        website=website.strip() if website else "",
                        is_private=is_private,
                        show_name_public=show_name_public,
                        show_email_public=show_email_public,
                    )
                )
                
        else:
            organizers.append(
                Organizer(
                    name=name.strip() if name else "",
                    email=email.strip() if email else "",
                    website=website.strip() if website else "",
                    is_private=is_private,
                    show_name_public=show_name_public,
                    show_email_public=show_email_public,
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

    record_demo_change(
        demo_id,
        demo_data,
        {},
        action="delete_demo",
        message=_("%(user)s poisti mielenosoituksen") % {"user": _get_actor_label()},
    )

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


@admin_demo_bp.route("/<demo_id>/audit_log", methods=["GET"])
@login_required
@admin_required
@permission_required("VIEW_DEMO")
def view_demo_audit_log(demo_id):
    demo = _find_demo_with_alias_support(demo_id)
    if not demo:
        flash_message(_("Mielenosoitusta ei löytynyt."), "error")
        return redirect(url_for("admin_demo.demo_control"))

    entries = list(
        mongo.demo_audit_logs.find({"demo_id": str(demo["_id"])}).sort("timestamp", -1)
    )
    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}demonstrations/audit_log.html",
        demo=demo,
        entries=entries,
    )


@admin_demo_bp.route("/audit/logs", methods=["GET"])
@login_required
@admin_required
@permission_required("VIEW_DEMO")
def audit_timeline():
    """Central timeline view for latest demo audit log entries."""
    limit = min(max(int(request.args.get("limit", 200)), 1), 500)
    demo_filter = (request.args.get("demo_id") or "").strip()
    automatic = (request.args.get("automatic") or "all").lower()

    query = {}
    obj_id = None
    if demo_filter:
        if ObjectId.is_valid(demo_filter):
            obj_id = ObjectId(demo_filter)
            query["demo_id"] = str(obj_id)
        else:
            query["demo_id"] = demo_filter

    entries = list(mongo.demo_audit_logs.find(query).sort("timestamp", -1).limit(limit))

    def _is_automatic(entry):
        if entry.get("automatic"):
            return True
        details = entry.get("details") or {}
        if details.get("automatic"):
            return True
        username = (entry.get("username") or "").strip()
        if username.startswith("[JOB]"):
            return True
        actor = entry.get("actor") or {}
        actor_name = (actor.get("username") or "").strip()
        return actor_name.startswith("[JOB]")

    if automatic == "manual":
        entries = [e for e in entries if not _is_automatic(e)]
    elif automatic == "auto":
        entries = [e for e in entries if _is_automatic(e)]

    # Attach demo details for quick reference
    demo_map = {}
    demo_ids = {entry.get("demo_id") for entry in entries if entry.get("demo_id")}
    obj_ids = []
    for did in demo_ids:
        if ObjectId.is_valid(did):
            obj_ids.append(ObjectId(did))
    if obj_ids:
        for doc in mongo.demonstrations.find({"_id": {"$in": obj_ids}}, {"title": 1, "city": 1, "date": 1}):
            demo_map[str(doc["_id"])] = doc

    for entry in entries:
        info = demo_map.get(entry.get("demo_id"))
        if info:
            entry["demo_title"] = info.get("title")
            entry["demo_city"] = info.get("city")
            entry["demo_date"] = info.get("date")
        entry["is_automatic"] = _is_automatic(entry)

    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}demonstrations/audit_timeline.html",
        entries=entries,
        limit=limit,
        filter_demo_id=demo_filter,
        automatic_filter=automatic,
    )


@admin_demo_bp.route("/tokens", methods=["GET", "POST"])
@login_required
@admin_required
def manage_magic_tokens():
    if not getattr(current_user, "global_admin", False):
        abort(403)

    if request.method == "POST":
        if request.form.get("revoke_all") == "1":
            revoke_filter = {
                "revoked": {"$ne": True},
                "$or": [
                    {"used_at": {"$exists": False}},
                    {"used_at": None},
                ],
            }
            tokens_to_revoke = list(
                mongo[MAGIC_COLLECTION].find(
                    revoke_filter, {"demo_id": 1, "action": 1}
                )
            )
            result = mongo[MAGIC_COLLECTION].update_many(
                revoke_filter,
                {"$set": {"revoked": True, "revoked_at": _now_utc()}},
            )
            flash_message(_("{} linkkiä mitätöitiin.").format(result.modified_count), "success")
            actor = _get_actor_label()
            for token in tokens_to_revoke:
                log_demo_audit_entry(
                    token.get("demo_id"),
                    action="token_revoked",
                    message=_("%(user)s mitätöi linkin massatoiminnolla").format(user=actor),
                    details={
                        "token_id": str(token.get("_id")),
                        "token_type": token.get("action"),
                        "mass_action": True,
                    },
                )
        else:
            token_id = request.form.get("token_id")
            if token_id and ObjectId.is_valid(token_id):
                token_doc = mongo[MAGIC_COLLECTION].find_one_and_update(
                    {"_id": ObjectId(token_id)},
                    {"$set": {"revoked": True, "revoked_at": _now_utc()}},
                    return_document=True,
                )
                flash_message(_("Linkki mitätöitiin."), "success")
                if token_doc:
                    log_demo_audit_entry(
                        token_doc.get("demo_id"),
                        action="token_revoked",
                        message=_("%(user)s mitätöi yksittäisen linkin").format(user=_get_actor_label()),
                        details={"token_id": token_id, "token_type": token_doc.get("action")},
                    )
        return redirect(url_for("admin_demo.manage_magic_tokens"))

    filters = {
        "action": (request.args.get("action") or "").strip(),
        "demo_id": (request.args.get("demo_id") or "").strip(),
        "status": (request.args.get("status") or "").strip(),
    }

    query = {}
    if filters["action"]:
        query["action"] = filters["action"]
    if filters["demo_id"]:
        query["demo_id"] = filters["demo_id"]
    if filters["status"] == "active":
        query["revoked"] = {"$ne": True}
        query["used_at"] = {"$exists": False}
    elif filters["status"] == "revoked":
        query["revoked"] = True
    elif filters["status"] == "used":
        query["used_at"] = {"$exists": True}

    tokens = list(
        mongo[MAGIC_COLLECTION]
        .find(query)
        .sort("created_at", -1)
        .limit(300)
    )

    summary_pipeline = []
    if query:
        summary_pipeline.append({"$match": query})
    summary_pipeline.append({"$group": {"_id": "$action", "count": {"$sum": 1}}})
    action_counts = {
        doc["_id"] or "unknown": doc.get("count", 0)
        for doc in mongo[MAGIC_COLLECTION].aggregate(summary_pipeline)
    }

    demo_map = {}
    demo_ids = {t.get("demo_id") for t in tokens if t.get("demo_id")}
    obj_ids = [ObjectId(d) for d in demo_ids if ObjectId.is_valid(d)]
    if obj_ids:
        for doc in mongo.demonstrations.find({"_id": {"$in": obj_ids}}, {"title": 1, "date": 1, "city": 1}):
            demo_map[str(doc["_id"])] = doc

    def _fmt(dt):
        if isinstance(dt, datetime):
            return dt.strftime("%d.%m.%Y %H:%M")
        return "-"

    for token in tokens:
        token["_id"] = str(token["_id"])
        demo_info = demo_map.get(token.get("demo_id"))
        if demo_info:
            token["demo_title"] = demo_info.get("title")
            token["demo_date"] = demo_info.get("date")
            token["demo_city"] = demo_info.get("city")
        token["created_by_display"] = token.get("created_by") or "-"
        token["created_at_display"] = _fmt(token.get("created_at"))
        token["expires_at_display"] = _fmt(token.get("expires_at"))
        token["first_seen_display"] = _fmt(token.get("first_seen_at"))
        token["used_at_display"] = _fmt(token.get("used_at"))
        token["revoked_at_display"] = _fmt(token.get("revoked_at"))
        token["ua_first_display"] = token.get("ua_first")
        token["ua_last_display"] = token.get("ua_last")

    distinct_actions = sorted(mongo[MAGIC_COLLECTION].distinct("action"))

    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}demonstrations/magic_tokens.html",
        tokens=tokens,
        filters=filters,
        actions=distinct_actions,
        action_counts=action_counts,
    )


@admin_demo_bp.route("/super_audit/logs", methods=["GET"])
@login_required
@admin_required
def view_super_audit_logs():
    if not getattr(current_user, "global_admin", False):
        abort(403)

    args = request.args
    limit = min(max(int(args.get("limit", 200)), 10), 1000)
    query = {}
    event = (args.get("event") or "").strip()
    if event:
        query["event"] = event
    path = (args.get("path") or "").strip()
    if path:
        query["request.path"] = {"$regex": re.escape(path), "$options": "i"}
    method = (args.get("method") or "").strip().upper()
    if method:
        query["request.method"] = method
    search_text = (args.get("q") or "").strip()
    if search_text:
        query["payload"] = {"$regex": re.escape(search_text), "$options": "i"}

    entries = list(
        mongo.super_audit_logs.find(query).sort("timestamp", -1).limit(limit)
    )
    for entry in entries:
        entry["_id"] = str(entry.get("_id"))
        ts = entry.get("timestamp")
        entry["timestamp_str"] = ts.strftime("%d.%m.%Y %H:%M:%S") if isinstance(ts, datetime) else "-"
        entry["payload"] = _json_safe(entry.get("payload"))
        if entry.get("request"):
            entry["request"] = _json_safe(entry.get("request"))
        if entry.get("entity"):
            entry["entity"] = _json_safe(entry.get("entity"))

    distinct_events = sorted(mongo.super_audit_logs.distinct("event"))

    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}super_audit/logs.html",
        entries=entries,
        events=distinct_events,
        filters={"event": event, "path": path, "method": method, "q": search_text, "limit": limit},
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


@admin_demo_bp.route("/submission_errors", methods=["GET"])
@admin_required
def submission_errors_dashboard():
    args = request.args
    filters = []
    selected = {}

    error_code = (args.get("error_code") or "").strip()
    if error_code:
        filters.append({"error_code": error_code})
        selected["error_code"] = error_code

    status_raw = (args.get("status") or "").strip()
    if status_raw:
        try:
            status_value = int(status_raw)
            filters.append({"status": status_value})
            selected["status"] = status_raw
        except ValueError:
            pass

    ip_value = (args.get("ip") or "").strip()
    if ip_value:
        filters.append({"ip": ip_value})
        selected["ip"] = ip_value

    user_id = (args.get("user_id") or "").strip()
    if user_id:
        filters.append({"user.id": user_id})
        selected["user_id"] = user_id

    request_path = (args.get("path") or "").strip()
    if request_path:
        filters.append({"request_path": {"$regex": re.escape(request_path), "$options": "i"}})
        selected["path"] = request_path

    query_text = (args.get("q") or "").strip()
    if query_text:
        filters.append({"message": {"$regex": re.escape(query_text), "$options": "i"}})
        selected["q"] = query_text

    created_bounds = {}
    start_date_raw = (args.get("start_date") or "").strip()
    if start_date_raw:
        try:
            created_bounds["$gte"] = datetime.strptime(start_date_raw, "%Y-%m-%d")
            selected["start_date"] = start_date_raw
        except ValueError:
            pass

    end_date_raw = (args.get("end_date") or "").strip()
    if end_date_raw:
        try:
            created_bounds["$lt"] = datetime.strptime(end_date_raw, "%Y-%m-%d") + timedelta(days=1)
            selected["end_date"] = end_date_raw
        except ValueError:
            pass

    if created_bounds:
        filters.append({"created_at": created_bounds})

    query = {"$and": filters} if filters else {}

    logs_cursor = (
        mongo.demo_submission_errors.find(query)
        .sort("created_at", DESCENDING)
        .limit(200)
    )

    logs = []
    for log in logs_cursor:
        log["_id"] = str(log.get("_id"))
        created = log.get("created_at")
        if isinstance(created, datetime):
            log["created_at_str"] = created.strftime("%d.%m.%Y %H:%M:%S")
        else:
            log["created_at_str"] = "-"
        logs.append(log)

    total_count = mongo.demo_submission_errors.count_documents(query)

    pipeline = []
    if query:
        pipeline.append({"$match": query})
    pipeline.extend(
        [
            {"$group": {"_id": "$error_code", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5},
        ]
    )
    error_stats = list(mongo.demo_submission_errors.aggregate(pipeline))
    error_stats = [
        {"code": stat.get("_id") or _("Tuntematon"), "count": stat.get("count", 0)}
        for stat in error_stats
    ]

    error_codes = sorted(
        [code for code in mongo.demo_submission_errors.distinct("error_code") if code]
    )
    status_options = sorted(
        [status for status in mongo.demo_submission_errors.distinct("status") if status is not None]
    )

    return render_template(
        "admin_V2/demonstrations/submission_errors.html",
        logs=logs,
        filters=selected,
        filters_active=bool(selected),
        error_codes=error_codes,
        status_options=status_options,
        total_count=total_count,
        error_stats=error_stats,
    )

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

    updated_demo = demo.copy()
    updated_demo["approved"] = True
    updated_demo["rejected"] = False
    record_demo_change(
        demo_id,
        demo,
        updated_demo,
        action="approve_demo",
        message=_("%(user)s hyväksyi mielenosoituksen") % {"user": _get_actor_label()},
    )
    _revoke_tokens_for_demo(demo_id, ["reject"])

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

    _log_case_decision(demo_id, demo.get("title"), "approve_demo", close_reason="demo_approved")
    _revoke_tokens_for_demo(demo_id, ["reject", "edit"])

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
    _revoke_tokens_for_demo(demo_id, ["approve"])

    updated_demo = demo.copy()
    updated_demo["approved"] = False
    updated_demo["rejected"] = True
    record_demo_change(
        demo_id,
        demo,
        updated_demo,
        action="reject_demo",
        message=_("%(user)s hylkäsi mielenosoituksen") % {"user": _get_actor_label()},
    )
    _revoke_tokens_for_demo(demo_id, ["approve"])

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

    _log_case_decision(demo_id, demo.get("title"), "reject_demo", close_reason="demo_rejected")
    _revoke_tokens_for_demo(demo_id, ["approve", "edit"])

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

    updated_demo = mongo.demonstrations.find_one({"_id": demo_oid}) or demo
    record_demo_change(
        demo_id,
        demo,
        updated_demo,
        action="cancel_demo",
        message=_("%(user)s perui mielenosoituksen") % {"user": _get_actor_label()},
        extra_details={"reason": reason} if reason else None,
    )

    return jsonify({"success": True, "message": "Mielenosoitus merkitty perutuksi."})


@admin_demo_api_bp.route("/bulk_cancel", methods=["POST"])
@login_required
@admin_required
@permission_required("EDIT_DEMO")
def bulk_cancel_demos():
    payload = request.get_json(silent=True) or {}
    demo_ids = payload.get("demo_ids") or []
    reason = payload.get("reason")

    if not isinstance(demo_ids, list) or not demo_ids:
        return jsonify({"success": False, "error": _(u"Valitse vähintään yksi mielenosoitus.")}), 400

    results = []
    cancelled_count = 0

    for raw_id in demo_ids:
        entry = {"demo_id": raw_id}
        try:
            demo_oid = _require_valid_objectid(raw_id)
        except ValueError:
            entry["status"] = "invalid_id"
            entry["message"] = _(u"Virheellinen tunniste.")
            results.append(entry)
            continue

        demo = mongo.demonstrations.find_one({"_id": demo_oid})
        if not demo:
            entry["status"] = "not_found"
            entry["message"] = _(u"Mielenosoitusta ei löytynyt.")
            results.append(entry)
            continue

        cancelled = cancel_demo(
            demo,
            cancelled_by={
                "user_id": str(current_user.id),
                "source": "admin_bulk",
                "username": getattr(current_user, "username", None),
            },
            reason=reason,
        )

        if cancelled:
            entry["status"] = "cancelled"
            entry["message"] = _(u"Merkitty perutuksi.")
            cancelled_count += 1
            updated_demo = mongo.demonstrations.find_one({"_id": demo_oid}) or demo
            record_demo_change(
                raw_id,
                demo,
                updated_demo,
                action="cancel_demo",
                message=_("%(user)s perui mielenosoituksen (bulk)") % {"user": _get_actor_label()},
                extra_details={"reason": reason, "bulk": True},
            )
        else:
            entry["status"] = "already_cancelled"
            entry["message"] = _(u"Mielenosoitus on jo merkitty perutuksi.")
            log_demo_audit_entry(
                raw_id,
                action="cancel_demo_attempt",
                message=_("%(user)s yritti perua jo perutun mielenosoituksen") % {"user": _get_actor_label()},
                details={"reason": reason, "bulk": True},
            )

        results.append(entry)

    return jsonify(
        {
            "success": cancelled_count > 0,
            "cancelled_count": cancelled_count,
            "results": results,
        }
    )
