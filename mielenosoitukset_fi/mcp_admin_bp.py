from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime
from typing import Any

from bson import ObjectId
from flask import Blueprint, current_app, jsonify, request

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.classes.Case import Case
from mielenosoitukset_fi.utils.classes.Demonstration import Demonstration
from mielenosoitukset_fi.utils.classes.Organization import Organization
from mielenosoitukset_fi.utils.database import stringify_object_ids


mcp_admin_bp = Blueprint("admin_mcp", __name__, url_prefix="/api/admin/mcp")


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


def _authenticate() -> dict[str, Any] | None:
    if not _get_mcp_config().get("ENABLED", False):
        return None

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    supplied_token = auth_header.split(" ", 1)[1].strip()
    if not supplied_token:
        return None

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
    if scope not in scopes and "write" not in scopes and "admin" not in scopes:
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
        created_datetime=datetime.utcnow(),
        last_modified=datetime.utcnow(),
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

    demo.last_modified = datetime.utcnow()
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
        "timestamp": datetime.utcnow(),
        "admin": actor,
        "action_type": "close_case",
        "note": reason,
    }
    history_entry = {
        "timestamp": datetime.utcnow(),
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
                "updated_at": datetime.utcnow(),
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
        "timestamp": datetime.utcnow(),
        "admin": actor,
        "action_type": "reopen_case",
        "note": reason,
    }
    history_entry = {
        "timestamp": datetime.utcnow(),
        "action": "Case reopened",
        "user": actor,
        "metadata": {"reason": reason, "source": "mcp"},
    }
    db.cases.update_one(
        {"_id": ObjectId(case_id)},
        {
            "$set": {
                "meta.closed": False,
                "updated_at": datetime.utcnow(),
            },
            "$unset": {"meta.closed_reason": ""},
            "$push": {"action_logs": action_entry, "case_history": history_entry},
        },
    )
    return _serialize_result({"updated": True, "case_id": case_id, "closed": False})


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


@mcp_admin_bp.route("", methods=["POST"])
def handle_admin_mcp():
    request_json = request.get_json(silent=True) or {}
    request_id = request_json.get("id")

    token_entry = _authenticate()
    if not token_entry:
        return _jsonrpc_error(request_id, -32001, "Unauthorized MCP token", http_status=401)

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
