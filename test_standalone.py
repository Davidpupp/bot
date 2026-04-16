#!/usr/bin/env python3
"""
Standalone test for webhook server without Telegram bot
"""
import os
import sys
import logging
import sqlite3
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from fastapi import FastAPI, Request, BackgroundTasks
import uvicorn
import httpx

# Set test environment
os.environ["BOT_TOKEN"] = "TEST_TOKEN_ONLY_FOR_TESTING"
os.environ["SILLIENTPAY_API_KEY"] = ""
os.environ["MP_ACCESS_TOKEN"] = ""
os.environ["WEBHOOK_URL"] = "http://localhost:8002"
os.environ["DATABASE_URL"] = "sqlite:///test_sales_bot.db"

# Import the necessary parts from bot.py
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///test_sales_bot.db")
BOT_TOKEN = os.getenv("BOT_TOKEN", "TEST_TOKEN")

# Database setup
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

# Create test data
def create_test_data():
    db = SessionLocal()
    
    # Create test user
    user = User(
        telegram_id=123456,
        username="testuser",
        first_name="Test User",
        is_admin=True
    )
    db.add(user)
    
    # Create test product
    product = Product(
        name="Test Product",
        description="Test product for webhook testing",
        price=10.0,
        stock=100
    )
    db.add(product)
    
    # Create test order with payment_id
    order = Order(
        user_id=1,
        total_price=10.0,
        status="pending",
        payment_id="pay_test_123",
        delivery_status="pending"
    )
    db.add(order)
    
    # Create order item
    item = OrderItem(
        order_id=1,
        product_id=1,
        quantity=1,
        price=10.0
    )
    db.add(item)
    
    db.commit()
    db.close()
    print("Test data created successfully")

# Webhook app (simplified)
app_webhook = FastAPI()

from fastapi.middleware.cors import CORSMiddleware
app_webhook.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    db = SessionLocal()
    release_expired_reservations(db)
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return
    if order.status != "paid":
        db.close()
        return
    user = db.query(User).filter(User.id == order.user_id).first()
    if not user:
        db.close()
        return
    
    print(f"Delivering product for order {order_id} to user {user.telegram_id}")
    
    order.delivery_status = "delivered"
    order.delivered_at = datetime.utcnow()
    db.commit()
    db.close()

@app_webhook.get("/")
async def root():
    return {"status": "Webhook ativo", "message": "Bot de vendas SillientPay"}

@app_webhook.post("/")
async def root_post(request: Request, background_tasks: BackgroundTasks):
    """POST na raiz - SillientPay envia aqui"""
    try:
        payload = await request.json()
        logging.info(f"Webhook POST na raiz recebido: {payload}")
        
        order_id = payload.get("orderId") or payload.get("order_id")
        status = payload.get("status")
        
        logging.info(f"Order ID: {order_id}, Status: {status}")
        
        if status == "paid" and order_id:
            db = SessionLocal()
            release_expired_reservations(db)
            order = db.query(Order).filter(Order.id == int(order_id)).first()
            
            if order and order.status != "paid":
                order.status = "paid"
                order.payment_id = payload.get("id") or str(order_id)
                order.delivery_status = "processing"
                db.commit()
                background_tasks.add_task(deliver_digital_product, order.id)
                user = db.query(User).filter(User.id == order.user_id).first()
                if user:
                    await send_telegram_message(user.telegram_id, f"Pagamento confirmado! Pedido #{order.id} foi aprovado.")
                logging.info(f"Pagamento confirmado para pedido #{order.id}")
            else:
                logging.info(f"Pedido #{order_id} já estava pago ou não encontrado")
            db.close()
        
        return {"status": "ok", "message": "Webhook processado com sucesso"}
    except Exception as e:
        logging.error(f"Erro no webhook: {str(e)}")
        return {"status": "error", "message": str(e)}

