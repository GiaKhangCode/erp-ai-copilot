import abc
import hashlib
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple


# Maximum allowed upload size (20MB)
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024

# Allowed MIME types for ingestion
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
    "application/octet-stream",  # Fallback for some clients
}


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal attacks, special character exploits,
    and non-ASCII S3 header/URL encoding issues.
    """
    # Remove directory separators
    clean = filename.replace("\\", "/").split("/")[-1].strip()
    # Normalize unicode accents to ASCII (e.g. 'á' -> 'a')
    clean = unicodedata.normalize("NFKD", clean).encode("ascii", "ignore").decode("ascii")
    # Replace non-alphanumeric (except dot and dash) with underscores
    clean = re.sub(r"[^\w\.\-]", "_", clean)
    # Collapse multiple underscores
    clean = re.sub(r"_+", "_", clean)
    # Avoid empty filenames or filenames starting with dot
    if not clean or clean.startswith("."):
        clean = f"document_{clean.lstrip('.')}" if clean.lstrip(".") else "document"
    return clean


def compute_sha256(content: bytes) -> str:
    """Compute SHA-256 hex digest of file binary content."""
    hasher = hashlib.sha256()
    hasher.update(content)
    return hasher.hexdigest()


class BaseStorageService(abc.ABC):
    """
    Abstract interface for object storage operations.
    Follows Adapter Pattern to allow seamless switching between S3/MinIO and Local Storage.
    """

    def validate_file(self, content: bytes, filename: str, mime_type: Optional[str] = None) -> None:
        """Validate file size and MIME type before storage."""
        if len(content) == 0:
            raise ValueError("File content is empty")

        if len(content) > MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"File size ({len(content)} bytes) exceeds the maximum allowed limit of {MAX_FILE_SIZE_BYTES} bytes (20MB)"
            )

        if mime_type and mime_type.lower() not in ALLOWED_MIME_TYPES:
            # Check by extension as fallback
            lower_name = filename.lower()
            if not any(lower_name.endswith(ext) for ext in [".pdf", ".docx", ".txt", ".md"]):
                raise ValueError(f"Unsupported file type: {mime_type}")

    def generate_storage_key(self, filename: str) -> str:
        """Generate a hierarchical, non-colliding storage key (path)."""
        now = datetime.now(timezone.utc)
        clean_name = sanitize_filename(filename)
        unique_id = uuid.uuid4().hex[:12]
        return f"documents/{now.year}/{now.month:02d}/{unique_id}_{clean_name}"

    @abc.abstractmethod
    def upload_file(
        self,
        content: bytes,
        filename: str,
        mime_type: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Upload file content to storage.
        Returns:
            Tuple[str, str]: (storage_key, sha256_checksum)
        """
        pass

    @abc.abstractmethod
    def download_file(self, storage_key: str) -> bytes:
        """Download and return raw file bytes from storage."""
        pass

    @abc.abstractmethod
    def delete_file(self, storage_key: str) -> bool:
        """Delete file from storage. Returns True if deleted or did not exist."""
        pass

    @abc.abstractmethod
    def file_exists(self, storage_key: str) -> bool:
        """Check if file exists in storage."""
        pass

    @abc.abstractmethod
    def get_presigned_url(self, storage_key: str, expires_in: int = 3600) -> Optional[str]:
        """Generate a temporary presigned URL for downloading the file directly."""
        pass
