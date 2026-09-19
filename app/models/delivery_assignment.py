"""DeliveryAssignment — a delivery partner assigned to an order."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin
from app.models.enums import DeliveryAssignmentStatus, pg_enum
if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.user import User
class DeliveryAssignment(Base, TimestampMixin):
    __tablename__ = "delivery_assignments"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    partner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[DeliveryAssignmentStatus] = mapped_column(
        pg_enum(DeliveryAssignmentStatus, "delivery_assignment_status"),
        nullable=False,
        default=DeliveryAssignmentStatus.ASSIGNED,
        index=True,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    picked_up_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating: Mapped[int | None] = mapped_column(nullable=True)
    order: Mapped["Order"] = relationship("Order")
    partner: Mapped["User"] = relationship("User", foreign_keys=[partner_id])
    __table_args__ = (
        Index(
            "uq_delivery_assignments_order_active",
            "order_id",
            unique=True,
            postgresql_where=(
                "status IN ("
                "'assigned'::delivery_assignment_status, "
                "'accepted'::delivery_assignment_status, "
                "'picked_up'::delivery_assignment_status"
                ")"
            ),
        ),
        Index("ix_delivery_assignments_partner_status", "partner_id", "status"),
    )
    def __repr__(self) -> str:
        return f"<DeliveryAssignment order={self.order_id} partner={self.partner_id} {self.status.value}>"