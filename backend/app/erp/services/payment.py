import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from fastapi import HTTPException, status

from app.erp.models import Payment, Customer, SalesOrder, User
from app.erp.schemas import PaymentCreate
from app.erp.services.audit import AuditService


class PaymentService:
    @staticmethod
    async def create_payment(
        session: AsyncSession,
        payload: PaymentCreate,
        received_by: uuid.UUID,
        actor_email: str = "system",
        actor_role: str = "unknown",
        ip_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Tạo phiếu thu tiền, cấn trừ nợ khách hàng và ghi audit log"""
        # 1. Kiểm tra khách hàng tồn tại
        cust_stmt = select(Customer).where(Customer.id == payload.customer_id)
        cust_res = await session.execute(cust_stmt)
        customer = cust_res.scalar_one_or_none()
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy khách hàng với ID {payload.customer_id}"
            )

        # 2. Kiểm tra đơn hàng nếu có
        order: Optional[SalesOrder] = None
        if payload.order_id:
            ord_stmt = select(SalesOrder).where(
                SalesOrder.id == payload.order_id,
                SalesOrder.customer_id == payload.customer_id
            )
            ord_res = await session.execute(ord_stmt)
            order = ord_res.scalar_one_or_none()
            if not order:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Không tìm thấy đơn hàng {payload.order_id} thuộc khách hàng này"
                )

        # 3. Tạo mã phiếu thu độc nhất: PMT-YYYYMMDD-XXXX
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        rand_suffix = uuid.uuid4().hex[:4].upper()
        payment_number = f"PMT-{today_str}-{rand_suffix}"

        payment = Payment(
            id=uuid.uuid4(),
            payment_number=payment_number,
            customer_id=customer.id,
            order_id=order.id if order else None,
            amount=payload.amount,
            payment_method=payload.payment_method,
            reference_code=payload.reference_code,
            note=payload.note,
            received_by=received_by,
        )
        session.add(payment)

        # 4. Cấn trừ nợ của khách hàng
        old_debt = customer.current_debt
        # Đảm bảo nợ không bị âm vô lý nếu khách thanh toán nhiều hơn nợ
        new_debt = max(Decimal("0.00"), customer.current_debt - payload.amount)
        customer.current_debt = new_debt

        await session.commit()
        await session.refresh(payment)

        # 5. Ghi Audit Log tự động
        await AuditService.log_activity(
            session=session,
            action="PAYMENT_RECEIVED",
            actor=received_by,
            actor_email=actor_email,
            actor_role=actor_role,
            resource_type="Payment",
            resource_id=str(payment.id),
            ip_address=ip_address,
            details={
                "payment_number": payment.payment_number,
                "customer_code": customer.code,
                "customer_name": customer.name,
                "order_number": order.order_number if order else None,
                "amount": float(payment.amount),
                "payment_method": payment.payment_method,
                "old_debt": float(old_debt),
                "new_debt": float(new_debt),
            },
        )

        return {
            "id": payment.id,
            "payment_number": payment.payment_number,
            "customer_id": customer.id,
            "customer_name": customer.name,
            "customer_code": customer.code,
            "order_id": order.id if order else None,
            "order_number": order.order_number if order else None,
            "amount": payment.amount,
            "payment_method": payment.payment_method,
            "reference_code": payment.reference_code,
            "note": payment.note,
            "received_by": payment.received_by,
            "created_at": payment.created_at,
            "new_debt": new_debt,
        }

    @staticmethod
    async def list_payments(
        session: AsyncSession,
        customer_id: Optional[uuid.UUID] = None,
        order_id: Optional[uuid.UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Lấy danh sách các phiếu thu tiền"""
        stmt = (
            select(
                Payment,
                Customer.name.label("customer_name"),
                Customer.code.label("customer_code"),
                SalesOrder.order_number.label("order_number"),
                User.full_name.label("receiver_name"),
            )
            .join(Customer, Payment.customer_id == Customer.id)
            .outerjoin(SalesOrder, Payment.order_id == SalesOrder.id)
            .outerjoin(User, Payment.received_by == User.id)
            .order_by(desc(Payment.created_at))
            .limit(limit)
            .offset(offset)
        )

        if customer_id:
            stmt = stmt.where(Payment.customer_id == customer_id)
        if order_id:
            stmt = stmt.where(Payment.order_id == order_id)

        res = await session.execute(stmt)
        rows = res.all()

        results = []
        for payment, cust_name, cust_code, order_no, rec_name in rows:
            results.append({
                "id": payment.id,
                "payment_number": payment.payment_number,
                "customer_id": payment.customer_id,
                "customer_name": cust_name,
                "customer_code": cust_code,
                "order_id": payment.order_id,
                "order_number": order_no,
                "amount": payment.amount,
                "payment_method": payment.payment_method,
                "reference_code": payment.reference_code,
                "note": payment.note,
                "received_by": payment.received_by,
                "receiver_name": rec_name,
                "created_at": payment.created_at,
            })
        return results
