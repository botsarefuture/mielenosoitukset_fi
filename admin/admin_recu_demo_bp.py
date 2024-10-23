from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from bson.objectid import ObjectId
from datetime import datetime, date
from utils import CITY_LIST
from wrappers import permission_required

from database_manager import DatabaseManager
from wrappers import admin_required
from classes import RecurringDemonstration, RepeatSchedule, Organizer

from .utils import mongo

admin_recu_demo_bp = Blueprint(
    "admin_recu_demo", __name__, url_prefix="/admin/recu_demo"
)


@admin_recu_demo_bp.route("/")
@login_required
@admin_required
@permission_required("LIST_RECURRING_DEMOS")
def recu_demo_control():
    """Render the recurring demonstration control panel with a list of recurring demonstrations."""
    search_query = request.args.get("search", "")
    approved_status = request.args.get("approved", "false").lower() == "true"
    show_past = request.args.get("show_past", "false").lower() == "true"
    today = date.today()  # Get the current date

    query = {"approved": approved_status} if approved_status else {}

    # Fetch all recurring demonstrations from the database
    recurring_demos = mongo.recu_demos.find(query)

    # Filter based on the search query
    filtered_recurring_demos = []
    if 1 == 2:
        for demo in recurring_demos:
            demo_date = datetime.strptime(demo["date"], "%d.%m.%Y").date()
            if show_past or demo_date >= today:
                if (
                    search_query.lower() in demo["title"].lower()
                    or search_query.lower() in demo["city"].lower()
                    or search_query.lower() in demo["topic"].lower()
                    or search_query.lower() in demo["address"].lower()
                ):
                    filtered_recurring_demos.append(demo)

    else:
        filtered_recurring_demos = recurring_demos

    # Sort the filtered recurring demonstrations by date
    # filtered_recurring_demos.sort(
    #    key=lambda x: datetime.strptime(x["date"], "%d.%m.%Y").date()
    # )

    return render_template(
        "admin/recu_demonstrations/dashboard.html",
        recurring_demos=filtered_recurring_demos,
        search_query=search_query,
        approved_status=approved_status,
        show_past=show_past,
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
        "admin/recu_demonstrations/form.html",
        form_action=url_for("admin_recu_demo.create_recu_demo"),
        title="Luo toistuva mielenosoitus",
        submit_button_text="Luo",
        city_list=CITY_LIST,
    )


@admin_recu_demo_bp.route("/edit_recu_demo/<demo_id>", methods=["GET", "POST"])
@login_required
@admin_required
@permission_required("EDIT_RECURRING_DEMO")
def edit_recu_demo(demo_id):
    """Edit recurring demonstration details."""
    demo_data = mongo.recu_demos.find_one({"_id": ObjectId(demo_id)})
    if not demo_data:
        flash("Toistuva mielenosoitus ei löytynyt.")
        return redirect(url_for("admin_recu_demo.recu_demo_control"))

    if request.method == "POST":
        return handle_recu_demo_form(request, is_edit=True, demo_id=demo_id)

    recurring_demo = RecurringDemonstration.from_dict(demo_data)
    return render_template(
        "admin/recu_demonstrations/form.html",
        demo=recurring_demo,
        form_action=url_for("admin_recu_demo.edit_recu_demo", demo_id=demo_id),
        title="Muokkaa toistuvaa mielenosoitusta",
        submit_button_text="Vahvista muokkaus",
        city_list=CITY_LIST,
    )


def handle_recu_demo_form(request, is_edit=False, demo_id=None):
    """Handle form submission for creating or editing a recurring demonstration."""
    title = request.form.get("title")
    date = request.form.get("date")
    start_time = request.form.get("start_time")
    end_time = request.form.get("end_time")
    topic = request.form.get("topic")
    facebook = request.form.get("facebook")
    city = request.form.get("city")
    address = request.form.get("address")
    event_type = request.form.get("type")
    route = request.form.get("route")
    approved = request.form.get("approved") == "on"

    # Process organizers
    organizers = []
    i = 1
    while True:
        name = request.form.get(f"organizer_name_{i}")
        website = request.form.get(f"organizer_website_{i}")
        email = request.form.get(f"organizer_email_{i}")
        if not name:
            break
        organizer = Organizer(name=name, email=email, website=website)
        organizers.append(organizer)
        i += 1

    # Get the repeat schedule details
    repeat_schedule = {
        "frequency": request.form.get("frequency_type"),
        "interval": int(request.form.get("interval", 1)),
        "weekday": request.form.get("weekday"),  # Capture the weekday
    }

    demonstration_data = {
        "title": title,
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "topic": topic,
        "facebook": facebook,
        "city": city,
        "address": address,
        "type": event_type,
        "route": route,
        "approved": approved,
        "repeat_schedule": repeat_schedule,
        "linked_organizations": request.form.getlist(
            "linked_organizations"
        ),  # Collect linked organizations
        "created_until": request.form.get("created_until"),  # New field
        "repeating": request.form.get("repeating") == "on",  # New field,,
        "organizers": [org.to_dict() for org in organizers],
    }

    try:
        if is_edit:
            mongo.recu_demos.update_one(
                {"_id": ObjectId(demo_id)}, {"$set": demonstration_data}
            )
            flash("Toistuva mielenosoitus päivitetty onnistuneesti.")
        else:
            mongo.recu_demos.insert_one(demonstration_data)
            flash("Toistuva mielenosoitus luotu onnistuneesti.")
        return redirect(url_for("admin_recu_demo.recu_demo_control"))
    except ValueError as e:
        flash(str(e))
        if is_edit:
            return redirect(url_for("admin_recu_demo.edit_recu_demo", demo_id=demo_id))
        else:
            return redirect(url_for("admin_recu_demo.create_recu_demo"))


@admin_recu_demo_bp.route("/delete_recu_demo/<demo_id>", methods=["POST"])
@login_required
@admin_required
@permission_required("DELETE_RECURRING_DEMO")
def delete_recu_demo(demo_id):
    """Delete a recurring demonstration from the database."""
    demo_data = mongo.recu_demos.find_one({"_id": ObjectId(demo_id)})

    if not demo_data:
        flash("Toistuva mielenosoitus ei löytynyt.")
        return redirect(url_for("admin_recu_demo.recu_demo_control"))

    if "confirm_delete" in request.form:
        mongo.recu_demos.delete_one({"_id": ObjectId(demo_id)})
        flash("Toistuva mielenosoitus poistettu onnistuneesti.")
    else:
        flash("Et vahvistanut toistuvan mielenosoituksen poistoa.")

    return redirect(url_for("admin_recu_demo.recu_demo_control"))


@admin_recu_demo_bp.route("/confirm_delete_recu_demo/<demo_id>", methods=["GET"])
@login_required
@admin_required
def confirm_delete_recu_demo(demo_id):
    """Render a confirmation page before deleting a recurring demonstration."""
    demo_data = mongo.recu_demos.find_one({"_id": ObjectId(demo_id)})
    if not demo_data:
        flash("Toistuva mielenosoitus ei löytynyt.")
        return redirect(url_for("admin_recu_demo.recu_demo_control"))

    recurring_demo = RecurringDemonstration.from_dict(demo_data)
    return render_template(
        "admin/recu_demonstrations/confirm_delete.html", demo=recurring_demo
    )
