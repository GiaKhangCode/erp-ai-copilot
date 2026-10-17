import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.auth.dependencies import (
    get_current_user,
    require_permission,
    get_current_user_permissions,
)
from app.core.errors import AppException
from app.erp.models import User
from app.erp.schemas import (
    CustomerResponse,
    ProductResponse,
    InventoryResponse,
    OrderDraftCreate,
    OrderResponse,
    RevenueReportResponse,
    StockAdjustmentCreate,
    StockAdjustmentResponse,
)
from app.erp.services import (
    CustomerService,
    ProductService,
    InventoryService,
    SalesOrderService,
    ReportingService,
)

router = APIRouter(tags=["ERP Domain"])


# ==========================================
# Customers Endpoints
# ==========================================
@router.get("/customers", response_model=List[CustomerResponse])
async def list_customers(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái 'active' hoặc 'inactive'"),
    current_user: User = Depends(require_permission("customers:read")),
    db: AsyncSession = Depends(get_db),
):
    """Lấy danh sách khách hàng có phân trang và lọc theo trạng thái."""
    return await CustomerService.list_customers(db, limit=limit, offset=offset, status=status)


@router.get("/customers/{code}", response_model=CustomerResponse)
async def get_customer(
    code: str,
    current_user: User = Depends(require_permission("customers:read")),
    db: AsyncSession = Depends(get_db),
):
    """Tra cứu thông tin chi tiết một khách hàng theo mã code (ví dụ: CUS-0001)."""
    return await CustomerService.get_by_code(db, code=code)


# ==========================================
# Products Endpoints
# ==========================================
@router.get("/products", response_model=List[ProductResponse])
async def list_products(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    is_active: Optional[bool] = Query(None, description="Lọc theo trạng thái kinh doanh"),
    current_user: User = Depends(require_permission("products:read")),
    db: AsyncSession = Depends(get_db),
):
    """Lấy danh sách sản phẩm và bảng giá niêm yết."""
    return await ProductService.list_products(db, limit=limit, offset=offset, is_active=is_active)


@router.get("/products/{sku}", response_model=ProductResponse)
async def get_product(
    sku: str,
    current_user: User = Depends(require_permission("products:read")),
    db: AsyncSession = Depends(get_db),
):
    """Tra cứu chi tiết sản phẩm theo mã SKU (ví dụ: SKU-001)."""
    return await ProductService.get_by_sku(db, sku=sku)


# ==========================================
# Inventory Endpoints
# ==========================================
@router.get("/inventory", response_model=List[InventoryResponse])
async def get_inventory(
    sku: Optional[str] = Query(None, description="Mã SKU sản phẩm cần kiểm tra"),
    warehouse_code: Optional[str] = Query(None, description="Mã kho cần lọc (ví dụ: WH-HN)"),
    current_user: User = Depends(require_permission("inventory:read")),
    db: AsyncSession = Depends(get_db),
):
    """
    Tra cứu tồn kho theo thời gian thực.
    Trả về số lượng tồn kho (on_hand), số lượng đang giữ (reserved) và số lượng khả dụng (available).
    """
    return await InventoryService.get_inventory(db, sku=sku, warehouse_code=warehouse_code)


@router.post("/inventory/adjust", response_model=StockAdjustmentResponse, status_code=status.HTTP_201_CREATED)
async def adjust_inventory(
    payload: StockAdjustmentCreate,
    current_user: User = Depends(require_permission("inventory:write")),
    db: AsyncSession = Depends(get_db),
):
    """
    Tạo phiếu kiểm kê và điều chỉnh tồn kho thực tế.
    Yêu cầu quyền 'inventory:write' (thủ kho hoặc admin).
    """
    return await InventoryService.adjust_inventory(
        session=db,
        sku=payload.sku,
        warehouse_code=payload.warehouse_code,
        delta_quantity=payload.delta_quantity,
        reason=payload.reason,
        user_id=current_user.id,
    )


