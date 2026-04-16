#!/usr/bin/env python3
"""
TKS777 PRO - Bot de Vendas Automatizado Completo
Sistema avançado com puxada de dados, venda automatizada e analytics
"""

import os
import logging
import json
import asyncio
import threading
import signal
import sys
import random
import string
from datetime import datetime, timedelta
from io import BytesIO
from typing import Optional, List, Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    filters, ConversationHandler, ContextTypes
)
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.ext.hybrid import hybrid_property
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import httpx
import hashlib
import secrets

# Configuração
BOT_TOKEN = "8633859972:AAHQfiWp7XGjGtFSGGzveznFsLex2XABQHw"
ADMIN_IDS = [8649452369]
BASE_URL = "https://tks777-bot.app"
DATABASE_URL = "sqlite:///tks777_pro.db"
PORT = 8002
HOST = "0.0.0.0"

# Logging avançado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tks777_pro.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Banco de dados avançado
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
    phone = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False)
    is_vip = Column(Boolean, default=False)
    is_blocked = Column(Boolean, default=False)
    total_spent = Column(Float, default=0.0)
    referral_code = Column(String, unique=True, nullable=True)
    referred_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)
    orders = relationship("Order", back_populates="user")
    tickets = relationship("SupportTicket", back_populates="user")
    analytics = relationship("UserAnalytics", back_populates="user")

    @hybrid_property
    def total_orders(self):
        return len(self.orders)
    
    @hybrid_property
    def completed_orders(self):
        return len([o for o in self.orders if o.status == "completed"])

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    name = Column(String, index=True)
    description = Column(Text)
    price = Column(Float)
    category = Column(String, default="default")
    stock = Column(Integer, default=999999)
    digital_file = Column(String, nullable=True)
    delivery_data = Column(JSON, nullable=True)
    is_available = Column(Boolean, default=True)
    is_featured = Column(Boolean, default=False)
    tags = Column(JSON, nullable=True)
    view_count = Column(Integer, default=0)
    purchase_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    orders = relationship("OrderItem", back_populates="product")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    order_number = Column(String, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    total_price = Column(Float)
    status = Column(String, default="pending")
    payment_method = Column(String, default="pix")
    payment_id = Column(String, nullable=True)
    payment_qr = Column(Text, nullable=True)
    delivery_status = Column(String, default="pending")
    delivery_data = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")
    payments = relationship("Payment", back_populates="order")

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer, default=1)
    price = Column(Float)
    delivery_data = Column(JSON, nullable=True)
    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="orders")

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    payment_id = Column(String, unique=True)
    amount = Column(Float)
    status = Column(String, default="pending")
    gateway = Column(String, default="sillientpay")
    webhook_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)
    order = relationship("Order", back_populates="payments")

class SupportTicket(Base):
    __tablename__ = "support_tickets"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    ticket_number = Column(String, unique=True)
    subject = Column(String)
    message = Column(Text)
    status = Column(String, default="open")
    priority = Column(String, default="normal")
    responses = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="tickets")

class UserAnalytics(Base):
    __tablename__ = "user_analytics"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    event_type = Column(String)
    event_data = Column(JSON, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="analytics")

class SystemConfig(Base):
    __tablename__ = "system_config"
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True)
    value = Column(JSON)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)

# Criar tabelas
Base.metadata.create_all(bind=engine)

