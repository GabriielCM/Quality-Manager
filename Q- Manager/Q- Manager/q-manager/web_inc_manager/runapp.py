"""
Script simplificado para executar o aplicativo Flask
"""
import os
import sys
from flask import Flask, render_template, redirect, url_for
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

# Criar a aplicação Flask
app = Flask(__name__, 
            template_folder='web_inc_manager/templates',
            static_folder='web_inc_manager/static')

# Configurações básicas
app.config['SECRET_KEY'] = 'chave-secreta-desenvolvimento'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/inc_manager.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                         'web_inc_manager', 'static', 'uploads')

# Inicializar banco de dados
db = SQLAlchemy(app)

# Adicionar a função now() ao contexto global do Jinja2
@app.template_global()
def now():
    return datetime.utcnow()

# Páginas de teste
@app.route('/')
def index():
    return redirect(url_for('test_rnc'))

@app.route('/test_rnc')
def test_rnc():
    rnc = {
        "numero": "001/2023",
        "fornecedor": "Empresa Teste",
        "data_emissao": datetime.now(),
        "descricao_nao_conformidade": "Descrição de teste da não conformidade",
        "status": "Pendente"
    }
    return render_template('rnc_responder.html', rnc=rnc)

# Rota de teste específica que simula o token
@app.route('/rnc/responder/<token>')
def responder_rnc(token):
    rnc = {
        "numero": "001/2023",
        "fornecedor": "Empresa Teste",
        "data_emissao": datetime.now(),
        "descricao_nao_conformidade": "Descrição de teste da não conformidade",
        "status": "Pendente",
        "token": token
    }
    return render_template('rnc_responder.html', rnc=rnc)

if __name__ == '__main__':
    print("Iniciando servidor Flask simplificado...")
    app.run(debug=True, host='0.0.0.0', port=5000) 