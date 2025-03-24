import os
import logging
from logging.handlers import RotatingFileHandler
import matplotlib
matplotlib.use('Agg')  # Use the 'Agg' backend which doesn't require GUI

from flask import Flask, redirect, url_for, render_template, flash, session
from flask_session import Session
from flask_login import LoginManager, current_user, login_required
from werkzeug.security import generate_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime, timedelta
# Importar módulos do aplicativo
from config import Config
from models import db, User, INC, RotinaInspecao, LayoutSetting, Fornecedor, Notification
from utils import log_user_activity, save_file, remove_file

# Importar rotas de cada módulo
import auth
import inc_routes
import fornecedor_routes
import prateleira_routes
import inspecao_routes
import faturamento_routes
import log_routes
import api_routes

# Inicializar o aplicativo
app = Flask(__name__)
app.config.from_object(Config)

# Inicializar extensões
db.init_app(app)
migrate = Migrate(app, db)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True  # Aumentar segurança da sessão
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=4)  # Limitar sessões a 4 horas

Session(app)

@app.template_filter('date')
def date_filter(value, format='%d/%m/%Y %H:%M'):
    """Filtro para formatar datas em templates."""
    if not value:
        return ''
    
    try:
        # Se for uma string ISO
        if isinstance(value, str):
            try:
                # Tenta parse ISO com timezone
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                # Tenta outros formatos
                try:
                    dt = datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%f')
                except ValueError:
                    try:
                        dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S.%f')
                    except ValueError:
                        return value
        elif isinstance(value, datetime):
            dt = value
        else:
            return str(value)
        
        return dt.strftime(format)
    except Exception as e:
        app.logger.error(f"Erro ao formatar data: {e}")
        return str(value)

# Configurar login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"
login_manager.login_message = "Por favor, faça login para acessar esta página."
login_manager.login_message_category = "warning"

# Assegurar que pasta de uploads existe
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Configurações de logging
logging.basicConfig(
    level=logging.INFO,  # Alterado de DEBUG para INFO em produção
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        RotatingFileHandler('app.log', maxBytes=10485760, backupCount=5),  # Rotação de logs (10MB)
        logging.StreamHandler()
    ]
)

# Registrar blueprints
app.register_blueprint(auth.auth_bp)
app.register_blueprint(inc_routes.inc_bp)
app.register_blueprint(fornecedor_routes.fornecedor_bp)
app.register_blueprint(prateleira_routes.prateleira_bp)
app.register_blueprint(inspecao_routes.inspecao_bp)
app.register_blueprint(faturamento_routes.faturamento_bp)
app.register_blueprint(log_routes.log_bp)
app.register_blueprint(api_routes.api_bp)

# Loader de usuário para Flask-Login
@login_manager.user_loader
def load_user(user_id):
    # Utilizando Session.get() em vez de Query.get()
    return db.session.get(User, int(user_id))

# Rota principal
@app.route('/')
def index():
    return redirect(url_for('auth.login'))

