#!/usr/bin/env python3
"""
Bot de Vendas para Telegram - Integração com SillientPay
Versão: 2.1
Configuração via variáveis de ambiente para deploy em serviços gratuitos.
"""

import os
import logging
import base64
import threading
from io import BytesIO
from datetime import datetime, timedelta
from typing import Optional, Tuple

# Carregar variáveis de ambiente (Railway usa variáveis de ambiente do sistema)
try:
    from dotenv import load_dotenv
    load_dotenv()  # Carrega .env se existir localmente, mas não falha se não existir
except ImportError:
    pass  # python-dotenv não é obrigatório para Railway

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    filters, ConversationHandler, ContextTypes
)
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
import uuid
import random
from decimal import Decimal
import requests
from fastapi import FastAPI, Request, BackgroundTasks
import uvicorn
import httpx

print("OK Funcionalidades avancadas integradas com sucesso!")

# ======================= CONFIGURAÇÃO / AMBIENTE =======================
# Use variáveis de ambiente para deploy em serviços gratuitos como Railway, Render, Fly.io, etc.
BOT_TOKEN = os.getenv("BOT_TOKEN", "SEU_TOKEN_AQUI")
ADMIN_IDS = [8649452369]  # Pode adicionar mais: [123, 456]
BASE_URL = os.getenv("BASE_URL", "https://seu-app-publico.app").rstrip("/")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", BASE_URL)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///sales_bot.db")
PORT = int(os.getenv("PORT", "8002"))
HOST = os.getenv("HOST", "0.0.0.0")

# Chaves de pagamento (opcional – deixe vazio se não for usar)
MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "")
MP_WEBHOOK_SECRET = os.getenv("MP_WEBHOOK_SECRET", "")
SILLIENTPAY_API_KEY = os.getenv("SILLIENTPAY_API_KEY", "")
SILLIENTPAY_WEBHOOK_SECRET = os.getenv("SILLIENTPAY_WEBHOOK_SECRET", "")

# ======================= FIM DAS CONFIGURAÇÕES =======================

# Verificação básica
if not BOT_TOKEN or BOT_TOKEN == "SEU_TOKEN_AQUI":
    raise ValueError("Você precisa colocar o token do bot na variável BOT_TOKEN")

# ======================= BANCO DE DADOS =======================
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Criar tabelas automaticamente se não existirem
Base.metadata.create_all(engine)

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
    loyalty = relationship("LoyaltyPoints", back_populates="user")

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    name = Column(String, index=True)
    description = Column(Text)
    price = Column(Float)
    stock = Column(Integer, default=999999)
    digital_file = Column(String, nullable=True)
    is_available = Column(Boolean, default=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    tags = Column(Text, nullable=True)  # JSON de tags
    view_count = Column(Integer, default=0)
    purchase_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    orders = relationship("OrderItem", back_populates="product")
    category = relationship("Category", back_populates="products")

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

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, index=True)
    description = Column(Text, nullable=True)
    icon = Column(String, nullable=True)  # Emoji para categoria
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    products = relationship("Product", back_populates="category")

class DiscountCode(Base):
    __tablename__ = "discount_codes"
    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, index=True)
    discount_type = Column(String, default="percentage")  # percentage or fixed
    discount_value = Column(Float)
    min_purchase = Column(Float, default=0.0)
    max_discount = Column(Float, nullable=True)
    usage_limit = Column(Integer, nullable=True)
    usage_count = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

class LoyaltyPoints(Base):
    __tablename__ = "loyalty_points"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    points = Column(Integer, default=0)
    points_earned = Column(Integer, default=0)
    points_spent = Column(Integer, default=0)
    level = Column(String, default="Bronze")  # Bronze, Prata, Ouro
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="loyalty")

class Analytics(Base):
    __tablename__ = "analytics"
    id = Column(Integer, primary_key=True)
    event_type = Column(String, index=True)  # view, add_to_cart, purchase, etc.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    value = Column(Float, nullable=True)  # valor da transação
    extra_data = Column(Text, nullable=True)  # dados adicionais em JSON
    created_at = Column(DateTime, default=datetime.utcnow)

class MarketingCampaign(Base):
    __tablename__ = "marketing_campaigns"
    id = Column(Integer, primary_key=True)
    name = Column(String, index=True)
    message = Column(Text)
    target_audience = Column(String, default="all")  # all, vip, new_users, inactive
    send_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    status = Column(String, default="pending")  # pending, sent, failed
    opens_count = Column(Integer, default=0)
    clicks_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))

# ======================= GATEWAY DE PAGAMENTO =======================
class MercadoPagoGateway:
    @staticmethod
    def create_payment(amount: float, order_id: int, user_email: str = None, payment_method: str = "pix"):
        if not MP_ACCESS_TOKEN:
            return {"error": "MP_ACCESS_TOKEN não configurado"}
        headers = {"Authorization": f"Bearer {MP_ACCESS_TOKEN}", "Content-Type": "application/json"}
        payload = {
            "transaction_amount": amount,
            "description": f"Pedido #{order_id}",
            "payment_method_id": "pix",
            "payer": {"email": user_email or "cliente@email.com"}
        }
        try:
            response = requests.post("https://api.mercadopago.com/v1/payments", headers=headers, json=payload, timeout=30)
            return response.json()
        except Exception as e:
            return {"error": str(e)}

