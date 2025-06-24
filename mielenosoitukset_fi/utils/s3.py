import os
import shutil
from PIL import Image
import time

from config import Config  # Only used for other stuff; not needed by uploader now
from mielenosoitukset_fi.utils.logger import logger
from mielenosoitukset_fi.database_manager import DatabaseManager

# ─── DB setup ────────────────────────────────────────────────────────────────────
db_manager = DatabaseManager().get_instance()
mongo = db_manager.get_db()

# ─── Constants ──────────────────────────────────────────────────────────────────
_upload_folder = os.path.join("mielenosoitukset_fi", "uploads")
_LOCAL_STORAGE_ROOT = os.path.join("mielenosoitukset_fi", "static", "images")

os.makedirs(_upload_folder, exist_ok=True)
os.makedirs(_LOCAL_STORAGE_ROOT, exist_ok=True)

# ─── Retry decorator (unchanged) ────────────────────────────────────────────────
_max_retries = 3
_retry_delay = 2
def retry_with_graze(max_retries=_max_retries, delay=_retry_delay):
    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries < max_retries:
                        logger.warning(f"Retry {retries}/{max_retries} after error: {e}")
                        time.sleep(delay * (2 ** (retries - 1)))
                    else:
                        logger.info(
                            f"Well, grazed it. {func.__name__} didn’t succeed, moving on."
                        )
                        return None
        return wrapper
    return decorator

# ─── Helpers ────────────────────────────────────────────────────────────────────
def gen_ha(image_type: str) -> str:
    return image_type[:3].upper()

def get_id_and_add_one(hash_: str) -> int:
    last_id = mongo.s3_ids.find_one_and_update(
        {"hash": hash_},
        {"$inc": {"last_id": 1}},
        upsert=True,
        return_document=True,
    )
    return last_id["last_id"]

@retry_with_graze()
def generate_next_id(image_type: str = "upload") -> int:
    return get_id_and_add_one(gen_ha(image_type))

@retry_with_graze()
def convert_to_jpg(image_path: str, output_path: str) -> str | None:
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            img.save(output_path, "JPEG")
        logger.info(f"Image converted to JPEG: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Error converting image {image_path}: {e}")
        return None

# ─── Local-only uploader ────────────────────────────────────────────────────────
@retry_with_graze()
def upload_image(image_path: str, image_type: str = "upload") -> str | None:
    """
    Convert `image_path` to JPG (if needed) and stash it under
    mielenosoitukset_fi/static/images/<hash>/<image_type>-<id>.jpg.

    Returns a web-friendly relative path, e.g. "/static/images/UPL/upload-42.jpg".
    """
    _id = generate_next_id(image_type)
    if _id is None:
        logger.error("Failed to generate next ID.")
        return None

    # 1. Temp JPG in /uploads
    temp_jpg = os.path.join(_upload_folder, f"{image_type}-{_id}.jpg")
    converted = convert_to_jpg(image_path, temp_jpg)
    if not converted:
        logger.error("Image conversion failed.")
        return None

    # 2. Final destination
    rel_dir = os.path.join(gen_ha(image_type))
    rel_name = f"{image_type}-{_id}.jpg"
    rel_path = os.path.join(rel_dir, rel_name)          # UPL/upload-42.jpg
    abs_path = os.path.join(_LOCAL_STORAGE_ROOT, rel_path)

    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    shutil.move(converted, abs_path)
    logger.info(f"Image saved locally at {abs_path}")

    # 3. Return the public path (tweak to fit your routing)
    return f"/static/images/{rel_path.replace(os.sep, '/')}"

