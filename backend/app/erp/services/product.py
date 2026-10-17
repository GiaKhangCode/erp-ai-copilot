import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppException, NotFoundException
from app.erp.models import Product, Warehouse, Inventory


class ProductService:
    @staticmethod
    async def get_by_id(session: AsyncSession, product_id: uuid.UUID) -> Product:
        """Tra cứu chi tiết sản phẩm theo ID."""
        stmt = select(Product).where(Product.id == product_id)
        result = await session.execute(stmt)
        product = result.scalar_one_or_none()
        if not product:
            raise NotFoundException(
                f"Không tìm thấy sản phẩm với ID '{product_id}'",
                code="PRODUCT_NOT_FOUND",
            )
        return product

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
        search: Optional[str] = None,
    ) -> List[Product]:
        """Lấy danh sách sản phẩm và bảng giá niêm yết, hỗ trợ tìm kiếm theo tên hoặc mã SKU."""
        stmt = select(Product)
        if is_active is not None:
            stmt = stmt.where(Product.is_active == is_active)
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where((Product.name.ilike(pattern)) | (Product.sku.ilike(pattern)))
        stmt = stmt.order_by(Product.sku).limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create_product(session: AsyncSession, payload) -> Product:
        """Tạo mới sản phẩm và khởi tạo bản ghi tồn kho rỗng cho các kho hàng."""
        clean_sku = payload.sku.strip().upper()
        stmt = select(Product).where(Product.sku == clean_sku)
        res = await session.execute(stmt)
        if res.scalar_one_or_none():
            raise AppException(
                status_code=400,
                code="PRODUCT_EXISTS",
                message=f"Sản phẩm với mã SKU '{clean_sku}' đã tồn tại.",
            )

        product = Product(
            id=uuid.uuid4(),
            sku=clean_sku,
            name=payload.name.strip(),
            unit_price=payload.unit_price,
            cost_price=payload.cost_price or 0,
            is_active=payload.is_active if payload.is_active is not None else True,
        )
        session.add(product)
        await session.flush()

        # Tự động tạo bản ghi Inventory tồn kho cho các kho hiện có
        wh_res = await session.execute(select(Warehouse))
        warehouses = wh_res.scalars().all()
        for wh in warehouses:
            inv = Inventory(
                id=uuid.uuid4(),
                product_id=product.id,
                warehouse_id=wh.id,
                quantity_on_hand=0,
                quantity_reserved=0,
            )
            session.add(inv)

        await session.commit()
        await session.refresh(product)
        return product

    @staticmethod
    async def update_product(session: AsyncSession, product_id: uuid.UUID, payload) -> Product:
        """Cập nhật thông số giá bán, giá vốn và trạng thái kinh doanh của sản phẩm."""
        product = await ProductService.get_by_id(session, product_id)
        if payload.name is not None:
            product.name = payload.name.strip()
        if payload.unit_price is not None:
            product.unit_price = payload.unit_price
        if payload.cost_price is not None:
            product.cost_price = payload.cost_price
        if payload.is_active is not None:
            product.is_active = payload.is_active

        await session.commit()
        await session.refresh(product)
        return product

    @staticmethod
    async def delete_product(session: AsyncSession, product_id: uuid.UUID) -> Product:
        """Soft delete sản phẩm: chuyển is_active sang False để ngừng kinh doanh."""
        product = await ProductService.get_by_id(session, product_id)
        product.is_active = False
        await session.commit()
        await session.refresh(product)
        return product

