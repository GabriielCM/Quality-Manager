from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class INC(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nf = db.Column(db.Integer, nullable=False, unique=False)
    data = db.Column(db.String(10), nullable=False)
    representante = db.Column(db.String(100), nullable=False)
    fornecedor = db.Column(db.String(100), nullable=False)
    item = db.Column(db.String(20), nullable=False)
    quantidade_recebida = db.Column(db.Integer, nullable=False)
    quantidade_com_defeito = db.Column(db.Integer, nullable=False)
    descricao_defeito = db.Column(db.Text, default="")
    urgencia = db.Column(db.String(20), default="Moderada")
    acao_recomendada = db.Column(db.Text, default="")
    fotos = db.Column(db.Text, default="[]")
    status = db.Column(db.String(20), default="Em andamento")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    oc = db.Column(db.Integer, unique=True, nullable=False)

class LayoutSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    element = db.Column(db.String(20), unique=True, nullable=False)
    foreground = db.Column(db.String(7), default="#000000")
    background = db.Column(db.String(7), default="#ffffff")
    font_family = db.Column(db.String(50), default="Helvetica")
    font_size = db.Column(db.Integer, default=12)

class Fornecedor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    razao_social = db.Column(db.String(100), nullable=False)
    cnpj = db.Column(db.String(18), unique=True, nullable=False)
    fornecedor_logix = db.Column(db.String(100), nullable=False)

# Novo modelo para Rotina de Inspeção
class RotinaInspecao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    inspetor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Relaciona com o usuário
    data_inspecao = db.Column(db.DateTime, default=datetime.utcnow)
    registros = db.Column(db.Text, nullable=False)  # JSON com os registros (itens inspecionados/adiados)
    inspetor = db.relationship('User', backref=db.backref('rotinas', lazy=True))