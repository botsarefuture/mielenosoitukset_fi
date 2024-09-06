from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app,
)
from flask_login import login_required, current_user
from bson.objectid import ObjectId
from database_manager import DatabaseManager
from classes import Organizer, Demonstration
from emailer.EmailSender import EmailSender
from emailer.EmailJob import EmailJob


# Create a Blueprint for organization-related routes
organization_bp = Blueprint("organization", __name__)

# Initialize the database manager and get the database connection
db_manager = DatabaseManager()
db = db_manager.get_db()

# Initialize the EmailSender
email_sender = EmailSender()


@organization_bp.route("/organizations")
@login_required
def list_organizations():
    # TODO: Consider adding pagination to handle large number of organizations.
    organizations = db["organizations"].find()
    return render_template(
        "organization/list_organizations.html", organizations=organizations
    )


@organization_bp.route("/organization/<org_id>")
@login_required
def organization_detail(org_id):
    # TODO: Add error handling for invalid ObjectId format.
    organization = db["organizations"].find_one({"_id": ObjectId(org_id)})
    if not organization:
        flash("Organization not found.")
        return redirect(url_for("organization.list_organizations"))

    # Check if the current user is a member of the organization
    is_member = current_user.is_member_of_organization(ObjectId(org_id))

    return render_template(
        "organization/organization_detail.html",
        organization=organization,
        is_member=is_member,
    )


@organization_bp.route("/organization/create", methods=["GET", "POST"])
@login_required
def create_organization():
    if not current_user.is_authenticated:
        flash("You do not have permission to create organizations.")
        return redirect(url_for("index"))

    if request.method == "POST":
        name = request.form.get("name")
        description = request.form.get("description")
        email = request.form.get("email")
        website = request.form.get("website")

        result = db["organizations"].insert_one(
            {
                "name": name,
                "description": description,
                "email": email,
                "website": website,
                "members": [{"user_id": current_user.id, "role": "admin"}],
            }
        )

        current_user.add_organization(db, result.inserted_id, "admin")
        db["users"].update_one(
            {"_id": ObjectId(current_user.id)},
            {
                "$push": {
                    "organizations": {"org_id": result.inserted_id, "role": "admin"}
                }
            },
        )

        flash("Organization created successfully!")

        # Send email notification
        email_sender.queue_email(
            template_name="organization_access_notification.html",
            subject="New Organization Access",
            recipients=[
                current_user.email
            ],  # Assumes current_user has an email attribute
            context={
                "user_name": current_user.username,  # Assumes current_user has a username attribute
                "organization_name": name,
                "organization_description": description,
                "organization_email": email,
                "organization_website": website,
            },
        )

        return redirect(url_for("organization.list_organizations"))

    return render_template("organization/create_organization.html")


@organization_bp.route("/organization/edit/<org_id>", methods=["GET", "POST"])
@login_required
def edit_organization(org_id):
    # Fetch the organization to be edited
    organization = db["organizations"].find_one({"_id": ObjectId(org_id)})
    if not organization:
        flash("Organization not found.")
        return redirect(url_for("organization.list_organizations"))

    # Check if the user is an admin of the organization
    # TODO: Extract permission check to a separate function for reuse.
    if not any(
        str(org["org_id"]) == str(org_id) and org["role"] == "admin"
        for org in current_user.organizations
    ):
        flash("You do not have permission to edit this organization.")
        print(org_id, current_user.organizations)
        return redirect(url_for("organization.organization_detail", org_id=org_id))

    if request.method == "POST":
        # Extract updated organization details from the form
        name = request.form.get("name")
        description = request.form.get("description")
        email = request.form.get("email")
        website = request.form.get("website")

        # TODO: Add form validation to ensure required fields are filled out.
        # Update the organization details in the database
        db["organizations"].update_one(
            {"_id": ObjectId(org_id)},
            {
                "$set": {
                    "name": name,
                    "description": description,
                    "email": email,
                    "website": website,
                }
            },
        )

        flash("Organization updated successfully!")
        return redirect(url_for("organization.organization_detail", org_id=org_id))

    return render_template(
        "organization/edit_organization.html", organization=organization
    )


@organization_bp.route("/organization/delete/<org_id>", methods=["POST"])
@login_required
def delete_organization(org_id):
    # Fetch the organization to be deleted
    organization = db["organizations"].find_one({"_id": ObjectId(org_id)})
    if not organization:
        flash("Organization not found.")
        return redirect(url_for("organization.list_organizations"))

    # Check if the user is an admin of the organization
    # TODO: Extract permission check to a separate function for reuse.
    if not any(
        str(org["org_id"]) == str(org_id) and org["role"] == "admin"
        for org in current_user.organizations
    ):
        flash("You do not have permission to delete this organization.")
        return redirect(url_for("organization.organization_detail", org_id=org_id))

    # Delete the organization from the database
    db["organizations"].delete_one({"_id": ObjectId(org_id)})

    # Remove the organization from all users' lists
    # TODO: Consider adding a confirmation step before deletion.
    db["users"].update_many(
        {"organizations.org_id": ObjectId(org_id)},
        {"$pull": {"organizations": {"org_id": ObjectId(org_id)}}},
    )

    flash("Organization deleted successfully!")
    return redirect(url_for("organization.list_organizations"))


@organization_bp.route("/demonstration/create", methods=["GET", "POST"])
@login_required
def create_demonstration():
    """
    Creates a new demonstration and links it to an organization if the user has permission.
    """
    if request.method == "POST":
        # Extract demonstration details from the form
        title = request.form.get("title")
        date = request.form.get("date")
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time")
        topic = request.form.get("topic")
        facebook = request.form.get("facebook")
        city = request.form.get("city")
        address = request.form.get("address")
        event_type = request.form.get("event_type")
        route = request.form.get("route")
        organization_id = request.form.get("organization_id")

        # Fetch the organization to ensure it exists and the user has permission to link to it
        # TODO: Add error handling for invalid ObjectId format.
        organization = db["organizations"].find_one({"_id": ObjectId(organization_id)})
        if not organization or not any(
            str(org["org_id"]) == str(organization_id)
            and org["role"] in ["admin", "member"]
            for org in current_user.organizations
        ):
            flash(
                "Organization not found or you do not have permission to link to this organization."
            )
            return redirect(url_for("organization.create_demonstration"))

        # Determine if the demonstration should be approved based on the organization's verified status
        approved = organization.get("verified", False)

        # Create the demonstration record with linked organization
        demonstration = Demonstration(
            title=title,
            date=date,
            start_time=start_time,
            end_time=end_time,
            topic=topic,
            facebook=facebook,
            city=city,
            organizers=[Organizer(organization_id=organization_id)],
            address=address,
            event_type=event_type,
            route=route,
            linked_organizations=[organization_id],  # Set editing rights
            approved=approved,  # Set approval based on the organization's verified status
        )

        # Insert the demonstration into the database
        result = db["demonstrations"].insert_one(demonstration.to_dict())

        flash("Demonstration created successfully!")
        return redirect(url_for("organization.list_organizations"))

    # Fetch only the organizations the user has access to
    # TODO: Optimize query if the list of accessible organizations is large.

    accessible_orgs = [org for org in current_user.organizations]
    organizations = db["organizations"].find(
        {"_id": {"$in": [ObjectId(org["org_id"]) for org in accessible_orgs]}}
    )

    return render_template(
        "demonstration/create_demonstration.html", organizations=organizations
    )
