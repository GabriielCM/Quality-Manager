import os
import json
import re
import socket
import logging
import chardet
from datetime import datetime, timedelta
from io import BytesIO
import base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import textwrap  # Para formatar texto em múltiplas linhas no PDF
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session, Response, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import csv
from models import db, User, INC, LayoutSetting, Fornecedor, RotinaInspecao, SolicitacaoFaturamento, ItemSolicitacaoFaturamento, PrateleiraNaoConforme, UserActivityLog, InspectionPlan, InspectionActivity, InspectionMethod, ActivityDenomination
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Assegurar que pasta de uploads existe
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Adicionar filtro from_json ao Jinja2
app.jinja_env.filters['from_json'] = lambda s: json.loads(s)

# Adicionar filtro enumerate ao Jinja2
def jinja_enumerate(iterable):
    return enumerate(iterable)

app.jinja_env.filters['enumerate'] = jinja_enumerate
app.jinja_env.filters['tojson'] = lambda x: json.dumps(x)

# Configurações de logging
logging.basicConfig(level=logging.DEBUG)


# Configurar logging aprimorado
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

# =====================================
# FUNÇÃO DE LOG DE ATIVIDADES DO USUÁRIO
# =====================================

def log_user_activity(user_id, action, entity_type, entity_id=None, details=None):
    """
    Registra uma ação do usuário no sistema
    
    Args:
        user_id (int): ID do usuário que realizou a ação
        action (str): Tipo de ação (login, logout, edit, delete, create, etc.)
        entity_type (str): Tipo de entidade afetada (user, inc, fornecedor, etc.)
        entity_id (int, optional): ID da entidade afetada
        details (dict, optional): Detalhes adicionais da ação
    """
    try:
        # Obter endereço IP do cliente
        ip_address = request.remote_addr
        
        # Converter detalhes para JSON se fornecido
        details_json = None
        if details:
            details_json = json.dumps(details, ensure_ascii=False)
            
        # Criar o registro de log
        log_entry = UserActivityLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details_json,
            ip_address=ip_address
        )
        
        # Adicionar e confirmar no banco de dados
        db.session.add(log_entry)
        db.session.commit()
        
    except Exception as e:
        # Não deixar um erro de log interromper a operação principal
        app.logger.error(f"Erro ao registrar atividade do usuário: {str(e)}")
        db.session.rollback()

# Função para visualizar o conteúdo do arquivo
def display_file_preview(filepath, num_lines=20):
    """Exibe uma prévia do conteúdo do arquivo para depuração"""
    try:
        with open(filepath, 'rb') as f:
            raw_data = f.read()
            encoding = chardet.detect(raw_data)['encoding'] or 'latin-1'
        
        with open(filepath, 'r', encoding=encoding) as file:
            lines = [line.rstrip() for line in file.readlines()[:num_lines]]
            
        app.logger.debug(f"Prévia do arquivo ({encoding}):")
        for i, line in enumerate(lines):
            app.logger.debug(f"{i+1:3d}: {line}")
            
    except Exception as e:
        app.logger.error(f"Erro ao ler prévia do arquivo: {str(e)}")


# =====================================
# FUNÇÕES UTILITÁRIAS
# =====================================

def diagnosticar_linha_lst(line, linha_numero):
    """Diagnostica uma linha do arquivo LST para ajudar na depuração"""
    try:
        app.logger.debug(f"Diagnóstico da linha {linha_numero}:")
        app.logger.debug(f"  Comprimento: {len(line)} caracteres")
        app.logger.debug(f"  Conteúdo: '{line}'")
        
        # Contar espaços iniciais
        espacos_iniciais = len(line) - len(line.lstrip(' '))
        app.logger.debug(f"  Espaços iniciais: {espacos_iniciais}")
        
        # Exibir caracteres posicionalmente (índices)
        posicoes = ""
        for i in range(0, min(130, len(line)), 10):
            posicoes += f"{i:10d}"
        app.logger.debug(f"  Posições: {posicoes}")
        
        # Exibir os primeiros caracteres em detalhes
        chars = ""
        for i in range(min(130, len(line))):
            chars += line[i]
        app.logger.debug(f"  Chars:    {chars}")
        
        # Testar expressões regulares específicas
        item_pattern1 = re.compile(r'\s+([A-Z]{3}\.\d{5})\s+')
        item_pattern2 = re.compile(r'\s{20,}([A-Z]{3}\.\d{5})')
        item_pattern3 = re.compile(r'\s+([A-Z]{3}\.\d{5})\s+(.*?)\s+(\d+(?:\.\d+)*,\d+)\s+\d+,\d+\s+(\d{2}/\d{2}/\d{4})')
        
        m1 = item_pattern1.search(line)
        m2 = item_pattern2.match(line)
        m3 = item_pattern3.search(line)
        
        app.logger.debug(f"  Padrão 1 (r'\\s+([A-Z]{{3}}\\.\\d{{5}})\\s+'): {m1.group(1) if m1 else 'Não corresponde'}")
        app.logger.debug(f"  Padrão 2 (r'\\s{{20,}}([A-Z]{{3}}\\.\\d{{5}})'): {m2.group(1) if m2 else 'Não corresponde'}")
        app.logger.debug(f"  Padrão 3 (completo): {bool(m3)}")
        
        if m3:
            app.logger.debug(f"    Item: {m3.group(1)}")
            app.logger.debug(f"    Descrição: {m3.group(2)}")
            app.logger.debug(f"    Quantidade: {m3.group(3)}")
            app.logger.debug(f"    Data: {m3.group(4)}")
    
    except Exception as e:
        app.logger.error(f"Erro no diagnóstico da linha {linha_numero}: {str(e)}")

def validate_item_format(item):
    """Valida o formato do item - 3 letras maiúsculas, ponto e 5 dígitos"""
    pattern = r'^[A-Z]{3}\.\d{5}$'
    return re.match(pattern, item) is not None

def format_date_for_db(date_str):
    """Converte uma string de data para o formato armazenado no banco"""
    if isinstance(date_str, str):
        # Verifica se o formato é YYYY-MM-DD (do input HTML)
        if len(date_str) == 10 and date_str[4] == '-':
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            return date_obj.strftime('%d-%m-%Y')
        return date_str
    elif isinstance(date_str, datetime):
        return date_str.strftime('%d-%m-%Y')
    return None

def parse_date(date_str):
    """Converte uma string de data para um objeto datetime"""
    if not date_str:
        return None
    try:
        # Tenta formato DD-MM-YYYY
        return datetime.strptime(date_str, '%d-%m-%Y')
    except ValueError:
        try:
            # Tenta formato YYYY-MM-DD
            return datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            return None

def save_file(file, allowed_extensions=None):
    """Salva um arquivo enviado com verificação de segurança"""
    if file.filename == '':
        return None
        
    if allowed_extensions and not file.filename.lower().endswith(tuple(allowed_extensions)):
        return None
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    return f"uploads/{filename}"

def remove_file(filepath):
    """Remove um arquivo com verificação de segurança"""
    if not filepath:
        return False
        
    filename = os.path.basename(filepath)
    full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    if not os.path.realpath(full_path).startswith(
            os.path.realpath(app.config['UPLOAD_FOLDER'])):
        return False
    
    if os.path.exists(full_path):
        os.remove(full_path)
        return True
    return False

def ler_arquivo_lst(caminho):
    """
    Lê o arquivo .lst, filtra e processa os registros.
    """
    registros = []
    
    try:
        # Detectar codificação
        with open(caminho, "rb") as f:
            conteudo = f.read()
        
        # Tente várias codificações se a detecção automática falhar
        possible_encodings = ['utf-8', 'latin1', 'cp1252', 'iso-8859-1']
        encoding = chardet.detect(conteudo)['encoding']
        
        if not encoding or encoding.lower() == 'ascii':
            # Se a detecção falhar ou retornar ASCII, tente outras codificações
            for enc in possible_encodings:
                try:
                    with open(caminho, "r", encoding=enc) as arquivo:
                        # Tenta ler a primeira linha para testar a codificação
                        arquivo.readline()
                    encoding = enc
                    break
                except UnicodeDecodeError:
                    continue
        
        print(f"Usando codificação: {encoding}")
        
        with open(caminho, "r", encoding=encoding) as arquivo:
            for linha in arquivo:
                linha_str = linha.strip()
                if not linha_str:
                    continue
                
                # Dividir por múltiplos espaços
                campos = re.split(r"\s{2,}", linha_str)
                
                # Validar e processar colunas
                if len(campos) < 9:
                    continue
                
                # Consolidar colunas se mais de 9
                while len(campos) > 9:
                    campos[3] = campos[3] + " " + campos[4]
                    del campos[4]
                
                try:
                    data_entrada = campos[0]
                    num_aviso = int(campos[1])
                    
                    # Analisar código do item
                    parts_item = re.split(r"\s+", campos[2], maxsplit=1)
                    item_code = parts_item[1].strip() if len(parts_item) > 1 else parts_item[0].strip()
                    
                    descricao = campos[3]
                    
                    # Analisar quantidade
                    qtd_str = campos[5].replace(",", ".")
                    qtd_recebida = float(qtd_str)
                    
                    # Analisar fornecedor
                    splitted_6 = re.split(r"\s+", campos[6], maxsplit=1)
                    fornecedor = splitted_6[1] if len(splitted_6) == 2 else "DESCONHECIDO"
                    
                    # Analisar O.C.
                    oc_str = campos[-1].strip()
                    oc_int = int(oc_str)
                    
                    # Pular se O.C. é 0
                    if oc_int == 0:
                        continue
                    
                    registro = {
                        "fornecedor": fornecedor,
                        "razao_social": fornecedor,
                        "item": item_code,
                        "descricao": descricao,
                        "num_aviso": num_aviso,
                        "qtd_recebida": qtd_recebida,
                        "inspecionado": False,
                        "adiado": False,
                        "oc_value": oc_int
                    }
                    registros.append(registro)
                
                except Exception as e:
                    print(f"Erro ao processar linha: {linha_str}, Erro: {str(e)}")
                    continue
        
        print(f"Total de registros processados: {len(registros)}")
        return registros
    
    except Exception as e:
        print(f"Erro ao ler o arquivo: {str(e)}")
        return []