# Sistema de Puxada de Dados Automática
class DataPuller:
    def __init__(self):
        self.api_keys = {
            "sillientpay": os.getenv("SILLIENTPAY_API_KEY", ""),
            "mercadopago": os.getenv("MP_ACCESS_TOKEN", ""),
        }
    
    async def pull_cc_data(self, product_type: str) -> Dict[str, Any]:
        """Puxa dados de CC baseado no tipo do produto"""
        try:
            # Simulação de puxada de dados - em produção, conectar APIs reais
            data_templates = {
                "CC FULL BASIC": {
                    "card_number": self.generate_card_number(),
                    "cvv": self.generate_cvv(),
                    "expiry": self.generate_expiry(),
                    "holder": self.generate_holder_name(),
                    "billing_zip": self.generate_zip(),
                    "billing_address": self.generate_address()
                },
                "CC FULL GOLD": {
                    "card_number": self.generate_card_number(),
                    "cvv": self.generate_cvv(),
                    "expiry": self.generate_expiry(),
                    "holder": self.generate_holder_name(),
                    "billing_zip": self.generate_zip(),
                    "billing_address": self.generate_address(),
                    "bank_phone": self.generate_phone(),
                    "security_question": self.generate_security_question()
                },
                "CC FULL BUSINESS": {
                    "card_number": self.generate_card_number(),
                    "cvv": self.generate_cvv(),
                    "expiry": self.generate_expiry(),
                    "holder": self.generate_holder_name(),
                    "billing_zip": self.generate_zip(),
                    "billing_address": self.generate_address(),
                    "bank_phone": self.generate_phone(),
                    "security_question": self.generate_security_question(),
                    "ssn": self.generate_ssn(),
                    "dob": self.generate_dob()
                },
                "CC FULL INFINITE": {
                    "card_number": self.generate_card_number(),
                    "cvv": self.generate_cvv(),
                    "expiry": self.generate_expiry(),
                    "holder": self.generate_holder_name(),
                    "billing_zip": self.generate_zip(),
                    "billing_address": self.generate_address(),
                    "bank_phone": self.generate_phone(),
                    "security_question": self.generate_security_question(),
                    "ssn": self.generate_ssn(),
                    "dob": self.generate_dob(),
                    "mmn": self.generate_mmn(),
                    "pin": self.generate_pin()
                },
                "CC FULL BLACK": {
                    "card_number": self.generate_card_number(),
                    "cvv": self.generate_cvv(),
                    "expiry": self.generate_expiry(),
                    "holder": self.generate_holder_name(),
                    "billing_zip": self.generate_zip(),
                    "billing_address": self.generate_address(),
                    "bank_phone": self.generate_phone(),
                    "security_question": self.generate_security_question(),
                    "ssn": self.generate_ssn(),
                    "dob": self.generate_dob(),
                    "mmn": self.generate_mmn(),
                    "pin": self.generate_pin(),
                    "routing": self.generate_routing(),
                    "account": self.generate_account()
                }
            }
            
            return data_templates.get(product_type, {})
        except Exception as e:
            logger.error(f"Erro na puxada de dados: {e}")
            return {}
    
    def generate_card_number(self) -> str:
        """Gera número de cartão válido"""
        return f"{random.randint(4000, 4999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"
    
    def generate_cvv(self) -> str:
        """Gera CVV"""
        return f"{random.randint(100, 999)}"
    
    def generate_expiry(self) -> str:
        """Gera data de expiração"""
        month = f"{random.randint(1, 12):02d}"
        year = f"{random.randint(24, 30)}"
        return f"{month}/{year}"
    
    def generate_holder_name(self) -> str:
        """Gera nome do titular"""
        first_names = ["JOHN", "MARY", "JAMES", "ROBERT", "MICHAEL", "WILLIAM", "DAVID", "RICHARD"]
        last_names = ["SMITH", "JOHNSON", "WILLIAMS", "BROWN", "JONES", "GARCIA", "MILLER", "DAVIS"]
        return f"{random.choice(first_names)} {random.choice(last_names)}"
    
    def generate_zip(self) -> str:
        """Gera CEP"""
        return f"{random.randint(10000, 99999)}-{random.randint(100, 999)}"
    
    def generate_address(self) -> str:
        """Gera endereço"""
        streets = ["Main St", "Oak Ave", "Pine Rd", "Elm Dr", "Maple Ln"]
        return f"{random.randint(100, 9999)} {random.choice(streets)}"
    
    def generate_phone(self) -> str:
        """Gera telefone"""
        return f"({random.randint(100, 999)}) {random.randint(100, 999)}-{random.randint(1000, 9999)}"
    
    def generate_security_question(self) -> str:
        """Gera pergunta de segurança"""
        questions = [
            "What was your first pet's name?",
            "What is your mother's maiden name?",
            "What city were you born in?",
            "What is your favorite color?"
        ]
        return random.choice(questions)
    
    def generate_ssn(self) -> str:
        """Gera SSN"""
        return f"{random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(1000, 9999)}"
    
    def generate_dob(self) -> str:
        """Gera data de nascimento"""
        year = random.randint(1960, 2000)
        month = f"{random.randint(1, 12):02d}"
        day = f"{random.randint(1, 28):02d}"
        return f"{month}/{day}/{year}"
    
    def generate_mmn(self) -> str:
        """Gera nome da mãe"""
        names = ["MARIA", "JOSEFA", "ANA", "CARMEN", "ROSA", "LUISA", "TERESA", "ISABEL"]
        return random.choice(names)
    
    def generate_pin(self) -> str:
        """Gera PIN"""
        return f"{random.randint(1000, 9999)}"
    
    def generate_routing(self) -> str:
        """Gera routing number"""
        return f"{random.randint(100000000, 999999999)}"
    
    def generate_account(self) -> str:
        """Gera número de conta"""
        return f"{random.randint(1000000, 9999999)}"

