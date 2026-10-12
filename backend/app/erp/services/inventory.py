from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.erp.models import Product, Warehouse, Inventory
from app.erp.schemas import InventoryResponse


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
