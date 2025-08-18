from flask import Blueprint, request, jsonify, render_template
from werkzeug.utils import secure_filename
import os
from mielenosoitukset_fi.utils.s3 import upload_image_fileobj
from mielenosoitukset_fi.utils.logger import logger
from mielenosoitukset_fi.database_manager import DatabaseManager

import datetime
from bson.objectid import ObjectId
from flask_login import current_user

db_manager = DatabaseManager().get_instance()
mongo = db_manager.get_db()


admin_media_bp = Blueprint("admin_media_bp", __name__, url_prefix="/admin/media")

UPLOAD_FOLDER = "mielenosoitukset_fi/uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}


def allowed_file(filename):
    """Check if the file has an allowed extension.

    Parameters
    ----------
    filename : str
        The name of the file to check.

    Returns
    -------
    bool
        True if the file has an allowed extension, False otherwise.
    """
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@admin_media_bp.route("/upload", methods=["POST"])
def upload_file():
    """Handle file upload and upload it to S3.

    Returns
    -------
    Response
        JSON response with the status and URL of the uploaded file.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        bucket_name = "mielenosoitukset.fi"
        image_type = request.form.get("image_type", "default")

        # Upload straight from the file storage stream
        s3_url = upload_image_fileobj(bucket_name, file.stream, filename, image_type)
        if s3_url:
            mongo.media.insert_one(
                {
                    "url": s3_url,
                    "uploaded_at": datetime.datetime.now(),
                    "uploader": ObjectId(current_user._id),
                }
            )
            return jsonify({"success": True, "url": s3_url}), 200
        else:
            return jsonify({"error": "Failed to upload to S3"}), 500
    else:
        return jsonify({"error": "File type not allowed"}), 400


@admin_media_bp.route("/dashboard", methods=["GET"])
def dashboard():
    """Render the dashboard page.

    Returns
    -------
    Response
        Rendered HTML page for the dashboard.
    """
    return render_template("admin/s3/dashboard.html")


# route for viewing all media
@admin_media_bp.route("/view", methods=["GET"])
def view_media():
    """View all media files.

    Returns
    -------
    Response
        Rendered HTML page with all media files.
    """
    media = list(mongo.media.find())
    return render_template("admin/s3/view_media.html", media=media)


@admin_media_bp.route("/upload_multiple", methods=["POST"])
def upload_multiple():
    """Handle multiple file uploads and upload them to S3.

    Returns
    -------
    Response
        JSON response with the status of each uploaded file.
    """
    if "photos" not in request.files:
        return jsonify({"error": "No file part"}), 400

    files = request.files.getlist("photos")
    if not files:
        return jsonify({"error": "No selected files"}), 400

    responses = []
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            bucket_name = "mielenosoitukset.fi"
            image_type = request.form.get("image_type", "default")

            s3_url = upload_image_fileobj(bucket_name, file.stream, filename, image_type)
            if s3_url:
                mongo.media.insert_one(
                    {
                        "url": s3_url,
                        "uploaded_at": datetime.datetime.now(),
                        "uploader": ObjectId(current_user._id),
                    }
                )
                responses.append({"success": True, "url": s3_url})
            else:
                responses.append({"error": f"Failed to upload {filename} to S3"})
        else:
            responses.append({"error": f"File type not allowed for {file.filename}"})

    return jsonify(responses), 200