# =====================================
# ROTAS DE AUTENTICAÇÃO
# =====================================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main_menu'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
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

@app.route('/logout')
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
    return redirect(url_for('login'))

@app.route('/main_menu')
@login_required
def main_menu():
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
    
    # NOVA SEÇÃO: Últimas rotinas de inspeção
    ultimas_rotinas = RotinaInspecao.query.order_by(RotinaInspecao.data_inspecao.desc()).limit(5).all()
    
    # NOVA SEÇÃO: Ranking de fornecedores com mais INCs
    fornecedor_counts = db.session.query(
        INC.fornecedor, 
        db.func.count(INC.id).label('total')
    ).group_by(INC.fornecedor).order_by(db.func.count(INC.id).desc()).limit(5).all()
    
    fornecedor_ranking = [
        {'nome': fornecedor, 'total_incs': total} 
        for fornecedor, total in fornecedor_counts
    ]
    
    # NOVA SEÇÃO: Fornecedores com últimas INCs
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

# Atualizar no app.py - Rota de gerenciamento de logins modificada
@app.route('/gerenciar_logins', methods=['GET', 'POST'])
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
                    return redirect(url_for('gerenciar_logins'))
            
            # Atualizar senha se fornecida
            new_password = request.form.get('new_password')
            if new_password:
                if len(new_password) < 6:
                    flash('A nova senha deve ter pelo menos 6 caracteres.', 'danger')
                    return redirect(url_for('gerenciar_logins'))
                user.password = generate_password_hash(new_password)
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
    has_logs = UserActivityLog.query.limit(1).count() > 0
    
    return render_template('gerenciar_logins.html', users=users, system_functions=system_functions, has_logs=has_logs)

@app.route('/cadastrar_usuario', methods=['GET', 'POST'])
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
        return redirect(url_for('gerenciar_logins'))

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

#Nova rota para perfil de usuário
@app.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    user = current_user
    
    if request.method == 'POST':
        # Apenas permitir a atualização de senha
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Validações
        if not current_password or not new_password or not confirm_password:
            flash('Todos os campos são obrigatórios.', 'danger')
            return redirect(url_for('perfil'))
        
        # Verificar senha atual
        if not check_password_hash(user.password, current_password):
            flash('Senha atual incorreta.', 'danger')
            
            # Registrar tentativa de alteração de senha malsucedida
            log_user_activity(
                user_id=user.id,
                action="password_change_failed",
                entity_type="user",
                entity_id=user.id,
                details={"reason": "incorrect_current_password"}
            )
            
            return redirect(url_for('perfil'))
        
        # Verificar se as senhas coincidem
        if new_password != confirm_password:
            flash('As senhas não coincidem.', 'danger')
            return redirect(url_for('perfil'))
        
        # Verificar comprimento mínimo da senha
        if len(new_password) < 6:
            flash('A nova senha deve ter pelo menos 6 caracteres.', 'danger')
            return redirect(url_for('perfil'))
        
        # Atualizar senha
        user.password = generate_password_hash(new_password)
        db.session.commit()
        
        # Registrar alteração de senha
        log_user_activity(
            user_id=user.id,
            action="password_change",
            entity_type="user",
            entity_id=user.id,
            details={"self_initiated": True}
        )
        
        flash('Senha atualizada com sucesso!', 'success')
        return redirect(url_for('perfil'))
    
    # Converter permissões de JSON para dicionário Python
    try:
        user_permissions = json.loads(user.permissions) if user.permissions else {}
    except:
        user_permissions = {}
    
    # Preparar lista de funções do sistema para exibir as permissões
    system_functions = [
        {'id': 'cadastro_inc', 'name': 'Cadastrar INC'},
        {'id': 'visualizar_incs', 'name': 'Visualizar INCs'},
        {'id': 'rotina_inspecao', 'name': 'Rotina de Inspeção'},
        {'id': 'prateleira', 'name': 'Prateleira Não Conforme'},
        {'id': 'fornecedores', 'name': 'Monitorar Fornecedores'},
        {'id': 'faturamento', 'name': 'Solicitação de Faturamento'},
    ]
    
    return render_template('perfil.html', user=user, permissions=user_permissions, system_functions=system_functions)

@app.route('/editar_layout', methods=['GET', 'POST'])
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

# =====================================
# ROTAS PARA PRATELEIRA NÃO CONFORME
# =====================================

@app.route('/prateleira_nao_conforme')
@login_required
def listar_prateleira_nao_conforme():
    """Lista os itens da prateleira não conforme"""
    # Verificar se o usuário tem permissão para acessar a página
    if not current_user.is_admin and not current_user.has_permission('prateleira'):
        flash('Acesso negado. Você não tem permissão para acessar esta funcionalidade.', 'danger')
        return redirect(url_for('main_menu'))
    
    # Verificar se há dados na prateleira
    itens = PrateleiraNaoConforme.query.order_by(PrateleiraNaoConforme.item).all()
    
    # Calcular o valor total dos itens (soma das quantidades)
    valor_total = db.session.query(db.func.sum(PrateleiraNaoConforme.quantidade)).scalar() or 0
    
    # Verificar idade dos dados
    dados_antigos = False
    if itens:
        # Usar o registro mais recente como referência
        ultima_atualizacao = db.session.query(db.func.max(PrateleiraNaoConforme.data_importacao)).scalar()
        if ultima_atualizacao:
            delta = datetime.utcnow() - ultima_atualizacao
            dados_antigos = delta.total_seconds() / 3600 > 24  # Mais de 24 horas
    
    # Separar itens por categoria
    itens_recebimento = [item for item in itens if item.tipo_defeito == "Recebimento"]
    itens_producao = [item for item in itens if item.tipo_defeito == "Produção"]
    
    # Registrar visualização da prateleira
    log_user_activity(
        user_id=current_user.id,
        action="view",
        entity_type="prateleira",
        details={
            "items_count": len(itens),
            "recebimento_count": len(itens_recebimento),
            "producao_count": len(itens_producao),
            "valor_total": valor_total
        }
    )
    
    return render_template('prateleira_nao_conforme.html', 
                          itens_recebimento=itens_recebimento,
                          itens_producao=itens_producao,
                          valor_total=valor_total,
                          dados_antigos=dados_antigos,
                          ultima_atualizacao=ultima_atualizacao if 'ultima_atualizacao' in locals() else None)

