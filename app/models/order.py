"""Order — the central transactional record."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin
from app.models.enums import OrderStatus, SlotType, pg_enum
if TYPE_CHECKING:
    from app.models.order_event import OrderEvent
    from app.models.order_item import OrderItem
    from app.models.payment import Payment
    from app.models.shop import Shop
    from app.models.user import User
class Order(Base, TimestampMixin):
    __tablename__ = "orders"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(
        String(12), unique=True, nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shops.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    delivery_label: Mapped[str] = mapped_column(String(50), nullable=False)
    delivery_line1: Mapped[str] = mapped_column(String(255), nullable=False)
    delivery_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delivery_landmark: Mapped[str | None] = mapped_column(String(120), nullable=True)
    delivery_city: Mapped[str] = mapped_column(String(80), nullable=False)
    delivery_state: Mapped[str] = mapped_column(String(80), nullable=False)
    delivery_pincode: Mapped[str] = mapped_column(String(10), nullable=False)
    delivery_latitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    delivery_longitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    delivery_phone: Mapped[str] = mapped_column(String(15), nullable=False)
    slot_type: Mapped[SlotType] = mapped_column(
        pg_enum(SlotType, "slot_type"),
        nullable=False,
        default=SlotType.EXPRESS,
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    discount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    tax: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        pg_enum(OrderStatus, "order_status"),
        nullable=False,
        default=OrderStatus.PLACED,
        index=True,
    )
    delivery_otp: Mapped[str] = mapped_column(String(6), nullable=False)
    customer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    customer: Mapped["User"] = relationship("User", foreign_keys=[customer_id])
    shop: Mapped["Shop"] = relationship("Shop")
    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    events: Mapped[list["OrderEvent"]] = relationship(
        "OrderEvent",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderEvent.created_at",
    )
    payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="order",
        cascade="all, delete-orphan",
    )
    __table_args__ = (
        CheckConstraint("subtotal >= 0", name="ck_orders_subtotal_nonneg"),
        CheckConstraint("delivery_fee >= 0", name="ck_orders_delivery_fee_nonneg"),
        CheckConstraint("discount >= 0", name="ck_orders_discount_nonneg"),
        CheckConstraint("tax >= 0", name="ck_orders_tax_nonneg"),
        CheckConstraint("total >= 0", name="ck_orders_total_nonneg"),
        Index("ix_orders_customer_created", "customer_id", "created_at"),
        Index("ix_orders_shop_status", "shop_id", "status"),
    )
    def __repr__(self) -> str:
        return f"<Order {self.code} {self.status.value} total={self.total}>"