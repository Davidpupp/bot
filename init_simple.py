#!/usr/bin/env python3
"""
Script simples de inicialização para funcionalidades avançadas
"""

import os
import sys
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Adicionar o diretório atual ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot import DATABASE_URL, SessionLocal, Base

def create_sample_data():
    """Cria dados de exemplo para o sistema"""
    print("🔧 Criando dados de exemplo...")
    
    db = SessionLocal()
    
    try:
        # Criar categorias
        db.execute(text("""
            INSERT OR IGNORE INTO categories (name, description, icon, is_active, created_at)
            VALUES 
                ('E-books', 'Livros digitais diversos', '📚', 1, :now),
                ('Cursos', 'Cursos online e videoaulas', '🎓', 1, :now),
                ('Software', 'Programas e ferramentas', '💻', 1, :now),
                ('Templates', 'Modelos e documentos', '📄', 1, :now),
                ('Premium', 'Conteudo exclusivo VIP', '⭐', 1, :now)
        """), {"now": datetime.utcnow()})
        
        # Criar códigos de desconto
        db.execute(text("""
            INSERT OR IGNORE INTO discount_codes (code, discount_type, discount_value, min_purchase, usage_limit, expires_at, is_active, created_at)
            VALUES 
                ('WELCOME10', 'percentage', 10.0, 50.0, 100, :expire30, 1, :now),
                ('VIP20', 'percentage', 20.0, 100.0, 50, :expire60, 1, :now),
                ('FIXED15', 'fixed', 15.0, 0.0, 200, :expire45, 1, :now)
        """), {
            "expire30": datetime.utcnow() + timedelta(days=30),
            "expire60": datetime.utcnow() + timedelta(days=60),
            "expire45": datetime.utcnow() + timedelta(days=45),
            "now": datetime.utcnow()
        })
        
        # Criar campanha de marketing
        db.execute(text("""
            INSERT OR IGNORE INTO marketing_campaigns (name, message, target_audience, status, created_at)
            VALUES 
                ('Boas-vindas', '🎉 Bem-vindo a nossa loja! Use o cupom WELCOME10 e ganhe 10% de desconto na primeira compra! 🛍️', 'new_users', 'pending', :now)
        """), {"now": datetime.utcnow()})
        
        db.commit()
        print("✅ Dados de exemplo criados com sucesso!")
        
    except Exception as e:
        print(f"❌ Erro ao criar dados: {e}")
        db.rollback()
    finally:
        db.close()

def update_database():
    """Atualiza o banco de dados com as novas tabelas"""
    print("🗃️ Atualizando banco de dados...")
    
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
        db.execute(text("""
            UPDATE products 
            SET category_id = (
                SELECT id FROM categories WHERE id = 1
            ) 
            WHERE category_id IS NULL
        """))
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
