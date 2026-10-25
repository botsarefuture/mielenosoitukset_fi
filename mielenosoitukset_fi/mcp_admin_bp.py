from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import io
import json
import logging
import secrets
import warnings
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

from bson import ObjectId
from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user
import jwt
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename

from mielenosoitukset_fi.utils.admin.organizers import collect_admin_organizers
from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.api.exceptions import ApiException
from mielenosoitukset_fi.utils.classes.Case import Case
from mielenosoitukset_fi.utils.classes.Demonstration import Demonstration
from mielenosoitukset_fi.utils.classes.Organization import Organization
from mielenosoitukset_fi.utils.database import stringify_object_ids
from mielenosoitukset_fi.utils.tokens import check_token
from mielenosoitukset_fi.utils.s3 import upload_image_fileobj


mcp_admin_bp = Blueprint("admin_mcp", __name__)
logger = logging.getLogger(__name__)
MCP_CONSENT_CSRF_SESSION_KEY = "admin_mcp_consent_csrf"


def _consent_csrf_token() -> str:
    token = session.get(MCP_CONSENT_CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[MCP_CONSENT_CSRF_SESSION_KEY] = token
    return token


def _mongo():
    return DatabaseManager().get_instance().get_db()


def _normalize_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        return [str(part).strip() for part in value if str(part).strip()]
    return []


def _normalize_organizers(value: Any, existing_organizers=None) -> list[dict[str, Any]]:
    """Use the dashboard's organizer parser, including profile hydration.

    Strings are accepted for compatibility: ObjectIds link profiles and other
    strings are freeform names. Never persist bare ids as organizer rows.
    """
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("organizers must be an array of organizer objects or strings")

    form = {}
    for index, organizer in enumerate(value):
        if isinstance(organizer, str):
            organizer = organizer.strip()
            organizer = (
                {"organization_id": organizer}
                if ObjectId.is_valid(organizer)
                else {"name": organizer}
            )
        if not isinstance(organizer, dict):
            raise ValueError("Each organizer must be an object or string")
        organization_id = organizer.get("organization_id")
        if organization_id:
            if not ObjectId.is_valid(str(organization_id)):
                raise ValueError("Invalid organizer organization_id")
            if not _mongo().organizations.find_one({"_id": ObjectId(str(organization_id))}):
                raise ValueError(f"Organizer organization not found: {organization_id}")
        elif not str(organizer.get("name") or "").strip():
            raise ValueError("Freeform organizers require a name; email and website are optional")

        for field, form_field in (
            ("name", "name"), ("email", "email"), ("website", "website"),
            ("organization_id", "id"), ("_id", "record_id"),
        ):
            field_value = organizer.get(field)
            if field_value is not None:
                if not isinstance(field_value, (str, ObjectId)):
                    raise ValueError(f"Organizer {field} must be a string")
                form[f"organizer_{form_field}_{index}"] = str(field_value)
        for field, form_field, default in (
            ("is_private", "is_private", False),
            ("show_name_public", "show_name", True),
            ("show_email_public", "show_email", True),
        ):
            flag = organizer.get(field, default)
            if not isinstance(flag, bool):
                raise ValueError(f"Organizer {field} must be a boolean")
            form[f"organizer_{form_field}_{index}"] = "on" if flag else "off"

    return collect_admin_organizers(form, existing_organizers=existing_organizers)


def _normalize_gallery_images(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.splitlines() if v.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(v).strip() for v in value if str(v).strip()]
    v = str(value).strip()
    return [v] if v else []


def _jsonrpc_response(result: Any, request_id: Any, http_status: int = 200):
    return (
        jsonify({"jsonrpc": "2.0", "id": request_id, "result": result}),
        http_status,
    )


def _jsonrpc_error(request_id: Any, code: int, message: str, data: Any = None, http_status: int = 200):
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }
    if data is not None:
        payload["error"]["data"] = data
    return jsonify(payload), http_status


def _get_mcp_config() -> dict[str, Any]:
    config = current_app.config.get("ADMIN_MCP") or {}
    return config if isinstance(config, dict) else {}


def _token_entries() -> list[dict[str, Any]]:
    raw_entries = _get_mcp_config().get("TOKENS") or []
    normalized: list[dict[str, Any]] = []
    for entry in raw_entries:
        if isinstance(entry, str):
            normalized.append({"name": "token", "token": entry, "scopes": ["read", "write"]})
        elif isinstance(entry, dict):
            normalized.append(
                {
                    "name": entry.get("name", "token"),
                    "token": entry.get("token"),
                    "sha256": entry.get("sha256"),
                    "scopes": entry.get("scopes") or ["read", "write"],
                }
            )
    return normalized


def _oauth_config() -> dict[str, Any]:
    oauth = _get_mcp_config().get("OAUTH") or {}
    return oauth if isinstance(oauth, dict) else {}


def _oauth_enabled() -> bool:
    if not _get_mcp_config().get("ENABLED", False):
        return False
    oauth = _oauth_config()
    return oauth.get("ENABLED", True) is not False


def _oauth_signing_secret() -> str:
    oauth = _oauth_config()
    return str(oauth.get("JWT_SHARED_SECRET") or current_app.config.get("SECRET_KEY") or "")


def _oauth_audience() -> str:
    oauth = _oauth_config()
    return str(oauth.get("AUDIENCE") or _mcp_endpoint_url())


def _oauth_required_scopes() -> list[str]:
    oauth = _oauth_config()
    required = oauth.get("REQUIRED_SCOPES")
    if isinstance(required, list) and required:
        return [str(scope) for scope in required if str(scope)]
    return ["mcp.admin"]


def _oauth_supported_scopes() -> list[str]:
    oauth = _oauth_config()
    configured = oauth.get("SUPPORTED_SCOPES")
    if isinstance(configured, list) and configured:
        return [str(scope) for scope in configured if str(scope)]
    return ["mcp.admin", "read", "write", "admin"]


def _oauth_default_scopes() -> list[str]:
    oauth = _oauth_config()
    configured = oauth.get("DEFAULT_SCOPES")
    if isinstance(configured, list) and configured:
        return [str(scope) for scope in configured if str(scope)]
    default_scopes = _oauth_supported_scopes()
    if "mcp.admin" not in default_scopes:
        default_scopes.insert(0, "mcp.admin")
    return default_scopes


def _oauth_issuer() -> str:
    oauth = _oauth_config()
    return str(oauth.get("ISSUER") or request.url_root.rstrip("/"))


def _mcp_endpoint_url() -> str:
    return request.url_root.rstrip("/") + url_for("admin_mcp.handle_admin_mcp")


def _oauth_authorization_endpoint_url() -> str:
    return request.url_root.rstrip("/") + url_for("admin_mcp.oauth_authorize")


def _oauth_token_endpoint_url() -> str:
    return request.url_root.rstrip("/") + url_for("admin_mcp.oauth_token")


def _oauth_registration_endpoint_url() -> str:
    return request.url_root.rstrip("/") + url_for("admin_mcp.oauth_register")


def _oauth_resource_metadata_url() -> str:
    return request.url_root.rstrip("/") + url_for("admin_mcp.oauth_protected_resource_metadata")


