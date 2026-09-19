"""Seed the database with demo data.
Idempotent: safe to run multiple times. It checks for existing records
by their unique identifiers (phone numbers, shop slug) before creating.
Usage:
    python -m app.scripts.seed
"""
import asyncio
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.category import Category
from app.models.inventory import Inventory
from app.models.enums import UserRole
from app.models.product import Product
from app.models.shop import Shop
from app.models.user import User
DEMO_PASSWORD = "DemoPass123"
async def _get_or_create_user(
    db: AsyncSession,
    *,
    phone: str,
    email: str,
    full_name: str,
    role: UserRole,
) -> User:
    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    if user:
        print(f"  [skip] user exists: {phone} ({role.value})")
        return user
    user = User(
        phone=phone,
        email=email,
        full_name=full_name,
        password_hash=hash_password(DEMO_PASSWORD),
        role=role,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.flush()
    print(f"  [new]  user: {phone} ({role.value}) - password: {DEMO_PASSWORD}")
    return user
async def _get_or_create_shop(
    db: AsyncSession,
    *,
    owner: User,
    slug: str,
    name: str,
    **kwargs,
) -> Shop:
    result = await db.execute(select(Shop).where(Shop.slug == slug))
    shop = result.scalar_one_or_none()
    if shop:
        print(f"  [skip] shop exists: {slug}")
        return shop
    shop = Shop(owner_id=owner.id, slug=slug, name=name, **kwargs)
    db.add(shop)
    await db.flush()
    print(f"  [new]  shop: {name} ({slug})")
    return shop
async def _get_or_create_category(
    db: AsyncSession,
    *,
    shop: Shop,
    name: str,
    slug: str,
    sort_order: int = 0,
) -> Category:
    result = await db.execute(
        select(Category).where(Category.shop_id == shop.id, Category.slug == slug)
    )
    category = result.scalar_one_or_none()
    if category:
        return category
    category = Category(
        shop_id=shop.id,
        name=name,
        slug=slug,
        sort_order=sort_order,
        is_active=True,
    )
    db.add(category)
    await db.flush()
    print(f"    [new]  category: {name}")
    return category
async def _get_or_create_product(
    db: AsyncSession,
    *,
    shop: Shop,
    category: Category,
    name: str,
    slug: str,
    price: Decimal,
    mrp: Decimal | None,
    unit: str,
    stock_qty: int,
    description: str | None = None,
    is_veg: bool | None = None,
) -> Product:
    result = await db.execute(
        select(Product).where(Product.shop_id == shop.id, Product.slug == slug)
    )
    product = result.scalar_one_or_none()
    if product:
        return product
    product = Product(
        shop_id=shop.id,
        category_id=category.id,
        name=name,
        slug=slug,
        price=price,
        mrp=mrp,
        unit=unit,
        description=description,
        is_active=True,
        is_veg=is_veg,
    )
    db.add(product)
    await db.flush()
    inventory = Inventory(
        product_id=product.id,
        stock_qty=stock_qty,
        reserved_qty=0,
        low_stock_threshold=5,
    )
    db.add(inventory)
    await db.flush()
    print(f"      [new]  product: {name} @ {price} ({stock_qty} in stock)")
    return product
async def seed() -> None:
    print("Seeding demo data...")
    async with AsyncSessionLocal() as db:
        print("\nUsers:")
        admin = await _get_or_create_user(
            db,
            phone="9000000001",
            email="admin@quickcart.in",
            full_name="Admin User",
            role=UserRole.ADMIN,
        )
        owner = await _get_or_create_user(
            db,
            phone="9000000002",
            email="owner@quickcart.in",
            full_name="Shop Owner",
            role=UserRole.SHOP_OWNER,
        )
        customer = await _get_or_create_user(
            db,
            phone="9000000003",
            email="customer@quickcart.in",
            full_name="Demo Customer",
            role=UserRole.CUSTOMER,
        )
        partner = await _get_or_create_user(
            db,
            phone="9000000004",
            email="partner@quickcart.in",
            full_name="Delivery Partner",
            role=UserRole.DELIVERY_PARTNER,
        )
        print("\nShop:")
        shop = await _get_or_create_shop(
            db,
            owner=owner,
            slug="freshmart-koramangala",
            name="FreshMart Koramangala",
            description="Your neighbourhood grocery store",
            address_line="123 5th Block, Koramangala",
            city="Bengaluru",
            pincode="560095",
            latitude=Decimal("12.9352000"),
            longitude=Decimal("77.6245000"),
            phone="9000000002",
            is_open=True,
            is_active=True,
            delivery_radius_km=Decimal("6.00"),
            min_order_value=Decimal("99.00"),
            delivery_fee=Decimal("25.00"),
            avg_prep_minutes=12,
        )
        print("\nCategories + Products:")
        fruits = await _get_or_create_category(
            db, shop=shop, name="Fruits", slug="fruits", sort_order=1
        )
        await _get_or_create_product(
            db, shop=shop, category=fruits,
            name="Banana (Robusta)", slug="banana-robusta",
            price=Decimal("45.00"), mrp=Decimal("55.00"),
            unit="1 dozen", stock_qty=50, is_veg=True,
        )
        await _get_or_create_product(
            db, shop=shop, category=fruits,
            name="Apple (Shimla)", slug="apple-shimla",
            price=Decimal("180.00"), mrp=Decimal("220.00"),
            unit="1 kg", stock_qty=30, is_veg=True,
        )
        veggies = await _get_or_create_category(
            db, shop=shop, name="Vegetables", slug="vegetables", sort_order=2
        )
        await _get_or_create_product(
            db, shop=shop, category=veggies,
            name="Tomato (Local)", slug="tomato-local",
            price=Decimal("35.00"), mrp=Decimal("40.00"),
            unit="1 kg", stock_qty=40, is_veg=True,
        )
        await _get_or_create_product(
            db, shop=shop, category=veggies,
            name="Onion", slug="onion",
            price=Decimal("28.00"), mrp=Decimal("35.00"),
            unit="1 kg", stock_qty=100, is_veg=True,
        )
        dairy = await _get_or_create_category(
            db, shop=shop, name="Dairy & Bread", slug="dairy-bread", sort_order=3
        )
        await _get_or_create_product(
            db, shop=shop, category=dairy,
            name="Amul Taaza Toned Milk", slug="amul-taaza-1l",
            price=Decimal("58.00"), mrp=Decimal("60.00"),
            unit="1 L", stock_qty=80, is_veg=True,
        )
        await _get_or_create_product(
            db, shop=shop, category=dairy,
            name="Britannia Brown Bread", slug="britannia-brown-bread",
            price=Decimal("50.00"), mrp=Decimal("55.00"),
            unit="400 g", stock_qty=25, is_veg=True,
        )
        snacks = await _get_or_create_category(
            db, shop=shop, name="Snacks", slug="snacks", sort_order=4
        )
        await _get_or_create_product(
            db, shop=shop, category=snacks,
            name="Lays Classic Salted", slug="lays-classic",
            price=Decimal("20.00"), mrp=Decimal("20.00"),
            unit="52 g", stock_qty=60, is_veg=True,
        )
        await _get_or_create_product(
            db, shop=shop, category=snacks,
            name="Kurkure Masala Munch", slug="kurkure-masala",
            price=Decimal("20.00"), mrp=Decimal("20.00"),
            unit="90 g", stock_qty=60, is_veg=True,
        )
        await db.commit()
    print("\nSeed complete.")
    print("\nDemo accounts (all use password: " + DEMO_PASSWORD + "):")
    print("  Admin:            phone 9000000001")
    print("  Shop Owner:       phone 9000000002")
    print("  Customer:         phone 9000000003")
    print("  Delivery Partner: phone 9000000004")
    print("\nDemo shop: FreshMart Koramangala (slug: freshmart-koramangala)")
def main() -> None:
    asyncio.run(seed())
if __name__ == "__main__":
    main()