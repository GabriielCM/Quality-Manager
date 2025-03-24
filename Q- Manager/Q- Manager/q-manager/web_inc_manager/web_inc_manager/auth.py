from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, LayoutSetting
from utils import log_user_activity
from datetime import datetime
import json

# Criar o blueprint de autenticação
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main_menu'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and user.verify_password(password):
            login_user(user)
            
            # Registrar login do usuário
            log_user_activity(
                user_id=user.id,
                action="login",
                entity_type="session",
                details={"method": "form_login", "ip": request.remote_addr}
            )
            
            # Atualizar último login
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main_menu'))
        else:
            flash('Usuário ou senha incorretos.', 'danger')
            
            # Registrar tentativa de login malsucedida
            if user:
                log_user_activity(
                    user_id=user.id,
                    action="login_failed",
                    entity_type="session",
                    details={"reason": "invalid_password", "ip": request.remote_addr}
                )
            # Mesmo quando o usuário não existe, podemos registrar a tentativa
            # Isso é útil para detectar varreduras de força bruta
            else:
                # Aqui usamos user_id=1 (admin) como padrão para registrar essa tentativa
                log_user_activity(
                    user_id=1,  # Assumindo que o ID 1 é o admin
                    action="login_failed",
                    entity_type="session",
                    details={"attempted_username": username, "reason": "user_not_found", "ip": request.remote_addr}
                )
    else:
        if 'next' in request.args:
            flash('Por favor, faça login para acessar essa página.', 'warning')

    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    # Registrar logout
    log_user_activity(
        user_id=current_user.id,
        action="logout",
        entity_type="session",
        details={"ip": request.remote_addr}
    )
    
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/gerenciar_logins', methods=['GET', 'POST'])
@login_required
def gerenciar_logins():
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main_menu'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        user_id = request.form.get('user_id')
        user = User.query.get_or_404(user_id)
        
        # Armazenar valores originais para log
        original_values = {
            'email': user.email,
            'is_admin': user.is_admin,
            'is_representante': user.is_representante,
            'permissions': json.loads(user.permissions) if user.permissions else {}
        }
        
        if action == 'delete' and user.username != current_user.username:
            # Verificar se o usuário é um representante em uso
            from models import INC
            incs_com_representante = INC.query.filter_by(representante_id=user.id).count()
            if incs_com_representante > 0:
                flash(f'Não é possível excluir este usuário. Ele é representante em {incs_com_representante} INCs.', 'danger')
            else:
                # Registrar a exclusão
                log_user_activity(
                    user_id=current_user.id,
                    action="delete",
                    entity_type="user",
                    entity_id=user.id,
                    details={
                        "username": user.username,
                        "reason": "user_request"
                    }
                )
                
                db.session.delete(user)
                db.session.commit()
                flash('Usuário excluído com sucesso!', 'success')
        elif action == 'update':
            # Atualizar informações básicas
            email = request.form.get('email')
            is_admin = 'is_admin' in request.form
            is_representante = 'is_representante' in request.form
            
            # Rastrear mudanças para o log
            changes = {}
            if email != user.email:
                changes['email'] = {'old': user.email, 'new': email}
            if is_admin != user.is_admin:
                changes['is_admin'] = {'old': user.is_admin, 'new': is_admin}
            if is_representante != user.is_representante:
                changes['is_representante'] = {'old': user.is_representante, 'new': is_representante}
            
            # Verificar se o email já existe (se fornecido e alterado)
            if email and email != user.email:
                existing_user = User.query.filter_by(email=email).first()
                if existing_user and existing_user.id != user.id:
                    flash('Email já está em uso por outro usuário.', 'danger')
                    return redirect(url_for('auth.gerenciar_logins'))
            
            # Atualizar senha se fornecida
            new_password = request.form.get('new_password')
            if new_password:
                if len(new_password) < 6:
                    flash('A nova senha deve ter pelo menos 6 caracteres.', 'danger')
                    return redirect(url_for('auth.gerenciar_logins'))
                user.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
                changes['password'] = {'old': '********', 'new': '********'}
            
            # Coletar permissões selecionadas
            permissions = {}
            for key in request.form:
                if key.startswith('perm_'):
                    permission_name = key[5:]  # Remove o prefixo 'perm_'
                    permissions[permission_name] = True
            
            # Se for admin, todas as permissões são concedidas automaticamente
            if is_admin:
                # Lista completa de permissões
                all_permissions = ['cadastro_inc', 'visualizar_incs', 'rotina_inspecao', 
                                'prateleira', 'fornecedores', 'faturamento']
                permissions = {perm: True for perm in all_permissions}
            
            # Verificar mudanças nas permissões
            old_permissions = json.loads(user.permissions) if user.permissions else {}
            if permissions != old_permissions:
                changes['permissions'] = {'old': old_permissions, 'new': permissions}
            
            # Atualizar usuário
            user.email = email
            user.is_admin = is_admin
            user.is_representante = is_representante
            user.permissions = json.dumps(permissions)
            
            # Registrar a atualização, apenas se houve mudanças
            if changes:
                log_user_activity(
                    user_id=current_user.id,
                    action="update",
                    entity_type="user",
                    entity_id=user.id,
                    details={
                        "username": user.username,
                        "changes": changes
                    }
                )
            
            db.session.commit()
            flash('Usuário atualizado com sucesso!', 'success')
    
    users = User.query.all()
    
    # Preparar lista de funções do sistema para o formulário de permissões
    system_functions = [
        {'id': 'cadastro_inc', 'name': 'Cadastrar INC'},
        {'id': 'visualizar_incs', 'name': 'Visualizar INCs'},
        {'id': 'rotina_inspecao', 'name': 'Rotina de Inspeção'},
        {'id': 'prateleira', 'name': 'Prateleira Não Conforme'},
        {'id': 'fornecedores', 'name': 'Monitorar Fornecedores'},
        {'id': 'faturamento', 'name': 'Solicitação de Faturamento'},
    ]
    
    # Verificar se há logs para exibir o botão
    from models import UserActivityLog
    has_logs = UserActivityLog.query.limit(1).count() > 0
    
    return render_template('gerenciar_logins.html', users=users, system_functions=system_functions, has_logs=has_logs)