@app.route('/atualizar_prateleira', methods=['GET', 'POST'])
@login_required
def atualizar_prateleira_nao_conforme():
    """Atualiza a prateleira não conforme importando um novo arquivo LST"""
    # Verificar se o usuário tem permissão para atualizar a prateleira
    if not current_user.is_admin and not current_user.has_permission('prateleira'):
        flash('Acesso negado. Você não tem permissão para atualizar a prateleira.', 'danger')
        return redirect(url_for('main_menu'))
    
    if request.method == 'POST':
        # Verificar se o arquivo foi enviado
        if 'arquivo_lst' not in request.files:
            flash('Nenhum arquivo selecionado', 'danger')
            return redirect(request.url)
        
        arquivo = request.files['arquivo_lst']
        
        # Se nenhum arquivo foi selecionado
        if arquivo.filename == '':
            flash('Nenhum arquivo selecionado', 'danger')
            return redirect(request.url)
        
        # Verificar extensão do arquivo
        if not arquivo.filename.lower().endswith('.lst'):
            flash('Apenas arquivos .lst são permitidos', 'danger')
            return redirect(request.url)
        
        # Salvar o arquivo temporariamente
        filename = secure_filename(arquivo.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        arquivo.save(filepath)
        
        try:
            # Exibir prévia do conteúdo para depuração
            app.logger.info(f"Processando arquivo: {filename}")
            display_file_preview(filepath)
            
            # Limpar os dados antigos
            db.session.query(PrateleiraNaoConforme).delete()
            
            # Processar o arquivo LST - Agora a função retorna também as notificações
            itens_processados, notificacoes_faturamento = processar_arquivo_lst_prateleira(filepath)
            
            if not itens_processados:
                flash('Nenhum item encontrado no arquivo. Verifique se o formato está correto.', 'warning')
                return redirect(request.url)
            
            # Salvar os novos itens no banco
            for item_data in itens_processados:
                item = PrateleiraNaoConforme(**item_data)
                db.session.add(item)
            
            db.session.commit()
            
            # Registrar a atualização da prateleira
            log_user_activity(
                user_id=current_user.id,
                action="update",
                entity_type="prateleira",
                details={
                    "file": filename,
                    "items_count": len(itens_processados)
                }
            )
            
            # Exibir notificações sobre solicitações de faturamento pendentes
            for notificacao in notificacoes_faturamento:
                flash(
                    f'O item {notificacao["item"]} possui uma solicitação de faturamento '
                    f'#{notificacao["solicitacao_numero"]} de {notificacao["data_solicitacao"]} '
                    f'que ainda não foi faturada pelo Recebimento. '
                    f'<a href="{url_for("visualizar_solicitacao_faturamento", solicitacao_id=notificacao["solicitacao_id"])}">Ver solicitação</a>', 
                    'warning'
                )
            
            flash(f'Prateleira não conforme atualizada com sucesso! {len(itens_processados)} itens processados.', 'success')
            return redirect(url_for('listar_prateleira_nao_conforme'))
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Erro ao processar arquivo: {str(e)}", exc_info=True)
            flash(f'Erro ao processar arquivo: {str(e)}', 'danger')
            return redirect(request.url)
        finally:
            # Remover o arquivo temporário
            if os.path.exists(filepath):
                os.remove(filepath)
    
    return render_template('atualizar_prateleira.html')

def processar_arquivo_lst_prateleira(filepath):
    """Processa um arquivo LST e retorna os itens para a prateleira não conforme"""
    itens = []
    notificacoes_faturamento = []  # Lista para armazenar notificações
    
    # Detectar a codificação do arquivo
    with open(filepath, 'rb') as f:
        raw_data = f.read()
        encoding = chardet.detect(raw_data)['encoding'] or 'latin-1'
    
    app.logger.debug(f"Usando codificação: {encoding}")
    
    # Ler o conteúdo do arquivo
    with open(filepath, 'r', encoding=encoding) as file:
        lines = file.readlines()
    
    app.logger.debug(f"Arquivo LST lido com sucesso. Total de linhas: {len(lines)}")
    
    # Abordagem alternativa: processar linhas com base em critérios mais simples
    for i, line in enumerate(lines):
        # Remover quebras de linha e espaços extras
        line = line.rstrip('\n')
        
        # Pular linhas vazias, cabeçalhos e rodapés
        if not line.strip() or "ITEM / LOCAL" in line or "DENOMINACAO DO ITEM" in line or "TOTAL" in line:
            continue
        
        # Verificação simplificada para linhas de item - procurar padrão XXX.NNNNN precedido por espaços
        # Usamos abordagem de índice em vez de regex
        stripped_line = line.strip()
        
        if (len(stripped_line) > 9 and 
            stripped_line[3] == '.' and 
            stripped_line[:3].isalpha() and 
            stripped_line[:3].isupper() and
            stripped_line[4:9].isdigit()):
            
            # Fazer diagnóstico detalhado para as 3 primeiras linhas com itens encontradas
            if len(itens) < 3:
                app.logger.debug(f"Analisando linha {i+1} que parece conter um item")
                diagnosticar_linha_lst(line, i+1)
            
            try:
                # Extrair dados usando um método simplificado
                parts = stripped_line.split()
                
                if len(parts) >= 4:  # Deve ter pelo menos item, partes da descrição, quantidade e data
                    item_code = parts[0]
                    
                    # A data está normalmente no final (último campo)
                    item_date = parts[-1]
                    
                    # Quantidade está tipicamente antes da data, no formato 99,999
                    quantidade_idx = -3  # Considerando: quantidade, 0,000, data
                    quantidade_str = parts[quantidade_idx].replace('.', '').replace(',', '.')
                    
                    try:
                        item_qty = float(quantidade_str)
                    except ValueError:
                        # Tentar encontrar a quantidade olhando para um padrão com vírgula
                        for idx, part in enumerate(parts):
                            if ',' in part and part.replace('.', '').replace(',', '').isdigit():
                                quantidade_str = part.replace('.', '').replace(',', '.')
                                item_qty = float(quantidade_str)
                                quantidade_idx = idx
                                break
                        else:
                            app.logger.warning(f"Não foi possível encontrar quantidade na linha {i+1}")
                            continue
                    
                    # Descrição é tudo entre o código e a quantidade
                    desc_end_idx = quantidade_idx
                    desc_parts = parts[1:desc_end_idx]
                    item_desc = ' '.join(desc_parts)
                    
                    # Validações adicionais
                    if not re.match(r'\d{2}/\d{2}/\d{4}', item_date):
                        app.logger.warning(f"Data inválida na linha {i+1}: {item_date}")
                        continue
                    
                    app.logger.debug(f"Item extraído: código={item_code}, desc={item_desc}, qtd={item_qty}, data={item_date}")
                    
                    # Verificar se existe uma INC em andamento para este item
                    inc = INC.query.filter_by(
                        item=item_code, 
                        status='Em andamento'
                    ).first()
                    
                    # Também verificar se existe uma INC concluída que está em uma solicitação de faturamento
                    inc_concluida = INC.query.filter_by(
                        item=item_code, 
                        status='Concluída'
                    ).first()
                    
                    # Se há uma INC concluída, verificar se ela está em alguma solicitação de faturamento
                    if inc_concluida:
                        solicitacao_item = ItemSolicitacaoFaturamento.query.filter_by(
                            inc_id=inc_concluida.id
                        ).first()
                        
                        if solicitacao_item:
                            # Buscar a solicitação de faturamento completa
                            solicitacao = SolicitacaoFaturamento.query.get(solicitacao_item.solicitacao_id)
                            
                            # Adicionar notificação
                            notificacoes_faturamento.append({
                                'item': item_code,
                                'solicitacao_numero': solicitacao.numero,
                                'solicitacao_id': solicitacao.id,
                                'data_solicitacao': solicitacao.data_criacao.strftime('%d/%m/%Y')
                            })
                    
                    # Verificar correspondência de quantidade
                    inc_match = False
                    if inc:
                        # Tolerância para diferenças de arredondamento
                        tolerancia = 0.01
                        inc_match = abs(inc.quantidade_com_defeito - item_qty) < tolerancia
                    
                    if inc and inc_match:
                        tipo_defeito = "Recebimento"
                        inc_id = inc.id
                        app.logger.debug(f"Item {item_code} associado à INC #{inc.id} (Recebimento)")
                    else:
                        tipo_defeito = "Produção"
                        inc_id = None
                        app.logger.debug(f"Item {item_code} classificado como defeito de Produção")
                    
                    # Adicionar à lista de itens
                    itens.append({
                        'item': item_code,
                        'descricao': item_desc,
                        'quantidade': item_qty,
                        'data_ultima_movimentacao': item_date,
                        'tipo_defeito': tipo_defeito,
                        'inc_id': inc_id
                    })
                else:
                    app.logger.warning(f"Linha {i+1} não tem campos suficientes: {stripped_line}")
            
            except Exception as e:
                app.logger.error(f"Erro ao processar linha {i+1}: {str(e)}")
                app.logger.error(f"Linha com erro: {line}")
    
    app.logger.info(f"Total de itens processados: {len(itens)}")
    
    # Retornar tanto os itens quanto as notificações
    return itens, notificacoes_faturamento

@app.route('/api/atualizar_status_prateleira', methods=['POST'])
@login_required
def api_atualizar_status_prateleira():
    """API para atualizar o status de um item na prateleira (ex: finalizar inspeção)"""
    data = request.json
    if not data or 'item_id' not in data:
        return jsonify({'success': False, 'error': 'Dados incompletos'}), 400
    
    item_id = data.get('item_id')
    novo_status = data.get('status')
    
    try:
        item = PrateleiraNaoConforme.query.get_or_404(item_id)
        
        # Implementar as regras específicas para cada tipo de atualização
        if novo_status == 'finalizar':
            # Se o item tem uma INC associada, marcá-la como concluída
            if item.inc_id:
                inc = INC.query.get(item.inc_id)
                if inc:
                    inc.status = 'Concluída'
                    
                    # Registrar a finalização da INC
                    log_user_activity(
                        user_id=current_user.id,
                        action="update",
                        entity_type="inc",
                        entity_id=inc.id,
                        details={
                            "changes": {
                                "status": {
                                    "old": "Em andamento",
                                    "new": "Concluída"
                                }
                            },
                            "reason": "finalized_from_prateleira"
                        }
                    )
                    
                    db.session.commit()
            
            # Registrar a finalização do item da prateleira
            log_user_activity(
                user_id=current_user.id,
                action="finalize",
                entity_type="prateleira_item",
                entity_id=item.id,
                details={
                    "item": item.item,
                    "quantidade": item.quantidade,
                    "tipo_defeito": item.tipo_defeito,
                    "inc_id": item.inc_id
                }
            )
            
            # Remover o item da prateleira
            db.session.delete(item)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Item removido da prateleira'})
        
        return jsonify({'success': False, 'error': 'Ação não suportada'}), 400
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# =====================================
# ROTAS PARA SOLICITAÇÃO DE FATURAMENTO
# =====================================

@app.route('/solicitacoes_faturamento')
@login_required
def listar_solicitacoes_faturamento():
    """Exibe a lista de solicitações de faturamento"""
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('faturamento'):
        flash('Acesso negado. Você não tem permissão para acessar esta funcionalidade.', 'danger')
        return redirect(url_for('main_menu'))
    
    solicitacoes = SolicitacaoFaturamento.query.order_by(SolicitacaoFaturamento.id.desc()).all()
    
    # Registrar visualização de solicitações
    log_user_activity(
        user_id=current_user.id,
        action="view",
        entity_type="solicitacoes_faturamento",
        details={
            "count": len(solicitacoes)
        }
    )
    
    return render_template('listar_solicitacoes_faturamento.html', solicitacoes=solicitacoes)

@app.route('/nova_solicitacao_faturamento', methods=['GET', 'POST'])
@login_required
def nova_solicitacao_faturamento():
    """Cria uma nova solicitação de faturamento"""
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('faturamento'):
        flash('Acesso negado. Você não tem permissão para acessar esta funcionalidade.', 'danger')
        return redirect(url_for('main_menu'))
    
    if request.method == 'POST':
        try:
            # Obter dados do formulário
            tipo = request.form['tipo']
            fornecedor = request.form['fornecedor']
            volumes = int(request.form['volumes'])
            tipo_frete = request.form['tipo_frete']
            observacoes = request.form.get('observacoes', '')
            
            # Obter INCs selecionadas e quantidades
            incs_ids = request.form.getlist('incs[]')
            quantidades = {}
            
            for inc_id in incs_ids:
                quantidade_key = f'quantidade_{inc_id}'
                if quantidade_key in request.form:
                    quantidades[inc_id] = int(request.form[quantidade_key])
            
            # Validações
            if not incs_ids:
                flash('Selecione pelo menos uma INC', 'danger')
                return redirect(url_for('nova_solicitacao_faturamento'))
            
            if not quantidades:
                flash('Informe as quantidades para as INCs selecionadas', 'danger')
                return redirect(url_for('nova_solicitacao_faturamento'))
                
            # Gerar número sequencial para a solicitação
            ultimo_numero = db.session.query(db.func.max(SolicitacaoFaturamento.numero)).scalar() or 0
            novo_numero = ultimo_numero + 1
            
            # Criar a solicitação
            solicitacao = SolicitacaoFaturamento(
                numero=novo_numero,
                tipo=tipo,
                usuario_id=current_user.id,
                fornecedor=fornecedor,
                volumes=volumes,
                tipo_frete=tipo_frete,
                observacoes=observacoes
            )
            
            db.session.add(solicitacao)
            db.session.flush()  # Para obter o ID da solicitação
            
            # Preparar detalhes para o log
            inc_details = []
            
            # Adicionar itens à solicitação e atualizar status das INCs
            for inc_id in incs_ids:
                inc = INC.query.get(inc_id)
                if inc:
                    quantidade = quantidades.get(inc_id, 0)
                    
                    # Validar quantidade
                    if quantidade <= 0 or quantidade > inc.quantidade_com_defeito:
                        flash(f'Quantidade inválida para o item {inc.item}', 'danger')
                        db.session.rollback()
                        return redirect(url_for('nova_solicitacao_faturamento'))
                    
                    # Adicionar item à solicitação
                    item = ItemSolicitacaoFaturamento(
                        solicitacao_id=solicitacao.id,
                        inc_id=inc.id,
                        quantidade=quantidade
                    )
                    db.session.add(item)
                    
                    # Adicionar detalhes para o log
                    inc_details.append({
                        'inc_id': inc.id,
                        'item': inc.item,
                        'quantidade': quantidade
                    })
                    
                    # Atualizar status da INC para "Concluída"
                    old_status = inc.status
                    inc.status = "Concluída"
                    
                    # Registrar a atualização da INC
                    log_user_activity(
                        user_id=current_user.id,
                        action="update",
                        entity_type="inc",
                        entity_id=inc.id,
                        details={
                            "changes": {
                                "status": {
                                    "old": old_status,
                                    "new": "Concluída"
                                }
                            },
                            "reason": "added_to_faturamento"
                        }
                    )
            
            db.session.commit()
            
            # Registrar a criação da solicitação
            log_user_activity(
                user_id=current_user.id,
                action="create",
                entity_type="solicitacao_faturamento",
                entity_id=solicitacao.id,
                details={
                    "numero": novo_numero,
                    "tipo": tipo,
                    "fornecedor": fornecedor,
                    "volumes": volumes,
                    "tipo_frete": tipo_frete,
                    "incs": inc_details
                }
            )
            
            flash('Solicitação de faturamento criada com sucesso!', 'success')
            return redirect(url_for('visualizar_solicitacao_faturamento', solicitacao_id=solicitacao.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar solicitação: {str(e)}', 'danger')
            return redirect(url_for('nova_solicitacao_faturamento'))
    
    # Processar solicitação GET
    # Buscar fornecedores e INCs em andamento
    fornecedores = Fornecedor.query.all()
    incs = INC.query.filter_by(status='Em andamento').all()
    
    return render_template('nova_solicitacao_faturamento.html', 
                          fornecedores=fornecedores, 
                          incs=incs)

@app.route('/solicitacao_faturamento/<int:solicitacao_id>')
@login_required
def visualizar_solicitacao_faturamento(solicitacao_id):
    """Visualiza os detalhes de uma solicitação de faturamento"""
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('faturamento'):
        flash('Acesso negado. Você não tem permissão para acessar esta funcionalidade.', 'danger')
        return redirect(url_for('main_menu'))
    
    solicitacao = SolicitacaoFaturamento.query.get_or_404(solicitacao_id)
    
    # Registrar visualização de solicitação
    log_user_activity(
        user_id=current_user.id,
        action="view",
        entity_type="solicitacao_faturamento",
        entity_id=solicitacao_id,
        details={
            "numero": solicitacao.numero,
            "fornecedor": solicitacao.fornecedor
        }
    )
    
    return render_template('visualizar_solicitacao_faturamento.html', solicitacao=solicitacao)

@app.route('/exportar_pdf_solicitacao/<int:solicitacao_id>')
@login_required
def exportar_pdf_solicitacao(solicitacao_id):
    """Exporta uma solicitação de faturamento para PDF"""
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('faturamento'):
        flash('Acesso negado. Você não tem permissão para acessar esta funcionalidade.', 'danger')
        return redirect(url_for('main_menu'))
    
    solicitacao = SolicitacaoFaturamento.query.get_or_404(solicitacao_id)
    
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Configurar o título e cabeçalho
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, f"Solicitação de Faturamento #{solicitacao.numero}")
    
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 80, f"Tipo: {solicitacao.tipo}")
    c.drawString(300, height - 80, f"Data: {solicitacao.data_criacao.strftime('%d/%m/%Y')}")
    
    c.drawString(50, height - 100, f"Fornecedor: {solicitacao.fornecedor}")
    c.drawString(50, height - 120, f"Volumes: {solicitacao.volumes}")
    c.drawString(300, height - 120, f"Frete: {solicitacao.tipo_frete}")
    c.drawString(50, height - 140, f"Solicitante: {solicitacao.usuario.username}")
    
    # Desenhar linha separadora
    c.line(50, height - 160, width - 50, height - 160)
    
    # Cabeçalho da tabela de itens
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, height - 180, "Item")
    c.drawString(150, height - 180, "Descrição")
    c.drawString(350, height - 180, "Quantidade")
    c.drawString(450, height - 180, "NF-e")
    
    # Conteúdo da tabela
    c.setFont("Helvetica", 10)
    y = height - 200
    
    for i, item in enumerate(solicitacao.itens):
        if y < 100:  # Nova página se não houver espaço suficiente
            c.showPage()
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, height - 50, f"Solicitação de Faturamento #{solicitacao.numero} (continuação)")
            c.setFont("Helvetica", 10)
            y = height - 80
        
        c.drawString(50, y, item.inc.item)
        
        # Limitar o tamanho da descrição para caber na página
        descricao = item.inc.descricao_defeito
        if len(descricao) > 40:
            descricao = descricao[:37] + "..."
        c.drawString(150, y, descricao)
        
        c.drawString(350, y, str(item.quantidade))
        c.drawString(450, y, str(item.inc.nf))
        
        y -= 20
    
    # Observações
    if solicitacao.observacoes:
        if y < 150:  # Nova página se não houver espaço suficiente
            c.showPage()
            y = height - 50
        
        y -= 40
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "Observações:")
        c.setFont("Helvetica", 10)
        
        # Quebrar observações em múltiplas linhas se necessário
        text_object = c.beginText(50, y - 20)
        text_object.setFont("Helvetica", 10)
        
        observacoes = solicitacao.observacoes
        wrapped_text = textwrap.fill(observacoes, width=80)
        for line in wrapped_text.split('\n'):
            text_object.textLine(line)
        
        c.drawText(text_object)
    
    # Assinaturas
    y = 100
    c.line(50, y, 250, y)
    c.drawString(150 - (c.stringWidth("Assinatura Solicitante") / 2), y - 20, "Assinatura Solicitante")
    
    c.line(350, y, 550, y)
    c.drawString(450 - (c.stringWidth("Assinatura Aprovador") / 2), y - 20, "Assinatura Aprovador")
    
    c.save()
    
    # Registrar exportação do PDF
    log_user_activity(
        user_id=current_user.id,
        action="export",
        entity_type="solicitacao_faturamento_pdf",
        entity_id=solicitacao_id,
        details={
            "numero": solicitacao.numero,
            "format": "pdf"
        }
    )
    
    buffer.seek(0)
    return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=f'solicitacao_faturamento_{solicitacao.numero}.pdf')

