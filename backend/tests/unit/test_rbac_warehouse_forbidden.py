import json
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.ai.tools.context import UserContext, set_current_user_context
from app.ai.tools.erp_tools import (
    propose_sales_order_draft,
    generate_sales_quotation,
    check_customer_credit,
    get_revenue_report,
    deliver_sales_order,
    adjust_inventory,
    get_inventory,
)

transport = ASGITransport(app=app)


@pytest.mark.asyncio
async def test_warehouse_keeper_cannot_create_order_via_apis():
    """
    Xác thực tài khoản Thủ kho (warehouse_keeper) bị chặn 403 khi gọi các REST & Ingestion APIs tạo đơn hàng.
    """
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Đăng nhập tài khoản Thủ kho
        res_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "warehouse@erpcopilot.vn", "password": "warehouse123"},
        )
        assert res_login.status_code == 200
        wh_token = res_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {wh_token}"}

        # 2. Thử tạo đơn hàng nháp qua REST API -> 403 Forbidden
        draft_payload = {
            "customer_code": "CUS-0001",
            "items": [{"sku": "SKU-001", "quantity": 1}],
        }
        res_draft = await client.post(
            "/api/v1/sales-orders/drafts",
            json=draft_payload,
            headers=headers,
        )
        assert res_draft.status_code == 403
        assert "orders:create" in res_draft.json().get("error", {}).get("message", "")

        # 3. Thử nạp đơn hàng qua Ingestion text -> 403 Forbidden
        res_ingest_text = await client.post(
            "/api/v1/orders/ingest-text",
            json={"text": "Đặt hàng 5 cái SKU-001 cho CUS-0001"},
            headers=headers,
        )
        assert res_ingest_text.status_code == 403
        assert "orders:create" in res_ingest_text.json().get("error", {}).get("message", "")


@pytest.mark.asyncio
async def test_warehouse_keeper_ai_tools_rbac_enforcement():
    """
    Xác thực các AI Tools độc lập chặn quyền truy cập trái phép của Thủ kho (warehouse_keeper).
    - propose_sales_order_draft -> PERMISSION_DENIED
    - generate_sales_quotation -> PERMISSION_DENIED
    - check_customer_credit -> PERMISSION_DENIED
    - get_revenue_report -> PERMISSION_DENIED
    - get_inventory / adjust_inventory -> Được phép (Quyền kho)
    """
    # Giả lập context của Thủ kho (warehouse_keeper)
    set_current_user_context(UserContext(
        user_id="d055e795-fb5a-4212-9975-db1a90e29697",
        user_role="warehouse_keeper",
        user_name="Phạm Văn Thủ Kho",
        user_email="warehouse@erpcopilot.vn",
        user_permissions=["customers:read", "documents:read", "inventory:read", "inventory:write", "orders:read", "products:read"],
    ))

    # 1. Thử gọi propose_sales_order_draft -> Phải bị từ chối
    res_draft_str = await propose_sales_order_draft.ainvoke({
        "customer_code": "CUS-0001",
        "items": [{"sku": "SKU-001", "quantity": 2}],
    })
    res_draft = json.loads(res_draft_str)
    assert res_draft.get("success") is False
    assert res_draft.get("error") == "PERMISSION_DENIED"
    assert "orders:create" in res_draft.get("message", "")

    # 2. Thử gọi generate_sales_quotation -> Phải bị từ chối
    res_quote_str = await generate_sales_quotation.ainvoke({
        "order_identifier": "SO-2026-001",
    })
    res_quote = json.loads(res_quote_str)
    assert res_quote.get("error") == "PERMISSION_DENIED"
    assert "Báo giá kinh doanh chỉ dành cho" in res_quote.get("message", "")

    # 3. Thử gọi check_customer_credit -> Phải bị từ chối
    res_credit_str = await check_customer_credit.ainvoke({
        "customer_identifier": "CUS-0001",
    })
    res_credit = json.loads(res_credit_str)
    assert res_credit.get("error") == "PERMISSION_DENIED"
    assert "Thẩm định công nợ" in res_credit.get("message", "")

    # 4. Thử gọi get_revenue_report -> Phải bị từ chối
    res_rev_str = await get_revenue_report.ainvoke({"year": 2026})
    res_rev = json.loads(res_rev_str)
    assert res_rev.get("error") == "PERMISSION_DENIED"

    # 5. Gọi get_inventory -> Được phép (đúng nghiệp vụ)
    res_inv_str = await get_inventory.ainvoke({"sku": "SKU-001"})
    res_inv = json.loads(res_inv_str)
    assert res_inv.get("found") is True or "items" in res_inv


@pytest.mark.asyncio
async def test_warehouse_keeper_chat_cannot_propose_order():
    """
    Kiểm tra luồng đàm thoại AI Copilot: Khi Thủ kho chat yêu cầu tạo đơn nháp, hệ thống phải từ chối.
    """
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Đăng nhập tài khoản Thủ kho
        res_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "warehouse@erpcopilot.vn", "password": "warehouse123"},
        )
        assert res_login.status_code == 200
        wh_token = res_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {wh_token}"}

        # Gửi tin nhắn yêu cầu lập đơn
        chat_res = await client.post(
            "/api/v1/chat",
            json={"message": "Tạo đơn hàng nháp cho khách hàng CUS-0001 gồm 2 cái SKU-001"},
            headers=headers,
        )
        assert chat_res.status_code == 200
        data = chat_res.json()

        # Không được có proposed_action tạo đơn
        assert data.get("proposed_action") is None
        # Câu trả lời phải chứa cảnh báo từ chối quyền
        answer = data.get("answer", "")
        assert "từ chối" in answer.lower() or "orders:create" in answer or "không có quyền" in answer.lower() or "thủ kho" in answer.lower()