@auth_bp.route('/cadastrar_usuario', methods=['GET', 'POST'])
@login_required
def cadastrar_usuario():
    if not current_user.is_admin:
        flash('Acesso negado. Somente administradores podem cadastrar novos usuários.', 'danger')
        return redirect(url_for('main_menu'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form.get('confirm_password')
        email = request.form.get('email')
        is_admin = 'is_admin' in request.form
        is_representante = 'is_representante' in request.form
        
        # Validações
        if password != confirm_password:
            flash('As senhas não coincidem.', 'danger')
            return render_template('cadastrar_usuario.html')
        
        if len(password) < 6:
            flash('A senha deve ter pelo menos 6 caracteres.', 'danger')
            return render_template('cadastrar_usuario.html')
        
        # Verificar se o usuário já existe
        if User.query.filter_by(username=username).first():
            flash('Nome de usuário já existe. Escolha outro.', 'danger')
            return render_template('cadastrar_usuario.html')
        
        # Verificar se o email já existe (se fornecido)
        if email and User.query.filter_by(email=email).first():
            flash('Email já está em uso. Escolha outro.', 'danger')
            return render_template('cadastrar_usuario.html')
        
        # Coletar permissões selecionadas
        permissions = {}
        for key in request.form:
            if key.startswith('perm_'):
                permission_name = key[5:]  # Remove o prefixo 'perm_'
                permissions[permission_name] = True
        
        # Se for admin, todas as permissões são concedidas automaticamente
        if is_admin:
            # Lista completa de permissões
            all_permissions = ['cadastro_inc', 'visualizar_incs', 'rotina_inspecao', 
                             'prateleira', 'fornecedores', 'faturamento']
            permissions = {perm: True for perm in all_permissions}

        # Criar novo usuário
        new_user = User(
            username=username, 
            password=generate_password_hash(password), 
            email=email,
            is_admin=is_admin,
            is_representante=is_representante,
            permissions=json.dumps(permissions)
        )
        db.session.add(new_user)
        db.session.commit()
        
        # Registrar a criação do usuário
        log_user_activity(
            user_id=current_user.id,
            action="create",
            entity_type="user",
            entity_id=new_user.id,
            details={
                "username": new_user.username,
                "email": email,
                "is_admin": is_admin,
                "is_representante": is_representante,
                "permissions": permissions
            }
        )
        
        flash('Usuário cadastrado com sucesso!', 'success')
        return redirect(url_for('auth.gerenciar_logins'))

    # Preparar lista de funções do sistema para o formulário de permissões
    system_functions = [
        {'id': 'cadastro_inc', 'name': 'Cadastrar INC'},
        {'id': 'visualizar_incs', 'name': 'Visualizar INCs'},
        {'id': 'rotina_inspecao', 'name': 'Rotina de Inspeção'},
        {'id': 'prateleira', 'name': 'Prateleira Não Conforme'},
        {'id': 'fornecedores', 'name': 'Monitorar Fornecedores'},
        {'id': 'faturamento', 'name': 'Solicitação de Faturamento'},
    ]
    
    return render_template('cadastrar_usuario.html', system_functions=system_functions)

@auth_bp.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    if request.method == 'POST':
        # Verificar qual formulário foi enviado
        if 'update_info' in request.form:
            # Atualização de informações gerais
            email = request.form.get('email')
            
            # Atualizar informações gerais
            current_user.email = email
            db.session.commit()
            
            flash('Informações atualizadas com sucesso!', 'success')
            
            # Registrar atividade
            log_user_activity(
                user_id=current_user.id,
                action="update",
                entity_type="user",
                entity_id=current_user.id,
                details={"fields": ["email"]}
            )
            
        elif 'change_password' in request.form:
            # Alteração de senha
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            # Validações
            if not current_password or not new_password or not confirm_password:
                flash('Todos os campos de senha são obrigatórios.', 'danger')
            elif new_password != confirm_password:
                flash('A nova senha e a confirmação não coincidem.', 'danger')
            elif not current_user.verify_password(current_password):
                flash('Senha atual incorreta.', 'danger')
            else:
                # Atualizar senha
                current_user.password = new_password  # Este é o setter que aplica o hash
                db.session.commit()
                
                flash('Senha alterada com sucesso!', 'success')
                
                # Registrar atividade
                log_user_activity(
                    user_id=current_user.id,
                    action="update",
                    entity_type="user",
                    entity_id=current_user.id,
                    details={"fields": ["password"]}
                )
    
    return render_template('perfil.html', user=current_user)

@auth_bp.route('/editar_layout', methods=['GET', 'POST'])
@login_required
def editar_layout():
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main_menu'))
        
    if request.method == 'POST':
        element = request.form['element']
        setting = LayoutSetting.query.filter_by(element=element).first()
        if not setting:
            setting = LayoutSetting(element=element)
            db.session.add(setting)
            
        # Salvar valores originais para log
        original_values = {
            'foreground': setting.foreground,
            'background': setting.background,
            'font_family': setting.font_family,
            'font_size': setting.font_size
        }
        
        # Novos valores
        setting.foreground = request.form['foreground']
        setting.background = request.form['background']
        setting.font_family = request.form['font_family']
        setting.font_size = int(request.form['font_size'])
        
        # Identificar mudanças para o log
        changes = {}
        if setting.foreground != original_values['foreground']:
            changes['foreground'] = {'old': original_values['foreground'], 'new': setting.foreground}
        if setting.background != original_values['background']:
            changes['background'] = {'old': original_values['background'], 'new': setting.background}
        if setting.font_family != original_values['font_family']:
            changes['font_family'] = {'old': original_values['font_family'], 'new': setting.font_family}
        if setting.font_size != original_values['font_size']:
            changes['font_size'] = {'old': original_values['font_size'], 'new': setting.font_size}
        
        # Registrar a atualização, apenas se houve mudanças
        if changes:
            log_user_activity(
                user_id=current_user.id,
                action="update",
                entity_type="layout",
                entity_id=setting.id,
                details={
                    "element": element,
                    "changes": changes
                }
            )
        
        db.session.commit()
        flash('Layout atualizado com sucesso!', 'success')
        
    settings = {s.element: s for s in LayoutSetting.query.all()}
    return render_template('editar_layout.html', settings=settings)