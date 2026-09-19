"""Cart service â€” with atomic stock reservation."""
import uuid
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.exceptions import ConflictError, NotFoundError
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.shop import Shop
from app.schemas.cart import AddCartItemRequest, CartItemOut, CartOut
MAX_QTY_PER_LINE = 100
async def _get_or_create_active_cart(
    db: AsyncSession, *, user_id: uuid.UUID, shop_id: uuid.UUID
) -> Cart:
    """Fetch the user's active cart for this shop, or create one.
    Always returns a Cart with `.items` eagerly loaded â€” safe to iterate.
    """
    stmt = (
        select(Cart)
        .where(
            Cart.user_id == user_id,
            Cart.shop_id == shop_id,
            Cart.is_active.is_(True),
        )
        .options(selectinload(Cart.items).selectinload(CartItem.product))
    )
    cart = (await db.execute(stmt)).scalar_one_or_none()
    if cart is not None:
        return cart
    # Create new cart
    cart = Cart(user_id=user_id, shop_id=shop_id, is_active=True)
    db.add(cart)
    await db.flush()
    # Force-load .items so subsequent access doesn't trigger a sync lazy load.
    # After flush the cart has an id but no items; we re-fetch with eager
    # loading to get a fully-populated object.
    stmt = (
        select(Cart)
        .where(Cart.id == cart.id)
        .options(selectinload(Cart.items).selectinload(CartItem.product))
    )
    cart = (await db.execute(stmt)).scalar_one()
    return cart
async def _try_reserve(db: AsyncSession, *, product_id: uuid.UUID, delta: int) -> bool:
    """Atomically reserve `delta` units. Returns True on success."""
    if delta == 0:
        return True
    if delta < 0:
        await db.execute(
            update(Inventory)
            .where(Inventory.product_id == product_id)
            .values(reserved_qty=Inventory.reserved_qty + delta)
        )
        return True
    stmt = (
        update(Inventory)
        .where(
            Inventory.product_id == product_id,
            Inventory.stock_qty - Inventory.reserved_qty >= delta,
        )
        .values(reserved_qty=Inventory.reserved_qty + delta)
    )
    result = await db.execute(stmt)
    return result.rowcount == 1
