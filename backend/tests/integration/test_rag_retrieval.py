import io
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


async def get_auth_headers(client: AsyncClient, email: str, password: str) -> dict:
    """Helper to authenticate and obtain Bearer token."""
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def policy_doc_content() -> bytes:
    return b"""# CHINH SACH DOI TRA VA BAO HANH ERP 2026

## 1. Thoi han doi tra hang
Khach hang duoc quyen doi tra hang trong vong 07 ngay ke tu ngay nhan hang thuc te.
Cac san pham ap dung chinh sach bao gom ma SKU-001 (Laptop Pro) va SKU-002 (Man hinh Dell).

## 2. Ty le hoan tien theo thoi gian
- Trong 3 ngay dau tien: Hoan tien 100% gia tri don hang.
- Tu ngay thu 4 den ngay thu 7: Hoan tien 90% gia tri don hang.

## 3. Dieu kien bao hanh
Thoi han bao hanh thiet bi phan cung la 24 thang theo tieu chuan nha san xuat.
"""


@pytest.fixture
def admin_secret_doc_content() -> bytes:
    return b"""# QUY CHE LUONG THUONG BAN GIAM DOC NAM 2026

## 1. Muc thuong quy dac biet
Muc thuong quy cua ban giam doc la 15% loi nhuan sau thue cua quy do.
Chi quan tri vien cap cao (role:admin) moi co tham quyen phe duyet muc thuong nay.
Chinh sach nay la toi mat, khong tiet lo cho nhan vien ban hang.
"""


@pytest.mark.asyncio
async def test_rag_end_to_end_retrieval_and_qa_lifecycle(
    policy_doc_content: bytes,
    admin_secret_doc_content: bytes,
):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_headers = await get_auth_headers(client, "admin@erpcopilot.vn", "admin123")
        sales_headers = await get_auth_headers(client, "sales@erpcopilot.vn", "sales123")

        # =====================================================================
        # 1. SETUP: Upload 2 documents (1 internal policy, 1 admin-only confidential)
        # =====================================================================
        # Doc 1: Internal policy
        doc1_files = {
            "file": ("chinh_sach_doi_tra_2026.md", io.BytesIO(policy_doc_content), "text/markdown"),
        }
        doc1_res = await client.post(
            "/api/v1/documents/upload",
            files=doc1_files,
            data={"access_scope": "internal"},
            headers=admin_headers,
        )
        assert doc1_res.status_code == 201
        doc1_id = doc1_res.json()["id"]

        # Doc 2: Admin confidential
        doc2_files = {
            "file": ("quy_che_thuong_ban_giam_doc.md", io.BytesIO(admin_secret_doc_content), "text/markdown"),
        }
        doc2_res = await client.post(
            "/api/v1/documents/upload",
            files=doc2_files,
            data={"access_scope": "role:admin"},
            headers=admin_headers,
        )
        assert doc2_res.status_code == 201
        doc2_id = doc2_res.json()["id"]

        try:
            # =====================================================================
            # 2. TEST CASE 1: Hybrid Search (Vector + Keyword FTS)
            # =====================================================================
            search_res = await client.post(
                "/api/v1/rag/search",
                json={"query": "Thời gian đổi trả hàng cho mã SKU-001", "top_k": 5},
                headers=sales_headers,
            )
            assert search_res.status_code == 200
            search_data = search_res.json()
            assert search_data["total_retrieved"] >= 1
            top_chunk = search_data["chunks"][0]
            assert top_chunk["filename"] == "chinh_sach_doi_tra_2026.md"
            assert top_chunk["score"] > 0
            assert "07 ngay" in top_chunk["content"] or "07 ngày" in top_chunk["content"]

            # =====================================================================
            # 3. TEST CASE 2: Strict ACL Isolation (Sales Rep vs Admin)
            # =====================================================================
            # A) Sales Rep searches for confidential info -> 0 confidential chunks
            sales_secret_search = await client.post(
                "/api/v1/rag/search",
                json={"query": "mức thưởng quý của ban giám đốc", "top_k": 5},
                headers=sales_headers,
            )
            assert sales_secret_search.status_code == 200
            sales_search_data = sales_secret_search.json()
            confidential_chunks_sales = [
                c for c in sales_search_data["chunks"]
                if c["filename"] == "quy_che_thuong_ban_giam_doc.md"
            ]
            assert len(confidential_chunks_sales) == 0

            # B) Sales Rep asks confidential question -> Short-circuit Abstention
            sales_secret_ask = await client.post(
                "/api/v1/rag/ask",
                json={"query": "Mức thưởng quý của ban giám đốc là bao nhiêu %?", "top_k": 5},
                headers=sales_headers,
            )
            assert sales_secret_ask.status_code == 200
            sales_ask_data = sales_secret_ask.json()
            assert sales_ask_data["has_sufficient_context"] is False
            assert "không tìm thấy thông tin" in sales_ask_data["answer"]
            assert len(sales_ask_data["citations"]) == 0

            # C) Admin searches for confidential info -> MUST see confidential chunk
            admin_secret_search = await client.post(
                "/api/v1/rag/search",
                json={"query": "mức thưởng quý của ban giám đốc", "top_k": 5},
                headers=admin_headers,
            )
            assert admin_secret_search.status_code == 200
            admin_search_data = admin_secret_search.json()
            confidential_chunks_admin = [
                c for c in admin_search_data["chunks"]
                if c["filename"] == "quy_che_thuong_ban_giam_doc.md"
            ]
            assert len(confidential_chunks_admin) >= 1

            # =====================================================================
            # 4. TEST CASE 3: Grounded Q&A with Gemini (In-Domain with Citation)
            # =====================================================================
            live_ask_res = await client.post(
                "/api/v1/rag/ask",
                json={
                    "query": "Khách hàng được đổi trả hàng trong mấy ngày và tỷ lệ hoàn tiền trong 3 ngày đầu là bao nhiêu?",
                    "top_k": 3,
                },
                headers=sales_headers,
            )
            assert live_ask_res.status_code == 200
            live_ask_data = live_ask_res.json()
            assert live_ask_data["has_sufficient_context"] is True
            # Answer should ground on the policy numbers (07/7 days, 100%)
            answer_text = live_ask_data["answer"]
            assert "7" in answer_text or "07" in answer_text
            assert "100" in answer_text
            # Citations must be provided and ground on chinh_sach_doi_tra_2026.md
            assert len(live_ask_data["citations"]) >= 1
            citation = live_ask_data["citations"][0]
            assert citation["filename"] == "chinh_sach_doi_tra_2026.md"
            assert len(citation["quote"]) > 0

            # =====================================================================
            # 5. TEST CASE 4: Out-of-Domain Abstention
            # =====================================================================
            out_of_domain_res = await client.post(
                "/api/v1/rag/ask",
                json={
                    "query": "Công thức hóa học của nước và định luật vạn vật hấp dẫn của Newton là gì?",
                    "top_k": 3,
                },
                headers=sales_headers,
            )
            assert out_of_domain_res.status_code == 200
            ood_data = out_of_domain_res.json()
            # Must either abstain via short-circuit or LLM explicit abstention
            assert ood_data["has_sufficient_context"] is False or "không tìm thấy" in ood_data["answer"].lower()
            assert len(ood_data["citations"]) == 0

        finally:
            # =====================================================================
            # CLEANUP: Delete created test documents
            # =====================================================================
            await client.delete(f"/api/v1/documents/{doc1_id}", headers=admin_headers)
            await client.delete(f"/api/v1/documents/{doc2_id}", headers=admin_headers)
