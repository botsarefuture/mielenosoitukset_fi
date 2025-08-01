from flask import abort
"""
Edit History and Diff Views
"""
# ...existing code...

# --- Edit History and Diff Views ---
# These must be placed after all imports and after admin_demo_bp is defined


# Approve demo with token (magic link for admins)

from datetime import date, datetime
from bson.objectid import ObjectId
import logging
from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from flask_babel import _

from mielenosoitukset_fi.utils.classes import Demonstration, Organizer
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
    return render_template(
        "admin/demonstrations/edit_history.html",
        history=history,
        demo_id=demo_id
    )

@admin_demo_bp.route("/view_demo_diff/<demo_id>/<history_id>", methods=["GET"])
@login_required
@admin_required
@permission_required("EDIT_DEMO")
def view_demo_diff(demo_id, history_id):
    """
    View the diff between a historical and current demonstration version.

    Parameters
    ----------
    demo_id : str
        The ID of the demonstration.
    history_id : str
        The ID of the history entry.

    Returns
    -------
    flask.Response
        Renders the diff page.
    """
    from bson.objectid import ObjectId as BsonObjectId
    hist = mongo.demo_edit_history.find_one({"_id": BsonObjectId(history_id)})
    if not hist:
        abort(404)
    old = hist.get("demo_data", {})
    new = mongo.demonstrations.find_one({"_id": BsonObjectId(demo_id)})
    if not new:
        abort(404)
    import difflib
    from markupsafe import Markup

    def html_diff(a, b):
        """Generate an HTML diff for two values, line by line and character by character.

        Parameters
        ----------
        a : Any
            Old value.
        b : Any
            New value.

        Returns
        -------
        str
            HTML-formatted diff.
        """
        a_str = str(a) if a is not None else ""
        b_str = str(b) if b is not None else ""
        a_lines = a_str.splitlines() or [""]
        b_lines = b_str.splitlines() or [""]
        html = []
        sm = difflib.SequenceMatcher(None, a_lines, b_lines)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                for line in a_lines[i1:i2]:
                    html.append('<span class="diff-unchanged">{}</span>'.format(line))
            elif tag == "replace":
                # If the number of lines is the same, show char diff on the same row
                if (i2 - i1) == (j2 - j1):
                    for idx in range(i2 - i1):
                        html.append('<span class="diff-line">')
                        html.append(diff_chars(a_lines[i1 + idx], b_lines[j1 + idx]))
                        html.append('</span>')
                else:
                    for line in a_lines[i1:i2]:
                        html.append('<span class="diff-remove">{}</span>'.format(line))
                    for line in b_lines[j1:j2]:
                        html.append('<span class="diff-add">{}</span>'.format(line))
            elif tag == "delete":
                for line in a_lines[i1:i2]:
                    html.append('<span class="diff-remove">{}</span>'.format(line))
            elif tag == "insert":
                for line in b_lines[j1:j2]:
                    html.append('<span class="diff-add">{}</span>'.format(line))
        return Markup("".join(html))

    def diff_chars(a, b):
        """Highlight character-level differences between two strings.

        If there is no change, use the diff-unchanged class.

        Parameters
        ----------
        a : str
            Old string.
        b : str
            New string.

        Returns
        -------
        str
            HTML-formatted diff.
        """
        if a == b:
            return f'<span class="diff-unchanged">{Markup.escape(a)}</span>'
        result = []
        sm = difflib.SequenceMatcher(None, a, b)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                result.append(f'<span class="diff-unchanged">{Markup.escape(a[i1:i2])}</span>')
            elif tag == "replace":
                result.append('<span class="diff-remove">{}</span>'.format(Markup.escape(a[i1:i2])))
                result.append('<span class="diff-add">{}</span>'.format(Markup.escape(b[j1:j2])))
            elif tag == "delete":
                result.append('<span class="diff-remove">{}</span>'.format(Markup.escape(a[i1:i2])))
            elif tag == "insert":
                result.append('<span class="diff-add">{}</span>'.format(Markup.escape(b[j1:j2])))
        return "".join(result)


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
        demo_id=demo_id
    )
@admin_demo_bp.route("/preview_demo_with_token/<token>", methods=["GET"])
def preview_demo_with_token(token):
    """
    Secure preview of a demonstration using a token.

    Parameters
    ----------
    token : str
        The secure token for previewing the demonstration.

    Returns
    -------
    flask.Response
        Renders the demonstration preview page or redirects with an error.
    """
    try:
        demo_id = serializer.loads(token, salt="preview-demo", max_age=86400)  # 24h expiry
    except SignatureExpired:
        flash_message("Esikatselulinkki on vanhentunut.", "error")
        return redirect(url_for("admin_demo.demo_control"))
    except BadSignature:
        flash_message("Esikatselulinkki on virheellinen.", "error")
        return redirect(url_for("admin_demo.demo_control"))

    demo_data = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
    if not demo_data:
        flash_message("Mielenosoitusta ei löytynyt.", "error")
        return redirect(url_for("admin_demo.demo_control"))

    # Convert ObjectId to str for template compatibility
    if isinstance(demo_data.get("_id"), ObjectId):
        demo_data["_id"] = str(demo_data["_id"])
    # Pass the raw dict to the template for JSON serialization compatibility
    return render_template(
        "detail.html",
        demo=stringify_object_ids(demo_data),
        preview_mode=True,
    )

