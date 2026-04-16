#!/usr/bin/env python3
"""
Funcionalidades Avançadas para o Bot de Vendas
- Sistema de Analytics
- Códigos de Desconto
- Categorias de Produtos
- Sistema de Fidelidade
- Campanhas de Marketing
"""

import os
import logging
import base64
import threading
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
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
import httpx

# Importar configurações do bot principal
import os
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

# Configurações
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///sales_bot.db")
ADMIN_IDS = [8649452369]

# Criar sessão local para este módulo
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Funções utilitárias básicas
def format_currency(value: float) -> str:
    return f"R$ {value:.2f}".replace(".", ",")

# ======================= MODELOS AVANÇADOS =======================
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

# ======================= FUNÇÕES AVANÇADAS =======================

def track_analytics(event_type: str, user_id: int = None, product_id: int = None, order_id: int = None, value: float = None, extra_data: str = None):
    """Registra eventos de analytics"""
    db = SessionLocal()
    analytics = Analytics(
        event_type=event_type,
        user_id=user_id,
        product_id=product_id,
        order_id=order_id,
        value=value,
        extra_data=extra_data
    )
    db.add(analytics)
    db.commit()
    db.close()

def generate_discount_code(discount_type: str = "percentage", discount_value: float = 10.0, usage_limit: int = None, expires_days: int = 30) -> str:
    """Gera código de desconto aleatório"""
    code = f"DESC{random.randint(1000, 9999)}"
    db = SessionLocal()
    discount = DiscountCode(
        code=code,
        discount_type=discount_type,
        discount_value=discount_value,
        usage_limit=usage_limit,
        expires_at=datetime.utcnow() + timedelta(days=expires_days) if expires_days else None
    )
    db.add(discount)
    db.commit()
    db.close()
    return code

def validate_discount_code(code: str, total_amount: float) -> dict:
    """Valida e aplica código de desconto"""
    db = SessionLocal()
    discount = db.query(DiscountCode).filter(
        DiscountCode.code == code,
        DiscountCode.is_active == True
    ).first()
    
    if not discount:
        db.close()
        return {"valid": False, "message": "Código inválido"}
    
    # Verificar expiração
    if discount.expires_at and discount.expires_at < datetime.utcnow():
        db.close()
        return {"valid": False, "message": "Código expirado"}
    
    # Verificar limite de uso
    if discount.usage_limit and discount.usage_count >= discount.usage_limit:
        db.close()
        return {"valid": False, "message": "Limite de uso atingido"}
    
    # Verificar compra mínima
    if total_amount < discount.min_purchase:
        db.close()
        return {"valid": False, "message": f"Compra mínima de {format_currency(discount.min_purchase)}"}
    
    # Calcular desconto
    if discount.discount_type == "percentage":
        discount_amount = total_amount * (discount.discount_value / 100)
        if discount.max_discount and discount_amount > discount.max_discount:
            discount_amount = discount.max_discount
    else:  # fixed
        discount_amount = discount.discount_value
    
    # Incrementar uso
    discount.usage_count += 1
    db.commit()
    db.close()
    
    return {
        "valid": True,
        "discount_amount": discount_amount,
        "final_amount": total_amount - discount_amount,
        "percentage": discount.discount_value if discount.discount_type == "percentage" else None
    }

def update_loyalty_points(user_id: int, points_to_add: int = 0, points_to_spend: int = 0):
    """Atualiza pontos de fidelidade"""
    db = SessionLocal()
    loyalty = db.query(LoyaltyPoints).filter(LoyaltyPoints.user_id == user_id).first()
    
    if not loyalty:
        loyalty = LoyaltyPoints(
            user_id=user_id,
            points=points_to_add,
            points_earned=points_to_add,
            points_spent=points_to_spend
        )
        db.add(loyalty)
    else:
        loyalty.points += points_to_add - points_to_spend
        loyalty.points_earned += points_to_add
        loyalty.points_spent += points_to_spend
        
        # Atualizar nível
        total_points = loyalty.points_earned
        if total_points >= 1000:
            loyalty.level = "Ouro"
        elif total_points >= 500:
            loyalty.level = "Prata"
        else:
            loyalty.level = "Bronze"
        
        loyalty.updated_at = datetime.utcnow()
    
    db.commit()
    db.close()

