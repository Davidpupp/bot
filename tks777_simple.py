#!/usr/bin/env python3
"""
TKS777 SIMPLE - Bot de Vendas Simples e Funcional
Versão limpa e direta sem complicações
"""

import os
import logging
import json
import random
import string
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# Configuração básica
BOT_TOKEN = "8633859972:AAHQfiWp7XGjGtFSGGzveznFsLex2XABQHw"
ADMIN_IDS = [8649452369]
DATABASE_URL = "sqlite:///tks777_simple.db"

# Logging simples
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Banco de dados simples
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String)
    is_admin = Column(Boolean, default=False)
    total_spent = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    name = Column(String, index=True)
    description = Column(Text)
    price = Column(Float)
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    order_number = Column(String, unique=True)
    total_price = Column(Float)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User")

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer, default=1)
    price = Column(Float)

# Criar tabelas
Base.metadata.create_all(bind=engine)

# Utilitários simples
def format_currency(value: float) -> str:
    return f"R$ {value:.2f}".replace(".", ",")

def generate_order_number() -> str:
    return f"TKS{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"

def get_main_menu(is_admin: bool = False):
    keyboard = [
        [InlineKeyboardButton("📚 Catálogo", callback_data="catalog")],
        [InlineKeyboardButton("🛒 Carrinho", callback_data="cart")],
        [InlineKeyboardButton("📋 Meus Pedidos", callback_data="orders")],
        [InlineKeyboardButton("🎧 Suporte", callback_data="support")]
    ]
    if is_admin:
        keyboard.append([InlineKeyboardButton("⚙️ Admin", callback_data="admin")])
    return InlineKeyboardMarkup(keyboard)

# Gerador de dados simples
class DataGenerator:
    @staticmethod
    def generate_cc_data(product_name: str) -> str:
        """Gera dados simples baseado no produto"""
        card_number = f"{random.randint(4000, 4999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"
        cvv = f"{random.randint(100, 999)}"
        expiry = f"{random.randint(1, 12):02d}/{random.randint(24, 30)}"
        holder = f"USER_{random.randint(10000, 99999)}"
        
        if "BASIC" in product_name:
            return f"CC BASIC:\nNúmero: {card_number}\nCVV: {cvv}\nValidade: {expiry}\nTitular: {holder}"
        elif "GOLD" in product_name:
            phone = f"({random.randint(100, 999)}) {random.randint(100, 999)}-{random.randint(1000, 9999)}"
            return f"CC GOLD:\nNúmero: {card_number}\nCVV: {cvv}\nValidade: {expiry}\nTitular: {holder}\nTelefone: {phone}"
        elif "BUSINESS" in product_name:
            ssn = f"{random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(1000, 9999)}"
            return f"CC BUSINESS:\nNúmero: {card_number}\nCVV: {cvv}\nValidade: {expiry}\nTitular: {holder}\nSSN: {ssn}"
        elif "INFINITE" in product_name:
            ssn = f"{random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(1000, 9999)}"
            pin = f"{random.randint(1000, 9999)}"
            return f"CC INFINITE:\nNúmero: {card_number}\nCVV: {cvv}\nValidade: {expiry}\nTitular: {holder}\nSSN: {ssn}\nPIN: {pin}"
        elif "BLACK" in product_name:
            ssn = f"{random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(1000, 9999)}"
            pin = f"{random.randint(1000, 9999)}"
            routing = f"{random.randint(100000000, 999999999)}"
            return f"CC BLACK:\nNúmero: {card_number}\nCVV: {cvv}\nValidade: {expiry}\nTitular: {holder}\nSSN: {ssn}\nPIN: {pin}\nRouting: {routing}"
        else:
            return f"DADOS GERADOS:\n{card_number}\n{cvv}\n{expiry}\n{holder}"

# Handlers principais
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler do start"""
    try:
        user = update.effective_user
        db = SessionLocal()
        
        # Criar usuário se não existir
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
            with open(banner_path, 'rb') as photo:
                await update.message.reply_photo(
                    photo=photo,
                    caption=f"👋 Olá {user.first_name}!\n\n🎉 Bem-vindo à TKS777!\n💳 Sistema de vendas automatizado.\n\n🚀 Use os botões abaixo para navegar.",
                    reply_markup=get_main_menu(is_admin)
                )
        else:
            await update.message.reply_text(
                f"👋 Olá {user.first_name}!\n\n🎉 Bem-vindo à TKS777!\n💳 Sistema de vendas automatizado.\n\n🚀 Use os botões abaixo para navegar.",
                reply_markup=get_main_menu(is_admin)
            )
    except Exception as e:
        logger.error(f"Erro no start: {e}")
        await update.message.reply_text("Erro ao processar mensagem.")

async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Catálogo de produtos"""
    try:
        query = update.callback_query
        await query.answer()
        
        db = SessionLocal()
        products = db.query(Product).filter(Product.is_available == True).all()
        db.close()
        
        if not products:
            await query.edit_message_text(" Nenhum produto disponível.")
            return
        
        text = "📚 *Catálogo TKS777*\n\n"
        for product in products:
            text += f"💳 *{product.name}*\n💰 {format_currency(product.price)}\n\n"
        
        keyboard = []
        for product in products:
            keyboard.append([InlineKeyboardButton(product.name, callback_data=f"product_{product.id}")])
        keyboard.append([InlineKeyboardButton("🏠 Menu Principal", callback_data="main")])
        
        try:
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            # Se não conseguir editar (mensagem com foto), envia nova mensagem
            await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Erro no catalog: {e}")

