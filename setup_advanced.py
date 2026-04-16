#!/usr/bin/env python3
"""
Setup script para funcionalidades avancadas - sem unicode
"""

import os
import sys
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Configuracoes
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///sales_bot.db")

def create_sample_data():
    """Cria dados de exemplo para o sistema"""
    print("Criando dados de exemplo...")
    
    # Criar engine
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    
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
        
        # Criar codigos de desconto
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
                ('Boas-vindas', 'Bem-vindo a nossa loja! Use o cupom WELCOME10 e ganhe 10% de desconto na primeira compra!', 'new_users', 'pending', :now)
        """), {"now": datetime.utcnow()})
        
        db.commit()
        print("Dados de exemplo criados com sucesso!")
        
    except Exception as e:
        print(f"Erro ao criar dados: {e}")
        db.rollback()
    finally:
        db.close()

def update_database():
    """Atualiza o banco de dados com as novas tabelas"""
    print("Atualizando banco de dados...")
    
    # Criar engine
    engine = create_engine(DATABASE_URL)
    
    # Criar todas as tabelas manualmente
    from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
    
    # Tabela categories
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY,
                name VARCHAR UNIQUE NOT NULL,
                description TEXT,
                icon VARCHAR,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # Tabela discount_codes
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS discount_codes (
                id INTEGER PRIMARY KEY,
                code VARCHAR UNIQUE NOT NULL,
                discount_type VARCHAR DEFAULT 'percentage',
                discount_value REAL,
                min_purchase REAL DEFAULT 0.0,
                max_discount REAL,
                usage_limit INTEGER,
                usage_count INTEGER DEFAULT 0,
                expires_at DATETIME,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER
            )
        """))
        
        # Tabela loyalty_points
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS loyalty_points (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                points INTEGER DEFAULT 0,
                points_earned INTEGER DEFAULT 0,
                points_spent INTEGER DEFAULT 0,
                level VARCHAR DEFAULT 'Bronze',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """))
        
        # Tabela analytics
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS analytics (
                id INTEGER PRIMARY KEY,
                event_type VARCHAR NOT NULL,
                user_id INTEGER,
                product_id INTEGER,
                order_id INTEGER,
                value REAL,
                extra_data TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (product_id) REFERENCES products (id),
                FOREIGN KEY (order_id) REFERENCES orders (id)
            )
        """))
        
        # Tabela marketing_campaigns
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS marketing_campaigns (
                id INTEGER PRIMARY KEY,
                name VARCHAR NOT NULL,
                message TEXT,
                target_audience VARCHAR DEFAULT 'all',
                send_at DATETIME,
                sent_at DATETIME,
                status VARCHAR DEFAULT 'pending',
                opens_count INTEGER DEFAULT 0,
                clicks_count INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER,
                FOREIGN KEY (created_by) REFERENCES users (id)
            )
        """))
        
        # Adicionar coluna category_id a products se não existir
        try:
            conn.execute(text("ALTER TABLE products ADD COLUMN category_id INTEGER"))
            conn.execute(text("ALTER TABLE products ADD COLUMN tags TEXT"))
            conn.execute(text("ALTER TABLE products ADD COLUMN view_count INTEGER DEFAULT 0"))
            conn.execute(text("ALTER TABLE products ADD COLUMN purchase_count INTEGER DEFAULT 0"))
            conn.execute(text("ALTER TABLE products ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
            conn.execute(text("ALTER TABLE products ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
        except:
            pass  # Colunas já existem
    
    print("Tabelas criadas/atualizadas")
    
    # Atualizar produtos existentes com categoria_id
    Session = sessionmaker(bind=engine)
    db = Session()
    
    try:
        # Atualizar produtos sem categoria para a primeira categoria
        db.execute(text("""
            UPDATE products 
            SET category_id = 1 
            WHERE category_id IS NULL
        """))
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