@app_webhook.post("/webhook/sillientpay")
async def sillientpay_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        payload = await request.json()
        logging.info(f"Webhook SillientPay (POST) recebido: {payload}")
        
        event = payload.get("event")
        logging.info(f"Evento: {event}")
        
        if event == "payment.succeeded":
            payment_id = payload.get("data", {}).get("id")
            db = SessionLocal()
            release_expired_reservations(db)
            order = db.query(Order).filter(Order.payment_id == payment_id).first()
            if order and order.status != "paid":
                order.status = "paid"
                order.delivery_status = "processing"
                db.commit()
                background_tasks.add_task(deliver_digital_product, order.id)
                user_id = order.user_id
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    await send_telegram_message(user.telegram_id, f"Pagamento confirmado! Pedido #{order.id} foi aprovado.")
                logging.info(f"Pagamento confirmado para pedido #{order.id}")
            db.close()
        return {"status": "ok", "message": "Webhook processado com sucesso"}
    except Exception as e:
        logging.error(f"Erro no webhook: {str(e)}")
        return {"status": "error", "message": str(e)}

@app_webhook.put("/webhook/sillientpay")
async def sillientpay_webhook_put(request: Request, background_tasks: BackgroundTasks):
    """Rota PUT para compatibilidade"""
    try:
        payload = await request.json()
        logging.info(f"Webhook SillientPay (PUT) recebido: {payload}")
        
        event = payload.get("event")
        logging.info(f"Evento: {event}")
        
        if event == "payment.succeeded":
            payment_id = payload.get("data", {}).get("id")
            db = SessionLocal()
            release_expired_reservations(db)
            order = db.query(Order).filter(Order.payment_id == payment_id).first()
            if order and order.status != "paid":
                order.status = "paid"
                order.delivery_status = "processing"
                db.commit()
                background_tasks.add_task(deliver_digital_product, order.id)
                user_id = order.user_id
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    await send_telegram_message(user.telegram_id, f"Pagamento confirmado! Pedido #{order.id} foi aprovado.")
                logging.info(f"Pagamento confirmado para pedido #{order.id}")
            db.close()
        return {"status": "ok", "message": "Webhook processado com sucesso"}
    except Exception as e:
        logging.error(f"Erro no webhook (PUT): {str(e)}")
        return {"status": "error", "message": str(e)}

@app_webhook.patch("/webhook/sillientpay")
async def sillientpay_webhook_patch(request: Request, background_tasks: BackgroundTasks):
    """Rota PATCH para compatibilidade"""
    try:
        payload = await request.json()
        logging.info(f"Webhook SillientPay (PATCH) recebido: {payload}")
        
        event = payload.get("event")
        logging.info(f"Evento: {event}")
        
        if event == "payment.succeeded":
            payment_id = payload.get("data", {}).get("id")
            db = SessionLocal()
            release_expired_reservations(db)
            order = db.query(Order).filter(Order.payment_id == payment_id).first()
            if order and order.status != "paid":
                order.status = "paid"
                order.delivery_status = "processing"
                db.commit()
                background_tasks.add_task(deliver_digital_product, order.id)
                user_id = order.user_id
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    await send_telegram_message(user.telegram_id, f"Pagamento confirmado! Pedido #{order.id} foi aprovado.")
                logging.info(f"Pagamento confirmado para pedido #{order.id}")
            db.close()
        return {"status": "ok", "message": "Webhook processado com sucesso"}
    except Exception as e:
        logging.error(f"Erro no webhook (PATCH): {str(e)}")
        return {"status": "error", "message": str(e)}

def run_webhook():
    uvicorn.run(app_webhook, host="0.0.0.0", port=8002, log_level="info")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Create test data
    create_test_data()
    
    print("Starting standalone webhook server on port 8002...")
    print("Test endpoints:")
    print("  GET  http://localhost:8002/")
    print("  POST http://localhost:8002/ (with orderId and status)")
    print("  POST http://localhost:8002/webhook/sillientpay (with event and data)")
    print("  PUT  http://localhost:8002/webhook/sillientpay")
    print("  PATCH http://localhost:8002/webhook/sillientpay")
    
    run_webhook()
