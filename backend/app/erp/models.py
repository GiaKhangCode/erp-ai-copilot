import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import (
    String,
    Text,
    Boolean,
    Numeric,
    Integer,
    DateTime,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "erp"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="sales_rep", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'inactive')", name="check_customer_status"),
        {"schema": "erp"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")

    sales_orders: Mapped[List["SalesOrder"]] = relationship("SalesOrder", back_populates="customer")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("unit_price >= 0", name="check_product_unit_price"),
        {"schema": "erp"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sku: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    inventory_items: Mapped[List["Inventory"]] = relationship("Inventory", back_populates="product")
    order_items: Mapped[List["SalesOrderItem"]] = relationship("SalesOrderItem", back_populates="product")


class Warehouse(Base):
    __tablename__ = "warehouses"
    __table_args__ = {"schema": "erp"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)

    inventories: Mapped[List["Inventory"]] = relationship("Inventory", back_populates="warehouse")


class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = (
        CheckConstraint("quantity_on_hand >= 0", name="check_inventory_on_hand"),
        CheckConstraint("quantity_reserved >= 0", name="check_inventory_reserved"),
        CheckConstraint("quantity_reserved <= quantity_on_hand", name="check_reserved_le_on_hand"),
        {"schema": "erp"},
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("erp.products.id"), primary_key=True
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("erp.warehouses.id"), primary_key=True
    )
    quantity_on_hand: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quantity_reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    product: Mapped["Product"] = relationship("Product", back_populates="inventory_items")
    warehouse: Mapped["Warehouse"] = relationship("Warehouse", back_populates="inventories")

    @property
    def available_quantity(self) -> int:
        return self.quantity_on_hand - self.quantity_reserved


class SalesOrder(Base):
    __tablename__ = "sales_orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'pending_approval', 'confirmed', 'cancelled')",
            name="check_sales_order_status",
        ),
        CheckConstraint("total_amount >= 0", name="check_sales_order_total_amount"),
        {"schema": "erp"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_number: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("erp.customers.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, default="draft", nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    customer: Mapped["Customer"] = relationship("Customer", back_populates="sales_orders")
    items: Mapped[List["SalesOrderItem"]] = relationship(
        "SalesOrderItem", back_populates="order", cascade="all, delete-orphan"
    )

    @property
    def customer_name(self) -> Optional[str]:
        return self.customer.name if self.customer else None

    @property
    def customer_code(self) -> Optional[str]:
        return self.customer.code if self.customer else None


class SalesOrderItem(Base):
    __tablename__ = "sales_order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="check_order_item_quantity"),
        CheckConstraint("unit_price >= 0", name="check_order_item_unit_price"),
        {"schema": "erp"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("erp.sales_orders.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("erp.products.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    order: Mapped["SalesOrder"] = relationship("SalesOrder", back_populates="items")
    product: Mapped["Product"] = relationship("Product", back_populates="order_items")

    @property
    def sku(self) -> str:
        return self.product.sku if self.product else ""

    @property
    def product_name(self) -> str:
        return self.product.name if self.product else ""


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'expired')",
            name="check_approval_status",
        ),
        {"schema": "erp"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(Text, default="pending", nullable=False)
    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = {"schema": "erp"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str] = mapped_column(Text, nullable=False)
    resource_id: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("key", "actor_id", name="uq_idempotency_key_actor"),
        {"schema": "erp"},
    )

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_ref: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
