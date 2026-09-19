"""Product model — sellable item in a shop."""
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin
if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.inventory import Inventory
    from app.models.shop import Shop
class Product(Base, TimestampMixin):
    __tablename__ = "products"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shops.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # --- Identity ---
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(220), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # --- Pricing ---
    # price: what the customer pays
    # mrp: maximum retail price (for strikethrough display)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    mrp: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    # --- Unit ---
    # e.g., "500 g", "1 L", "6 pcs"
    unit: Mapped[str] = mapped_column(String(30), nullable=False, default="1 pc")
    # --- Flags ---
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_veg: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # --- Relationships ---
    shop: Mapped["Shop"] = relationship("Shop", back_populates="products")
    category: Mapped["Category"] = relationship("Category", back_populates="products")
    inventory: Mapped["Inventory"] = relationship(
        "Inventory",
        back_populates="product",
        uselist=False,
        cascade="all, delete-orphan",
    )
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_products_price_nonneg"),
        CheckConstraint("mrp IS NULL OR mrp >= 0", name="ck_products_mrp_nonneg"),
        UniqueConstraint("shop_id", "slug", name="uq_products_shop_slug"),
        Index("ix_products_shop_active", "shop_id", "is_active"),
        Index("ix_products_category_active", "category_id", "is_active"),
    )
    def __repr__(self) -> str:
        return f"<Product {self.id} {self.name}>"