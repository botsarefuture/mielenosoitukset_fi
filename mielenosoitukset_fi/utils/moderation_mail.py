"""One private registered action-link family per moderation mail recipient."""
import re
from flask import current_app, has_request_context
from mielenosoitukset_fi.utils.system_teams import national_recipients


def _recipient_links(demo_id, recipient):
    """Build external links from background jobs that have no request context."""
    from mielenosoitukset_fi.admin.admin_demo_bp import (
        generate_demo_approve_link, generate_demo_preview_link, generate_demo_reject_link,
    )
    if has_request_context():
        return (generate_demo_approve_link(str(demo_id), recipient=recipient),
                generate_demo_preview_link(str(demo_id), recipient=recipient),
                generate_demo_reject_link(str(demo_id), recipient=recipient))
    base = current_app.config.get("GOD_AUTH_ORIGIN") or "https://mielenosoitukset.fi"
    with current_app.test_request_context(base_url=base):
        return (generate_demo_approve_link(str(demo_id), recipient=recipient),
                generate_demo_preview_link(str(demo_id), recipient=recipient),
                generate_demo_reject_link(str(demo_id), recipient=recipient))


def personalize_moderation_messages(db, demo_id, messages, *, national=False):
    result = []
    for message in messages:
        recipients = national_recipients(db) if national else [{"email": value} for value in message["recipients"]]
        seen = set()
        for recipient in recipients:
            email = recipient["email"].strip()
            if not email or email.casefold() in seen:
                continue
            seen.add(email.casefold())
            if not recipient.get("user_id"):
                user = db.users.find_one({"email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}}, {"username": 1})
                if user:
                    recipient = {**recipient, "user_id": str(user["_id"]), "username": user.get("username")}
            approve_link, preview_link, reject_link = _recipient_links(demo_id, recipient)
            context = {**message["context"],
                "approve_link": approve_link, "preview_link": preview_link, "reject_link": reject_link}
            result.append({**message, "recipients": [email], "context": context})
    return result
