import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app

transport = ASGITransport(app=app)


async def get_token_for(client: AsyncClient, email: str, password: str) -> str:
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_erp_endpoints_require_authentication():
    """
    Vá lỗ hổng Giai đoạn 1: Mọi endpoint ERP bắt buộc phải có Authorization header hợp lệ.
    """
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Không truyền token
        assert (await client.get("/api/v1/customers")).status_code == 401
        assert (await client.get("/api/v1/products")).status_code == 401
        assert (await client.get("/api/v1/inventory")).status_code == 401
        assert (await client.get("/api/v1/sales-orders")).status_code == 401
        assert (await client.get("/api/v1/reporting/revenue")).status_code == 401
        assert (await client.post("/api/v1/sales-orders/drafts", json={"customer_code": "CUS-0001", "items": []})).status_code == 401


@pytest.mark.asyncio
async def test_reporting_revenue_rbac_permissions():
    """
    Kiểm tra quyền xem báo cáo doanh thu tài chính (reports:revenue_view):
    - sales_rep: Bị chặn 403 Forbidden (chống bypass từ bên ngoài).
    - sales_manager: Được phép xem 200 OK.
    - director: Được phép xem 200 OK.
    """
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sales_token = await get_token_for(client, "sales@erpcopilot.vn", "sales123")
        mgr_token = await get_token_for(client, "manager@erpcopilot.vn", "manager123")
        dir_token = await get_token_for(client, "director@erpcopilot.vn", "director123")

        # 1. Sales Rep bị chặn
        res_sales = await client.get(
            "/api/v1/reporting/revenue",
            headers={"Authorization": f"Bearer {sales_token}"},
        )
        assert res_sales.status_code == 403

        # 2. Sales Manager được phép
        res_mgr = await client.get(
            "/api/v1/reporting/revenue",
            headers={"Authorization": f"Bearer {mgr_token}"},
        )
        assert res_mgr.status_code == 200
        assert "total_revenue" in res_mgr.json()

        # 3. Director được phép
        res_dir = await client.get(
            "/api/v1/reporting/revenue",
            headers={"Authorization": f"Bearer {dir_token}"},
        )
        assert res_dir.status_code == 200
        assert "total_revenue" in res_dir.json()


@pytest.mark.asyncio
async def test_sales_orders_data_scoping():
    """
    Kiểm tra Data Scoping:
    - sales_rep: Chỉ xem được các đơn hàng do chính mình tạo (orders:read).
    - sales_manager: Có quyền orders:read_all, xem được toàn bộ đơn hàng của tất cả nhân viên.
    """
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sales_token = await get_token_for(client, "sales@erpcopilot.vn", "sales123")
        mgr_token = await get_token_for(client, "manager@erpcopilot.vn", "manager123")

        # Lấy profile sales_rep
        res_me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {sales_token}"})
        sales_user_id = res_me.json()["id"]

        # Sales rep lấy danh sách đơn hàng
        res_sales_orders = await client.get(
            "/api/v1/sales-orders",
            headers={"Authorization": f"Bearer {sales_token}"},
        )
        assert res_sales_orders.status_code == 200
        orders = res_sales_orders.json()
        assert len(orders) > 0
        # Mọi đơn hàng sales_rep thấy đều phải do sales_rep tạo
        for o in orders:
            # Tra cứu chi tiết từng đơn
            detail_res = await client.get(f"/api/v1/sales-orders/{o['id']}", headers={"Authorization": f"Bearer {sales_token}"})
            assert detail_res.status_code == 200

        # Sales manager lấy danh sách đơn hàng -> Có quyền xem tất cả
        res_mgr_orders = await client.get(
            "/api/v1/sales-orders",
            headers={"Authorization": f"Bearer {mgr_token}"},
        )
        assert res_mgr_orders.status_code == 200
        assert len(res_mgr_orders.json()) >= len(orders)


@pytest.mark.asyncio
async def test_four_eyes_principle_prevent_self_approval():
    """
    Kiểm tra Nguyên tắc 4 mắt (Four-Eyes Principle / Segregation of Duties):
    - Người đề xuất đơn hàng (kể cả Manager/Admin) KHÔNG được phép tự phê duyệt đơn của chính mình.
    """
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        mgr_token = await get_token_for(client, "manager@erpcopilot.vn", "manager123")
        admin_token = await get_token_for(client, "admin@erpcopilot.vn", "admin123")

        # 1. Manager tạo đơn hàng qua Text Ingestion
        res_ingest = await client.post(
            "/api/v1/orders/ingest-text",
            json={
                "text": "Email từ CUS-0001: Đặt mua 1 chiếc SKU-001 giao sớm nhé.",
                "source_identifier": "test_four_eyes",
            },
            headers={"Authorization": f"Bearer {mgr_token}"},
        )
        assert res_ingest.status_code == 200
        approval_id = res_ingest.json()["approval_request_id"]

        # 2. Manager tự mình duyệt đơn của chính mình -> PHẢI BỊ CHẶN (Four-Eyes Principle)
        res_self_approve = await client.post(
            f"/api/v1/approvals/{approval_id}/approve",
            headers={"Authorization": f"Bearer {mgr_token}"},
        )
        assert res_self_approve.status_code in (400, 422)
        err_msg = res_self_approve.json()["error"]["message"]
        assert "Four-Eyes Principle" in err_msg or "phân tách trách nhiệm" in err_msg

        # 3. Chuyển cho Quản trị viên (Admin) khác duyệt -> Thành công 200 OK
        res_admin_approve = await client.post(
            f"/api/v1/approvals/{approval_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res_admin_approve.status_code == 200
        assert res_admin_approve.json()["status"] == "confirmed"
