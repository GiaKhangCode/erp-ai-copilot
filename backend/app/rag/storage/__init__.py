from functools import lru_cache

from app.core.config import get_settings
from app.rag.storage.base import (
    BaseStorageService,
    compute_sha256,
    sanitize_filename,
    MAX_FILE_SIZE_BYTES,
    ALLOWED_MIME_TYPES,
)
from app.rag.storage.s3_storage import S3StorageService
from app.rag.storage.local_storage import LocalStorageService


@lru_cache
def get_storage_service() -> BaseStorageService:
    """
    Factory dependency returning the active storage provider based on application settings.
    Default in production/staging: S3StorageService (MinIO / S3).
    Fallback for offline/dev: LocalStorageService.
    """
    settings = get_settings()
    if settings.STORAGE_TYPE == "s3":
        return S3StorageService(
            endpoint_url=settings.S3_ENDPOINT_URL,
            access_key=settings.S3_ACCESS_KEY,
            secret_key=settings.S3_SECRET_KEY,
            bucket_name=settings.S3_BUCKET_NAME,
            region_name=settings.S3_REGION,
        )
    return LocalStorageService(base_dir=settings.STORAGE_LOCAL_DIR)


__all__ = [
    "BaseStorageService",
    "S3StorageService",
    "LocalStorageService",
    "get_storage_service",
    "compute_sha256",
    "sanitize_filename",
    "MAX_FILE_SIZE_BYTES",
    "ALLOWED_MIME_TYPES",
]
