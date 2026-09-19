"""CartItem — a line in a cart."""
import uuid
from typing import TYPE_CHECKING
from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin
if TYPE_CHECKING:
    from app.models.cart import Cart
    from app.models.product import Product
class CartItem(Base, TimestampMixin):
    __tablename__ = "cart_items"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cart_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("carts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cart: Mapped["Cart"] = relationship("Cart", back_populates="items")
    product: Mapped["Product"] = relationship("Product")
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_cart_items_qty_positive"),
        UniqueConstraint("cart_id", "product_id", name="uq_cart_items_cart_product"),
    )
    def __repr__(self) -> str:
        return f"<CartItem cart={self.cart_id} product={self.product_id} qty={self.quantity}>"