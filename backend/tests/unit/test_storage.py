import pytest
from pathlib import Path

from app.rag.storage.base import (
    sanitize_filename,
    compute_sha256,
    MAX_FILE_SIZE_BYTES,
)
from app.rag.storage.local_storage import LocalStorageService
from app.rag.storage.s3_storage import S3StorageService
from app.rag.storage import get_storage_service


def test_sanitize_filename():
    assert sanitize_filename("simple_doc.pdf") == "simple_doc.pdf"
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("..\\..\\Windows\\System32\\cmd.exe") == "cmd.exe"
    assert sanitize_filename("Báo cáo & doanh thu (2026).pdf") == "Bao_cao_doanh_thu_2026_.pdf"
    assert sanitize_filename(".hidden_file") == "document_hidden_file"
    assert sanitize_filename("") == "document"


def test_compute_sha256():
    data = b"ERP AI Copilot test content"
    hash1 = compute_sha256(data)
    hash2 = compute_sha256(data)
    assert len(hash1) == 64
    assert hash1 == hash2

    different_data = b"Different content"
    assert compute_sha256(different_data) != hash1


def test_validation_rules(tmp_path: Path):
    storage = LocalStorageService(base_dir=tmp_path)

    # Empty file
    with pytest.raises(ValueError, match="empty"):
        storage.upload_file(b"", "empty.txt")

    # Oversized file (> 20MB)
    fake_huge_data = b"x" * (MAX_FILE_SIZE_BYTES + 10)
    with pytest.raises(ValueError, match="exceeds"):
        storage.upload_file(fake_huge_data, "huge.txt")

    # Unsupported extension
    with pytest.raises(ValueError, match="Unsupported"):
        storage.upload_file(b"some binary", "malware.exe", mime_type="application/x-msdownload")


def test_local_storage_lifecycle(tmp_path: Path):
    storage = LocalStorageService(base_dir=tmp_path)
    content = b"Noi dung chinh sach ban hang va bao hanh 2026"
    filename = "chinh_sach_2026.txt"

    # 1. Upload
    storage_key, checksum = storage.upload_file(content, filename, mime_type="text/plain")
    assert storage_key.startswith("documents/")
    assert checksum == compute_sha256(content)

    # 2. Exists
    assert storage.file_exists(storage_key) is True
    assert storage.file_exists("documents/non_existent.txt") is False

    # 3. Download
    downloaded = storage.download_file(storage_key)
    assert downloaded == content

    # 4. Presigned URL representation
    url = storage.get_presigned_url(storage_key)
    assert url is not None
    assert storage_key in url

    # 5. Delete
    deleted = storage.delete_file(storage_key)
    assert deleted is True
    assert storage.file_exists(storage_key) is False


def test_s3_storage_minio_lifecycle():
    """
    Test real MinIO S3 integration against the running docker container on port 9000.
    """
    s3_storage = S3StorageService(
        endpoint_url="http://localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket_name="erp-documents-test",
        region_name="us-east-1",
    )

    content = b"%PDF-1.4 Sample PDF content for ERP Copilot testing"
    filename = "tai_lieu_mau.pdf"

    # 1. Upload
    storage_key, checksum = s3_storage.upload_file(
        content=content,
        filename=filename,
        mime_type="application/pdf",
    )
    assert storage_key.startswith("documents/")
    assert checksum == compute_sha256(content)

    # 2. Exists
    assert s3_storage.file_exists(storage_key) is True
    assert s3_storage.file_exists("documents/non_existent_key.pdf") is False

    # 3. Download
    downloaded = s3_storage.download_file(storage_key)
    assert downloaded == content

    # 4. Presigned URL
    presigned_url = s3_storage.get_presigned_url(storage_key, expires_in=1800)
    assert presigned_url is not None
    assert "erp-documents-test" in presigned_url
    assert "AWSAccessKeyId" in presigned_url or "X-Amz-Algorithm" in presigned_url

    # 5. Delete
    deleted = s3_storage.delete_file(storage_key)
    assert deleted is True
    assert s3_storage.file_exists(storage_key) is False


def test_storage_factory_resolves():
    service = get_storage_service()
    assert isinstance(service, S3StorageService)
    assert service.bucket_name == "erp-documents"
