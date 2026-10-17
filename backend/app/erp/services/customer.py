import uuid
from decimal import Decimal
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
    async def get_by_id(session: AsyncSession, customer_id) -> Customer:
        stmt = select(Customer).where(Customer.id == customer_id)
        result = await session.execute(stmt)
        customer = result.scalar_one_or_none()
        if not customer:
            raise NotFoundException(
                f"Không tìm thấy khách hàng với ID '{customer_id}'",
                code="CUSTOMER_NOT_FOUND",
            )
        return customer

    @staticmethod
    async def check_credit_limit(
        session: AsyncSession,
        customer_id_or_code: str,
        additional_amount: Optional[Decimal] = Decimal("0"),
    ) -> dict:
        """Kiểm tra hạn mức công nợ và tỷ lệ sử dụng tín dụng của khách hàng."""
        query_str = str(customer_id_or_code).strip()
        customer = None

        # 1. Thử theo UUID
        try:
            cust_uuid = uuid.UUID(query_str)
            stmt = select(Customer).where(Customer.id == cust_uuid)
            res = await session.execute(stmt)
            customer = res.scalar_one_or_none()
        except ValueError:
            pass

        # 2. Thử theo Code chính xác hoặc không phân biệt hoa thường
        if not customer:
            stmt = select(Customer).where(Customer.code.ilike(query_str))
            res = await session.execute(stmt)
            customer = res.scalar_one_or_none()

        # 3. Thử chuẩn hóa mã code (ví dụ: CUS-001 -> CUS-0001)
        if not customer and query_str.upper().startswith("CUS-"):
            parts = query_str.split("-")
            if len(parts) == 2 and parts[1].isdigit():
                padded_code = f"CUS-{int(parts[1]):04d}"
                stmt = select(Customer).where(Customer.code == padded_code)
                res = await session.execute(stmt)
                customer = res.scalar_one_or_none()

        # 4. Thử tìm theo tên khách hàng
        if not customer:
            stmt = select(Customer).where(Customer.name.ilike(f"%{query_str}%"))
            res = await session.execute(stmt)
            customer = res.scalar_one_or_none()

        if not customer:
            raise NotFoundException(
                f"Không tìm thấy khách hàng: '{query_str}'",
                code="CUSTOMER_NOT_FOUND",
            )

        limit = Decimal(str(customer.credit_limit or 50000000))
        debt = Decimal(str(customer.current_debt or 0))
        new_debt = debt + Decimal(str(additional_amount or 0))
        available = limit - new_debt
        utilization = float(new_debt / limit * 100) if limit > 0 else 100.0
        is_exceeded = new_debt > limit

        return {
            "customer_id": customer.id,
            "customer_code": customer.code,
            "customer_name": customer.name,
            "credit_limit": limit,
            "current_debt": debt,
            "additional_amount": Decimal(str(additional_amount or 0)),
            "projected_debt": new_debt,
            "available_credit": available,
            "credit_utilization_rate": round(utilization, 2),
            "is_exceeded": is_exceeded,
            "status": "EXCEEDED" if is_exceeded else "GOOD",
        }

    @staticmethod
    async def list_customers(
        session: AsyncSession,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Customer]:
        """Lấy danh sách khách hàng có phân trang, lọc trạng thái và tìm kiếm theo tên hoặc mã code."""
        stmt = select(Customer)
        if status:
            stmt = stmt.where(Customer.status == status)
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where((Customer.name.ilike(pattern)) | (Customer.code.ilike(pattern)))
        stmt = stmt.order_by(Customer.code).limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create_customer(session: AsyncSession, payload) -> Customer:
        """Tạo mới hồ sơ khách hàng."""
        clean_code = payload.code.strip().upper()
        stmt = select(Customer).where(Customer.code == clean_code)
        res = await session.execute(stmt)
        if res.scalar_one_or_none():
            from app.core.errors import AppException
            raise AppException(
                status_code=400,
                code="CUSTOMER_EXISTS",
                message=f"Khách hàng với mã '{clean_code}' đã tồn tại trong hệ thống.",
            )

        customer = Customer(
            id=uuid.uuid4(),
            code=clean_code,
            name=payload.name.strip(),
            email=payload.email.strip() if payload.email else None,
            phone=payload.phone.strip() if payload.phone else None,
            address=payload.address.strip() if payload.address else None,
            credit_limit=payload.credit_limit or Decimal("50000000"),
            current_debt=Decimal("0"),
            status=payload.status or "active",
        )
        session.add(customer)
        await session.commit()
        await session.refresh(customer)
        return customer

    @staticmethod
    async def update_customer(session: AsyncSession, customer_id: uuid.UUID, payload) -> Customer:
        """Cập nhật thông tin khách hàng."""
        customer = await CustomerService.get_by_id(session, customer_id)
        if payload.name is not None:
            customer.name = payload.name.strip()
        if payload.email is not None:
            customer.email = payload.email.strip() if payload.email else None
        if payload.phone is not None:
            customer.phone = payload.phone.strip() if payload.phone else None
        if payload.address is not None:
            customer.address = payload.address.strip() if payload.address else None
        if payload.credit_limit is not None:
            customer.credit_limit = payload.credit_limit
        if payload.status is not None:
            customer.status = payload.status

        await session.commit()
        await session.refresh(customer)
        return customer

    @staticmethod
    async def delete_customer(session: AsyncSession, customer_id: uuid.UUID) -> Customer:
        """Soft delete khách hàng: chuyển trạng thái sang inactive để ngừng giao dịch."""
        customer = await CustomerService.get_by_id(session, customer_id)
        customer.status = "inactive"
        await session.commit()
        await session.refresh(customer)
        return customer

