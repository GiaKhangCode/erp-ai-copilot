import json
import uuid
import pytest
from unittest.mock import AsyncMock, patch

from app.ai.tools import (
    ALL_AGENT_TOOLS,
    get_tools_map,
    get_inventory,
    get_product,
    get_customer,
    get_sales_orders,
    get_revenue_report,
    propose_sales_order_draft,
    search_company_knowledge,
    set_current_user_context,
)
from app.rag.schemas import GroundedAnswer, Citation


def test_tool_registry_contains_all_seven_tools():
    """Verify registry exports all 7 allowlisted tools with distinct names."""
    tool_map = get_tools_map()
    expected_names = {
        "get_inventory",
        "get_product",
        "get_customer",
        "get_sales_orders",
        "get_revenue_report",
        "propose_sales_order_draft",
        "search_company_knowledge",
    }
    assert len(ALL_AGENT_TOOLS) == 7
    assert set(tool_map.keys()) == expected_names


@pytest.mark.asyncio
async def test_get_inventory_tool_found():
    """Verify get_inventory tool returns real-time stock numbers."""
    raw = await get_inventory.ainvoke({"sku": "SKU-001"})
    data = json.loads(raw)

    assert data["found"] is True
    assert data["sku"] == "SKU-001"
    assert data["total_available"] > 0
    assert data["total_on_hand"] >= data["total_available"]
    assert len(data["warehouses"]) >= 1


@pytest.mark.asyncio
async def test_get_inventory_tool_not_found():
    """Verify get_inventory tool handles unknown SKU gracefully."""
    raw = await get_inventory.ainvoke({"sku": "SKU-KHONG-TON-TAI"})
    data = json.loads(raw)

    assert data["found"] is False
    assert "Không tìm thấy" in data["message"]


@pytest.mark.asyncio
async def test_get_product_tool():
    """Verify get_product tool for valid and invalid SKU."""
    raw_found = await get_product.ainvoke({"sku": "SKU-001"})
    data_found = json.loads(raw_found)
    assert data_found["found"] is True
    assert data_found["unit_price"] == 28500000.0
    assert "Laptop Pro" in data_found["name"]

    raw_missing = await get_product.ainvoke({"sku": "SKU-999"})
    data_missing = json.loads(raw_missing)
    assert data_missing["found"] is False


@pytest.mark.asyncio
async def test_get_customer_tool():
    """Verify get_customer tool for existing and non-existing code."""
    raw_found = await get_customer.ainvoke({"customer_code": "CUS-0001"})
    data_found = json.loads(raw_found)
    assert data_found["found"] is True
    assert "Á Châu" in data_found["name"]

    raw_missing = await get_customer.ainvoke({"customer_code": "CUS-9999"})
    data_missing = json.loads(raw_missing)
    assert data_missing["found"] is False


@pytest.mark.asyncio
async def test_get_sales_orders_tool():
    """Verify get_sales_orders tool returns seeded orders."""
    raw = await get_sales_orders.ainvoke({"limit": 5})
    data = json.loads(raw)

    assert data["found"] is True
    assert data["total"] >= 1
    assert any(o["customer_code"] == "CUS-0001" for o in data["orders"])


@pytest.mark.asyncio
async def test_get_revenue_report_tool():
    """Verify get_revenue_report tool returns calculated metric from DB for admin."""
    set_current_user_context(user_role="admin")
    raw = await get_revenue_report.ainvoke({"year": 2026})
    data = json.loads(raw)

    assert data["metric_id"] == "revenue_summary"
    assert data["total_revenue"] > 0
    assert data["total_orders"] >= 1


@pytest.mark.asyncio
async def test_get_revenue_report_tool_unauthorized_sales_rep():
    """Verify get_revenue_report tool rejects sales_rep with PERMISSION_DENIED."""
    set_current_user_context(user_role="sales_rep")
    raw = await get_revenue_report.ainvoke({"year": 2026})
    data = json.loads(raw)

    assert data.get("error") == "PERMISSION_DENIED"
    assert "Truy cập bị từ chối" in data.get("message", "")


@pytest.mark.asyncio
async def test_propose_sales_order_draft_tool_success():
    """Verify propose_sales_order_draft validates customer, calculates prices and returns proposal."""
    payload = {
        "customer_code": "CUS-0001",
        "items": [
            {"sku": "SKU-001", "quantity": 2},  # 2 * 28,500,000 = 57,000,000
            {"sku": "SKU-002", "quantity": 1},  # 1 * 12,900,000 = 12,900,000
        ],
    }
    raw = await propose_sales_order_draft.ainvoke(payload)
    data = json.loads(raw)

    assert data["success"] is True
    assert data["action"] == "propose_order_draft"
    assert data["customer_code"] == "CUS-0001"
    assert len(data["items"]) == 2
    # 57,000,000 + 12,900,000 = 69,900,000
    assert data["total_amount"] == 69900000.0
    assert data["requires_user_confirmation"] is True


@pytest.mark.asyncio
async def test_propose_sales_order_draft_tool_validation_errors():
    """Verify propose_sales_order_draft rejects invalid inputs."""
    # 1. Invalid customer
    res1 = json.loads(await propose_sales_order_draft.ainvoke({
        "customer_code": "CUS-UNKNOWN",
        "items": [{"sku": "SKU-001", "quantity": 1}],
    }))
    assert res1["success"] is False
    assert "không tồn tại" in res1["message"]

    # 2. Invalid SKU
    res2 = json.loads(await propose_sales_order_draft.ainvoke({
        "customer_code": "CUS-0001",
        "items": [{"sku": "SKU-FAKE", "quantity": 1}],
    }))
    assert res2["success"] is False
    assert "không tồn tại" in res2["message"]

    # 3. Invalid quantity
    res3 = json.loads(await propose_sales_order_draft.ainvoke({
        "customer_code": "CUS-0001",
        "items": [{"sku": "SKU-001", "quantity": -5}],
    }))
    assert res3["success"] is False
    assert "số nguyên dương" in res3["message"]


@pytest.mark.asyncio
async def test_search_company_knowledge_tool():
    """Verify search_company_knowledge tool wraps QAService with user context."""
    set_current_user_context(
        user_id=uuid.uuid4(),
        user_role="sales_rep",
        user_name="Test Sales",
    )

    mock_answer = GroundedAnswer(
        answer="Khách hàng được đổi hàng trong 7 ngày [Nguồn: policy.md].",
        citations=[
            Citation(
                document_id=uuid.uuid4(),
                filename="policy.md",
                chunk_id=uuid.uuid4(),
                page_number=1,
                chunk_index=0,
                quote="Đổi hàng trong 7 ngày.",
            )
        ],
        has_sufficient_context=True,
        confidence_score=0.95,
        suggested_followups=[],
    )

    with patch("app.ai.tools.rag_tool.get_qa_service") as mock_get_qa:
        mock_qa = AsyncMock()
        mock_qa.ask.return_value = mock_answer
        mock_get_qa.return_value = mock_qa

        raw = await search_company_knowledge.ainvoke({"query": "đổi trả hàng"})
        data = json.loads(raw)

        assert data["has_sufficient_context"] is True
        assert "7 ngày" in data["answer"]
        assert len(data["citations"]) == 1
        assert data["citations"][0]["filename"] == "policy.md"
