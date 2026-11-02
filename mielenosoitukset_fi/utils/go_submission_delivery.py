"""Prepare Go submissions using Flask's existing moderation and mail helpers.

No HTTP surface and no SMTP here. The notification worker persists preparation
before inserting stable child jobs, then uses its normal claim/receipt handling.
"""
from io import BytesIO

from flask import current_app

from mielenosoitukset_fi.utils.time_utils import utcnow
from mielenosoitukset_fi.utils.cities import normalize_city_key
from mielenosoitukset_fi.utils.city_assignment import active_city_admins_for_city, assign_demo_to_city
from mielenosoitukset_fi.utils.classes import Case
from mielenosoitukset_fi.utils.demo_cancellation import cancellation_link_messages
from mielenosoitukset_fi.utils.s3 import upload_image_fileobj


def _prepare_media(db, record, demo):
    if demo.get("cover_picture"):
        return
    image = record.get("pending_image")
    photo = None
    if image:
        # Existing Pillow decode, EXIF orientation, RGB JPEG normalization and S3
        # uploader. Never serve the untrusted bytes stored in the private record.
        photo = upload_image_fileobj(
            current_app.config.get("S3_BUCKET", "mielenosoitukset.fi"),
            BytesIO(image), "submission-image", "demo_pics",
        )
        if not photo:
            raise RuntimeError("Submission image preparation failed")
    else:
        imported = (record.get("pending_submitter") or {}).get("imported_image_url", "")
        cdn = (current_app.config.get("CDN_BASE_URL") or "").rstrip("/")
        if cdn and imported.startswith(cdn + "/"):
            photo = imported
    if photo and not demo.get("cover_picture"):
        db.demonstrations.update_one(
            {"_id": demo["_id"], "cover_picture": {"$in": [None, ""]}},
            {"$set": {"img": photo, "cover_picture": photo, "gallery_images": [photo],
                      "cover_source": "user", "last_modified": utcnow()}},
        )


def _prepare_messages(db, record, demo, submitter):
    from mielenosoitukset_fi.admin.admin_demo_bp import (
        generate_demo_approve_link, generate_demo_preview_link, generate_demo_reject_link,
    )
    context = {key: demo.get(key) for key in ("title", "date", "city", "address")}
    confirmation = {
        "template_name": "demo_submitter_confirmation.html",
        "subject": "Kiitos mielenosoituksen ilmoittamisesta",
        "recipients": [submitter["submitter_email"]], "context": dict(context),
    }
    context.update({key: submitter.get(key) for key in (
        "submitter_name", "submitter_email", "submitter_role",
    )})
    context.update(approve_link=generate_demo_approve_link(str(demo["_id"])),
                   preview_link=generate_demo_preview_link(str(demo["_id"])),
                   reject_link=generate_demo_reject_link(str(demo["_id"])))
    city = normalize_city_key(demo.get("city", ""))
    admins = active_city_admins_for_city(db, city)
    assignment = None
    if admins and not any(demo.get(key) for key in ("approved", "rejected", "cancelled")):
        assignment = assign_demo_to_city(
            db, demo["_id"], city, admins,
            template_name="admin_demo_city_assignment.html",
            subject=f"Uusi mielenosoitus odottaa hyväksyntää: {demo.get('city', '')}",
            context=context,
            escalate_after_hours=current_app.config.get("CITY_ASSIGNMENT_ESCALATION_HOURS", 24),
        )
    admin = assignment or {
        "template_name": "admin_demo_approve_notification.html",
        "subject": "Uusi mielenosoitus odottaa hyväksyntää",
        "recipients": ["tuki@mielenosoitukset.fi"], "context": context,
    }
    return [
        {"suffix": "confirmation", "notification_type": "go_confirmation",
         "marks_admin_contact": False, "messages": [confirmation]},
        {"suffix": "moderation", "notification_type": "city_assignment" if assignment else "initial_submission",
         "marks_admin_contact": not bool(assignment), "messages": [admin]},
        {"suffix": "cancellation", "notification_type": "go_cancellation",
         "marks_admin_contact": False, "messages": cancellation_link_messages(demo)},
    ]


def prepare_go_submission(db, queue, job, owner, owned_update):
    """Replay preparation after crashes without recreating delivered child jobs."""
    record = db.demo_submission_tokens.find_one({"_id": job["submission_record"], "go_submission": True})
    demo = db.demonstrations.find_one({"_id": job["demo_id"]})
    submitter = db.submitters.find_one({"demonstration_id": job["demo_id"]})
    if not record or not demo or not submitter:
        raise RuntimeError("Go submission records are incomplete")
    children = job.get("prepared_children")
    if children is None:
        # A stable case ID protects retries and preserves later admin edits.
        if not db.cases.find_one({"_id": demo["_id"]}, {"_id": 1}):
            case = Case(case_type="new_demo", demo_id=demo["_id"], submitter=submitter,
                        submitter_id=(record.get("pending_submitter") or {}).get("actor_id"),
                        meta={"urgency": "high"}, _id=demo["_id"])
            db.cases.update_one({"_id": case._id}, {"$setOnInsert": case.to_dict()}, upsert=True)
        _prepare_media(db, record, demo)
        # Background jobs have an app context, not a visitor request. Build
        # external links against trusted server configuration, never a payload URL.
        origin = current_app.config.get("GO_SUBMIT_ORIGIN", "https://mielenosoitukset.fi")
        with current_app.test_request_context(base_url=origin):
            children = _prepare_messages(db, record, demo, submitter)
        owned_update(queue, owner, {"$set": {"prepared_children": children, "updated_at": utcnow()}})
    for child in children:
        fields = {key: value for key, value in child.items() if key != "suffix"}
        fields.update(demo_id=demo["_id"], status="pending", created_at=utcnow(), delivery_tracking_version=1)
        queue.update_one(
            {"_id": f"go:{demo['_id']}:{child['suffix']}"}, {"$setOnInsert": fields}, upsert=True,
        )
    db.demo_submission_tokens.update_one(
        {"_id": record["_id"]}, {"$unset": {"pending_image": "", "pending_submitter": "", "pending_event": ""}},
    )
    db.demonstrations.update_one({"_id": demo["_id"]}, {"$unset": {"submission_delivery_pending": ""}})
