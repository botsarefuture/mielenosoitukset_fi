import os
from PIL import Image
from config import Config  # Import your Config class
from mielenosoitukset_fi.utils.logger import logger
import time
from mielenosoitukset_fi.database_manager import DatabaseManager

# Constants
db_manager = DatabaseManager().get_instance()
mongo = db_manager.get_db()

_max_retries = 3
_retry_delay = 2  # Initial delay in seconds

# _self_path is not used, so it has been removed

# one level down and then up to uploads
_upload_folder = os.path.join("mielenosoitukset_fi", "uploads")
print(_upload_folder)


def get_id_and_add_one(hash):
    """
    Get the last ID from the database and increment it by one.

    Parameters
    ----------
    hash : str
        The hash to use as a prefix for the ID.

    Returns
    -------
    int
        The next ID.
    """
    last_id = mongo.s3_ids.find_one_and_update(
        {"hash": hash},
        {"$inc": {"last_id": 1}},
        upsert=True,
        return_document=True,
    )
    return last_id["last_id"]


def retry_with_graze(max_retries=_max_retries, delay=_retry_delay):
    """
    Decorator to retry a function with exponential backoff and a graze handler.

    Parameters
    ----------
    max_retries : int, optional
        Maximum number of retries (default is _max_retries).
    delay : int, optional
        Initial delay between retries in seconds (default is _retry_delay).

    Returns
    -------
    function
        The decorated function with retry logic.
    """

    def decorator(func):
        """
        Inner decorator function.

        Parameters
        ----------
        func : function
            The function to be decorated.

        Returns
        -------
        function
            The wrapped function with retry logic.
        """

        def wrapper(*args, **kwargs):
            """
            Wrapper function to apply retry logic.

            Parameters
            ----------
            *args : tuple
                Positional arguments for the decorated function.
            **kwargs : dict
                Keyword arguments for the decorated function.

            Returns
            -------
            Any
                The return value of the decorated function or None if all retries fail.
            """
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries < max_retries:
                        logger.warning(
                            f"Retry {retries}/{max_retries} after error: {e}"
                        )
                        time.sleep(delay * (2 ** (retries - 1)))  # Exponential backoff
                    else:
                        logger.info(
                            f"Well, grazed it. {func.__name__} didn’t succeed, moving on."
                        )
                        return None  # Handle the graze and move on

        return wrapper

    return decorator


@retry_with_graze()
def convert_to_jpg(image_path: str, output_path: str) -> str:
    """
    Convert an image to JPEG format and save it locally.

    Parameters
    ----------
    image_path : str
        Path to the input image.
    output_path : str
        Path to save the converted JPEG image.

    Returns
    -------
    str or None
        Path to the converted JPEG image or None if conversion fails.
    """
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB")  # Ensure it's in RGB mode
            img.save(output_path, "JPEG")
        logger.info(f"Image converted to JPEG: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Error converting image {image_path}: {e}")
        return None


@retry_with_graze()
def generate_next_id(image_type: str = "upload") -> int:
    """
    Generate the next ID by checking the current objects in the S3 bucket.

    Parameters
    ----------
    image_type : str
        Type of the image (used as a prefix).

    Returns
    -------
    int or None
        The next ID or None if an error occurs.
    """
    return get_id_and_add_one(gen_ha(image_type))

def generate_next_id_local(image_type: str = "upload") -> int:
    """
    Generate the next ID by checking the local uploads folder for the image type.

    Parameters
    ----------
    image_type : str
        Type of the image (used as a prefix).

    Returns
    -------
    int or None
        The next ID or None if an error occurs.
    """
    subfolder = os.path.join(_upload_folder, gen_ha(image_type))
    if not os.path.exists(subfolder):
        return 1
    files = [f for f in os.listdir(subfolder) if f.startswith(f"{image_type}-") and f.endswith(".jpg")]
    ids = []
    for fname in files:
        try:
            num = int(fname.replace(f"{image_type}-", "").replace(".jpg", ""))
            ids.append(num)
        except Exception:
            continue
    return max(ids) + 1 if ids else 1


def upload_path_gen(_id: str, image_type: str) -> str:
    """
    Generate the path for the uploaded image.

    Parameters
    ----------
    _id : str
        The ID of the image.
    image_type : str
        Type of the image (used as a prefix).

    Returns
    -------
    str
        The path for the uploaded image.
    """

    return f"{gen_ha(image_type)}/{image_type}-{_id}.jpg"


def gen_ha(image_type):
    """
    Generate a 3-letter uppercase hash for the image type.

    Parameters
    ----------
    image_type : str
        Type of the image.

    Returns
    -------
    str
        The 3-letter uppercase hash.
    """
    return image_type[:3].upper()


@retry_with_graze()
def upload_image(bucket_name: str, image_path: str, image_type: str) -> str:
    """
    Save an image locally in the uploads folder.

    Parameters
    ----------
    bucket_name : str
        Unused. Kept for compatibility.
    image_path : str
        Path to the input image.
    image_type : str
        Type of the image (used as a prefix).

    Returns
    -------
    str or None
        Local path of the saved image or None if saving fails.
    """
    _id = generate_next_id_local(image_type)
    if _id is None:
        logger.error("Failed to generate next ID.")
        return ""

    # Ensure uploads subfolder exists
    subfolder = os.path.join(_upload_folder, gen_ha(image_type))
    os.makedirs(subfolder, exist_ok=True)

    jpg_image_path = os.path.join(subfolder, f"{image_type}-{_id}.jpg").replace("mielenosoitukset_fi/", "")
    output_image_path = convert_to_jpg(image_path, jpg_image_path)

    if output_image_path is None:
        logger.error("Failed to convert image.")
        return ""

    logger.info(f"Image saved locally: {output_image_path}")
    return output_image_path