@app.route('/api/incs_por_fornecedor/<fornecedor>')
@login_required
def api_incs_por_fornecedor(fornecedor):
    """API para buscar INCs por fornecedor"""
    try:
        incs = INC.query.filter_by(fornecedor=fornecedor, status='Em andamento').all()
        incs_json = []
        
        for inc in incs:
            incs_json.append({
                'id': inc.id,
                'item': inc.item,
                'nf': inc.nf,
                'descricao_defeito': inc.descricao_defeito,
                'quantidade_recebida': inc.quantidade_recebida,
                'quantidade_com_defeito': inc.quantidade_com_defeito,
                'data': inc.data,
                'representante': inc.representante
            })
        
        # Registrar consulta de INCs por fornecedor
        log_user_activity(
            user_id=current_user.id,
            action="query",
            entity_type="incs_fornecedor",
            details={
                "fornecedor": fornecedor,
                "count": len(incs_json)
            }
        )
        
        return jsonify({
            'success': True,
            'incs': incs_json
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# =====================================
# ROTAS DE INC 
# =====================================

@app.route('/cadastro_inc', methods=['GET', 'POST'])
@login_required
def cadastro_inc():
    # Verificar se o usuário tem permissão para cadastrar INC
    if not current_user.is_admin and not current_user.has_permission('cadastro_inc'):
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('main_menu'))
    
    # Buscar representantes (usuários com flag is_representante)
    representantes = User.query.filter_by(is_representante=True).all()
    fornecedores = Fornecedor.query.all()

    if request.method == 'POST':
        nf = int(request.form['nf'])
        representante_id = int(request.form['representante'])
        fornecedor = request.form['fornecedor']
        item = request.form['item'].upper()
        quantidade_recebida = int(request.form['quantidade_recebida'])
        quantidade_com_defeito = int(request.form['quantidade_com_defeito'])
        descricao_defeito = request.form.get('descricao_defeito', '')
        urgencia = request.form.get('urgencia', 'Moderada')
        acao_recomendada = request.form.get('acao_recomendada', '')

        # Obter o representante pelo ID
        representante_user = User.query.get(representante_id)
        if not representante_user:
            flash('Representante inválido.', 'danger')
            return render_template('cadastro_inc.html', representantes=representantes, fornecedores=fornecedores)

        if not validate_item_format(item):
            flash('Formato do item inválido. Deve ser 3 letras maiúsculas, ponto e 5 dígitos, ex: MPR.02199', 'danger')
            return render_template('cadastro_inc.html', representantes=representantes, fornecedores=fornecedores)

        if quantidade_com_defeito > quantidade_recebida:
            flash('Quantidade com defeito não pode ser maior que a quantidade recebida.', 'danger')
            return render_template('cadastro_inc.html', representantes=representantes, fornecedores=fornecedores)

        # Gerar número OC sequencial
        last_inc = INC.query.order_by(INC.oc.desc()).first()
        new_oc = (last_inc.oc + 1) if last_inc and last_inc.oc else 1

        # Capturar fotos, se houver
        fotos = []
        if 'fotos' in request.files:
            files = request.files.getlist('fotos')
            for file in files:
                if file and file.filename:
                    filepath = save_file(file, ['png', 'jpg', 'jpeg', 'gif'])
                    if filepath:
                        fotos.append(filepath)

        # Criar nova INC
        inc = INC(
            nf=nf,
            data=datetime.today().strftime("%d-%m-%Y"),
            representante_id=representante_id,
            representante_nome=representante_user.username,
            fornecedor=fornecedor,
            item=item,
            quantidade_recebida=quantidade_recebida,
            quantidade_com_defeito=quantidade_com_defeito,
            descricao_defeito=descricao_defeito,
            urgencia=urgencia,
            acao_recomendada=acao_recomendada,
            fotos=json.dumps(fotos),
            oc=new_oc,
            status="Em andamento"
        )

        db.session.add(inc)
        db.session.commit()
        
        # Registrar a criação da INC
        log_user_activity(
            user_id=current_user.id,
            action="create",
            entity_type="inc",
            entity_id=inc.id,
            details={
                "nf": nf,
                "item": item,
                "fornecedor": fornecedor,
                "quantidade_com_defeito": quantidade_com_defeito,
                "representante_id": representante_id,
                "urgencia": urgencia,
                "fotos_count": len(fotos)
            }
        )
        
        flash('INC cadastrada com sucesso!', 'success')
        return redirect(url_for('visualizar_incs'))

    return render_template('cadastro_inc.html', representantes=representantes, fornecedores=fornecedores)

@app.route('/visualizar_incs')
@login_required
def visualizar_incs():
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('visualizar_incs'):
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('main_menu'))
    
    # Obter parâmetros de filtro
    nf = request.args.get('nf')
    item = request.args.get('item')
    fornecedor = request.args.get('fornecedor')
    status = request.args.get('status')
    page = request.args.get('page', 1, type=int)
    per_page = app.config.get('ITEMS_PER_PAGE', 10)

    # Construir consulta com filtros
    query = INC.query
    if nf:
        query = query.filter_by(nf=int(nf))
    if item:
        query = query.filter(INC.item.ilike(f'%{item}%'))
    if fornecedor:
        query = query.filter(INC.fornecedor.ilike(f'%{fornecedor}%'))
    if status:
        query = query.filter_by(status=status)

    # Paginar resultados
    pagination = query.order_by(INC.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    incs = pagination.items
    
    # Registrar visualização de INCs (opcional, pode gerar muitos logs)
    # log_user_activity(
    #     user_id=current_user.id,
    #     action="view",
    #     entity_type="inc_list",
    #     details={
    #         "filters": {
    #             "nf": nf,
    #             "item": item,
    #             "fornecedor": fornecedor,
    #             "status": status
    #         },
    #         "page": page,
    #         "results_count": len(incs)
    #     }
    # )

    return render_template('visualizar_incs.html', incs=incs, pagination=pagination)

@app.route('/detalhes_inc/<int:inc_id>')
@login_required
def detalhes_inc(inc_id):
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('visualizar_incs'):
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('main_menu'))
    
    inc = INC.query.get_or_404(inc_id)
    fotos = json.loads(inc.fotos)
    
    # Registrar visualização detalhada de INC
    log_user_activity(
        user_id=current_user.id,
        action="view",
        entity_type="inc",
        entity_id=inc.id,
        details={
            "nf": inc.nf,
            "item": inc.item
        }
    )
    
    return render_template('detalhes_inc.html', inc=inc, fotos=fotos)