# Sistema de Pagamento Avançado
class PaymentProcessor:
    def __init__(self):
        self.sillientpay_key = os.getenv("SILLIENTPAY_API_KEY", "")
        self.mp_key = os.getenv("MP_ACCESS_TOKEN", "")
    
    async def create_payment(self, amount: float, order_id: str, user_email: str = None) -> Dict[str, Any]:
        """Cria pagamento automatizado"""
        try:
            if self.sillientpay_key:
                return await self._create_sillientpay_payment(amount, order_id, user_email)
            elif self.mp_key:
                return await self._create_mp_payment(amount, order_id, user_email)
            else:
                # Simulação de pagamento para testes
                return {
                    "id": f"TEST_{order_id}",
                    "qr_code": f"QR_CODE_SIMULATED_{order_id}",
                    "status": "pending"
                }
        except Exception as e:
            logger.error(f"Erro ao criar pagamento: {e}")
            return {"error": str(e)}
    
    async def _create_sillientpay_payment(self, amount: float, order_id: str, user_email: str) -> Dict[str, Any]:
        """Cria pagamento SillientPay"""
        url = "https://api.sillientpay.com/v1/payments"
        headers = {
            "Authorization": f"Bearer {self.sillientpay_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "amount": int(amount * 100),
            "currency": "BRL",
            "orderId": order_id,
            "paymentMethod": "pix",
            "webhookUrl": f"{BASE_URL}/webhook/sillientpay",
            "customer": {
                "email": user_email or "cliente@tks777.com"
            }
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
    
    async def _create_mp_payment(self, amount: float, order_id: str, user_email: str) -> Dict[str, Any]:
        """Cria pagamento Mercado Pago"""
        url = "https://api.mercadopago.com/v1/payments"
        headers = {
            "Authorization": f"Bearer {self.mp_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "transaction_amount": amount,
            "description": f"TKS777 Order #{order_id}",
            "payment_method_id": "pix",
            "payer": {"email": user_email or "cliente@tks777.com"}
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=30)
            return response.json()

# Sistema de Delivery Automatizado
class DeliverySystem:
    def __init__(self):
        self.data_puller = DataPuller()
    
    async def process_delivery(self, order_id: int) -> bool:
        """Processa delivery automático do pedido"""
        try:
            db = SessionLocal()
            order = db.query(Order).filter(Order.id == order_id).first()
            
            if not order:
                db.close()
                return False
            
            # Gerar dados para cada item
            for item in order.items:
                product = db.query(Product).filter(Product.id == item.product_id).first()
                if product:
                    delivery_data = await self.data_puller.pull_cc_data(product.name)
                    item.delivery_data = delivery_data
                    product.purchase_count += 1
            
            order.delivery_status = "delivered"
            order.delivery_data = {
                "delivered_at": datetime.utcnow().isoformat(),
                "method": "automated"
            }
            
            db.commit()
            db.close()
            
            # Enviar notificação para o usuário
            await self._send_delivery_notification(order)
            
            return True
        except Exception as e:
            logger.error(f"Erro no delivery: {e}")
            return False
    
    async def _send_delivery_notification(self, order: Order):
        """Envia notificação de delivery"""
        try:
            db = SessionLocal()
            user = db.query(User).filter(User.id == order.user_id).first()
            
            if user:
                message = f" Seu pedido #{order.order_number} foi entregue!\n\n"
                message += "Dados enviados com sucesso. Verifique suas informações.\n\n"
                message += "Obrigado por comprar na TKS777! "
                
                # Enviar mensagem via Telegram
                bot = Bot(token=BOT_TOKEN)
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=message,
                    parse_mode="Markdown"
                )
            
            db.close()
        except Exception as e:
            logger.error(f"Erro ao enviar notificação: {e}")

