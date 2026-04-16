#!/usr/bin/env python3
"""
Bot de Vendas TKS777 - Versão Final Corrigida
Integração com SillientPay - Sem Bugs
"""

import os
import logging
import base64
import threading
import signal
import sys
from io import BytesIO
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    filters, ConversationHandler, ContextTypes
)
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
import requests
from fastapi import FastAPI, Request, BackgroundTasks
import uvicorn
import httpx

# Configuração
BOT_TOKEN = "8783109233:AAGFaneNYd4m377qdBO192ST2uWG5y3AxFA"
ADMIN_IDS = [8649452369]
BASE_URL = "https://seu-app-publico.app"
DATABASE_URL = "sqlite:///sales_bot.db"
PORT = 8002
HOST = "0.0.0.0"

# Chaves de pagamento (opcional)
SILLIENTPAY_API_KEY = os.getenv("SILLIENTPAY_API_KEY", "")

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Banco de dados
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

# Gateway de pagamento
class SillientPayGateway:
    @staticmethod
    def create_payment(amount: float, order_id: int, user_email: str = None):
        if not SILLIENTPAY_API_KEY:
            return {"error": "Gateway não configurado"}
        
        url = "https://api.sillientpay.com/v1/payments"
        headers = {
            "Authorization": f"Bearer {SILLIENTPAY_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "amount": int(amount * 100),
            "currency": "BRL",
            "orderId": str(order_id),
            "paymentMethod": "pix",
            "webhookUrl": f"{BASE_URL}/webhook/sillientpay",
            "customer": {
                "email": user_email or "cliente@email.com"
            }
        }

        try:
            logger.info(f"Criando pagamento: R$ {amount:.2f} - Pedido #{order_id}")
            response = httpx.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Erro no pagamento: {e}")
            return {"error": str(e)}

# Utilidades
def format_currency(value: float) -> str:
    return f"R$ {value:.2f}".replace(".", ",")