@router.get("/inventory/adjustments", response_model=List[StockAdjustmentResponse])
async def list_inventory_adjustments(
    sku: Optional[str] = Query(None, description="Lọc theo mã SKU"),
    warehouse_code: Optional[str] = Query(None, description="Lọc theo mã kho"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_permission("inventory:read")),
    db: AsyncSession = Depends(get_db),
):
    """
    Lấy danh sách lịch sử các phiếu kiểm kê điều chỉnh tồn kho.
    """
    return await InventoryService.list_adjustments(
        session=db,
        sku=sku,
        warehouse_code=warehouse_code,
        limit=limit,
        offset=offset,
    )


# ==========================================
# Sales Orders Endpoints
# ==========================================
@router.get("/sales-orders", response_model=List[OrderResponse])
async def list_sales_orders(
    customer_code: Optional[str] = Query(None, description="Lọc theo mã khách hàng"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái ('draft', 'confirmed', ...)"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_permission("orders:read")),
    user_permissions: set[str] = Depends(get_current_user_permissions),
    db: AsyncSession = Depends(get_db),
):
    """
    Lấy danh sách đơn hàng bán.
    Tự động áp dụng Data Scoping:
    - Nếu không có quyền 'orders:read_all', nhân viên (sales_rep) chỉ xem được đơn hàng do chính mình tạo.
    """
    has_read_all = (
        "*" in user_permissions
        or "orders:read_all" in user_permissions
        or "inventory:write" in user_permissions
        or current_user.role in ["admin", "director", "sales_manager", "warehouse_keeper"]
    )
    created_by_filter = None if has_read_all else current_user.id

    return await SalesOrderService.list_orders(
        db,
        customer_code=customer_code,
        status=status,
        limit=limit,
        offset=offset,
        created_by=created_by_filter,
    )


@router.get("/sales-orders/{order_id}", response_model=OrderResponse)
async def get_sales_order(
    order_id: uuid.UUID,
    current_user: User = Depends(require_permission("orders:read")),
    user_permissions: set[str] = Depends(get_current_user_permissions),
    db: AsyncSession = Depends(get_db),
):
    """
    Tra cứu chi tiết đơn hàng bao gồm danh sách các dòng sản phẩm.
    Áp dụng Object-Level Authorization: Chặn nhân viên xem đơn hàng của đồng nghiệp nếu không có quyền 'orders:read_all'.
    """
    order = await SalesOrderService.get_order_by_id(db, order_id=order_id)
    has_read_all = (
        "*" in user_permissions
        or "orders:read_all" in user_permissions
        or "inventory:write" in user_permissions
        or current_user.role in ["admin", "director", "sales_manager", "warehouse_keeper"]
    )
    if not has_read_all and order.created_by != current_user.id:
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            message="Bạn không có quyền truy cập thông tin đơn hàng này.",
        )
    return order


@router.post(
    "/sales-orders/drafts",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_sales_order_draft(
    payload: OrderDraftCreate,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: User = Depends(require_permission("orders:create")),
    db: AsyncSession = Depends(get_db),
):
    """
    Tạo đơn hàng nháp (draft). Yêu cầu quyền 'orders:create'.
    Hệ thống sẽ tự động gán actor_id là ID của người dùng đăng nhập hiện tại.
    """
    return await SalesOrderService.create_order_draft(
        db,
        payload=payload,
        actor_id=current_user.id,
        idempotency_key=idempotency_key,
    )


# ==========================================
# Reporting Endpoints (UC-02)
# ==========================================
@router.get("/reporting/revenue", response_model=RevenueReportResponse, tags=["Reporting"])
async def get_revenue_report(
    year: Optional[int] = Query(None, description="Năm báo cáo (ví dụ: 2026)"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Tháng báo cáo (1-12)"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái đơn hàng"),
    current_user: User = Depends(require_permission("reports:revenue_view")),
    db: AsyncSession = Depends(get_db),
):
    """
    Báo cáo doanh thu theo kỳ và tháng (Use Case UC-02).
    Chỉ dành cho người dùng có quyền 'reports:revenue_view' (admin, director, sales_manager).
    """
    return await ReportingService.get_revenue(db, year=year, month=month, status=status)