@app.route('/editar_inc/<int:inc_id>', methods=['GET', 'POST'])
@login_required
def editar_inc(inc_id):
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('cadastro_inc'):
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('main_menu'))
    
    inc = INC.query.get_or_404(inc_id)
    representantes = ["Gabriel Rodrigues da Silva", "Marcos Vinicius Gomes Teixeira", "Aleksandro Carvalho Leão"]
    fotos = json.loads(inc.fotos) if inc.fotos else []

    if request.method == 'POST':
        # Salvar valores originais para o log
        original_values = {
            'item': inc.item,
            'representante': inc.representante,
            'fornecedor': inc.fornecedor,
            'quantidade_recebida': inc.quantidade_recebida,
            'quantidade_com_defeito': inc.quantidade_com_defeito,
            'descricao_defeito': inc.descricao_defeito,
            'urgencia': inc.urgencia, 
            'acao_recomendada': inc.acao_recomendada,
            'status': inc.status
        }
        
        # Get form data
        item = request.form['item'].upper()
        representante = request.form['representante']
        fornecedor = request.form['fornecedor']
        quantidade_recebida = int(request.form['quantidade_recebida'])
        quantidade_com_defeito = int(request.form['quantidade_com_defeito'])
        descricao_defeito = request.form['descricao_defeito']
        urgencia = request.form['urgencia']
        acao_recomendada = request.form['acao_recomendada']
        status = request.form['status']
        
        # Rastrear mudanças para o log
        changes = {}
        if item != inc.item:
            changes['item'] = {'old': inc.item, 'new': item}
        if representante != inc.representante:
            changes['representante'] = {'old': inc.representante, 'new': representante}
        if fornecedor != inc.fornecedor:
            changes['fornecedor'] = {'old': inc.fornecedor, 'new': fornecedor}
        if quantidade_recebida != inc.quantidade_recebida:
            changes['quantidade_recebida'] = {'old': inc.quantidade_recebida, 'new': quantidade_recebida}
        if quantidade_com_defeito != inc.quantidade_com_defeito:
            changes['quantidade_com_defeito'] = {'old': inc.quantidade_com_defeito, 'new': quantidade_com_defeito}
        if descricao_defeito != inc.descricao_defeito:
            changes['descricao_defeito'] = {'old': inc.descricao_defeito, 'new': descricao_defeito}
        if urgencia != inc.urgencia:
            changes['urgencia'] = {'old': inc.urgencia, 'new': urgencia}
        if acao_recomendada != inc.acao_recomendada:
            changes['acao_recomendada'] = {'old': inc.acao_recomendada, 'new': acao_recomendada}
        if status != inc.status:
            changes['status'] = {'old': inc.status, 'new': status}
        
        # Validate data
        valid = True
        
        if not validate_item_format(item):
            flash('Formato do item inválido. Deve ser 3 letras maiúsculas, ponto e 5 dígitos, ex: MPR.02199', 'danger')
            valid = False
        
        if quantidade_com_defeito > quantidade_recebida:
            flash('Quantidade com defeito não pode ser maior que a quantidade recebida.', 'danger')
            valid = False
        
        if not valid:
            return render_template('editar_inc.html', inc=inc, representantes=representantes, fotos=fotos)
        
        # Update INC data
        inc.representante = representante
        inc.fornecedor = fornecedor
        inc.item = item
        inc.quantidade_recebida = quantidade_recebida
        inc.quantidade_com_defeito = quantidade_com_defeito
        inc.descricao_defeito = descricao_defeito
        inc.urgencia = urgencia
        inc.acao_recomendada = acao_recomendada
        inc.status = status

        # Process new photos
        new_fotos_added = 0
        if 'fotos' in request.files:
            files = request.files.getlist('fotos')
            for file in files:
                if file and file.filename:
                    filepath = save_file(file, ['png', 'jpg', 'jpeg', 'gif'])
                    if filepath:
                        fotos.append(filepath)
                        new_fotos_added += 1

        inc.fotos = json.dumps(fotos)
        
        # Registrar a edição da INC
        if changes or new_fotos_added > 0:
            if new_fotos_added > 0:
                changes['fotos'] = {'action': 'added', 'count': new_fotos_added}
                
            log_user_activity(
                user_id=current_user.id,
                action="update",
                entity_type="inc",
                entity_id=inc.id,
                details={
                    "nf": inc.nf,
                    "item": inc.item,
                    "changes": changes
                }
            )
        
        # Save changes to database
        try:
            db.session.commit()
            flash('INC atualizada com sucesso!', 'success')
            return redirect(url_for('visualizar_incs'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar INC: {str(e)}', 'danger')
            print(f"Error saving INC: {str(e)}")
    
    # GET request - just render the form
    return render_template('editar_inc.html', inc=inc, representantes=representantes, fotos=fotos)

@app.route('/remover_foto_inc/<int:inc_id>/<path:foto>', methods=['POST'])
@login_required
def remover_foto_inc(inc_id, foto):
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('cadastro_inc'):
        flash('Você não tem permissão para realizar esta ação.', 'danger')
        return redirect(url_for('main_menu'))
    
    inc = INC.query.get_or_404(inc_id)
    fotos = json.loads(inc.fotos) if inc.fotos else []
    
    # Normalizar o caminho da foto para comparação
    foto_normalized = foto.replace('\\', '/')
    for i, f in enumerate(fotos):
        f_normalized = f.replace('\\', '/')
        if f_normalized == foto_normalized:
            # Remover da lista
            foto_to_remove = fotos.pop(i)
            
            # Remover o arquivo físico (corrigindo o caminho)
            filename = os.path.basename(foto_to_remove)
            full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            try:
                if os.path.exists(full_path):
                    os.remove(full_path)
                    print(f"Arquivo removido com sucesso: {full_path}")
                else:
                    print(f"Arquivo não encontrado para remoção: {full_path}")
            except Exception as e:
                print(f"Erro ao remover arquivo: {e}")
            
            # Registrar a remoção da foto
            log_user_activity(
                user_id=current_user.id,
                action="delete",
                entity_type="inc_photo",
                entity_id=inc_id,
                details={
                    "foto": foto,
                    "inc_nf": inc.nf,
                    "inc_item": inc.item
                }
            )
            
            break
    
    # Atualizar o campo de fotos na INC
    inc.fotos = json.dumps(fotos)
    db.session.commit()
    
    flash('Foto removida com sucesso!', 'success')
    return redirect(url_for('editar_inc', inc_id=inc_id))

@app.route('/excluir_inc/<int:inc_id>', methods=['POST'])
@login_required
def excluir_inc(inc_id):
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('cadastro_inc'):
        flash('Você não tem permissão para realizar esta ação.', 'danger')
        return redirect(url_for('main_menu'))
    
    inc = INC.query.get_or_404(inc_id)
    
    # Salvar informações para o log antes de excluir
    inc_info = {
        "nf": inc.nf,
        "item": inc.item,
        "fornecedor": inc.fornecedor,
        "data": inc.data,
        "status": inc.status
    }
    
    # Remover fotos associadas
    fotos = json.loads(inc.fotos) if inc.fotos else []
    for foto in fotos:
        remove_file(foto)
    
    # Registrar a exclusão da INC antes de excluí-la
    log_user_activity(
        user_id=current_user.id,
        action="delete",
        entity_type="inc",
        entity_id=inc_id,
        details=inc_info
    )
    
    db.session.delete(inc)
    db.session.commit()
    flash('INC excluída com sucesso!', 'success')
    return redirect(url_for('visualizar_incs'))

@app.route('/expiracao_inc')
@login_required
def expiracao_inc():
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('visualizar_incs'):
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('main_menu'))
    
    incs = INC.query.all()
    today = datetime.today().date()
    vencidas = []
    for inc in incs:
        inc_date = datetime.strptime(inc.data, "%d-%m-%Y").date()
        delta_days = {"leve": 45, "moderada": 20, "crítico": 10}.get(inc.urgencia.lower(), 45)
        expiration_date = inc_date + timedelta(days=delta_days)
        if today > expiration_date:
            days_overdue = (today - expiration_date).days
            vencidas.append((inc, days_overdue))
    
    # Registrar a visualização de INCs vencidas
    log_user_activity(
        user_id=current_user.id,
        action="view",
        entity_type="vencidas",
        details={
            "total_vencidas": len(vencidas)
        }
    )
    
    return render_template('expiracao_inc.html', vencidas=vencidas)

@app.route('/print_inc_label/<int:inc_id>')
@login_required
def print_inc_label(inc_id):
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('cadastro_inc'):
        flash('Você não tem permissão para realizar esta ação.', 'danger')
        return redirect(url_for('main_menu'))
    
    inc = INC.query.get_or_404(inc_id)
    
    # Função para sanitizar texto para ZPL
    def sanitize_for_zpl(text):
        if not text:
            return ""
        
        # Mapeamento de caracteres especiais do português para seus equivalentes ZPL
        special_chars = {
            'á': 'a\x81', 'à': 'a\x85', 'ã': 'a\x83', 'â': 'a\x82', 'ä': 'a\x84',
            'é': 'e\x81', 'è': 'e\x85', 'ê': 'e\x82', 'ë': 'e\x84',
            'í': 'i\x81', 'ì': 'i\x85', 'î': 'i\x82', 'ï': 'i\x84',
            'ó': 'o\x81', 'ò': 'o\x85', 'õ': 'o\x83', 'ô': 'o\x82', 'ö': 'o\x84',
            'ú': 'u\x81', 'ù': 'u\x85', 'û': 'u\x82', 'ü': 'u\x84',
            'ç': 'c\x87', 'Ç': 'C\x87',
            'ñ': 'n\x83', 'Ñ': 'N\x83'
        }
        
        # Substituir caracteres especiais
        for char, zpl_char in special_chars.items():
            text = text.replace(char, zpl_char)
        
        # Remover outros caracteres não-ASCII que não foram mapeados
        text = ''.join(c if ord(c) < 128 or c in ['\x81', '\x82', '\x83', '\x84', '\x85', '\x87'] else '?' for c in text)
        
        return text
    
    # Quebrar texto em linhas com máximo de 40 caracteres
    def format_text_with_linebreaks(text, max_chars=40):
        if not text:
            return ""
        
        # Sanitizar o texto primeiro
        text = sanitize_for_zpl(text)
        
        # Dividir o texto em palavras
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            # Se adicionar esta palavra ultrapassa o limite
            if len(current_line) + len(word) + 1 > max_chars:
                # Adicionar linha atual à lista de linhas
                if current_line:
                    lines.append(current_line)
                # Começar nova linha com esta palavra
                current_line = word
            else:
                # Adicionar palavra à linha atual
                if current_line:
                    current_line += " " + word
                else:
                    current_line = word
        
        # Adicionar a última linha
        if current_line:
            lines.append(current_line)
        
        # Juntar as linhas com quebras de linha ZPL
        return "\\&".join(lines)
    
    # Preparar os dados com quebras de linha e caracteres especiais tratados
    descricao_formatada = format_text_with_linebreaks(inc.descricao_defeito)
    acao_formatada = format_text_with_linebreaks(inc.acao_recomendada)
    
    # Montar o ZPL com layout ajustado
    zpl = f"""^XA
^PW800          ; Largura: 100 mm = 800 pontos (203 DPI)
^LL976          ; Altura: 122 mm = 976 pontos (203 DPI)
^CF0,30         ; Fonte padrão, tamanho 20 pontos
^FO50,50^FDNF-e:^FS
^FO300,50^FD{inc.nf}^FS
^FO50,100^FDData:^FS
^FO300,100^FD{sanitize_for_zpl(inc.data)}^FS
^FO50,150^FDRepresentante:^FS
^FO300,150^FD{sanitize_for_zpl(inc.representante[:20])}^FS    ; Limitar a 20 caracteres
^FO50,200^FDFornecedor:^FS
^FO300,200^FD{sanitize_for_zpl(inc.fornecedor[:20])}^FS      ; Limitar a 20 caracteres
^FO50,250^FDItem:^FS
^FO300,250^FD{sanitize_for_zpl(inc.item)}^FS
^FO50,300^FDQtd. Recebida:^FS
^FO300,300^FD{inc.quantidade_recebida}^FS
^FO50,350^FDQtd. Defeituosa:^FS
^FO300,350^FD{inc.quantidade_com_defeito}^FS
^FO50,400^FDDescricao:^FS
^FO300,400^FB400,6,L,10^FD{descricao_formatada}^FS  ; Bloco de texto com quebra de linha
^FO50,650^FDUrgencia:^FS
^FO300,650^FD{sanitize_for_zpl(inc.urgencia)}^FS
^FO50,720^FDAcao Recomendada:^FS
^FO300,720^FB400,3,L,10^FD{acao_formatada}^FS  ; Bloco de texto com quebra de linha
^FO50,830^FDStatus:^FS
^FO300,830^FD{sanitize_for_zpl(inc.status)}^FS
^XZ"""

    printer_ip = app.config.get('PRINTER_IP', "192.168.1.48")
    printer_port = app.config.get('PRINTER_PORT', 9100)
    
    try:
        logging.debug(f"Tentando conectar a {printer_ip}:{printer_port}")
        logging.debug(f"ZPL a ser enviado: {zpl}")
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)  # Timeout de 5 segundos
            s.connect((printer_ip, printer_port))
            logging.debug("Conexão estabelecida, enviando ZPL")
            # Enviar dados como bytes brutos sem nenhuma codificação adicional
            s.send(zpl.encode('ascii', errors='replace'))
            logging.debug("ZPL enviado com sucesso")
        
        # Registrar impressão de etiqueta
        log_user_activity(
            user_id=current_user.id,
            action="print",
            entity_type="inc_label",
            entity_id=inc.id,
            details={
                "nf": inc.nf,
                "item": inc.item,
                "printer": f"{printer_ip}:{printer_port}"
            }
        )
        
        flash('Etiqueta enviada para impressão!', 'success')
    except socket.error as e:
        logging.error(f"Erro de socket: {str(e)}")
        flash(f'Erro ao imprimir: {str(e)}', 'danger')
    except Exception as e:
        logging.error(f"Erro geral: {str(e)}")
        flash(f'Erro ao imprimir: {str(e)}', 'danger')

    return redirect(url_for('detalhes_inc', inc_id=inc_id))