def _oauth_authorization_server_metadata() -> dict[str, Any]:
    return {
        "issuer": _oauth_issuer(),
        "authorization_endpoint": _oauth_authorization_endpoint_url(),
        "token_endpoint": _oauth_token_endpoint_url(),
        "registration_endpoint": _oauth_registration_endpoint_url(),
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256", "plain"],
        "token_endpoint_auth_methods_supported": ["none", "client_secret_post", "client_secret_basic"],
        "scopes_supported": _oauth_supported_scopes(),
    }


def _oauth_protected_resource_metadata_payload() -> dict[str, Any]:
    return {
        "resource": _mcp_endpoint_url(),
        "authorization_servers": [_oauth_issuer()],
        "scopes_supported": _oauth_supported_scopes(),
        "bearer_methods_supported": ["header"],
    }


def _client_collection():
    return _mongo().oauth_clients


def _authorization_code_collection():
    return _mongo().oauth_authorization_codes


def _normalize_scope_list(raw_scope: str | None, *, default_to_all: bool = False) -> list[str]:
    if raw_scope:
        requested = [part for part in str(raw_scope).split() if part]
    elif default_to_all:
        requested = list(_oauth_default_scopes())
    else:
        requested = []

    supported = _oauth_supported_scopes()
    normalized: list[str] = []
    for scope in requested:
        if scope in supported and scope not in normalized:
            normalized.append(scope)
    return normalized


def _serialize_scope_list(scopes: list[str]) -> str:
    return " ".join(scope for scope in scopes if scope)


def _code_challenge_s256(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _hash_client_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _is_mcp_admin_user(user: Any) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return bool(user.has_full_permissions())


def _lookup_client(client_id: str) -> dict[str, Any] | None:
    if not client_id:
        return None
    return _client_collection().find_one({"client_id": client_id})


def _register_client_document(payload: dict[str, Any]) -> dict[str, Any]:
    redirect_uris = payload.get("redirect_uris") or []
    if not isinstance(redirect_uris, list) or not redirect_uris:
        raise ValueError("redirect_uris is required")

    token_auth_method = str(payload.get("token_endpoint_auth_method") or "none")
    if token_auth_method not in {"none", "client_secret_post", "client_secret_basic"}:
        raise ValueError("Unsupported token_endpoint_auth_method")

    client_id = f"mcp_{secrets.token_urlsafe(18)}"
    client_secret = secrets.token_urlsafe(32) if token_auth_method != "none" else None
    doc = {
        "client_id": client_id,
        "client_name": payload.get("client_name") or "ChatGPT MCP Client",
        "redirect_uris": [str(uri) for uri in redirect_uris if str(uri)],
        "grant_types": payload.get("grant_types") or ["authorization_code"],
        "response_types": payload.get("response_types") or ["code"],
        "scope": _serialize_scope_list(_normalize_scope_list(payload.get("scope"), default_to_all=True)),
        "token_endpoint_auth_method": token_auth_method,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    if client_secret:
        doc["client_secret_hash"] = _hash_client_secret(client_secret)
    _client_collection().insert_one(doc)
    response_doc = {
        "client_id": client_id,
        "client_name": doc["client_name"],
        "redirect_uris": doc["redirect_uris"],
        "grant_types": doc["grant_types"],
        "response_types": doc["response_types"],
        "scope": doc["scope"],
        "token_endpoint_auth_method": token_auth_method,
        "client_id_issued_at": int(doc["created_at"].timestamp()),
    }
    if client_secret:
        response_doc["client_secret"] = client_secret
        response_doc["client_secret_expires_at"] = 0
    return response_doc


def _resolve_client_auth() -> tuple[dict[str, Any] | None, str | None, str | None]:
    basic_auth = request.authorization
    if basic_auth and basic_auth.username:
        return _lookup_client(basic_auth.username), basic_auth.username, basic_auth.password

    json_payload = request.get_json(silent=True) if request.is_json else {}
    client_id = (request.form.get("client_id") or (json_payload or {}).get("client_id"))
    client_secret = (request.form.get("client_secret") or (json_payload or {}).get("client_secret"))
    if client_id:
        return _lookup_client(client_id), client_id, client_secret
    return None, None, None


def _validate_client_auth(client: dict[str, Any] | None, client_id: str | None, client_secret: str | None) -> dict[str, Any]:
    if not client or not client_id:
        raise LookupError("Unknown OAuth client")

    auth_method = client.get("token_endpoint_auth_method") or "none"
    if auth_method == "none":
        return client

    expected_hash = client.get("client_secret_hash")
    supplied_hash = _hash_client_secret(client_secret or "")
    if not expected_hash or not hmac.compare_digest(expected_hash, supplied_hash):
        raise PermissionError("Invalid OAuth client secret")
    return client


def _store_authorization_code(
    *,
    client_id: str,
    user_id: Any,
    redirect_uri: str,
    scope: str,
    code_challenge: str | None,
    code_challenge_method: str | None,
) -> str:
    code = secrets.token_urlsafe(32)
    _authorization_code_collection().insert_one(
        {
            "code": code,
            "client_id": client_id,
            "user_id": user_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method or "plain",
            "created_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
            "used_at": None,
        }
    )
    return code


def _issue_oauth_access_token(*, client_id: str, user_id: Any, scope: str) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "iss": _oauth_issuer(),
        "sub": str(user_id),
        "aud": _oauth_audience(),
        "scope": scope,
        "client_id": client_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    return jwt.encode(claims, _oauth_signing_secret(), algorithm="HS256")

def _scopes_from_claims(claims: dict[str, Any]) -> list[str]:
    scopes: list[str] = []
    scope_claim = claims.get("scope")
    if isinstance(scope_claim, str):
        scopes.extend(part for part in scope_claim.split() if part)
    scp_claim = claims.get("scp")
    if isinstance(scp_claim, list):
        scopes.extend(str(part) for part in scp_claim if str(part))
    unique_scopes: list[str] = []
    for scope in scopes:
        if scope not in unique_scopes:
            unique_scopes.append(scope)
    return unique_scopes


def _authenticate_oauth_bearer(supplied_token: str) -> dict[str, Any] | None:
    oauth = _oauth_config()
    if not _oauth_enabled():
        logger.debug("OAuth not enabled")
        return None

    algorithms = oauth.get("JWT_ALGORITHMS") or ["HS256"]
    issuer = oauth.get("ISSUER")
    audience = oauth.get("AUDIENCE") or _oauth_audience()
    shared_secret = _oauth_signing_secret()
    public_key = oauth.get("JWT_PUBLIC_KEY")
    required_scopes = _oauth_required_scopes()

    verification_key = public_key or shared_secret
    if not verification_key:
        logger.warning("OAuth verification key not configured")
        return None

    decode_kwargs: dict[str, Any] = {"algorithms": algorithms}
    if audience:
        decode_kwargs["audience"] = audience
    if issuer:
        decode_kwargs["issuer"] = issuer

    logger.debug(f"Decoding OAuth JWT with algorithms: {algorithms}, audience: {audience}")
    claims = jwt.decode(supplied_token, verification_key, **decode_kwargs)
    scopes = _scopes_from_claims(claims)
    logger.debug(f"OAuth JWT decoded successfully. Scopes: {scopes}, Required: {required_scopes}")
    if required_scopes and not all(scope in scopes for scope in required_scopes):
        logger.warning(f"OAuth token missing required scopes. Token has: {scopes}, Required: {required_scopes}")
        raise PermissionError("OAuth token missing required MCP scopes")

    return {
        "name": claims.get("sub") or claims.get("client_id") or "oauth-token",
        "scopes": scopes or ["read"],
        "claims": claims,
        "auth_type": "oauth_bearer",
    }


def _authenticate() -> dict[str, Any] | None:
    if not _get_mcp_config().get("ENABLED", False):
        logger.debug("MCP not enabled in config")
        return None

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        logger.debug("No Bearer token in Authorization header")
        return None

    supplied_token = auth_header.split(" ", 1)[1].strip()
    if not supplied_token:
        logger.debug("Empty Bearer token")
        return None

    logger.debug("Attempting MCP bearer authentication")

    try:
        token_record = check_token(supplied_token)
        logger.info(f"MCP authenticated via API token: {token_record.get('user_id') or token_record.get('app_id')}")
        return {
            "name": str(token_record.get("user_id") or token_record.get("app_id") or "api-token"),
            "scopes": token_record.get("scopes") or ["read"],
            "token_record": token_record,
            "auth_type": "api_token",
        }
    except ApiException as e:
        logger.debug(f"API token check failed: {e}")
        pass

    try:
        oauth_entry = _authenticate_oauth_bearer(supplied_token)
        if oauth_entry:
            logger.info(f"MCP authenticated via OAuth bearer: {oauth_entry.get('name')}")
            return oauth_entry
    except jwt.PyJWTError as e:
        logger.debug(f"OAuth bearer check failed: {e}")
        pass

    supplied_hash = hashlib.sha256(supplied_token.encode("utf-8")).hexdigest()
    for entry in _token_entries():
        entry_token = entry.get("token")
        entry_hash = entry.get("sha256")
        if entry_token and hmac.compare_digest(entry_token, supplied_token):
            logger.info(f"MCP authenticated via configured token: {entry.get('name')}")
            return entry
        if entry_hash and hmac.compare_digest(entry_hash, supplied_hash):
            logger.info(f"MCP authenticated via configured token hash: {entry.get('name')}")
            return entry
    logger.warning("MCP authentication failed - no matching token found")
    return None


def _require_scope(token_entry: dict[str, Any], scope: str) -> None:
    scopes = token_entry.get("scopes") or []
    if token_entry.get("auth_type") == "api_token" and "mcp.admin" not in scopes:
        raise PermissionError("API token missing required scope: mcp.admin")
    if "mcp.admin" in scopes:
        return
    if scope == "read" and ("read" in scopes or "write" in scopes or "admin" in scopes):
        return
    if scope == "write" and ("write" in scopes or "admin" in scopes):
        return
    if scope == "admin" and "admin" in scopes:
        return
    if scope not in scopes:
        raise PermissionError(f"Token missing required scope: {scope}")


def _serialize_result(data: Any) -> dict[str, Any]:
    structured = stringify_object_ids(data)
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(structured, ensure_ascii=False, default=str),
            }
        ],
        "structuredContent": structured,
    }


