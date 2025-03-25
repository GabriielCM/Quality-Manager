from app import app
from db_migration import add_reincidencia_to_rnc
from models import db, MigrationHistory
from sqlalchemy import text

# Executar a migração dentro do contexto da aplicação
with app.app_context():
    print("Iniciando migração para adicionar coluna 'reincidencia'...")
    
    try:
        # Adicionar a coluna
        # Se ocorrer erro devido à coluna já existir, tente executar o SQL diretamente
        try:
            add_reincidencia_to_rnc()
        except Exception as e:
            print(f"Primeira tentativa falhou: {str(e)}")
            print("Tentando alternativa...")
            sql = text("ALTER TABLE registro_nao_conformidade ADD COLUMN reincidencia BOOLEAN DEFAULT 0 NOT NULL;")
            try:
                db.session.execute(sql)
                db.session.commit()
                print("Coluna adicionada com sucesso na segunda tentativa!")
            except Exception as e2:
                # Se a coluna já existe, isso não é um erro
                if "duplicate column name" in str(e2) or "already exists" in str(e2):
                    print("Coluna já existe, continuando...")
                else:
                    raise e2
        
        # Registrar migração como concluída
        migration = MigrationHistory(migration_name='add_reincidencia_to_rnc')
        db.session.add(migration)
        db.session.commit()
        
        print("Migração concluída com sucesso!")
    except Exception as e:
        db.session.rollback()
        print(f"Erro durante a migração: {str(e)}") 