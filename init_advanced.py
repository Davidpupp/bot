#!/usr/bin/env python3
"""
Script de inicialização para funcionalidades avançadas
Cria tabelas, dados de teste e configura o sistema
"""

import os
import sys
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Adicionar o diretório atual ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot import DATABASE_URL, SessionLocal, Base
from advanced_features import Category, DiscountCode, LoyaltyPoints, Analytics, MarketingCampaign

def create_sample_data():
    """Cria dados de exemplo para o sistema"""
    print("🔧 Criando dados de exemplo...")
    
    db = SessionLocal()
    
    try:
        # Criar categorias
        categories = [
            Category(name="E-books", icon="📚", description="Livros digitais diversos"),
            Category(name="Cursos", icon="🎓", description="Cursos online e videoaulas"),
            Category(name="Software", icon="💻", description="Programas e ferramentas"),
            Category(name="Templates", icon="📄", description="Modelos e documentos"),
            Category(name="Premium", icon="⭐", description="Conteúdo exclusivo VIP")
        ]
        
        for cat in categories:
            existing = db.query(Category).filter(Category.name == cat.name).first()
            if not existing:
                db.add(cat)
        
        db.commit()
        print("✅ Categorias criadas")
        
        # Criar códigos de desconto
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
        print("✅ Códigos de desconto criados")
        
        # Criar campanha de marketing
        campaign = MarketingCampaign(
            name="Boas-vindas",
            message="🎉 Bem-vindo à nossa loja! Use o cupom WELCOME10 e ganhe 10% de desconto na primeira compra! 🛍️",
            target_audience="new_users",
            status="pending"
        )
        
        existing = db.query(MarketingCampaign).filter(MarketingCampaign.name == campaign.name).first()
        if not existing:
            db.add(campaign)
        
        db.commit()
        print("✅ Campanha de marketing criada")
        
        print("🎉 Dados de exemplo criados com sucesso!")
        
    except Exception as e:
        print(f"❌ Erro ao criar dados: {e}")
        db.rollback()
    finally:
        db.close()

def update_database():
    """Atualiza o banco de dados com as novas tabelas"""
    print("🗄️ Atualizando banco de dados...")
    
    # Criar engine
    engine = create_engine(DATABASE_URL)
    
    # Criar todas as tabelas
    Base.metadata.create_all(bind=engine)
    print("✅ Tabelas criadas/atualizadas")
    
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
            print("✅ Produtos atualizados com categorias")
    except Exception as e:
        print(f"❌ Erro ao atualizar produtos: {e}")
        db.rollback()
    finally:
        db.close()

def main():
    """Função principal"""
    print("🚀 Inicializando sistema avançado...")
    
    # Atualizar banco de dados
    update_database()
    
    # Criar dados de exemplo
    create_sample_data()
    
    print("\n✅ Sistema inicializado com sucesso!")
    print("\n📋 Funcionalidades disponíveis:")
    print("• 📂 Categorias de produtos")
    print("• 🎟 Sistema de cupons de desconto")
    print("• ⭐ Programa de fidelidade")
    print("• 📊 Dashboard de analytics")
    print("• 📢 Campanhas de marketing")
    print("• 🎯 Segmentação de usuários")
    print("\n🎯 Para usar:")
    print("1. Reinicie o bot: python bot.py")
    print("2. Use /start no Telegram")
    print("3. Explore as novas funcionalidades!")

if __name__ == "__main__":
    main()
