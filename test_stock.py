#!/usr/bin/env python3
"""
Test script for stock reservation and release logic
"""
import os
import sys
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# Set test environment
os.environ["DATABASE_URL"] = "sqlite:///test_stock.db"

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///test_stock.db")
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

def test_stock_reservation():
    """Test stock reservation and release logic"""
    print("=== Testing Stock Reservation Logic ===\n")
    
    db = SessionLocal()
    
    # Clean up previous test data
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
    
    # Create test product with limited stock
    product = Product(
        name="Limited Stock Product",
        description="Product with only 10 units",
        price=10.0,
        stock=10
    )
    db.add(product)
    db.commit()
    
    print(f"1. Initial stock: {product.stock} units")
    
    # Test 1: Create order with reservation
    print("\n2. Creating order with reservation...")
    order = Order(
        user_id=user.id,
        total_price=20.0,
        status="reserved",
        reserved_until=datetime.utcnow() + timedelta(minutes=30),
        delivery_status="pending"
    )
    db.add(order)
    db.commit()
    
    # Add items (2 units)
    item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        quantity=2,
        price=10.0
    )
    db.add(item)
    
    # Deduct stock
    product.stock -= 2
    db.commit()
    
    print(f"   Stock after reservation: {product.stock} units")
    print(f"   Order status: {order.status}")
    print(f"   Reserved until: {order.reserved_until}")
    
    # Test 2: Try to create another order with remaining stock
    print("\n3. Creating second order...")
    order2 = Order(
        user_id=user.id,
        total_price=50.0,
        status="reserved",
        reserved_until=datetime.utcnow() + timedelta(minutes=30),
        delivery_status="pending"
    )
    db.add(order2)
    db.commit()
    
    # Add items (5 units)
    item2 = OrderItem(
        order_id=order2.id,
        product_id=product.id,
        quantity=5,
        price=10.0
    )
    db.add(item2)
    
    # Deduct stock
    product.stock -= 5
    db.commit()
    
    print(f"   Stock after second reservation: {product.stock} units")
    
    # Test 3: Try to create order with insufficient stock
    print("\n4. Attempting to create order with insufficient stock...")
    order3 = Order(
        user_id=user.id,
        total_price=60.0,
        status="reserved",
        reserved_until=datetime.utcnow() + timedelta(minutes=30),
        delivery_status="pending"
    )
    db.add(order3)
    db.commit()
    
    # Try to add 6 units (only 3 left)
    if product.stock >= 6:
        item3 = OrderItem(
            order_id=order3.id,
            product_id=product.id,
            quantity=6,
            price=10.0
        )
        db.add(item3)
        product.stock -= 6
        print("   Order created (unexpected!)")
    else:
        print(f"   Cannot create order: insufficient stock ({product.stock} available, 6 requested)")
        order3.status = "cancelled"
        order3.delivery_status = "cancelled"
    
    db.commit()
    print(f"   Stock remains: {product.stock} units")
    
    # Test 4: Simulate expired reservation
    print("\n5. Simulating expired reservation...")
    
    # Manually expire the first order
    order.reserved_until = datetime.utcnow() - timedelta(minutes=1)
    db.commit()
    
    print(f"   Order 1 reserved until: {order.reserved_until}")
    
    # Release expired reservations
    release_expired_reservations(db)
    
    # Refresh product data
    db.refresh(product)
    print(f"   Stock after releasing expired reservation: {product.stock} units")
    print(f"   Order 1 status: {order.status}")
    
    # Test 5: Complete payment for second order
    print("\n6. Completing payment for second order...")
    order2.status = "paid"
    order2.delivery_status = "processing"
    db.commit()
    
    print(f"   Order 2 status: {order2.status}")
    print(f"   Stock remains: {product.stock} units (should not change on payment)")
    
    # Final stock check
    db.refresh(product)
    print(f"\n7. Final stock: {product.stock} units")
    
    db.close()

def test_concurrent_reservations():
    """Test concurrent reservation scenarios"""
    print("\n=== Testing Concurrent Reservations ===\n")
    
    db = SessionLocal()
    
    # Create another product
    product = Product(
        name="Concurrent Test Product",
        description="Testing concurrent reservations",
        price=5.0,
        stock=5
    )
    db.add(product)
    db.commit()
    
    print(f"1. Product created with {product.stock} units")
    
    # Create multiple orders rapidly
    orders = []
    for i in range(3):
        order = Order(
            user_id=1,
            total_price=10.0,
            status="reserved",
            reserved_until=datetime.utcnow() + timedelta(minutes=30),
            delivery_status="pending"
        )
        db.add(order)
        db.commit()
        
        # Try to reserve 2 units each
        if product.stock >= 2:
            item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=2,
                price=5.0
            )
            db.add(item)
            product.stock -= 2
            db.commit()
            orders.append(order)
            print(f"   Order {i+1}: Reserved 2 units, remaining stock: {product.stock}")
        else:
            order.status = "cancelled"
            order.delivery_status = "cancelled"
            db.commit()
            print(f"   Order {i+1}: Cannot reserve (insufficient stock: {product.stock})")
    
    print(f"\n2. Final stock after reservations: {product.stock}")
    
    # Cancel one order to release stock
    if orders:
        cancelled_order = orders[0]
        cancelled_order.status = "cancelled"
        cancelled_order.delivery_status = "cancelled"
        
        # Return stock
        for item in cancelled_order.items:
            product.stock += item.quantity
        
        db.commit()
        print(f"3. Cancelled order 1, stock returned: {product.stock}")
    
    db.close()

if __name__ == "__main__":
    test_stock_reservation()
    test_concurrent_reservations()
    print("\n=== Stock reservation tests completed ===")
