"""
This module contains the blueprint for the AM (Action Manager) module.

The module contains the following routes:
    
        * /signup
        * /signup/<action_id>
        * /submit-signup/<action_id>
        * /confirm-participation/<hash>
        * /cancel-participation/<hash>
        * /confirm-cancel/<hash>
        
The module also contains the following functions:
        
            * hash_participant_id
            * confirm_participation
            * cancel_participation
            * confirm_cancel
            

"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from mielenosoitukset_fi.utils.database import get_database_manager
from AM.models import Shift, Role, Action
from mielenosoitukset_fi.utils.flashing import flash_message
from mielenosoitukset_fi.emailer.EmailSender import EmailSender
import hashlib
import datetime
from AM.utils import get_action_by_id

from bson.objectid import ObjectId

am_bp = Blueprint("am", __name__)

DB = get_database_manager()
actions_collection = DB["actions"]


emailer = EmailSender()


@am_bp.route("/signup", methods=["GET", "POST"])
def signup():
    """
    Handle the signup process for actions and show a thank you message.

    Returns
    -------
    response : flask.Response
        The response object to render the thank you template or redirect to another page.
    """
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        if not name or not email:
            flash("Name and email are required!", "error")
            return redirect(url_for("am.signup"))
        flash("Signup successful!", "success")
        return redirect(url_for("am.thank_you"))
    return render_template("AM/next_steps.html")


@am_bp.route("/thank-you", methods=["GET"])
def thank_you():
    """
    Show a thank you message after successful signup.

    Returns
    -------
    response : flask.Response
        The response object to render the thank you template.
    """
    return render_template("AM/thank_you.html")


@am_bp.route("/signup/<action_id>/", methods=["GET"])
def signup_s1(action_id):
    """
    Handle the first step of the signup process for actions: return template with role descriptions.

    Parameters
    ----------
    action_id : str
        The ID of the action.

    Returns
    -------
    response : flask.Response
        The response object to render the signup step 1 template.
    """

    action = actions_collection.find_one({"_id": ObjectId(action_id)})

    action = Action.from_dict(action)
    roles = action.roles

    return render_template("AM/signup_s1.html", action=action, roles=roles)


@am_bp.route("/submit-signup/<action_id>", methods=["POST"])
def submit_signup(action_id):
    """
    Handle the submission of the signup form.

    Returns
    -------
    response : flask.Response
        The response object to redirect to the signup page with a success or error message.
    """
    print(request.form.to_dict(), action_id)
    name = request.form.get("name")
    email = request.form.get("email")
    phone = request.form.get("phone")
    selected_roles = request.form.get("selected_roles").split(",")

    if not name or not email or not phone:
        flash("All contact information fields are required!", "error")
        return redirect(url_for("am.signup"))

    result = DB["action_signups"].insert_one(
        {
            "action_id": ObjectId(action_id),
            "name": name,
            "email": email,
            "phone": phone,
            "roles": request.form.getlist("roles"),
            "confirmed": False,
        }
    )

    if result.inserted_id:
        _id = result.inserted_id
        hash = hash_participant_id(_id)
        DB["action_signups"].update_one({"_id": _id}, {"$set": {"hash": hash}})

    emailer.queue_email(
        "AM/confirm_participation.html",
        subject="Vahvista osallistumisesi!",
        recipients=[email],
        context={
            "name": name,
            "action_id": action_id,
            "action": Action.from_dict(
                actions_collection.find_one({"_id": ObjectId(action_id)})
            ),
            "confirmation_link": url_for(
                "am.confirm_participation", hash=hash, _external=True
            ),
        },
    )

    flash("Signup successful!", "success")
    return redirect(url_for("am.signup"))


def hash_participant_id(participant_id):
    """
    Hash the participant ID for confirmation.

    Parameters
    ----------
    participant_id : str
        The ID of the participant.

    Returns
    -------
    hash : str
        The hashed participant ID.
    """
    return hashlib.sha256(str(participant_id).encode()).hexdigest()


@am_bp.route("/confirm-participation/<hash>", methods=["GET"])
def confirm_participation(hash):
    """
    Confirm participation in an action.

    Parameters
    ----------
    hash : str
        The hash of the signup.

    Returns
    -------
    response : flask.Response
        The response object to render the confirmation template.
    """
    signup = DB["action_signups"].find_one({"hash": hash})
    if not signup:
        flash("Invalid signup link!", "error")
        return redirect(url_for("am.signup"))

    if not signup["confirmed"]:

        action = Action.from_dict(
            actions_collection.find_one({"_id": ObjectId(signup["action_id"])})
        )

        DB["action_signups"].update_one(
            {"_id": signup["_id"]}, {"$set": {"confirmed": True}}
        )

        emailer.queue_email(
            "AM/confirmation_email.html",
            subject="Osallistumisesi vahvistettu!",
            recipients=[signup["email"]],
            context={
                "name": signup["name"],
                "action": action,
                "cancel_link": url_for(
                    "am.cancel_participation", hash=hash, _external=True
                ),
            },
        )

        return render_template(
            "AM/confirm_participation.html", signup=signup, action=action
        )

    else:
        flash_message("You have already confirmed your participation.")
        return redirect("/")


@am_bp.route("/cancel-participation/<hash>", methods=["GET"])
def cancel_participation(hash):
    """
    Cancel participation in an action.

    Parameters
    ----------
    hash : str
        The hash of the signup.

    Returns
    -------
    response : flask.Response
        The response object to render the cancellation template.
    """
    signup = DB["action_signups"].find_one({"hash": hash})
    if not signup:
        flash("Invalid signup link!", "error")
        return redirect(url_for("am.signup"))

    DB["action_signups"].update_one(
        {"_id": signup["_id"]},
        {
            "$set": {
                "cancellation_started": True,
                "last_updated": datetime.datetime.now(),
            }
        },
    )

    return render_template(
        "AM/cancel_participation.html",
        cancel_confirm_link=url_for("am.confirm_cancel", hash=hash),
    )


@am_bp.route("/confirm-cancel/<hash>", methods=["GET"])
def confirm_cancel(hash):
    """
    Confirm the cancellation of participation in an action.

    Parameters
    ----------
    hash : str
        The hash of the signup.

    Returns
    -------
    response : flask.Response
        The response object to render the confirmation of cancellation template.
    """
    signup = DB["action_signups"].find_one({"hash": hash})

    if signup["cancelled"]:
        flash("You have already cancelled this shit fuck off man pls im horny")
        abort(400)

    DB["action_signups"].update_one(
        {"_id": signup["_id"]},
        {"$set": {"cancelled": True, "last_updated": datetime.datetime.now()}},
    )

    emailer.queue_email(
        "AM/cancellation_email.html",
        subject="Osallistumisesi peruutettu!",
        recipients=[signup["email"]],
        context={
            "name": signup["name"],
            "action": Action.from_dict(
                actions_collection.find_one({"_id": ObjectId(signup["action_id"])})
            ),
        },
    )
    flash_message("Successfully cancelled participation", "success")

    return redirect("/")
