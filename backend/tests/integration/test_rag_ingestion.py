import io
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.main import app
from app.db.session import async_session_factory
from app.rag.models import Document, DocumentChunk


async def get_admin_auth_headers(client: AsyncClient) -> dict:
    """Helper to authenticate as admin and obtain Bearer token."""
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@erpcopilot.vn", "password": "admin123"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_upload_document_unauthorized():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("test.txt", io.BytesIO(b"Sample content"), "text/plain")}
        res = await client.post("/api/v1/documents/upload", files=files)
        assert res.status_code in [401, 403]


@pytest.mark.asyncio
async def test_document_ingestion_full_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        auth_headers = await get_admin_auth_headers(client)

        doc_content = b"""# CHINH SACH DOI TRA HANG HOA ERP 2026

## 1. Dieu kien doi tra
Khach hang duoc doi tra san pham trong vong 07 ngay ke tu ngay nhan hang.
San pham phai con nguyen tem mac va chua qua su dung.

## 2. Bang ty le hoan tien
| Thoi gian | Ty le hoan tien |
|---|---|
| Trong 3 ngay | 100% |
| Tu 4 den 7 ngay | 90% |
"""
        files = {
            "file": ("chinh_sach_doi_tra.md", io.BytesIO(doc_content), "text/markdown"),
        }
        data = {
            "access_scope": "internal",
        }

        # 1. Upload & Ingest
        upload_res = await client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
            headers=auth_headers,
        )
        assert upload_res.status_code == 201
        doc_data = upload_res.json()
        doc_id = doc_data["id"]

        assert doc_data["status"] == "indexed"
        assert doc_data["filename"] == "chinh_sach_doi_tra.md"
        assert doc_data["access_scope"] == "internal"
        assert doc_data["version"] == 1
        assert doc_data["chunk_count"] >= 2
        assert doc_data["download_url"] is not None

        # 2. Direct Database Vector Verification
        async with async_session_factory() as session:
            chunks_stmt = select(DocumentChunk).where(DocumentChunk.document_id == doc_id)
            chunks_res = await session.execute(chunks_stmt)
            db_chunks = list(chunks_res.scalars().all())

            assert len(db_chunks) >= 2
            for chunk in db_chunks:
                assert chunk.embedding is not None
                # Verify pgvector dimension 1536
                assert len(chunk.embedding) == 1536
                assert chunk.metadata_["filename"] == "chinh_sach_doi_tra.md"
                assert chunk.metadata_["access_scope"] == "internal"

        # 3. List Documents
        list_res = await client.get("/api/v1/documents", headers=auth_headers)
        assert list_res.status_code == 200
        list_data = list_res.json()
        assert list_data["total"] >= 1
        assert any(item["id"] == doc_id for item in list_data["items"])

        # 4. Get Document Detail
        detail_res = await client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers)
        assert detail_res.status_code == 200
        detail_data = detail_res.json()
        assert detail_data["id"] == doc_id
        assert len(detail_data["chunks"]) >= 2
        assert any("07 ngay" in c["content"] for c in detail_data["chunks"])

        # 5. Get Download URL
        url_res = await client.get(f"/api/v1/documents/{doc_id}/download-url", headers=auth_headers)
        assert url_res.status_code == 200
        url_data = url_res.json()
        assert "download_url" in url_data
        assert "erp-documents" in url_data["download_url"]

        # 6. Re-index Document
        reindex_res = await client.post(f"/api/v1/documents/{doc_id}/reindex", headers=auth_headers)
        assert reindex_res.status_code == 200
        reindex_data = reindex_res.json()
        assert reindex_data["status"] == "indexed"
        assert reindex_data["version"] == 2

        # 7. Delete Document
        del_res = await client.delete(f"/api/v1/documents/{doc_id}", headers=auth_headers)
        assert del_res.status_code == 200

        # Verify not found after deletion
        get_deleted_res = await client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers)
        assert get_deleted_res.status_code == 404

        # Verify cascade in DB
        async with async_session_factory() as session:
            chunks_after = await session.execute(
                select(DocumentChunk).where(DocumentChunk.document_id == doc_id)
            )
            assert len(list(chunks_after.scalars().all())) == 0
