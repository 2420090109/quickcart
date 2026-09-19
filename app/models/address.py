"""Address model — customer delivery addresses."""
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin
if TYPE_CHECKING:
    from app.models.user import User
class Address(Base, TimestampMixin):
    __tablename__ = "addresses"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # --- Human-readable parts ---
    label: Mapped[str] = mapped_column(String(50), nullable=False)  # "Home", "Work"
    line1: Mapped[str] = mapped_column(String(255), nullable=False)
    line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    landmark: Mapped[str | None] = mapped_column(String(120), nullable=True)
    city: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str] = mapped_column(String(80), nullable=False)
    pincode: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    # --- Geo coordinates ---
    # Numeric(10, 7) = up to 999.9999999, precision ~1 cm. Plenty for delivery.
    latitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    # --- Meta ---
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # --- Relationships ---
    user: Mapped["User"] = relationship("User", back_populates="addresses")
    __table_args__ = (
        Index("ix_addresses_user_default", "user_id", "is_default"),
    )
    def __repr__(self) -> str:
        return f"<Address {self.id} {self.label} {self.city}>"