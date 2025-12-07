# blueprints/notification_bp.py
from flask import Blueprint, jsonify, render_template
from flask_login import login_required, current_user

from utils.notifications import (
    fetch_notifications,
    mark_all_read,
    serialize_notification,
)

notif_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


@notif_bp.route("/", methods=["GET"])
@login_required
def list_notifications():
    """
    JSON API: return serialized notifications for current user.
    Used by header dropdown JS.
    """
    raw = fetch_notifications(current_user.id)
    data = [serialize_notification(n) for n in raw]
    return jsonify(data)


@notif_bp.route("/mark-read", methods=["POST"])
@login_required
def mark_read():
    """
    Mark all notifications for current user as read.
    Used by dropdown + can be used from full list.
    """
    mark_all_read(current_user.id)
    return jsonify({"success": True})


@notif_bp.route("/all", methods=["GET"])
@login_required
def list_all_page():
    """
    Full page that shows all (or last N) notifications.
    Renders notifications/all.html with the same serialized dicts
    as the JSON API, including .message, .icon, .read, .created_at, etc.
    """
    raw = fetch_notifications(current_user.id, limit=50)
    notifs = [serialize_notification(n) for n in raw]
    return render_template("notifications/all.html", notifications=notifs)
