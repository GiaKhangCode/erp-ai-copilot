import logging
import re
import uuid
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.document_ai.schemas import (
    ExtractedOrderItem,
    ExtractedPurchaseOrder,
    OrderDiscrepancyWarning,
    ResolvedOrderItem,
)
from app.erp.models import Customer, Inventory, Product

logger = logging.getLogger(__name__)


class EntityResolutionResult:
    def __init__(
        self,
        customer: Optional[Customer],
        resolved_items: List[ResolvedOrderItem],
        unresolved_items: List[ExtractedOrderItem],
        warnings: List[OrderDiscrepancyWarning],
        total_amount: Decimal,
    ):
        self.customer = customer
        self.resolved_items = resolved_items
        self.unresolved_items = unresolved_items
        self.warnings = warnings
        self.total_amount = total_amount

    @property
    def is_fully_resolved(self) -> bool:
        """Đơn hàng chỉ được coi là hoàn toàn hợp lệ nếu tìm thấy khách hàng và ít nhất 1 mặt hàng, không có mặt hàng nào bị lỗi SKU."""
        return bool(self.customer) and len(self.resolved_items) > 0 and len(self.unresolved_items) == 0


class EntityResolver:
    """
    Domain Service phụ trách đối chiếu và khớp nối các thực thể bóc tách từ Email/Tài liệu
    với cơ sở dữ liệu thật của hệ thống ERP (Customers, Products, Inventory).
    """

    @classmethod
    async def resolve_order(
        cls,
        session: AsyncSession,
        extracted_order: ExtractedPurchaseOrder,
    ) -> EntityResolutionResult:
        warnings: List[OrderDiscrepancyWarning] = []

        # 1. Đối chiếu thông tin khách hàng (Customer Resolution)
        customer = await cls.resolve_customer(session, extracted_order)
        if not customer:
            warnings.append(
                OrderDiscrepancyWarning(
                    warning_type="unmatched_customer",
                    severity="critical",
                    message=(
                        f"Không tìm thấy khách hàng tương ứng trong cơ sở dữ liệu "
                        f"(Tên: '{extracted_order.customer_name_candidate}', "
                        f"Mã: '{extracted_order.customer_code_candidate}', "
                        f"Email: '{extracted_order.sender_email}'). "
                        f"Cần tạo hồ sơ khách hàng mới trước khi chốt đơn."
                    ),
                    field_affected="customer",
                )
            )

        # 2. Đối chiếu danh sách sản phẩm và kiểm tra tồn kho (Product & Inventory Resolution)
        resolved_items: List[ResolvedOrderItem] = []
        unresolved_items: List[ExtractedOrderItem] = []
        total_amount = Decimal("0.00")

        if not extracted_order.items:
            warnings.append(
                OrderDiscrepancyWarning(
                    warning_type="empty_items",
                    severity="critical",
                    message="Đơn hàng không có mặt hàng nào được trích xuất.",
                    field_affected="items",
                )
            )

        for item in extracted_order.items:
            resolved_item = await cls.resolve_single_item(session, item)
            if resolved_item:
                resolved_items.append(resolved_item)
                total_amount += resolved_item.line_total

                # Cảnh báo thiếu hàng trong kho
                if not resolved_item.stock_sufficient:
                    warnings.append(
                        OrderDiscrepancyWarning(
                            warning_type="stock_shortage",
                            severity="warning",
                            message=(
                                f"Sản phẩm {resolved_item.product_name} ({resolved_item.sku}) "
                                f"đặt {resolved_item.quantity} cái nhưng tổng tồn khả dụng toàn hệ thống chỉ còn {resolved_item.available_stock} cái."
                            ),
                            field_affected=f"items.{resolved_item.sku}.quantity",
                        )
                    )

                # Cảnh báo lệch giá so với giá niêm yết DB
                if resolved_item.price_discrepancy and resolved_item.price_discrepancy_message:
                    warnings.append(
                        OrderDiscrepancyWarning(
                            warning_type="price_mismatch",
                            severity="warning",
                            message=resolved_item.price_discrepancy_message,
                            field_affected=f"items.{resolved_item.sku}.unit_price",
                        )
                    )
            else:
                unresolved_items.append(item)
                warnings.append(
                    OrderDiscrepancyWarning(
                        warning_type="unmatched_sku",
                        severity="critical",
                        message=(
                            f"Không tìm thấy sản phẩm phù hợp trong hệ thống ERP "
                            f"(Mã SKU: '{item.sku_candidate}', Tên: '{item.product_name}')."
                        ),
                        field_affected=f"items.{item.sku_candidate or item.product_name}",
                    )
                )

        # 3. Kiểm tra ngày giao hàng
        if not extracted_order.requested_delivery_date:
            warnings.append(
                OrderDiscrepancyWarning(
                    warning_type="missing_delivery_date",
                    severity="info",
                    message="Khách hàng không ghi rõ ngày yêu cầu giao hàng mong muốn.",
                    field_affected="requested_delivery_date",
                )
            )

        return EntityResolutionResult(
            customer=customer,
            resolved_items=resolved_items,
            unresolved_items=unresolved_items,
            warnings=warnings,
            total_amount=total_amount,
        )

    @classmethod
    async def resolve_customer(
        cls,
        session: AsyncSession,
        extracted: ExtractedPurchaseOrder,
    ) -> Optional[Customer]:
        """
        Khớp nối khách hàng đa cấp độ:
        1. Khớp theo mã khách hàng (customer_code_candidate)
        2. Khớp theo địa chỉ email người gửi (sender_email)
        3. Khớp mờ theo tên công ty (customer_name_candidate)
        """
        # Cấp 1: Mã khách hàng chính xác
        if extracted.customer_code_candidate:
            code_clean = extracted.customer_code_candidate.strip().upper()
            stmt = select(Customer).where(Customer.code == code_clean, Customer.status == "active")
            res = await session.execute(stmt)
            customer = res.scalar_one_or_none()
            if customer:
                return customer

        # Cấp 2: Email người gửi
        if extracted.sender_email:
            email_clean = extracted.sender_email.strip().lower()
            stmt = select(Customer).where(func.lower(Customer.email) == email_clean, Customer.status == "active")
            res = await session.execute(stmt)
            customer = res.scalar_one_or_none()
            if customer:
                return customer

        # Cấp 3: Tên khách hàng (tìm kiếm chứa chuỗi hoặc từ khóa chính)
        if extracted.customer_name_candidate:
            name_clean = extracted.customer_name_candidate.strip()
            # Bỏ các từ chung chung như "Công ty", "TNHH", "Cổ phần", "Tập đoàn" để so khớp từ khóa đặc trưng
            keywords = re.sub(r"(?i)\b(công ty|tnhh|cổ phần|cp|tập đoàn|doanh nghiệp|cty)\b", "", name_clean).strip()
            if len(keywords) >= 3:
                stmt = select(Customer).where(Customer.name.ilike(f"%{keywords}%"), Customer.status == "active")
                res = await session.execute(stmt)
                customer = res.scalars().first()
                if customer:
                    return customer

        return None

    @classmethod
    async def resolve_single_item(
        cls,
        session: AsyncSession,
        item: ExtractedOrderItem,
    ) -> Optional[ResolvedOrderItem]:
        """
        Khớp nối sản phẩm trong DB qua SKU hoặc Tên sản phẩm,
        lấy giá niêm yết DB và tính toán tồn kho khả dụng thời gian thực.
        """
        product: Optional[Product] = None

        # 1. Tìm theo SKU
        if item.sku_candidate:
            sku_clean = item.sku_candidate.strip().upper()
            stmt = select(Product).where(Product.sku == sku_clean, Product.is_active == True)
            res = await session.execute(stmt)
            product = res.scalar_one_or_none()

        # 2. Tìm theo tên sản phẩm nếu không có SKU hoặc tìm theo SKU không ra
        if not product and item.product_name:
            name_clean = item.product_name.strip()
            stmt = select(Product).where(Product.name.ilike(f"%{name_clean}%"), Product.is_active == True)
            res = await session.execute(stmt)
            product = res.scalars().first()

        if not product:
            return None

        # 3. Tính toán tổng tồn kho khả dụng của sản phẩm trên tất cả các kho
        # available = sum(quantity_on_hand - quantity_reserved)
        inv_stmt = select(
            func.coalesce(func.sum(Inventory.quantity_on_hand - Inventory.quantity_reserved), 0)
        ).where(Inventory.product_id == product.id)
        inv_res = await session.execute(inv_stmt)
        total_available = int(inv_res.scalar() or 0)

        # 4. Đối chiếu giá niêm yết vs giá tài liệu
        db_price = Decimal(str(product.unit_price))
        doc_price = Decimal(str(item.unit_price_in_doc)) if item.unit_price_in_doc is not None else None
        price_discrepancy = False
        discrepancy_msg = None

        if doc_price is not None and doc_price != db_price:
            price_discrepancy = True
            discrepancy_msg = (
                f"Giá ghi trong tài liệu ({doc_price:,.0f} VND) khác với giá niêm yết chuẩn ERP "
                f"({db_price:,.0f} VND) cho sản phẩm {product.sku}. Hệ thống áp dụng giá chuẩn từ DB."
            )

        line_total = Decimal(item.quantity) * db_price

        return ResolvedOrderItem(
            product_id=product.id,
            sku=product.sku,
            product_name=product.name,
            quantity=item.quantity,
            db_unit_price=db_price,
            doc_unit_price=doc_price,
            line_total=line_total,
            price_discrepancy=price_discrepancy,
            price_discrepancy_message=discrepancy_msg,
            available_stock=total_available,
            stock_sufficient=(total_available >= item.quantity),
        )
