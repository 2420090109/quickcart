"""Cart model — one active cart per (user, shop) pair.
Why one cart per shop?
  Because you can't order from multiple shops in one checkout.
  If a customer browses Shop A and Shop B, they get two separate carts
  and check them out separately.
Carts are persistent (not session-based) so a customer can add items on
their phone, then continue on the web.
"""
import uuid
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin
if TYPE_CHECKING:
    from app.models.cart_item import CartItem
    from app.models.shop import Shop
    from app.models.user import User
class Cart(Base, TimestampMixin):
    __tablename__ = "carts"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shops.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Only one "active" cart per (user, shop). Old carts are marked inactive
    # after checkout or abandonment, preserving analytics.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    user: Mapped["User"] = relationship("User")
    shop: Mapped["Shop"] = relationship("Shop")
    items: Mapped[list["CartItem"]] = relationship(
        "CartItem",
        back_populates="cart",
        cascade="all, delete-orphan",
    )
    __table_args__ = (
        # Enforce one active cart per (user, shop)
        Index(
            "uq_carts_user_shop_active",
            "user_id",
            "shop_id",
            unique=True,
            postgresql_where="is_active = true",
        ),
    )
    def __repr__(self) -> str:
        return f"<Cart {self.id} user={self.user_id} shop={self.shop_id}>"