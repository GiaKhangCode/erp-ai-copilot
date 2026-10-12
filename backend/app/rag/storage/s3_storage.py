import logging
from typing import Optional, Tuple
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.rag.storage.base import (
    BaseStorageService,
    compute_sha256,
    sanitize_filename,
)

logger = logging.getLogger(__name__)


class S3StorageService(BaseStorageService):
    """
    S3-compatible Object Storage implementation using boto3.
    Compatible with MinIO, AWS S3, Cloudflare R2, Ceph, etc.
    """

    def __init__(
        self,
        endpoint_url: Optional[str] = "http://localhost:9000",
        access_key: Optional[str] = "minioadmin",
        secret_key: Optional[str] = "minioadmin",
        bucket_name: str = "erp-documents",
        region_name: str = "us-east-1",
    ):
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket_name = bucket_name
        self.region_name = region_name

        # Configure boto3 client with path-style addressing (required for MinIO)
        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region_name,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        )

        self.ensure_bucket_exists()

    def ensure_bucket_exists(self) -> None:
        """Create bucket if it does not already exist."""
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
            logger.info("Storage bucket '%s' exists and is accessible.", self.bucket_name)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            # 404 or NoSuchBucket
            if error_code in ("404", "NoSuchBucket"):
                logger.info("Bucket '%s' not found. Creating bucket...", self.bucket_name)
                try:
                    if self.region_name == "us-east-1":
                        self.client.create_bucket(Bucket=self.bucket_name)
                    else:
                        self.client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={"LocationConstraint": self.region_name},
                        )
                    logger.info("Bucket '%s' created successfully.", self.bucket_name)
                except ClientError as create_err:
                    logger.error("Failed to create bucket '%s': %s", self.bucket_name, create_err)
                    raise
            else:
                logger.error("Error inspecting bucket '%s': %s", self.bucket_name, e)
                raise

    def upload_file(
        self,
        content: bytes,
        filename: str,
        mime_type: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Upload binary file content to S3/MinIO bucket.
        Returns:
            Tuple[str, str]: (storage_key, sha256_checksum)
        """
        self.validate_file(content, filename, mime_type)
        checksum = compute_sha256(content)
        clean_name = sanitize_filename(filename)
        storage_key = self.generate_storage_key(filename)

        content_type = mime_type or "application/octet-stream"

        try:
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=storage_key,
                Body=content,
                ContentType=content_type,
                Metadata={
                    "checksum": checksum,
                    "original_filename": clean_name,
                },
            )
            logger.info("Uploaded file '%s' to S3 key '%s' (checksum: %s)", filename, storage_key, checksum)
            return storage_key, checksum
        except ClientError as e:
            logger.error("Failed to upload '%s' to S3: %s", filename, e)
            raise IOError(f"Storage upload failed: {e}") from e

    def download_file(self, storage_key: str) -> bytes:
        """Download file content from S3/MinIO."""
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=storage_key)
            return response["Body"].read()
        except ClientError as e:
            logger.error("Failed to download key '%s' from S3: %s", storage_key, e)
            raise FileNotFoundError(f"Storage object not found: {storage_key}") from e

    def delete_file(self, storage_key: str) -> bool:
        """Delete file object from S3/MinIO."""
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=storage_key)
            logger.info("Deleted S3 object '%s'", storage_key)
            return True
        except ClientError as e:
            logger.error("Failed to delete key '%s' from S3: %s", storage_key, e)
            return False

    def file_exists(self, storage_key: str) -> bool:
        """Check if file object exists in S3/MinIO."""
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=storage_key)
            return True
        except ClientError:
            return False

    def get_presigned_url(self, storage_key: str, expires_in: int = 3600) -> Optional[str]:
        """Generate a temporary presigned URL for secure document download."""
        try:
            url = self.client.generate_presigned_url(
                ClientMethod="get_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": storage_key,
                },
                ExpiresIn=expires_in,
            )
            return url
        except ClientError as e:
            logger.error("Failed to generate presigned URL for key '%s': %s", storage_key, e)
            return None
