from flask import Blueprint, abort, render_template, request, url_for
from flask_login import current_user, login_required

from mielenosoitukset_fi.utils.city_settings import enabled_city_keys
from mielenosoitukset_fi.utils.wrappers import admin_required, permission_required

from .board_audit import audit_rows
from .board_compliance import clearance_rows, governance_csrf_token
from .pagination import build_admin_pagination, parse_admin_pagination
from .utils import _ADMIN_TEMPLATE_FOLDER, mongo


admin_governance_bp = Blueprint(
    "admin_governance",
    __name__,
    url_prefix="/admin/governance",
)


def _can(permission):
    return bool(
        getattr(current_user, "global_admin", False)
    ) or current_user.has_permission(permission)


@admin_governance_bp.route("/")
@login_required
@admin_required
def dashboard():
    permissions = {
        "clearances": _can("MANAGE_CLEARANCE"),
        "audit": _can("VIEW_CLEARANCE_AUDIT"),
        "cities": _can("MANAGE_CITIES"),
    }
    if not any(permissions.values()):
        abort(403)

    clearance_count = mongo.board_clearances.count_documents({"approved": True})
    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}governance/dashboard.html",
        permissions=permissions,
        clearance_count=clearance_count,
        active_city_count=len(enabled_city_keys(mongo)),
        recent_events=audit_rows(limit=5) if permissions["audit"] else [],
    )


@admin_governance_bp.route("/clearances")
@login_required
@admin_required
@permission_required("MANAGE_CLEARANCE")
def clearances():
    all_users = clearance_rows()
    total_count = len(all_users)
    approved_count = sum(1 for user in all_users if user["approved"])
    search_query = (request.args.get("search") or "").strip()
    approval_filter = (request.args.get("approval") or "all").strip().lower()
    if approval_filter not in {"all", "approved", "missing"}:
        approval_filter = "all"

    normalized_search = search_query.casefold()
    users = [
        user
        for user in all_users
        if (
            not normalized_search
            or normalized_search
            in f"{user.get('username') or ''} {user.get('role') or ''}".casefold()
        )
        and (
            approval_filter == "all"
            or (approval_filter == "approved" and user["approved"])
            or (approval_filter == "missing" and not user["approved"])
        )
    ]
    filtered_count = len(users)
    page, per_page = parse_admin_pagination(request.args)
    pagination = build_admin_pagination(
        "admin_governance.clearances",
        total_count=filtered_count,
        page=page,
        per_page=per_page,
        query_args={"search": search_query, "approval": approval_filter},
    )
    users = users[pagination["slice_start"] : pagination["slice_end"]]
    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}governance/clearances.html",
        users=users,
        approved_count=approved_count,
        total_count=total_count,
        filtered_count=filtered_count,
        search_query=search_query,
        approval_filter=approval_filter,
        clear_filters_url=url_for("admin_governance.clearances"),
        governance_csrf_token=governance_csrf_token(),
        **pagination,
    )


@admin_governance_bp.route("/audit")
@login_required
@admin_required
@permission_required("VIEW_CLEARANCE_AUDIT")
def audit_log():
    all_events = audit_rows()
    total_count = len(all_events)
    search_query = (request.args.get("search") or "").strip()
    action_filter = (request.args.get("action") or "all").strip().lower()
    allowed_actions = {
        (event.get("action") or "").strip().lower()
        for event in all_events
        if event.get("action")
    }
    if action_filter != "all" and action_filter not in allowed_actions:
        action_filter = "all"

    normalized_search = search_query.casefold()
    audit_events = [
        event
        for event in all_events
        if (
            not normalized_search
            or normalized_search
            in (
                f"{event.get('username') or ''} {event.get('action') or ''} "
                f"{event.get('granted_by') or ''}"
            ).casefold()
        )
        and (
            action_filter == "all"
            or (event.get("action") or "").strip().lower() == action_filter
        )
    ]
    filtered_count = len(audit_events)
    page, per_page = parse_admin_pagination(request.args)
    pagination = build_admin_pagination(
        "admin_governance.audit_log",
        total_count=filtered_count,
        page=page,
        per_page=per_page,
        query_args={"search": search_query, "action": action_filter},
    )
    audit_events = audit_events[
        pagination["slice_start"] : pagination["slice_end"]
    ]
    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}governance/audit.html",
        audit_events=audit_events,
        action_options=sorted(allowed_actions),
        total_count=total_count,
        filtered_count=filtered_count,
        search_query=search_query,
        action_filter=action_filter,
        clear_filters_url=url_for("admin_governance.audit_log"),
        **pagination,
    )
