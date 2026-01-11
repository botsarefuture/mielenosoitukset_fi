from datetime import datetime, date

from bson.objectid import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required
from mielenosoitukset_fi.utils.flashing import flash_message

from mielenosoitukset_fi.utils.classes import RecurringDemonstration, Organizer
from mielenosoitukset_fi.utils.variables import CITY_LIST
from mielenosoitukset_fi.utils.wrappers import permission_required, admin_required

from mielenosoitukset_fi.utils.admin.demonstration import collect_tags
from .utils import mongo, _ADMIN_TEMPLATE_FOLDER

from mielenosoitukset_fi.utils.classes import RecurringDemonstration

admin_recu_demo_bp = Blueprint(
    "admin_recu_demo", __name__, url_prefix="/admin/recu_demo"
)

from .utils import AdminActParser, log_admin_action_V2
from flask_login import current_user


@admin_recu_demo_bp.before_request
def log_request_info():
    """Log request information before handling it."""
    log_admin_action_V2(
        AdminActParser().log_request_info(request.__dict__, current_user)
    )


@admin_recu_demo_bp.route("/")
@login_required
@admin_required
@permission_required("LIST_RECURRING_DEMOS")
def recu_demo_control():
    """Render the recurring demonstration control panel with a list of recurring demonstrations."""
    search_query = request.args.get("search", "")
    approved_status = request.args.get("approved", "false").lower() == "true"
    # show_past = request.args.get("show_past", "false").lower() == "true"
    today = date.today()

    # Construct query based on approval status
    query = {"approved": approved_status} if approved_status else {}
    recurring_demos = [
        RecurringDemonstration.from_dict(recudemo)
        for recudemo in list(mongo.recu_demos.find(query))
    ]  #  .recu_demos.find(query)

    # Filter based on search query and date
    filtered_recurring_demos = [
        demo
        for demo in recurring_demos
        if (
            search_query.lower() in demo.title.lower()
            or search_query.lower() in demo.city.lower()
            or search_query.lower() in demo.address.lower()
        )
    ]

    # Sort the filtered recurring demonstrations by date
    filtered_recurring_demos.sort(
        key=lambda x: datetime.strptime(x.date, "%Y-%m-%d").date()
    )

    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}recu_demonstrations/dashboard.html",
        recurring_demos=filtered_recurring_demos,
        search_query=search_query,
        approved_status=approved_status,
    )


@admin_recu_demo_bp.route("/create_recu_demo", methods=["GET", "POST"])
@login_required
@admin_required
@permission_required("CREATE_RECURRING_DEMO")
def create_recu_demo():
    """Create a new recurring demonstration."""
    if request.method == "POST":
        return handle_recu_demo_form(request, is_edit=False)

    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}recu_demonstrations/form.html",
        form_action=url_for("admin_recu_demo.create_recu_demo"),
        title="Luo toistuva mielenosoitus",
        submit_button_text="Luo",
        city_list=CITY_LIST,
        all_organizations=list(mongo.organizations.find()),
    )


@admin_recu_demo_bp.route("/edit_recu_demo/<demo_id>", methods=["GET", "POST"])
@login_required
@admin_required
@permission_required("EDIT_RECURRING_DEMO")
def edit_recu_demo(demo_id):
    """Edit recurring demonstration details.

    Changelog:
    ---------
    v2.4.0:
    - Fixed some typos in flash_messages

    Parameters
    ----------
    demo_id :


    Returns
    -------


    """
    demo_data = mongo.recu_demos.find_one({"_id": ObjectId(demo_id)})

    if not demo_data:
        flash_message("Toistuvaa mielenosoitusta ei löytynyt.")
        return redirect(url_for("admin_recu_demo.recu_demo_control"))

    if request.method == "POST":
        return handle_recu_demo_form(request, is_edit=True, demo_id=demo_id)

    recurring_demo = RecurringDemonstration.from_dict(demo_data)
    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}recu_demonstrations/_form_v2.html",
        demo=recurring_demo,
        form_action=url_for("admin_recu_demo.edit_recu_demo", demo_id=demo_id),
        title="Muokkaa toistuvaa mielenosoitusta",
        submit_button_text="Vahvista muokkaus",
        city_list=CITY_LIST,
    )
