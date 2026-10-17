import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.auth.dependencies import get_current_user, require_permission
from app.erp.models import User
from app.erp.schemas import PaymentCreate, PaymentResponse
from app.erp.services.payment import PaymentService

router = APIRouter(prefix="/payments", tags=["Payments & AR"])


@router.post("", response_model=PaymentResponse)
async def create_payment(
    payload: PaymentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("payments:create")),
):
    """
    Tạo phiếu thu tiền và cấn trừ công nợ bán hàng.
    Quyền yêu cầu: payments:create
    """
    client_ip = request.client.host if request.client else None
    actor_role = getattr(current_user, "role", "unknown")
    if hasattr(current_user, "roles") and current_user.roles:
        actor_role = current_user.roles[0].code

    res = await PaymentService.create_payment(
        session=db,
        payload=payload,
        received_by=current_user.id,
        actor_email=current_user.email,
        actor_role=actor_role,
        ip_address=client_ip,
    )
    return res


@router.get("", response_model=List[PaymentResponse])
async def list_payments(
    customer_id: Optional[uuid.UUID] = Query(None, description="Lọc theo khách hàng"),
    order_id: Optional[uuid.UUID] = Query(None, description="Lọc theo đơn hàng"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("payments:read")),
):
    """
    Xem danh sách phiếu thu tiền bán hàng.
    Quyền yêu cầu: payments:read
    """
    return await PaymentService.list_payments(
        session=db,
        customer_id=customer_id,
        order_id=order_id,
        limit=limit,
        offset=offset,
    )
