from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundException
from app.erp.models import Customer


class CustomerService:
    @staticmethod
    async def get_by_code(session: AsyncSession, code: str) -> Customer:
        """Tra cứu thông tin khách hàng theo mã code."""
        stmt = select(Customer).where(Customer.code == code)
        result = await session.execute(stmt)
        customer = result.scalar_one_or_none()
        if not customer:
            raise NotFoundException(
                f"Không tìm thấy khách hàng với mã '{code}'",
                code="CUSTOMER_NOT_FOUND",
            )
        return customer

    @staticmethod
    async def list_customers(
        session: AsyncSession,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> List[Customer]:
        """Lấy danh sách khách hàng có phân trang và lọc trạng thái."""
        stmt = select(Customer)
        if status:
            stmt = stmt.where(Customer.status == status)
        stmt = stmt.order_by(Customer.code).limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all())
