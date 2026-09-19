"""DeliveryLocation — time-series pings from a partner's device.
We keep the latest N pings per partner for live tracking. In production
you would shard this by day or push to Redis + a time-series DB. For our
scale, Postgres + an index is plenty.
Cleanup strategy (implemented later as a background task):
  DELETE FROM delivery_locations WHERE updated_at < now() - interval '24 hours'
"""
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin
if TYPE_CHECKING:
    from app.models.user import User
class DeliveryLocation(Base, TimestampMixin):
    __tablename__ = "delivery_locations"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    partner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    latitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    # Optional accuracy from device GPS (meters)
    accuracy_m: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    partner: Mapped["User"] = relationship("User")
    __table_args__ = (
        CheckConstraint(
            "latitude >= -90 AND latitude <= 90",
            name="ck_delivery_locations_lat_range",
        ),
        CheckConstraint(
            "longitude >= -180 AND longitude <= 180",
            name="ck_delivery_locations_lng_range",
        ),
        # Latest ping for a partner/order — hot path for the tracking UI
        Index(
            "ix_delivery_locations_partner_created",
            "partner_id",
            "created_at",
        ),
    )
    def __repr__(self) -> str:
        return f"<DeliveryLocation partner={self.partner_id} ({self.latitude},{self.longitude})>"