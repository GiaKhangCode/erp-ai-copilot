import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.auth.dependencies import get_optional_current_user
from app.erp.models import User
from app.erp.schemas import (
    CustomerResponse,
    ProductResponse,
    InventoryResponse,
    OrderDraftCreate,
    OrderResponse,
    RevenueReportResponse,
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
    db: AsyncSession = Depends(get_db),
):
    """Lấy danh sách khách hàng có phân trang và lọc theo trạng thái."""
    return await CustomerService.list_customers(db, limit=limit, offset=offset, status=status)


@router.get("/customers/{code}", response_model=CustomerResponse)
async def get_customer(
    code: str,
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
    db: AsyncSession = Depends(get_db),
):
    """Lấy danh sách sản phẩm và bảng giá niêm yết."""
    return await ProductService.list_products(db, limit=limit, offset=offset, is_active=is_active)


@router.get("/products/{sku}", response_model=ProductResponse)
async def get_product(
    sku: str,
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
    db: AsyncSession = Depends(get_db),
):
    """
    Tra cứu tồn kho theo thời gian thực.
    Trả về số lượng tồn kho (on_hand), số lượng đang giữ (reserved) và số lượng khả dụng (available).
    """
    return await InventoryService.get_inventory(db, sku=sku, warehouse_code=warehouse_code)


# ==========================================
# Sales Orders Endpoints
# ==========================================
@router.get("/sales-orders", response_model=List[OrderResponse])
async def list_sales_orders(
    customer_code: Optional[str] = Query(None, description="Lọc theo mã khách hàng"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái ('draft', 'confirmed', ...)"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Lấy danh sách đơn hàng bán."""
    return await SalesOrderService.list_orders(
        db, customer_code=customer_code, status=status, limit=limit, offset=offset
    )


@router.get("/sales-orders/{order_id}", response_model=OrderResponse)
async def get_sales_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Tra cứu chi tiết đơn hàng bao gồm danh sách các dòng sản phẩm."""
    return await SalesOrderService.get_order_by_id(db, order_id=order_id)


@router.post(
    "/sales-orders/drafts",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_sales_order_draft(
    payload: OrderDraftCreate,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Tạo đơn hàng nháp (draft).
    Hệ thống sẽ tự động:
    1. Kiểm tra sự tồn tại và tính hợp lệ của khách hàng và SKU.
    2. Snapshot giá bán trực tiếp từ danh mục sản phẩm (không tin giá từ client/LLM).
    3. Tự động tính toán tổng tiền đơn hàng trên máy chủ trong transaction.
    4. Hỗ trợ Idempotency-Key chống duplicate writes khi retry.
    5. Gán trạng thái 'draft' chờ duyệt.
    """
    actor_id = current_user.id if current_user else None
    return await SalesOrderService.create_order_draft(
        db,
        payload=payload,
        actor_id=actor_id,
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
    db: AsyncSession = Depends(get_db),
):
    """
    Báo cáo doanh thu theo kỳ và tháng (Use Case UC-02 & Tool get_revenue).
    Tính toán doanh thu tổng và phân rã chi tiết từ cơ sở dữ liệu.
    """
    return await ReportingService.get_revenue(db, year=year, month=month, status=status)
