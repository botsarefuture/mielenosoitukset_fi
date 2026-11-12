"""Shared organizer form parsing for admin demonstration editors."""

import re

from bson import ObjectId
from flask_babel import gettext as _

from mielenosoitukset_fi.utils.classes import Organizer


def linkable_admin_organization_ids(
    user,
    permission_name,
    *,
    existing_demo=None,
    preserve_existing_only=False,
):
    """Return allowed linked organization ids, or ``None`` when unrestricted."""
    existing_ids = {
        ObjectId(str(organizer.get("organization_id")))
        for organizer in (existing_demo or {}).get("organizers", [])
        if isinstance(organizer, dict)
        and organizer.get("organization_id")
        and ObjectId.is_valid(str(organizer.get("organization_id")))
    }
    if preserve_existing_only:
        return existing_ids

    has_full_permissions = getattr(user, "has_full_permissions", None)
    if (
        callable(has_full_permissions) and has_full_permissions()
    ) or permission_name in getattr(user, "global_permissions", []):
        return None

    membership_ids = {
        membership.organization_id
        for membership in getattr(user, "memberships", [])
        if permission_name in membership.permissions
    }
    return existing_ids | membership_ids


def collect_admin_organizers(form, existing_organizers=None):
    """Return normalized organizer dictionaries from sparse indexed fields.

    Existing organizer records are matched by linked organization or record id
    so immutable metadata survives reordering and edits. Linked organizations
    and exact freeform entries may only appear once.
    """
    existing_by_organization_id = {
        str(organizer.get("organization_id")): organizer
        for organizer in (existing_organizers or [])
        if isinstance(organizer, dict) and organizer.get("organization_id")
    }
    existing_by_record_id = {
        str(organizer.get("_id")): organizer
        for organizer in (existing_organizers or [])
        if isinstance(organizer, dict) and organizer.get("_id")
    }
    indexes = sorted(
        {
            int(match.group(1))
            for key in form.keys()
            if (match := re.match(r"organizer_(?:name|id)_(\d+)$", key))
        }
    )
    linked_ids = set()
    freeform_keys = set()
    organizers = []

    for index in indexes:
        name = (form.get(f"organizer_name_{index}") or "").strip()
        email = (form.get(f"organizer_email_{index}") or "").strip()
        website = (form.get(f"organizer_website_{index}") or "").strip()
        raw_organization_id = (form.get(f"organizer_id_{index}") or "").strip()
        record_id = form.get(f"organizer_record_id_{index}")
        if not any((name, email, website, raw_organization_id, record_id)):
            continue

        organization_id = None
        if raw_organization_id:
            if not ObjectId.is_valid(raw_organization_id):
                raise ValueError(_("Järjestäjän organisaatiotunniste ei ole kelvollinen."))
            organization_id = ObjectId(raw_organization_id)
            if organization_id in linked_ids:
                raise ValueError(
                    _("Sama organisaatio on lisätty järjestäjäksi useammin kuin kerran.")
                )
            linked_ids.add(organization_id)
        else:
            if not name:
                raise ValueError(_("Vapaamuotoisen järjestäjän nimi on pakollinen."))
            identity = (name.casefold(), email.casefold(), website.casefold())
            if identity in freeform_keys:
                raise ValueError(
                    _("Sama vapaamuotoinen järjestäjä on lisätty useammin kuin kerran.")
                )
            freeform_keys.add(identity)

        existing = dict(
            existing_by_organization_id.get(str(organization_id))
            or existing_by_record_id.get(str(record_id))
            or {}
        )
        is_private = form.get(f"organizer_is_private_{index}") == "on"
        show_name_public = form.get(f"organizer_show_name_{index}") == "on"
        show_email_public = form.get(f"organizer_show_email_{index}") == "on"
        if organization_id:
            is_private = False
            show_name_public = True
            show_email_public = True
        elif not is_private:
            if form.get(f"organizer_show_name_{index}") is None:
                show_name_public = True
            if form.get(f"organizer_show_email_{index}") is None:
                show_email_public = True

        organizer_data = Organizer(
            name=name,
            email=email,
            website=website,
            organization_id=organization_id,
            is_private=is_private,
            show_name_public=show_name_public,
            show_email_public=show_email_public,
        ).to_dict()
        for metadata_field in ("_id", "url", "logo"):
            if metadata_field in existing:
                organizer_data[metadata_field] = existing[metadata_field]
        existing.update(organizer_data)
        organizers.append(existing)

    return organizers
