import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.auth.dependencies import require_permission
from app.erp.models import User
from app.erp.schemas import (
    SupplierCreate,
    SupplierResponse,
    PurchaseOrderCreate,
    PurchaseOrderResponse,
)
from app.erp.services.purchasing import PurchasingService

router = APIRouter(prefix="/purchasing", tags=["Purchasing & Suppliers"])


class CancelPORequest(BaseModel):
    reason: Optional[str] = "Hủy đơn mua hàng"


# ==========================================
# Supplier Endpoints
# ==========================================
@router.get(
    "/suppliers",
    response_model=List[SupplierResponse],
    summary="Lấy danh sách nhà cung cấp (Suppliers)",
)
async def list_suppliers(
    status: Optional[str] = Query(None, description="Lọc theo trạng thái active/inactive"),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_permission("purchasing:read")),
    db: AsyncSession = Depends(get_db),
):
    """Lấy danh sách các nhà cung cấp vật tư/sản phẩm."""
    return await PurchasingService.list_suppliers(db, status=status, limit=limit, offset=offset)


@router.post(
    "/suppliers",
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Thêm mới nhà cung cấp (Supplier)",
)
async def create_supplier(
    payload: SupplierCreate,
    current_user: User = Depends(require_permission("purchasing:create")),
    db: AsyncSession = Depends(get_db),
):
    """Tạo mới nhà cung cấp hàng hóa."""
    return await PurchasingService.create_supplier(db, payload=payload, actor_id=current_user.id)


# ==========================================
# Purchase Order (PO) Endpoints
# ==========================================
@router.get(
    "/orders",
    response_model=List[PurchaseOrderResponse],
    summary="Lấy danh sách đơn mua hàng PO",
)
async def list_purchase_orders(
    status: Optional[str] = Query(None, description="Lọc trạng thái: draft, ordered, received, cancelled"),
    supplier_code: Optional[str] = Query(None, description="Lọc theo mã nhà cung cấp"),
    warehouse_code: Optional[str] = Query(None, description="Lọc theo mã kho nhập"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_permission("purchasing:read")),
    db: AsyncSession = Depends(get_db),
):
    """Lấy danh sách đơn đặt mua hàng PO."""
    return await PurchasingService.list_purchase_orders(
        db,
        status=status,
        supplier_code=supplier_code,
        warehouse_code=warehouse_code,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/orders/{po_id}",
    response_model=PurchaseOrderResponse,
    summary="Lấy chi tiết đơn mua hàng PO theo ID",
)
async def get_purchase_order(
    po_id: uuid.UUID,
    current_user: User = Depends(require_permission("purchasing:read")),
    db: AsyncSession = Depends(get_db),
):
    """Lấy thông tin chi tiết một đơn đặt mua hàng PO."""
    return await PurchasingService.get_purchase_order(db, po_id=po_id)


@router.post(
    "/orders",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Lập đơn mua hàng PO mới",
)
async def create_purchase_order(
    payload: PurchaseOrderCreate,
    current_user: User = Depends(require_permission("purchasing:create")),
    db: AsyncSession = Depends(get_db),
):
    """
    Tạo đơn mua hàng PO:
    - Bắt buộc kiểm tra mã NCC và kho tiếp nhận.
    - Snapshot đơn giá nhập, tính tổng giá trị PO.
    - Lưu trạng thái ban đầu 'draft'.
    """
    return await PurchasingService.create_purchase_order(db, payload=payload, actor_id=current_user.id)


@router.post(
    "/orders/{po_id}/receive",
    response_model=PurchaseOrderResponse,
    summary="Thủ kho xác nhận Nhập kho đơn mua hàng PO",
)
async def receive_purchase_order(
    po_id: uuid.UUID,
    current_user: User = Depends(require_permission("purchasing:receive")),
    db: AsyncSession = Depends(get_db),
):
    """
    Nghiệp vụ Nhập kho Mua hàng:
    - Tự động cộng số lượng thực tế tồn kho 'quantity_on_hand' tại kho đích.
    - Đổi trạng thái PO thành 'received'.
    - Ghi nhận AuditLog.
    """
    return await PurchasingService.receive_purchase_order(db, po_id=po_id, actor_id=current_user.id)


@router.post(
    "/orders/{po_id}/cancel",
    response_model=PurchaseOrderResponse,
    summary="Hủy đơn mua hàng PO chưa nhập kho",
)
async def cancel_purchase_order(
    po_id: uuid.UUID,
    payload: Optional[CancelPORequest] = None,
    current_user: User = Depends(require_permission("purchasing:cancel")),
    db: AsyncSession = Depends(get_db),
):
    """Hủy đơn mua hàng chưa nhập kho."""
    reason = payload.reason if payload else "Hủy đơn mua hàng"
    return await PurchasingService.cancel_purchase_order(db, po_id=po_id, actor_id=current_user.id, reason=reason)
