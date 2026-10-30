"""Thin public HTML shell; the browser reads event content from the Go API.

No model construction, geocoding, organization joins or upstream HTTP request
belongs here. Authentication/private previews keep the existing Flask view.
"""
from copy import deepcopy
from datetime import date
from urllib.parse import urlsplit

from bson import ObjectId
from flask import abort, current_app, make_response, redirect, render_template, request, url_for
from flask_babel import _
from flask_login import current_user

from mielenosoitukset_fi.utils.database import DEMO_FILTER
from mielenosoitukset_fi.utils.demo_localization import get_demo_localized_fields
from mielenosoitukset_fi.utils.demo_seo import demo_is_beyond_future_horizon, parse_demo_date

# Only metadata needed before first byte; event body comes from the browser API.
METADATA_PROJECTION = {key: 1 for key in (
    "_id", "approved", "hide", "rejected", "title", "description", "default_language", "translations", "date",
    "start_time", "end_time", "city", "address", "preview_image", "cover_picture",
    "cover_source", "slug", "running_number", "parent", "cancelled",
)}
METADATA_PROJECTION["organizers.organization_id"] = 1


def public_metadata_query(identifier):
    query = deepcopy(DEMO_FILTER)
    query.pop("cancelled", None)  # Public cancellation notices must remain readable.
    query.update(identifier)
    query["$expr"] = {"$and": [
        {"$eq": [{"$type": "$approved"}, "bool"]},
        {"$in": [{"$type": "$hide"}, ["missing", "bool"]]},
        {"$in": [{"$type": "$rejected"}, ["missing", "bool"]]},
    ]}
    return query


def resolve_metadata(db, identifier):
    """Preserve ObjectId, alias, running-number and slug lookup precedence."""
    identifier = str(identifier)
    if len(identifier) > 200:
        return None
    if ObjectId.is_valid(identifier):
        oid = ObjectId(identifier)
        # Do not allow a nonpublic original to resolve as a different alias.
        original = db.demonstrations.find_one({"_id": oid}, METADATA_PROJECTION)
        if original:
            visible = (original.get("approved") is True
                       and ("hide" not in original or original["hide"] is False)
                       and ("rejected" not in original or original["rejected"] is False))
            return original if visible else None
        found = db.demonstrations.find_one(public_metadata_query({"aliases": {"$in": [oid]}}), METADATA_PROJECTION)
        if found:
            return found
    if identifier.isascii() and identifier.isdigit() and len(identifier) <= 18:
        found = db.demonstrations.find_one(public_metadata_query({"running_number": int(identifier)}), METADATA_PROJECTION)
        if found:
            return found
    return db.demonstrations.find_one(public_metadata_query({"slug": identifier}), METADATA_PROJECTION)


def _api_endpoint():
    endpoint = current_app.config.get("PUBLIC_DEMONSTRATION_API_URL", "https://api.mielenosoitukset.fi/api/demonstrations")
    parsed = urlsplit(endpoint)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("Invalid public demonstration API URL")
    return endpoint.rstrip("/")