@app.route('/export_csv')
@login_required
def export_csv():
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('visualizar_incs'):
        flash('Você não tem permissão para exportar dados.', 'danger')
        return redirect(url_for('main_menu'))
        
    incs = INC.query.all()
    output = BytesIO()
    writer = csv.writer(output)
    writer.writerow(['nf', 'data', 'representante', 'fornecedor', 'item', 'quantidade_recebida', 
                     'quantidade_com_defeito', 'descricao_defeito', 'urgencia', 'acao_recomendada', 
                     'status', 'oc'])
    for inc in incs:
        writer.writerow([inc.nf, inc.data, inc.representante, inc.fornecedor, inc.item, 
                         inc.quantidade_recebida, inc.quantidade_com_defeito, inc.descricao_defeito, 
                         inc.urgencia, inc.acao_recomendada, inc.status, inc.oc])
    
    # Registrar exportação
    log_user_activity(
        user_id=current_user.id,
        action="export",
        entity_type="inc_csv",
        details={
            "record_count": len(incs),
            "format": "csv"
        }
    )
    
    output.seek(0)
    return send_file(output, mimetype='text/csv', as_attachment=True, download_name='incs.csv')

@app.route('/export_pdf/<int:inc_id>')
@login_required
def export_pdf(inc_id):
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('visualizar_incs'):
        flash('Você não tem permissão para exportar dados.', 'danger')
        return redirect(url_for('main_menu'))
        
    inc = INC.query.get_or_404(inc_id)
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 50
    c.setFont("Helvetica", 12)
    c.drawString(50, y, f"INC #{inc.oc}")
    y -= 20
    
    details = [
        f"NF-e: {inc.nf}", f"Data: {inc.data}", f"Representante: {inc.representante}",
        f"Fornecedor: {inc.fornecedor}", f"Item: {inc.item}", f"Qtd. Recebida: {inc.quantidade_recebida}",
        f"Qtd. com Defeito: {inc.quantidade_com_defeito}", f"Descrição do Defeito: {inc.descricao_defeito}",
        f"Urgência: {inc.urgencia}", f"Ação Recomendada: {inc.acao_recomendada}", f"Status: {inc.status}"
    ]
    
    for line in details:
        c.drawString(50, y, line)
        y -= 20
        
    fotos = json.loads(inc.fotos)
    if fotos:
        c.showPage()
        x, y = 50, height - 220
        for foto in fotos:
            full_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(foto))
            if os.path.exists(full_path):
                c.drawImage(full_path, x, y, width=200, height=200, preserveAspectRatio=True)
                x += 220
                if x > width - 200:
                    x = 50
                    y -= 220
                    if y < 50:
                        c.showPage()
                        y = height - 220
    c.save()
    
    # Registrar exportação
    log_user_activity(
        user_id=current_user.id,
        action="export",
        entity_type="inc_pdf",
        entity_id=inc.id,
        details={
            "nf": inc.nf,
            "item": inc.item,
            "format": "pdf"
        }
    )
    
    buffer.seek(0)
    return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=f'inc_{inc.nf}.pdf')

