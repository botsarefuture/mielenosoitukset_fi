from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

from bson import ObjectId
from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
import jwt

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.api.exceptions import ApiException
from mielenosoitukset_fi.utils.classes.Case import Case
from mielenosoitukset_fi.utils.classes.Demonstration import Demonstration
from mielenosoitukset_fi.utils.classes.Organization import Organization
from mielenosoitukset_fi.utils.database import stringify_object_ids
from mielenosoitukset_fi.utils.tokens import check_token


mcp_admin_bp = Blueprint("admin_mcp", __name__)


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


def _normalize_organizers(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return []


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
    if getattr(user, "global_admin", False):
        return True
    return getattr(user, "role", None) in {"god", "global_admin", "admin", "superuser"}


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
        return None

    algorithms = oauth.get("JWT_ALGORITHMS") or ["HS256"]
    issuer = oauth.get("ISSUER")
    audience = oauth.get("AUDIENCE") or _oauth_audience()
    shared_secret = _oauth_signing_secret()
    public_key = oauth.get("JWT_PUBLIC_KEY")
    required_scopes = _oauth_required_scopes()

    verification_key = public_key or shared_secret
    if not verification_key:
        return None

    decode_kwargs: dict[str, Any] = {"algorithms": algorithms}
    if audience:
        decode_kwargs["audience"] = audience
    if issuer:
        decode_kwargs["issuer"] = issuer

    claims = jwt.decode(supplied_token, verification_key, **decode_kwargs)
    scopes = _scopes_from_claims(claims)
    if required_scopes and not all(scope in scopes for scope in required_scopes):
        raise PermissionError("OAuth token missing required MCP scopes")

    return {
        "name": claims.get("sub") or claims.get("client_id") or "oauth-token",
        "scopes": scopes or ["read"],
        "claims": claims,
        "auth_type": "oauth_bearer",
    }


def _authenticate() -> dict[str, Any] | None:
    if not _get_mcp_config().get("ENABLED", False):
        return None

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    supplied_token = auth_header.split(" ", 1)[1].strip()
    if not supplied_token:
        return None

    try:
        token_record = check_token(supplied_token)
        return {
            "name": str(token_record.get("user_id") or token_record.get("app_id") or "api-token"),
            "scopes": token_record.get("scopes") or ["read"],
            "token_record": token_record,
            "auth_type": "api_token",
        }
    except ApiException:
        pass

    try:
        oauth_entry = _authenticate_oauth_bearer(supplied_token)
        if oauth_entry:
            return oauth_entry
    except jwt.PyJWTError:
        pass

    supplied_hash = hashlib.sha256(supplied_token.encode("utf-8")).hexdigest()
    for entry in _token_entries():
        entry_token = entry.get("token")
        entry_hash = entry.get("sha256")
        if entry_token and hmac.compare_digest(entry_token, supplied_token):
            return entry
        if entry_hash and hmac.compare_digest(entry_hash, supplied_hash):
            return entry
    return None


def _require_scope(token_entry: dict[str, Any], scope: str) -> None:
    scopes = token_entry.get("scopes") or []
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
    doc = _mongo().demonstrations.find_one({"_id": ObjectId(demo_id)})
    if not doc:
        raise LookupError("Demonstration not found")
    return _serialize_result(doc)


def _create_demo(arguments: dict[str, Any], token_entry: dict[str, Any]) -> dict[str, Any]:
    _require_scope(token_entry, "write")
    required = ["title", "date", "start_time", "end_time", "city", "address"]
    missing = [field for field in required if not arguments.get(field)]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    demo = Demonstration(
        title=arguments["title"],
        date=arguments["date"],
        start_time=arguments["start_time"],
        end_time=arguments["end_time"],
        city=arguments["city"],
        address=arguments["address"],
        description=arguments.get("description"),
        facebook=arguments.get("facebook"),
        route=arguments.get("route"),
        event_type=arguments.get("event_type") or arguments.get("type") or "other",
        tags=_normalize_tags(arguments.get("tags")),
        organizers=_normalize_organizers(arguments.get("organizers")),
        approved=bool(arguments.get("approved", False)),
        hide=bool(arguments.get("hide", False)),
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

    db = _mongo()
    doc = db.demonstrations.find_one({"_id": ObjectId(demo_id)})
    if not doc:
        raise LookupError("Demonstration not found")

    demo = Demonstration.from_dict(doc)
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
        "approved",
        "hide",
        "cancelled",
        "event_type",
    }
    applied: dict[str, Any] = {}
    for key, value in patch.items():
        if key not in allowed_fields:
            continue
        if key == "tags":
            value = _normalize_tags(value)
        elif key == "organizers":
            value = _normalize_organizers(value)
        setattr(demo, key, value)
        applied[key] = value

    if not applied:
        raise ValueError("No supported fields in patch")

    demo.last_modified = datetime.now(timezone.utc)
    demo.save()
    return _serialize_result({"updated": True, "demo_id": demo._id, "applied": applied})


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
    required = ["name", "email", "description"]
    missing = [field for field in required if not arguments.get(field)]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    organization = Organization(
        name=arguments["name"],
        description=arguments["description"],
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
        "description": "Create a new demonstration.",
        "inputSchema": {
            "type": "object",
            "required": ["title", "date", "start_time", "end_time", "city", "address"],
            "properties": {
                "title": {"type": "string"},
                "date": {"type": "string"},
                "start_time": {"type": "string"},
                "end_time": {"type": "string"},
                "city": {"type": "string"},
                "address": {"type": "string"},
                "description": {"type": "string"},
                "facebook": {"type": "string"},
                "route": {},
                "event_type": {"type": "string"},
                "tags": {},
                "organizers": {"type": "array"},
                "approved": {"type": "boolean"},
                "hide": {"type": "boolean"},
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
                "patch": {"type": "object"},
            },
        },
        "handler": _update_demo,
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
            "required": ["name", "email", "description"],
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "description": {"type": "string"},
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


@mcp_admin_bp.route("/.well-known/oauth-authorization-server", methods=["GET"])
@mcp_admin_bp.route("/.well-known/oauth-authorization-server/api/admin/mcp", methods=["GET"])
@mcp_admin_bp.route("/.well-known/openid-configuration", methods=["GET"])
def oauth_authorization_server_metadata():
    if not _oauth_enabled():
        return jsonify({"error": "OAuth is disabled"}), 404
    return jsonify(_oauth_authorization_server_metadata())


@mcp_admin_bp.route("/.well-known/oauth-protected-resource/api/admin/mcp", methods=["GET"])
def oauth_protected_resource_metadata():
    if not _oauth_enabled():
        return jsonify({"error": "OAuth is disabled"}), 404
    return jsonify(_oauth_protected_resource_metadata_payload())


@mcp_admin_bp.route("/api/admin/mcp/oauth/register", methods=["POST"])
def oauth_register():
    if not _oauth_enabled():
        return jsonify({"error": "OAuth is disabled"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        client_doc = _register_client_document(payload)
    except ValueError as exc:
        return _oauth_json_error("invalid_client_metadata", str(exc), status=400)
    return jsonify(client_doc), 201


@mcp_admin_bp.route("/api/admin/mcp/oauth/authorize", methods=["GET", "POST"])
def oauth_authorize():
    if not _oauth_enabled():
        return jsonify({"error": "OAuth is disabled"}), 404

    if request.method == "GET":
        if not getattr(current_user, "is_authenticated", False):
            return redirect(url_for("users.auth.login", next=request.url))
        if not _is_mcp_admin_user(current_user):
            return "Admin MCP access requires an admin-capable account.", 403

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
        )

    if not getattr(current_user, "is_authenticated", False):
        return redirect(url_for("users.auth.login", next=request.url))
    if not _is_mcp_admin_user(current_user):
        return "Admin MCP access requires an admin-capable account.", 403

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


@mcp_admin_bp.route("/api/admin/mcp/oauth/token", methods=["POST"])
def oauth_token():
    if not _oauth_enabled():
        return jsonify({"error": "OAuth is disabled"}), 404

    grant_type = (request.form.get("grant_type") or "").strip()
    if grant_type != "authorization_code":
        return _oauth_json_error("unsupported_grant_type", "Only authorization_code is supported", status=400)

    client, client_id, client_secret = _resolve_client_auth()
    try:
        client = _validate_client_auth(client, client_id, client_secret)
    except LookupError as exc:
        return _oauth_json_error("invalid_client", str(exc), status=401)
    except PermissionError as exc:
        return _oauth_json_error("invalid_client", str(exc), status=401)

    code_value = (request.form.get("code") or "").strip()
    redirect_uri = (request.form.get("redirect_uri") or "").strip()
    code_verifier = (request.form.get("code_verifier") or "").strip()
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

    _authorization_code_collection().update_one(
        {"_id": code_doc["_id"]},
        {"$set": {"used_at": datetime.now(timezone.utc)}},
    )
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


@mcp_admin_bp.route("/api/admin/mcp", methods=["POST"])
def handle_admin_mcp():
    request_json = request.get_json(silent=True) or {}
    request_id = request_json.get("id")

    token_entry = _authenticate()
    if not token_entry:
        return _unauthorized_mcp_response(request_id)

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
            return _jsonrpc_error(request_id, -32602, f"Unknown tool: {tool_name}")
        try:
            return _jsonrpc_response(tool["handler"](arguments, token_entry), request_id)
        except PermissionError as exc:
            return _jsonrpc_error(request_id, -32003, str(exc), http_status=403)
        except (ValueError, TypeError) as exc:
            return _jsonrpc_error(request_id, -32602, str(exc))
        except LookupError as exc:
            return _jsonrpc_error(request_id, -32004, str(exc), http_status=404)
        except Exception as exc:
            return _jsonrpc_error(request_id, -32603, "Internal MCP tool error", data=str(exc), http_status=500)

    return _jsonrpc_error(request_id, -32601, f"Method not found: {method}")
