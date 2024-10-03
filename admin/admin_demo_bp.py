from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from bson.objectid import ObjectId
from datetime import datetime, date
from utils import CITY_LIST

from database_manager import DatabaseManager
from wrappers import admin_required
from classes import Demonstration, Organizer

admin_demo_bp = Blueprint("admin_demo", __name__, url_prefix="/admin/demo")

# Initialize MongoDB
db_manager = DatabaseManager().get_instance()
mongo = db_manager.get_db()

@admin_demo_bp.route("/")
@login_required
@admin_required
def demo_control():
    """Render the demonstration control panel with a list of demonstrations."""
    search_query = request.args.get("search", "")
    approved_status = request.args.get("approved", "false").lower() == "true"
    show_past = request.args.get("show_past", "false").lower() == "true"
    today = date.today()  # Get the current date

    # Construct the base query
    query = {"hide": {"$exists": False}}
    if approved_status:
        query["approved"] = approved_status

    # Fetch all demonstrations from the database
    demonstrations = mongo.demonstrations.find(query)

    # Filter based on the search query
    filtered_demonstrations = [
        demo for demo in demonstrations
        if (show_past or datetime.strptime(demo["date"], "%d.%m.%Y").date() >= today) and (
            search_query.lower() in demo["title"].lower() or
            search_query.lower() in demo["city"].lower() or
            search_query.lower() in demo["topic"].lower() or
            search_query.lower() in demo["address"].lower())
    ]

    # Sort the filtered demonstrations by date
    filtered_demonstrations.sort(
        key=lambda x: datetime.strptime(x["date"], "%d.%m.%Y").date()
    )

    return render_template(
        "admin/demonstrations/dashboard.html",
        demonstrations=filtered_demonstrations,
        search_query=search_query,
        approved_status=approved_status,
        show_past=show_past,
    )



@admin_demo_bp.route("/create_demo", methods=["GET", "POST"])
@login_required
@admin_required
def create_demo():
    """Create a new demonstration."""
    if request.method == "POST":
        return handle_demo_form(request, is_edit=False)

    # Fetch organizations for the dropdown
    organizations = mongo.organizations.find()
    return render_template(
        "admin/demonstrations/form.html", organizations=organizations, form_action=url_for("admin_demo.create_demo"), title="Luo mielenosoitus", submit_button_text="Luo", demo=None, city_list=CITY_LIST
    )


@admin_demo_bp.route("/edit_demo/<demo_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_demo(demo_id):
    """Edit demonstration details."""
    demo_data = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
    if not demo_data:
        flash("Mielenosoitusta ei löytynyt.")
        return redirect(url_for("admin_demo.demo_control"))

    if request.method == "POST":
        return handle_demo_form(request, is_edit=True, demo_id=demo_id)

    demonstration = Demonstration.from_dict(demo_data)
    return render_template("admin/demonstrations/form.html", demo=demonstration, form_action=url_for("admin_demo.edit_demo",demo_id=demo_id), title="Muokkaa mielenosoitusta", submit_button_text="Vahvista muokkaus")

def handle_demo_form(request, is_edit=False, demo_id=None):
    """Handle form submission for creating or editing a demonstration."""
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
    approved = request.form.get("approved") == 'on'

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
        "organizers": [org.to_dict() for org in organizers],
        "approved": approved
    }

    try:
        if is_edit:
            mongo.demonstrations.update_one(
                {"_id": ObjectId(demo_id)},
                {"$set": demonstration_data}
            )
            flash("Mielenosoitus päivitetty onnistuneesti.")
        else:
            mongo.demonstrations.insert_one(demonstration_data)
            flash("Mielenosoitus luotu onnistuneesti.")
        return redirect(url_for("admin_demo.demo_control"))
    except ValueError as e:
        flash(str(e))
        if is_edit:
            return redirect(url_for("admin_demo.edit_demo", demo_id=demo_id))
        else:
            return redirect(url_for("admin_demo.create_demo"))


@admin_demo_bp.route("/delete_demo", methods=["POST"])
@login_required
@admin_required
def delete_demo():
    """Delete a demonstration from the database."""
    demo_id = request.form.get("demo_id")  # Get the demo ID from the form
    demo_data = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})

    if not demo_data:
        flash("Mielenosoitusta ei löytynyt.")
        return redirect(url_for("admin_demo.demo_control"))

    mongo.demonstrations.delete_one({"_id": ObjectId(demo_id)})
    flash("Mielenosoitus poistettu onnistuneesti.")

    return redirect(url_for("admin_demo.demo_control"))



@admin_demo_bp.route("/confirm_delete_demo/<demo_id>", methods=["GET"])
@login_required
@admin_required
def confirm_delete_demo(demo_id):
    """Render a confirmation page before deleting a demonstration."""
    demo_data = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
    if not demo_data:
        flash("Mielenosoitusta ei löytynyt.")
        return redirect(url_for("admin_demo.demo_control"))

    demonstration = Demonstration.from_dict(demo_data)
    return render_template(
        "admin/demonstrations/confirm_delete.html", demo=demonstration
    )
