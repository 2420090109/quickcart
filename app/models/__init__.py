"""Model registry.
Alembic needs to import every model module so that Base.metadata knows
about all tables before generating migrations. Importing here ensures
that ``from app.models import *`` (or importing the package) registers
everything.
"""
from app.models.address import Address
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.category import Category
from app.models.delivery_assignment import DeliveryAssignment
from app.models.delivery_location import DeliveryLocation
from app.models.enums import (
    DeliveryAssignmentStatus,
    NotificationChannel,
    NotificationStatus,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    SlotType,
    UserRole,
)
from app.models.inventory import Inventory
from app.models.notification import Notification
from app.models.order import Order
from app.models.order_event import OrderEvent
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.product import Product
from app.models.review import Review
from app.models.shop import Shop
from app.models.user import User
__all__ = [
    # models
    "Address",
    "Cart",
    "CartItem",
    "Category",
    "DeliveryAssignment",
    "DeliveryLocation",
    "Inventory",
    "Notification",
    "Order",
    "OrderEvent",
    "OrderItem",
    "Payment",
    "Product",
    "Review",
    "Shop",
    "User",
    # enums
    "DeliveryAssignmentStatus",
    "NotificationChannel",
    "NotificationStatus",
    "OrderStatus",
    "PaymentMethod",
    "PaymentStatus",
    "SlotType",
    "UserRole",
]