def _list_demos(arguments: dict[str, Any], token_entry: dict[str, Any]) -> dict[str, Any]:
    _require_scope(token_entry, "read")
    db = _mongo()
    search = (arguments.get("search") or "").strip()
    approved_only = bool(arguments.get("approved_only", False))
    include_hidden = bool(arguments.get("include_hidden", False))
    include_cancelled = bool(arguments.get("include_cancelled", False))
    include_past = bool(arguments.get("include_past", True))
    page = max(int(arguments.get("page", 1) or 1), 1)
    per_page = min(max(int(arguments.get("per_page", 20) or 20), 1), 100)

    clauses: list[dict[str, Any]] = [{"$or": [{"rejected": {"$exists": False}}, {"rejected": False}]}]
    if approved_only:
        clauses.append({"approved": True})
    if not include_hidden:
        clauses.append({"$or": [{"hide": {"$exists": False}}, {"hide": False}]})
    if not include_cancelled:
        clauses.append({"cancelled": {"$ne": True}})
    if not include_past:
        clauses.append({"$or": [{"in_past": {"$exists": False}}, {"in_past": False}]})
    if search:
        clauses.append(
            {
                "$or": [
                    {"title": {"$regex": search, "$options": "i"}},
                    {"city": {"$regex": search, "$options": "i"}},
                    {"address": {"$regex": search, "$options": "i"}},
                    {"description": {"$regex": search, "$options": "i"}},
                ]
            }
        )
    query = {"$and": clauses} if len(clauses) > 1 else clauses[0]

    total = db.demonstrations.count_documents(query)
    cursor = (
        db.demonstrations.find(query)
        .sort([("date", 1), ("_id", 1)])
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    items = [
        {
            "_id": doc["_id"],
            "title": doc.get("title"),
            "date": doc.get("date"),
            "city": doc.get("city"),
            "approved": doc.get("approved", False),
            "hide": doc.get("hide", False),
            "cancelled": doc.get("cancelled", False),
            "running_number": doc.get("running_number"),
            "slug": doc.get("slug"),
        }
        for doc in cursor
    ]
    return _serialize_result({"items": items, "total": total, "page": page, "per_page": per_page})


def _get_demo(arguments: dict[str, Any], token_entry: dict[str, Any]) -> dict[str, Any]:
    _require_scope(token_entry, "read")
    demo_id = arguments.get("demo_id")
    if not demo_id:
        raise ValueError("demo_id is required")
    doc = _mongo().demonstrations.find_one(
        {"_id": ObjectId(demo_id)}, {"_pending_rollback_history": 0},
    )
    if not doc:
        raise LookupError("Demonstration not found")
    return _serialize_result(doc)


def _create_demo(arguments: dict[str, Any], token_entry: dict[str, Any]) -> dict[str, Any]:
    _require_scope(token_entry, "write")
    required = ["title", "date", "start_time", "city", "address"]
    missing = [field for field in required if not arguments.get(field)]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    demo = Demonstration(
        title=arguments["title"],
        date=arguments["date"],
        start_time=arguments["start_time"],
        end_time=arguments.get("end_time"),
        city=arguments["city"],
        address=arguments["address"],
        description=arguments.get("description"),
        facebook=arguments.get("facebook"),
        route=arguments.get("route"),
        event_type=arguments.get("event_type") or arguments.get("type") or "OTHER",
        tags=_normalize_tags(arguments.get("tags")),
        organizers=_normalize_organizers(arguments.get("organizers")),
        # Content-write scope does not grant moderation authority.
        approved=False,
        hide=bool(arguments.get("hide", False)),
        cover_picture=arguments.get("cover_picture"),
        img=arguments.get("img"),
        preview_image=arguments.get("preview_image"),
        gallery_images=_normalize_gallery_images(arguments.get("gallery_images")),
        _dont_override=True,
        created_datetime=datetime.now(timezone.utc),
        last_modified=datetime.now(timezone.utc),
    )
    demo.save()
    return _serialize_result({"created": True, "demo_id": demo._id, "slug": demo.slug})


def _update_demo(arguments: dict[str, Any], token_entry: dict[str, Any]) -> dict[str, Any]:
    _require_scope(token_entry, "write")
    demo_id = arguments.get("demo_id")
    patch = arguments.get("patch") or {}
    if not demo_id:
        raise ValueError("demo_id is required")
    if not isinstance(patch, dict) or not patch:
        raise ValueError("patch must be a non-empty object")
    if "approved" in patch:
        # A generic write token is not a moderation decision. In particular,
        # False must not silently invent a pending/rejected transition.
        raise ValueError("Use the moderation workflow to change approval")

    db = _mongo()
    doc = db.demonstrations.find_one({"_id": ObjectId(demo_id)})
    if not doc:
        raise LookupError("Demonstration not found")

    allowed_fields = {
        "title",
        "date",
        "start_time",
        "end_time",
        "city",
        "address",
        "description",
        "facebook",
        "route",
        "tags",
        "organizers",
        "hide",
        "cancelled",
        "event_type",
        "cover_picture",
        "img",
        "gallery_images",
        "preview_image",
    }
    applied: dict[str, Any] = {}
    for key, value in patch.items():
        if key not in allowed_fields:
            continue
        if key == "tags":
            value = _normalize_tags(value)
        elif key == "organizers":
            value = _normalize_organizers(value, existing_organizers=doc.get("organizers"))
        elif key == "gallery_images":
            value = _normalize_gallery_images(value)
        applied[key] = value

    if not applied:
        raise ValueError("No supported fields in patch")

    if applied.get("cover_picture"):
        # A supplied cover replaces any generated cover, including its source
        # marker; automatic covers are suppressed by the public gallery.
        applied["cover_source"] = "user"

    # Reconstruct after merging so dates, times and organizers use the same
    # model normalization as create and the dashboard, rather than raw setattr.
    demo = Demonstration.from_dict({**doc, **applied}, save_on_normalize=False)
    demo.last_modified = datetime.now(timezone.utc)
    demo.save()
    stored = demo.to_dict()
    return _serialize_result({
        "updated": True, "demo_id": demo._id,
        "applied": {key: stored[key] for key in applied},
    })


def _upload_image(arguments: dict[str, Any], token_entry: dict[str, Any]) -> dict[str, Any]:
    """Upload client-supplied bytes using the same S3 pipeline as the forms.

    Remote MCP clients cannot pass local server paths. Base64 allows an attached
    image to be uploaded without first hosting it on another public service.
    """
    _require_scope(token_entry, "write")
    filename = secure_filename(arguments.get("filename") or "")
    encoded = arguments.get("data_base64")
    if not filename or not isinstance(encoded, str) or not encoded:
        raise ValueError("filename and data_base64 are required")
    if encoded.startswith("data:"):
        header, separator, encoded = encoded.partition(",")
        if not separator or not header.startswith("data:image/") or not header.endswith(";base64"):
            raise ValueError("Expected an image base64 data URL")
    # Bound memory use before decoding. HTTP/proxy request limits still apply.
    max_bytes = int(_get_mcp_config().get("MAX_IMAGE_BYTES", 16 * 1024 * 1024))
    if len(encoded) > 4 * ((max_bytes + 2) // 3):
        raise ValueError(f"Image exceeds the {max_bytes}-byte upload limit")
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("data_base64 must contain valid base64 image bytes") from exc
    if not image_bytes or len(image_bytes) > max_bytes:
        raise ValueError(f"Image must contain between 1 and {max_bytes} bytes")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(image_bytes)) as image:
                image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError,
            Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("The uploaded file is not a supported, valid image") from exc

    demo_id = arguments.get("demo_id")
    organization_id = arguments.get("organization_id")
    if demo_id and organization_id:
        raise ValueError("Specify either demo_id or organization_id, not both")
    field = arguments.get("field")
    collection = None
    target_id = None
    image_type = "demo_pics"
    if demo_id:
        field = field or "cover_picture"
        if field not in {"cover_picture", "img", "preview_image", "gallery_images"}:
            raise ValueError("Unsupported demonstration image field")
        if not ObjectId.is_valid(demo_id):
            raise ValueError("Invalid demo_id")
        collection = _mongo().demonstrations
        target_id = ObjectId(demo_id)
    elif organization_id:
        field = field or "logo"
        if field != "logo":
            raise ValueError("Organization images must use the logo field")
        if not ObjectId.is_valid(organization_id):
            raise ValueError("Invalid organization_id")
        image_type = "organization_logos"
        collection = _mongo().organizations
        target_id = ObjectId(organization_id)
    elif field:
        raise ValueError("field requires demo_id or organization_id")
    if collection is not None and not collection.find_one({"_id": target_id}):
        raise LookupError("Image target not found")

    url = upload_image_fileobj(
        current_app.config.get("S3_BUCKET"), io.BytesIO(image_bytes), filename, image_type,
    )
    if not url:
        raise RuntimeError("Image storage upload failed; no image fields were changed")

    result = {"uploaded": True, "url": url}
    if collection is not None:
        update = {"$set": {field: url}}
        if demo_id:
            update["$set"]["last_modified"] = datetime.now(timezone.utc)
            if field == "cover_picture":
                update["$set"]["cover_source"] = "user"
            if field == "gallery_images":
                update["$set"].pop(field)
                update["$addToSet"] = {field: url}
        saved = collection.update_one({"_id": target_id}, update)
        if not saved.matched_count:
            raise LookupError("Image target no longer exists; uploaded URL: " + url)
        result.update({"demo_id" if demo_id else "organization_id": str(target_id), "field": field})
    return _serialize_result(result)


def _list_organizations(arguments: dict[str, Any], token_entry: dict[str, Any]) -> dict[str, Any]:
    _require_scope(token_entry, "read")
    db = _mongo()
    search = (arguments.get("search") or "").strip()
    page = max(int(arguments.get("page", 1) or 1), 1)
    per_page = min(max(int(arguments.get("per_page", 20) or 20), 1), 100)
    query: dict[str, Any] = {}
    if search:
        query = {
            "$or": [
                {"name": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}},
            ]
        }
    total = db.organizations.count_documents(query)
    cursor = (
        db.organizations.find(query)
        .sort("name", 1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    items = [
        {
            "_id": doc["_id"],
            "name": doc.get("name"),
            "email": doc.get("email"),
            "website": doc.get("website"),
            "verified": doc.get("verified", False),
        }
        for doc in cursor
    ]
    return _serialize_result({"items": items, "total": total, "page": page, "per_page": per_page})


def _get_organization(arguments: dict[str, Any], token_entry: dict[str, Any]) -> dict[str, Any]:
    _require_scope(token_entry, "read")
    org_id = arguments.get("organization_id")
    if not org_id:
        raise ValueError("organization_id is required")
    doc = _mongo().organizations.find_one({"_id": ObjectId(org_id)})
    if not doc:
        raise LookupError("Organization not found")
    return _serialize_result(doc)


def _create_organization(arguments: dict[str, Any], token_entry: dict[str, Any]) -> dict[str, Any]:
    _require_scope(token_entry, "write")
    required = ["name", "email"]
    missing = [field for field in required if not arguments.get(field)]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    organization = Organization(
        name=arguments["name"],
        description=arguments.get("description", ""),
        email=arguments["email"],
        website=arguments.get("website", ""),
        logo=arguments.get("logo"),
        social_media_links=arguments.get("social_media_links") or {},
        verified=bool(arguments.get("verified", False)),
        invitations=arguments.get("invitations") or [],
    )
    organization.save()
    return _serialize_result({"created": True, "organization_id": organization._id})


def _update_organization(arguments: dict[str, Any], token_entry: dict[str, Any]) -> dict[str, Any]:
    _require_scope(token_entry, "write")
    org_id = arguments.get("organization_id")
    patch = arguments.get("patch") or {}
    if not org_id:
        raise ValueError("organization_id is required")
    if not isinstance(patch, dict) or not patch:
        raise ValueError("patch must be a non-empty object")
    allowed_fields = {
        "name",
        "description",
        "email",
        "website",
        "logo",
        "social_media_links",
        "verified",
        "fill_url",
        "invitations",
    }
    update_payload = {key: value for key, value in patch.items() if key in allowed_fields}
    if not update_payload:
        raise ValueError("No supported fields in patch")

    result = _mongo().organizations.update_one(
        {"_id": ObjectId(org_id)},
        {"$set": update_payload},
    )
    if result.matched_count == 0:
        raise LookupError("Organization not found")
    return _serialize_result({"updated": True, "organization_id": org_id, "applied": update_payload})


def _list_cases(arguments: dict[str, Any], token_entry: dict[str, Any]) -> dict[str, Any]:
    _require_scope(token_entry, "read")
    db = _mongo()
    case_type = (arguments.get("case_type") or "").strip()
    closed = arguments.get("closed")
    page = max(int(arguments.get("page", 1) or 1), 1)
    per_page = min(max(int(arguments.get("per_page", 20) or 20), 1), 100)
    query: dict[str, Any] = {}
    if case_type:
        query["type"] = case_type
    if closed is True:
        query["meta.closed"] = True
    elif closed is False:
        query["$or"] = [{"meta.closed": {"$exists": False}}, {"meta.closed": False}]

    total = db.cases.count_documents(query)
    cursor = (
        db.cases.find(query)
        .sort([("created_at", -1), ("_id", -1)])
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    items = []
    for doc in cursor:
        items.append(
            {
                "_id": doc["_id"],
                "running_num": doc.get("running_num"),
                "type": doc.get("type"),
                "demo_id": doc.get("demo_id"),
                "organization_id": doc.get("organization_id"),
                "closed": bool((doc.get("meta") or {}).get("closed")),
                "updated_at": doc.get("updated_at"),
            }
        )
    return _serialize_result({"items": items, "total": total, "page": page, "per_page": per_page})


def _get_case(arguments: dict[str, Any], token_entry: dict[str, Any]) -> dict[str, Any]:
    _require_scope(token_entry, "read")
    case_id = arguments.get("case_id")
    if not case_id:
        raise ValueError("case_id is required")
    doc = _mongo().cases.find_one({"_id": ObjectId(case_id)})
    if not doc:
        raise LookupError("Case not found")
    return _serialize_result(doc)


def _add_case_note(arguments: dict[str, Any], token_entry: dict[str, Any]) -> dict[str, Any]:
    _require_scope(token_entry, "write")
    case_id = arguments.get("case_id")
    note = (arguments.get("note") or "").strip()
    actor = (arguments.get("actor") or token_entry.get("name") or "mcp").strip()
    action_type = (arguments.get("action_type") or "internal_note").strip()
    if not case_id or not note:
        raise ValueError("case_id and note are required")
    case = Case.get(case_id)
    if not case:
        raise LookupError("Case not found")
    case.add_action(action_type=action_type, admin_user=actor, note=note)
    return _serialize_result({"updated": True, "case_id": case_id, "action_type": action_type})


def _close_case(arguments: dict[str, Any], token_entry: dict[str, Any]) -> dict[str, Any]:
    _require_scope(token_entry, "write")
    case_id = arguments.get("case_id")
    reason = (arguments.get("reason") or "Closed via MCP").strip()
    actor = (arguments.get("actor") or token_entry.get("name") or "mcp").strip()
    if not case_id:
        raise ValueError("case_id is required")
    db = _mongo()
    doc = db.cases.find_one({"_id": ObjectId(case_id)})
    if not doc:
        raise LookupError("Case not found")
    action_entry = {
        "timestamp": datetime.now(timezone.utc),
        "admin": actor,
        "action_type": "close_case",
        "note": reason,
    }
    history_entry = {
        "timestamp": datetime.now(timezone.utc),
        "action": "Case closed",
        "user": actor,
        "metadata": {"reason": reason, "source": "mcp"},
    }
    db.cases.update_one(
        {"_id": ObjectId(case_id)},
        {
            "$set": {
                "meta.closed": True,
                "meta.closed_reason": reason,
                "updated_at": datetime.now(timezone.utc),
            },
            "$push": {"action_logs": action_entry, "case_history": history_entry},
        },
    )
    return _serialize_result({"updated": True, "case_id": case_id, "closed": True})


def _reopen_case(arguments: dict[str, Any], token_entry: dict[str, Any]) -> dict[str, Any]:
    _require_scope(token_entry, "write")
    case_id = arguments.get("case_id")
    reason = (arguments.get("reason") or "Reopened via MCP").strip()
    actor = (arguments.get("actor") or token_entry.get("name") or "mcp").strip()
    if not case_id:
        raise ValueError("case_id is required")
    db = _mongo()
    doc = db.cases.find_one({"_id": ObjectId(case_id)})
    if not doc:
        raise LookupError("Case not found")
    action_entry = {
        "timestamp": datetime.now(timezone.utc),
        "admin": actor,
        "action_type": "reopen_case",
        "note": reason,
    }
    history_entry = {
        "timestamp": datetime.now(timezone.utc),
        "action": "Case reopened",
        "user": actor,
        "metadata": {"reason": reason, "source": "mcp"},
    }
    db.cases.update_one(
        {"_id": ObjectId(case_id)},
        {
            "$set": {
                "meta.closed": False,
                "updated_at": datetime.now(timezone.utc),
            },
            "$unset": {"meta.closed_reason": ""},
            "$push": {"action_logs": action_entry, "case_history": history_entry},
        },
    )
    return _serialize_result({"updated": True, "case_id": case_id, "closed": False})


def _oauth_error_redirect(redirect_uri: str, *, error: str, state: str | None = None, description: str | None = None):
    params = {"error": error}
    if state:
        params["state"] = state
    if description:
        params["error_description"] = description
    separator = "&" if "?" in redirect_uri else "?"
    return redirect(f"{redirect_uri}{separator}{urlencode(params)}")


def _oauth_json_error(error: str, description: str, status: int = 400):
    return jsonify({"error": error, "error_description": description}), status


def _unauthorized_mcp_response(request_id: Any):
    response, status = _jsonrpc_error(request_id, -32001, "Unauthorized MCP token", http_status=401)
    response.headers["WWW-Authenticate"] = (
        f'Bearer realm="mielenosoitukset-admin-mcp", '
        f'resource_metadata="{_oauth_resource_metadata_url()}"'
    )
    return response, status


ORGANIZERS_SCHEMA = {
    "type": "array",
    "description": (
        "Event organizers, as in the admin form. Link an existing profile with "
        "organization_id, or provide a freeform name with optional email/website. "
        "You do not need to create an organization profile for a freeform organizer. "
        "An empty array removes all organizers. Existing organization IDs and "
        "freeform names are also accepted as strings."
    ),
    "items": {
        "anyOf": [
            {
                "type": "object",
                "anyOf": [{"required": ["name"]}, {"required": ["organization_id"]}],
                "properties": {
                    "organization_id": {"type": "string", "description": "Existing profile ID; contact details come from the profile."},
                    "name": {"type": "string", "description": "Required for freeform organizers."},
                    "email": {"type": "string", "description": "Optional for freeform organizers."},
                    "website": {"type": "string"},
                    "_id": {"type": "string", "description": "Preserve the existing organizer record ID when editing."},
                    "is_private": {"type": "boolean", "default": False},
                    "show_name_public": {"type": "boolean", "default": True},
                    "show_email_public": {"type": "boolean", "default": True},
                },
            },
            {"type": "string", "minLength": 1},
        ],
    },
}

IMAGE_FIELDS_SCHEMA = {
    "cover_picture": {"type": ["string", "null"], "description": "Cover image URL. Use upload_image for a local attachment."},
    "img": {"type": ["string", "null"], "description": "Main image URL."},
    "preview_image": {"type": ["string", "null"], "description": "Listing preview image URL."},
    "gallery_images": {"type": "array", "items": {"type": "string"}},
}


TOOLS: dict[str, dict[str, Any]] = {
    "list_demos": {
        "description": "List and search demonstrations from the admin dashboard dataset.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "search": {"type": "string"},
                "approved_only": {"type": "boolean"},
                "include_hidden": {"type": "boolean"},
                "include_cancelled": {"type": "boolean"},
                "include_past": {"type": "boolean"},
                "page": {"type": "integer", "minimum": 1},
                "per_page": {"type": "integer", "minimum": 1, "maximum": 100},
            },
        },
        "handler": _list_demos,
    },
    "get_demo": {
        "description": "Fetch a single demonstration by id.",
        "inputSchema": {
            "type": "object",
            "required": ["demo_id"],
            "properties": {"demo_id": {"type": "string"}},
        },
        "handler": _get_demo,
    },
    "create_demo": {
        "description": "Create a demonstration with the same organizer and image fields as the admin form. End time is optional.",
        "inputSchema": {
            "type": "object",
            "required": ["title", "date", "start_time", "city", "address"],
            "properties": {
                "title": {"type": "string"},
                "date": {"type": "string"},
                "start_time": {"type": "string"},
                "end_time": {"type": ["string", "null"], "description": "Optional; omit if unknown."},
                "city": {"type": "string"},
                "address": {"type": "string"},
                "description": {"type": "string"},
                "facebook": {"type": "string"},
                "route": {"anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "string"}]},
                "event_type": {"type": "string", "description": "MARCH, STAY_STILL, ROAD_BLOCK, or OTHER (default)."},
                "tags": {"anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "string"}]},
                "organizers": ORGANIZERS_SCHEMA,
                "hide": {"type": "boolean"},
                **IMAGE_FIELDS_SCHEMA,
            },
        },
        "handler": _create_demo,
    },
    "update_demo": {
        "description": "Update a demonstration by applying a patch to supported admin fields.",
        "inputSchema": {
            "type": "object",
            "required": ["demo_id", "patch"],
            "properties": {
                "demo_id": {"type": "string"},
                "patch": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "date": {"type": "string"},
                        "start_time": {"type": "string"},
                        "end_time": {"type": ["string", "null"]},
                        "city": {"type": "string"},
                        "address": {"type": "string"},
                        "description": {"type": "string"},
                        "facebook": {"type": "string"},
                        "route": {"type": "array", "items": {"type": "string"}},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "organizers": ORGANIZERS_SCHEMA,
                        "hide": {"type": "boolean"},
                        "cancelled": {"type": "boolean"},
                        "event_type": {"type": "string"},
                        **IMAGE_FIELDS_SCHEMA,
                    },
                },
            },
        },
        "handler": _update_demo,
    },
    "upload_image": {
        "description": (
            "Upload an attached image as base64 bytes (or an image data URL) through "
            "the site's normal image storage pipeline. Returns a public URL. Optionally "
            "set demo_id to attach it to an event (cover_picture by default; gallery_images "
            "appends), or organization_id to set its logo. No public source URL is needed."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["filename", "data_base64"],
            "properties": {
                "filename": {"type": "string", "description": "Original filename. Image contents are validated and converted as in the admin uploader."},
                "data_base64": {"type": "string", "description": "Base64-encoded image bytes or data:image/...;base64,...; never a local filesystem path."},
                "demo_id": {"type": "string"},
                "organization_id": {"type": "string"},
                "field": {"type": "string", "enum": ["cover_picture", "img", "preview_image", "gallery_images", "logo"]},
            },
        },
        "handler": _upload_image,
    },
    "list_organizations": {
        "description": "List and search organizations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "search": {"type": "string"},
                "page": {"type": "integer", "minimum": 1},
                "per_page": {"type": "integer", "minimum": 1, "maximum": 100},
            },
        },
        "handler": _list_organizations,
    },
    "get_organization": {
        "description": "Fetch a single organization by id.",
        "inputSchema": {
            "type": "object",
            "required": ["organization_id"],
            "properties": {"organization_id": {"type": "string"}},
        },
        "handler": _get_organization,
    },
    "create_organization": {
        "description": "Create a new organization.",
        "inputSchema": {
            "type": "object",
            "required": ["name", "email"],
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "description": {"type": "string", "description": "Optional organization description."},
                "website": {"type": "string"},
                "logo": {"type": "string"},
                "social_media_links": {"type": "object"},
                "verified": {"type": "boolean"},
                "invitations": {"type": "array"},
            },
        },
        "handler": _create_organization,
    },
    "update_organization": {
        "description": "Update an organization with a supported field patch.",
        "inputSchema": {
            "type": "object",
            "required": ["organization_id", "patch"],
            "properties": {
                "organization_id": {"type": "string"},
                "patch": {"type": "object"},
            },
        },
        "handler": _update_organization,
    },
    "list_cases": {
        "description": "List support/admin cases with basic filtering.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "case_type": {"type": "string"},
                "closed": {"type": "boolean"},
                "page": {"type": "integer", "minimum": 1},
                "per_page": {"type": "integer", "minimum": 1, "maximum": 100},
            },
        },
        "handler": _list_cases,
    },
    "get_case": {
        "description": "Fetch a support/admin case by id.",
        "inputSchema": {
            "type": "object",
            "required": ["case_id"],
            "properties": {"case_id": {"type": "string"}},
        },
        "handler": _get_case,
    },
    "add_case_note": {
        "description": "Add an internal note/action log entry to a support case.",
        "inputSchema": {
            "type": "object",
            "required": ["case_id", "note"],
            "properties": {
                "case_id": {"type": "string"},
                "note": {"type": "string"},
                "action_type": {"type": "string"},
                "actor": {"type": "string"},
            },
        },
        "handler": _add_case_note,
    },
    "close_case": {
        "description": "Close a support case and append audit/history entries.",
        "inputSchema": {
            "type": "object",
            "required": ["case_id"],
            "properties": {
                "case_id": {"type": "string"},
                "reason": {"type": "string"},
                "actor": {"type": "string"},
            },
        },
        "handler": _close_case,
    },
    "reopen_case": {
        "description": "Reopen a support case and append audit/history entries.",
        "inputSchema": {
            "type": "object",
            "required": ["case_id"],
            "properties": {
                "case_id": {"type": "string"},
                "reason": {"type": "string"},
                "actor": {"type": "string"},
            },
        },
        "handler": _reopen_case,
    },
}


