from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundException
from app.erp.models import Product


class ProductService:
    @staticmethod
    async def get_by_sku(session: AsyncSession, sku: str) -> Product:
        """Tra cứu chi tiết sản phẩm theo SKU."""
        stmt = select(Product).where(Product.sku == sku)
        result = await session.execute(stmt)
        product = result.scalar_one_or_none()
        if not product:
            raise NotFoundException(
                f"Không tìm thấy sản phẩm với SKU '{sku}'",
                code="PRODUCT_NOT_FOUND",
            )
        return product

    @staticmethod
    async def list_products(
        session: AsyncSession,
        limit: int = 50,
        offset: int = 0,
        is_active: Optional[bool] = None,
    ) -> List[Product]:
        """Lấy danh sách sản phẩm và bảng giá niêm yết."""
        stmt = select(Product)
        if is_active is not None:
            stmt = stmt.where(Product.is_active == is_active)
        stmt = stmt.order_by(Product.sku).limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all())
