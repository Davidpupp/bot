#!/usr/bin/env python3
"""
Bot de Vendas para Telegram - Integração com SillientPay
Versão: 2.1 - Corrigida
Configuração via variáveis de ambiente para deploy em serviços gratuitos.
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

# ======================= CONFIGURAÇÃO / AMBIENTE =======================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8783109233:AAGFaneNYd4m377qdBO192ST2uWG5y3AxFA")
ADMIN_IDS = [8649452369]
BASE_URL = os.getenv("BASE_URL", "https://seu-app-publico.app").rstrip("/")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", BASE_URL)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///sales_bot.db")
PORT = int(os.getenv("PORT", "8002"))
HOST = os.getenv("HOST", "0.0.0.0")

# Chaves de pagamento
MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "")
MP_WEBHOOK_SECRET = os.getenv("MP_WEBHOOK_SECRET", "")
SILLIENTPAY_API_KEY = os.getenv("SILLIENTPAY_API_KEY", "")
SILLIENTPAY_WEBHOOK_SECRET = os.getenv("SILLIENTPAY_WEBHOOK_SECRET", "")

# ======================= VERIFICAÇÃO =======================
if not BOT_TOKEN or BOT_TOKEN == "SEU_TOKEN_AQUI":
    print("ERRO: Você precisa colocar o token do bot na variável BOT_TOKEN")
    sys.exit(1)

# ======================= BANCO DE DADOS =======================
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

# ======================= GATEWAY DE PAGAMENTO =======================
class MercadoPagoGateway:
    @staticmethod
    def create_payment(amount: float, order_id: int, user_email: str = None):
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
    def create_payment(amount: float, order_id: int, user_email: str = None):
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
            "webhookUrl": f"{WEBHOOK_URL}/webhook/sillientpay",
            "customer": {
                "email": user_email or "cliente@email.com"
            }
        }

        try:
            logging.info(f" Criando pagamento SillientPay: R$ {amount:.2f} - Pedido #{order_id}")
            response = httpx.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()

            payment_data = response.json()
            logging.info(f" Pagamento criado: {payment_data.get('id', 'N/A')}")

            return payment_data

        except httpx.HTTPStatusError as e:
            logging.error(f" Erro HTTP SillientPay: {e.response.status_code} - {e.response.text}")
            return {"error": f"Erro HTTP: {e.response.status_code}", "details": e.response.text}

        except Exception as e:
            logging.error(f" Erro geral SillientPay: {e}")
            return {"error": str(e)}

def create_payment(amount: float, order_id: int, user_email: str = None):
    if SILLIENTPAY_API_KEY:
        return SillientPayGateway.create_payment(amount, order_id, user_email)
    elif MP_ACCESS_TOKEN:
        return MercadoPagoGateway.create_payment(amount, order_id, user_email)
    else:
        return {"error": "Nenhum gateway configurado"}

# ======================= UTILIDADES =======================
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

def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton(" Adicionar Produto", callback_data="admin_add_product")],
        [InlineKeyboardButton(" Ver Pedidos Pagos", callback_data="admin_orders")],
        [InlineKeyboardButton(" Menu Principal", callback_data="main_menu")]
    ]
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
                    caption=f" Olá {user.first_name}!\n\nBem-vindo à nossa loja.\nUse os botões abaixo para navegar.",
                    reply_markup=get_main_menu_keyboard(is_admin)
                )
        except Exception as e:
            logging.error(f"Erro ao enviar banner: {e}")
            await update.message.reply_text(
                f" Olá {user.first_name}!\n\nBem-vindo à nossa loja.\nUse os botões abaixo para navegar.",
                reply_markup=get_main_menu_keyboard(is_admin)
            )
    else:
        await update.message.reply_text(
            f" Olá {user.first_name}!\n\nBem-vindo à nossa loja.\nUse os botões abaixo para navegar.",
            reply_markup=get_main_menu_keyboard(is_admin)
        )

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    db = SessionLocal()
    db_user = db.query(User).filter(User.telegram_id == user_id).first()
    is_admin = db_user.is_admin if db_user else False
    db.close()
    await query.edit_message_text("Menu Principal:", reply_markup=get_main_menu_keyboard(is_admin))

async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db = SessionLocal()
    products = db.query(Product).filter(Product.is_available == True).all()
    db.close()
    if not products:
        await query.edit_message_text(" Nenhum produto disponível no momento.")
        return
    text = " *Catálogo de Produtos*\n\n" + "\n".join(f"*{p.name}*\n {format_currency(p.price)}\n" for p in products)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_catalog_keyboard(products))

async def product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        product_id = int(query.data.split("_")[1])
    except:
        return
    db = SessionLocal()
    product = db.query(Product).filter(Product.id == product_id).first()
    db.close()
    if not product:
        await query.edit_message_text("Produto não encontrado.")
        return
    text = f"*{product.name}*\n\n{product.description}\n\n {format_currency(product.price)}"
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_product_keyboard(product.id))

async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        product_id = int(query.data.split("_")[3])
    except:
        await query.edit_message_text("Erro ao adicionar produto.")
        return
    cart = context.user_data.get("cart", {})
    cart[product_id] = cart.get(product_id, 0) + 1
    context.user_data["cart"] = cart
    await query.edit_message_text(" Produto adicionado ao carrinho!")
    user_id = query.from_user.id
    db = SessionLocal()
    db_user = db.query(User).filter(User.telegram_id == user_id).first()
    is_admin = db_user.is_admin if db_user else False
    db.close()
    await query.message.reply_text("Use o menu para continuar ou finalizar.", reply_markup=get_main_menu_keyboard(is_admin))

async def view_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["cart"] = {}
    await query.edit_message_text(" Carrinho limpo!", reply_markup=get_main_menu_keyboard(False))

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
    total = 0
    for pid, qty in cart.items():
        p = db.query(Product).filter(Product.id == pid).first()
        if p:
            total += p.price * qty
    order = Order(user_id=db_user.id, total_price=total, status="pending")
    db.add(order)
    db.commit()
    for pid, qty in cart.items():
        p = db.query(Product).filter(Product.id == pid).first()
        if p:
            item = OrderItem(order_id=order.id, product_id=pid, quantity=qty, price=p.price)
            db.add(item)
    db.commit()
    payment_data = create_payment(amount=total, order_id=order.id, user_email=db_user.email)
    if "error" in payment_data:
        await query.message.reply_text(f" Erro ao gerar pagamento: {payment_data['error']}")
        db.close()
        return
    payment_id = payment_data.get("id")
    if payment_id:
        order.payment_id = payment_id
        db.commit()
    db.close()
    qr_code = payment_data.get("point_of_interaction", {}).get("transaction_data", {}).get("qr_code_base64")
    if qr_code:
        qr_bytes = base64.b64decode(qr_code)
        await query.message.reply_photo(photo=BytesIO(qr_bytes), caption=f" PIX - Pedido #{order.id}\nValor: {format_currency(total)}\n\nApós o pagamento, o produto será enviado.")
    else:
        await query.message.reply_text(f" Pedido #{order.id} gerado!\nValor: {format_currency(total)}\n\nAguardando confirmação de pagamento.")
    context.user_data["cart"] = {}
    await query.message.reply_text(" Pedido finalizado! Em breve você receberá a confirmação.", reply_markup=get_main_menu_keyboard(db_user.is_admin))

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
    text = " *Seus Pedidos*\n\n"
    for o in orders:
        text += f"Pedido #{o.id} - {o.created_at.strftime('%d/%m/%Y %H:%M')}\n"
        text += f"Total: {format_currency(o.total_price)} - Status: {' Pago' if o.status == 'paid' else ' Pendente'}\n\n"
    await query.edit_message_text(text, parse_mode="Markdown")

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        " *Suporte*\n\nE-mail: suporte@seudominio.com\nWhatsApp: (11) 99999-9999",
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
        text = f" *Minha Conta*\n\nNome: {db_user.first_name}\nUsername: @{db_user.username or 'não definido'}\nE-mail: {db_user.email or 'não informado'}"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_main_menu_keyboard(db_user.is_admin))
    db.close()

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
    await query.edit_message_text(" Envie o *nome* do produto:", parse_mode="Markdown")
    return ADD_PRODUCT_NAME

async def admin_add_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_name"] = update.message.text
    await update.message.reply_text(" Envie a *descrição* do produto:", parse_mode="Markdown")
    return ADD_PRODUCT_DESC

async def admin_add_product_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_desc"] = update.message.text
    await update.message.reply_text(" Envie o *preço* (ex: 49.90):", parse_mode="Markdown")
    return ADD_PRODUCT_PRICE

async def admin_add_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.replace(",", "."))
        context.user_data["new_price"] = price
        await update.message.reply_text(" Envie o arquivo do produto digital (ou /skip):")
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
    await update.message.reply_text(" Produto adicionado com sucesso!", reply_markup=get_main_menu_keyboard(True))
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
        text = " *Pedidos Pagos (últimos 20)*\n\n"
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
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
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
                    data = {"chat_id": user.telegram_id, "caption": f" Seu produto: {item.product.name}"}
                    await client.post(url, data=data, files=files)
        else:
            await send_telegram_message(user.telegram_id, f" Seu pedido #{order.id} foi confirmado! Em breve você receberá mais informações.")
    db.close()

@app_webhook.get("/")
async def root():
    return {"status": "Webhook ativo", "message": "Bot de vendas TKS777"}

@app_webhook.post("/")
async def root_post(request: Request, background_tasks: BackgroundTasks):
    try:
        payload = await request.json()
        logging.info(f" Webhook POST recebido: {payload}")
        
        order_id = payload.get("orderId") or payload.get("order_id")
        status = payload.get("status")
        
        if status == "paid" and order_id:
            db = SessionLocal()
            order = db.query(Order).filter(Order.id == int(order_id)).first()
            
            if order and order.status != "paid":
                order.status = "paid"
                order.payment_id = payload.get("id") or str(order_id)
                db.commit()
                background_tasks.add_task(deliver_digital_product, order.id)
                await send_telegram_message(order.user.telegram_id, f" Pagamento confirmado! Pedido #{order.id} foi aprovado.")
                logging.info(f" Pagamento confirmado para pedido #{order.id}")
            else:
                logging.info(f"Pedido #{order_id} já estava pago ou não encontrado")
            db.close()
        
        return {"status": "ok", "message": "Webhook processado com sucesso"}
    except Exception as e:
        logging.error(f" Erro no webhook: {str(e)}")
        return {"status": "error", "message": str(e)}

@app_webhook.get("/health")
async def health():
    return {"status": "ok"}

def run_webhook():
    uvicorn.run(app_webhook, host=HOST, port=PORT, log_level="info")

# ======================= INICIALIZAÇÃO DE PRODUTOS =======================
def create_test_products():
    """Cria produtos de teste se a tabela estiver vazia"""
    db = SessionLocal()
    
    # Verifica se já existem produtos
    existing_products = db.query(Product).count()
    if existing_products > 0:
        db.close()
        return
    
    # Produtos atualizados
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
    logging.info(" 7 produtos criados com sucesso!")

# ======================= CONTROLE DE SINALIZAÇÃO =======================
shutdown_flag = False

def signal_handler(signum, frame):
    global shutdown_flag
    print("\nRecebido sinal para encerrar o bot...")
    shutdown_flag = True
    sys.exit(0)

# ======================= MAIN =======================
def main():
    global shutdown_flag
    
    # Configurar handlers de sinal
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print(" Iniciando Bot TKS777...")
    
    # Inicia o webhook em thread separada
    webhook_thread = threading.Thread(target=run_webhook, daemon=True)
    webhook_thread.start()
    logging.info(" Servidor webhook iniciado na porta %s", PORT)
    
    # Cria produtos de teste
    create_test_products()
    
    # Configuração do bot
    app = Application.builder().token(BOT_TOKEN).build()
    app.bot_data["admin_ids"] = ADMIN_IDS

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
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
    app.add_handler(CallbackQueryHandler(admin_orders, pattern="^admin_orders$"))

    # Conversation handler para admin
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

    logging.info(" Bot TKS777 iniciado com sucesso!")
    print(" Bot TKS777 online e funcionando! ")
    
    try:
        app.run_polling()
    except KeyboardInterrupt:
        print("\nBot encerrado pelo usuário.")
    except Exception as e:
        logging.error(f"Erro ao executar bot: {e}")
        print(f"Erro: {e}")

if __name__ == "__main__":
    main()
