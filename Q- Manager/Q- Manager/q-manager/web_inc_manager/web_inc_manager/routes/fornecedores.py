from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Fornecedor

fornecedores_bp = Blueprint('fornecedores', __name__)

@fornecedores_bp.route('/gerenciar_fornecedores', methods=['GET', 'POST'])
@login_required
def gerenciar_fornecedores():
    if not current_user.is_admin:
        flash('Acesso negado.')
        return redirect(url_for('main_menu'))

    if request.method == 'POST':
        action = request.form.get('action')
        fornecedor_id = request.form.get('fornecedor_id')
        fornecedor = Fornecedor.query.get_or_404(fornecedor_id) if fornecedor_id else None

        if action == 'delete':
            db.session.delete(fornecedor)
            db.session.commit()
            flash('Fornecedor excluído com sucesso!')
        elif action == 'update':
            fornecedor.razao_social = request.form['razao_social']
            fornecedor.cnpj = request.form['cnpj']
            fornecedor.fornecedor_logix = request.form['fornecedor_logix']
            db.session.commit()
            flash('Fornecedor atualizado com sucesso!!')

    fornecedores = Fornecedor.query.all()
    return render_template('gerenciar_fornecedores.html', fornecedores=fornecedores)

@fornecedores_bp.route('/cadastrar_fornecedor', methods=['GET', 'POST'])
@login_required
def cadastrar_fornecedor():
    if not current_user.is_admin:
        flash('Acesso negado.')
        return redirect(url_for('main_menu'))

    if request.method == 'POST':
        razao_social = request.form['razao_social']
        cnpj = request.form['cnpj']
        fornecedor_logix = request.form['fornecedor_logix']

        # Validação do CNPJ
        if Fornecedor.query.filter_by(cnpj=cnpj).first():
            flash('CNPJ já cadastrado.')
            return render_template('cadastrar_fornecedor.html')

        fornecedor = Fornecedor(
            razao_social=razao_social,
            cnpj=cnpj,
            fornecedor_logix=fornecedor_logix
        )
        db.session.add(fornecedor)
        db.session.commit()
        flash('Fornecedor cadastrado com sucesso!')
        return redirect(url_for('fornecedores.gerenciar_fornecedores'))

    return render_template('cadastrar_fornecedor.html')