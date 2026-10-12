import uuid
import secrets
import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFoundException, ValidationException
from app.erp.models import Customer, Product, SalesOrder, SalesOrderItem, IdempotencyKey
from app.erp.schemas import OrderDraftCreate


class SalesOrderService:
    @staticmethod
    async def list_orders(
        session: AsyncSession,
        customer_code: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[SalesOrder]:
        """Lấy danh sách đơn hàng bán có lọc theo khách hàng và trạng thái."""
        stmt = (
            select(SalesOrder)
            .join(SalesOrder.customer)
            .options(
                selectinload(SalesOrder.customer),
                selectinload(SalesOrder.items).selectinload(SalesOrderItem.product),
            )
        )
        if customer_code:
            stmt = stmt.where(Customer.code == customer_code)
        if status:
            stmt = stmt.where(SalesOrder.status == status)

        stmt = stmt.order_by(SalesOrder.created_at.desc()).limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_order_by_id(session: AsyncSession, order_id: uuid.UUID) -> SalesOrder:
        """Lấy chi tiết đơn hàng theo ID kèm danh sách mặt hàng."""
        stmt = (
            select(SalesOrder)
            .options(
                selectinload(SalesOrder.customer),
                selectinload(SalesOrder.items).selectinload(SalesOrderItem.product),
            )
            .where(SalesOrder.id == order_id)
        )
        result = await session.execute(stmt)
        order = result.scalar_one_or_none()
        if not order:
            raise NotFoundException(
                f"Không tìm thấy đơn hàng với ID '{order_id}'",
                code="ORDER_NOT_FOUND",
            )
        return order

    @staticmethod
    async def create_order_draft(
        session: AsyncSession,
        payload: OrderDraftCreate,
        actor_id: Optional[uuid.UUID] = None,
        idempotency_key: Optional[str] = None,
    ) -> SalesOrder:
        """
        Tạo đơn hàng nháp (draft).
        - Kiểm tra tính hợp lệ của khách hàng và SKU
        - Snapshot giá bán trực tiếp từ ERP catalog (không tin client/LLM)
        - Tính toán tổng tiền server-side
        - Hỗ trợ Idempotency-Key chống duplicate writes
        """
        resolved_actor_id = actor_id or uuid.UUID("00000000-0000-0000-0000-000000000001")

        # Idempotency Check (Blueprint 5.2 & Invariant 6)
        if idempotency_key:
            stmt_idemp = select(IdempotencyKey).where(
                IdempotencyKey.key == idempotency_key,
                IdempotencyKey.actor_id == resolved_actor_id,
            )
            res_idemp = await session.execute(stmt_idemp)
            existing_key = res_idemp.scalar_one_or_none()
            if existing_key and existing_key.response_ref:
                cached_order_id = existing_key.response_ref.get("order_id")
                if cached_order_id:
                    return await SalesOrderService.get_order_by_id(session, uuid.UUID(cached_order_id))

        # Invariant 1: Validate customer exists and is active
        stmt = select(Customer).where(Customer.code == payload.customer_code)
        result = await session.execute(stmt)
        customer = result.scalar_one_or_none()
        if not customer:
            raise NotFoundException(
                f"Khách hàng với mã '{payload.customer_code}' không tồn tại",
                code="CUSTOMER_NOT_FOUND",
            )
        if customer.status != "active":
            raise ValidationException(
                f"Khách hàng '{payload.customer_code}' đang trong trạng thái ngừng hoạt động"
            )

        # Invariant 2: Items cannot be empty
        if not payload.items:
            raise ValidationException("Đơn hàng phải chứa ít nhất một mặt hàng")

        # Invariant 3: Server-side price snapshot and total computation
        order_items_to_create: list[SalesOrderItem] = []
        total_amount = Decimal("0.00")

        for item_draft in payload.items:
            if item_draft.quantity <= 0:
                raise ValidationException(
                    f"Số lượng đặt hàng cho SKU '{item_draft.sku}' phải lớn hơn 0"
                )

            prod_stmt = select(Product).where(Product.sku == item_draft.sku)
            prod_result = await session.execute(prod_stmt)
            product = prod_result.scalar_one_or_none()
            if not product:
                raise NotFoundException(
                    f"Sản phẩm với SKU '{item_draft.sku}' không tồn tại",
                    code="PRODUCT_NOT_FOUND",
                )
            if not product.is_active:
                raise ValidationException(
                    f"Sản phẩm với SKU '{item_draft.sku}' đã ngừng kinh doanh"
                )

            # Invariant: Snapshot price directly from ERP catalog
            unit_price = product.unit_price
            line_total = Decimal(item_draft.quantity) * unit_price
            total_amount += line_total

            order_item = SalesOrderItem(
                product_id=product.id,
                quantity=item_draft.quantity,
                unit_price=unit_price,
                line_total=line_total,
            )
            order_items_to_create.append(order_item)

        # Invariant 4: Generate unique order number
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        random_suffix = secrets.token_hex(2).upper()
        order_number = f"SO-{today_str}-{random_suffix}"

        # Invariant 5: Default status is 'draft', non-destructive
        order = SalesOrder(
            order_number=order_number,
            customer_id=customer.id,
            status="draft",
            total_amount=total_amount,
            created_by=resolved_actor_id,
            items=order_items_to_create,
        )

        session.add(order)
        await session.flush()

        # Save idempotency key if provided
        if idempotency_key:
            req_hash = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
            idemp_record = IdempotencyKey(
                key=idempotency_key,
                actor_id=resolved_actor_id,
                request_hash=req_hash,
                response_ref={"order_id": str(order.id)},
            )
            session.add(idemp_record)

        await session.commit()
        await session.refresh(order)

        return await SalesOrderService.get_order_by_id(session, order.id)