@app.route('/monitorar_fornecedores', methods=['GET', 'POST'])
@login_required
def monitorar_fornecedores():
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('fornecedores'):
        flash('Você não tem permissão para acessar esta funcionalidade.', 'danger')
        return redirect(url_for('main_menu'))
        
    fornecedores = Fornecedor.query.all()
    incs = []
    graph_url = None  # Inicializar graph_url como None

    if request.method == 'POST':
        fornecedor = request.form.get('fornecedor')
        item = request.form.get('item')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')

        # Registrar o monitoramento
        log_user_activity(
            user_id=current_user.id,
            action="monitor",
            entity_type="fornecedor",
            details={
                "fornecedor": fornecedor,
                "item": item,
                "period": {
                    "start": start_date,
                    "end": end_date
                }
            }
        )

        # Construir consulta com filtros
        query = INC.query
        if fornecedor:
            query = query.filter_by(fornecedor=fornecedor)
        if item:
            query = query.filter(INC.item.ilike(f'%{item}%'))
        if start_date and end_date:
            start = parse_date(start_date)
            end = parse_date(end_date)
            if start and end:
                start_str = format_date_for_db(start)
                end_str = format_date_for_db(end)
                query = query.filter(INC.data >= start_str, INC.data <= end_str)

        incs = query.all()

        # Preparar dados para o gráfico (mês vs quantidade de INCs) apenas se houver INCs
        if incs:
            graph_data = {}
            for inc in incs:
                month = datetime.strptime(inc.data, '%d-%m-%Y').strftime('%m-%Y')  # Ex.: "03-2025"
                graph_data[month] = graph_data.get(month, 0) + 1

            # Gerar gráfico
            plt.figure(figsize=(10, 6))
            plt.bar(graph_data.keys(), graph_data.values())
            plt.xlabel('Mês de Referência')
            plt.ylabel('Quantidade de INCs')
            plt.title('Monitoramento de Fornecedores')
            plt.xticks(rotation=45)
            plt.tight_layout()

            # Salvar gráfico em memória
            img = BytesIO()
            plt.savefig(img, format='png')
            img.seek(0)
            graph_url = 'data:image/png;base64,' + base64.b64encode(img.getvalue()).decode()
            plt.close()

    return render_template('monitorar_fornecedores.html', fornecedores=fornecedores, incs=incs, graph_url=graph_url)

@app.route('/export_monitor_pdf', methods=['GET'])
@login_required
def export_monitor_pdf():
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('fornecedores'):
        flash('Você não tem permissão para exportar dados.', 'danger')
        return redirect(url_for('main_menu'))
        
    fornecedor = request.args.get('fornecedor')
    item = request.args.get('item')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = INC.query
    if fornecedor:
        query = query.filter_by(fornecedor=fornecedor)
    if item:
        query = query.filter(INC.item.ilike(f'%{item}%'))
    if start_date and end_date:
        start = parse_date(start_date)
        end = parse_date(end_date)
        if start and end:
            start_str = format_date_for_db(start)
            end_str = format_date_for_db(end)
            query = query.filter(INC.data >= start_str, INC.data <= end_str)

    incs = query.all()
    if not incs:
        flash('Nenhum dado para exportar', 'warning')
        return redirect(url_for('monitorar_fornecedores'))

    # Registrar exportação
    log_user_activity(
        user_id=current_user.id,
        action="export",
        entity_type="fornecedor_report",
        details={
            "fornecedor": fornecedor,
            "item": item,
            "period": {
                "start": start_date,
                "end": end_date
            },
            "record_count": len(incs),
            "format": "pdf"
        }
    )

    # Criar arquivo temporário
    temp_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp_graph.png')
    try:
        # Gerar gráfico
        graph_data = {}
        for inc in incs:
            month = datetime.strptime(inc.data, '%d-%m-%Y').strftime('%m-%Y')
            graph_data[month] = graph_data.get(month, 0) + 1

        plt.figure(figsize=(10, 6))
        plt.bar(graph_data.keys(), graph_data.values())
        plt.xlabel('Mês de Referência')
        plt.ylabel('Quantidade de INCs')
        plt.title('Monitoramento de Fornecedores')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(temp_path, format='png')
        plt.close()

        # Gerar PDF
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        y = height - 50

        # Adicionar gráfico ao PDF
        c.drawString(50, y, "Gráfico de Monitoramento")
        y -= 20
        c.drawImage(temp_path, 50, y - 400, width=500, height=400, preserveAspectRatio=True)
        y -= 450

        # Listar INCs
        c.drawString(50, y, "Lista de INCs")
        y -= 20
        for inc in incs:
            text = f"NF-e: {inc.nf}, Data: {inc.data}, Fornecedor: {inc.fornecedor[:20]}, Item: {inc.item}"
            c.drawString(50, y, text)
            y -= 20
            if y < 50:
                c.showPage()
                y = height - 50

        c.save()
        buffer.seek(0)
        
        # Limpar arquivo temporário após uso
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name='monitor_fornecedores.pdf')
    
    finally:
        # Garantir que o arquivo temporário seja removido mesmo em caso de erro
        if os.path.exists(temp_path):
            os.remove(temp_path)

