import os
import sqlite3
import json
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import db, User, INC, RotinaInspecao, Fornecedor, PrateleiraNaoConforme, SolicitacaoFaturamento, ItemSolicitacaoFaturamento
from utils import log_user_activity

migration_bp = Blueprint('migration', __name__, url_prefix='/migration')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'db'

@migration_bp.route('/', methods=['GET'])
@login_required
def index():
    """
    Página inicial da interface de migração de banco de dados
    """
    if not current_user.is_admin:
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('main_menu'))
    
    return render_template('migration/index.html')

@migration_bp.route('/upload', methods=['POST'])
@login_required
def upload_database():
    """
    Recebe o upload do banco de dados antigo e armazena temporariamente
    """
    if not current_user.is_admin:
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('main_menu'))
    
    if 'db_file' not in request.files:
        flash('Nenhum arquivo selecionado', 'danger')
        return redirect(url_for('migration.index'))
    
    db_file = request.files['db_file']
    
    if db_file.filename == '':
        flash('Nenhum arquivo selecionado', 'danger')
        return redirect(url_for('migration.index'))
    
    if db_file and allowed_file(db_file.filename):
        filename = secure_filename(db_file.filename)
        temp_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'temp_' + filename)
        db_file.save(temp_path)
        
        # Analisar o banco de dados e extrair as informações das tabelas
        try:
            db_info = analyze_database(temp_path)
            return render_template('migration/preview.html', db_info=db_info, db_path=temp_path)
        except Exception as e:
            flash(f'Erro ao analisar o banco de dados: {str(e)}', 'danger')
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return redirect(url_for('migration.index'))
    else:
        flash('Formato de arquivo inválido. Por favor, envie um arquivo .db', 'danger')
        return redirect(url_for('migration.index'))

def analyze_database(db_path):
    """
    Analisa o banco de dados e retorna informações sobre as tabelas
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Obter lista de tabelas
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row['name'] for row in cursor.fetchall()]
    
    db_info = {}
    for table in tables:
        # Ignorar tabelas do sistema
        if table.startswith('sqlite_'):
            continue
        
        # Obter contagem de registros
        cursor.execute(f"SELECT COUNT(*) as count FROM {table};")
        count = cursor.fetchone()['count']
        
        # Obter estrutura da tabela
        cursor.execute(f"PRAGMA table_info({table});")
        columns = [dict(row) for row in cursor.fetchall()]
        
        # Obter uma amostra dos dados
        cursor.execute(f"SELECT * FROM {table} LIMIT 3;")
        sample_data = [dict(row) for row in cursor.fetchall()]
        
        db_info[table] = {
            'count': count,
            'columns': columns,
            'sample': sample_data
        }
    
    conn.close()
    return db_info

@migration_bp.route('/migrate', methods=['POST'])
@login_required
def migrate_database():
    """
    Realiza a migração dos dados do banco de dados antigo para o atual
    """
    if not current_user.is_admin:
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('main_menu'))
    
    db_path = request.form.get('db_path')
    selected_tables = request.form.getlist('tables')
    
    if not db_path or not os.path.exists(db_path):
        flash('Arquivo de banco de dados não encontrado', 'danger')
        return redirect(url_for('migration.index'))
    
    if not selected_tables:
        flash('Nenhuma tabela selecionada para migração', 'warning')
        return redirect(url_for('migration.index'))
    
    try:
        results = perform_migration(db_path, selected_tables)
        
        # Registrar a atividade de migração
        details = {
            'migrated_tables': selected_tables,
            'results': results
        }
        log_user_activity(
            user_id=current_user.id,
            action='database_migration',
            entity_type='system',
            entity_id=None,
            details=json.dumps(details)
        )
        
        # Remover arquivo temporário após a migração
        if os.path.exists(db_path):
            os.remove(db_path)
        
        flash('Migração concluída com sucesso!', 'success')
        return render_template('migration/results.html', results=results)
    
    except Exception as e:
        flash(f'Erro durante a migração: {str(e)}', 'danger')
        return redirect(url_for('migration.index'))

def perform_migration(db_path, selected_tables):
    """
    Realiza a migração efetiva dos dados para o banco atual
    """
    source_conn = sqlite3.connect(db_path)
    source_conn.row_factory = sqlite3.Row
    source_cursor = source_conn.cursor()
    
    results = {}
    
    for table in selected_tables:
        try:
            source_cursor.execute(f"SELECT * FROM {table};")
            rows = source_cursor.fetchall()
            count = len(rows)
            
            # Migrar dados para o modelo correspondente
            migrated = 0
            errors = 0
            
            if table == 'user':
                for row in rows:
                    try:
                        user_data = dict(row)
                        existing_user = User.query.filter_by(username=user_data['username']).first()
                        
                        if not existing_user:
                            new_user = User(
                                username=user_data['username'],
                                email=user_data.get('email'),
                                is_admin=bool(user_data.get('is_admin', 0)),
                                is_representante=bool(user_data.get('is_representante', 0)),
                                permissions=user_data.get('permissions', '{}'),
                                active=bool(user_data.get('active', 1))
                            )
                            
                            # Definir senha se o campo password_hash existir
                            if 'password_hash' in user_data:
                                new_user.password_hash = user_data['password_hash']
                            
                            db.session.add(new_user)
                            migrated += 1
                    except Exception as e:
                        errors += 1
                        current_app.logger.error(f"Erro ao migrar usuário: {str(e)}")
            
            elif table == 'inc':
                for row in rows:
                    try:
                        inc_data = dict(row)
                        existing_inc = INC.query.filter_by(oc=inc_data['oc']).first()
                        
                        if not existing_inc:
                            new_inc = INC(
                                nf=inc_data['nf'],
                                data=inc_data['data'],
                                representante_id=inc_data['representante_id'],
                                representante_nome=inc_data['representante_nome'],
                                fornecedor=inc_data['fornecedor'],
                                item=inc_data['item'],
                                quantidade_recebida=inc_data['quantidade_recebida'],
                                quantidade_com_defeito=inc_data['quantidade_com_defeito'],
                                descricao_defeito=inc_data.get('descricao_defeito'),
                                urgencia=inc_data['urgencia'],
                                acao_recomendada=inc_data.get('acao_recomendada'),
                                fotos=inc_data.get('fotos'),
                                oc=inc_data['oc'],
                                status=inc_data['status'],
                                concessao_data=inc_data.get('concessao_data')
                            )
                            db.session.add(new_inc)
                            migrated += 1
                    except Exception as e:
                        errors += 1
                        current_app.logger.error(f"Erro ao migrar INC: {str(e)}")
            
            # Adicionar outros modelos conforme necessário...
            
            db.session.commit()
            results[table] = {
                'total': count,
                'migrated': migrated,
                'errors': errors
            }
        
        except Exception as e:
            results[table] = {
                'error': str(e)
            }
            db.session.rollback()
    
    source_conn.close()
    return results 