# Sistema de Analytics
class AnalyticsSystem:
    @staticmethod
    def track_user_event(user_id: int, event_type: str, event_data: Dict[str, Any] = None):
        """Rastreia eventos do usuário"""
        try:
            db = SessionLocal()
            analytics = UserAnalytics(
                user_id=user_id,
                event_type=event_type,
                event_data=event_data or {}
            )
            db.add(analytics)
            db.commit()
            db.close()
        except Exception as e:
            logger.error(f"Erro no analytics: {e}")
    
    @staticmethod
    def get_sales_report(days: int = 7) -> Dict[str, Any]:
        """Gera relatório de vendas"""
        try:
            db = SessionLocal()
            start_date = datetime.utcnow() - timedelta(days=days)
            
            orders = db.query(Order).filter(
                Order.created_at >= start_date,
                Order.status == "completed"
            ).all()
            
            total_revenue = sum(o.total_price for o in orders)
            total_orders = len(orders)
            
            # Top produtos
            top_products = {}
            for order in orders:
                for item in order.items:
                    product_name = item.product.name
                    if product_name not in top_products:
                        top_products[product_name] = 0
                    top_products[product_name] += item.quantity
            
            db.close()
            
            return {
                "period": f"{days} dias",
                "total_revenue": total_revenue,
                "total_orders": total_orders,
                "avg_order_value": total_revenue / total_orders if total_orders > 0 else 0,
                "top_products": dict(sorted(top_products.items(), key=lambda x: x[1], reverse=True)[:5])
            }
        except Exception as e:
            logger.error(f"Erro no relatório: {e}")
            return {}

# Utilitários
class Utils:
    @staticmethod
    def format_currency(value: float) -> str:
        return f"R$ {value:.2f}".replace(".", ",")
    
    @staticmethod
    def generate_order_number() -> str:
        return f"TKS{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"
    
    @staticmethod
    def generate_referral_code() -> str:
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    @staticmethod
    def get_main_menu_keyboard(is_admin: bool = False, is_vip: bool = False):
        keyboard = [
            [InlineKeyboardButton(" Catálogo", callback_data="catalog")],
            [InlineKeyboardButton(" Carrinho", callback_data="view_cart")],
            [InlineKeyboardButton(" Meus Pedidos", callback_data="my_orders")],
            [InlineKeyboardButton(" Suporte", callback_data="support")],
            [InlineKeyboardButton(" Minha Conta", callback_data="my_account")]
        ]
        
        if is_vip:
            keyboard.insert(-1, [InlineKeyboardButton(" VIP", callback_data="vip_menu")])
        
        if is_admin:
            keyboard.append([InlineKeyboardButton(" Admin", callback_data="admin_panel")])
        
        return InlineKeyboardMarkup(keyboard)

# Handlers principais
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler do comando start com analytics"""
    try:
        user = update.effective_user
        db = SessionLocal()
        
        # Criar ou buscar usuário
        db_user = db.query(User).filter(User.telegram_id == user.id).first()
        if not db_user:
            referral_code = Utils.generate_referral_code()
            db_user = User(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                referral_code=referral_code,
                is_admin=user.id in ADMIN_IDS
            )
            db.add(db_user)
            db.commit()
            
            # Analytics: novo usuário
            AnalyticsSystem.track_user_event(db_user.id, "new_user", {
                "source": "telegram",
                "username": user.username
            })
        
        # Atualizar última atividade
        db_user.last_active = datetime.utcnow()
        db.commit()
        
        is_admin = db_user.is_admin
        is_vip = db_user.is_vip
        db.close()
        
        # Analytics: acesso ao bot
        AnalyticsSystem.track_user_event(user.id, "bot_access")
        
        # Enviar banner se existir
        banner_path = "banners/welcome_banner.jpg"
        if os.path.exists(banner_path):
            try:
                with open(banner_path, 'rb') as photo:
                    await update.message.reply_photo(
                        photo=photo,
                        caption=f" Olá {user.first_name}!\n\n Bem-vindo à TKS777 PRO!\n Sistema automatizado de vendas.\nUse os botões abaixo para navegar.",
                        reply_markup=Utils.get_main_menu_keyboard(is_admin, is_vip)
                    )
            except Exception as e:
                logger.error(f"Erro ao enviar banner: {e}")
                await update.message.reply_text(
                    f" Olá {user.first_name}!\n\n Bem-vindo à TKS777 PRO!\n Sistema automatizado de vendas.",
                    reply_markup=Utils.get_main_menu_keyboard(is_admin, is_vip)
                )
        else:
            await update.message.reply_text(
                f" Olá {user.first_name}!\n\n Bem-vindo à TKS777 PRO!\n Sistema automatizado de vendas.",
                reply_markup=Utils.get_main_menu_keyboard(is_admin, is_vip)
            )
    except Exception as e:
        logger.error(f"Erro no start: {e}")
        await update.message.reply_text("Erro ao processar mensagem. Tente novamente.")

async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Catálogo avançado com analytics"""
    try:
        query = update.callback_query
        await query.answer()
        
        db = SessionLocal()
        products = db.query(Product).filter(Product.is_available == True).all()
        db.close()
        
        if not products:
            await query.edit_message_text(" Nenhum produto disponível no momento.")
            return
        
        # Analytics: visualização do catálogo
        AnalyticsSystem.track_user_event(query.from_user.id, "catalog_view")
        
        # Criar teclado com produtos
        text = " *Catálogo TKS777 PRO*\n\n"
        
        for product in products:
            icon = " " if product.is_featured else ""
            text += f"{icon}*{product.name}*\n{Utils.format_currency(product.price)}\n"
            if product.stock < 10:
                text += f" Apenas {product.stock} disponíveis!\n"
            text += "\n"
        
        keyboard = []
        for product in products:
            keyboard.append([InlineKeyboardButton(f"{product.name}", callback_data=f"product_{product.id}")])
        keyboard.append([InlineKeyboardButton(" Menu Principal", callback_data="main_menu")])
        
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Erro no catalog: {e}")

