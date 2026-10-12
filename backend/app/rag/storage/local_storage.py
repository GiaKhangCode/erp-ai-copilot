import logging
from pathlib import Path
from typing import Optional, Tuple

from app.rag.storage.base import (
    BaseStorageService,
    compute_sha256,
)

logger = logging.getLogger(__name__)


class LocalStorageService(BaseStorageService):
    """
    Local filesystem storage provider (offline fallback & local testing).
    Saves files under configured directory with directory traversal protection.
    """

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = (base_dir or Path("./data/uploads")).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info("LocalStorage initialized at '%s'", self.base_dir)

    def _resolve_safe_path(self, storage_key: str) -> Path:
        """Ensure the target path does not escape base_dir."""
        target_path = (self.base_dir / storage_key).resolve()
        if not target_path.is_relative_to(self.base_dir):
            raise ValueError(f"Path traversal detected: {storage_key}")
        return target_path

    def upload_file(
        self,
        content: bytes,
        filename: str,
        mime_type: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Save file bytes to local directory."""
        self.validate_file(content, filename, mime_type)
        checksum = compute_sha256(content)
        storage_key = self.generate_storage_key(filename)
        target_path = self._resolve_safe_path(storage_key)

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(content)

        logger.info("Saved local file '%s' to '%s' (checksum: %s)", filename, target_path, checksum)
        return storage_key, checksum

    def download_file(self, storage_key: str) -> bytes:
        """Read file bytes from local disk."""
        target_path = self._resolve_safe_path(storage_key)
        if not target_path.is_file():
            raise FileNotFoundError(f"Local storage file not found: {storage_key}")
        return target_path.read_bytes()

    def delete_file(self, storage_key: str) -> bool:
        """Delete file from local disk."""
        try:
            target_path = self._resolve_safe_path(storage_key)
            if target_path.is_file():
                target_path.unlink()
                logger.info("Deleted local file '%s'", target_path)
            return True
        except Exception as e:
            logger.error("Failed to delete local file '%s': %s", storage_key, e)
            return False

    def file_exists(self, storage_key: str) -> bool:
        """Check if file exists on local disk."""
        try:
            target_path = self._resolve_safe_path(storage_key)
            return target_path.is_file()
        except Exception:
            return False

    def get_presigned_url(self, storage_key: str, expires_in: int = 3600) -> Optional[str]:
        """Local storage does not have presigned URLs; return API download endpoint relative path."""
        if self.file_exists(storage_key):
            return f"/api/v1/documents/raw/{storage_key}"
        return None