async def product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detalhes do produto"""
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
        
        text = f"💳 *{product.name}*\n\n📝 {product.description}\n\n💰 {format_currency(product.price)}"
        
        keyboard = [
            [InlineKeyboardButton("🛒 Adicionar ao Carrinho", callback_data=f"add_{product_id}")],
            [InlineKeyboardButton("⬅️ Voltar", callback_data="catalog")]
        ]
        
        try:
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Erro no product_detail: {e}")

async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Adicionar ao carrinho"""
    try:
        query = update.callback_query
        await query.answer()
        
        product_id = int(query.data.split("_")[1])
        
        cart = context.user_data.get("cart", {})
        cart[product_id] = cart.get(product_id, 0) + 1
        context.user_data["cart"] = cart
        
        await query.edit_message_text("✅ Produto adicionado ao carrinho!")
        
        db = SessionLocal()
        db_user = db.query(User).filter(User.telegram_id == query.from_user.id).first()
        is_admin = db_user.is_admin if db_user else False
        db.close()
        
        await query.message.reply_text("🚀 Use o menu para continuar.", reply_markup=get_main_menu(is_admin))
    except Exception as e:
        logger.error(f"Erro no add_to_cart: {e}")

async def cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ver carrinho"""
    try:
        query = update.callback_query
        await query.answer()
        
        cart = context.user_data.get("cart", {})
        if not cart:
            await query.edit_message_text("🛒 Seu carrinho está vazio.")
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
        
        keyboard = [
            [InlineKeyboardButton("💳 Finalizar Compra", callback_data="checkout")],
            [InlineKeyboardButton("🗑️ Limpar Carrinho", callback_data="clear")],
            [InlineKeyboardButton("🏠 Menu Principal", callback_data="main")]
        ]
        
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Erro no cart: {e}")

async def clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Limpar carrinho"""
    try:
        query = update.callback_query
        await query.answer()
        context.user_data["cart"] = {}
        
        db = SessionLocal()
        db_user = db.query(User).filter(User.telegram_id == query.from_user.id).first()
        is_admin = db_user.is_admin if db_user else False
        db.close()
        
        await query.edit_message_text("🗑️ Carrinho limpo!", reply_markup=get_main_menu(is_admin))
    except Exception as e:
        logger.error(f"Erro no clear_cart: {e}")

