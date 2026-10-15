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
    is_active: bool = True


class ProductResponse(ProductBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)


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


class OrderDraftCreate(BaseModel):
    customer_code: str
    items: List[OrderItemDraft]
    requested_delivery_date: Optional[str] = None
    source_document_id: Optional[UUID] = None


class OrderItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    sku: str
    product_name: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    model_config = ConfigDict(from_attributes=True)


class OrderResponse(BaseModel):
    id: UUID
    order_number: str
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