def detail_messages():
    """The component's portable text contract, supplied by the host application."""
    return {
        "loading": _("Ladataan tapahtuman tietoja..."),
        "error": _("Tapahtuman tietoja ei voitu ladata."),
        "retry": _("Yritä uudelleen"),
        "notFound": _("Tapahtumaa ei löydy tai se ei ole julkinen."),
        "date": _("Ajankohta"), "location": _("Sijainti"),
        "description": _("Kuvaus"), "organizers": _("Järjestäjät"),
        "route": _("Reitti"), "cancelled": _("Tämä mielenosoitus on peruttu."),
        "calendar": _("Lisää kalenteriin (.ics)"), "reminder": _("Tilaa muistutus"),
        "report": _("Ilmoita virheestä"), "invite": _("Kutsu kavereita"),
        "share": _("Jaa tapahtuma"), "shareCopied": _("Linkki kopioitu"),
        "allEvents": _("Kaikki mielenosoitukset"),
        "login": _("Kirjaudu sisään"), "attend": _("Osallistun"),
        "startingFrom": _("alkaen"), "unknownTime": _("Kellonaikaa ei ole ilmoitettu"),
        "gallery": _("Tapahtuman kuvat"), "close": _("Sulje"),
        "previous": _("Edellinen kuva"), "next": _("Seuraava kuva"),
        "showMap": _("Näytä kartta"), "map": _("Kartta"),
        "mapError": _("Karttaa ei voitu ladata."), "directions": _("Avaa reittiohjeet"),
        "series": _("Kaikki tapahtuman ajankohdat"), "website": _("Verkkosivusto"),
        "email": _("Sähköpostiosoite"), "emailOptional": _("Sähköposti (valinnainen)"),
        "reportDescription": _("Kerro virheestä"), "markCancelled": _("Tapahtuma on peruttu"),
        "sendReport": _("Lähetä ilmoitus"), "sendInvites": _("Lähetä kutsut"),
        "chooseFriends": _("Valitse ainakin yksi kaveri."), "noFriends": _("Sinulla ei ole vielä kutsuttavia kavereita."),
        "friendsError": _("Kaverien lataaminen epäonnistui."), "inviteSent": _("Kutsut lähetetty!"),
        "actionError": _("Toiminto epäonnistui. Yritä uudelleen."), "sending": _("Lähetetään..."),
        "saved": _("Tallennettu"), "cancelAttendance": _("Peru osallistuminen"),
        "anonymousOrganizer": _("Yksityishenkilö (nimi piilotettu)"),
        "follow": _("Seuraa"), "following": _("Seurataan"), "followSeries": _("Seuraa sarjaa"),
        "noDescription": _("Tapahtumalle ei ole lisätty kuvausta."),
        "noOrganizers": _("Järjestäjätietoja ei ole ilmoitettu"),
        "organizerProfile": _("Organisaation profiili"),
        "openImage": _("Avaa kuva"), "imageUnavailable": _("Kuvaa ei voitu ladata."),
        "mapLoading": _("Ladataan karttaa..."),
        "loginRequired": _("Kirjaudu sisään ilmoittaaksesi osallistumisestasi."),
        "copyLink": _("Kopioi linkki"), "copyFailed": _("Linkkiä ei voitu kopioida."),
        "facebook": _("Facebook-tapahtuma"), "shareFacebook": _("Jaa Facebookissa"),
        "shareMastodon": _("Jaa Mastodonissa"), "shareX": _("Jaa X:ssä"),
        "shareLinkedIn": _("Jaa LinkedInissä"),
    }