def handle_recu_demo_form(request, is_edit=False, demo_id=None):
    """Handle form submission for creating or editing a recurring demonstration."""

    # Basic info
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

    tags = collect_tags(request)
    cover_picture = request.form.get("cover_picture")
    gallery_images = parse_gallery_images_field(request.form.get("gallery_images"))

    # Process organizers dynamically
    organizers = []
    index = 1
    while True:
        name = request.form.get(f"organizer_name_{index}")
        _id = request.form.get(f"organizer_id_{index}")
        if not name and not _id:
            break
        website = request.form.get(f"organizer_website_{index}")
        email = request.form.get(f"organizer_email_{index}")
        organizers.append(
            Organizer(name=name, email=email, website=website, organization_id=_id).to_dict()
        )
        index += 1

    # Recurrence / repeat schedule
    freq = request.form.get("frequency_type", "none")
    interval = int(request.form.get("frequency_interval", 1))
    end_date = request.form.get("end_date")

    # Weekly
    weekday = None
    if freq == "weekly":
        weekday = request.form.get("weekday")

    # Monthly
    monthly_option = None
    day_of_month = None
    nth_weekday = None
    weekday_of_month = None
    if freq == "monthly":
        monthly_option = request.form.get("monthly_option", "day_of_month")
        if monthly_option == "day_of_month":
            day_of_month_raw = request.form.get("day_of_month")
            if day_of_month_raw and day_of_month_raw.isdigit():
                day_of_month = int(day_of_month_raw)
            else:
                day_of_month = None  # safe fallback
        elif monthly_option == "nth_weekday":
            nth_weekday = request.form.get("nth_weekday")
            weekday_of_month = request.form.get("weekday_of_month")

    repeat_schedule = {
        "frequency": freq,
        "interval": interval,
        "weekday": weekday,
        "monthly_option": monthly_option,
        "day_of_month": day_of_month,
        "nth_weekday": nth_weekday,
        "weekday_of_month": weekday_of_month,
        "end_date": end_date,
    }

    # Assemble demonstration data
    demonstration_data = {
        "title": title,
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "tags": tags,
        "facebook": facebook,
        "city": city,
        "address": address,
        "event_type": event_type,
        "route": route,
        "approved": approved,
        "cover_picture": cover_picture,
        "gallery_images": gallery_images,
        "repeat_schedule": repeat_schedule,
        "recurs": freq != "none",
        "organizers": organizers,
    }

    # Ensure organizer IDs are ObjectId if present
    for org in demonstration_data["organizers"]:
        if org.get("organization_id"):
            try:
                org["organization_id"] = ObjectId(org["organization_id"])
            except Exception:
                org["organization_id"] = None

    try:
        if is_edit:
            mongo.recu_demos.update_one(
                {"_id": ObjectId(demo_id)}, {"$set": demonstration_data}
            )
            flash_message("Toistuva mielenosoitus päivitetty onnistuneesti.")
        else:
            mongo.recu_demos.insert_one(demonstration_data)
            flash_message("Toistuva mielenosoitus luotu onnistuneesti.")
        return redirect(url_for("admin_recu_demo.recu_demo_control"))
    except Exception as e:
        import logging
        logging.error(f"An error occurred: {str(e)}")
        flash_message(f"Virhe: {str(e)}")
        return redirect(
            url_for(
                "admin_recu_demo.edit_recu_demo" if is_edit else "admin_recu_demo.create_recu_demo",
                demo_id=demo_id,
            )
        )


def parse_gallery_images_field(raw_value):
    """Convert textarea input into a clean list of gallery image URLs."""
    if not raw_value:
        return []
    entries = []
    for line in raw_value.replace("\r", "").splitlines():
        url = line.strip()
        if url:
            entries.append(url)
    return entries


@admin_recu_demo_bp.route("/delete_recu_demo/<demo_id>", methods=["POST"])
@login_required
@admin_required
@permission_required("DELETE_RECURRING_DEMO")
def delete_recu_demo(demo_id):
    """Delete a recurring demonstration from the database.

    Parameters
    ----------
    demo_id :


    Returns
    -------


    """
    demo_data = mongo.recu_demos.find_one({"_id": ObjectId(demo_id)})

    if not demo_data:
        flash_message("Toistuvaa mielenosoitusta ei löytynyt.")
        return redirect(url_for("admin_recu_demo.recu_demo_control"))

    if "confirm_delete" in request.form:
        mongo.recu_demos.delete_one({"_id": ObjectId(demo_id)})
        flash_message("Toistuva mielenosoitus poistettu onnistuneesti.")
    else:
        flash_message("Et vahvistanut toistuvan mielenosoituksen poistoa.")

    return redirect(url_for("admin_recu_demo.recu_demo_control"))


@admin_recu_demo_bp.route("/confirm_delete_recu_demo/<demo_id>", methods=["GET"])
@login_required
@admin_required
@permission_required("DELETE_RECURRING_DEMO")
def confirm_delete_recu_demo(demo_id):
    """Render a confirmation page before deleting a recurring demonstration.

    Changelog:
    ----------
    v2.4.0:
    - Fixed some typos in flash_messagees

    Parameters
    ----------
    demo_id :


    Returns
    -------


    """
    demo_data = mongo.recu_demos.find_one({"_id": ObjectId(demo_id)})

    if not demo_data:
        flash_message("Toistuvaa mielenosoitusta ei löytynyt.")
        return redirect(url_for("admin_recu_demo.recu_demo_control"))

    recurring_demo = RecurringDemonstration.from_dict(demo_data)
    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}recu_demonstrations/confirm_delete.html", demo=recurring_demo
    )