async def product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detalhes do produto com analytics"""
    try:
        query = update.callback_query
        await query.answer()
        
        product_id = int(query.data.split("_")[1])
        
        db = SessionLocal()
        product = db.query(Product).filter(Product.id == product_id).first()
        
        if not product:
            await query.edit_message_text("Produto não encontrado.")
            db.close()
            return
        
        # Incrementar visualizações
        product.view_count += 1
        db.commit()
        
        # Analytics: visualização do produto
        AnalyticsSystem.track_user_event(query.from_user.id, "product_view", {
            "product_id": product_id,
            "product_name": product.name
        })
        
        text = f"*{product.name}*\n\n"
        text += f"{product.description}\n\n"
        text += f" {Utils.format_currency(product.price)}\n"
        text += f" Estoque: {product.stock}\n"
        text += f" Visualizações: {product.view_count}\n"
        text += f" Vendidos: {product.purchase_count}\n"
        
        if product.is_featured:
            text += "\n PRODUTO DESTAQUE "
        
        keyboard = [
            [InlineKeyboardButton(" Adicionar ao Carrinho", callback_data=f"add_to_cart_{product_id}")],
            [InlineKeyboardButton(" Voltar ao Catálogo", callback_data="catalog")]
        ]
        
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        db.close()
    except Exception as e:
        logger.error(f"Erro no product_detail: {e}")

async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Adicionar ao carrinho com analytics"""
    try:
        query = update.callback_query
        await query.answer()
        
        product_id = int(query.data.split("_")[3])
        
        cart = context.user_data.get("cart", {})
        cart[product_id] = cart.get(product_id, 0) + 1
        context.user_data["cart"] = cart
        
        # Analytics: adição ao carrinho
        AnalyticsSystem.track_user_event(query.from_user.id, "add_to_cart", {
            "product_id": product_id,
            "cart_total": len(cart)
        })
        
        await query.edit_message_text(" Produto adicionado ao carrinho!")
        
        db = SessionLocal()
        db_user = db.query(User).filter(User.telegram_id == query.from_user.id).first()
        is_admin = db_user.is_admin if db_user else False
        is_vip = db_user.is_vip if db_user else False
        db.close()
        
        await query.message.reply_text("Use o menu para continuar ou finalizar.", reply_markup=Utils.get_main_menu_keyboard(is_admin, is_vip))
    except Exception as e:
        logger.error(f"Erro no add_to_cart: {e}")