class SillientPayGateway:
    @staticmethod
    def create_payment(amount: float, order_id: int, user_email: str = None, payment_method: str = "pix"):
        """Cria pagamento real via SillientPay API"""
        import httpx

        url = "https://api.sillientpay.com/v1/pix"
        headers = {
            "Authorization": f"Bearer {SILLIENTPAY_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "amount": int(amount * 100),  # Valor em centavos
            "currency": "BRL",
            "orderId": str(order_id),
            "paymentMethod": "pix",
            "webhookUrl": f"{WEBHOOK_URL}/webhook/sillientpay",
            "customer": {
                "email": user_email or "cliente@email.com"
            }
        }

        try:
            logging.info(f"💳 Criando pagamento SillientPay: R$ {amount:.2f} - Pedido #{order_id}")
            response = httpx.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()

            payment_data = response.json()
            logging.info(f"✅ Pagamento criado: {payment_data.get('id', 'N/A')}")

            return payment_data

        except httpx.HTTPStatusError as e:
            logging.error(f"❌ Erro HTTP SillientPay: {e.response.status_code} - {e.response.text}")
            return {"error": f"Erro HTTP: {e.response.status_code}", "details": e.response.text}

        except Exception as e:
            logging.error(f"❌ Erro geral SillientPay: {e}")
            return {"error": str(e)}

def create_payment(amount: float, order_id: int, user_email: str = None, payment_method: str = "pix"):
    if SILLIENTPAY_API_KEY:
        return SillientPayGateway.create_payment(amount, order_id, user_email, payment_method)
    elif MP_ACCESS_TOKEN:
        return MercadoPagoGateway.create_payment(amount, order_id, user_email, payment_method)
    else:
        # Simulação para testes - não gera pagamento real
        return {
            "id": f"SIM_{order_id}",
            "status": "pending",
            "qrCode": None,  # Sem QR code em modo de teste
            "brCode": None,  # Sem código copia-e-cola em modo de teste
            "simulation": True
        }

# ======================= UTILIDADES =======================
def format_currency(value: float) -> str:
    return f"R$ {value:.2f}".replace(".", ",")

def extract_pix_info(payment_data: dict) -> Tuple[Optional[str], Optional[str]]:
    qr_base64 = (
        payment_data.get("qrCode")
        or payment_data.get("qr_code_base64")
        or payment_data.get("qrCodeBase64")
        or payment_data.get("point_of_interaction", {})
        .get("transaction_data", {})
        .get("qr_code_base64")
    )

    copy_paste = (
        payment_data.get("brCode")
        or payment_data.get("br_code")
        or payment_data.get("copyPaste")
        or payment_data.get("copy_paste")
        or payment_data.get("copiaECola")
        or payment_data.get("pixCopyPaste")
        or payment_data.get("point_of_interaction", {})
        .get("transaction_data", {})
        .get("qr_code")
    )

    if isinstance(qr_base64, dict):
        qr_base64 = None
    if isinstance(copy_paste, dict):
        copy_paste = None

    return qr_base64, copy_paste

