"""Inventory model — 1:1 with Product.
Why a separate table instead of columns on Product?
  - Logical separation: catalog vs. stock
  - Room to grow: stock movements, per-batch expiry, multiple warehouses
  - Reservation logic has a clean home
Reservation model:
  - stock_qty: total physical units on the shelf
  - reserved_qty: units held by unconfirmed orders (not yet paid)
  - available = stock_qty - reserved_qty (computed at query time)
When an order is placed:
  1. reserved_qty += item.quantity (atomic update)
When payment confirmed:
  2. stock_qty -= item.quantity; reserved_qty -= item.quantity
When order cancelled/expires:
  3. reserved_qty -= item.quantity
"""
import uuid
from typing import TYPE_CHECKING
from sqlalchemy import CheckConstraint, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin
if TYPE_CHECKING:
    from app.models.product import Product
class Inventory(Base, TimestampMixin):
    __tablename__ = "inventories"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # 1:1 with product
        index=True,
    )
    stock_qty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reserved_qty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Low-stock threshold for admin alerts
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    product: Mapped["Product"] = relationship("Product", back_populates="inventory")
    __table_args__ = (
        CheckConstraint("stock_qty >= 0", name="ck_inventories_stock_nonneg"),
        CheckConstraint("reserved_qty >= 0", name="ck_inventories_reserved_nonneg"),
        CheckConstraint(
            "reserved_qty <= stock_qty",
            name="ck_inventories_reserved_le_stock",
        ),
    )
    @property
    def available_qty(self) -> int:
        """Units available for new orders."""
        return self.stock_qty - self.reserved_qty
    def __repr__(self) -> str:
        return (
            f"<Inventory product={self.product_id} "
            f"stock={self.stock_qty} reserved={self.reserved_qty}>"
        )