def get_analytics_dashboard(days: int = 7) -> dict:
    """Gera dashboard de analytics"""
    db = SessionLocal()
    since = datetime.utcnow() - timedelta(days=days)
    
    # Vendas totais
    total_sales = db.query(Order).filter(Order.status == "paid", Order.created_at >= since).count()
    total_revenue = db.query(Order).filter(Order.status == "paid", Order.created_at >= since).with_entities(Order.total_price).all()
    total_revenue = sum(order.total_price for order in total_revenue)
    
    # Produtos mais vendidos
    top_products = db.query(OrderItem, Product.name, Product.price)\
        .join(Order, OrderItem.order_id == Order.id)\
        .join(Product, OrderItem.product_id == Product.id)\
        .filter(Order.status == "paid", Order.created_at >= since)\
        .group_by(Product.id)\
        .order_by(db.func.count(OrderItem.id).desc())\
        .limit(5)\
        .all()
    
    # Usuários ativos
    active_users = db.query(Order).filter(Order.created_at >= since).distinct(Order.user_id).count()
    
    db.close()
    
    return {
        "total_sales": total_sales,
        "total_revenue": total_revenue,
        "top_products": [{"name": p[1], "sales": len(db.query(OrderItem).filter(OrderItem.product_id == p[0]).all())} for p in top_products],
        "active_users": active_users,
        "period_days": days
    }

def get_categories_keyboard():
    """Teclado com categorias"""
    db = SessionLocal()
    categories = db.query(Category).filter(Category.is_active == True).all()
    db.close()
    
    if not categories:
        return None
    
    keyboard = [[InlineKeyboardButton(f"{cat.icon or '📂'} {cat.name}", callback_data=f"category_{cat.id}")] for cat in categories]
    keyboard.append([InlineKeyboardButton("🔙 Menu Principal", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

def get_user_loyalty_info(user_id: int) -> dict:
    """Obtém informações de fidelidade do usuário"""
    db = SessionLocal()
    loyalty = db.query(LoyaltyPoints).filter(LoyaltyPoints.user_id == user_id).first()
    db.close()
    
    if not loyalty:
        return {"points": 0, "level": "Bronze", "next_level": "Prata", "points_needed": 500}
    
    next_level_points = {
        "Bronze": {"next": "Prata", "needed": 500},
        "Prata": {"next": "Ouro", "needed": 1000},
        "Ouro": {"next": "Ouro", "needed": 0}
    }
    
    current_level = loyalty.level
    next_info = next_level_points.get(current_level, {"next": "Ouro", "needed": 0})
    
    return {
        "points": loyalty.points,
        "level": current_level,
        "next_level": next_info["next"],
        "points_needed": max(0, next_info["needed"] - loyalty.points_earned)
    }

# ======================= HANDLERS AVANÇADOS =======================

async def apply_discount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Aplica código de desconto no carrinho"""
    query = update.callback_query
    await query.answer()
    
    # Pedir código de desconto
    await query.edit_message_text(
        "🎟 *Aplicar Cupom de Desconto*\n\n"
        "Digite o código do cupom:\n"
        "Ex: DESC1234\n\n"
        "Ou cancele com /cancel",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancelar", callback_data="cancel_discount")]
        ])
    )
    
    # Aguardar resposta do usuário
    context.user_data["awaiting_discount"] = True

async def cancel_discount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela aplicação de cupom"""
    query = update.callback_query
    await query.answer()
    
    if "discount_code" in context.user_data:
        del context.user_data["discount_code"]
    if "discount_amount" in context.user_data:
        del context.user_data["discount_amount"]
    
    context.user_data["awaiting_discount"] = False
    
    await query.edit_message_text("❌ Cupom cancelado")

async def admin_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dashboard de analytics para admins"""
    query = update.callback_query
    await query.answer()
    
    dashboard = get_analytics_dashboard()
    
    text = f"📊 *Analytics Dashboard*\n\n"
    text += f"📈 *Vendas (7 dias):* {dashboard['total_sales']}\n"
    text += f"💰 *Faturamento:* {format_currency(dashboard['total_revenue'])}\n"
    text += f"👥 *Usuários Ativos:* {dashboard['active_users']}\n\n"
    
    text += "🏆 *Produtos Mais Vendidos:*\n"
    for i, product in enumerate(dashboard['top_products'], 1, 6):
        text += f"{i}. {product['name']} - {product['sales']} vendas\n"
    
    await query.edit_message_text(text, parse_mode="Markdown")

async def admin_create_discount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cria código de desconto"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🎟 *Criar Cupom de Desconto*\n\n"
        "Escolha o tipo:\n\n",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 10% de Desconto", callback_data="create_discount_10")],
            [InlineKeyboardButton("💵 R$5 de Desconto", callback_data="create_discount_5")],
            [InlineKeyboardButton("🎯 Personalizado", callback_data="create_discount_custom")],
            [InlineKeyboardButton("🔙 Voltar", callback_data="admin_panel")]
        ])
    )

async def admin_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gerencia categorias"""
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    categories = db.query(Category).all()
    db.close()
    
    if not categories:
        await query.edit_message_text("📂 Nenhuma categoria cadastrada.")
        return
    
    text = "📂 *Categorias Cadastradas*\n\n"
    for cat in categories:
        status = "✅ Ativa" if cat.is_active else "❌ Inativa"
        text += f"{cat.icon or '📂'} {cat.name} - {status}\n"
    
    await query.edit_message_text(text, parse_mode="Markdown")

async def admin_campaigns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gerencia campanhas de marketing"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📢 *Campanhas de Marketing*\n\n"
        "Funcionalidade em desenvolvimento...\n\n"
        "Em breve você poderá:\n"
        "• Criar campanhas personalizadas\n"
        "• Enviar para segmentos de usuários\n"
        "• Acompanhar taxas de abertura\n"
        "• Agendar envios automáticos",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Voltar", callback_data="admin_panel")]
        ])
    )

