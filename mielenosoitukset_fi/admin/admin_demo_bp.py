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
from .utils import mongo, log_admin_action_V2, AdminActParser

from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

# Secret key for generating tokens
SECRET_KEY = "your_secret_key"
serializer = URLSafeTimedSerializer(SECRET_KEY)

# Blueprint setup
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
        user_org_ids = [
            ObjectId(org.get("org_id")) for org in current_user.organizations
        ]
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

    if user_org_ids:
        query["organizers"] = {"$elemMatch": {"organization_id": {"$in": user_org_ids}}}

    # Filter demonstrations based on search query, approval status, and date
    filtered_demos = filter_demonstrations(query, search_query, show_past, today)

    # Sort filtered demonstrations by date
    filtered_demos.sort(
        key=lambda demo: datetime.strptime(demo["date"], "%d.%m.%Y").date()
    )

    return render_template(
        "admin/demonstrations/dashboard.html",
        demonstrations=filtered_demos,
        search_query=search_query,
        approved_status=approved_only,
        show_past=show_past,
    )


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
        if (show_past or datetime.strptime(demo["date"], "%d.%m.%Y").date() >= today)
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
        "admin/demonstrations/form.html",
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
        "admin/demonstrations/form.html",
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
        "admin/demonstrations/form.html",
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

    try:
        if is_edit and demo_id:
            # Update the existing demonstration
            mongo.demonstrations.update_one(
                {"_id": ObjectId(demo_id)}, {"$set": demonstration_data}
            )
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
    """Collect demonstration data from the request form.

    This function extracts and returns relevant data from the submitted form.

    Parameters
    ----------
    request :
        The incoming request object containing form data.

    Returns
    -------


    """
    # We could basically just get the demo id and then use the same function as in the edit_demo functiot

    # Collect basic form data
    title = request.form.get("title")
    date = request.form.get("date")
    start_time = request.form.get("start_time")
    end_time = request.form.get("end_time")
    facebook = request.form.get("facebook")
    city = request.form.get("city")
    address = request.form.get("address")
    event_type = request.form.get("type")
    route = request.form.get("route")
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
        organizers.append(
            Organizer(
                name=name.strip() if name else None,
                email=email.strip() if email else None,
                website=website.strip() if website else None,
                organization_id=organizer_id.strip() if organizer_id else None,
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
    demo_id = request.form.get("demo_id") or (
        request.json.get("demo_id") if json_mode else None
    )

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
        "admin/demonstrations/confirm_delete.html", demo=demonstration
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
        return jsonify({"status": "OK", "message": "Demonstration accepted successfully."}), 200
    except Exception as e:
        logging.error("An error occurred while accepting the demonstration: %s", str(e))
        return jsonify({"status": "ERROR", "message": "An internal error has occurred."}), 500