async def checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Checkout automatizado com analytics"""
    try:
        query = update.callback_query
        await query.answer()
        
        cart = context.user_data.get("cart", {})
        if not cart:
            await query.edit_message_text("Carrinho vazio. Adicione produtos antes de finalizar.")
            return
        
        user_id = update.effective_user.id
        db = SessionLocal()
        db_user = db.query(User).filter(User.telegram_id == user_id).first()
        
        # Calcular total
        total = 0
        for pid, qty in cart.items():
            p = db.query(Product).filter(Product.id == pid).first()
            if p:
                total += p.price * qty
        
        # Criar pedido
        order_number = Utils.generate_order_number()
        order = Order(
            user_id=db_user.id,
            order_number=order_number,
            total_price=total,
            status="pending"
        )
        db.add(order)
        db.commit()
        
        # Adicionar itens
        for pid, qty in cart.items():
            p = db.query(Product).filter(Product.id == pid).first()
            if p:
                item = OrderItem(order_id=order.id, product_id=pid, quantity=qty, price=p.price)
                db.add(item)
        
        db.commit()
        
        # Analytics: início do checkout
        AnalyticsSystem.track_user_event(user_id, "checkout_started", {
            "order_id": order.id,
            "order_number": order_number,
            "total_value": total
        })
        
        # Criar pagamento
        payment_processor = PaymentProcessor()
        payment_data = await payment_processor.create_payment(total, order_number, db_user.email)
        
        if "error" in payment_data:
            await query.message.reply_text(f" Erro ao gerar pagamento: {payment_data['error']}")
        else:
            # Salvar informações de pagamento
            payment = Payment(
                order_id=order.id,
                payment_id=payment_data.get("id", f"PAY_{order_number}"),
                amount=total,
                status="pending",
                gateway="sillientpay"
            )
            db.add(payment)
            
            order.payment_id = payment_data.get("id")
            order.payment_qr = payment_data.get("qr_code", "")
            db.commit()
            
            await query.message.reply_text(
                f" Pedido #{order_number} gerado!\n"
                f"Valor: {Utils.format_currency(total)}\n\n"
                f"Aguardando confirmação de pagamento.\n"
                f"Após pagamento, delivery automático!"
            )
        
        context.user_data["cart"] = {}
        await query.message.reply_text(" Pedido finalizado!", reply_markup=Utils.get_main_menu_keyboard(db_user.is_admin, db_user.is_vip))
        db.close()
    except Exception as e:
        logger.error(f"Erro no checkout: {e}")

# Handlers faltantes
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler do menu principal"""
    try:
        query = update.callback_query
        await query.answer()
        
        db = SessionLocal()
        db_user = db.query(User).filter(User.telegram_id == query.from_user.id).first()
        is_admin = db_user.is_admin if db_user else False
        is_vip = db_user.is_vip if db_user else False
        db.close()
        
        await query.edit_message_text("Menu Principal:", reply_markup=Utils.get_main_menu_keyboard(is_admin, is_vip))
    except Exception as e:
        logger.error(f"Erro no main_menu: {e}")

async def view_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ver carrinho"""
    try:
        query = update.callback_query
        await query.answer()
        
        cart = context.user_data.get("cart", {})
        if not cart:
            await query.edit_message_text(" Seu carrinho está vazio.")
            return
        
        db = SessionLocal()
        total = 0
        text = " *Seu Carrinho*\n\n"
        
        for pid, qty in cart.items():
            product = db.query(Product).filter(Product.id == pid).first()
            if product:
                subtotal = product.price * qty
                total += subtotal
                text += f"{product.name} x{qty} = {Utils.format_currency(subtotal)}\n"
        
        db.close()
        text += f"\n*Total: {Utils.format_currency(total)}*"
        
        keyboard = [
            [InlineKeyboardButton(" Atualizar", callback_data="view_cart")],
            [InlineKeyboardButton(" Finalizar Compra", callback_data="checkout")],
            [InlineKeyboardButton(" Limpar Carrinho", callback_data="clear_cart")],
            [InlineKeyboardButton(" Menu Principal", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Erro no view_cart: {e}")

async def clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Limpar carrinho"""
    try:
        query = update.callback_query
        await query.answer()
        context.user_data["cart"] = {}
        
        db = SessionLocal()
        db_user = db.query(User).filter(User.telegram_id == query.from_user.id).first()
        is_admin = db_user.is_admin if db_user else False
        is_vip = db_user.is_vip if db_user else False
        db.close()
        
        await query.edit_message_text(" Carrinho limpo!", reply_markup=Utils.get_main_menu_keyboard(is_admin, is_vip))
    except Exception as e:
        logger.error(f"Erro no clear_cart: {e}")

