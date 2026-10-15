import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.ai.tools.erp_tools import generate_sales_quotation, check_customer_credit
from app.ai.tools.context import set_current_user_context, UserContext

@pytest.mark.asyncio
async def test_phase2_export_quotation_pdf_and_summary():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login as Sales Rep
        sales_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "sales@erpcopilot.vn", "password": "sales123"},
        )
        assert sales_login.status_code == 200
        sales_token = sales_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {sales_token}"}

        # 2. Get list of orders
        orders_res = await client.get("/api/v1/sales-orders", headers=headers)
        assert orders_res.status_code == 200
        orders = orders_res.json()
        assert len(orders) > 0

        target_order = orders[0]
        order_id = target_order["id"]

        # 3. Test Quotation Summary endpoint
        summary_res = await client.get(f"/api/v1/orders/{order_id}/quotation/summary", headers=headers)
        assert summary_res.status_code == 200
        summary_data = summary_res.json()
        assert summary_data["order_id"] == str(order_id)
        assert "pdf_url" in summary_data
        assert "filename" in summary_data
        assert summary_data["filename"].endswith(".pdf")
        assert len(summary_data["items"]) > 0

        # 4. Test Export Quotation PDF Binary Stream
        pdf_res = await client.get(f"/api/v1/orders/{order_id}/quotation/pdf", headers=headers)
        assert pdf_res.status_code == 200
        assert pdf_res.headers.get("content-type") == "application/pdf"
        assert "inline" in pdf_res.headers.get("content-disposition", "")
        # Standard PDF files start with %PDF-
        assert pdf_res.content.startswith(b"%PDF-")
        assert len(pdf_res.content) > 1000 # Valid non-empty PDF document


@pytest.mark.asyncio
async def test_phase2_customer_credit_limit_check():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login as Sales Rep
        sales_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "sales@erpcopilot.vn", "password": "sales123"},
        )
        assert sales_login.status_code == 200
        sales_token = sales_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {sales_token}"}

        # 2. Check credit for CUS-001 (Credit limit: 100M, Debt: 25M)
        credit_res = await client.get("/api/v1/customers/CUS-001/credit-check?additional_amount=10000000", headers=headers)
        assert credit_res.status_code == 200
        credit_data = credit_res.json()
        assert float(credit_data["credit_limit"]) == 100000000
        assert float(credit_data["current_debt"]) == 25000000
        assert credit_data["is_exceeded"] is False
        assert float(credit_data["available_credit"]) == 65000000 # 100M - (25M + 10M)

        # 3. Check credit with high additional amount that triggers exceed
        credit_exceed = await client.get("/api/v1/customers/CUS-001/credit-check?additional_amount=90000000", headers=headers)
        assert credit_exceed.status_code == 200
        exceed_data = credit_exceed.json()
        assert exceed_data["is_exceeded"] is True
        assert float(exceed_data["available_credit"]) < 0


@pytest.mark.asyncio
async def test_phase2_ai_tools_execution():
    # Setup user context for sales rep
    set_current_user_context(UserContext(
        user_id=uuid.uuid4(),
        user_email="sales@erpcopilot.vn",
        user_role="sales_rep",
        user_permissions=["orders:read", "customers:read"],
    ))

    # 1. Test check_customer_credit AI tool
    credit_tool_result = await check_customer_credit.ainvoke({
        "customer_identifier": "CUS-001",
        "additional_amount": 5000000.0,
    })
    assert "Báo cáo thẩm định công nợ" in credit_tool_result
    assert "Hạn mức công nợ tối đa" in credit_tool_result

    # 2. Test generate_sales_quotation AI tool
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sales_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "sales@erpcopilot.vn", "password": "sales123"},
        )
        sales_token = sales_login.json()["access_token"]
        orders_res = await client.get("/api/v1/sales-orders", headers={"Authorization": f"Bearer {sales_token}"})
        orders = orders_res.json()
        order_num = orders[0]["order_number"]

        quotation_tool_result = await generate_sales_quotation.ainvoke({
            "order_identifier": order_num,
        })
        assert "Báo giá kinh doanh" in quotation_tool_result
        # Must contain ChatGPT-style file attachment card tag: :::quotation[...]:::
        assert ":::quotation[" in quotation_tool_result
        assert ".pdf" in quotation_tool_result
