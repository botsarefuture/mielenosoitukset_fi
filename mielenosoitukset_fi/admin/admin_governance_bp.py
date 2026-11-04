import hmac

from bson import ObjectId
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from mielenosoitukset_fi.utils.city_settings import enabled_city_keys
from mielenosoitukset_fi.utils.wrappers import (
    admin_required, permission_required, global_permission_required, has_global_permission,
)

from .board_audit import audit_rows
from .board_compliance import clearance_rows, governance_csrf_token
from .pagination import build_admin_pagination, parse_admin_pagination
from .utils import _ADMIN_TEMPLATE_FOLDER, mongo
from mielenosoitukset_fi.utils.system_teams import board_ids, clearance_record_approved
from mielenosoitukset_fi.utils.team_governance import override_role
from mielenosoitukset_fi.utils.security_cases import actor_access, decide, open_case
from mielenosoitukset_fi.utils.team_governance import GovernanceConflict
from mielenosoitukset_fi.utils.time_utils import utcnow


admin_governance_bp = Blueprint(
    "admin_governance",
    __name__,
    url_prefix="/admin/governance",
)


@admin_governance_bp.route("/security", methods=["GET", "POST"])
@login_required
def security():
    try:
        actor_access(mongo, current_user)
    except PermissionError:
        abort(403)
    error = None
    status = 200
    if request.method == "POST":
        expected = session.get("governance_csrf_token", "")
        if not expected or not hmac.compare_digest(expected, request.form.get("csrf_token", "")):
            abort(403)
        try:
            if request.form.get("case_id"):
                decide(mongo, request.form["case_id"], current_user, request.form.get("action"), request.form.get("reason"),
                       recovery_confirmed=request.form.get("recovery_confirmed") == "yes", hearing=request.form.get("hearing"))
            else:
                lockdown = request.form.get("action") == "lockdown"
                target = None if lockdown else mongo.users.find_one({"username_canonical": request.form.get("username", "").strip().casefold()})
                if not lockdown and not target:
                    raise ValueError("Käyttäjää ei löytynyt.")
                open_case(mongo, current_user, target["_id"] if target else None, request.form.get("reason"), lockdown=lockdown)
            flash("Päätös tai osahyväksyntä kirjattu. Ilmoitukset lähetetään sähköpostityöntekijällä.", "success")
            return redirect(url_for("admin_governance.security"), code=303)
        except PermissionError as exc:
            error, status = str(exc), 403
        except (GovernanceConflict, ValueError) as exc:
            error, status = str(exc), 409
    from mielenosoitukset_fi.utils.security_cases import _roster
    cases = list(mongo.security_cases.find().sort("created_at", -1).limit(100))
    for case in cases:
        target = mongo.users.find_one({"_id": ObjectId(case["target_id"])}) if case["target_id"] else None
        case["reviewers"] = len(set(_roster(mongo, target).values()))
        case["overdue"] = case.get("status") == "suspended" and case.get("review_due_at", utcnow()) <= utcnow()
    return render_template(f"{_ADMIN_TEMPLATE_FOLDER}governance/security.html", cases=cases, error=error,
                           governance_csrf_token=governance_csrf_token()), status


def _can(permission):
    return bool(
        getattr(current_user, "global_admin", False)
    ) or current_user.has_permission(permission)


@admin_governance_bp.route("/")
@login_required
@admin_required
def dashboard():
    permissions = {
        "clearances": has_global_permission(current_user, "MANAGE_CLEARANCE"),
        "audit": _can("VIEW_CLEARANCE_AUDIT"),
        "cities": _can("MANAGE_CITIES"),
    }
    if not any(permissions.values()):
        abort(403)

    clearance_count = sum(clearance_record_approved(row) for row in mongo.board_clearances.find({"approved": True}))
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
@global_permission_required("MANAGE_CLEARANCE")
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
        can_vote=str(current_user.id) in board_ids(mongo),
        can_override=override_role(mongo,current_user) is not None,
        board_size=len(board_ids(mongo)),
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
