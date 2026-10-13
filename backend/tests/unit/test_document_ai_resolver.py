import uuid
from decimal import Decimal
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.document_ai.schemas import ExtractedOrderItem, ExtractedPurchaseOrder
from app.document_ai.resolver import EntityResolver


@pytest.mark.asyncio
async def test_resolve_customer_by_code():
    """Kiểm thử khớp nối khách hàng chính xác theo mã CUS-0001."""
    async with async_session_factory() as session:
        extracted = ExtractedPurchaseOrder(
            customer_code_candidate="CUS-0001",
            customer_name_candidate="Tên khác",
        )
        customer = await EntityResolver.resolve_customer(session, extracted)
        assert customer is not None
        assert customer.code == "CUS-0001"
        assert "Á Châu" in customer.name


@pytest.mark.asyncio
async def test_resolve_customer_by_email():
    """Kiểm thử khớp nối khách hàng theo địa chỉ email người gửi."""
    async with async_session_factory() as session:
        extracted = ExtractedPurchaseOrder(
            sender_email="contact@asiatech.vn",
        )
        customer = await EntityResolver.resolve_customer(session, extracted)
        assert customer is not None
        assert customer.code == "CUS-0001"


@pytest.mark.asyncio
async def test_resolve_customer_fuzzy_name():
    """Kiểm thử khớp nối mờ khách hàng theo tên công ty."""
    async with async_session_factory() as session:
        extracted = ExtractedPurchaseOrder(
            customer_name_candidate="Công ty TNHH Công Nghệ Á Châu",
        )
        customer = await EntityResolver.resolve_customer(session, extracted)
        assert customer is not None
        assert customer.code == "CUS-0001"


@pytest.mark.asyncio
async def test_resolve_single_item_pricing_and_inventory():
    """
    Kiểm thử khớp nối sản phẩm:
    - Lấy đúng giá niêm yết DB (28,500,000 VND).
    - Tính tồn kho khả dụng từ tất cả các kho.
    - Cảnh báo lệch giá khi đơn hàng tài liệu ghi đơn giá khác.
    """
    async with async_session_factory() as session:
        item = ExtractedOrderItem(
            product_name="Laptop Pro 14 M3",
            sku_candidate="SKU-001",
            quantity=2,
            unit_price_in_doc=Decimal("20000000"),  # Giá ghi trong email thấp hơn giá DB
        )
        resolved = await EntityResolver.resolve_single_item(session, item)
        assert resolved is not None
        assert resolved.sku == "SKU-001"
        assert resolved.db_unit_price == Decimal("28500000.00")
        assert resolved.line_total == Decimal("57000000.00")  # Tính lại theo giá DB
        assert resolved.price_discrepancy is True
        assert "khác với giá niêm yết" in (resolved.price_discrepancy_message or "")
        assert resolved.available_stock > 0
        assert resolved.stock_sufficient is True


@pytest.mark.asyncio
async def test_resolve_full_order_with_warnings():
    """
    Kiểm thử quy trình đối chiếu toàn bộ đơn hàng:
    - Có khách hàng CUS-0001.
    - Mặt hàng 1 (SKU-001) hợp lệ.
    - Mặt hàng 2 (SKU-UNKNOWN) không tìm thấy trong DB -> phát sinh cảnh báo unmatched_sku.
    - Số lượng đặt cực lớn -> phát sinh cảnh báo thiếu tồn kho (stock_shortage).
    """
    async with async_session_factory() as session:
        extracted_order = ExtractedPurchaseOrder(
            customer_code_candidate="CUS-0001",
            sender_email="contact@asiatech.vn",
            items=[
                ExtractedOrderItem(
                    product_name="Laptop Pro M3",
                    sku_candidate="SKU-001",
                    quantity=99999,  # Vượt quá tồn kho
                ),
                ExtractedOrderItem(
                    product_name="Món hàng không tồn tại",
                    sku_candidate="SKU-999-NONEXISTENT",
                    quantity=1,
                ),
            ],
        )

        result = await EntityResolver.resolve_order(session, extracted_order)

        assert result.customer is not None
        assert result.customer.code == "CUS-0001"
        assert len(result.resolved_items) == 1
        assert len(result.unresolved_items) == 1
        assert result.is_fully_resolved is False  # Do có SKU không tìm thấy

        warning_types = [w.warning_type for w in result.warnings]
        assert "stock_shortage" in warning_types
        assert "unmatched_sku" in warning_types
        assert "missing_delivery_date" in warning_types
