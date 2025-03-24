from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import json
import re
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import validates
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class INC(db.Model):
    """Modelo para Informação de Não-Conformidade"""
    __tablename__ = 'inc'
    
    id = db.Column(db.Integer, primary_key=True)
    nf = db.Column(db.Integer, nullable=False)
    data = db.Column(db.String(20), nullable=False)
    representante_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    representante_nome = db.Column(db.String(100), nullable=False)
    fornecedor = db.Column(db.String(200), nullable=False)
    item = db.Column(db.String(50), nullable=False, index=True)
    quantidade_recebida = db.Column(db.Integer, nullable=False)
    quantidade_com_defeito = db.Column(db.Integer, nullable=False)
    descricao_defeito = db.Column(db.Text)
    urgencia = db.Column(db.String(20), nullable=False)
    acao_recomendada = db.Column(db.Text)
    fotos = db.Column(db.Text)  # JSON string of photo paths
    oc = db.Column(db.Integer, nullable=False, unique=True, index=True)
    status = db.Column(db.String(20), nullable=False, default='Em andamento', index=True)
    concessao_data = db.Column(db.Text, nullable=True)  # JSON string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    representante = db.relationship('User', backref=db.backref('incs_criadas', lazy='dynamic'))
    
    @validates('item')
    def validate_item(self, key, value):
        # Validar formato do item: 3 letras maiúsculas, ponto, 5 dígitos
        pattern = r'^[A-Z]{3}\.\d{5}$'
        if not re.match(pattern, value):
            raise ValueError(f"Formato de item inválido: {value}. Esperado: 3 letras maiúsculas, ponto, 5 dígitos (ex: ABC.12345)")
        return value
    
    @validates('urgencia')
    def validate_urgencia(self, key, value):
        # Validar que urgência é um dos valores permitidos
        allowed = ['leve', 'moderada', 'crítico']
        if value.lower() not in allowed:
            raise ValueError(f"Urgência deve ser uma das seguintes: {', '.join(allowed)}")
        return value
    
    @hybrid_property
    def fotos_list(self):
        """Retorna a lista de fotos como um array Python"""
        if not self.fotos:
            return []
        try:
            return json.loads(self.fotos)
        except json.JSONDecodeError:
            return []
    
    @fotos_list.setter
    def fotos_list(self, value):
        """Define a lista de fotos a partir de um array Python"""
        if isinstance(value, list):
            self.fotos = json.dumps(value)
        else:
            raise TypeError("O valor de fotos deve ser uma lista")
    
    def set_concessao_data(self, data):
        """
        Helper method to set concessao_data safely
        
        :param data: Dictionary with concessao details
        """
        if isinstance(data, dict):
            self.concessao_data = json.dumps(data)
        elif isinstance(data, str):
            # Validate if it's a valid JSON string
            try:
                json.loads(data)
                self.concessao_data = data
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON string for concessao_data")
        else:
            raise TypeError("Concessao data must be a dictionary or a valid JSON string")
    
    def get_concessao_data(self):
        """
        Helper method to get concessao_data safely
        
        :return: Parsed concessao data or None
        """
        if self.concessao_data:
            try:
                return json.loads(self.concessao_data)
            except json.JSONDecodeError:
                return None
        return None
    
    def __repr__(self):
        return f'<INC {self.id}: {self.item} - {self.status}>'

class LayoutSetting(db.Model):
    """Modelo para configurações de layout da interface"""
    __tablename__ = 'layout_setting'
    
    id = db.Column(db.Integer, primary_key=True)
    element = db.Column(db.String(20), unique=True, nullable=False)
    foreground = db.Column(db.String(7), default="#000000")
    background = db.Column(db.String(7), default="#ffffff")
    font_family = db.Column(db.String(50), default="Helvetica")
    font_size = db.Column(db.Integer, default=12)
    
    @validates('foreground', 'background')
    def validate_color(self, key, value):
        # Validar formato de cor hexadecimal: #RRGGBB
        pattern = r'^#[0-9A-Fa-f]{6}$'
        if not re.match(pattern, value):
            raise ValueError(f"Formato de cor inválido: {value}. Esperado: #RRGGBB")
        return value
    
    def __repr__(self):
        return f'<LayoutSetting {self.element}>'

class Fornecedor(db.Model):
    """Modelo para informações de fornecedores"""
    __tablename__ = 'fornecedor'
    
    id = db.Column(db.Integer, primary_key=True)
    razao_social = db.Column(db.String(100), nullable=False, index=True)
    cnpj = db.Column(db.String(18), unique=True, nullable=False, index=True)
    fornecedor_logix = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @validates('cnpj')
    def validate_cnpj(self, key, value):
        # Validar formato do CNPJ: XX.XXX.XXX/XXXX-XX
        pattern = r'^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$'
        if not re.match(pattern, value):
            raise ValueError(f"Formato de CNPJ inválido: {value}. Esperado: XX.XXX.XXX/XXXX-XX")
        return value
    
    def __repr__(self):
        return f'<Fornecedor {self.razao_social}>'