@mcp_admin_bp.route("/.well-known/oauth-authorization-server", methods=["GET"], strict_slashes=False)
@mcp_admin_bp.route("/.well-known/oauth-authorization-server/api/admin/mcp", methods=["GET"], strict_slashes=False)
@mcp_admin_bp.route("/.well-known/openid-configuration", methods=["GET"], strict_slashes=False)
def oauth_authorization_server_metadata():
    if not _oauth_enabled():
        return jsonify({"error": "OAuth is disabled"}), 404
    metadata = _oauth_authorization_server_metadata()
    logger.info(f"OAuth server metadata requested. Token endpoint: {metadata.get('token_endpoint')}")
    return jsonify(metadata)


@mcp_admin_bp.route("/.well-known/oauth-protected-resource/api/admin/mcp", methods=["GET"], strict_slashes=False)
def oauth_protected_resource_metadata():
    if not _oauth_enabled():
        return jsonify({"error": "OAuth is disabled"}), 404
    return jsonify(_oauth_protected_resource_metadata_payload())


@mcp_admin_bp.route("/api/admin/mcp/oauth/register", methods=["POST"], strict_slashes=False)
def oauth_register():
    if not _oauth_enabled():
        return jsonify({"error": "OAuth is disabled"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        client_doc = _register_client_document(payload)
    except ValueError as exc:
        return _oauth_json_error("invalid_client_metadata", str(exc), status=400)
    return jsonify(client_doc), 201


@mcp_admin_bp.route("/api/admin/mcp/oauth/authorize", methods=["GET", "POST"], strict_slashes=False)
def oauth_authorize():
    if not _oauth_enabled():
        return jsonify({"error": "OAuth is disabled"}), 404

    if request.method == "GET":
        if not getattr(current_user, "is_authenticated", False):
            return redirect(url_for("users.auth.login", next=request.url))
        if not _is_mcp_admin_user(current_user):
            return "Admin MCP access requires full global authority.", 403

        client_id = (request.args.get("client_id") or "").strip()
        redirect_uri = (request.args.get("redirect_uri") or "").strip()
        response_type = (request.args.get("response_type") or "").strip()
        state = (request.args.get("state") or "").strip()
        scope = request.args.get("scope")
        code_challenge = (request.args.get("code_challenge") or "").strip()
        code_challenge_method = (request.args.get("code_challenge_method") or "plain").strip()

        client = _lookup_client(client_id)
        if not client:
            return _oauth_json_error("invalid_client", "Unknown OAuth client", status=400)
        if response_type != "code":
            return _oauth_json_error("unsupported_response_type", "Only authorization code flow is supported", status=400)
        if redirect_uri not in (client.get("redirect_uris") or []):
            return _oauth_json_error("invalid_request", "redirect_uri is not registered for this client", status=400)
        if code_challenge_method not in {"plain", "S256"}:
            return _oauth_json_error("invalid_request", "Unsupported code_challenge_method", status=400)

        requested_scopes = _normalize_scope_list(scope, default_to_all=True)
        if not requested_scopes:
            return _oauth_json_error("invalid_scope", "No supported scopes were requested", status=400)

        return render_template(
            "oauth/mcp_consent.html",
            client=client,
            client_name=client.get("client_name") or client_id,
            redirect_uri=redirect_uri,
            response_type=response_type,
            state=state,
            scope=_serialize_scope_list(requested_scopes),
            scopes=requested_scopes,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            csrf_token=_consent_csrf_token(),
        )

    if not getattr(current_user, "is_authenticated", False):
        return redirect(url_for("users.auth.login", next=request.url))
    if not _is_mcp_admin_user(current_user):
        return "Admin MCP access requires full global authority.", 403

    expected_csrf = session.get(MCP_CONSENT_CSRF_SESSION_KEY, "")
    provided_csrf = request.form.get("csrf_token", "")
    if not (
        expected_csrf and provided_csrf
        and hmac.compare_digest(expected_csrf.encode("utf-8"), provided_csrf.encode("utf-8"))
    ):
        return _oauth_json_error("invalid_request", "Invalid consent CSRF token", status=403)

    client_id = (request.form.get("client_id") or "").strip()
    redirect_uri = (request.form.get("redirect_uri") or "").strip()
    state = (request.form.get("state") or "").strip()
    scope = request.form.get("scope")
    code_challenge = (request.form.get("code_challenge") or "").strip() or None
    code_challenge_method = (request.form.get("code_challenge_method") or "plain").strip()
    decision = (request.form.get("decision") or "deny").strip()

    client = _lookup_client(client_id)
    if not client or redirect_uri not in (client.get("redirect_uris") or []):
        return _oauth_json_error("invalid_client", "Unknown OAuth client", status=400)
    if decision != "approve":
        return _oauth_error_redirect(
            redirect_uri,
            error="access_denied",
            state=state or None,
            description="The user denied the MCP authorization request.",
        )

    granted_scopes = _normalize_scope_list(scope, default_to_all=True)
    if not granted_scopes:
        return _oauth_error_redirect(
            redirect_uri,
            error="invalid_scope",
            state=state or None,
            description="No supported scopes were requested.",
        )

    code = _store_authorization_code(
        client_id=client_id,
        user_id=current_user._id,
        redirect_uri=redirect_uri,
        scope=_serialize_scope_list(granted_scopes),
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
    )
    params = {"code": code}
    if state:
        params["state"] = state
    separator = "&" if "?" in redirect_uri else "?"
    return redirect(f"{redirect_uri}{separator}{urlencode(params)}")


@mcp_admin_bp.route("/api/admin/mcp/oauth/token", methods=["POST"], strict_slashes=False)
def oauth_token():
    logger.info("OAuth token exchange requested")
    if not _oauth_enabled():
        logger.warning("OAuth not enabled, rejecting token request")
        return jsonify({"error": "OAuth is disabled"}), 404

    grant_type = (request.form.get("grant_type") or "").strip()
    logger.debug(f"OAuth token request - grant_type: {grant_type}")
    if grant_type != "authorization_code":
        logger.warning(f"Unsupported grant type: {grant_type}")
        return _oauth_json_error("unsupported_grant_type", "Only authorization_code is supported", status=400)

    client, client_id, client_secret = _resolve_client_auth()
    logger.debug(f"OAuth client resolution - client_id: {client_id}, auth method: {'basic' if request.authorization else 'form'}")
    try:
        client = _validate_client_auth(client, client_id, client_secret)
        logger.info(f"OAuth client authenticated successfully: {client_id}")
    except LookupError as exc:
        logger.warning(f"OAuth client lookup failed: {exc}")
        return _oauth_json_error("invalid_client", str(exc), status=401)
    except PermissionError as exc:
        logger.warning(f"OAuth client secret invalid: {exc}")
        return _oauth_json_error("invalid_client", str(exc), status=401)

    code_value = (request.form.get("code") or "").strip()
    redirect_uri = (request.form.get("redirect_uri") or "").strip()
    code_verifier = (request.form.get("code_verifier") or "").strip()
    logger.debug(f"OAuth token exchange - code present: {bool(code_value)}, redirect_uri: {redirect_uri}")
    if not code_value or not redirect_uri:
        return _oauth_json_error("invalid_request", "code and redirect_uri are required", status=400)

    code_doc = _authorization_code_collection().find_one({"code": code_value})
    if not code_doc:
        return _oauth_json_error("invalid_grant", "Authorization code is invalid", status=400)
    if code_doc.get("used_at") is not None:
        return _oauth_json_error("invalid_grant", "Authorization code has already been used", status=400)
    expires_at = code_doc.get("expires_at")
    if expires_at:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            return _oauth_json_error("invalid_grant", "Authorization code has expired", status=400)
    if code_doc.get("client_id") != client["client_id"]:
        return _oauth_json_error("invalid_grant", "Authorization code was issued to another client", status=400)
    if code_doc.get("redirect_uri") != redirect_uri:
        return _oauth_json_error("invalid_grant", "redirect_uri does not match the original authorization request", status=400)

    code_challenge = code_doc.get("code_challenge")
    code_challenge_method = code_doc.get("code_challenge_method") or "plain"
    if code_challenge:
        if not code_verifier:
            return _oauth_json_error("invalid_request", "code_verifier is required for this authorization code", status=400)
        derived_challenge = _code_challenge_s256(code_verifier) if code_challenge_method == "S256" else code_verifier
        if not hmac.compare_digest(code_challenge, derived_challenge):
            return _oauth_json_error("invalid_grant", "code_verifier did not match the original code challenge", status=400)

    now = datetime.now(timezone.utc)
    consumed = _authorization_code_collection().update_one(
        {
            "_id": code_doc["_id"],
            "used_at": None,
            "$or": [{"expires_at": None}, {"expires_at": {"$gte": now}}],
        },
        {"$set": {"used_at": now}},
    )
    if consumed.matched_count != 1:
        return _oauth_json_error("invalid_grant", "Authorization code is expired or already used", status=400)
    access_token = _issue_oauth_access_token(
        client_id=client["client_id"],
        user_id=code_doc["user_id"],
        scope=code_doc.get("scope") or _serialize_scope_list(_oauth_default_scopes()),
    )
    return jsonify(
        {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": code_doc.get("scope") or _serialize_scope_list(_oauth_default_scopes()),
        }
    )


# Alternative token endpoint routes for OAuth client compatibility
@mcp_admin_bp.route("/token", methods=["POST"], strict_slashes=False)
@mcp_admin_bp.route("/.well-known/oauth/token", methods=["POST"], strict_slashes=False)
def oauth_token_alias():
    """Alias endpoint for OAuth token exchange (for client compatibility)"""
    logger.debug("OAuth token request via alternative endpoint (/token)")
    return oauth_token()


@mcp_admin_bp.route("/api/admin/mcp", methods=["POST"], strict_slashes=False)
def handle_admin_mcp():
    request_json = request.get_json(silent=True) or {}
    request_id = request_json.get("id")
    logger.debug(f"MCP request received - ID: {request_id}, Method: {request_json.get('method')}, Params: {list(request_json.get('params', {}).keys())}")

    try:
        token_entry = _authenticate()
        if not token_entry:
            logger.warning(f"MCP request unauthorized - ID: {request_id}")
            return _unauthorized_mcp_response(request_id)
        _require_scope(token_entry, "read")
    except PermissionError as exc:
        logger.warning(
            "MCP connection permission denied - ID: %s, Error: %s",
            request_id,
            exc,
        )
        return _jsonrpc_error(request_id, -32003, str(exc), http_status=403)

    method = request_json.get("method")
    params = request_json.get("params") or {}

    if method == "initialize":
        return _jsonrpc_response(
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "mielenosoitukset-admin-mcp", "version": "0.1.0"},
            },
            request_id,
        )

    if method == "ping":
        return _jsonrpc_response({}, request_id)

    if method == "notifications/initialized":
        return ("", 202)

    if method == "tools/list":
        return _jsonrpc_response(
            {
                "tools": [
                    {
                        "name": name,
                        "description": tool["description"],
                        "inputSchema": tool["inputSchema"],
                    }
                    for name, tool in TOOLS.items()
                ]
            },
            request_id,
        )

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}
        tool = TOOLS.get(tool_name)
        if not tool:
            logger.error(f"MCP tool not found - ID: {request_id}, Tool: {tool_name}")
            return _jsonrpc_error(request_id, -32602, f"Unknown tool: {tool_name}")
        logger.debug(f"MCP tool call - ID: {request_id}, Tool: {tool_name}, Arguments: {list(arguments.keys())}")
        try:
            result = tool["handler"](arguments, token_entry)
            logger.debug(f"MCP tool succeeded - ID: {request_id}, Tool: {tool_name}")
            return _jsonrpc_response(result, request_id)
        except PermissionError as exc:
            logger.warning(f"MCP tool permission denied - ID: {request_id}, Tool: {tool_name}, Error: {exc}")
            return _jsonrpc_error(request_id, -32003, str(exc), http_status=403)
        except (ValueError, TypeError) as exc:
            logger.warning(f"MCP tool invalid argument - ID: {request_id}, Tool: {tool_name}, Error: {exc}")
            return _jsonrpc_error(request_id, -32602, str(exc))
        except LookupError as exc:
            logger.warning(f"MCP tool not found - ID: {request_id}, Tool: {tool_name}, Error: {exc}")
            return _jsonrpc_error(request_id, -32004, str(exc), http_status=404)
        except Exception as exc:
            logger.exception(f"MCP tool error - ID: {request_id}, Tool: {tool_name}, Error: {exc}")
            return _jsonrpc_error(request_id, -32603, "Internal MCP tool error", data=str(exc), http_status=500)

    return _jsonrpc_error(request_id, -32601, f"Method not found: {method}")