@admin_demo_bp.route("/reject_demo_with_token/<token>", methods=["GET"])
def reject_demo_with_token(token):
    """
    Reject a demonstration using a one-time token (magic link).

    Parameters
    ----------
    token : str
        The secure token for rejecting the demonstration.

    Returns
    -------
    flask.Response
        Redirects to the admin dashboard with a flash message.
    """
    try:
        demo_id = serializer.loads(token, salt="reject-demo", max_age=86400)  # 24h expiry
    except SignatureExpired:
        flash_message("Hylkäyslinkki on vanhentunut.", "error")
        return redirect(url_for("admin_demo.demo_control"))
    except BadSignature:
        flash_message("Hylkäyslinkki on virheellinen.", "error")
        return redirect(url_for("admin_demo.demo_control"))

    demo_data = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
    if not demo_data:
        flash_message("Mielenosoitusta ei löytynyt.", "error")
        return redirect(url_for("admin_demo.demo_control"))

    if demo_data.get("approved") is False and demo_data.get("rejected") is True:
        flash_message("Mielenosoitus on jo hylätty.", "info")
        return redirect(url_for("admin_demo.demo_control"))

    # Mark the demonstration as rejected
    mongo.demonstrations.update_one({"_id": ObjectId(demo_id)}, {"$set": {"approved": False, "rejected": True}})

    # Optionally, notify the submitter (if you want to send a rejection email)
    submitter = mongo.submitters.find_one({"demonstration_id": ObjectId(demo_id)})
    if submitter and submitter.get("submitter_email"):
        email_sender.queue_email(
            template_name="demo_submitter_rejected.html",
            subject="Mielenosoituksesi on hylätty",
            recipients=[submitter["submitter_email"]],
            context={
                "title": demo_data.get("title", ""),
                "date": demo_data.get("date", ""),
                "city": demo_data.get("city", ""),
                "address": demo_data.get("address", ""),
            },
        )

    flash_message("Mielenosoitus hylättiin onnistuneesti!", "success")
    return redirect(url_for("admin_demo.demo_control"))
    
@admin_demo_bp.route("/approve_demo_with_token/<token>", methods=["GET"])
def approve_demo_with_token(token):
    """
    Approve a demonstration using a one-time token (magic link).

    Parameters
    ----------
    token : str
        The secure token for approving the demonstration.

    Returns
    -------
    flask.Response
        Redirects to the admin dashboard with a flash message.
    """
    try:
        demo_id = serializer.loads(token, salt="approve-demo", max_age=86400)  # 24h expiry
    except SignatureExpired:
        flash_message("Hyväksymislinkki on vanhentunut.", "error")
        return redirect(url_for("admin_demo.demo_control"))
    except BadSignature:
        flash_message("Hyväksymislinkki on virheellinen.", "error")
        return redirect(url_for("admin_demo.demo_control"))

    demo_data = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
    if not demo_data:
        flash_message("Mielenosoitusta ei löytynyt.", "error")
        return redirect(url_for("admin_demo.demo_control"))

    if demo_data.get("approved"):
        flash_message("Mielenosoitus on jo hyväksytty.", "info")
        return redirect(url_for("admin_demo.demo_control"))

    # Approve the demonstration
    mongo.demonstrations.update_one({"_id": ObjectId(demo_id)}, {"$set": {"approved": True}})


    # Notify submitter if possible
    submitter = mongo.submitters.find_one({"demonstration_id": ObjectId(demo_id)})
    if submitter and submitter.get("submitter_email"):
        demo = demo_data
        email_sender.queue_email(
            template_name="demo_submitter_approved.html",
            subject="Mielenosoituksesi on hyväksytty",
            recipients=[submitter["submitter_email"]],
            context={
                "title": demo.get("title", ""),
                "date": demo.get("date", ""),
                "city": demo.get("city", ""),
                "address": demo.get("address", ""),
            },
        )

    flash_message("Mielenosoitus hyväksyttiin onnistuneesti!", "success")
    return redirect(url_for("admin_demo.demo_control"))


