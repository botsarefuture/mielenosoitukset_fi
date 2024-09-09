from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from bson.objectid import ObjectId
from database_manager import DatabaseManager
from wrappers import admin_required
from classes import Demonstration, Organizer

admin_demo_bp = Blueprint("admin_demo", __name__, url_prefix="/admin/demo")

# Initialize MongoDB
db_manager = DatabaseManager()
mongo = db_manager.get_db()
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from bson.objectid import ObjectId
from database_manager import DatabaseManager
from wrappers import admin_required
from classes import Demonstration, Organizer
from datetime import datetime, date

admin_demo_bp = Blueprint("admin_demo", __name__, url_prefix="/admin/demo")

# Initialize MongoDB
db_manager = DatabaseManager()
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

    query = dict({"approved": approved_status})

    # Initial query to get all approved demonstrations
    if approved_status == False:
        query = dict()

    # Fetch all approved demonstrations from the database
    demonstrations = mongo.demonstrations.find(query)

    # Filter based on the search query
    filtered_demonstrations = []
    for demo in demonstrations:
        demo_date = datetime.strptime(demo["date"], "%d.%m.%Y").date()
        if show_past or demo_date >= today:
            if (
                search_query.lower() in demo["title"].lower()
                or search_query.lower() in demo["city"].lower()
                or search_query.lower() in demo["topic"].lower()
                or search_query.lower() in demo["address"].lower()
            ):
                filtered_demonstrations.append(demo)

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

        organization_id = request.form.get("organization_id", None)
        organizer_name = request.form.get("organizer_name")
        organizer_email = request.form.get("organizer_email")
        organizer_website = request.form.get("organizer_website")

        organizers = []

        # Check if an organization is selected
        if organization_id and organization_id != "manual":
            # Fetch the organization from the database
            organization = mongo.organizations.find_one(
                {"_id": ObjectId(organization_id)}
            )
            if organization:
                organizer = Organizer(
                    name=organization["name"],
                    email=organization["email"],
                    organization_id=str(organization["_id"]),
                    website=organization.get("website"),
                )
                organizers.append(organizer)
            else:
                flash("Valittua organisaatiota ei ole olemassa.")
                return redirect(url_for("admin_demo.create_demo"))
        elif organizer_name and organizer_email:
            # Use the manually entered details
            organizer = Organizer(
                name=organizer_name, email=organizer_email, website=organizer_website
            )
            organizers.append(organizer)

        try:
            demonstration = Demonstration(
                title=title,
                date=date,
                start_time=start_time,
                end_time=end_time,
                topic=topic,
                facebook=facebook,
                city=city,
                address=address,
                event_type=event_type,
                route=route,
                organizers=organizers,
            )
            mongo.demonstrations.insert_one(demonstration.to_dict())
            flash("Mielenosoitus luotu onnistuneesti.")
            return redirect(url_for("admin_demo.demo_control"))
        except ValueError as e:
            flash(str(e))
            return redirect(url_for("admin_demo.create_demo"))

    # Fetch organizations for the dropdown
    organizations = mongo.organizations.find()
    return render_template(
        "admin/demonstrations/create.html", organizations=organizations
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

    demonstration = Demonstration.from_dict(demo_data)

    if request.method == "POST":
        # Update demonstration fields
        demonstration.title = request.form.get("title")
        demonstration.date = request.form.get("date")
        demonstration.start_time = request.form.get("start_time")
        demonstration.end_time = request.form.get("end_time")
        demonstration.topic = request.form.get("topic")
        demonstration.facebook = request.form.get("facebook")
        demonstration.city = request.form.get("city")
        demonstration.address = request.form.get("address")
        demonstration.event_type = request.form.get("type")
        demonstration.route = request.form.get("route")
        demonstration.approved = bool(request.form.get("approved"))

        # Process organizers
        organizers = []
        i = 1
        while True:
            name = request.form.get(f"organizer_name_{i}")
            website = request.form.get(f"organizer_website_{i}")
            email = request.form.get(f"organizer_email_{i}")
            organization_id = request.form.get(
                f"organization_id_{i}", None
            )  # TODO: Add this to form.

            if not name:
                break

            organizer = Organizer(
                name=name, email=email, website=website, organization_id=organization_id
            )
            organizers.append(organizer)
            i += 1
        demonstration.organizers = organizers

        try:
            mongo.demonstrations.update_one(
                {"_id": ObjectId(demo_id)}, {"$set": demonstration.to_dict()}
            )
            flash("Mielenosoitus päivitetty onnistuneesti.")
            return redirect(url_for("admin_demo.demo_control"))
        except ValueError as e:
            flash(str(e))
            return redirect(url_for("admin_demo.edit_demo", demo_id=demo_id))

    return render_template("admin/demonstrations/edit.html", demo=demonstration)


@admin_demo_bp.route("/delete_demo/<demo_id>", methods=["POST"])
@login_required
@admin_required
def delete_demo(demo_id):
    """Delete a demonstration from the database."""
    demo_data = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})

    if not demo_data:
        flash("Mielenosoitusta ei löytynyt.")
        return redirect(url_for("admin_demo.demo_control"))

    if "confirm_delete" in request.form:
        mongo.demonstrations.delete_one({"_id": ObjectId(demo_id)})
        flash("Mielenosoitus poistettu onnistuneesti.")
    else:
        flash("Et vahvistanut mielenosoituksen poistoa.")

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