async def admin_loyalty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sistema de fidelidade"""
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    users_with_loyalty = db.query(LoyaltyPoints, User.first_name).join(User, LoyaltyPoints.user_id == User.id).all()
    db.close()
    
    if not users_with_loyalty:
        await query.edit_message_text("⭐ Nenhum usuário com pontos de fidelidade.")
        return
    
    text = "⭐ *Sistema de Fidelidade*\n\n"
    
    # Estatísticas
    bronze_count = sum(1 for u in users_with_loyalty if u.level == "Bronze")
    silver_count = sum(1 for u in users_with_loyalty if u.level == "Prata")
    gold_count = sum(1 for u in users_with_loyalty if u.level == "Ouro")
    
    text += f"🥉 Bronze: {bronze_count} usuários\n"
    text += f"🥈 Prata: {silver_count} usuários\n"
    text += f"🥇 Ouro: {gold_count} usuários\n\n"
    
    # Top 5 usuários
    top_users = sorted(users_with_loyalty, key=lambda x: x.points, reverse=True)[:5]
    text += "🏆 *Top 5 Usuários:*\n"
    for i, user in enumerate(top_users, 1, 6):
        text += f"{i}. {user.first_name} - {user.points} pontos\n"
    
    await query.edit_message_text(text, parse_mode="Markdown")

async def view_loyalty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ver pontos de fidelidade do usuário"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    loyalty_info = get_user_loyalty_info(user_id)
    
    text = f"⭐ *Meus Pontos de Fidelidade*\n\n"
    text += f"🏆 *Nível Atual:* {loyalty_info['level']}\n"
    text += f"💎 *Pontos Atuais:* {loyalty_info['points']}\n"
    text += f"📈 *Próximo Nível:* {loyalty_info['next_level']}\n"
    text += f"🎯 *Pontos Necessários:* {loyalty_info['points_needed']}\n\n"
    
    text += "🎁 *Benefícios por Nível:*\n"
    text += "🥉 Bronze: Acesso básico\n"
    text += "🥈 Prata: 5% de desconto\n"
    text += "🥇 Ouro: 10% de desconto + Frete Grátis\n"
    
    await query.edit_message_text(text, parse_mode="Markdown")

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
    db.close()
    
    if not category:
        await query.edit_message_text("❌ Categoria não encontrada.")
        return
    
    # Buscar produtos da categoria
    db = SessionLocal()
    products = db.query(Product).filter(
        Product.category_id == category_id,
        Product.is_available == True
    ).all()
    db.close()
    
    if not products:
        await query.edit_message_text(f"📂 Nenhum produto na categoria {category.icon or '📂'} {category.name}.")
        return
    
    text = f"{category.icon or '📂'} *{category.name}*\n\n"
    text += "\n".join(f"*{p.name}*\n💰 {format_currency(p.price)}\n" for p in products)
    
    keyboard = [[InlineKeyboardButton(p.name, callback_data=f"product_{p.id}")] for p in products]
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="categories")])
    keyboard.append([InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")])
    
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def categories_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu de categorias"""
    query = update.callback_query
    await query.answer()
    
    keyboard = get_categories_keyboard()
    if keyboard:
        await query.edit_message_text(
            "📂 *Categorias de Produtos*\n\n"
            "Escolha uma categoria:",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
        await query.edit_message_text(
            "📂 Nenhuma categoria disponível no momento.\n\n"
            "Volte mais tarde!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Menu Principal", callback_data="main_menu")]
            ])
        )

