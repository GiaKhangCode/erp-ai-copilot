import json
import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


async def get_auth_headers(client: AsyncClient, email: str, password: str) -> dict:
    """Helper đăng nhập lấy Bearer token headers"""
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_openapi_schema_contains_document_ai_endpoints():
    """Kiểm tra OpenAPI schema đăng ký đầy đủ các endpoints của Document AI & Approvals."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/openapi.json")
        assert res.status_code == 200
        paths = res.json()["paths"]
        assert "/api/v1/orders/ingest-text" in paths
        assert "/api/v1/orders/ingest-email" in paths
        assert "/api/v1/orders/ingest-document" in paths
        assert "/api/v1/approvals" in paths
        assert "/api/v1/approvals/{approval_id}" in paths
        assert "/api/v1/approvals/{approval_id}/approve" in paths
        assert "/api/v1/approvals/{approval_id}/reject" in paths


@pytest.mark.asyncio
async def test_ingest_order_from_text_and_approval_lifecycle():
    """
    Kiểm thử vòng đời hoàn chỉnh:
    1. Sales rep gửi văn bản email đặt hàng cho khách CUS-0001 (mua 2 cái SKU-001).
    2. API ingest-text bóc tách, đối chiếu ERP và tạo draft order + pending approval.
    3. Kiểm tra Approval Inbox thấy yêu cầu mới.
    4. Sales rep (không có quyền) thử approve -> bị từ chối 403 Forbidden.
    5. Admin (có quyền) approve -> thành công, đơn hàng chuyển sang 'confirmed'.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sales_headers = await get_auth_headers(client, "sales@erpcopilot.vn", "sales123")
        admin_headers = await get_auth_headers(client, "admin@erpcopilot.vn", "admin123")

        # 1. Ingest từ text
        order_text = (
            "Kính gửi ERP Copilot,\n"
            "Công ty TNHH Công Nghệ Á Châu (Mã KH: CUS-0001)\n"
            "Chúng tôi muốn đặt 2 cái Laptop Pro 14 M3 (Mã: SKU-001)\n"
            "Giao hàng trước ngày 2026-10-31."
        )

        res_ingest = await client.post(
            "/api/v1/orders/ingest-text",
            json={"text": order_text, "source_identifier": "test_text_order"},
            headers=sales_headers,
        )
        assert res_ingest.status_code == 200
        data = res_ingest.json()

        assert data["resolved_customer_code"] == "CUS-0001"
        assert len(data["resolved_items"]) == 1
        assert data["resolved_items"][0]["sku"] == "SKU-001"
        assert data["resolved_items"][0]["quantity"] == 2
        assert float(data["total_amount"]) == 57000000.0  # 2 * 28,500,000 VND
        assert data["draft_order_id"] is not None
        assert data["approval_request_id"] is not None

        approval_id = data["approval_request_id"]
        order_id = data["draft_order_id"]

        # 2. Xem chi tiết Approval
        res_detail = await client.get(f"/api/v1/approvals/{approval_id}", headers=sales_headers)
        assert res_detail.status_code == 200
        detail_data = res_detail.json()
        assert detail_data["status"] == "pending"
        assert detail_data["payload"]["order_id"] == order_id

        # 3. RBAC: Sales rep không được phép approve
        res_unauthorized = await client.post(
            f"/api/v1/approvals/{approval_id}/approve",
            headers=sales_headers,
        )
        assert res_unauthorized.status_code == 403  # Forbidden

        # 4. Admin approve thành công
        res_approve = await client.post(
            f"/api/v1/approvals/{approval_id}/approve",
            headers=admin_headers,
        )
        assert res_approve.status_code == 200
        approve_data = res_approve.json()
        assert approve_data["status"] == "confirmed"

        # 5. Kiểm tra đơn hàng trong DB đã sang confirmed
        res_order = await client.get(f"/api/v1/sales-orders/{order_id}", headers=sales_headers)
        assert res_order.status_code == 200
        assert res_order.json()["status"] == "confirmed"


@pytest.mark.asyncio
async def test_reject_approval_workflow():
    """Kiểm thử quy trình từ chối phê duyệt đơn hàng nháp."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sales_headers = await get_auth_headers(client, "sales@erpcopilot.vn", "sales123")
        admin_headers = await get_auth_headers(client, "admin@erpcopilot.vn", "admin123")

        order_text = "Đặt 1 cái SKU-001 cho khách CUS-0001"
        res_ingest = await client.post(
            "/api/v1/orders/ingest-text",
            json={"text": order_text},
            headers=sales_headers,
        )
        approval_id = res_ingest.json()["approval_request_id"]

        # Admin từ chối
        res_reject = await client.post(
            f"/api/v1/approvals/{approval_id}/reject",
            json={"reason": "Khách hàng còn nợ quá hạn."},
            headers=admin_headers,
        )
        assert res_reject.status_code == 200
        assert res_reject.json()["status"] == "rejected"
        assert res_reject.json()["reason"] == "Khách hàng còn nợ quá hạn."