async def send_telegram_message(chat_id: int, text: str):
    """Envia mensagem via API do Telegram"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})

async def send_pix_instructions(
    *,
    chat_id: int,
    caption: str,
    qr_base64: Optional[str],
    copy_paste: Optional[str],
):
    if qr_base64:
        try:
            qr_bytes = base64.b64decode(qr_base64)
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
            async with httpx.AsyncClient() as client:
                files = {"photo": ("pix.png", qr_bytes)}
                data = {"chat_id": chat_id, "caption": caption}
                await client.post(url, data=data, files=files)
        except Exception:
            await send_telegram_message(chat_id, caption)
    else:
        await send_telegram_message(chat_id, caption)

    if copy_paste:
        await send_telegram_message(chat_id, f"📋 PIX Copia e Cola:\n`{copy_paste}`")

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

def get_main_menu_keyboard(is_admin: bool = False):
    keyboard = [
        [InlineKeyboardButton("⬛ Catálogo", callback_data="catalog")],
        [InlineKeyboardButton("� Carrinho", callback_data="view_cart")],
        [InlineKeyboardButton("� Pedidos", callback_data="my_orders")],
        [InlineKeyboardButton("🗂 Categorias", callback_data="categories")],
        [InlineKeyboardButton("👤 Conta", callback_data="my_account")],
        [InlineKeyboardButton("� Suporte", callback_data="support")]
    ]
    if is_admin:
        keyboard.append([InlineKeyboardButton("⚙ Admin", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Adicionar Produto", callback_data="admin_add_product")],
        [InlineKeyboardButton("📊 Ver Pedidos Pagos", callback_data="admin_orders")],
        [InlineKeyboardButton("🔙 Menu Principal", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_catalog_keyboard(products):
    keyboard = [[InlineKeyboardButton(p.name, callback_data=f"product_{p.id}")] for p in products]
    keyboard.append([InlineKeyboardButton("🔙 Menu Principal", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

def get_product_keyboard(product_id):
    keyboard = [
        [InlineKeyboardButton("⬛ Adicionar", callback_data=f"add_to_cart_{product_id}")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="catalog")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_cart_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔄 Atualizar", callback_data="view_cart")],
        [InlineKeyboardButton("⬛ Finalizar", callback_data="checkout")],
        [InlineKeyboardButton("🗑 Limpar", callback_data="clear_cart")],
        [InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ======================= HANDLERS =======================
ADD_PRODUCT_NAME, ADD_PRODUCT_DESC, ADD_PRODUCT_PRICE, ADD_PRODUCT_FILE = range(4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = SessionLocal()
    db_user = db.query(User).filter(User.telegram_id == user.id).first()
    if not db_user:
        db_user = User(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            is_admin=user.id in ADMIN_IDS
        )
        db.add(db_user)
        db.commit()
    is_admin = db_user.is_admin
    db.close()
    
    # Enviar banner de boas-vindas (se existir)
    banner_path = "banners/welcome_banner.jpg"
    if os.path.exists(banner_path):
        try:
            with open(banner_path, 'rb') as photo:
                await update.message.reply_photo(
                    photo=photo,
                    caption=f"⬛ {user.first_name}\n\nAcesso concedido.\nUse os botões abaixo.",
                    reply_markup=get_main_menu_keyboard(is_admin)
                )
        except Exception as e:
            logging.error(f"Erro ao enviar banner: {e}")
            # Fallback para mensagem de texto se falhar
            await update.message.reply_text(
                f"⬛ {user.first_name}\n\nAcesso concedido.\nUse os botões abaixo.",
                reply_markup=get_main_menu_keyboard(is_admin)
            )
    else:
        # Mensagem padrão se não houver banner
        await update.message.reply_text(
            f"⬛ {user.first_name}\n\nAcesso concedido.\nUse os botões abaixo.",
            reply_markup=get_main_menu_keyboard(is_admin)
        )

async def teste(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando de teste simples"""
    await update.message.reply_text("🤖 Bot funcionando! Sistema de teste ativo.")

async def teste_pagamento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Testa pagamento real com valor mínimo"""
    try:
        # Criar pedido de teste
        db = SessionLocal()
        release_expired_reservations(db)
        user = db.query(User).filter(User.telegram_id == update.effective_user.id).first()
        if not user:
            await update.message.reply_text("❌ Usuário não encontrado.")
            return

        # Criar pedido de teste com R$ 0,10
        order = Order(
            user_id=user.id,
            total_price=0.10,
            status="pending"
        )
        db.add(order)
        db.commit()

        # Tentar criar pagamento real
        payment_result = create_payment(0.10, order.id, user.username + "@teste.com")

        if "error" in payment_result:
            await update.message.reply_text(f"❌ Erro no pagamento: {payment_result['error']}")
        else:
            qr_base64, copy_paste = extract_pix_info(payment_result)
            payment_id = payment_result.get("id", "N/A")

            # Atualizar pedido com payment_id
            order.payment_id = payment_id
            order.payment_qr_base64 = qr_base64
            order.payment_copy_paste = copy_paste
            db.commit()

            await update.message.reply_text(
                f"💳 Pagamento de teste criado!\n\n"
                f"📄 ID: {payment_id}\n"
                f"💰 Valor: R$ 0,10\n"
                f"Use /pagar {order.id} para simular aprovação."
            )

            await send_pix_instructions(
                chat_id=update.effective_user.id,
                caption=f"💰 PIX - Pedido #{order.id}\nValor: {format_currency(order.total_price)}\n\nApós o pagamento, o produto será enviado.",
                qr_base64=qr_base64,
                copy_paste=copy_paste,
            )

        db.close()

    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {str(e)}")

async def pagar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simula aprovação de pagamento para teste"""
    try:
        if not context.args:
            await update.message.reply_text("❌ Uso: /pagar <id_do_pedido>")
            return

        order_id = int(context.args[0])
        db = SessionLocal()
        order = db.query(Order).filter(Order.id == order_id).first()

        if not order:
            await update.message.reply_text("❌ Pedido não encontrado.")
            db.close()
            return

        if order.status == "paid":
            await update.message.reply_text("✅ Este pedido já foi pago!")
            db.close()
            return

        # Simular aprovação do pagamento
        order.status = "paid"
        order.delivery_status = "processing"
        db.commit()

        # Entregar produto
        from concurrent.futures import ThreadPoolExecutor
        executor = ThreadPoolExecutor()
        executor.submit(deliver_digital_product, order.id)

        await update.message.reply_text(
            f"🎉 Pagamento aprovado!\n\n"
            f"📦 Pedido #{order.id}\n"
            f"💰 Valor: {format_currency(order.total_price)}\n"
            f"✅ Status: Pago\n\n"
            f"📧 Produto enviado para seu e-mail!"
        )

        db.close()

    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {str(e)}")

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    db = SessionLocal()
    db_user = db.query(User).filter(User.telegram_id == user_id).first()
    is_admin = db_user.is_admin if db_user else False
    db.close()
    try:
        await query.edit_message_text("Menu Principal:", reply_markup=get_main_menu_keyboard(is_admin))
    except Exception as e:
        # If edit fails, send new message
        await query.message.reply_text("Menu Principal:", reply_markup=get_main_menu_keyboard(is_admin))

