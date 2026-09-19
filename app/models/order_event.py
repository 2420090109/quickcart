"""OrderEvent — the state machine + audit log."""
import uuid
from typing import TYPE_CHECKING
from sqlalchemy import Enum as SAEnum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin
from app.models.enums import OrderStatus
if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.user import User
class OrderEvent(Base, TimestampMixin):
    __tablename__ = "order_events"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_role: Mapped[str | None] = mapped_column(String(30), nullable=True)
    from_status: Mapped[OrderStatus | None] = mapped_column(
        SAEnum(
            OrderStatus,
            name="order_status",
            native_enum=True,
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
    )
    to_status: Mapped[OrderStatus] = mapped_column(
        SAEnum(
            OrderStatus,
            name="order_status",
            native_enum=True,
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[str | None] = mapped_column(Text, nullable=True)
    order: Mapped["Order"] = relationship("Order", back_populates="events")
    actor: Mapped["User | None"] = relationship("User")
    __table_args__ = (
        Index("ix_order_events_order_created", "order_id", "created_at"),
    )
    def __repr__(self) -> str:
        return f"<OrderEvent {self.order_id} {self.from_status} -> {self.to_status}>"