async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Meus pedidos"""
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        db = SessionLocal()
        db_user = db.query(User).filter(User.telegram_id == user_id).first()
        
        if not db_user:
            await query.edit_message_text("Usuário não encontrado.")
            db.close()
            return
        
        orders = db.query(Order).filter(Order.user_id == db_user.id).order_by(Order.created_at.desc()).all()
        db.close()
        
        if not orders:
            await query.edit_message_text("Você ainda não fez nenhum pedido.")
            return
        
        text = " *Seus Pedidos*\n\n"
        for o in orders:
            text += f"Pedido #{o.order_number} - {o.created_at.strftime('%d/%m/%Y %H:%M')}\n"
            text += f"Total: {Utils.format_currency(o.total_price)} - Status: {' Pago' if o.status == 'completed' else ' Pendente'}\n\n"
        
        await query.edit_message_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Erro no my_orders: {e}")

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Suporte"""
    try:
        query = update.callback_query
        await query.answer()
        
        db = SessionLocal()
        db_user = db.query(User).filter(User.telegram_id == query.from_user.id).first()
        is_admin = db_user.is_admin if db_user else False
        is_vip = db_user.is_vip if db_user else False
        db.close()
        
        await query.edit_message_text(
            " *Suporte TKS777 PRO*\n\n"
            "Telegram: @TKS777\n"
            "Resposta em até 24h\n\n"
            "VIP: atendimento prioritário",
            parse_mode="Markdown",
            reply_markup=Utils.get_main_menu_keyboard(is_admin, is_vip)
        )
    except Exception as e:
        logger.error(f"Erro no support: {e}")

async def my_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Minha conta"""
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        db = SessionLocal()
        db_user = db.query(User).filter(User.telegram_id == user_id).first()
        
        if db_user:
            text = f" *Minha Conta*\n\n"
            text += f"Nome: {db_user.first_name}\n"
            text += f"Username: @{db_user.username or 'não definido'}\n"
            text += f"E-mail: {db_user.email or 'não informado'}\n"
            text += f"Total gasto: {Utils.format_currency(db_user.total_spent)}\n"
            text += f"Pedidos: {db_user.total_orders}\n"
            text += f"Status: {' VIP' if db_user.is_vip else 'Normal'}\n"
            text += f"Código de referência: {db_user.referral_code}"
            
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=Utils.get_main_menu_keyboard(db_user.is_admin, db_user.is_vip))
        
        db.close()
    except Exception as e:
        logger.error(f"Erro no my_account: {e}")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Painel admin"""
    try:
        query = update.callback_query
        await query.answer()
        
        if query.from_user.id not in ADMIN_IDS:
            await query.edit_message_text("Acesso negado.")
            return
        
        db = SessionLocal()
        total_users = db.query(User).count()
        total_orders = db.query(Order).count()
        total_revenue = sum(o.total_price for o in db.query(Order).filter(Order.status == "completed").all())
        db.close()
        
        text = " *Painel Admin TKS777 PRO*\n\n"
        text += f" Usuários: {total_users}\n"
        text += f" Pedidos: {total_orders}\n"
        text += f" Faturamento: {Utils.format_currency(total_revenue)}\n\n"
        text += "Funcionalidades em desenvolvimento..."
        
        await query.edit_message_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Erro no admin_panel: {e}")

# Webhook avançado
app_webhook = FastAPI()

@app_webhook.get("/")
async def root():
    return {"status": "TKS777 PRO API Online", "version": "3.0"}

@app_webhook.post("/webhook/sillientpay")
async def sillientpay_webhook(request: Request, background_tasks: BackgroundTasks):
    """Webhook SillientPay com delivery automático"""
    try:
        payload = await request.json()
        logger.info(f"Webhook SillientPay recebido: {payload}")
        
        if payload.get("status") == "paid":
            order_id = payload.get("orderId")
            if order_id:
                db = SessionLocal()
                order = db.query(Order).filter(Order.order_number == order_id).first()
                
                if order and order.status != "completed":
                    # Atualizar status
                    order.status = "completed"
                    
                    # Atualizar pagamento
                    payment = db.query(Payment).filter(Payment.order_id == order.id).first()
                    if payment:
                        payment.status = "confirmed"
                        payment.confirmed_at = datetime.utcnow()
                        payment.webhook_data = payload
                    
                    # Atualizar total gasto do usuário
                    user = db.query(User).filter(User.id == order.user_id).first()
                    if user:
                        user.total_spent += order.total_price
                        
                        # Analytics: venda completada
                        AnalyticsSystem.track_user_event(user.id, "purchase_completed", {
                            "order_id": order.id,
                            "order_value": order.total_price
                        })
                    
                    db.commit()
                    
                    # Iniciar delivery automático
                    delivery_system = DeliverySystem()
                    background_tasks.add_task(delivery_system.process_delivery, order.id)
                    
                    logger.info(f"Pedido {order_id} pago e delivery iniciado")
                
                db.close()
        
        return {"status": "ok", "message": "Webhook processado"}
    except Exception as e:
        logger.error(f"Erro no webhook: {e}")
        return {"status": "error", "message": str(e)}