async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db = SessionLocal()
    products = db.query(Product).filter(Product.is_available == True).all()
    db.close()
    if not products:
        await query.edit_message_text("📭 Nenhum produto disponível no momento.", reply_markup=get_main_menu_keyboard(False))
        return
    text = "📚 *Catálogo de Produtos*\n\n" + "\n".join(f"*{p.name}*\n💰 {format_currency(p.price)}\n" for p in products)
    try:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_catalog_keyboard(products))
    except Exception as e:
        # If edit fails, send new message
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=get_catalog_keyboard(products))

async def product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        parts = query.data.split("_")
        product_id = int(parts[1])
    except Exception as e:
        await query.message.reply_text(f"❌ Erro ao identificar produto: {str(e)}")
        return
    
    db = SessionLocal()
    product = db.query(Product).filter(Product.id == product_id).first()
    db.close()
    if not product:
        await query.message.reply_text("❌ Produto não encontrado.")
        return
    
    text = f"*{product.name}*\n\n{product.description}\n\n💰 {format_currency(product.price)}"
    try:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_product_keyboard(product.id))
    except Exception as e:
        # If edit fails, send new message
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=get_product_keyboard(product.id))

async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        # Extract product ID from callback_data
        parts = query.data.split("_")
        if len(parts) >= 4:
            product_id = int(parts[3])
        else:
            product_id = int(parts[2]) if len(parts) >= 3 else None
        
        if product_id is None:
            await query.message.reply_text("❌ Erro ao identificar produto.")
            return
    except Exception as e:
        await query.message.reply_text(f"❌ Erro: {str(e)}")
        return
    
    cart = context.user_data.get("cart", {})
    cart[product_id] = cart.get(product_id, 0) + 1
    context.user_data["cart"] = cart
    
    # Send confirmation as new message to avoid edit conflicts
    await query.message.reply_text("✅ Produto adicionado ao carrinho!")
    
    user_id = query.from_user.id
    db = SessionLocal()
    db_user = db.query(User).filter(User.telegram_id == user_id).first()
    is_admin = db_user.is_admin if db_user else False
    db.close()
    
    # Send menu as new message
    await query.message.reply_text("Use o menu para continuar ou finalizar.", reply_markup=get_main_menu_keyboard(is_admin))

async def view_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cart = context.user_data.get("cart", {})
    if not cart:
        try:
            await query.edit_message_text("🛒 Seu carrinho está vazio.", reply_markup=get_main_menu_keyboard(False))
        except:
            await query.message.reply_text("🛒 Seu carrinho está vazio.", reply_markup=get_main_menu_keyboard(False))
        return
    
    db = SessionLocal()
    total = 0
    text = "🛒 *Seu Carrinho*\n\n"
    for pid, qty in cart.items():
        product = db.query(Product).filter(Product.id == pid).first()
        if product:
            subtotal = product.price * qty
            total += subtotal
            text += f"{product.name} x{qty} = {format_currency(subtotal)}\n"
    db.close()
    text += f"\n*Total: {format_currency(total)}*"
    
    try:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_cart_keyboard())
    except Exception as e:
        # If edit fails, send new message
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=get_cart_keyboard())

async def clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["cart"] = {}
    try:
        await query.edit_message_text("🗑 Carrinho limpo!", reply_markup=get_main_menu_keyboard(False))
    except Exception as e:
        # If edit fails, send new message
        await query.message.reply_text("🗑 Carrinho limpo!", reply_markup=get_main_menu_keyboard(False))