def get_main_menu_keyboard(is_admin: bool = False):
    keyboard = [
        [InlineKeyboardButton(" Catálogo", callback_data="catalog")],
        [InlineKeyboardButton(" Carrinho", callback_data="view_cart")],
        [InlineKeyboardButton(" Meus Pedidos", callback_data="my_orders")],
        [InlineKeyboardButton(" Suporte", callback_data="support")],
        [InlineKeyboardButton(" Minha Conta", callback_data="my_account")]
    ]
    if is_admin:
        keyboard.append([InlineKeyboardButton(" Admin", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def get_catalog_keyboard(products):
    keyboard = [[InlineKeyboardButton(p.name, callback_data=f"product_{p.id}")] for p in products]
    keyboard.append([InlineKeyboardButton(" Menu Principal", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

def get_product_keyboard(product_id):
    keyboard = [
        [InlineKeyboardButton(" Adicionar ao Carrinho", callback_data=f"add_to_cart_{product_id}")],
        [InlineKeyboardButton(" Voltar ao Catálogo", callback_data="catalog")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_cart_keyboard():
    keyboard = [
        [InlineKeyboardButton(" Atualizar", callback_data="view_cart")],
        [InlineKeyboardButton(" Finalizar Compra", callback_data="checkout")],
        [InlineKeyboardButton(" Limpar Carrinho", callback_data="clear_cart")],
        [InlineKeyboardButton(" Menu Principal", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        db = SessionLocal()
        
        # Criar ou buscar usuário
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
        
        # Enviar banner se existir
        banner_path = "banners/welcome_banner.jpg"
        if os.path.exists(banner_path):
            try:
                with open(banner_path, 'rb') as photo:
                    await update.message.reply_photo(
                        photo=photo,
                        caption=f" Olá {user.first_name}!\n\nBem-vindo à TKS777!\nUse os botões abaixo para navegar.",
                        reply_markup=get_main_menu_keyboard(is_admin)
                    )
            except Exception as e:
                logger.error(f"Erro ao enviar banner: {e}")
                await update.message.reply_text(
                    f" Olá {user.first_name}!\n\nBem-vindo à TKS777!\nUse os botões abaixo para navegar.",
                    reply_markup=get_main_menu_keyboard(is_admin)
                )
        else:
            await update.message.reply_text(
                f" Olá {user.first_name}!\n\nBem-vindo à TKS777!\nUse os botões abaixo para navegar.",
                reply_markup=get_main_menu_keyboard(is_admin)
            )
    except Exception as e:
        logger.error(f"Erro no start: {e}")
        await update.message.reply_text("Erro ao processar mensagem. Tente novamente.")

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        
        db = SessionLocal()
        db_user = db.query(User).filter(User.telegram_id == query.from_user.id).first()
        is_admin = db_user.is_admin if db_user else False
        db.close()
        
        await query.edit_message_text("Menu Principal:", reply_markup=get_main_menu_keyboard(is_admin))
    except Exception as e:
        logger.error(f"Erro no main_menu: {e}")

async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        
        db = SessionLocal()
        products = db.query(Product).filter(Product.is_available == True).all()
        db.close()
        
        if not products:
            await query.edit_message_text(" Nenhum produto disponível no momento.")
            return
        
        text = " *Catálogo TKS777*\n\n"
        for p in products:
            text += f"*{p.name}*\n {format_currency(p.price)}\n\n"
        
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_catalog_keyboard(products))
    except Exception as e:
        logger.error(f"Erro no catalog: {e}")

async def product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        
        product_id = int(query.data.split("_")[1])
        
        db = SessionLocal()
        product = db.query(Product).filter(Product.id == product_id).first()
        db.close()
        
        if not product:
            await query.edit_message_text("Produto não encontrado.")
            return
        
        text = f"*{product.name}*\n\n{product.description}\n\n {format_currency(product.price)}"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_product_keyboard(product.id))
    except Exception as e:
        logger.error(f"Erro no product_detail: {e}")

async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        
        product_id = int(query.data.split("_")[3])
        
        cart = context.user_data.get("cart", {})
        cart[product_id] = cart.get(product_id, 0) + 1
        context.user_data["cart"] = cart
        
        await query.edit_message_text(" Produto adicionado ao carrinho!")
        
        db = SessionLocal()
        db_user = db.query(User).filter(User.telegram_id == query.from_user.id).first()
        is_admin = db_user.is_admin if db_user else False
        db.close()
        
        await query.message.reply_text("Use o menu para continuar ou finalizar.", reply_markup=get_main_menu_keyboard(is_admin))
    except Exception as e:
        logger.error(f"Erro no add_to_cart: {e}")

async def view_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                text += f"{product.name} x{qty} = {format_currency(subtotal)}\n"
        
        db.close()
        text += f"\n*Total: {format_currency(total)}*"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_cart_keyboard())
    except Exception as e:
        logger.error(f"Erro no view_cart: {e}")

async def clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        context.user_data["cart"] = {}
        await query.edit_message_text(" Carrinho limpo!", reply_markup=get_main_menu_keyboard(False))
    except Exception as e:
        logger.error(f"Erro no clear_cart: {e}")

async def checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        order = Order(user_id=db_user.id, total_price=total, status="pending")
        db.add(order)
        db.commit()
        
        # Adicionar itens
        for pid, qty in cart.items():
            p = db.query(Product).filter(Product.id == pid).first()
            if p:
                item = OrderItem(order_id=order.id, product_id=pid, quantity=qty, price=p.price)
                db.add(item)
        
        db.commit()
        
        # Criar pagamento
        payment_data = SillientPayGateway.create_payment(total, order.id, db_user.email)
        
        if "error" in payment_data:
            await query.message.reply_text(f" Erro ao gerar pagamento: {payment_data['error']}")
        else:
            await query.message.reply_text(
                f" Pedido #{order.id} gerado!\nValor: {format_currency(total)}\n\nAguardando confirmação de pagamento."
            )
        
        context.user_data["cart"] = {}
        await query.message.reply_text(" Pedido finalizado!", reply_markup=get_main_menu_keyboard(db_user.is_admin))
        db.close()
    except Exception as e:
        logger.error(f"Erro no checkout: {e}")

async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            text += f"Pedido #{o.id} - {o.created_at.strftime('%d/%m/%Y %H:%M')}\n"
            text += f"Total: {format_currency(o.total_price)} - Status: {' Pago' if o.status == 'paid' else ' Pendente'}\n\n"
        
        await query.edit_message_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Erro no my_orders: {e}")

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            " *Suporte TKS777*\n\nTelegram: @TKS777\nWhatsApp: Consulte o admin",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard(False)
        )
    except Exception as e:
        logger.error(f"Erro no support: {e}")

async def my_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        db = SessionLocal()
        db_user = db.query(User).filter(User.telegram_id == user_id).first()
        
        if db_user:
            text = f" *Minha Conta*\n\nNome: {db_user.first_name}\nUsername: @{db_user.username or 'não definido'}\nE-mail: {db_user.email or 'não informado'}"
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_main_menu_keyboard(db_user.is_admin))
        
        db.close()
    except Exception as e:
        logger.error(f"Erro no my_account: {e}")

# Admin handlers
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        
        if query.from_user.id not in ADMIN_IDS:
            await query.edit_message_text("Acesso negado.")
            return
        
        await query.edit_message_text("Painel Administrativo TKS777:")
    except Exception as e:
        logger.error(f"Erro no admin_panel: {e}")

# Webhook
app_webhook = FastAPI()

@app_webhook.get("/")
async def root():
    return {"status": "Webhook TKS777 ativo"}

@app_webhook.post("/webhook/sillientpay")
async def sillientpay_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        payload = await request.json()
        logger.info(f"Webhook recebido: {payload}")
        
        if payload.get("status") == "paid":
            order_id = payload.get("orderId")
            if order_id:
                db = SessionLocal()
                order = db.query(Order).filter(Order.id == int(order_id)).first()
                
                if order and order.status != "paid":
                    order.status = "paid"
                    db.commit()
                    logger.info(f"Pedido #{order_id} pago com sucesso")
                
                db.close()
        
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Erro no webhook: {e}")
        return {"status": "error", "message": str(e)}

def run_webhook():
    uvicorn.run(app_webhook, host=HOST, port=PORT, log_level="warning")

# Criar produtos
def create_products():
    db = SessionLocal()
    
    if db.query(Product).count() == 0:
        products = [
            Product(name="CC FULL BASIC", description="Pacote básico com informações completas", price=49.99),
            Product(name="CC FULL GOLD", description="Pacote gold com dados premium", price=59.99),
            Product(name="CC FULL BUSINESS", description="Pacote business para empresas", price=44.99),
            Product(name="CC FULL INFINITE", description="Pacote infinite com acesso ilimitado", price=54.99),
            Product(name="CC FULL BLACK", description="Pacote black exclusivo VIP", price=64.99),
            Product(name="DOC FAKE APP", description="Aplicativo para documentos personalizados", price=69.99),
            Product(name="COMPROVANTE FK", description="Comprovantes personalizados diversos", price=15.99),
        ]
        
        for product in products:
            db.add(product)
        
        db.commit()
        logger.info("7 produtos criados com sucesso!")
    
    db.close()

# Main
def main():
    logger.info("Iniciando Bot TKS777...")
    
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
    app.add_handler(CallbackQueryHandler(main_menu, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(catalog, pattern="^catalog$"))
    app.add_handler(CallbackQueryHandler(product_detail, pattern=r"^product_(\d+)$"))
    app.add_handler(CallbackQueryHandler(add_to_cart, pattern=r"^add_to_cart_(\d+)$"))
    app.add_handler(CallbackQueryHandler(view_cart, pattern="^view_cart$"))
    app.add_handler(CallbackQueryHandler(clear_cart, pattern="^clear_cart$"))
    app.add_handler(CallbackQueryHandler(checkout, pattern="^checkout$"))
    app.add_handler(CallbackQueryHandler(my_orders, pattern="^my_orders$"))
    app.add_handler(CallbackQueryHandler(support, pattern="^support$"))
    app.add_handler(CallbackQueryHandler(my_account, pattern="^my_account$"))
    app.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_panel$"))
    
    logger.info("Bot TKS777 iniciado com sucesso!")
    print(" TKS777 Bot Online! ")
    
    try:
        app.run_polling()
    except KeyboardInterrupt:
        logger.info("Bot encerrado pelo usuário")
    except Exception as e:
        logger.error(f"Erro fatal: {e}")

if __name__ == "__main__":
    main()
