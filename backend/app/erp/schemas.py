from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


# Customer schemas
class CustomerBase(BaseModel):
    code: str
    name: str
    email: Optional[str] = None
    status: str = "active"
    credit_limit: Decimal = Field(default=Decimal("50000000"))
    current_debt: Decimal = Field(default=Decimal("0"))
    phone: Optional[str] = None
    address: Optional[str] = None


class CustomerCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=50, description="Mã khách hàng (ví dụ: CUS-0010)")
    name: str = Field(..., min_length=2, max_length=255, description="Tên doanh nghiệp hoặc cá nhân")
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    credit_limit: Optional[Decimal] = Field(default=Decimal("50000000"), ge=Decimal("0"))
    status: str = Field(default="active", pattern="^(active|inactive)$")


class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    credit_limit: Optional[Decimal] = Field(None, ge=Decimal("0"))
    status: Optional[str] = Field(None, pattern="^(active|inactive)$")


class CustomerResponse(CustomerBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)


class CustomerCreditCheckResponse(BaseModel):
    customer_id: UUID
    customer_code: str
    customer_name: str
    credit_limit: Decimal
    current_debt: Decimal
    available_credit: Decimal
    credit_utilization_rate: float
    is_exceeded: bool
    currency: str = "VND"


# Product schemas
class ProductBase(BaseModel):
    sku: str
    name: str
    unit_price: Decimal
    cost_price: Decimal = Field(default=Decimal("0.00"))
    is_active: bool = True


class ProductCreate(BaseModel):
    sku: str = Field(..., min_length=2, max_length=50, description="Mã SKU (ví dụ: SKU-010)")
    name: str = Field(..., min_length=2, max_length=255, description="Tên sản phẩm")
    unit_price: Decimal = Field(..., gt=Decimal("0"), description="Giá bán niêm yết")
    cost_price: Optional[Decimal] = Field(default=Decimal("0.00"), ge=Decimal("0"), description="Giá vốn (COGS)")
    is_active: bool = Field(default=True)


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    unit_price: Optional[Decimal] = Field(None, gt=Decimal("0"))
    cost_price: Optional[Decimal] = Field(None, ge=Decimal("0"))
    is_active: Optional[bool] = None


class ProductResponse(ProductBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)


class OrderCancelRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=500, description="Lý do hủy đơn hàng")



# Inventory schemas
class InventoryResponse(BaseModel):
    product_sku: str
    product_name: str
    warehouse_code: str
    warehouse_name: str
    quantity_on_hand: int
    quantity_reserved: int
    quantity_available: int


# Sales Order schemas
class OrderItemDraft(BaseModel):
    sku: str
    quantity: int = Field(gt=0, description="Quantity must be greater than zero")
    unit_price: Optional[Decimal] = Field(None, ge=0, description="Đơn giá thỏa thuận trong PO của khách (nếu có)")


class OrderDraftCreate(BaseModel):
    customer_code: str
    items: List[OrderItemDraft]
    customer_po_number: Optional[str] = Field(None, max_length=100, description="Số đơn đặt hàng PO của đối tác")
    requested_delivery_date: Optional[str] = None
    source_document_id: Optional[UUID] = None


class OrderDraftUpdate(BaseModel):
    customer_code: Optional[str] = None
    items: List[OrderItemDraft]
    customer_po_number: Optional[str] = Field(None, max_length=100, description="Số đơn đặt hàng PO của đối tác")
    requested_delivery_date: Optional[str] = None


class OrderItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    sku: str
    product_name: str
    quantity: int
    unit_price: Decimal
    catalog_price: Optional[Decimal] = None
    allocated_quantity: Optional[int] = 0
    backorder_quantity: Optional[int] = 0
    line_total: Decimal
    model_config = ConfigDict(from_attributes=True)


class OrderResponse(BaseModel):
    id: UUID
    order_number: str
    customer_po_number: Optional[str] = None
    customer_id: UUID
    customer_name: Optional[str] = None
    customer_code: Optional[str] = None
    status: str
    total_amount: Decimal
    created_at: datetime
    items: List[OrderItemResponse] = []
    model_config = ConfigDict(from_attributes=True)


# User & Auth Schemas
class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    phone: Optional[str] = None
    department: Optional[str] = None
    job_title: Optional[str] = None
    is_superuser: bool = False
    roles: List[str] = []
    permissions: List[str] = []
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: Optional[int] = None
    user: UserResponse



# Reporting Schemas
class RevenueReportItem(BaseModel):
    period: str
    order_count: int
    total_revenue: Decimal


class RevenueReportResponse(BaseModel):
    metric_id: str = "revenue_summary"
    period: Optional[str] = None
    total_revenue: Decimal
    total_orders: int
    breakdown: List[RevenueReportItem] = []


# Stock Adjustment Schemas
class StockAdjustmentCreate(BaseModel):
    sku: str = Field(..., min_length=1, description="Mã SKU sản phẩm cần điều chỉnh")
    warehouse_code: str = Field(..., min_length=1, description="Mã kho (ví dụ: WH-HN, WH-HCM)")
    delta_quantity: int = Field(..., description="Số lượng tăng (+) hoặc giảm (-)")
    reason: str = Field(..., min_length=3, max_length=500, description="Lý do điều chỉnh kiểm kê")


