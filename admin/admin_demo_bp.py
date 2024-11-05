from datetime import date, datetime
from bson.objectid import ObjectId

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required

from classes import Demonstration, Organizer
from utils import CITY_LIST
from wrappers import admin_required, permission_required
from .utils import mongo


# Blueprint setup
admin_demo_bp = Blueprint("admin_demo", __name__, url_prefix="/admin/demo")


@admin_demo_bp.route("/")
@login_required
@admin_required
@permission_required("LIST_DEMOS")
def demo_control():
    """
    Render the demonstration control panel with a list of demonstrations.

    Filters demonstrations by search query, approval status, and whether past events should be shown.
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
    query = {"hide": {"$exists": False}}

    if approved_only:
        query["approved"] = False

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
    """
    Fetch and filter demonstrations based on search criteria.

    Args:
        query (dict): MongoDB query to filter demonstrations.
        search_query (str): The search term to filter by (applies to title, city, topic, and address).
        show_past (bool): Whether to include past demonstrations.
        today (date): The current date for filtering future demonstrations.

    Returns:
        list: A list of filtered demonstrations matching the criteria.
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
            for field in ["title", "city", "topic", "address"]
        )
    ]

    return filtered_demos


@admin_demo_bp.route("/create_demo", methods=["GET", "POST"])
@login_required
@admin_required
def create_demo():
    """
    Create a new demonstration.

    Renders the form for creating a demonstration or handles the form submission.
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
    """
    Edit demonstration details.

    Fetches the demonstration data by ID for editing or processes the edit form submission.
    """
    # Fetch demonstration data by ID
    demo_data = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
    if not demo_data:
        flash("Mielenosoitusta ei löytynyt.", "error")
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
        title="Muokkaa mielenosoitusta",
        submit_button_text="Vahvista muokkaus",
        city_list=CITY_LIST,
        all_organizations=mongo.organizations.find(),
    )


def handle_demo_form(request, is_edit=False, demo_id=None):
    """
    Handle form submission for creating or editing a demonstration.

    Args:
        request: The incoming request object containing form data.
        is_edit (bool): Whether this is an edit operation.
        demo_id (str): The ID of the demonstration being edited, if applicable.

    Returns:
        Redirect to the appropriate page based on the success or failure of the operation.
    """
    # Collect demonstration data from the form
    demonstration_data = collect_demo_data(request)

    try:
        if is_edit and demo_id:
            # Update the existing demonstration
            mongo.demonstrations.update_one(
                {"_id": ObjectId(demo_id)}, {"$set": demonstration_data}
            )
            flash("Mielenosoitus päivitetty onnistuneesti.", "success")
        else:
            # Insert a new demonstration
            mongo.demonstrations.insert_one(demonstration_data)
            flash("Mielenosoitus luotu onnistuneesti.", "success")

        # Redirect to the demonstration control panel on success
        return redirect(url_for("admin_demo.demo_control"))

    except ValueError as e:
        flash(f"Virhe: {str(e)}", "error")

        # Redirect to the edit or create form based on operation type
        return redirect(
            url_for("admin_demo.edit_demo", demo_id=demo_id)
            if is_edit
            else url_for("admin_demo.create_demo")
        )


def collect_demo_data(request):
    """
    Collect demonstration data from the request form.

    This function extracts and returns relevant data from the submitted form.

    Args:
        request: The incoming request object containing form data.

    Returns:
        dict: A dictionary containing the collected demonstration data.
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
    route = request.form.get("route")
    approved = request.form.get("approved") == "on"

    # Validate required fields
    if not title or not date or not city:
        raise ValueError("Otsikko, päivämäärä ja kaupunki ovat pakollisia kenttiä.")

    # Process organizers and tags
    organizers = collect_organizers(request)
    tags = collect_tags(request)

    # Return the collected data as a dictionary
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
    }


def collect_organizers(request):
    """
    Collect organizer data from the request form.

    This function extracts multiple organizers' information from the form and returns a list
    of Organizer objects.

    Args:
        request: The incoming request object containing form data.

    Returns:
        list: A list of Organizer objects, each containing name, email, website, and organization ID.
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


def collect_tags(request):
    """
    Collect tags data from the request form.

    This function extracts multiple tags from the form fields and returns them as a list.

    Args:
        request: The incoming request object containing form data.

    Returns:
        list: A list of tags extracted from the form.
    """
    tags = []
    i = 1

    while True:
        # Extract the tag value from the dynamic form field names
        tag_name = request.form.get(f"tag_{i}")

        # Break the loop if no tag name is found
        if not tag_name:
            if not request.form.get(f"tag_{i+1}"):
                break

            else:
                continue

        # Append the trimmed tag to the list
        tags.append(tag_name.strip())

        i += 1  # Move to the next tag field

    return tags


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
            flash(error_message)
            return redirect(url_for("admin_demo.demo_control"))

    # Perform deletion
    mongo.demonstrations.delete_one({"_id": ObjectId(demo_id)})

    success_message = "Mielenosoitus poistettu onnistuneesti."
    if json_mode:
        return jsonify({"status": "OK", "message": success_message})
    else:
        flash(success_message)
        return redirect(url_for("admin_demo.demo_control"))


@admin_demo_bp.route("/confirm_delete_demo/<demo_id>", methods=["GET"])
@login_required
@admin_required
@permission_required("DELETE_DEMO")
def confirm_delete_demo(demo_id):
    """Render a confirmation page before deleting a demonstration."""
    # Fetch the demonstration data from the database
    demo_data = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})

    if not demo_data:
        flash("Mielenosoitusta ei löytynyt.")
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
    """Accept an existing demonstration by updating its status."""
    # Ensure the request is JSON
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
        return jsonify({"status": "ERROR", "message": "Demonstration not found."}), 404

    demo = Demonstration.from_dict(demo_data)

    # Update the approved status
    try:
        demo.approved = True
        demo.save()

        return (
            jsonify(
                {"status": "OK", "message": "Demonstration accepted successfully."}
            ),
            200,
        )
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 500