class RotinaInspecao(db.Model):
    """Modelo para rotinas de inspeção"""
    __tablename__ = 'rotina_inspecao'
    
    id = db.Column(db.Integer, primary_key=True)
    inspetor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    data_inspecao = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    registros = db.Column(db.Text, nullable=False)  # JSON com os registros
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    inspetor = db.relationship('User', backref=db.backref('rotinas', lazy=True))
    
    @hybrid_property
    def registros_obj(self):
        """Retorna os registros como objeto Python"""
        if not self.registros:
            return []
        try:
            return json.loads(self.registros)
        except json.JSONDecodeError:
            return []
    
    @registros_obj.setter
    def registros_obj(self, value):
        """Define os registros a partir de um objeto Python"""
        if isinstance(value, (list, dict)):
            self.registros = json.dumps(value)
        else:
            raise TypeError("O valor dos registros deve ser uma lista ou dicionário")
    
    def __repr__(self):
        return f'<RotinaInspecao {self.id}: {self.data_inspecao}>'

class SolicitacaoFaturamento(db.Model):
    """Modelo para solicitações de faturamento"""
    __tablename__ = 'solicitacao_faturamento'
    
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, unique=True, nullable=False, index=True)
    tipo = db.Column(db.String(30), nullable=False, index=True)  # Conserto, Conserto em Garantia, Devolução
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    fornecedor = db.Column(db.String(100), nullable=False, index=True)
    volumes = db.Column(db.Integer, nullable=False)
    tipo_frete = db.Column(db.String(3), nullable=False)  # CIF, FOB
    observacoes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    usuario = db.relationship('User', backref=db.backref('solicitacoes', lazy=True))
    itens = db.relationship('ItemSolicitacaoFaturamento', backref='solicitacao', lazy=True, cascade="all, delete-orphan")
    
    @validates('tipo')
    def validate_tipo(self, key, value):
        allowed = ['Conserto', 'Conserto em Garantia', 'Devolução']
        if value not in allowed:
            raise ValueError(f"Tipo deve ser um dos seguintes: {', '.join(allowed)}")
        return value
    
    @validates('tipo_frete')
    def validate_tipo_frete(self, key, value):
        allowed = ['CIF', 'FOB']
        if value not in allowed:
            raise ValueError(f"Tipo de frete deve ser um dos seguintes: {', '.join(allowed)}")
        return value
    
    def __repr__(self):
        return f'<SolicitacaoFaturamento {self.numero}: {self.tipo}>'