@app_webhook.get("/analytics/sales")
async def get_sales_analytics(days: int = 7):
    """Endpoint para analytics de vendas"""
    try:
        report = AnalyticsSystem.get_sales_report(days)
        return JSONResponse(content=report)
    except Exception as e:
        logger.error(f"Erro no analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Sistema principal
delivery_system = DeliverySystem()

def run_webhook():
    uvicorn.run(app_webhook, host=HOST, port=PORT, log_level="warning")

def create_products():
    """Cria produtos iniciais"""
    db = SessionLocal()
    
    if db.query(Product).count() == 0:
        products = [
            Product(
                name="CC FULL BASIC",
                description="Pacote básico com informações completas do cartão",
                price=49.99,
                category="basic",
                tags=["basic", "starter", "cc"],
                is_featured=True
            ),
            Product(
                name="CC FULL GOLD",
                description="Pacote gold com dados premium e informações bancárias",
                price=59.99,
                category="gold",
                tags=["gold", "premium", "banking"],
                is_featured=True
            ),
            Product(
                name="CC FULL BUSINESS",
                description="Pacote business para empresas com dados completos",
                price=44.99,
                category="business",
                tags=["business", "corporate", "full"]
            ),
            Product(
                name="CC FULL INFINITE",
                description="Pacote infinite com acesso ilimitado e dados VIP",
                price=54.99,
                category="infinite",
                tags=["infinite", "unlimited", "vip"]
            ),
            Product(
                name="CC FULL BLACK",
                description="Pacote black exclusivo com todos os dados possíveis",
                price=64.99,
                category="black",
                tags=["black", "exclusive", "ultimate"],
                is_featured=True
            ),
            Product(
                name="DOC FAKE APP",
                description="Aplicativo para documentos personalizados",
                price=69.99,
                category="documents",
                tags=["docs", "fake", "documents"]
            ),
            Product(
                name="COMPROVANTE FK",
                description="Comprovantes personalizados diversos",
                price=15.99,
                category="documents",
                tags=["receipt", "proof", "document"]
            ),
        ]
        
        for product in products:
            db.add(product)
        
        db.commit()
        logger.info("7 produtos criados com sucesso!")
    
    db.close()

def main():
    logger.info(" Iniciando TKS777 PRO...")
    
    # Iniciar webhook
    webhook_thread = threading.Thread(target=run_webhook, daemon=True)
    webhook_thread.start()
    logger.info(f"Webhook iniciado na porta {PORT}")
    
    # Criar produtos
    create_products()
    
    # Configurar bot
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(catalog, pattern="^catalog$"))
    app.add_handler(CallbackQueryHandler(product_detail, pattern=r"^product_(\d+)$"))
    app.add_handler(CallbackQueryHandler(add_to_cart, pattern=r"^add_to_cart_(\d+)$"))
    app.add_handler(CallbackQueryHandler(checkout, pattern="^checkout$"))
    
    # Adicionar handlers faltantes
    app.add_handler(CallbackQueryHandler(main_menu, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(view_cart, pattern="^view_cart$"))
    app.add_handler(CallbackQueryHandler(clear_cart, pattern="^clear_cart$"))
    app.add_handler(CallbackQueryHandler(my_orders, pattern="^my_orders$"))
    app.add_handler(CallbackQueryHandler(support, pattern="^support$"))
    app.add_handler(CallbackQueryHandler(my_account, pattern="^my_account$"))
    app.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_panel$"))
    
    logger.info(" TKS777 PRO iniciado com sucesso!")
    print(" TKS777 PRO - Sistema Automatizado Online! ")
    
    try:
        app.run_polling()
    except KeyboardInterrupt:
        logger.info("Bot encerrado pelo usuário")
    except Exception as e:
        logger.error(f"Erro fatal: {e}")

if __name__ == "__main__":
    main()
