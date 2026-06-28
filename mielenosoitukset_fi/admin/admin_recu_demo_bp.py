import re
from copy import deepcopy
from datetime import datetime, date

from bson.objectid import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required
from mielenosoitukset_fi.utils.flashing import flash_message

from mielenosoitukset_fi.utils.classes import RecurringDemonstration, Organizer, RepeatSchedule
from mielenosoitukset_fi.utils.cities import normalize_city_key
from mielenosoitukset_fi.utils.variables import CITY_LIST
from mielenosoitukset_fi.utils.wrappers import permission_required, admin_required

from mielenosoitukset_fi.utils.admin.demonstration import collect_tags
from mielenosoitukset_fi.utils.demo_cancellation import cancel_demo
from mielenosoitukset_fi.demonstrations.audit import record_demo_change
from .utils import mongo, _ADMIN_TEMPLATE_FOLDER

admin_recu_demo_bp = Blueprint(
    "admin_recu_demo", __name__, url_prefix="/admin/recu_demo"
)

CHILD_BULK_FIELD_MAP = {
    "title": ("title",),
    "description": ("description",),
    "times": ("start_time", "end_time"),
    "location": ("city", "city_key", "address"),
    "type": ("event_type",),
    "route": ("route",),
    "organizers": ("organizers",),
    "tags": ("tags",),
    "links_and_images": ("facebook", "cover_picture", "gallery_images"),
    "approved": ("approved",),
}

from .utils import AdminActParser, log_admin_action_V2
from flask_login import current_user


@admin_recu_demo_bp.before_request
def log_request_info():
    """Log request information before handling it."""
    log_admin_action_V2(
        AdminActParser().log_request_info(request.__dict__, current_user)
    )


def _render_recu_demo_form(*, form_action, title, submit_button_text, demo=None):
    """Render the shared recurring-demonstration form."""
    child_demos = []
    child_counts = {"total": 0, "future": 0, "shown": 0}
    frozen_child_ids = set()
    if demo and demo._id:
        parent_id = ObjectId(demo._id)
        today_string = date.today().isoformat()
        frozen_child_ids = {str(child_id) for child_id in demo.freezed_children}
        child_counts["total"] = mongo.demonstrations.count_documents({"parent": parent_id})
        child_counts["future"] = mongo.demonstrations.count_documents(
            {"parent": parent_id, "date": {"$gte": today_string}}
        )
        child_demos = list(
            mongo.demonstrations.find(
                {"parent": parent_id, "date": {"$gte": today_string}},
                {
                    "title": 1,
                    "date": 1,
                    "start_time": 1,
                    "city": 1,
                    "approved": 1,
                    "cancelled": 1,
                    "cancellation_reason": 1,
                },
            )
            .sort("date", 1)
            .limit(200)
        )
        child_counts["shown"] = len(child_demos)
        for child in child_demos:
            child["is_frozen"] = str(child["_id"]) in frozen_child_ids
            child["is_break"] = child.get("date") in (demo.break_dates or [])

    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}recu_demonstrations/_form_v2.html",
        demo=demo,
        form_action=form_action,
        title=title,
        submit_button_text=submit_button_text,
        city_list=CITY_LIST,
        all_organizations=list(mongo.organizations.find()),
        child_demos=child_demos,
        child_counts=child_counts,
        frozen_child_ids=frozen_child_ids,
        today=date.today().isoformat(),
    )


def _safe_text(value):
    """Return a lower-cased string for filtering, tolerating missing fields."""
    return (value or "").lower()


