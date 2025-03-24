from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from models import db, INC, RotinaInspecao, Fornecedor, UserActivityLog, Notification, User
from utils import log_user_activity
from datetime import datetime, timedelta
import uuid

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/update_inc_status/<int:inc_id>', methods=['POST'])
@login_required
def update_inc_status(inc_id):
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('cadastro_inc'):
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    
    inc = INC.query.get_or_404(inc_id)
    
    # Obter dados da solicitação
    data = request.json
    new_status = data.get('status')
    
    if not new_status:
        return jsonify({'success': False, 'error': 'Status não fornecido'}), 400
    
    # Registrar o status original para o log
    old_status = inc.status
    
    # Atualizar status da INC
    inc.status = new_status
    db.session.commit()
    
    # Registrar a atualização de status
    log_user_activity(
        user_id=current_user.id,
        action="update",
        entity_type="inc_status",
        entity_id=inc.id,
        details={
            "changes": {
                "status": {
                    "old": old_status,
                    "new": new_status
                }
            },
            "method": "api"
        }
    )
    
    # Criar notificação para o representante e para os administradores
    
    # Determinar categoria e mensagem baseado no novo status
    category = 'update'
    message = f'Status da INC {inc.item} alterado de "{old_status}" para "{new_status}"'
    
    if new_status == 'Concluído':
        category = 'task'
        message = f'INC {inc.item} foi concluída!'
        title = f'INC {inc.item} concluída'
    elif new_status == 'Cancelado':
        category = 'alert'
        message = f'INC {inc.item} foi cancelada'
        title = f'INC {inc.item} cancelada'
    else:
        title = f'Status da INC {inc.item} atualizado'
    
    # Notificação para o representante
    notification = Notification(
        user_id=inc.representante_id,
        title=title,
        message=message,
        category=category,
        entity_type='inc',
        entity_id=inc.id,
        action_text='Visualizar INC'
    )
    db.session.add(notification)
    
    # Notificação para administradores
    admins = User.query.filter_by(is_admin=True).all()
    for admin in admins:
        if admin.id != current_user.id and admin.id != inc.representante_id:  # Evitar duplicatas
            admin_notification = Notification(
                user_id=admin.id,
                title=title,
                message=message,
                category=category,
                entity_type='inc',
                entity_id=inc.id,
                action_text='Visualizar INC'
            )
            db.session.add(admin_notification)
    
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'inc_id': inc.id,
        'inc_oc': inc.oc,
        'new_status': new_status
    })

@api_bp.route('/notifications', methods=['GET'])
@login_required
def get_notifications():
    # Em vez de verificar diretamente por INCs pendentes, 
    # vamos buscar notificações no banco de dados do usuário atual
    
    notifications = Notification.query\
        .filter(Notification.user_id == current_user.id)\
        .order_by(Notification.created_at.desc())\
        .limit(15)\
        .all()
    
    result = []
    for notification in notifications:
        notification_data = {
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'read': notification.read,
            'category': notification.category,
            'timestamp': notification.created_at.isoformat(),
        }
        
        # Adicionar actionUrl e actionText, se disponíveis
        if notification.action_url:
            notification_data['actionUrl'] = notification.action_url
            
        if notification.action_text:
            notification_data['actionText'] = notification.action_text
            
        result.append(notification_data)
    
    return jsonify(result)

@api_bp.route('/notificacoes', methods=['GET'])
@login_required
def get_notificacoes():
    # Alias em português para a mesma funcionalidade
    return get_notifications()

@api_bp.route('/notificacoes/marcar-lida', methods=['POST'])
@login_required
def mark_notification_read():
    data = request.json
    notification_id = data.get('id')
    
    if not notification_id:
        return jsonify({'success': False, 'error': 'ID da notificação não fornecido'}), 400
    
    notification = Notification.query.get(notification_id)
    
    if not notification:
        return jsonify({'success': False, 'error': 'Notificação não encontrada'}), 404
        
    # Verificar se a notificação pertence ao usuário atual
    if notification.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    
    notification.read = True
    db.session.commit()
    
    return jsonify({'success': True})

@api_bp.route('/notificacoes/marcar-todas-lidas', methods=['POST'])
@login_required
def mark_all_notifications_read():
    Notification.query\
        .filter(Notification.user_id == current_user.id, Notification.read == False)\
        .update({Notification.read: True})
    
    db.session.commit()
    
    return jsonify({'success': True})