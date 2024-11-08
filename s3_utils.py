import os
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from PIL import Image
from config import Config  # Import your Config class
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 2  # Initial delay in seconds

# Initialize the S3 client with configuration
def create_s3_client():
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

s3_client = create_s3_client()

# Retry decorator with a "graze" handler if all retries fail
def retry_with_graze(max_retries=MAX_RETRIES, delay=RETRY_DELAY):
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
                        time.sleep(delay * (2 ** (retries - 1)))  # Exponential backoff
                    else:
                        logger.info(f"Well, grazed it. {func.__name__} didn’t succeed, moving on.")
                        return None  # Handle the graze and move on
        return wrapper
    return decorator

# Convert image to JPEG and save locally
@retry_with_graze()
def convert_to_jpg(image_path: str, output_path: str) -> str:
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB")  # Ensure it's in RGB mode
            img.save(output_path, "JPEG")
        logger.info(f"Image converted to JPEG: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Error converting image {image_path}: {e}")
        return None

# Generate the next ID by checking the current objects in the bucket
@retry_with_graze()
def generate_next_id(bucket_name: str, image_type: str) -> int:
    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=image_type)
        ids = [
            int(obj["Key"].split("-")[-1].split(".")[0])
            for obj in response.get("Contents", [])
            if "-" in obj["Key"] and obj["Key"].split("-")[-1].split(".")[0].isdigit()
        ]
        next_id = max(ids, default=0) + 1
        logger.info(f"Generated next ID: {next_id} for image type: {image_type}")
        return next_id
    except Exception as e:
        logger.error(f"Error generating next ID for bucket '{bucket_name}': {e}")
        return None

# Upload the image to a bucket with retry logic
@retry_with_graze()
def upload_image(bucket_name: str, image_path: str, image_type: str) -> str:
    _id = generate_next_id(bucket_name, image_type)
    if _id is None:
        logger.error("Failed to generate next ID.")
        return None

    jpg_image_path = f"temps/{image_type}-{_id}.jpg"
    output_image_path = convert_to_jpg(image_path, jpg_image_path)

    if output_image_path is None:
        logger.error("Failed to convert image.")
        return None

    try:
        s3_client.upload_file(output_image_path, bucket_name, jpg_image_path)
        logger.info(f"{jpg_image_path} uploaded successfully to {bucket_name}.")
        os.remove(output_image_path)  # Remove the converted file
        s3_file_path = f"{Config.ENDPOINT_URL}/{bucket_name}/{jpg_image_path}"
        return s3_file_path
    except ClientError as e:
        logger.error(f"Error uploading image to bucket '{bucket_name}': {e}")
        return None

#upload_image("mielenosoitukset_fi1", "default-pfp.jpg", "jpg")