def _safe_demo_date(value):
    """Return a sortable date, falling back for malformed legacy records."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return date.max


def _get_repeat_frequency(form):
    """Support both legacy and current recurrence field names."""
    raw_frequency = form.get("frequency_type") or form.get("recurrence_type") or "none"
    return raw_frequency.lower()


def _get_repeat_interval(form, frequency):
    """Normalize repeat interval so `none` schedules always serialize safely."""
    if frequency == "none":
        return 0

    raw_interval = (
        form.get("frequency_interval") or form.get("recurrence_interval") or "1"
    )
    try:
        interval = int(raw_interval)
    except (TypeError, ValueError):
        interval = 1
    return max(interval, 1)


def _get_route_points(form):
    """Collect route points from both pill-based and legacy text inputs."""
    route_points = [
        point.strip() for point in form.getlist("route[]") if point and point.strip()
    ]
    if route_points:
        return route_points

    legacy_route = form.get("route")
    if not legacy_route:
        return []

    return [point.strip() for point in legacy_route.split(",") if point.strip()]


def _collect_break_dates(form):
    """Collect unique recurring-series break dates from repeated date inputs."""
    dates = []
    seen = set()
    for raw_date in form.getlist("break_dates"):
        value = (raw_date or "").strip()
        if not value:
            continue
        try:
            normalized = datetime.strptime(value, "%Y-%m-%d").date().isoformat()
        except ValueError:
            continue
        if normalized not in seen:
            dates.append(normalized)
            seen.add(normalized)
    return sorted(dates)


def _current_admin_actor(source):
    return {
        "user_id": str(current_user.id),
        "source": source,
        "username": getattr(current_user, "username", None),
    }


def _cancel_recurring_children(parent_id, child_query, reason, action, message):
    """Cancel children scoped to a recurring parent and record per-child audit history."""
    cancelled_count = 0
    matched_count = 0
    for child in mongo.demonstrations.find(child_query):
        matched_count += 1
        old_child = deepcopy(child)
        cancelled = cancel_demo(
            child,
            cancelled_by=_current_admin_actor("admin_recurring"),
            reason=reason,
        )
        updated_child = mongo.demonstrations.find_one({"_id": child["_id"]}) or child
        if cancelled:
            cancelled_count += 1
            record_demo_change(
                child["_id"],
                old_child,
                updated_child,
                action=action,
                message=message,
                extra_details={
                    "parent_id": str(parent_id),
                    "reason": reason,
                },
            )
    return matched_count, cancelled_count


def _cancel_children_for_break_dates(parent_id, break_dates):
    """Mark already-created children on break dates as cancelled."""
    if not break_dates:
        return 0, 0
    return _cancel_recurring_children(
        parent_id,
        {"parent": parent_id, "date": {"$in": break_dates}},
        "Toistuvan mielenosoituksen taukopäivä",
        "cancel_recurring_child_break",
        "Lapsimielenosoitus peruttiin sarjan taukopäivän vuoksi",
    )


def _collect_organizers(form, existing_organizers=None):
    """Collect organizer cards even if client-side indexes become sparse."""
    organizers = []
    existing_by_organization_id = {
        str(organizer.get("organization_id")): organizer
        for organizer in (existing_organizers or [])
        if organizer.get("organization_id")
    }
    existing_by_record_id = {
        str(organizer.get("_id")): organizer
        for organizer in (existing_organizers or [])
        if organizer.get("_id")
    }
    organizer_indexes = sorted(
        {
            int(match.group(1))
            for key in form.keys()
            if (match := re.match(r"organizer_name_(\d+)$", key))
        }
        | {
            int(match.group(1))
            for key in form.keys()
            if (match := re.match(r"organizer_id_(\d+)$", key))
        }
    )

    for index in organizer_indexes:
        name = form.get(f"organizer_name_{index}")
        organization_id = form.get(f"organizer_id_{index}")
        organizer_record_id = form.get(f"organizer_record_id_{index}")
        if not name and not organization_id:
            continue

        existing = deepcopy(
            existing_by_organization_id.get(str(organization_id))
            or existing_by_record_id.get(str(organizer_record_id))
            or {}
        )
        organizer = Organizer(
            name=name,
            email=form.get(f"organizer_email_{index}"),
            website=form.get(f"organizer_website_{index}"),
            organization_id=organization_id,
            is_private=form.get(f"organizer_is_private_{index}") == "on",
            show_name_public=form.get(f"organizer_show_name_{index}") == "on",
            show_email_public=form.get(f"organizer_show_email_{index}") == "on",
        )
        organizer_data = organizer.to_dict()
        if existing:
            for field_name, default_value in (
                ("is_private", False),
                ("show_name_public", True),
                ("show_email_public", True),
            ):
                if field_name not in existing and organizer_data.get(field_name) == default_value:
                    organizer_data.pop(field_name, None)
            for field_name in ("logo", "url"):
                if field_name not in existing and organizer_data.get(field_name) is None:
                    organizer_data.pop(field_name, None)
        for metadata_field in ("_id", "url", "logo"):
            if metadata_field in existing:
                organizer_data[metadata_field] = existing[metadata_field]
        existing.update(organizer_data)
        organizers.append(existing)

    return organizers


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
    recurring_demos = []
    for recudemo in list(mongo.recu_demos.find(query)):
        try:
            recurring_demos.append(RecurringDemonstration.from_dict(recudemo))
        except Exception:
            continue

    # Filter based on search query and date
    filtered_recurring_demos = [
        demo
        for demo in recurring_demos
        if (
            _safe_text(search_query) in _safe_text(demo.title)
            or _safe_text(search_query) in _safe_text(demo.city)
            or _safe_text(search_query) in _safe_text(demo.address)
        )
    ]

    # Sort the filtered recurring demonstrations by date
    filtered_recurring_demos.sort(key=lambda x: _safe_demo_date(x.date))

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

    return _render_recu_demo_form(
        form_action=url_for("admin_recu_demo.create_recu_demo"),
        title="Luo toistuva mielenosoitus",
        submit_button_text="Luo",
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
    return _render_recu_demo_form(
        demo=recurring_demo,
        form_action=url_for("admin_recu_demo.edit_recu_demo", demo_id=demo_id),
        title="Muokkaa toistuvaa mielenosoitusta",
        submit_button_text="Vahvista muokkaus",
    )


def handle_recu_demo_form(request, is_edit=False, demo_id=None):
    """Handle form submission for creating or editing a recurring demonstration."""
    existing_demo = (
        mongo.recu_demos.find_one({"_id": ObjectId(demo_id)})
        if is_edit and demo_id
        else None
    )

    # Basic info
    title = request.form.get("title")
    description = request.form.get("description")
    date = request.form.get("date")
    start_time = request.form.get("start_time")
    end_time = request.form.get("end_time")
    facebook = request.form.get("facebook")
    city = request.form.get("city") or ""
    address = request.form.get("address")
    event_type = request.form.get("type")
    route = _get_route_points(request.form)
    approved = request.form.get("approved") == "on"

    tags = collect_tags(request)
    cover_picture = request.form.get("cover_picture")
    gallery_images = parse_gallery_images_field(request.form.get("gallery_images"))

    organizers = _collect_organizers(
        request.form,
        existing_organizers=(existing_demo or {}).get("organizers", []),
    )

    # Recurrence / repeat schedule
    freq = _get_repeat_frequency(request.form)
    interval = _get_repeat_interval(request.form, freq)
    end_date = request.form.get("end_date") or request.form.get("recurrence_end_date")

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

    repeat_schedule = RepeatSchedule(
        frequency=freq,
        interval=interval,
        weekday=weekday,
        monthly_option=monthly_option,
        day_of_month=day_of_month,
        nth_weekday=nth_weekday,
        weekday_of_month=weekday_of_month,
        end_date=end_date,
    ).to_dict()
    break_dates = _collect_break_dates(request.form)

    if existing_demo:
        for field_name, submitted_value in (
            ("start_time", start_time),
            ("end_time", end_time),
        ):
            existing_value = existing_demo.get(field_name)
            if (
                existing_value
                and submitted_value
                and str(existing_value)[:5] == str(submitted_value)[:5]
            ):
                if field_name == "start_time":
                    start_time = existing_value
                else:
                    end_time = existing_value

        if not route and existing_demo.get("route") is None:
            route = None
        if not gallery_images and existing_demo.get("gallery_images") is None:
            gallery_images = None
        for field_name, value in (
            ("description", description),
            ("facebook", facebook),
            ("cover_picture", cover_picture),
        ):
            if value == "" and existing_demo.get(field_name) is None:
                if field_name == "description":
                    description = None
                elif field_name == "facebook":
                    facebook = None
                else:
                    cover_picture = None

    # Assemble demonstration data
    demonstration_data = {
        "title": title,
        "description": description,
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "tags": tags,
        "facebook": facebook,
        "city": city,
        "city_key": normalize_city_key(city),
        "address": address,
        "event_type": event_type,
        "route": route,
        "approved": approved,
        "cover_picture": cover_picture,
        "gallery_images": gallery_images,
        "repeat_schedule": repeat_schedule,
        "break_dates": break_dates,
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
            _, cancelled_count = _cancel_children_for_break_dates(
                ObjectId(demo_id), break_dates
            )
            message = "Toistuva mielenosoitus päivitetty onnistuneesti."
            if cancelled_count:
                message += f" Peruttiin {cancelled_count} taukopäivälle osuvaa lapsimielenosoitusta."
            flash_message(message)
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
                (
                    "admin_recu_demo.edit_recu_demo"
                    if is_edit
                    else "admin_recu_demo.create_recu_demo"
                ),
                demo_id=demo_id,
            )
        )


@admin_recu_demo_bp.route("/<demo_id>/bulk-update-children", methods=["POST"])
@login_required
@admin_required
@permission_required("EDIT_RECURRING_DEMO")
@permission_required("EDIT_DEMO")
def bulk_update_children(demo_id):
    """Copy selected recurring-parent fields to selected generated children."""
    try:
        parent_id = ObjectId(demo_id)
    except Exception:
        flash_message("Virheellinen toistuvan mielenosoituksen tunniste.", "error")
        return redirect(url_for("admin_recu_demo.recu_demo_control"))

    parent = mongo.recu_demos.find_one({"_id": parent_id})
    if not parent:
        flash_message("Toistuvaa mielenosoitusta ei löytynyt.", "error")
        return redirect(url_for("admin_recu_demo.recu_demo_control"))

    requested_fields = [
        field for field in request.form.getlist("fields") if field in CHILD_BULK_FIELD_MAP
    ]
    child_scope = request.form.get("child_scope", "selected")
    requested_child_ids = set(request.form.getlist("child_ids"))
    if not requested_fields or (child_scope == "selected" and not requested_child_ids):
        flash_message("Valitse vähintään yksi päivitettävä kenttä ja lapsimielenosoitus.", "error")
        return redirect(url_for("admin_recu_demo.edit_recu_demo", demo_id=demo_id))

    child_query = {"parent": parent_id}
    if child_scope == "all_future":
        child_query["date"] = {"$gte": date.today().isoformat()}
    else:
        child_ids = []
        for child_id in requested_child_ids:
            try:
                child_ids.append(ObjectId(child_id))
            except Exception:
                continue
        child_query["_id"] = {"$in": child_ids}

    children = mongo.demonstrations.find(child_query)
    update_fields = {}
    for field_group in requested_fields:
        for child_field in CHILD_BULK_FIELD_MAP[field_group]:
            if child_field == "event_type":
                value = parent.get("event_type") or parent.get("type")
            elif child_field == "city_key":
                value = parent.get("city_key") or normalize_city_key(parent.get("city"))
            else:
                value = parent.get(child_field)
            update_fields[child_field] = deepcopy(value)

    updated_ids = []
    updated_count = 0
    for child in children:
        new_child = deepcopy(child)
        new_child.update(deepcopy(update_fields))
        mongo.demonstrations.update_one(
            {"_id": child["_id"], "parent": parent_id},
            {"$set": deepcopy(update_fields)},
        )
        record_demo_change(
            child["_id"],
            child,
            new_child,
            action="bulk_update_recurring_child",
            message="Toistuvan mielenosoituksen tiedot kopioitiin lapsimielenosoitukseen",
            extra_details={
                "parent_id": demo_id,
                "field_groups": requested_fields,
            },
        )
        updated_ids.append(str(child["_id"]))
        updated_count += 1

    if request.form.get("freeze_after_update") == "on" and updated_ids:
        mongo.recu_demos.update_one(
            {"_id": parent_id},
            {"$addToSet": {"freezed_children": {"$each": updated_ids}}},
        )

    flash_message(
        f"Päivitettiin {updated_count} lapsimielenosoitusta.",
        "success",
    )
    return redirect(url_for("admin_recu_demo.edit_recu_demo", demo_id=demo_id))


@admin_recu_demo_bp.route("/<demo_id>/bulk-cancel-children", methods=["POST"])
@login_required
@admin_required
@permission_required("EDIT_RECURRING_DEMO")
@permission_required("EDIT_DEMO")
def bulk_cancel_children(demo_id):
    """Mark selected or all future generated children from a recurring parent cancelled."""
    try:
        parent_id = ObjectId(demo_id)
    except Exception:
        flash_message("Virheellinen toistuvan mielenosoituksen tunniste.", "error")
        return redirect(url_for("admin_recu_demo.recu_demo_control"))

    parent = mongo.recu_demos.find_one({"_id": parent_id})
    if not parent:
        flash_message("Toistuvaa mielenosoitusta ei löytynyt.", "error")
        return redirect(url_for("admin_recu_demo.recu_demo_control"))

    child_scope = request.form.get("child_scope", "selected")
    requested_child_ids = set(request.form.getlist("child_ids"))
    if child_scope == "selected" and not requested_child_ids:
        flash_message("Valitse vähintään yksi peruttava lapsimielenosoitus.", "error")
        return redirect(url_for("admin_recu_demo.edit_recu_demo", demo_id=demo_id))

    child_query = {"parent": parent_id}
    if child_scope == "all_future":
        child_query["date"] = {"$gte": date.today().isoformat()}
    else:
        child_ids = []
        for child_id in requested_child_ids:
            try:
                child_ids.append(ObjectId(child_id))
            except Exception:
                continue
        child_query["_id"] = {"$in": child_ids}

    reason = (
        request.form.get("cancellation_reason")
        or "Peruttu toistuvan mielenosoituksen sarjahallinnasta"
    )
    matched_count, cancelled_count = _cancel_recurring_children(
        parent_id,
        child_query,
        reason,
        "bulk_cancel_recurring_child",
        "Lapsimielenosoitus peruttiin toistuvan sarjan hallinnasta",
    )
    if matched_count == 0:
        flash_message("Valittuja lapsimielenosoituksia ei löytynyt.", "error")
    elif cancelled_count == 0:
        flash_message("Valitut lapsimielenosoitukset olivat jo peruttuja.", "info")
    else:
        flash_message(f"Peruttiin {cancelled_count} lapsimielenosoitusta.", "success")
    return redirect(url_for("admin_recu_demo.edit_recu_demo", demo_id=demo_id))


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
