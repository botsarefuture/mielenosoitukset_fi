import os
import io
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
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
# keep _upload_folder for compatibility; new helpers avoid writing to disk


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


def create_s3_client():
    """
    Initialize and return an S3 client using the provided configuration.

    Returns
    -------
    boto3.client or None
        The initialized S3 client or None if credentials are not found.
    """
    try:
        return boto3.client(
            "s3",
            aws_access_key_id=Config.ACCESS_KEY,
            aws_secret_access_key=Config.SECRET_KEY,
            endpoint_url=Config.ENDPOINT_URL,
        )
    except NoCredentialsError:
        logger.error("AWS credentials not found.")
        return None


_s3_client = create_s3_client()


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


def convert_image_fileobj_to_jpeg_bytes(fileobj) -> bytes:
    """
    Convert an image file-like object to JPEG bytes in-memory.

    Parameters
    ----------
    fileobj : file-like
        File-like object containing the image data.

    Returns
    -------
    bytes or None
        JPEG-encoded image bytes, or None on error.
    """
    try:
        fileobj.seek(0)
        with Image.open(fileobj) as img:
            img = img.convert("RGB")
            out = io.BytesIO()
            img.save(out, format="JPEG")
            out.seek(0)
            return out.read()
    except Exception as e:
        logger.error(f"Error converting image from fileobj: {e}")
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


def upload_path_gen(_id, image_type: str) -> str:
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
    Upload an image to an S3 bucket with retry logic.

    Parameters
    ----------
    bucket_name : str
        Name of the S3 bucket.
    image_path : str
        Path to the input image.
    image_type : str
        Type of the image (used as a prefix).

    Returns
    -------
    str or None
        URL of the uploaded image or None if upload fails.
    """
    # Backwards-compatible wrapper that reads the local file into memory
    try:
        with open(image_path, "rb") as f:
            jpeg_bytes = convert_image_fileobj_to_jpeg_bytes(f)
            if jpeg_bytes is None:
                logger.error("Failed to convert image to JPEG bytes")
                return None
            _id = generate_next_id(image_type)
            if _id is None:
                logger.error("Failed to generate next ID.")
                return None
            object_key = upload_path_gen(_id, image_type)
            # Use put_object to upload bytes
            _s3_client.put_object(Bucket=bucket_name, Key=object_key, Body=jpeg_bytes, ContentType="image/jpeg")
            # Return canonical CDN URL as requested
            s3_file_path = f"https://cdn.mielenosoitukset.fi/{object_key}"
            logger.info(f"Uploaded {image_path} to s3://{bucket_name}/{object_key}")
            return s3_file_path
    except Exception as e:
        logger.error(f"Error uploading image to bucket '{bucket_name}': {e}")
        return None


@retry_with_graze()
def upload_image_fileobj(bucket_name: str, fileobj, filename: str, image_type: str) -> str:
    """
    Upload a file-like object (Flask FileStorage.stream or similar) to S3 after converting to JPEG in-memory.

    Parameters
    ----------
    bucket_name : str
    fileobj : file-like
    filename : str
        Original filename (used for logging).
    image_type : str

    Returns
    -------
    str or None
        Public URL of uploaded image or None on failure.
    """
    try:
        jpeg_bytes = convert_image_fileobj_to_jpeg_bytes(fileobj)
        if jpeg_bytes is None:
            logger.error("Conversion to JPEG failed for uploaded fileobj")
            return None
        _id = generate_next_id(image_type)
        if _id is None:
            logger.error("Failed to generate next ID.")
            return None
        object_key = upload_path_gen(_id, image_type)
        _s3_client.put_object(Bucket=bucket_name, Key=object_key, Body=jpeg_bytes, ContentType="image/jpeg")
        s3_file_path = f"https://cdn.mielenosoitukset.fi/{object_key}"
        logger.info(f"Uploaded in-memory file {filename} to s3://{bucket_name}/{object_key}")
        return s3_file_path
    except Exception as e:
        logger.error(f"Error uploading fileobj to S3: {e}")
        return None
