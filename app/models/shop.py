"""Shop model — a store that sells products."""
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin
if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.product import Product
    from app.models.user import User
class Shop(Base, TimestampMixin):
    __tablename__ = "shops"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # --- Identity ---
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # --- Location ---
    address_line: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    pincode: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    latitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    # --- Operations ---
    phone: Mapped[str] = mapped_column(String(15), nullable=False)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Delivery radius in kilometers. Numeric(5,2) => max 999.99 km
    delivery_radius_km: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("5.00"), nullable=False
    )
    # Minimum cart value for an order from this shop
    min_order_value: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), nullable=False
    )
    # Flat delivery fee charged per order
    delivery_fee: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("20.00"), nullable=False
    )
    # Estimated preparation time in minutes
    avg_prep_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    # --- Relationships ---
    owner: Mapped["User"] = relationship("User", back_populates="shops")
    categories: Mapped[list["Category"]] = relationship(
        "Category",
        back_populates="shop",
        cascade="all, delete-orphan",
    )
    products: Mapped[list["Product"]] = relationship(
        "Product",
        back_populates="shop",
        cascade="all, delete-orphan",
    )
    __table_args__ = (
        CheckConstraint(
            "latitude >= -90 AND latitude <= 90",
            name="ck_shops_lat_range",
        ),
        CheckConstraint(
            "longitude >= -180 AND longitude <= 180",
            name="ck_shops_lng_range",
        ),
        CheckConstraint("delivery_radius_km > 0", name="ck_shops_radius_positive"),
        CheckConstraint("min_order_value >= 0", name="ck_shops_min_order_nonneg"),
        Index("ix_shops_city_active", "city", "is_active"),
        Index("ix_shops_lat_lng", "latitude", "longitude"),
    )
    def __repr__(self) -> str:
        return f"<Shop {self.id} {self.name}>"