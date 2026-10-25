import os
import uuid
import logging
import boto3
from botocore.exceptions import ClientError, EndpointConnectionError
from app.core.config import settings

logger = logging.getLogger(__name__)

class CloudStorageService:
    """
    Cloud Storage Abstraction supporting S3 and MinIO with local disk fallback.
    Folder structure:
      invoices/pending/
      invoices/processed/
      invoices/flagged/
    """

    def __init__(self):
        self.bucket_name = settings.S3_BUCKET_NAME
        self.local_dir = settings.LOCAL_STORAGE_DIR
        os.makedirs(self.local_dir, exist_ok=True)
        for sub in ["pending", "processed", "flagged"]:
            os.makedirs(os.path.join(self.local_dir, "invoices", sub), exist_ok=True)

        self._s3_client = None
        self._s3_available = False
        self._init_s3()

    def _init_s3(self):
        try:
            from botocore.config import Config
            fast_config = Config(connect_timeout=1, read_timeout=1, retries={'max_attempts': 0})
            client = boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT_URL,
                aws_access_key_id=settings.S3_ACCESS_KEY_ID,
                aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
                region_name=settings.S3_REGION,
                use_ssl=settings.S3_USE_SSL,
                config=fast_config
            )
            # Check or create bucket
            try:
                client.head_bucket(Bucket=self.bucket_name)
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code")
                if error_code in ["404", "NoSuchBucket"]:
                    client.create_bucket(Bucket=self.bucket_name)
                    logger.info(f"Created S3/MinIO bucket: {self.bucket_name}")
            self._s3_client = client
            self._s3_available = True
            logger.info(f"S3/MinIO cloud storage connected: {settings.S3_ENDPOINT_URL}")
        except Exception as e:
            logger.info(f"S3/MinIO not accessible ({e}). Running with local storage fallback.")
            self._s3_available = False

    def upload_file(self, file_bytes: bytes, original_filename: str, folder: str = "pending") -> str:
        """
        Upload file to cloud storage (or local fallback).
        Returns the storage path key, e.g., 'invoices/pending/uuid_filename.pdf'.
        """
        ext = os.path.splitext(original_filename)[1]
        unique_name = f"{uuid.uuid4().hex}{ext}"
        object_key = f"invoices/{folder}/{unique_name}"

        if self._s3_available and self._s3_client:
            try:
                self._s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=object_key,
                    Body=file_bytes,
                    Metadata={"original_filename": original_filename}
                )
                return object_key
            except (EndpointConnectionError, ClientError) as e:
                logger.warning(f"S3 upload failed ({e}), writing to local disk fallback.")
                self._s3_available = False

        # Local storage fallback
        local_path = os.path.join(self.local_dir, object_key.replace("/", os.sep))
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(file_bytes)
        return object_key

    def get_file(self, object_key: str) -> bytes:
        """Retrieve file content bytes from S3 or local storage."""
        if self._s3_available and self._s3_client:
            try:
                response = self._s3_client.get_object(Bucket=self.bucket_name, Key=object_key)
                return response["Body"].read()
            except Exception as e:
                logger.warning(f"S3 get_object failed ({e}), checking local disk.")

        local_path = os.path.join(self.local_dir, object_key.replace("/", os.sep))
        if os.path.exists(local_path):
            with open(local_path, "rb") as f:
                return f.read()
        raise FileNotFoundError(f"File not found in cloud or local storage: {object_key}")

    def move_file(self, object_key: str, destination_folder: str) -> str:
        """
        Move file from its current folder to another (e.g. pending -> processed or flagged).
        """
        parts = object_key.split("/")
        filename = parts[-1]
        new_key = f"invoices/{destination_folder}/{filename}"

        if self._s3_available and self._s3_client:
            try:
                # Copy then delete
                self._s3_client.copy_object(
                    Bucket=self.bucket_name,
                    CopySource={"Bucket": self.bucket_name, "Key": object_key},
                    Key=new_key
                )
                self._s3_client.delete_object(Bucket=self.bucket_name, Key=object_key)
                return new_key
            except Exception as e:
                logger.warning(f"S3 move failed ({e}), falling back to local move.")

        # Local file move
        old_local = os.path.join(self.local_dir, object_key.replace("/", os.sep))
        new_local = os.path.join(self.local_dir, new_key.replace("/", os.sep))
        if os.path.exists(old_local):
            os.makedirs(os.path.dirname(new_local), exist_ok=True)
            os.replace(old_local, new_local)
        return new_key

cloud_storage_service = CloudStorageService()
