from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_required, current_user
from models import db, RotinaInspecao, InspectionPlan, InspectionActivity, ActivityDenomination, InspectionMethod, INC, Notification, User
from utils import log_user_activity, ler_arquivo_lst
from werkzeug.utils import secure_filename
import os
import json
from datetime import datetime

inspecao_bp = Blueprint('inspecao', __name__, url_prefix='/inspecao')

@inspecao_bp.route('/set_crm_token', methods=['GET', 'POST'])
@login_required
def set_crm_token():
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('rotina_inspecao'):
        flash('Você não tem permissão para acessar esta funcionalidade.', 'danger')
        return redirect(url_for('main_menu'))
        
    if request.method == 'POST':
        crm_link = request.form['crm_link']
        import re
        token_match = re.search(r'token=([a-f0-9]+)', crm_link)
        
        if token_match:
            token = token_match.group(1)
            session['crm_token'] = token
            session['inspecao_crm_token'] = token  # Atualiza o token da inspeção também
            
            # Registrar atualização do token CRM
            log_user_activity(
                user_id=current_user.id,
                action="update",
                entity_type="crm_token",
                details={
                    "token_updated": True,
                    "token_prefix": token[:4] + "..." if token else "none"  # Apenas para referência, não registrar token completo
                }
            )
            
            flash('Token CRM atualizado com sucesso!', 'success')
            return redirect(url_for('inspecao.visualizar_registros_inspecao'))
        else:
            flash('Link CRM inválido. Verifique o link.', 'danger')
            return redirect(url_for('inspecao.visualizar_registros_inspecao'))
    
    return render_template('set_crm_token.html')

@inspecao_bp.route('/api/historico_incs/<path:item>', methods=['GET'])
@login_required
def api_historico_incs(item):
    """API para buscar o histórico de INCs para um item"""
    from flask import current_app
    
    try:
        # Decodificar o item, pois pode conter caracteres especiais
        item = item.upper().strip()
        current_app.logger.info(f"Buscando histórico de INCs para item: {item}")
        
        # Buscar histórico de INCs para este item
        incs = INC.query.filter_by(item=item).order_by(INC.id.desc()).all()
        current_app.logger.info(f"Encontradas {len(incs)} INCs para o item {item}")
        
        # Registrar consulta de histórico do item
        log_user_activity(
            user_id=current_user.id,
            action="query",
            entity_type="item_history",
            details={
                "item": item,
                "count": len(incs)
            }
        )
        
        # Converter para JSON
        incs_json = []
        for inc in incs:
            try:
                # Truncar descrição muito longa
                descricao = inc.descricao_defeito or ""
                descricao_truncada = descricao[:100] + '...' if len(descricao) > 100 else descricao
                
                incs_json.append({
                    'id': inc.id,
                    'nf': inc.nf,
                    'data': inc.data,
                    'representante': inc.representante_nome or "N/A",
                    'fornecedor': inc.fornecedor,
                    'quantidade_recebida': inc.quantidade_recebida,
                    'quantidade_com_defeito': inc.quantidade_com_defeito,
                    'descricao_defeito': descricao_truncada,
                    'urgencia': inc.urgencia,
                    'status': inc.status,
                    'oc': inc.oc
                })
            except Exception as e:
                current_app.logger.error(f"Erro ao processar INC {inc.id}: {str(e)}")
        
        return jsonify({
            'success': True,
            'item': item, 
            'incs': incs_json, 
            'total': len(incs_json)
        })
    except Exception as e:
        current_app.logger.error(f"Erro na API de histórico de INCs: {str(e)}")
        return jsonify({
            'success': False,
            'item': item,
            'incs': [],
            'total': 0,
            'error': str(e)
        }), 500
    
@inspecao_bp.route('/rotina_inspecao', methods=['GET', 'POST'])
@login_required
def rotina_inspecao():
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('rotina_inspecao'):
        flash('Você não tem permissão para acessar esta funcionalidade.', 'danger')
        return redirect(url_for('main_menu'))
        
    # Verificar se o token CRM está definido
    if 'crm_token' not in session:
        flash('Você precisa importar o token do CRM primeiro.', 'warning')
        return redirect(url_for('inspecao.set_crm_token'))
    
    if request.method == 'POST':
        # Verificar se o arquivo foi enviado
        if 'file' not in request.files:
            flash('Nenhum arquivo selecionado', 'danger')
            return redirect(request.url)
        
        file = request.files['file']
        
        # Se nenhum arquivo foi selecionado
        if file.filename == '':
            flash('Nenhum arquivo selecionado', 'danger')
            return redirect(request.url)
        
        # Verificar extensão do arquivo
        if not file.filename.lower().endswith('.lst'):
            flash('Apenas arquivos .lst são permitidos', 'danger')
            return redirect(request.url)
        
        # Salvar o arquivo temporariamente
        from flask import current_app
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            # Analisar o arquivo .lst
            registros = ler_arquivo_lst(filepath)
            
            if registros:
                # Armazenar os registros analisados na sessão
                session['inspecao_registros'] = registros
                # Armazenar o token CRM atual com os registros
                session['inspecao_crm_token'] = session['crm_token']
                
                # Registrar importação da rotina
                log_user_activity(
                    user_id=current_user.id,
                    action="import",
                    entity_type="rotina_inspecao",
                    details={
                        "file": filename,
                        "registros_count": len(registros)
                    }
                )
                
                flash(f'Foram importados {len(registros)} registros.', 'success')
                return redirect(url_for('inspecao.visualizar_registros_inspecao'))
            else:
                flash('Nenhum registro válido foi importado. Verifique o formato do arquivo .lst.', 'warning')
                return redirect(request.url)
        
        except Exception as e:
            flash(f'Erro ao importar arquivo: {str(e)}', 'danger')
            return redirect(request.url)
        finally:
            # Limpar o arquivo temporário
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception as e:
                print(f"Erro ao remover arquivo temporário: {str(e)}")
    
    return render_template('rotina_inspecao.html')

@inspecao_bp.route('/visualizar_registros', methods=['GET', 'POST'])
@login_required
def visualizar_registros_inspecao():
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('rotina_inspecao'):
        flash('Você não tem permissão para acessar esta funcionalidade.', 'danger')
        return redirect(url_for('main_menu'))
        
    registros = session.get('inspecao_registros', [])
    
    if not registros:
        flash('Nenhum registro para inspeção.', 'warning')
        return redirect(url_for('inspecao.rotina_inspecao'))
    
    scroll_position = request.args.get('scroll_position', request.form.get('scroll_position', '0'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        item_index = int(request.form.get('item_index'))
        ar = int(request.form.get('ar'))
        scroll_position = request.form.get('scroll_position', '0')
        
        registros_no_grupo = [r for r in registros if r['num_aviso'] == ar]
        
        if 0 <= item_index < len(registros_no_grupo):
            registro_global_index = registros.index(registros_no_grupo[item_index])
            if action == 'inspecionar':
                registros[registro_global_index]['inspecionado'] = True
                registros[registro_global_index]['adiado'] = False
                
                # Registrar inspeção de item
                log_user_activity(
                    user_id=current_user.id,
                    action="inspect",
                    entity_type="item_inspecao",
                    details={
                        "item": registros[registro_global_index]["item"],
                        "status": "inspecionado",
                        "aviso": ar
                    }
                )
                
                flash(f'Item {registros[registro_global_index]["item"]} marcado como inspecionado.', 'success')
            elif action == 'adiar':
                registros[registro_global_index]['inspecionado'] = False
                registros[registro_global_index]['adiado'] = True
                
                # Registrar adiamento de item
                log_user_activity(
                    user_id=current_user.id,
                    action="inspect",
                    entity_type="item_inspecao",
                    details={
                        "item": registros[registro_global_index]["item"],
                        "status": "adiado",
                        "aviso": ar
                    }
                )
                
                flash(f'Item {registros[registro_global_index]["item"]} marcado como adiado.', 'warning')
            session['inspecao_registros'] = registros
    
    # Agrupar registros por AR
    grupos_ar = {}
    for registro in registros:
        ar = registro['num_aviso']
        if ar not in grupos_ar:
            grupos_ar[ar] = []
        grupos_ar[ar].append(registro)
    
    grupos_ar_ordenados = sorted(grupos_ar.items(), key=lambda x: x[0])
    
    # Passar scroll_position como parâmetro na URL
    return render_template(
        'visualizar_registros_inspecao.html', 
        grupos_ar=grupos_ar_ordenados,
        scroll_position=scroll_position
    )

@inspecao_bp.route('/listar_rotinas')
@login_required
def listar_rotinas_inspecao():
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('rotina_inspecao'):
        flash('Você não tem permissão para acessar esta funcionalidade.', 'danger')
        return redirect(url_for('main_menu'))
        
    rotinas = RotinaInspecao.query.all()
    # Converter registros de JSON para Python para cada rotina
    for rotina in rotinas:
        rotina.registros_python = json.loads(rotina.registros)
    
    # Registrar visualização das rotinas
    log_user_activity(
        user_id=current_user.id,
        action="view",
        entity_type="rotinas_inspecao",
        details={
            "count": len(rotinas)
        }
    )
    
    return render_template('listar_rotinas_inspecao.html', rotinas=rotinas)

@inspecao_bp.route('/salvar_rotina', methods=['POST'])
@login_required
def salvar_rotina_inspecao():
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('rotina_inspecao'):
        flash('Você não tem permissão para realizar esta ação.', 'danger')
        return redirect(url_for('main_menu'))
        
    registros = session.get('inspecao_registros', [])
    
    if not registros:
        flash('Nenhum registro para salvar.', 'warning')
        return redirect(url_for('inspecao.rotina_inspecao'))
    
    # Verificar se todos os registros foram processados
    for registro in registros:
        inspecionado = registro.get('inspecionado', False)
        adiado = registro.get('adiado', False)
        if not inspecionado and not adiado:
            flash('Todos os registros devem ser inspecionados ou adiados antes de salvar a rotina.', 'danger')
            return redirect(url_for('inspecao.visualizar_registros_inspecao'))
    
    # Estatísticas para o log
    inspecionados = sum(1 for r in registros if r.get('inspecionado', False))
    adiados = sum(1 for r in registros if r.get('adiado', False))
    
    rotina = RotinaInspecao(
        inspetor_id=current_user.id,
        registros=json.dumps(registros)
    )
    db.session.add(rotina)
    db.session.commit()
    
    # Registrar a criação da rotina
    log_user_activity(
        user_id=current_user.id,
        action="create",
        entity_type="rotina_inspecao",
        entity_id=rotina.id,
        details={
            "registros_count": len(registros),
            "inspecionados_count": inspecionados,
            "adiados_count": adiados
        }
    )
    
    # Criar notificações para informar sobre a conclusão da rotina de inspeção
    
    # Determinar itens inspecionados para incluir na notificação
    itens_inspecionados = [r.get('item', 'N/A') for r in registros if r.get('inspecionado', False)]
    itens_str = ", ".join(itens_inspecionados[:3])
    if len(itens_inspecionados) > 3:
        itens_str += f" e mais {len(itens_inspecionados) - 3} itens"
    
    # Criar notificação para o próprio inspetor
    notificacao_inspetor = Notification(
        user_id=current_user.id,
        title='Rotina de inspeção concluída',
        message=f'Você concluiu uma rotina de inspeção com {inspecionados} itens inspecionados e {adiados} adiados.',
        category='success',
        entity_type='inspecao',
        entity_id=rotina.id,
        action_text='Visualizar Rotinas'
    )
    db.session.add(notificacao_inspetor)
    
    # Criar notificações para administradores
    administradores = User.query.filter_by(is_admin=True).all()
    for admin in administradores:
        if admin.id != current_user.id:  # Evitar duplicidade
            notificacao_admin = Notification(
                user_id=admin.id,
                title='Nova rotina de inspeção concluída',
                message=f'{current_user.username} concluiu uma inspeção com {len(registros)} itens ({itens_str}).',
                category='update',
                entity_type='inspecao',
                entity_id=rotina.id,
                action_text='Visualizar Rotinas'
            )
            db.session.add(notificacao_admin)
    
    # Encontrar usuários com permissão para rotina de inspeção
    usuarios_com_permissao = User.query.filter(
        User.id != current_user.id,  # Excluir o próprio inspetor
        User.is_admin == False,       # Excluir administradores (já notificados acima)
        User.active == True           # Apenas usuários ativos
    ).all()
    
    for usuario in usuarios_com_permissao:
        if usuario.has_permission('rotina_inspecao'):
            notificacao_usuario = Notification(
                user_id=usuario.id,
                title='Nova rotina de inspeção disponível',
                message=f'Uma nova rotina de inspeção foi concluída por {current_user.username}.',
                category='message',
                entity_type='inspecao',
                entity_id=rotina.id,
                action_text='Visualizar Detalhes'
            )
            db.session.add(notificacao_usuario)
    
    db.session.commit()
    
    flash('Rotina de inspeção salva com sucesso!', 'success')
    session.pop('inspecao_registros', None)
    return redirect(url_for('main_menu'))

# Rotas para o Plano de Inspeção

@inspecao_bp.route('/planos')
@login_required
def listar_planos_inspecao():
    """Lista os planos de inspeção cadastrados"""
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('rotina_inspecao'):
        flash('Acesso negado. Você não tem permissão para acessar esta funcionalidade.', 'danger')
        return redirect(url_for('main_menu'))
    
    planos = InspectionPlan.query.order_by(InspectionPlan.item).all()
    
    # Registrar visualização dos planos
    log_user_activity(
        user_id=current_user.id,
        action="view",
        entity_type="planos_inspecao",
        details={"count": len(planos)}
    )
    
    return render_template('listar_planos_inspecao.html', planos=planos)

@inspecao_bp.route('/novo_plano', methods=['GET', 'POST'])
@login_required
def novo_plano_inspecao():
    """Cria um novo plano de inspeção"""
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('rotina_inspecao'):
        flash('Acesso negado. Você não tem permissão para acessar esta funcionalidade.', 'danger')
        return redirect(url_for('main_menu'))
    
    from utils import validate_item_format
    
    if request.method == 'POST':
        item = request.form['item'].upper()
        
        # Validar o formato do item
        if not validate_item_format(item):
            flash('Formato do item inválido. Deve ser 3 letras maiúsculas, ponto e 5 dígitos, ex: MPR.02199', 'danger')
            return redirect(url_for('inspecao.novo_plano_inspecao'))
        
        # Verificar se é uma atividade existente ou nova
        activity_option = request.form['activity_option']
        
        if activity_option == 'existing':
            activity_id = request.form['activity_id']
            activity = InspectionActivity.query.get_or_404(activity_id)
        else:
            # Criar nova atividade
            activity_name = request.form['new_activity']
            
            if not activity_name:
                flash('Nome da atividade é obrigatório', 'danger')
                return redirect(url_for('inspecao.novo_plano_inspecao'))
            
            # Verificar se já existe
            existing_activity = InspectionActivity.query.filter_by(name=activity_name).first()
            if existing_activity:
                activity = existing_activity
            else:
                activity = InspectionActivity(name=activity_name)
                db.session.add(activity)
                db.session.flush()  # Para obter o ID
        
        # Verificar se é uma denominação existente ou nova
        denomination_option = request.form['denomination_option']
        
        if denomination_option == 'existing':
            denomination_id = request.form['denomination_id']
            denomination = ActivityDenomination.query.get_or_404(denomination_id)
        else:
            # Criar nova denominação
            denomination_name = request.form['new_denomination']
            
            if not denomination_name:
                flash('Nome da denominação é obrigatório', 'danger')
                return redirect(url_for('inspecao.novo_plano_inspecao'))
            
            # Verificar se já existe para esta atividade
            existing_denomination = ActivityDenomination.query.filter_by(
                name=denomination_name, 
                activity_id=activity.id
            ).first()
            
            if existing_denomination:
                denomination = existing_denomination
            else:
                denomination = ActivityDenomination(
                    name=denomination_name,
                    activity_id=activity.id
                )
                db.session.add(denomination)
                db.session.flush()  # Para obter o ID
        
        # Verificar se é um método existente ou novo
        method_option = request.form['method_option']
        
        if method_option == 'existing':
            method_id = request.form['method_id']
            method = InspectionMethod.query.get_or_404(method_id)
        else:
            # Criar novo método
            method_name = request.form['new_method']
            
            if not method_name:
                flash('Nome do método é obrigatório', 'danger')
                return redirect(url_for('inspecao.novo_plano_inspecao'))
            
            # Verificar se já existe
            existing_method = InspectionMethod.query.filter_by(name=method_name).first()
            if existing_method:
                method = existing_method
            else:
                method = InspectionMethod(name=method_name)
                db.session.add(method)
                db.session.flush()  # Para obter o ID
        
        # Verificar se já existe um plano para este item
        existing_plan = InspectionPlan.query.filter_by(item=item).first()
        if existing_plan:
            flash(f'Já existe um plano de inspeção para o item {item}', 'warning')
            return redirect(url_for('inspecao.editar_plano_inspecao', plano_id=existing_plan.id))
        
        # Criar o plano de inspeção
        plano = InspectionPlan(
            item=item,
            activity_id=activity.id,
            denomination_id=denomination.id,
            method_id=method.id,
            created_by=current_user.id
        )
        
        db.session.add(plano)
        db.session.commit()
        
        # Registrar a criação do plano
        log_user_activity(
            user_id=current_user.id,
            action="create",
            entity_type="plano_inspecao",
            entity_id=plano.id,
            details={
                "item": item,
                "activity": activity.name,
                "denomination": denomination.name,
                "method": method.name
            }
        )
        
        flash('Plano de inspeção criado com sucesso!', 'success')
        return redirect(url_for('inspecao.listar_planos_inspecao'))
    
    # Obter dados para os selects
    activities = InspectionActivity.query.all()
    methods = InspectionMethod.query.all()
    
    return render_template('novo_plano_inspecao.html', 
                          activities=activities,
                          methods=methods)

@inspecao_bp.route('/editar_plano/<int:plano_id>', methods=['GET', 'POST'])
@login_required
def editar_plano_inspecao(plano_id):
    """Edita um plano de inspeção existente"""
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('rotina_inspecao'):
        flash('Acesso negado. Você não tem permissão para acessar esta funcionalidade.', 'danger')
        return redirect(url_for('main_menu'))
    
    plano = InspectionPlan.query.get_or_404(plano_id)
    
    if request.method == 'POST':
        # Salvar valores originais para o log
        original_values = {
            'activity_id': plano.activity_id,
            'denomination_id': plano.denomination_id,
            'method_id': plano.method_id
        }
        
        # Verificar se é uma atividade existente ou nova
        activity_option = request.form['activity_option']
        
        if activity_option == 'existing':
            activity_id = request.form['activity_id']
            activity = InspectionActivity.query.get_or_404(activity_id)
        else:
            # Criar nova atividade
            activity_name = request.form['new_activity']
            
            if not activity_name:
                flash('Nome da atividade é obrigatório', 'danger')
                return redirect(url_for('inspecao.editar_plano_inspecao', plano_id=plano_id))
            
            # Verificar se já existe
            existing_activity = InspectionActivity.query.filter_by(name=activity_name).first()
            if existing_activity:
                activity = existing_activity
            else:
                activity = InspectionActivity(name=activity_name)
                db.session.add(activity)
                db.session.flush()  # Para obter o ID
        
        # Verificar se é uma denominação existente ou nova
        denomination_option = request.form['denomination_option']
        
        if denomination_option == 'existing':
            denomination_id = request.form['denomination_id']
            denomination = ActivityDenomination.query.get_or_404(denomination_id)
        else:
            # Criar nova denominação
            denomination_name = request.form['new_denomination']
            
            if not denomination_name:
                flash('Nome da denominação é obrigatório', 'danger')
                return redirect(url_for('inspecao.editar_plano_inspecao', plano_id=plano_id))
            
            # Verificar se já existe para esta atividade
            existing_denomination = ActivityDenomination.query.filter_by(
                name=denomination_name, 
                activity_id=activity.id
            ).first()
            
            if existing_denomination:
                denomination = existing_denomination
            else:
                denomination = ActivityDenomination(
                    name=denomination_name,
                    activity_id=activity.id
                )
                db.session.add(denomination)
                db.session.flush()  # Para obter o ID
        
        # Verificar se é um método existente ou novo
        method_option = request.form['method_option']
        
        if method_option == 'existing':
            method_id = request.form['method_id']
            method = InspectionMethod.query.get_or_404(method_id)
        else:
            # Criar novo método
            method_name = request.form['new_method']
            
            if not method_name:
                flash('Nome do método é obrigatório', 'danger')
                return redirect(url_for('inspecao.editar_plano_inspecao', plano_id=plano_id))
            
            # Verificar se já existe
            existing_method = InspectionMethod.query.filter_by(name=method_name).first()
            if existing_method:
                method = existing_method
            else:
                method = InspectionMethod(name=method_name)
                db.session.add(method)
                db.session.flush()  # Para obter o ID
        
        # Identificar mudanças para o log
        changes = {}
        if activity.id != plano.activity_id:
            changes['activity'] = {
                'old': InspectionActivity.query.get(plano.activity_id).name,
                'new': activity.name
            }
        
        if denomination.id != plano.denomination_id:
            changes['denomination'] = {
                'old': ActivityDenomination.query.get(plano.denomination_id).name,
                'new': denomination.name
            }
        
        if method.id != plano.method_id:
            changes['method'] = {
                'old': InspectionMethod.query.get(plano.method_id).name,
                'new': method.name
            }
        
        # Atualizar o plano
        plano.activity_id = activity.id
        plano.denomination_id = denomination.id
        plano.method_id = method.id
        plano.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Registrar a atualização do plano
        if changes:
            log_user_activity(
                user_id=current_user.id,
                action="update",
                entity_type="plano_inspecao",
                entity_id=plano.id,
                details={
                    "item": plano.item,
                    "changes": changes
                }
            )
        
        flash('Plano de inspeção atualizado com sucesso!', 'success')
        return redirect(url_for('inspecao.listar_planos_inspecao'))
    
    # Obter dados para os selects
    activities = InspectionActivity.query.all()
    denominations = ActivityDenomination.query.filter_by(activity_id=plano.activity_id).all()
    methods = InspectionMethod.query.all()
    
    return render_template('editar_plano_inspecao.html', 
                          plano=plano,
                          activities=activities,
                          denominations=denominations,
                          methods=methods)

@inspecao_bp.route('/excluir_plano/<int:plano_id>', methods=['POST'])
@login_required
def excluir_plano_inspecao(plano_id):
    """Exclui um plano de inspeção"""
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('rotina_inspecao'):
        flash('Acesso negado. Você não tem permissão para acessar esta funcionalidade.', 'danger')
        return redirect(url_for('main_menu'))
    
    plano = InspectionPlan.query.get_or_404(plano_id)
    
    # Registrar a exclusão do plano
    log_user_activity(
        user_id=current_user.id,
        action="delete",
        entity_type="plano_inspecao",
        entity_id=plano.id,
        details={
            "item": plano.item,
            "activity": plano.activity.name,
            "denomination": plano.denomination.name,
            "method": plano.method.name
        }
    )
    
    db.session.delete(plano)
    db.session.commit()
    
    flash('Plano de inspeção excluído com sucesso!', 'success')
    return redirect(url_for('inspecao.listar_planos_inspecao'))

@inspecao_bp.route('/api/denominacoes_por_atividade/<int:activity_id>')
@login_required
def api_denominacoes_por_atividade(activity_id):
    """API para buscar denominações por atividade"""
    denominations = ActivityDenomination.query.filter_by(activity_id=activity_id).all()
    return jsonify({
        'denominations': [{'id': d.id, 'name': d.name} for d in denominations]
    })

@inspecao_bp.route('/api/plano_inspecao/<path:item>')
@login_required
def api_plano_inspecao(item):
    """API para buscar o plano de inspeção para um item"""
    # Decodificar o item, pois pode conter caracteres especiais
    item = item.upper().strip()
    
    # Buscar o plano de inspeção para este item
    plano = InspectionPlan.query.filter_by(item=item).first()
    
    if plano:
        # Verificar se existem INCs para este item
        incs = INC.query.filter_by(item=item).all()
        
        return jsonify({
            'success': True,
            'item': item,
            'has_plan': True,
            'plan': {
                'id': plano.id,
                'activity': plano.activity.name,
                'denomination': plano.denomination.name,
                'method': plano.method.name
            },
            'has_incs': len(incs) > 0,
            'incs_count': len(incs)
        })
    else:
        return jsonify({
            'success': True,
            'item': item,
            'has_plan': False
        })