async def checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finalizar compra"""
    try:
        query = update.callback_query
        await query.answer()
        
        cart = context.user_data.get("cart", {})
        if not cart:
            await query.edit_message_text("🛒 Carrinho vazio.")
            return
        
        user_id = update.effective_user.id
        db = SessionLocal()
        db_user = db.query(User).filter(User.telegram_id == user_id).first()
        
        # Calcular total
        total = 0
        for pid, qty in cart.items():
            product = db.query(Product).filter(Product.id == pid).first()
            if product:
                total += product.price * qty
        
        # Criar pedido
        order = Order(
            user_id=db_user.id,
            order_number=generate_order_number(),
            total_price=total,
            status="pending"
        )
        db.add(order)
        db.commit()
        
        # Adicionar itens
        for pid, qty in cart.items():
            product = db.query(Product).filter(Product.id == pid).first()
            if product:
                item = OrderItem(order_id=order.id, product_id=pid, quantity=qty, price=product.price)
                db.add(item)
        
        db.commit()
        
        # Gerar dados automaticamente
        delivery_data = []
        for pid, qty in cart.items():
            product = db.query(Product).filter(Product.id == pid).first()
            if product:
                data = DataGenerator.generate_cc_data(product.name)
                delivery_data.append(data)
        
        # Atualizar usuário
        db_user.total_spent += total
        order.status = "completed"
        db.commit()
        
        # Enviar dados para o usuário
        message = f"✅ Pedido #{order.order_number} aprovado!\n\n"
        message += "🔐 Seus dados:\n\n"
        for i, data in enumerate(delivery_data, 1):
            message += f"💳 Produto {i}:\n{data}\n\n"
        message += "🎉 Obrigado por comprar na TKS777!"
        
        await query.message.reply_text(message)
        
        context.user_data["cart"] = {}
        await query.message.reply_text("✅ Pedido finalizado com sucesso!", reply_markup=get_main_menu(db_user.is_admin))
        
        db.close()
    except Exception as e:
        logger.error(f"Erro no checkout: {e}")

async def orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        
        text = "📋 *Seus Pedidos*\n\n"
        for order in orders:
            text += f"📦 Pedido #{order.order_number}\n"
            text += f"💰 Total: {format_currency(order.total_price)}\n"
            text += f"📊 Status: {'✅ Concluído' if order.status == 'completed' else '⏳ Pendente'}\n\n"
        
        await query.edit_message_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Erro no orders: {e}")

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Suporte"""
    try:
        query = update.callback_query
        await query.answer()
        
        db = SessionLocal()
        db_user = db.query(User).filter(User.telegram_id == query.from_user.id).first()
        is_admin = db_user.is_admin if db_user else False
        db.close()
        
        await query.edit_message_text(
            "🎧 *Suporte TKS777*\n\n"
            "💬 Telegram: @TKS777\n"
            "⚡ Resposta rápida garantida",
            parse_mode="Markdown",
            reply_markup=get_main_menu(is_admin)
        )
    except Exception as e:
        logger.error(f"Erro no support: {e}")

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        total_revenue = sum(o.total_price for o in db.query(Order).all())
        db.close()
        
        text = f"⚙️ *Painel Admin*\n\n"
        text += f"👥 Usuários: {total_users}\n"
        text += f"📦 Pedidos: {total_orders}\n"
        text += f"💰 Faturamento: {format_currency(total_revenue)}"
        
        await query.edit_message_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Erro no admin: {e}")

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu principal"""
    try:
        query = update.callback_query
        await query.answer()
        
        db = SessionLocal()
        db_user = db.query(User).filter(User.telegram_id == query.from_user.id).first()
        is_admin = db_user.is_admin if db_user else False
        db.close()
        
        await query.edit_message_text("🏠 Menu Principal:", reply_markup=get_main_menu(is_admin))
    except Exception as e:
        logger.error(f"Erro no main_menu: {e}")

# Criar produtos iniciais
def create_products():
    db = SessionLocal()
    
    if db.query(Product).count() == 0:
        products = [
            Product(name="CC FULL BASIC", description="Pacote básico com informações completas", price=49.99),
            Product(name="CC FULL GOLD", description="Pacote gold com dados premium", price=59.99),
            Product(name="CC FULL BUSINESS", description="Pacote business para empresas", price=44.99),
            Product(name="CC FULL INFINITE", description="Pacote infinite com acesso ilimitado", price=54.99),
            Product(name="CC FULL BLACK", description="Pacote black exclusivo VIP", price=64.99),
            Product(name="DOC FAKE APP", description="Aplicativo para documentos", price=69.99),
            Product(name="COMPROVANTE FK", description="Comprovantes personalizados", price=15.99),
        ]
        
        for product in products:
            db.add(product)
        
        db.commit()
        logger.info("7 produtos criados!")
    
    db.close()

# Função principal
def main():
    logger.info("Iniciando TKS777 SIMPLE...")
    
    # Criar produtos
    create_products()
    
    # Configurar bot
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(main_menu, pattern="^main$"))
    app.add_handler(CallbackQueryHandler(catalog, pattern="^catalog$"))
    app.add_handler(CallbackQueryHandler(product_detail, pattern=r"^product_(\d+)$"))
    app.add_handler(CallbackQueryHandler(add_to_cart, pattern=r"^add_(\d+)$"))
    app.add_handler(CallbackQueryHandler(cart, pattern="^cart$"))
    app.add_handler(CallbackQueryHandler(clear_cart, pattern="^clear$"))
    app.add_handler(CallbackQueryHandler(checkout, pattern="^checkout$"))
    app.add_handler(CallbackQueryHandler(orders, pattern="^orders$"))
    app.add_handler(CallbackQueryHandler(support, pattern="^support$"))
    app.add_handler(CallbackQueryHandler(admin, pattern="^admin$"))
    
    logger.info("TKS777 SIMPLE iniciado!")
    print(" TKS777 SIMPLE - Bot Online! ")
    
    try:
        app.run_polling()
    except KeyboardInterrupt:
        logger.info("Bot encerrado.")
    except Exception as e:
        logger.error(f"Erro: {e}")

if __name__ == "__main__":
    main()
