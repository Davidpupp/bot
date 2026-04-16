#!/usr/bin/env python3
"""
Test script for product delivery after payment confirmation
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
import httpx

# Set test environment
os.environ["BOT_TOKEN"] = "TEST_TOKEN_ONLY_FOR_TESTING"
os.environ["DATABASE_URL"] = "sqlite:///test_delivery.db"

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///test_delivery.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String)
    email = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    orders = relationship("Order", back_populates="user")

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    name = Column(String, index=True)
    description = Column(Text)
    price = Column(Float)
    stock = Column(Integer, default=999999)
    digital_file = Column(String, nullable=True)
    is_available = Column(Boolean, default=True)
    orders = relationship("OrderItem", back_populates="product")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    total_price = Column(Float)
    status = Column(String, default="pending")
    payment_id = Column(String, nullable=True)
    payment_qr_base64 = Column(Text, nullable=True)
    payment_copy_paste = Column(Text, nullable=True)
    reserved_until = Column(DateTime, nullable=True)
    delivery_status = Column(String, default="pending")
    delivered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer, default=1)
    price = Column(Float)
    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="orders")

Base.metadata.create_all(bind=engine)

def release_expired_reservations(db):
    now = datetime.utcnow()
    expired = (
        db.query(Order)
        .filter(Order.status == "reserved")
        .filter(Order.reserved_until != None)
        .filter(Order.reserved_until < now)
        .all()
    )
    if not expired:
        return

    for order in expired:
        for item in order.items:
            product = db.query(Product).filter(Product.id == item.product_id).first()
            if product and product.stock is not None:
                product.stock += item.quantity
        order.status = "cancelled"
        order.delivery_status = "cancelled"
    db.commit()

async def send_telegram_message(chat_id: int, text: str):
    """Mock function for testing"""
    print(f"MOCK Telegram message to {chat_id}: {text}")

async def deliver_digital_product(order_id: int):
    """Mock delivery function"""
    db = SessionLocal()
    release_expired_reservations(db)
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        print(f"Order {order_id} not found")
        return
    if order.status != "paid":
        print(f"Order {order_id} not paid (status: {order.status})")
        db.close()
        return
    user = db.query(User).filter(User.id == order.user_id).first()
    if not user:
        print(f"User for order {order_id} not found")
        db.close()
        return
    
    print(f"Delivering products for order {order_id} to user {user.telegram_id}")
    
    for item in order.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if product:
            if product.digital_file and os.path.exists(product.digital_file):
                print(f"  - Sending digital file: {product.digital_file}")
                # Mock file sending
                await send_telegram_message(
                    user.telegram_id, 
                    f"Product delivered: {product.name} (File: {os.path.basename(product.digital_file)})"
                )
            else:
                print(f"  - No digital file for {product.name}, sending confirmation")
                await send_telegram_message(
                    user.telegram_id, 
                    f"Your product '{product.name}' has been confirmed! Access details will be sent separately."
                )
    
    order.delivery_status = "delivered"
    order.delivered_at = datetime.utcnow()
    db.commit()
    db.close()
    print(f"Order {order_id} marked as delivered")

def create_test_digital_file():
    """Create a test digital file"""
    test_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    test_file.write("This is a test digital product.\n")
    test_file.write("Generated for testing delivery system.\n")
    test_file.write(f"Created at: {datetime.now()}\n")
    test_file.close()
    return test_file.name

def test_delivery_with_digital_file():
    """Test delivery when product has digital file"""
    print("=== Testing Delivery with Digital File ===\n")
    
    db = SessionLocal()
    
    # Clean up
    db.query(OrderItem).delete()
    db.query(Order).delete()
    db.query(Product).delete()
    db.query(User).delete()
    db.commit()
    
    # Create test user
    user = User(
        telegram_id=123456,
        username="testuser",
        first_name="Test User",
        is_admin=True
    )
    db.add(user)
    db.commit()
    
    # Create test product with digital file
    digital_file = create_test_digital_file()
    product = Product(
        name="Digital Product Test",
        description="Product with digital file",
        price=10.0,
        stock=100,
        digital_file=digital_file
    )
    db.add(product)
    db.commit()
    
    print(f"1. Created product with digital file: {digital_file}")
    
    # Create paid order
    order = Order(
        user_id=user.id,
        total_price=10.0,
        status="paid",
        payment_id="pay_test_123",
        delivery_status="processing"
    )
    db.add(order)
    db.commit()
    
    # Add order item
    item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        quantity=1,
        price=10.0
    )
    db.add(item)
    db.commit()
    
    print(f"2. Created paid order #{order.id}")
    
    # Test delivery
    import asyncio
    asyncio.run(deliver_digital_product(order.id))
    
    # Check order status
    db.refresh(order)
    print(f"3. Order status after delivery: {order.status}")
    print(f"   Delivery status: {order.delivery_status}")
    print(f"   Delivered at: {order.delivered_at}")
    
    # Cleanup
    os.unlink(digital_file)
    db.close()
    print()

def test_delivery_without_digital_file():
    """Test delivery when product has no digital file"""
    print("=== Testing Delivery without Digital File ===\n")
    
    db = SessionLocal()
    
    # Create test user
    user = User(
        telegram_id=789012,
        username="testuser2",
        first_name="Test User 2",
        is_admin=False
    )
    db.add(user)
    db.commit()
    
    # Create test product without digital file
    product = Product(
        name="Service Product",
        description="Service/product without digital file",
        price=25.0,
        stock=999999,
        digital_file=None
    )
    db.add(product)
    db.commit()
    
    print("1. Created product without digital file")
    
    # Create paid order
    order = Order(
        user_id=user.id,
        total_price=25.0,
        status="paid",
        payment_id="pay_test_456",
        delivery_status="processing"
    )
    db.add(order)
    db.commit()
    
    # Add order item
    item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        quantity=1,
        price=25.0
    )
    db.add(item)
    db.commit()
    
    print(f"2. Created paid order #{order.id}")
    
    # Test delivery
    import asyncio
    asyncio.run(deliver_digital_product(order.id))
    
    # Check order status
    db.refresh(order)
    print(f"3. Order status after delivery: {order.status}")
    print(f"   Delivery status: {order.delivery_status}")
    
    db.close()
    print()

def test_multiple_products_delivery():
    """Test delivery with multiple products in one order"""
    print("=== Testing Multiple Products Delivery ===\n")
    
    db = SessionLocal()
    
    # Create test user
    user = User(
        telegram_id=345678,
        username="testuser3",
        first_name="Test User 3",
        is_admin=False
    )
    db.add(user)
    db.commit()
    
    # Create multiple products
    products = []
    
    # Product 1 with digital file
    digital_file1 = create_test_digital_file()
    product1 = Product(
        name="Digital Product 1",
        description="First digital product",
        price=15.0,
        stock=50,
        digital_file=digital_file1
    )
    db.add(product1)
    products.append(product1)
    
    # Product 2 without digital file
    product2 = Product(
        name="Service 1",
        description="Service product",
        price=30.0,
        stock=999999,
        digital_file=None
    )
    db.add(product2)
    products.append(product2)
    
    # Product 3 with digital file
    digital_file2 = create_test_digital_file()
    product3 = Product(
        name="Digital Product 2",
        description="Second digital product",
        price=20.0,
        stock=75,
        digital_file=digital_file2
    )
    db.add(product3)
    products.append(product3)
    
    db.commit()
    
    print(f"1. Created {len(products)} products")
    
    # Create paid order with multiple items
    order = Order(
        user_id=user.id,
        total_price=65.0,  # 15 + 30 + 20
        status="paid",
        payment_id="pay_test_789",
        delivery_status="processing"
    )
    db.add(order)
    db.commit()
    
    # Add multiple order items
    for i, product in enumerate(products, 1):
        item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=1,
            price=product.price
        )
        db.add(item)
        print(f"   - Added item {i}: {product.name} (R$ {product.price})")
    
    db.commit()
    
    print(f"\n2. Created paid order #{order.id} with {len(products)} items")
    
    # Test delivery
    import asyncio
    asyncio.run(deliver_digital_product(order.id))
    
    # Check order status
    db.refresh(order)
    print(f"\n3. Order status after delivery: {order.status}")
    print(f"   Delivery status: {order.delivery_status}")
    print(f"   Delivered at: {order.delivered_at}")
    
    # Cleanup
    os.unlink(digital_file1)
    os.unlink(digital_file2)
    db.close()
    print()

def test_delivery_preconditions():
    """Test delivery preconditions and edge cases"""
    print("=== Testing Delivery Preconditions ===\n")
    
    db = SessionLocal()
    
    # Test 1: Non-existent order
    print("1. Testing non-existent order:")
    import asyncio
    asyncio.run(deliver_digital_product(99999))
    print()
    
    # Test 2: Order not paid
    print("2. Testing order not paid:")
    user = User(
        telegram_id=999999,
        username="testuser4",
        first_name="Test User 4",
        is_admin=False
    )
    db.add(user)
    db.commit()
    
    order = Order(
        user_id=user.id,
        total_price=10.0,
        status="pending",  # Not paid
        payment_id="pay_test_pending",
        delivery_status="pending"
    )
    db.add(order)
    db.commit()
    
    asyncio.run(deliver_digital_product(order.id))
    print()
    
    # Test 3: Order already delivered
    print("3. Testing already delivered order:")
    order.status = "paid"
    order.delivery_status = "delivered"
    order.delivered_at = datetime.utcnow()
    db.commit()
    
    asyncio.run(deliver_digital_product(order.id))
    print()
    
    db.close()

if __name__ == "__main__":
    test_delivery_with_digital_file()
    test_delivery_without_digital_file()
    test_multiple_products_delivery()
    test_delivery_preconditions()
    print("=== Delivery tests completed ===")
