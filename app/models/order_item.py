"""OrderItem — a line item in an order, with price snapshot.
CRITICAL: We store the product name, unit, and price AT ORDER TIME.
If the shop later renames a product or changes its price, this order
still shows exactly what the customer bought and paid.
"""
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin
if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.product import Product
class OrderItem(Base, TimestampMixin):
    __tablename__ = "order_items"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # --- Snapshots ---
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    product_unit: Mapped[str] = mapped_column(String(30), nullable=False)
    product_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    # line_total = quantity * unit_price (also stored for reporting)
    line_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    order: Mapped["Order"] = relationship("Order", back_populates="items")
    product: Mapped["Product"] = relationship("Product")
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_order_items_qty_positive"),
        CheckConstraint("unit_price >= 0", name="ck_order_items_price_nonneg"),
        CheckConstraint("line_total >= 0", name="ck_order_items_total_nonneg"),
    )
    def __repr__(self) -> str:
        return f"<OrderItem order={self.order_id} {self.product_name} x{self.quantity}>"