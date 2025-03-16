from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from models import db, UserActivityLog, User
from utils import log_user_activity
from datetime import datetime
from io import BytesIO, StringIO
import csv

log_bp = Blueprint('log', __name__, url_prefix='/log')

@log_bp.route('/visualizar')
@login_required
def visualizar_logs_atividade():
    """Visualiza os logs de atividades dos usuários"""
    if not current_user.is_admin:
        flash('Acesso negado. Apenas administradores podem visualizar logs.', 'danger')
        return redirect(url_for('main_menu'))
    
    # Obter parâmetros de filtro
    user_id = request.args.get('user_id', type=int)
    action = request.args.get('action')
    entity_type = request.args.get('entity_type')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    ip_address = request.args.get('ip_address')
    page = request.args.get('page', 1, type=int)
    per_page = 15  # Ou obter da configuração da aplicação
    
    # Construir consulta com filtros
    query = UserActivityLog.query
    
    if user_id:
        query = query.filter_by(user_id=user_id)
    if action:
        query = query.filter_by(action=action)
    if entity_type:
        query = query.filter_by(entity_type=entity_type)
    if ip_address:
        query = query.filter(UserActivityLog.ip_address.like(f'%{ip_address}%'))
    
    # Aplicar filtros de data
    if data_inicio:
        data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d')
        query = query.filter(UserActivityLog.timestamp >= data_inicio_obj)
    if data_fim:
        data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d')
        # Incluir todo o dia final (até 23:59:59)
        data_fim_obj = data_fim_obj.replace(hour=23, minute=59, second=59)
        query = query.filter(UserActivityLog.timestamp <= data_fim_obj)
    
    # Ordenar por data/hora decrescente (mais recentes primeiro)
    query = query.order_by(UserActivityLog.timestamp.desc())
    
    # Paginar resultados
    pagination = query.paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Obter lista de usuários para o filtro
    users = User.query.all()
    
    return render_template('visualizar_logs_atividade.html', 
                          logs=pagination, 
                          users=users)

@log_bp.route('/exportar')
@login_required
def exportar_logs():
    """Exporta os logs para CSV"""
    if not current_user.is_admin:
        flash('Acesso negado. Apenas administradores podem exportar logs.', 'danger')
        return redirect(url_for('main_menu'))
    
    # Obter parâmetros de filtro (igual à visualização)
    user_id = request.args.get('user_id', type=int)
    action = request.args.get('action')
    entity_type = request.args.get('entity_type')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    ip_address = request.args.get('ip_address')
    
    # Construir consulta com filtros
    query = UserActivityLog.query
    
    if user_id:
        query = query.filter_by(user_id=user_id)
    if action:
        query = query.filter_by(action=action)
    if entity_type:
        query = query.filter_by(entity_type=entity_type)
    if ip_address:
        query = query.filter(UserActivityLog.ip_address.like(f'%{ip_address}%'))
    
    # Aplicar filtros de data
    if data_inicio:
        data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d')
        query = query.filter(UserActivityLog.timestamp >= data_inicio_obj)
    if data_fim:
        data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d')
        data_fim_obj = data_fim_obj.replace(hour=23, minute=59, second=59)
        query = query.filter(UserActivityLog.timestamp <= data_fim_obj)
    
    # Ordenar por data/hora decrescente
    logs = query.order_by(UserActivityLog.timestamp.desc()).all()
    
    # Criar CSV em memória
    output = StringIO()
    writer = csv.writer(output)
    
    # Cabeçalho
    writer.writerow(['ID', 'Data/Hora', 'Usuário', 'Ação', 'Tipo Entidade', 'ID Entidade', 
                    'Detalhes', 'Endereço IP'])
    
    # Dados
    for log in logs:
        writer.writerow([
            log.id,
            log.timestamp.strftime('%d/%m/%Y %H:%M:%S'),
            log.user.username,
            log.action,
            log.entity_type,
            log.entity_id,
            log.details,
            log.ip_address
        ])
    
    output.seek(0)
    return send_file(
        BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'logs_atividade_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )