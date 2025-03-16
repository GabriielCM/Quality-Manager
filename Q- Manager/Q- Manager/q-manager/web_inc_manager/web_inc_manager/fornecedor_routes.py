from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Fornecedor, INC
from utils import log_user_activity

fornecedor_bp = Blueprint('fornecedor', __name__, url_prefix='/fornecedor')

@fornecedor_bp.route('/api/fornecedor_incs/<int:fornecedor_id>')
@login_required
def fornecedor_incs(fornecedor_id):
    # Buscar o fornecedor
    fornecedor = Fornecedor.query.get_or_404(fornecedor_id)
    
    # Buscar todas as INCs relacionadas a este fornecedor
    incs = INC.query.filter_by(fornecedor=fornecedor.razao_social).order_by(INC.id.desc()).all()
    
    # Registrar a consulta de INCs do fornecedor
    log_user_activity(
        user_id=current_user.id,
        action="view",
        entity_type="fornecedor_incs",
        entity_id=fornecedor_id,
        details={
            "fornecedor": fornecedor.razao_social,
            "total_incs": len(incs)
        }
    )
    
    # Converter para formato JSON
    incs_json = []
    for inc in incs:
        incs_json.append({
            'id': inc.id,
            'nf': inc.nf,
            'data': inc.data,
            'representante': inc.representante_nome,
            'item': inc.item,
            'quantidade_recebida': inc.quantidade_recebida,
            'quantidade_com_defeito': inc.quantidade_com_defeito,
            'descricao_defeito': inc.descricao_defeito,
            'urgencia': inc.urgencia,
            'status': inc.status,
            'oc': inc.oc
        })
    
    return jsonify({
        'fornecedor': {
            'id': fornecedor.id,
            'razao_social': fornecedor.razao_social,
            'cnpj': fornecedor.cnpj,
            'fornecedor_logix': fornecedor.fornecedor_logix
        },
        'incs': incs_json,
        'total': len(incs_json)
    })

@fornecedor_bp.route('/gerenciar_fornecedores', methods=['GET', 'POST'])
@login_required
def gerenciar_fornecedores():
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main_menu'))

    if request.method == 'POST':
        action = request.form.get('action')
        fornecedor_id = request.form.get('fornecedor_id')
        fornecedor = Fornecedor.query.get_or_404(fornecedor_id) if fornecedor_id else None

        if action == 'delete':
            # Registrar a exclusão do fornecedor
            log_user_activity(
                user_id=current_user.id,
                action="delete",
                entity_type="fornecedor",
                entity_id=fornecedor.id,
                details={
                    "razao_social": fornecedor.razao_social,
                    "cnpj": fornecedor.cnpj,
                    "fornecedor_logix": fornecedor.fornecedor_logix
                }
            )
            
            db.session.delete(fornecedor)
            db.session.commit()
            flash('Fornecedor excluído com sucesso!', 'success')
        elif action == 'update':
            # Salvar valores originais para o log
            original_values = {
                'razao_social': fornecedor.razao_social,
                'cnpj': fornecedor.cnpj,
                'fornecedor_logix': fornecedor.fornecedor_logix
            }
            
            # Novos valores
            razao_social = request.form['razao_social']
            cnpj = request.form['cnpj']
            fornecedor_logix = request.form['fornecedor_logix']
            
            # Identificar mudanças para o log
            changes = {}
            if razao_social != fornecedor.razao_social:
                changes['razao_social'] = {'old': fornecedor.razao_social, 'new': razao_social}
            if cnpj != fornecedor.cnpj:
                changes['cnpj'] = {'old': fornecedor.cnpj, 'new': cnpj}
            if fornecedor_logix != fornecedor.fornecedor_logix:
                changes['fornecedor_logix'] = {'old': fornecedor.fornecedor_logix, 'new': fornecedor_logix}
            
            fornecedor.razao_social = razao_social
            fornecedor.cnpj = cnpj
            fornecedor.fornecedor_logix = fornecedor_logix
            
            # Registrar a atualização, apenas se houve mudanças
            if changes:
                log_user_activity(
                    user_id=current_user.id,
                    action="update",
                    entity_type="fornecedor",
                    entity_id=fornecedor.id,
                    details={
                        "changes": changes
                    }
                )
            
            db.session.commit()
            flash('Fornecedor atualizado com sucesso!!', 'success')

    # Buscar todos os fornecedores
    fornecedores = Fornecedor.query.all()
    
    # Adicionar contagem de INCs para cada fornecedor
    for fornecedor in fornecedores:
        fornecedor.total_incs = INC.query.filter_by(fornecedor=fornecedor.razao_social).count()
    
    return render_template('gerenciar_fornecedores.html', fornecedores=fornecedores)

@fornecedor_bp.route('/cadastrar_fornecedor', methods=['GET', 'POST'])
@login_required
def cadastrar_fornecedor():
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main_menu'))

    if request.method == 'POST':
        razao_social = request.form['razao_social']
        cnpj = request.form['cnpj']
        fornecedor_logix = request.form['fornecedor_logix']

        # Validação do CNPJ
        if Fornecedor.query.filter_by(cnpj=cnpj).first():
            flash('CNPJ já cadastrado.', 'danger')
            return render_template('cadastrar_fornecedor.html')

        fornecedor = Fornecedor(
            razao_social=razao_social,
            cnpj=cnpj,
            fornecedor_logix=fornecedor_logix
        )
        db.session.add(fornecedor)
        db.session.commit()
        
        # Registrar a criação do fornecedor
        log_user_activity(
            user_id=current_user.id,
            action="create",
            entity_type="fornecedor",
            entity_id=fornecedor.id,
            details={
                "razao_social": razao_social,
                "cnpj": cnpj,
                "fornecedor_logix": fornecedor_logix
            }
        )
        
        flash('Fornecedor cadastrado com sucesso!', 'success')
        return redirect(url_for('fornecedor.gerenciar_fornecedores'))

    return render_template('cadastrar_fornecedor.html')