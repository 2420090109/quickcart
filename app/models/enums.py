"""Shared enums used across models.
Using Python ``enum.Enum`` + SQLAlchemy ``Enum`` type maps these to
native PostgreSQL enum types. Native enums are enforced at the DB level,
which means invalid values are rejected before they even reach Python.
IMPORTANT: We always use ``pg_enum()`` (defined below) instead of raw
``SAEnum()``. SQLAlchemy's default uses enum *names* (uppercase Python
variable names) as Postgres labels — but our raw SQL uses the lowercase
*values*. ``values_callable`` fixes that mismatch.
"""
from enum import Enum
from sqlalchemy import Enum as SAEnum
def pg_enum(enum_cls, name: str) -> SAEnum:
    """Create a Postgres-native enum column that uses Python enum *values*."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda x: [e.value for e in x],
    )
class UserRole(str, Enum):
    CUSTOMER = "customer"
    SHOP_OWNER = "shop_owner"
    DELIVERY_PARTNER = "delivery_partner"
    ADMIN = "admin"
class OrderStatus(str, Enum):
    PLACED = "placed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PACKING = "packing"
    PACKED = "packed"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
class PaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
class PaymentMethod(str, Enum):
    RAZORPAY = "razorpay"
    COD = "cod"
    WALLET = "wallet"
class DeliveryAssignmentStatus(str, Enum):
    ASSIGNED = "assigned"
    ACCEPTED = "accepted"
    PICKED_UP = "picked_up"
    DELIVERED = "delivered"
    FAILED = "failed"
class SlotType(str, Enum):
    EXPRESS = "express"
    SCHEDULED = "scheduled"
class NotificationChannel(str, Enum):
    IN_APP = "in_app"
    SMS = "sms"
    EMAIL = "email"
    PUSH = "push"
class NotificationStatus(str, Enum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    READ = "read"