def generate_demo_preview_link(demo_id):
    """
    Generate a secure preview link for a demonstration using a token.

    Parameters
    ----------
    demo_id : str
        The ID of the demonstration.

    Returns
    -------
    str
        The preview link URL.
    """
    token = serializer.dumps(demo_id, salt="preview-demo")
    preview_link = url_for("admin_demo.preview_demo_with_token", token=token, _external=True)
    return preview_link

@admin_demo_bp.route("/")
@login_required
@admin_required
@permission_required("LIST_DEMOS")
def demo_control():
    """Render the demonstration control panel with a list of demonstrations.

    Filters demonstrations by search query, approval status, and whether past events should be shown.

    Parameters
    ----------

    Returns
    -------


    """
    # Limit demonstrations by organization if the user is not a global admin
    if not current_user.global_admin:
        user_org_ids = current_user.org_ids()
    else:
        user_org_ids = None

    search_query = request.args.get("search", "").lower()
    approved_only = request.args.get("approved", "false").lower() == "true"
    show_past = request.args.get("show_past", "false").lower() == "true"
    today = date.today()

    # Construct the base query to fetch demonstrations
    # Remove the "approved" filter to allow for dynamic filtering based on user input
    filter = DEMO_FILTER.copy()  # Copy the base filter to avoid modifying the original
    del filter["approved"]
    query = filter

    if approved_only:
        query["approved"] = True

    if not current_user.global_admin:
        # If the user does not have the global right to view all demos,
        # restrict to demos the user can edit: either via their organization or by specific edit right.
        _where = current_user._perm_in("EDIT_DEMO")
        print(_where)
                
        query["$or"] = [
            {"organizers": {"$elemMatch": {"organization_id": {"$in": [ObjectId(org_id) for org_id in _where]}}}},
            {"editors": current_user.id}
        ]
#        else:
 #           query["organizers"] = {"$elemMatch": {"organization_id": {"$in": user_org_ids}}}

    # Filter demonstrations based on search query, approval status, and date
    filtered_demos = filter_demonstrations(query, search_query, show_past, today)

    # Sort filtered demonstrations by date using ISO date format
    filtered_demos.sort(
        key=lambda demo: datetime.strptime(demo["date"], "%Y-%m-%d").date()
    )

    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}demonstrations/dashboard.html",
        demonstrations=filtered_demos,
        search_query=search_query,
        approved_status=approved_only,
        show_past=show_past,
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

    if request.method == "POST":
        # Handle form submission for editing the demonstration
        return handle_demo_form(request, is_edit=True, demo_id=demo_id)

    # Convert demonstration data to a Demonstration object
    demonstration = Demonstration.from_dict(demo_data)
    # Render the edit form with pre-filled demonstration details
    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}demonstrations/form.html",
        demo=demonstration,
        form_action=url_for("admin_demo.edit_demo", demo_id=demo_id),
        title=_("Muokkaa mielenosoitusta"),
        submit_button_text=_("Tallenna muutokset"),
        city_list=CITY_LIST,
        all_organizations=mongo.organizations.find(),
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


def handle_demo_form(request, is_edit=False, demo_id=None):
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

    from mielenosoitukset_fi.utils.admin.demonstration import fix_organizers

    demonstration_data = fix_organizers(demonstration_data)
    
    if demo_id and demonstration_data.get("_id") is None:
        demonstration_data["_id"] = ObjectId(demo_id)
        
    try:
        if is_edit and demo_id:
            # --- Save previous version to history ---
            prev_demo = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
            if prev_demo:
                mongo.demo_edit_history.insert_one({
                    "demo_id": str(demo_id),
                    "editor_id": str(getattr(current_user, "id", "unknown")),
                    "edited_at": datetime.utcnow(),
                    "demo_data": prev_demo
                })
            demo = Demonstration.from_dict(demonstration_data)
            demo.save()
            flash_message("Mielenosoitus päivitetty onnistuneesti.", "success")
        else:
            # Insert a new demonstration
            mongo.demonstrations.insert_one(demonstration_data)
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
        raise ValueError(_("Virheellinen leveysaste."))
    if longitude and not is_valid_longitude(longitude):
        raise ValueError(_("Virheellinen pituusaste."))

    # Handle cover picture (file upload or URL)
    cover_picture = request.form.get("cover_picture")
    file = request.files.get("cover_picture_file")
    if file and file.filename:
        import os
        from werkzeug.utils import secure_filename
        static_dir = os.path.join(os.path.dirname(__file__), '../static/demo_preview')
        os.makedirs(static_dir, exist_ok=True)
        filename = secure_filename(file.filename)
        file_path = os.path.join(static_dir, filename)
        file.save(file_path)
        
        # Use a URL relative to static
        cover_picture = f"/static/demo_preview/{filename}"

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
            organizers.append(
                Organizer(
                    name=name.strip() if name else "",
                    email=email.strip() if email else "",
                    website=website.strip() if website else "",
                    organization_id=ObjectId(organizer_id),
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
