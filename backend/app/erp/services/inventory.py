import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFoundException, ValidationException
from app.erp.models import Product, Warehouse, Inventory, StockAdjustment, AuditLog
from app.erp.schemas import InventoryResponse, StockAdjustmentResponse


class InventoryService:
    @staticmethod
    async def get_inventory(
        session: AsyncSession,
        sku: Optional[str] = None,
        warehouse_code: Optional[str] = None,
    ) -> List[InventoryResponse]:
        """
        Tra cứu tồn kho thời gian thực.
        Tính toán số lượng khả dụng: available = on_hand - reserved.
        """
        stmt = (
            select(Inventory)
            .join(Inventory.product)
            .join(Inventory.warehouse)
            .options(selectinload(Inventory.product), selectinload(Inventory.warehouse))
        )
        if sku:
            stmt = stmt.where(Product.sku == sku)
        if warehouse_code:
            stmt = stmt.where(Warehouse.code == warehouse_code)

        stmt = stmt.order_by(Product.sku, Warehouse.code)
        result = await session.execute(stmt)
        items = result.scalars().all()

        return [
            InventoryResponse(
                product_sku=item.product.sku,
                product_name=item.product.name,
                warehouse_code=item.warehouse.code,
                warehouse_name=item.warehouse.name,
                quantity_on_hand=item.quantity_on_hand,
                quantity_reserved=item.quantity_reserved,
                quantity_available=item.available_quantity,
            )
            for item in items
        ]

    @staticmethod
    async def adjust_inventory(
        session: AsyncSession,
        sku: str,
        warehouse_code: str,
        delta_quantity: int,
        reason: str,
        user_id: uuid.UUID,
    ) -> StockAdjustment:
        """
        Phiếu kiểm kê & điều chỉnh tồn kho (Stock Adjustment):
        - delta_quantity: số lượng tăng (+) hoặc giảm (-).
        - Kiểm tra tính hợp lệ: Tồn kho sau điều chỉnh không được nhỏ hơn số lượng đang giữ đơn (reserved).
        - Ghi nhật ký kiểm kê StockAdjustment và AuditLog.
        """
        if delta_quantity == 0:
            raise ValidationException("Số lượng điều chỉnh (delta) phải khác 0.")

        clean_sku = sku.strip().upper()
        clean_wh = warehouse_code.strip().upper()

        # Tìm sản phẩm
        prod_stmt = select(Product).where(Product.sku == clean_sku)
        prod_res = await session.execute(prod_stmt)
        product = prod_res.scalar_one_or_none()
        if not product:
            raise NotFoundException(f"Không tìm thấy sản phẩm có mã SKU '{clean_sku}'")

        # Tìm kho
        wh_stmt = select(Warehouse).where(Warehouse.code == clean_wh)
        wh_res = await session.execute(wh_stmt)
        warehouse = wh_res.scalar_one_or_none()
        if not warehouse:
            raise NotFoundException(f"Không tìm thấy kho hàng có mã '{clean_wh}'")

        # Tìm bản ghi tồn kho
        inv_stmt = select(Inventory).where(
            Inventory.product_id == product.id,
            Inventory.warehouse_id == warehouse.id,
        )
        inv_res = await session.execute(inv_stmt)
        inventory = inv_res.scalar_one_or_none()

        if not inventory:
            if delta_quantity < 0:
                raise ValidationException(f"Sản phẩm '{clean_sku}' chưa có tồn kho tại kho '{clean_wh}', không thể giảm.")
            inventory = Inventory(
                product_id=product.id,
                warehouse_id=warehouse.id,
                quantity_on_hand=0,
                quantity_reserved=0,
            )
            session.add(inventory)

        qty_before = inventory.quantity_on_hand
        qty_after = qty_before + delta_quantity

        if qty_after < 0:
            raise ValidationException(
                f"Tồn kho thực tế không thể âm ({qty_after}). Tồn kho hiện tại: {qty_before}."
            )

        if qty_after < inventory.quantity_reserved:
            raise ValidationException(
                f"Không thể giảm tồn kho xuống dưới số lượng đang giữ đơn hàng. "
                f"Tồn kho sau điều chỉnh: {qty_after}, số lượng đang giữ đơn: {inventory.quantity_reserved}."
            )

        inventory.quantity_on_hand = qty_after

        # Ghi nhận phiếu điều chỉnh
        adjustment = StockAdjustment(
            id=uuid.uuid4(),
            product_id=product.id,
            warehouse_id=warehouse.id,
            sku=clean_sku,
            warehouse_code=clean_wh,
            delta_quantity=delta_quantity,
            quantity_before=qty_before,
            quantity_after=qty_after,
            reason=reason.strip(),
            adjusted_by=user_id,
        )
        session.add(adjustment)

        # Ghi nhật ký kiểm toán
        audit_log = AuditLog(
            id=uuid.uuid4(),
            actor_id=user_id,
            action="STOCK_ADJUSTMENT",
            resource_type="inventory",
            resource_id=f"{clean_wh}:{clean_sku}",
            result=f"BEFORE={qty_before}, AFTER={qty_after}, DELTA={delta_quantity}",
        )
        session.add(audit_log)

        await session.commit()
        await session.refresh(adjustment)
        return adjustment

    @staticmethod
    async def list_adjustments(
        session: AsyncSession,
        sku: Optional[str] = None,
        warehouse_code: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[StockAdjustment]:
        """Lấy lịch sử các phiếu kiểm kê điều chỉnh tồn kho."""
        stmt = select(StockAdjustment)
        if sku:
            stmt = stmt.where(StockAdjustment.sku == sku.strip().upper())
        if warehouse_code:
            stmt = stmt.where(StockAdjustment.warehouse_code == warehouse_code.strip().upper())

        stmt = stmt.order_by(StockAdjustment.created_at.desc()).limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all())
