from flask import Blueprint, abort, render_template
from flask_login import current_user, login_required

from mielenosoitukset_fi.utils.city_settings import enabled_city_keys
from mielenosoitukset_fi.utils.wrappers import admin_required, permission_required

from .board_audit import audit_rows
from .board_compliance import clearance_rows
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
    users = clearance_rows()
    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}governance/clearances.html",
        users=users,
        approved_count=sum(1 for user in users if user["approved"]),
    )


@admin_governance_bp.route("/audit")
@login_required
@admin_required
@permission_required("VIEW_CLEARANCE_AUDIT")
def audit_log():
    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}governance/audit.html",
        audit_events=audit_rows(),
    )