@app.route('/main_menu')
@login_required
def main_menu():
    """
    Renderiza o menu principal com estatísticas e informações relevantes.
    Otimizado para usar menos consultas ao banco de dados.
    """
    try:
        # Estatísticas para cards - Usando uma única query com contagem
        # Corrigindo a sintaxe do case para SQLAlchemy 2.0
        incs_stats = db.session.query(
            db.func.sum(db.case((INC.status == 'Em andamento', 1), else_=0)).label('abertas'),
            db.func.sum(db.case((INC.status == 'Concluída', 1), else_=0)).label('concluidas')
        ).first()
        
        total_incs_abertas = incs_stats.abertas or 0
        total_incs_concluidas = incs_stats.concluidas or 0
        
        # INCs vencidas - Usando formato de data padronizado no banco
        today = datetime.today().date()
        
        # Query otimizada para INCs vencidas
        incs = INC.query.all()
        total_incs_vencidas = 0
        
        urgency_delta = {
            "leve": 45,
            "moderada": 20,
            "crítico": 10
        }
        
        for inc in incs:
            try:
                inc_date = datetime.strptime(inc.data, "%d-%m-%Y").date()
                delta_days = urgency_delta.get(inc.urgencia.lower(), 45)
                expiration_date = inc_date + timedelta(days=delta_days)
                if today > expiration_date:
                    total_incs_vencidas += 1
            except (ValueError, AttributeError) as e:
                app.logger.error(f"Erro ao processar data da INC {inc.id}: {e}")
        
        # Total de registros inspecionados - Com tratamento de erros
        inspections = RotinaInspecao.query.all()
        total_inspecionados = 0
        
        import json
        for inspection in inspections:
            try:
                registros = json.loads(inspection.registros)
                inspecionados = [r for r in registros if r.get('inspecionado', False)]
                total_inspecionados += len(inspecionados)
            except (json.JSONDecodeError, AttributeError) as e:
                app.logger.error(f"Erro ao processar registros da inspeção {inspection.id}: {e}")
        
        # Últimas rotinas de inspeção - Limitando a 5 para performance
        ultimas_rotinas = RotinaInspecao.query.order_by(RotinaInspecao.data_inspecao.desc()).limit(5).all()
        
        # Ranking de fornecedores com mais INCs - Query otimizada
        fornecedor_ranking = db.session.query(
            INC.fornecedor, 
            db.func.count(INC.id).label('total')
        ).group_by(INC.fornecedor).order_by(db.func.count(INC.id).desc()).limit(5).all()
        
        fornecedor_ranking = [
            {'nome': fornecedor, 'total_incs': total} 
            for fornecedor, total in fornecedor_ranking
        ]
        
        # Fornecedores com últimas INCs - Otimizado com JOIN
        # Coletando IDs de fornecedores primeiro para economizar memória
        fornecedor_ids = db.session.query(Fornecedor.id, Fornecedor.razao_social).all()
        
        fornecedores_list = []
        for fornecedor_id, razao_social in fornecedor_ids:
            # Usando Session.get() em vez de Query.get()
            fornecedor = db.session.get(Fornecedor, fornecedor_id)
            
            # Contar INCs para este fornecedor
            fornecedor.total_incs = INC.query.filter_by(fornecedor=fornecedor.razao_social).count()
            
            # Últimas 3 INCs deste fornecedor
            fornecedor.ultimas_incs = INC.query.filter_by(
                fornecedor=fornecedor.razao_social
            ).order_by(INC.id.desc()).limit(3).all()
            
            fornecedores_list.append(fornecedor)
        
        # Registrar acesso ao menu principal
        log_user_activity(
            user_id=current_user.id,
            action="view",
            entity_type="main_menu",
            details={
                "stats": {
                    "incs_abertas": total_incs_abertas,
                    "incs_concluidas": total_incs_concluidas,
                    "incs_vencidas": total_incs_vencidas,
                    "total_inspecionados": total_inspecionados
                }
            }
        )
        
        return render_template('main_menu.html',
                              total_incs_abertas=total_incs_abertas,
                              total_incs_concluidas=total_incs_concluidas,
                              total_incs_vencidas=total_incs_vencidas,
                              total_inspecionados=total_inspecionados,
                              ultimas_rotinas=ultimas_rotinas,
                              fornecedor_ranking=fornecedor_ranking,
                              fornecedores=fornecedores_list)
    except Exception as e:
        app.logger.error(f"Erro no main_menu: {e}")
        flash(f"Ocorreu um erro ao carregar o menu principal. Detalhes: {str(e)}", "danger")
        return render_template('main_menu.html')

# Processador de contexto para injetar configurações
@app.context_processor
def inject_settings():
    from models import LayoutSetting
    settings = {s.element: s for s in LayoutSetting.query.all()}
    return dict(settings=settings, config=app.config)

# Adicionar filtros ao Jinja2
import json as json_lib
app.jinja_env.filters['from_json'] = lambda s: json_lib.loads(s) if s else {}
app.jinja_env.filters['enumerate'] = lambda iterable: enumerate(iterable)
app.jinja_env.filters['tojson'] = lambda x: json_lib.dumps(x)

# Tratamento de exceções para o aplicativo todo
@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    app.logger.error(f"Erro 500: {str(e)}")
    return render_template('errors/500.html'), 500

# Inicialização do banco de dados deve ser feita apenas uma vez
with app.app_context():
    db.create_all()
    # Verificar se já existe um admin antes de criar
    if not User.query.filter_by(username="admin").first():
        admin = User(
            username="admin", 
            password="SenhaComplexaInicial123!",  # Usar o setter que aplica o hash
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)  # Desabilitar debug em produção