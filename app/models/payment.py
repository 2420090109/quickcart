"""Payment — one row per payment attempt."""
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
from app.models.enums import PaymentMethod, PaymentStatus, pg_enum
if TYPE_CHECKING:
    from app.models.order import Order
class Payment(Base, TimestampMixin):
    __tablename__ = "payments"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    method: Mapped[PaymentMethod] = mapped_column(
        pg_enum(PaymentMethod, "payment_method"),
        nullable=False,
    )
    status: Mapped[PaymentStatus] = mapped_column(
        pg_enum(PaymentStatus, "payment_status"),
        nullable=False,
        default=PaymentStatus.PENDING,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    razorpay_order_id: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )
    razorpay_payment_id: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )
    razorpay_signature: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_webhook_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    refunded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    refund_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    order: Mapped["Order"] = relationship("Order", back_populates="payments")
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_payments_amount_nonneg"),
        Index("ix_payments_order_status", "order_id", "status"),
    )
    def __repr__(self) -> str:
        return f"<Payment {self.id} {self.status.value} amount={self.amount}>"