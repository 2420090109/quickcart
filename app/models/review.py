"""Review — customer feedback on a delivered order.
We tie reviews to ORDERS, not just products, because:
  - Only verified buyers can review
  - A customer can't review the same order twice
  - We can compute shop-level and product-level ratings from one source
"""
import uuid
from typing import TYPE_CHECKING
from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin
if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.shop import Shop
    from app.models.user import User
class Review(Base, TimestampMixin):
    __tablename__ = "reviews"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # one review per order
        index=True,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shops.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Ratings 1-5
    shop_rating: Mapped[int] = mapped_column(Integer, nullable=False)
    # Optional: rate the delivery partner separately
    delivery_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Simple moderation flag
    is_hidden: Mapped[bool] = mapped_column(
        default=False, nullable=False
    )
    order: Mapped["Order"] = relationship("Order")
    customer: Mapped["User | None"] = relationship("User")
    shop: Mapped["Shop"] = relationship("Shop")
    __table_args__ = (
        CheckConstraint(
            "shop_rating BETWEEN 1 AND 5",
            name="ck_reviews_shop_rating_range",
        ),
        CheckConstraint(
            "delivery_rating IS NULL OR delivery_rating BETWEEN 1 AND 5",
            name="ck_reviews_delivery_rating_range",
        ),
        Index("ix_reviews_shop_created", "shop_id", "created_at"),
    )
    def __repr__(self) -> str:
        return f"<Review order={self.order_id} shop_rating={self.shop_rating}>"