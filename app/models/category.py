"""Category model — belongs to a shop (menu sections)."""
import uuid
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin
if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.shop import Shop
class Category(Base, TimestampMixin):
    __tablename__ = "categories"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shops.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    slug: Mapped[str] = mapped_column(String(90), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # For drag-and-drop ordering in the shop UI
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    shop: Mapped["Shop"] = relationship("Shop", back_populates="categories")
    products: Mapped[list["Product"]] = relationship(
        "Product",
        back_populates="category",
    )
    __table_args__ = (
        # Slug must be unique within a shop, but two shops can both have "beverages"
        UniqueConstraint("shop_id", "slug", name="uq_categories_shop_slug"),
    )
    def __repr__(self) -> str:
        return f"<Category {self.id} {self.name}>"