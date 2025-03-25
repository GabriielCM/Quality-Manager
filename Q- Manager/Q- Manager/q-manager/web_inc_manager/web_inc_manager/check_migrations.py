from app import app
from models import db, MigrationHistory
from sqlalchemy import text

# Executar dentro do contexto da aplicação
with app.app_context():
    print("Verificando as migrações registradas...")
    
    try:
        # Verificar se a tabela migration_history existe
        table_exists = db.session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='migration_history';")
        ).fetchone()
        
        if not table_exists:
            print("A tabela migration_history não existe!")
        else:
            # Obter migrações registradas
            migrations = MigrationHistory.query.all()
            
            print("\nMigrações registradas:")
            print("=" * 50)
            for migration in migrations:
                print(f"{migration.id}: {migration.migration_name} - {migration.applied_at}")
            print("=" * 50)
            
            # Verificar especificamente a migração add_reincidencia_to_rnc
            reincidencia_migration = MigrationHistory.query.filter_by(
                migration_name='add_reincidencia_to_rnc'
            ).first()
            
            if reincidencia_migration:
                print("\nA migração 'add_reincidencia_to_rnc' está registrada!")
            else:
                print("\nA migração 'add_reincidencia_to_rnc' NÃO está registrada!")
                
    except Exception as e:
        print(f"Erro ao verificar as migrações: {str(e)}") 