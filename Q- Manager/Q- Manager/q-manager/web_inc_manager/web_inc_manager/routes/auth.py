from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import User, db
from utils.security import hash_password, verify_password

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main_menu'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and verify_password(user.password, password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main_menu'))
            
        flash('Usuário ou senha incorretos.')
    else:
        if 'next' in request.args:
            flash('Por favor, faça login para acessar essa página.')

    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/gerenciar_logins', methods=['GET', 'POST'])
@login_required
def gerenciar_logins():
    if not current_user.is_admin:
        flash('Acesso negado.')
        return redirect(url_for('main_menu'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        user_id = request.form.get('user_id')
        user = User.query.get_or_404(user_id)
        
        if action == 'delete' and user.username != current_user.username:
            db.session.delete(user)
            db.session.commit()
            flash('Usuário excluído com sucesso!')
        elif action == 'update':
            new_password = request.form.get('new_password')
            if new_password:
                user.password = hash_password(new_password)
            user.is_admin = 'is_admin' in request.form
            db.session.commit()
            flash('Usuário atualizado com sucesso!')
    
    users = User.query.all()
    return render_template('gerenciar_logins.html', users=users)

@auth_bp.route('/cadastrar_usuario', methods=['GET', 'POST'])
@login_required
def cadastrar_usuario():
    if not current_user.is_admin:
        flash('Acesso negado. Somente administradores podem cadastrar novos usuários.', 'danger')
        return redirect(url_for('main_menu'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        is_admin = 'is_admin' in request.form

        # Verificar se o usuário já existe
        if User.query.filter_by(username=username).first():
            flash('Nome de usuário já existe. Escolha outro.', 'danger')
            return render_template('cadastrar_usuario.html')

        # Criar novo usuário
        new_user = User(
            username=username, 
            password=hash_password(password), 
            is_admin=is_admin
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Usuário cadastrado com sucesso!', 'success')
        return redirect(url_for('auth.gerenciar_logins'))

    return render_template('cadastrar_usuario.html')

@auth_bp.route('/editar_layout', methods=['GET', 'POST'])
@login_required
def editar_layout():
    from models import LayoutSetting
    
    if not current_user.is_admin:
        flash('Acesso negado.')
        return redirect(url_for('main_menu'))
        
    if request.method == 'POST':
        element = request.form['element']
        setting = LayoutSetting.query.filter_by(element=element).first()
        if not setting:
            setting = LayoutSetting(element=element)
            db.session.add(setting)
            
        setting.foreground = request.form['foreground']
        setting.background = request.form['background']
        setting.font_family = request.form['font_family']
        setting.font_size = int(request.form['font_size'])
        db.session.commit()
        flash('Layout atualizado com sucesso!')
        
    settings = {s.element: s for s in LayoutSetting.query.all()}
    return render_template('editar_layout.html', settings=settings)