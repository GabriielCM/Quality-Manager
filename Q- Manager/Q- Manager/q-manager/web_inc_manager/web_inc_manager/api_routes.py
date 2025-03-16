from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from models import db, INC
from utils import log_user_activity
from datetime import datetime, timedelta

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
    
    return jsonify({
        'success': True, 
        'inc_id': inc.id,
        'inc_oc': inc.oc,
        'new_status': new_status
    })

@api_bp.route('/notifications', methods=['GET'])
@login_required
def get_notifications():
    # Verificar INCs vencidas
    today = datetime.today().date()
    incs = INC.query.all()
    vencidas = []
    
    for inc in incs:
        inc_date = datetime.strptime(inc.data, "%d-%m-%Y").date()
        delta_days = {"leve": 45, "moderada": 20, "crítico": 10}.get(inc.urgencia.lower(), 45)
        expiration_date = inc_date + timedelta(days=delta_days)
        
        # INCs próximas do vencimento (faltando 3 dias)
        days_to_expire = (expiration_date - today).days
        if 0 < days_to_expire <= 3:
            vencidas.append({
                'id': inc.id,
                'oc': inc.oc,
                'days': days_to_expire
            })
    
    # Preparar notificações
    notifications = []
    
    # Notificação para INCs vencendo
    if vencidas:
        notifications.append({
            'id': 'exp_' + str(int(datetime.now().timestamp())),
            'type': 'warning',
            'title': 'INCs próximas ao vencimento',
            'message': f'Você tem {len(vencidas)} INCs que vencem em menos de 3 dias',
            'time': datetime.now().isoformat(),
            'read': False,
            'link': '/inc/expiracao_inc'
        })
    
    # Retornar dados como JSON
    return jsonify({'notifications': notifications})