async def add_to_cart(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    data: AddCartItemRequest,
) -> CartOut:
    """Add a product to the cart, reserving stock atomically."""
    stmt = (
        select(Product, Inventory, Shop)
        .join(Inventory, Inventory.product_id == Product.id)
        .join(Shop, Shop.id == Product.shop_id)
        .where(Product.id == data.product_id, Product.is_active.is_(True))
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        raise NotFoundError("Product not found or inactive.")
    product, inventory, shop = row
    if not shop.is_open or not shop.is_active:
        raise ConflictError(f"{shop.name} is not accepting orders right now.")
    cart = await _get_or_create_active_cart(db, user_id=user_id, shop_id=shop.id)
    existing_line = next(
        (i for i in cart.items if i.product_id == product.id), None
    )
    current_qty = existing_line.quantity if existing_line else 0
    new_qty = current_qty + data.quantity
    delta = new_qty - current_qty
    if new_qty > MAX_QTY_PER_LINE:
        raise ConflictError(f"Maximum {MAX_QTY_PER_LINE} units per item.")
    ok = await _try_reserve(db, product_id=product.id, delta=delta)
    if not ok:
        raise ConflictError(
            f"Only {inventory.available_qty} units of {product.name} available."
        )
    if existing_line:
        existing_line.quantity = new_qty
    else:
        db.add(CartItem(cart_id=cart.id, product_id=product.id, quantity=new_qty))
    await db.commit()
    return await get_cart(db, user_id=user_id, shop_id=shop.id)
async def update_cart_item(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    item_id: uuid.UUID,
    new_quantity: int,
) -> CartOut:
    stmt = (
        select(CartItem)
        .join(Cart, Cart.id == CartItem.cart_id)
        .where(
            CartItem.id == item_id,
            Cart.user_id == user_id,
            Cart.is_active.is_(True),
        )
        .options(selectinload(CartItem.cart))
    )
    item = (await db.execute(stmt)).scalar_one_or_none()
    if item is None:
        raise NotFoundError("Cart item not found.")
    if new_quantity > MAX_QTY_PER_LINE:
        raise ConflictError(f"Maximum {MAX_QTY_PER_LINE} units per item.")
    delta = new_quantity - item.quantity
    ok = await _try_reserve(db, product_id=item.product_id, delta=delta)
    if not ok:
        raise ConflictError("Not enough stock for the requested quantity.")
    item.quantity = new_quantity
    await db.commit()
    return await get_cart(db, user_id=user_id, shop_id=item.cart.shop_id)
async def remove_cart_item(
    db: AsyncSession, *, user_id: uuid.UUID, item_id: uuid.UUID
) -> CartOut:
    stmt = (
        select(CartItem)
        .join(Cart, Cart.id == CartItem.cart_id)
        .where(
            CartItem.id == item_id,
            Cart.user_id == user_id,
            Cart.is_active.is_(True),
        )
        .options(selectinload(CartItem.cart))
    )
    item = (await db.execute(stmt)).scalar_one_or_none()
    if item is None:
        raise NotFoundError("Cart item not found.")
    shop_id = item.cart.shop_id
    await _try_reserve(db, product_id=item.product_id, delta=-item.quantity)
    await db.execute(delete(CartItem).where(CartItem.id == item_id))
    await db.commit()
    return await get_cart(db, user_id=user_id, shop_id=shop_id)
async def clear_cart(db: AsyncSession, *, user_id: uuid.UUID) -> None:
    """Deactivate all active carts, release reservations, and remove items."""
    stmt = (
        select(Cart)
        .where(Cart.user_id == user_id, Cart.is_active.is_(True))
        .options(selectinload(Cart.items))
    )
    carts = (await db.execute(stmt)).scalars().all()
    for cart in carts:
        for item in cart.items:
            # Release the reservation
            await _try_reserve(db, product_id=item.product_id, delta=-item.quantity)
        # Delete the cart_items rows so they don't orphan
        await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
        cart.is_active = False
    await db.commit()
async def get_cart(
    db: AsyncSession, *, user_id: uuid.UUID, shop_id: uuid.UUID | None = None
) -> CartOut | None:
    stmt = (
        select(Cart)
        .where(Cart.user_id == user_id, Cart.is_active.is_(True))
        .options(
            selectinload(Cart.items)
            .selectinload(CartItem.product)
            .selectinload(Product.inventory),
            selectinload(Cart.shop),
        )
    )
    if shop_id is not None:
        stmt = stmt.where(Cart.shop_id == shop_id)
    cart = (await db.execute(stmt)).scalars().first()
    if cart is None:
        return None
    return _to_cart_out(cart)
def _to_cart_out(cart: Cart) -> CartOut:
    """Convert a Cart ORM object into a CartOut schema."""
    items: list[CartItemOut] = []
    subtotal = 0
    for item in cart.items:
        product = item.product
        line_total = product.price * item.quantity
        avail = product.inventory.available_qty if product.inventory else 0
        items.append(
            CartItemOut(
                id=item.id,
                product_id=product.id,
                product_name=product.name,
                product_slug=product.slug,
                product_unit=product.unit,
                product_image_url=product.image_url,
                unit_price=product.price,
                quantity=item.quantity,
                line_total=line_total,
                available_qty=avail,
            )
        )
        subtotal += line_total
    shop = cart.shop
    return CartOut(
        id=cart.id,
        shop_id=shop.id,
        shop_name=shop.name,
        shop_slug=shop.slug,
        min_order_value=shop.min_order_value,
        delivery_fee=shop.delivery_fee,
        items=items,
        subtotal=subtotal,
        item_count=sum(i.quantity for i in items),
        meets_min_order=subtotal >= shop.min_order_value,
    )