class StockAdjustmentResponse(BaseModel):
    id: UUID
    sku: str
    warehouse_code: str
    delta_quantity: int
    quantity_before: int
    quantity_after: int
    reason: str
    adjusted_by: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Phase 3: Executive Analytics & Sales Leaderboard Schemas
# ==========================================
class SalesLeaderboardItem(BaseModel):
    sales_id: UUID
    sales_name: str
    sales_email: str
    total_revenue: Decimal
    total_orders: int
    aov: Decimal
    rank: int


class SalesLeaderboardResponse(BaseModel):
    metric_id: str = "sales_leaderboard"
    period: str
    total_sales_reps: int
    items: List[SalesLeaderboardItem] = []


class FinancialProfitabilityResponse(BaseModel):
    metric_id: str = "financial_profitability"
    period: str
    total_revenue: Decimal
    total_cogs: Decimal
    gross_profit: Decimal
    gross_margin_percent: float
    total_orders: int


class DebtAgingBucket(BaseModel):
    bucket: str
    label: str
    amount: Decimal
    customer_count: int


class TopDebtorItem(BaseModel):
    customer_id: UUID
    customer_code: str
    customer_name: str
    credit_limit: Decimal
    current_debt: Decimal
    credit_utilization_rate: float
    is_over_limit: bool


class DebtAgingReportResponse(BaseModel):
    metric_id: str = "debt_aging_analysis"
    total_debt: Decimal
    total_credit_limit: Decimal
    overall_utilization_rate: float
    over_limit_customers_count: int
    buckets: List[DebtAgingBucket] = []
    top_debtors: List[TopDebtorItem] = []


# ==========================================
# Payment & AR Schemas
# ==========================================
class PaymentCreate(BaseModel):
    customer_id: UUID
    order_id: Optional[UUID] = None
    amount: Decimal = Field(..., gt=Decimal("0"), description="Số tiền thu (VND)")
    payment_method: str = Field(default="bank_transfer", description="Phương thức: bank_transfer, cash, credit_card")
    reference_code: Optional[str] = Field(None, description="Mã giao dịch ngân hàng / hóa đơn thu")
    note: Optional[str] = Field(None, description="Ghi chú thu tiền")


class PaymentResponse(BaseModel):
    id: UUID
    payment_number: str
    customer_id: UUID
    customer_name: Optional[str] = None
    customer_code: Optional[str] = None
    order_id: Optional[UUID] = None
    order_number: Optional[str] = None
    amount: Decimal
    payment_method: str
    reference_code: Optional[str] = None
    note: Optional[str] = None
    received_by: UUID
    receiver_name: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Stock Transfer Schemas
# ==========================================
class StockTransferCreate(BaseModel):
    source_warehouse_code: str = Field(..., description="Mã kho xuất hàng (VD: WH-HN)")
    target_warehouse_code: str = Field(..., description="Mã kho nhập hàng (VD: WH-HCM)")
    sku: str = Field(..., description="Mã SKU sản phẩm cần chuyển")
    quantity: int = Field(..., gt=0, description="Số lượng điều chuyển")
    reason: str = Field(..., min_length=3, description="Lý do điều chuyển kho nội bộ")


class StockTransferResponse(BaseModel):
    id: UUID
    transfer_number: str
    sku: str
    product_name: str
    source_warehouse_code: str
    source_warehouse_name: str
    target_warehouse_code: str
    target_warehouse_name: str
    quantity: int
    reason: str
    transferred_by: UUID
    transferrer_name: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Supplier & Purchasing Schemas
# ==========================================
class SupplierCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=50, description="Mã nhà cung cấp (VD: NCC-HP)")
    name: str = Field(..., min_length=2, max_length=255, description="Tên nhà cung cấp")
    tax_code: Optional[str] = None
    contact_email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    status: Optional[str] = "active"


class SupplierResponse(BaseModel):
    id: UUID
    code: str
    name: str
    tax_code: Optional[str] = None
    contact_email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderItemCreate(BaseModel):
    sku: str = Field(..., description="Mã SKU sản phẩm")
    quantity: int = Field(..., gt=0, description="Số lượng đặt mua")
    unit_price: Decimal = Field(..., ge=0, description="Đơn giá nhập hàng (VND)")


class PurchaseOrderItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    sku: str
    product_name: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderCreate(BaseModel):
    supplier_code: str = Field(..., description="Mã nhà cung cấp")
    warehouse_code: str = Field(..., description="Mã kho nhập hàng (VD: WH-HN, WH-HCM)")
    items: List[PurchaseOrderItemCreate]
    notes: Optional[str] = None


class PurchaseOrderResponse(BaseModel):
    id: UUID
    po_number: str
    supplier_id: UUID
    supplier_code: str
    supplier_name: str
    warehouse_id: UUID
    warehouse_code: str
    warehouse_name: str
    status: str
    total_amount: Decimal
    notes: Optional[str] = None
    created_by: UUID
    creator_name: Optional[str] = None
    created_at: datetime
    items: List[PurchaseOrderItemResponse] = []
    model_config = ConfigDict(from_attributes=True)