async def checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cart = context.user_data.get("cart", {})
    if not cart:
        await query.edit_message_text("Carrinho vazio. Adicione produtos antes de finalizar.")
        return
    user_id = update.effective_user.id
    db = SessionLocal()
    db_user = db.query(User).filter(User.telegram_id == user_id).first()
    release_expired_reservations(db)
    if not db_user:
        await query.message.reply_text("❌ Usuário não encontrado.")
        db.close()
        return
    total = 0
    for pid, qty in cart.items():
        p = db.query(Product).filter(Product.id == pid).first()
        if p:
            if not p.is_available:
                await query.message.reply_text(f"❌ Produto indisponível: {p.name}")
                db.close()
                return
            if p.stock is not None and p.stock < qty:
                await query.message.reply_text(f"❌ Sem estoque para {p.name}. Disponível: {p.stock}")
                db.close()
                return
            total += p.price * qty

    order = Order(
        user_id=db_user.id,
        total_price=total,
        status="reserved",
        reserved_until=datetime.utcnow() + timedelta(minutes=30),
        delivery_status="pending",
    )
    db.add(order)
    db.commit()
    for pid, qty in cart.items():
        p = db.query(Product).filter(Product.id == pid).first()
        if p:
            item = OrderItem(order_id=order.id, product_id=pid, quantity=qty, price=p.price)
            db.add(item)
            if p.stock is not None:
                p.stock -= qty
    db.commit()
    
    # Chave PIX fixa para pagamento manual
    pix_key = "00020101021126580014br.gov.bcb.pix0136ef03c58f-5ee1-46e7-b7f3-7bf3912c045b5204000053039865802BR5922DAVI LUZ FERREIRA PUPP6008SOROCABA62070503***6304769E"
    
    context.user_data["pending_order_id"] = order.id
    
    keyboard = [[InlineKeyboardButton("⬛ Confirmar", callback_data=f"confirm_payment_{order.id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        f"⬛ *Pagamento PIX*\n\n"
        f"Pedido #{order.id}\n"
        f"Valor: {format_currency(total)}\n\n"
        f"Chave PIX:\n`{pix_key}`\n\n"
        f"Após pagamento, clique abaixo.",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    context.user_data["cart"] = {}
    db.close()

async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para botão 'Já paguei' - pede comprovante"""
    query = update.callback_query
    await query.answer()
    
    try:
        order_id = int(query.data.split("_")[2])
    except:
        await query.message.reply_text(" Erro ao identificar pedido.")
        return
    
    context.user_data["awaiting_receipt"] = order_id
    await query.message.reply_text(
        " *Envie o comprovante*\n\n"
        "Foto ou documento do comprovante PIX.",
        parse_mode="Markdown"
    )

async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para receber comprovante de pagamento"""
    if "awaiting_receipt" not in context.user_data:
        return
    
    order_id = context.user_data["awaiting_receipt"]
    del context.user_data["awaiting_receipt"]
    
    db = SessionLocal()
    order = db.query(Order).filter(Order.id == order_id).first()
    
    if not order:
        await update.message.reply_text(" Pedido não encontrado.")
        db.close()
        return
    
    # Marcar pedido como pago
    order.status = "paid"
    order.delivery_status = "processing"
    db.commit()
    db.close()
    
    # Enviar mensagem para chamar @TK_O202
    await update.message.reply_text(
        " *Comprovante recebido*\n\n"
        "Contate @TK_O202 para entrega.\n\n"
        "Pedido #" + str(order_id),
        parse_mode="Markdown"
    )

async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    text = "📦 *Seus Pedidos*\n\n"
    for o in orders:
        text += f"Pedido #{o.id} - {o.created_at.strftime('%d/%m/%Y %H:%M')}\n"
        text += f"Total: {format_currency(o.total_price)} - Status: {'✅ Pago' if o.status == 'paid' else '⏳ Pendente'}\n\n"
    await query.edit_message_text(text, parse_mode="Markdown")

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📞 *Suporte*\n\nE-mail: suporte@seudominio.com\nWhatsApp: (11) 99999-9999",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(False)
    )

async def my_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    db = SessionLocal()
    db_user = db.query(User).filter(User.telegram_id == user_id).first()
    if db_user:
        text = f"👤 *Minha Conta*\n\nNome: {db_user.first_name}\nUsername: @{db_user.username or 'não definido'}\nE-mail: {db_user.email or 'não informado'}"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_main_menu_keyboard(db_user.is_admin))
    db.close()

# ------------------- FUNCIONALIDADES AVANCADAS -------------------
async def categories_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu de categorias"""
    query = update.callback_query
    await query.answer()
    db = SessionLocal()
    categories = db.query(Category).filter(Category.is_active == True).all()
    db.close()
    
    if not categories:
        await query.edit_message_text(
            "📂 Nenhuma categoria disponível no momento.\n\nVolte mais tarde!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Menu Principal", callback_data="main_menu")]
            ])
        )
        return
    
    keyboard = [[InlineKeyboardButton(f"{cat.icon or '📂'} {cat.name}", callback_data=f"category_{cat.id}")] for cat in categories]
    keyboard.append([InlineKeyboardButton("🔙 Menu Principal", callback_data="main_menu")])
    
    await query.edit_message_text(
        "📂 *Categorias de Produtos*\n\nEscolha uma categoria:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra produtos por categoria"""
    query = update.callback_query
    await query.answer()
    
    try:
        category_id = int(query.data.split("_")[1])
    except:
        await query.edit_message_text("❌ Categoria inválida.")
        return
    
    db = SessionLocal()
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        db.close()
        await query.edit_message_text("❌ Categoria não encontrada.")
        return
    
    products = db.query(Product).filter(
        Product.category_id == category_id,
        Product.is_available == True
    ).all()
    db.close()
    
    if not products:
        await query.edit_message_text(f"📂 Nenhum produto na categoria {category.icon or '📂'} {category.name}.")
        return
    
    text = f"{category.icon or '📂'} *{category.name}*\n\n"
    for p in products:
        text += f"*{p.name}*\n💰 {format_currency(p.price)}\n\n"
    
    keyboard = [[InlineKeyboardButton(p.name, callback_data=f"product_{p.id}")] for p in products]
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="categories")])
    keyboard.append([InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")])
    
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def view_loyalty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ver pontos de fidelidade do usuário"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    db = SessionLocal()
    loyalty = db.query(LoyaltyPoints).filter(LoyaltyPoints.user_id == user_id).first()
    db.close()
    
    if not loyalty:
        points = 0
        level = "Bronze"
        next_level = "Prata"
        points_needed = 500
    else:
        points = loyalty.points
        level = loyalty.level
        if level == "Bronze":
            next_level = "Prata"
            points_needed = max(0, 500 - loyalty.points_earned)
        elif level == "Prata":
            next_level = "Ouro"
            points_needed = max(0, 1000 - loyalty.points_earned)
        else:
            next_level = "Ouro"
            points_needed = 0
    
    text = f"⭐ *Meus Pontos de Fidelidade*\n\n"
    text += f"🏆 *Nível Atual:* {level}\n"
    text += f"💎 *Pontos Atuais:* {points}\n"
    text += f"📈 *Próximo Nível:* {next_level}\n"
    text += f"🎯 *Pontos Necessários:* {points_needed}\n\n"
    text += "🎁 *Benefícios por Nível:*\n"
    text += "🥉 Bronze: Acesso básico\n"
    text += "🥈 Prata: 5% de desconto\n"
    text += "🥇 Ouro: 10% de desconto\n"
    
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_main_menu_keyboard(False))

async def admin_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dashboard de analytics para admins"""
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id not in ADMIN_IDS:
        await query.edit_message_text("Acesso negado.")
        return
    
    db = SessionLocal()
    since = datetime.utcnow() - timedelta(days=7)
    
    total_sales = db.query(Order).filter(Order.status == "paid", Order.created_at >= since).count()
    total_revenue = sum(o.total_price for o in db.query(Order).filter(Order.status == "paid", Order.created_at >= since).all())
    active_users = db.query(Order).filter(Order.created_at >= since).distinct(Order.user_id).count()
    
    db.close()
    
    text = f"📊 *Analytics Dashboard (7 dias)*\n\n"
    text += f"📈 *Vendas:* {total_sales}\n"
    text += f"💰 *Faturamento:* {format_currency(total_revenue)}\n"
    text += f"👥 *Usuários Ativos:* {active_users}\n"
    
    await query.edit_message_text(text, parse_mode="Markdown")

# ------------------- ADMIN -------------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id not in ADMIN_IDS:
        await query.edit_message_text("Acesso negado.")
        return
    await query.edit_message_text("Painel Administrativo:", reply_markup=get_admin_keyboard())

async def admin_add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if update.effective_user.id not in ADMIN_IDS:
        await query.edit_message_text("Acesso negado.")
        return ConversationHandler.END
    await query.edit_message_text("✏️ Envie o *nome* do produto:", parse_mode="Markdown")
    return ADD_PRODUCT_NAME

async def admin_add_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_name"] = update.message.text
    await update.message.reply_text("📝 Envie a *descrição* do produto:", parse_mode="Markdown")
    return ADD_PRODUCT_DESC

async def admin_add_product_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_desc"] = update.message.text
    await update.message.reply_text("💰 Envie o *preço* (ex: 49.90):", parse_mode="Markdown")
    return ADD_PRODUCT_PRICE

async def admin_add_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.replace(",", "."))
        context.user_data["new_price"] = price
        await update.message.reply_text("📎 Envie o arquivo do produto digital (ou /skip):")
        return ADD_PRODUCT_FILE
    except:
        await update.message.reply_text("Preço inválido. Tente novamente.")
        return ADD_PRODUCT_PRICE

async def admin_add_product_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    os.makedirs("digital_products", exist_ok=True)
    file_path = f"digital_products/{file.file_id}_{update.message.document.file_name}"
    await file.download_to_drive(file_path)
    context.user_data["new_file"] = file_path
    return await save_product(update, context)

async def admin_add_product_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_file"] = None
    return await save_product(update, context)

async def save_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    product = Product(
        name=context.user_data["new_name"],
        description=context.user_data["new_desc"],
        price=context.user_data["new_price"],
        digital_file=context.user_data.get("new_file")
    )
    db.add(product)
    db.commit()
    db.close()
    await update.message.reply_text("✅ Produto adicionado com sucesso!", reply_markup=get_main_menu_keyboard(True))
    return ConversationHandler.END

async def admin_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if update.effective_user.id not in ADMIN_IDS:
        await query.edit_message_text("Acesso negado.")
        return
    db = SessionLocal()
    orders = db.query(Order).filter(Order.status == "paid").order_by(Order.created_at.desc()).limit(20).all()
    db.close()
    if not orders:
        await query.edit_message_text("Nenhum pedido pago encontrado.")
    else:
        text = "📊 *Pedidos Pagos (últimos 20)*\n\n"
        for o in orders:
            text += f"#{o.id} - {o.created_at.strftime('%d/%m %H:%M')} - {format_currency(o.total_price)}\n"
        await query.edit_message_text(text, parse_mode="Markdown")

# ======================= WEBHOOK (FastAPI) =======================
app_webhook = FastAPI()

# Middleware para CORS
from fastapi.middleware.cors import CORSMiddleware
app_webhook.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def send_telegram_message(chat_id: int, text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})

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
    for item in order.items:
        if item.product.digital_file and os.path.exists(item.product.digital_file):
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
            async with httpx.AsyncClient() as client:
                with open(item.product.digital_file, "rb") as f:
                    files = {"document": f}
                    data = {"chat_id": user.telegram_id, "caption": f"✅ Seu produto: {item.product.name}"}
                    await client.post(url, data=data, files=files)
        else:
            await send_telegram_message(user.telegram_id, f"✅ Seu pedido #{order.id} foi confirmado! Em breve você receberá mais informações.")
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
        logging.info(f"✅ Webhook POST na raiz recebido: {payload}")
        
        # SillientPay envia 'orderId' e 'status'
        order_id = payload.get("orderId") or payload.get("order_id")
        status = payload.get("status")
        
        logging.info(f"Order ID: {order_id}, Status: {status}")
        
        # Se o pagamento foi confirmado
        if status == "paid" and order_id:
            db = SessionLocal()
            release_expired_reservations(db)
            # Tenta buscar pelo ID do pedido
            order = db.query(Order).filter(Order.id == int(order_id)).first()
            
            if order and order.status != "paid":
                order.status = "paid"
                order.payment_id = payload.get("id") or str(order_id)
                order.delivery_status = "processing"
                db.commit()
                background_tasks.add_task(deliver_digital_product, order.id)
                user = db.query(User).filter(User.id == order.user_id).first()
                if user:
                    await send_telegram_message(user.telegram_id, f"🎉 Pagamento confirmado! Pedido #{order.id} foi aprovado.")
                logging.info(f"✅ Pagamento confirmado para pedido #{order.id}")
            else:
                logging.info(f"Pedido #{order_id} já estava pago ou não encontrado")
            db.close()
        
        return {"status": "ok", "message": "Webhook processado com sucesso"}
    except Exception as e:
        logging.error(f"❌ Erro no webhook: {str(e)}")
        return {"status": "error", "message": str(e)}

@app_webhook.options("/")
async def root_options():
    return {}

@app_webhook.get("/health")
async def health():
    return {"status": "ok"}

@app_webhook.options("/health")
async def health_options():
    return {}

@app_webhook.get("/webhook/sillientpay")
async def sillientpay_webhook_get():
    """Rota GET para testes do webhook"""
    return {"status": "ok", "message": "Webhook SillientPay está ativo. Use POST para enviar eventos."}

@app_webhook.options("/webhook/sillientpay")
async def sillientpay_webhook_options():
    return {}

@app_webhook.post("/webhook/sillientpay")
async def sillientpay_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        payload = await request.json()
        logging.info(f"✅ Webhook SillientPay (POST) recebido: {payload}")
        
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
                    await send_telegram_message(user.telegram_id, f"🎉 Pagamento confirmado! Pedido #{order.id} foi aprovado.")
                logging.info(f"✅ Pagamento confirmado para pedido #{order.id}")
            db.close()
        return {"status": "ok", "message": "Webhook processado com sucesso"}
    except Exception as e:
        logging.error(f"❌ Erro no webhook: {str(e)}")
        return {"status": "error", "message": str(e)}

@app_webhook.put("/webhook/sillientpay")
async def sillientpay_webhook_put(request: Request, background_tasks: BackgroundTasks):
    """Rota PUT para compatibilidade"""
    try:
        payload = await request.json()
        logging.info(f"✅ Webhook SillientPay (PUT) recebido: {payload}")
        
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
                    await send_telegram_message(user.telegram_id, f"🎉 Pagamento confirmado! Pedido #{order.id} foi aprovado.")
                logging.info(f"✅ Pagamento confirmado para pedido #{order.id}")
            db.close()
        return {"status": "ok", "message": "Webhook processado com sucesso"}
    except Exception as e:
        logging.error(f"❌ Erro no webhook (PUT): {str(e)}")
        return {"status": "error", "message": str(e)}

@app_webhook.patch("/webhook/sillientpay")
async def sillientpay_webhook_patch(request: Request, background_tasks: BackgroundTasks):
    """Rota PATCH para compatibilidade"""
    try:
        payload = await request.json()
        logging.info(f"✅ Webhook SillientPay (PATCH) recebido: {payload}")
        
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
                    await send_telegram_message(user.telegram_id, f"🎉 Pagamento confirmado! Pedido #{order.id} foi aprovado.")
                logging.info(f"✅ Pagamento confirmado para pedido #{order.id}")
            db.close()
        return {"status": "ok", "message": "Webhook processado com sucesso"}
    except Exception as e:
        logging.error(f"❌ Erro no webhook (PATCH): {str(e)}")
        return {"status": "error", "message": str(e)}

def run_webhook():
    uvicorn.run(app_webhook, host=HOST, port=PORT, log_level="info")

# ======================= INICIALIZAÇÃO DE PRODUTOS DE TESTE =======================
def create_test_products():
    """Cria produtos de teste se a tabela estiver vazia"""
    # Criar tabelas se não existirem
    Base.metadata.create_all(engine)
    
    db = SessionLocal()
    
    # Verifica se já existem produtos
    existing_products = db.query(Product).count()
    if existing_products > 0:
        db.close()
        return
    
    # Produtos de teste
    test_products = [
        Product(
            name="CC FULL BASIC",
            description="Pacote básico com informações completas",
            price=49.99,
            is_available=True
        ),
        Product(
            name="CC FULL GOLD",
            description="Pacote gold com dados premium",
            price=59.99,
            is_available=True
        ),
        Product(
            name="CC FULL BUSINESS",
            description="Pacote business para empresas",
            price=44.99,
            is_available=True
        ),
        Product(
            name="CC FULL INFINITE",
            description="Pacote infinite com acesso ilimitado",
            price=54.99,
            is_available=True
        ),
        Product(
            name="CC FULL BLACK",
            description="Pacote black exclusivo VIP",
            price=64.99,
            is_available=True
        ),
        Product(
            name="DOC FAKE APP",
            description="Aplicativo para documentos personalizados",
            price=69.99,
            is_available=True
        ),
        Product(
            name="COMPROVANTE FK",
            description="Comprovantes personalizados diversos",
            price=15.99,
            is_available=True
        ),
    ]
    
    # Adiciona produtos ao banco
    for product in test_products:
        db.add(product)
    
    db.commit()
    db.close()
    logging.info("✅ 7 produtos de teste criados com sucesso!")

# ======================= MAIN =======================
def main():
    logging.basicConfig(level=logging.INFO)
    
    # Inicia o webhook em thread separada
    webhook_thread = threading.Thread(target=run_webhook, daemon=True)
    webhook_thread.start()
    logging.info("Servidor webhook iniciado na porta 8000 (thread background).")
    
    # Cria produtos de teste
    create_test_products()
    
    # Funcao para deletar webhook no post_init
    async def post_init(application):
        await application.bot.delete_webhook(drop_pending_updates=True)
        logging.info("Webhook deletado - pronto para polling")
    
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.bot_data["admin_ids"] = ADMIN_IDS
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("teste", teste))  # Comando de teste
    app.add_handler(CommandHandler("teste_pagamento", teste_pagamento))  # Teste de pagamento real
    app.add_handler(CommandHandler("pagar", pagar))  # Simular aprovação de pagamento
    app.add_handler(CallbackQueryHandler(catalog, pattern="^catalog$"))
    app.add_handler(CallbackQueryHandler(product_detail, pattern=r"^product_(\d+)$"))
    app.add_handler(CallbackQueryHandler(add_to_cart, pattern=r"^add_to_cart_"))
    app.add_handler(CallbackQueryHandler(view_cart, pattern="^view_cart$"))
    app.add_handler(CallbackQueryHandler(clear_cart, pattern="^clear_cart$"))
    app.add_handler(CallbackQueryHandler(checkout, pattern="^checkout$"))
    app.add_handler(CallbackQueryHandler(confirm_payment, pattern=r"^confirm_payment_"))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, receive_receipt))
    app.add_handler(CallbackQueryHandler(my_orders, pattern="^my_orders$"))
    app.add_handler(CallbackQueryHandler(support, pattern="^support$"))
    app.add_handler(CallbackQueryHandler(my_account, pattern="^my_account$"))
    app.add_handler(CallbackQueryHandler(main_menu, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(categories_menu, pattern="^categories$"))
    app.add_handler(CallbackQueryHandler(show_categories, pattern=r"^category_(\d+)$"))
    app.add_handler(CallbackQueryHandler(view_loyalty, pattern="^view_loyalty$"))
    app.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(admin_orders, pattern="^admin_orders$"))
    app.add_handler(CallbackQueryHandler(admin_analytics, pattern="^admin_analytics$"))

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_product_start, pattern="^admin_add_product$")],
        states={
            ADD_PRODUCT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_product_name)],
            ADD_PRODUCT_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_product_desc)],
            ADD_PRODUCT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_product_price)],
            ADD_PRODUCT_FILE: [MessageHandler(filters.Document.ALL, admin_add_product_file),
                               CommandHandler("skip", admin_add_product_skip)],
        },
        fallbacks=[]
    )
    app.add_handler(conv_handler)

    logging.info("Bot iniciado (polling) - webhook rodando em background...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()