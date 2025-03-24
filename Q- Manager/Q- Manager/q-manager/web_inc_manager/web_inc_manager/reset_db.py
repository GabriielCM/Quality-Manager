import os
import sys
import glob
from werkzeug.security import generate_password_hash
from flask import Flask
from models import db, User

# Configurar o aplicativo Flask
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///web_inc_manager.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def reset_database():
    """Limpa o banco de dados e cria uma nova instância com o usuário admin"""
    
    print("Iniciando reset do banco de dados...")
    
    # Remover arquivos de banco de dados existentes
    db_files = glob.glob('*.db')
    db_files += glob.glob('instance/*.db')
    
    for db_file in db_files:
        try:
            os.remove(db_file)
            print(f"Arquivo removido: {db_file}")
        except Exception as e:
            print(f"Erro ao remover {db_file}: {e}")
    
    with app.app_context():
        # Criar tabelas do banco de dados
        print("Criando novas tabelas...")
        db.create_all()
        
        # Criar usuário admin
        print("Criando usuário admin...")
        admin = User(
            username="admin", 
            password="SenhaComplexaInicial123!",  # Usar o setter que aplica o hash
            is_admin=True
        )
        db.session.add(admin)
        
        # Confirmar alterações
        db.session.commit()
        print("Banco de dados reinicializado com sucesso!")
        print("Usuário admin criado com senha: SenhaComplexaInicial123!")

if __name__ == "__main__":
    # Pedir confirmação
    confirm = input("Isso irá APAGAR todos os dados existentes. Tem certeza? (s/n): ")
    
    if confirm.lower() == 's':
        reset_database()
    else:
        print("Operação cancelada.") 