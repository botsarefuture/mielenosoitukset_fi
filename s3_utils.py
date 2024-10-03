import os
import boto3
from botocore.exceptions import NoCredentialsError
from PIL import Image

# Credentials
access_key = 'UK274ZY9J27MTRSORF5U' # TODO: Move these to config
secret_key = 'WWiAnM7svI3hCvmcVvNipFe8SkB6dRYOCQ5SFmZL'  # TODO: Move these to config
endpoint_url = 'https://fsn1.your-objectstorage.com'  # Replace with your Hetzner endpoint

# Create the S3 client
s3_client = boto3.client('s3',
                         aws_access_key_id=access_key,
                         aws_secret_access_key=secret_key,
                         endpoint_url=endpoint_url)

# Convert image to JPEG and save locally
def convert_to_jpg(image_path, output_path):
    try:
        with Image.open(image_path) as img:
            img = img.convert('RGB')  # Ensure it's in RGB mode
            img.save(output_path, 'JPEG')
        return output_path
    except Exception as e:
        print(f"Error converting image: {e}")
        return None

# Generate the next ID by checking the current objects in the bucket
def generate_next_id(bucket_name, image_type):
    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=image_type)
        ids = []
        if 'Contents' in response:
            for obj in response['Contents']:
                key = obj['Key']
                try:
                    file_id = int(key.split('-')[-1].split('.')[0])
                    ids.append(file_id)
                except (IndexError, ValueError):
                    pass

        next_id = max(ids) + 1 if ids else 1
        return next_id
    except Exception as e:
        print(f"Error generating next ID: {e}")
        return None

# Upload the image to a bucket
def upload_image(bucket_name, image_path, image_type):
    _id = generate_next_id(bucket_name, image_type)

    if _id is None:
        print("Failed to generate next ID.")
        return None

    jpg_image_path = f"temps/{image_type}-{_id}.jpg"
    output_image_path = convert_to_jpg(image_path, jpg_image_path)

    if output_image_path is None:
        print("Failed to convert image.")
        return None

    try:
        s3_client.upload_file(output_image_path, bucket_name, jpg_image_path)
        print(f"{jpg_image_path} uploaded successfully to {bucket_name}.")
        
        os.remove(jpg_image_path)

        s3_file_path = f"{endpoint_url}/{bucket_name}/{jpg_image_path}"
        return s3_file_path
    except Exception as e:
        print(f"Error uploading image: {e}")
        return None
