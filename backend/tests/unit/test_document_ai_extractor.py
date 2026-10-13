import asyncio
import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.document_ai.schemas import ExtractedOrderItem, ExtractedPurchaseOrder, ParsedEmailMessage
from app.document_ai.extractor import OrderExtractor


@pytest.fixture
def sample_order_email() -> ParsedEmailMessage:
    return ParsedEmailMessage(
        subject="Đặt mua thiết bị văn phòng từ Cty Minh Long",
        from_address="muahang@minhlong.vn",
        sender_name="Công ty TNHH Minh Long",
        combined_body=(
            "Kính gửi ERP Copilot,\n\n"
            "Công ty TNHH Minh Long (Mã KH: CUS-0001, MST: 0101234567, SĐT: 0901234567)\n"
            "Chúng tôi cần đặt gấp các mặt hàng sau:\n"
            "- 5 chiếc Laptop Pro 14 M3 (Mã: SKU-001)\n"
            "- 10 con Chuột không dây (Mã: SKU-002)\n\n"
            "Yêu cầu giao trước ngày 2026-10-30 tại địa chỉ Landmark 81, TP.HCM.\n"
            "Thanh toán chuyển khoản 30 ngày."
        ),
    )


def test_heuristic_extractor_fallback(sample_order_email: ParsedEmailMessage):
    """Kiểm thử bộ trích xuất heuristic hoạt động chính xác khi không có LLM."""
    extractor = OrderExtractor(genai_client=MagicMock())
    result = extractor._extract_with_heuristic(sample_order_email)

    assert result.customer_code_candidate == "CUS-0001"
    assert "Minh Long" in (result.customer_name_candidate or "")
    assert result.sender_phone == "0901234567"
    assert result.tax_code == "0101234567"
    assert result.sender_email == "muahang@minhlong.vn"
    assert str(result.requested_delivery_date) == "2026-10-30"
    assert len(result.items) >= 2

    # Kiểm tra các items
    skus = [it.sku_candidate for it in result.items]
    assert "SKU-001" in skus
    assert "SKU-002" in skus


@pytest.mark.asyncio
async def test_order_extractor_sql_injection_guardrail():
    """Kiểm thử hệ thống phát hiện SQL Injection trong nội dung email và vô hiệu hóa an toàn."""
    malicious_email = ParsedEmailMessage(
        subject="DROP TABLE erp.products;",
        from_address="attacker@evil.com",
        combined_body="DROP TABLE erp.products; SELECT * FROM erp.users; Đặt 10 cái SKU-001",
    )

    extractor = OrderExtractor(genai_client=MagicMock())
    result = await extractor.extract_order(malicious_email)

    assert "Cảnh báo" in (result.notes or "")
    assert "vô hiệu hóa" in (result.notes or "")
    # Mặt hàng hợp lệ vẫn được bóc tách an toàn nếu có
    assert len(result.items) == 1
    assert result.items[0].sku_candidate == "SKU-001"
    assert result.items[0].quantity == 10


@pytest.mark.asyncio
async def test_order_extractor_with_mock_llm(sample_order_email: ParsedEmailMessage):
    """Kiểm thử OrderExtractor parse thành công từ Mocked LLM response."""
    mock_extracted = ExtractedPurchaseOrder(
        customer_name_candidate="Công ty TNHH Minh Long",
        customer_code_candidate="CUS-0001",
        sender_email="muahang@minhlong.vn",
        sender_phone="0901234567",
        tax_code="0101234567",
        shipping_address="Landmark 81, TP.HCM",
        items=[
            ExtractedOrderItem(
                raw_text="5 chiếc Laptop Pro 14 M3 (Mã: SKU-001)",
                sku_candidate="SKU-001",
                product_name="Laptop Pro 14 M3",
                quantity=5,
                unit="chiếc",
            ),
            ExtractedOrderItem(
                raw_text="10 con Chuột không dây (Mã: SKU-002)",
                sku_candidate="SKU-002",
                product_name="Chuột không dây",
                quantity=10,
                unit="con",
            ),
        ],
        confidence_score=0.98,
    )

    mock_response = MagicMock()
    mock_response.parsed = mock_extracted

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    extractor = OrderExtractor(genai_client=mock_client)
    res = await extractor.extract_order(sample_order_email)

    assert res.customer_code_candidate == "CUS-0001"
    assert len(res.items) == 2
    assert res.items[0].sku_candidate == "SKU-001"
    assert res.items[0].quantity == 5
    assert res.items[1].sku_candidate == "SKU-002"
    assert res.items[1].quantity == 10
    assert res.confidence_score == 0.98


@pytest.mark.asyncio
async def test_order_extractor_empty_content():
    """Kiểm thử xử lý khi tài liệu email hoàn toàn rỗng."""
    empty_email = ParsedEmailMessage(
        subject="",
        from_address="test@example.com",
        combined_body="   ",
    )
    extractor = OrderExtractor(genai_client=MagicMock())
    res = await extractor.extract_order(empty_email)
    assert res.confidence_score == 0.0
    assert len(res.items) == 0
    assert "rỗng" in (res.notes or "")