# =====================================
# ROTAS DE FORNECEDORES
# =====================================

@app.route('/api/fornecedor_incs/<int:fornecedor_id>')
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
            'representante': inc.representante,
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

@app.route('/gerenciar_fornecedores', methods=['GET', 'POST'])
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

@app.route('/cadastrar_fornecedor', methods=['GET', 'POST'])
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
        return redirect(url_for('gerenciar_fornecedores'))

    return render_template('cadastrar_fornecedor.html')


# =====================================
# ROTAS PLANO INSPEÇÃO
# =====================================
# Add these routes to app.py

@app.route('/planos_inspecao')
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

@app.route('/novo_plano_inspecao', methods=['GET', 'POST'])
@login_required
def novo_plano_inspecao():
    """Cria um novo plano de inspeção"""
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('rotina_inspecao'):
        flash('Acesso negado. Você não tem permissão para acessar esta funcionalidade.', 'danger')
        return redirect(url_for('main_menu'))
    
    if request.method == 'POST':
        item = request.form['item'].upper()
        
        # Validar o formato do item
        if not validate_item_format(item):
            flash('Formato do item inválido. Deve ser 3 letras maiúsculas, ponto e 5 dígitos, ex: MPR.02199', 'danger')
            return redirect(url_for('novo_plano_inspecao'))
        
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
                return redirect(url_for('novo_plano_inspecao'))
            
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
                return redirect(url_for('novo_plano_inspecao'))
            
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
                return redirect(url_for('novo_plano_inspecao'))
            
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
            return redirect(url_for('editar_plano_inspecao', plano_id=existing_plan.id))
        
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
        return redirect(url_for('listar_planos_inspecao'))
    
    # Obter dados para os selects
    activities = InspectionActivity.query.all()
    methods = InspectionMethod.query.all()
    
    return render_template('novo_plano_inspecao.html', 
                          activities=activities,
                          methods=methods)

@app.route('/editar_plano_inspecao/<int:plano_id>', methods=['GET', 'POST'])
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
                return redirect(url_for('editar_plano_inspecao', plano_id=plano_id))
            
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
                return redirect(url_for('editar_plano_inspecao', plano_id=plano_id))
            
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
                return redirect(url_for('editar_plano_inspecao', plano_id=plano_id))
            
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
        return redirect(url_for('listar_planos_inspecao'))
    
    # Obter dados para os selects
    activities = InspectionActivity.query.all()
    denominations = ActivityDenomination.query.filter_by(activity_id=plano.activity_id).all()
    methods = InspectionMethod.query.all()
    
    return render_template('editar_plano_inspecao.html', 
                          plano=plano,
                          activities=activities,
                          denominations=denominations,
                          methods=methods)

@app.route('/excluir_plano_inspecao/<int:plano_id>', methods=['POST'])
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
    return redirect(url_for('listar_planos_inspecao'))

@app.route('/api/denominacoes_por_atividade/<int:activity_id>')
@login_required
def api_denominacoes_por_atividade(activity_id):
    """API para buscar denominações por atividade"""
    denominations = ActivityDenomination.query.filter_by(activity_id=activity_id).all()
    return jsonify({
        'denominations': [{'id': d.id, 'name': d.name} for d in denominations]
    })

@app.route('/api/plano_inspecao/<path:item>')
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


# =====================================
# ROTAS DE INSPEÇÃO
# =====================================

@app.route('/set_crm_token', methods=['GET', 'POST'])
@login_required
def set_crm_token():
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('rotina_inspecao'):
        flash('Você não tem permissão para acessar esta funcionalidade.', 'danger')
        return redirect(url_for('main_menu'))
        
    if request.method == 'POST':
        crm_link = request.form['crm_link']
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
            return redirect(url_for('visualizar_registros_inspecao'))
        else:
            flash('Link CRM inválido. Verifique o link.', 'danger')
            return redirect(url_for('visualizar_registros_inspecao'))
    
    return render_template('set_crm_token.html')

@app.route('/api/historico_incs/<path:item>', methods=['GET'])
@login_required
def api_historico_incs(item):
    """API para buscar o histórico de INCs para um item"""
    try:
        # Decodificar o item, pois pode conter caracteres especiais
        item = item.upper().strip()
        app.logger.info(f"Buscando histórico de INCs para item: {item}")
        
        # Buscar histórico de INCs para este item
        incs = INC.query.filter_by(item=item).order_by(INC.id.desc()).all()
        app.logger.info(f"Encontradas {len(incs)} INCs para o item {item}")
        
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
                    'representante': inc.representante_nome or inc.representante,
                    'fornecedor': inc.fornecedor,
                    'quantidade_recebida': inc.quantidade_recebida,
                    'quantidade_com_defeito': inc.quantidade_com_defeito,
                    'descricao_defeito': descricao_truncada,
                    'urgencia': inc.urgencia,
                    'status': inc.status,
                    'oc': inc.oc
                })
            except Exception as e:
                app.logger.error(f"Erro ao processar INC {inc.id}: {str(e)}")
        
        return jsonify({
            'success': True,
            'item': item, 
            'incs': incs_json, 
            'total': len(incs_json)
        })
    except Exception as e:
        app.logger.error(f"Erro na API de histórico de INCs: {str(e)}")
        return jsonify({
            'success': False,
            'item': item,
            'incs': [],
            'total': 0,
            'error': str(e)
        }), 500
    
@app.route('/rotina_inspecao', methods=['GET', 'POST'])
@login_required
def rotina_inspecao():
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('rotina_inspecao'):
        flash('Você não tem permissão para acessar esta funcionalidade.', 'danger')
        return redirect(url_for('main_menu'))
        
    # Verificar se o token CRM está definido
    if 'crm_token' not in session:
        flash('Você precisa importar o token do CRM primeiro.', 'warning')
        return redirect(url_for('set_crm_token'))
    
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
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
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
                return redirect(url_for('visualizar_registros_inspecao'))
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

@app.route('/visualizar_registros_inspecao', methods=['GET', 'POST'])
@login_required
def visualizar_registros_inspecao():
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('rotina_inspecao'):
        flash('Você não tem permissão para acessar esta funcionalidade.', 'danger')
        return redirect(url_for('main_menu'))
        
    registros = session.get('inspecao_registros', [])
    
    if not registros:
        flash('Nenhum registro para inspeção.', 'warning')
        return redirect(url_for('rotina_inspecao'))
    
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

@app.route('/listar_rotinas_inspecao')
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

@app.route('/salvar_rotina_inspecao', methods=['POST'])
@login_required
def salvar_rotina_inspecao():
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('rotina_inspecao'):
        flash('Você não tem permissão para realizar esta ação.', 'danger')
        return redirect(url_for('main_menu'))
        
    registros = session.get('inspecao_registros', [])
    
    if not registros:
        flash('Nenhum registro para salvar.', 'warning')
        return redirect(url_for('rotina_inspecao'))
    
    # Verificar se todos os registros foram processados
    for registro in registros:
        inspecionado = registro.get('inspecionado', False)
        adiado = registro.get('adiado', False)
        if not inspecionado and not adiado:
            flash('Todos os registros devem ser inspecionados ou adiados antes de salvar a rotina.', 'danger')
            return redirect(url_for('visualizar_registros_inspecao'))
    
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
    
    flash('Rotina de inspeção salva com sucesso!', 'success')
    session.pop('inspecao_registros', None)
    return redirect(url_for('main_menu'))

# =====================================
# ROTAS PARA LOGS DE ATIVIDADE
# =====================================

@app.route('/visualizar_logs_atividade')
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
    per_page = app.config.get('ITEMS_PER_PAGE', 15)
    
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

@app.route('/exportar_logs')
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

# =====================================
# API ENDPOINTS
# =====================================

@app.route('/api/update_inc_status/<int:inc_id>', methods=['POST'])
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

@app.route('/api/notifications', methods=['GET'])
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
            'link': '/expiracao_inc'
        })
    
    # Retornar dados como JSON
    return jsonify({'notifications': notifications})

# =====================================
# PROCESSOR E INICIALIZAÇÃO
# =====================================

@app.context_processor
def inject_settings():
    settings = {s.element: s for s in LayoutSetting.query.all()}
    return dict(settings=settings, config=app.config)

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