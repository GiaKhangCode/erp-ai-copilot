from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field


# Customer schemas
class CustomerBase(BaseModel):
    code: str
    name: str
    email: Optional[str] = None
    status: str = "active"


class CustomerResponse(CustomerBase):
    id: UUID

    class Config:
        from_attributes = True


# Product schemas
class ProductBase(BaseModel):
    sku: str
    name: str
    unit_price: Decimal
    is_active: bool = True


class ProductResponse(ProductBase):
    id: UUID

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


class OrderResponse(BaseModel):
    id: UUID
    order_number: str
    customer_id: UUID
    status: str
    total_amount: Decimal
    created_at: datetime
    items: List[OrderItemResponse] = []

    class Config:
        from_attributes = True
