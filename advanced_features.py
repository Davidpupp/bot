#!/usr/bin/env python3
"""
Funcionalidades Avancadas Simplificadas
"""

import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

# Configuracoes
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///sales_bot.db")
ADMIN_IDS = [8649452369]

# Criar sessao local
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Funcoes basicas
def format_currency(value: float) -> str:
    return f"R$ {value:.2f}".replace(".", ",")

# ======================= MODELOS AVANCADOS =======================
class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, index=True)
    description = Column(Text, nullable=True)
    icon = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    products = relationship("Product", back_populates="category")

class DiscountCode(Base):
    __tablename__ = "discount_codes"
    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, index=True)
    discount_type = Column(String, default="percentage")
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
    level = Column(String, default="Bronze")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="loyalty")

class Analytics(Base):
    __tablename__ = "analytics"
    id = Column(Integer, primary_key=True)
    event_type = Column(String, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    value = Column(Float, nullable=True)
    extra_data = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class MarketingCampaign(Base):
    __tablename__ = "marketing_campaigns"
    id = Column(Integer, primary_key=True)
    name = Column(String, index=True)
    message = Column(Text)
    target_audience = Column(String, default="all")
    send_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    status = Column(String, default="pending")
    opens_count = Column(Integer, default=0)
    clicks_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))

# ======================= FUNCOES AVANCADAS =======================

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

def validate_discount_code(code: str, total_amount: float) -> dict:
    """Valida e aplica codigo de desconto"""
    db = SessionLocal()
    discount = db.query(DiscountCode).filter(
        DiscountCode.code == code,
        DiscountCode.is_active == True
    ).first()
    
    if not discount:
        db.close()
        return {"valid": False, "message": "Codigo invalido"}
    
    # Verificar expiracao
    if discount.expires_at and discount.expires_at < datetime.utcnow():
        db.close()
        return {"valid": False, "message": "Codigo expirado"}
    
    # Verificar limite de uso
    if discount.usage_limit and discount.usage_count >= discount.usage_limit:
        db.close()
        return {"valid": False, "message": "Limite de uso atingido"}
    
    # Verificar compra minima
    if total_amount < discount.min_purchase:
        db.close()
        return {"valid": False, "message": f"Compra minima de {format_currency(discount.min_purchase)}"}
    
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
        
        # Atualizar nivel
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
    """Obtem informacoes de fidelidade do usuario"""
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

def create_sample_data():
    """Cria dados de exemplo"""
    print("Criando dados de exemplo...")
    
    db = SessionLocal()
    
    try:
        # Criar categorias
        categories = [
            Category(name="E-books", icon="📚", description="Livros digitais diversos"),
            Category(name="Cursos", icon="🎓", description="Cursos online e videoaulas"),
            Category(name="Software", icon="💻", description="Programas e ferramentas"),
            Category(name="Templates", icon="📄", description="Modelos e documentos"),
            Category(name="Premium", icon="⭐", description="Conteudo exclusivo VIP")
        ]
        
        for cat in categories:
            existing = db.query(Category).filter(Category.name == cat.name).first()
            if not existing:
                db.add(cat)
        
        # Criar codigos de desconto
        discount_codes = [
            DiscountCode(
                code="WELCOME10",
                discount_type="percentage",
                discount_value=10.0,
                min_purchase=50.0,
                usage_limit=100,
                expires_at=datetime.utcnow() + timedelta(days=30)
            ),
            DiscountCode(
                code="VIP20",
                discount_type="percentage", 
                discount_value=20.0,
                min_purchase=100.0,
                usage_limit=50,
                expires_at=datetime.utcnow() + timedelta(days=60)
            ),
            DiscountCode(
                code="FIXED15",
                discount_type="fixed",
                discount_value=15.0,
                min_purchase=0.0,
                usage_limit=200,
                expires_at=datetime.utcnow() + timedelta(days=45)
            )
        ]
        
        for discount in discount_codes:
            existing = db.query(DiscountCode).filter(DiscountCode.code == discount.code).first()
            if not existing:
                db.add(discount)
        
        db.commit()
        print("Dados de exemplo criados com sucesso!")
        
    except Exception as e:
        print(f"Erro ao criar dados: {e}")
        db.rollback()
    finally:
        db.close()

def update_database():
    """Atualiza o banco com novas tabelas"""
    print("Atualizando banco de dados...")
    
    # Criar engine
    engine = create_engine(DATABASE_URL)
    
    # Criar todas as tabelas
    Base.metadata.create_all(bind=engine)
    print("Tabelas criadas/atualizadas")
    
    # Atualizar produtos existentes com categoria_id
    Session = sessionmaker(bind=engine)
    db = Session()
    
    try:
        # Atualizar produtos sem categoria para a primeira categoria
        first_category = db.query(Category).first()
        if first_category:
            db.execute(text("""
                UPDATE products 
                SET category_id = :cat_id 
                WHERE category_id IS NULL
            """), {"cat_id": first_category.id})
            db.commit()
            print("Produtos atualizados com categorias")
    except Exception as e:
        print(f"Erro ao atualizar produtos: {e}")
        db.rollback()
    finally:
        db.close()

def main():
    """Funcao principal"""
    print("Inicializando sistema avancado...")
    
    # Atualizar banco de dados
    update_database()
    
    # Criar dados de exemplo
    create_sample_data()
    
    print("\nSistema inicializado com sucesso!")
    print("\nFuncionalidades disponiveis:")
    print("- Categorias de produtos")
    print("- Sistema de cupons de desconto")
    print("- Programa de fidelidade")
    print("- Dashboard de analytics")
    print("- Campanhas de marketing")
    print("- Segmentacao de usuarios")
    print("\nPara usar:")
    print("1. Reinicie o bot: python bot.py")
    print("2. Use /start no Telegram")
    print("3. Explore as novas funcionalidades!")

if __name__ == "__main__":
    main()
