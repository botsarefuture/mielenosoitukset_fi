"""One private registered action-link family per moderation mail recipient."""
import re
from mielenosoitukset_fi.utils.system_teams import national_recipients


def personalize_moderation_messages(db, demo_id, messages, *, national=False):
    from mielenosoitukset_fi.admin.admin_demo_bp import (
        generate_demo_approve_link, generate_demo_preview_link, generate_demo_reject_link,
    )
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
            context = {**message["context"],
                "approve_link": generate_demo_approve_link(str(demo_id), recipient=recipient),
                "preview_link": generate_demo_preview_link(str(demo_id), recipient=recipient),
                "reject_link": generate_demo_reject_link(str(demo_id), recipient=recipient)}
            result.append({**message, "recipients": [email], "context": context})
    return result
