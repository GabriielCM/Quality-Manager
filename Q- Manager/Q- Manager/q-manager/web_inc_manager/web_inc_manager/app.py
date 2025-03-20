import os
import logging
import matplotlib
matplotlib.use('Agg')  # Use the 'Agg' backend which doesn't require GUI
from flask import Flask, redirect, url_for, render_template, flash, session
from flask_session import Session
from flask_login import LoginManager, current_user, login_required
from werkzeug.security import generate_password_hash

# Importar módulos do aplicativo
from config import Config
from models import db, User
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
db.init_app(app)
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = False

# Configurar login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"

# Assegurar que pasta de uploads existe
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Configurações de logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
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
    return User.query.get(int(user_id))

# Rota principal
@app.route('/')
def index():
    return redirect(url_for('auth.login'))

@app.route('/main_menu')
@login_required
def main_menu():
    # Importar modelos necessários
    from models import INC, RotinaInspecao, Fornecedor
    from datetime import datetime, timedelta
    import json
    
    # Estatísticas para cards
    total_incs_abertas = INC.query.filter_by(status='Em andamento').count()
    total_incs_concluidas = INC.query.filter_by(status='Concluída').count()
    
    # INCs vencidas
    today = datetime.today().date()
    incs = INC.query.all()
    total_incs_vencidas = 0
    
    for inc in incs:
        inc_date = datetime.strptime(inc.data, "%d-%m-%Y").date()
        delta_days = {"leve": 45, "moderada": 20, "crítico": 10}.get(inc.urgencia.lower(), 45)
        expiration_date = inc_date + timedelta(days=delta_days)
        if today > expiration_date:
            total_incs_vencidas += 1
    
    # Total de registros inspecionados (da rotina de inspeção)
    inspections = RotinaInspecao.query.all()
    total_inspecionados = 0
    
    for inspection in inspections:
        registros = json.loads(inspection.registros)
        inspecionados = [r for r in registros if r.get('inspecionado', False)]
        total_inspecionados += len(inspecionados)
    
    # Últimas rotinas de inspeção
    ultimas_rotinas = RotinaInspecao.query.order_by(RotinaInspecao.data_inspecao.desc()).limit(5).all()
    
    # Ranking de fornecedores com mais INCs
    fornecedor_counts = db.session.query(
        INC.fornecedor, 
        db.func.count(INC.id).label('total')
    ).group_by(INC.fornecedor).order_by(db.func.count(INC.id).desc()).limit(5).all()
    
    fornecedor_ranking = [
        {'nome': fornecedor, 'total_incs': total} 
        for fornecedor, total in fornecedor_counts
    ]
    
    # Fornecedores com últimas INCs
    fornecedores_list = Fornecedor.query.all()
    
    for fornecedor in fornecedores_list:
        # Contar INCs para este fornecedor
        fornecedor.total_incs = INC.query.filter_by(fornecedor=fornecedor.razao_social).count()
        
        # Últimas 3 INCs deste fornecedor
        fornecedor.ultimas_incs = INC.query.filter_by(
            fornecedor=fornecedor.razao_social
        ).order_by(INC.id.desc()).limit(3).all()
    
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

# Processador de contexto para injetar configurações
@app.context_processor
def inject_settings():
    from models import LayoutSetting
    settings = {s.element: s for s in LayoutSetting.query.all()}
    return dict(settings=settings, config=app.config)

# Adicionar filtros ao Jinja2
import json as json_lib
app.jinja_env.filters['from_json'] = lambda s: json_lib.loads(s)

def jinja_enumerate(iterable):
    return enumerate(iterable)

app.jinja_env.filters['enumerate'] = jinja_enumerate
app.jinja_env.filters['tojson'] = lambda x: json_lib.dumps(x)

# Inicialização do banco de dados
with app.app_context():
    db.create_all()
    # Verificar se já existe um admin antes de criar
    if not User.query.filter_by(username="admin").first():
        admin = User(
            username="admin", 
            password=generate_password_hash("admin"),
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)