# ======================= HANDLERS DE TEXTO =======================

async def handle_discount_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lida com texto de cupom"""
    if not context.user_data.get("awaiting_discount"):
        return
    
    code = update.message.text.strip().upper()
    user_id = update.effective_user.id
    
    # Obter total do carrinho
    cart = context.user_data.get("cart", {})
    if not cart:
        await update.message.reply_text("❌ Carrinho vazio. Adicione produtos antes de aplicar o cupom.")
        context.user_data["awaiting_discount"] = False
        return
    
    db = SessionLocal()
    total = 0
    for pid, qty in cart.items():
        product = db.query(Product).filter(Product.id == pid).first()
        if product:
            total += product.price * qty
    db.close()
    
    # Validar cupom
    result = validate_discount_code(code, total)
    
    if result["valid"]:
        context.user_data["discount_code"] = code
        context.user_data["discount_amount"] = result["discount_amount"]
        context.user_data["awaiting_discount"] = False
        
        await update.message.reply_text(
            f"✅ *Cupom Aplicado!*\n\n"
            f"🎟 Código: {code}\n"
            f"💰 Desconto: {format_currency(result['discount_amount'])}\n"
            f"💳 Total com desconto: {format_currency(result['final_amount'])}\n\n"
            f"Finalize sua compra!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Finalizar Compra", callback_data="checkout")],
                [InlineKeyboardButton("🗑 Limpar Carrinho", callback_data="clear_cart")]
            ])
        )
    else:
        await update.message.reply_text(f"❌ {result['message']}")
        context.user_data["awaiting_discount"] = False

# ======================= REGISTRAR HANDLERS =======================
def register_advanced_handlers(app: Application):
    """Registra todos os handlers avançados"""
    
    # Handlers de callback
    app.add_handler(CallbackQueryHandler(apply_discount, pattern="^apply_discount$"))
    app.add_handler(CallbackQueryHandler(cancel_discount, pattern="^cancel_discount$"))
    app.add_handler(CallbackQueryHandler(admin_analytics, pattern="^admin_analytics$"))
    app.add_handler(CallbackQueryHandler(admin_create_discount, pattern="^create_discount_"))
    app.add_handler(CallbackQueryHandler(admin_categories, pattern="^admin_categories$"))
    app.add_handler(CallbackQueryHandler(admin_campaigns, pattern="^admin_campaigns$"))
    app.add_handler(CallbackQueryHandler(admin_loyalty, pattern="^admin_loyalty$"))
    app.add_handler(CallbackQueryHandler(view_loyalty, pattern="^view_loyalty$"))
    app.add_handler(CallbackQueryHandler(show_categories, pattern=r"^category_(\d+)$"))
    app.add_handler(CallbackQueryHandler(categories_menu, pattern="^categories$"))
    
    # Handler de texto para cupons
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_discount_text))

print("✅ Modulo de funcionalidades avancadas carregado!")