class ItemSolicitacaoFaturamento(db.Model):
    """Modelo para itens de solicitação de faturamento"""
    __tablename__ = 'item_solicitacao_faturamento'
    
    id = db.Column(db.Integer, primary_key=True)
    solicitacao_id = db.Column(db.Integer, db.ForeignKey('solicitacao_faturamento.id'), nullable=False)
    inc_id = db.Column(db.Integer, db.ForeignKey('inc.id'), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    inc = db.relationship('INC')
    
    @validates('quantidade')
    def validate_quantidade(self, key, value):
        if value <= 0:
            raise ValueError("A quantidade deve ser maior que zero")
        return value
    
    def __repr__(self):
        return f'<ItemSolicitacaoFaturamento {self.id}: INC {self.inc_id}, Qtd {self.quantidade}>'

class PrateleiraNaoConforme(db.Model):
    """Modelo para itens na prateleira não-conforme"""
    __tablename__ = 'prateleira_nao_conforme'
    
    id = db.Column(db.Integer, primary_key=True)
    item = db.Column(db.String(20), nullable=False, index=True)
    descricao = db.Column(db.String(255), nullable=False)
    quantidade = db.Column(db.Float, nullable=False)
    data_ultima_movimentacao = db.Column(db.String(10), nullable=False)
    data_importacao = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    tipo_defeito = db.Column(db.String(20), nullable=False, default="Produção", index=True)  # "Recebimento" ou "Produção"
    inc_id = db.Column(db.Integer, db.ForeignKey('inc.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    inc = db.relationship('INC', backref=db.backref('itens_prateleira', lazy=True))
    
    @validates('tipo_defeito')
    def validate_tipo_defeito(self, key, value):
        allowed = ["Recebimento", "Produção"]
        if value not in allowed:
            raise ValueError(f"Tipo de defeito deve ser um dos seguintes: {', '.join(allowed)}")
        return value
    
    @validates('item')
    def validate_item(self, key, value):
        # Validar formato do item: 3 letras maiúsculas, ponto, 5 dígitos
        pattern = r'^[A-Z]{3}\.\d{5}$'
        if not re.match(pattern, value):
            raise ValueError(f"Formato de item inválido: {value}. Esperado: 3 letras maiúsculas, ponto, 5 dígitos (ex: ABC.12345)")
        return value
    
    @property
    def age_in_hours(self):
        """Retorna a idade dos dados em horas."""
        if self.data_importacao:
            delta = datetime.utcnow() - self.data_importacao
            return delta.total_seconds() / 3600
        return 0
    
    def __repr__(self):
        return f'<PrateleiraNaoConforme {self.item}: {self.quantidade} unidades>'

class User(UserMixin, db.Model):
    """Modelo para usuários do sistema"""
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)
    is_admin = db.Column(db.Boolean, default=False)
    is_representante = db.Column(db.Boolean, default=False)
    permissions = db.Column(db.Text, default='{}')  # JSON para permissões
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    active = db.Column(db.Boolean, default=True)
    
    @property
    def password(self):
        raise AttributeError('password não é um atributo legível')
    
    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def has_permission(self, permission_name):
        """Verifica se o usuário tem uma permissão específica"""
        if self.is_admin:  # Administradores têm todas as permissões
            return True
        
        try:
            perms = json.loads(self.permissions)
            return perms.get(permission_name, False)
        except json.JSONDecodeError:
            return False
    
    def set_permission(self, permission_name, value=True):
        """Define uma permissão para o usuário"""
        try:
            perms = json.loads(self.permissions)
        except json.JSONDecodeError:
            perms = {}
        
        perms[permission_name] = value
        self.permissions = json.dumps(perms)
    
    def get_all_permissions(self):
        """Retorna todas as permissões do usuário"""
        try:
            return json.loads(self.permissions)
        except json.JSONDecodeError:
            return {}
    
    @validates('email')
    def validate_email(self, key, value):
        if value:
            # Validar formato de email
            pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(pattern, value):
                raise ValueError(f"Formato de email inválido: {value}")
        return value
    
    def __repr__(self):
        return f'<User {self.username}>'

class UserActivityLog(db.Model):
    """Modelo para registrar as ações dos usuários no sistema"""
    __tablename__ = 'user_activity_log'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False, index=True)
    entity_type = db.Column(db.String(50), nullable=False, index=True)
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relacionamentos
    user = db.relationship('User', backref=db.backref('activity_logs', lazy=True))
    
    @hybrid_property
    def details_obj(self):
        """Retorna os detalhes como objeto Python"""
        if not self.details:
            return {}
        try:
            return json.loads(self.details)
        except json.JSONDecodeError:
            return {}
    
    def __repr__(self):
        return f'<UserActivityLog {self.id}: {self.user.username} {self.action} {self.entity_type}>'

class InspectionActivity(db.Model):
    """Modelo para atividades de inspeção"""
    __tablename__ = 'inspection_activity'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    denominations = db.relationship('ActivityDenomination', backref='activity', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<InspectionActivity {self.name}>'

class ActivityDenomination(db.Model):
    """Modelo para denominações de atividade"""
    __tablename__ = 'activity_denomination'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('inspection_activity.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ActivityDenomination {self.name}>'

class InspectionMethod(db.Model):
    """Modelo para métodos de inspeção"""
    __tablename__ = 'inspection_method'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<InspectionMethod {self.name}>'

class InspectionPlan(db.Model):
    """Modelo para planos de inspeção"""
    __tablename__ = 'inspection_plan'
    
    id = db.Column(db.Integer, primary_key=True)
    item = db.Column(db.String(20), nullable=False, index=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('inspection_activity.id'), nullable=False)
    denomination_id = db.Column(db.Integer, db.ForeignKey('activity_denomination.id'), nullable=False)
    method_id = db.Column(db.Integer, db.ForeignKey('inspection_method.id'), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relacionamentos
    activity = db.relationship('InspectionActivity')
    denomination = db.relationship('ActivityDenomination')
    method = db.relationship('InspectionMethod')
    creator = db.relationship('User')
    
    @validates('item')
    def validate_item(self, key, value):
        # Validar formato do item: 3 letras maiúsculas, ponto, 5 dígitos
        pattern = r'^[A-Z]{3}\.\d{5}$'
        if not re.match(pattern, value):
            raise ValueError(f"Formato de item inválido: {value}. Esperado: 3 letras maiúsculas, ponto, 5 dígitos (ex: ABC.12345)")
        return value
    
    def __repr__(self):
        return f'<InspectionPlan {self.id}: {self.item}>'

class Notification(db.Model):
    """Modelo para notificações do sistema"""
    __tablename__ = 'notification'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Pode ser nulo para notificações globais
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(20), nullable=False, default='info')  # task, system, alert, message, reminder, update
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Campos para notificações acionáveis
    entity_type = db.Column(db.String(50), nullable=True)  # inc, inspecao, etc.
    entity_id = db.Column(db.Integer, nullable=True)
    action_text = db.Column(db.String(50), nullable=True)  # Texto do botão de ação
    
    # Relacionamentos
    user = db.relationship('User', backref=db.backref('notifications', lazy=True))
    
    @property
    def action_url(self):
        """Retorna a URL de ação apropriada baseada no tipo de entidade e ID"""
        if not self.entity_type or not self.entity_id:
            return None
            
        if self.entity_type == 'inc':
            return f'/inc/detalhes_inc/{self.entity_id}'
        elif self.entity_type == 'inspecao':
            return f'/inspecao/listar_rotinas'
        elif self.entity_type == 'fornecedor':
            return f'/fornecedor/visualizar/{self.entity_id}'
        # Adicionar mais tipos conforme necessário
        return None
    
    def __repr__(self):
        return f'<Notification {self.id}: {self.title}>'