def render_public_detail(db, identifier, locale, recurring_context=None):
    metadata = resolve_metadata(db, identifier)
    if not metadata:
        if current_user.is_authenticated and current_user.has_permission("VIEW_DEMO"):
            return None  # Internal nonpublic preview keeps its privileged workflow.
        abort(404)
    translations = metadata.get("translations")
    metadata["translations"] = {
        lang: {field: value for field, value in values.items()
               if (field in {"title", "description"} and isinstance(value, str))
               or (field == "tags" and isinstance(value, list))}
        for lang, values in (translations.items() if isinstance(translations, dict) else [])
        if isinstance(lang, str) and isinstance(values, dict)
    }
    parsed_date = parse_demo_date(metadata.get("date"))
    metadata["date"] = parsed_date.isoformat() if parsed_date else None
    event_id = str(metadata["_id"])
    parent = metadata.get("parent")
    if recurring_context is None and parent and ObjectId.is_valid(str(parent)):
        parent_doc = db.recu_demos.find_one({"_id": ObjectId(str(parent))}, {"approved": 1, "hide": 1, "rejected": 1})
        if parent_doc and parent_doc.get("approved") and not parent_doc.get("hide") and not parent_doc.get("rejected"):
            return redirect(url_for("siblings_meeting", parent=str(parent), occurrence=metadata.get("slug") or event_id), code=301)
    localized = get_demo_localized_fields(metadata, locale)
    title = localized.get("title") if isinstance(localized.get("title"), str) else None
    title = title or _("Mielenosoitus")
    description = localized.get("description") if isinstance(localized.get("description"), str) else None
    canonical = (recurring_context or {}).get("canonical_url") or url_for(
        "demonstration_detail", demo_id=metadata.get("slug") or metadata.get("running_number") or event_id, _external=True)
    # Keep user/account operations on the existing same-origin routes in this slice.
    urls = {
        "trackView": url_for("track_demo_view"),
        "listing": url_for("demonstrations"),
        "login": url_for("users.auth.login", next=request.full_path.rstrip("?")),
        "calendar": url_for("download_demo_ics", demo_id="__EVENT_ID__"),
        "reminder": url_for("subscribe_reminder", demo_id="__EVENT_ID__"),
        "report": url_for("report"),
        "invite": url_for("api.invite_friends", demo_id="__EVENT_ID__"),
        "friends": url_for("users.profile.api_friends_list"),
        "like": url_for("api.like_demo", demo_id="__EVENT_ID__"),
        "unlike": url_for("api.unlike_demo", demo_id="__EVENT_ID__"),
        "attendance": url_for("api.demo_attending", demo_id="__EVENT_ID__"),
        "followOrganization": url_for("api_follow_organization", org_id="__ORGANIZATION_ID__"),
        "unfollowOrganization": url_for("api_unfollow_organization", org_id="__ORGANIZATION_ID__"),
        "followRecurring": url_for("api_follow_recurring", demo_id="__EVENT_ID__"),
        "unfollowRecurring": url_for("api_unfollow_recurring", demo_id="__EVENT_ID__"),
        "organizationPrefix": url_for("org", org_id="__ORGANIZATION_ID__").replace("__ORGANIZATION_ID__", ""), "tagPrefix": "/tag/",
    }
    props = {"id": event_id, "endpoint": _api_endpoint(), "locale": locale,
             "canonicalUrl": canonical, "urls": urls,
             "messages": detail_messages(),
             "authenticated": bool(current_user.is_authenticated),
             "followedOrganizations": [], "followableOrganizations": [],
             "recurringTargetId": str(parent) if parent and ObjectId.is_valid(str(parent)) else None,
             "recurringFollowing": False}
    if current_user.is_authenticated:
        followed = [str(value) for value in (getattr(current_user, "followed_organizations", []) or []) if value]
        props["followedOrganizations"] = followed
        props["recurringFollowing"] = str(parent) in {str(value) for value in (getattr(current_user, "followed_recurring_demos", []) or [])}
        org_ids = [ObjectId(str(row["organization_id"])) for row in (metadata.get("organizers") if isinstance(metadata.get("organizers"), list) else [])
                   if isinstance(row, dict) and ObjectId.is_valid(str(row.get("organization_id", "")))]
        if org_ids:
            props["followableOrganizations"] = [str(row["_id"]) for row in db.organizations.find({"_id": {"$in": org_ids}, "verified": True}, {"_id": 1})]
    if recurring_context:
        occurrences = []
        seen = set()
        for row in recurring_context.get("occurrences", []) + recurring_context.get("past_occurrences", []):
            if row["id"] in seen:
                continue
            seen.add(row["id"])
            occurrences.append({"id": row["id"], "url": row["url"], "date": row.get("date"),
                "start_time": row.get("start_time"), "end_time": row.get("end_time"),
                "cancelled": row.get("cancelled", False), "selected": row.get("is_selected", False)})
        if event_id not in seen:
            occurrences.append({"id": event_id, "url": request.full_path.rstrip("?"),
                "date": metadata.get("date"), "start_time": metadata.get("start_time"),
                "end_time": metadata.get("end_time"), "cancelled": bool(metadata.get("cancelled")), "selected": True})
        props["series"] = {"title": _("Kaikki tapahtuman ajankohdat"), "occurrences": occurrences}
    noindex = (not recurring_context["series_indexable"] if recurring_context and "series_indexable" in recurring_context
               else demo_is_beyond_future_horizon(metadata.get("date"), reference_date=date.today()))
    permissions = {}
    if current_user.is_authenticated:
        from mielenosoitukset_fi.utils.wrappers import has_demo_permission
        permissions = {permission: has_demo_permission(current_user, metadata["_id"], permission)
                       for permission in ("VIEW_DEMO", "EDIT_DEMO", "DELETE_DEMO", "VIEW_ANALYTICS")}
    response = make_response(render_template("detail_react.html", props=props, metadata=metadata,
        toolbox_demo_permissions=permissions,
        metadata_title=title, metadata_description=description or _("Mielenosoituksen tiedot."),
        detail_canonical_url=canonical, seo_noindex=noindex))
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Detail-Renderer"] = "react"
    if noindex:
        response.headers["X-Robots-Tag"] = "noindex, follow"
    return response
