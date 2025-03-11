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
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session, Response, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import csv
from models import db, User, INC, LayoutSetting, Fornecedor, RotinaInspecao
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

# =====================================
# FUNÇÕES UTILITÁRIAS
# =====================================

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
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main_menu'))
        else:
            flash('Usuário ou senha incorretos.', 'danger')
    else:
        if 'next' in request.args:
            flash('Por favor, faça login para acessar essa página.', 'warning')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
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
    
    return render_template('main_menu.html',
                          total_incs_abertas=total_incs_abertas,
                          total_incs_concluidas=total_incs_concluidas,
                          total_incs_vencidas=total_incs_vencidas,
                          total_inspecionados=total_inspecionados,
                          ultimas_rotinas=ultimas_rotinas,
                          fornecedor_ranking=fornecedor_ranking,
                          fornecedores=fornecedores_list)

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
        
        if action == 'delete' and user.username != current_user.username:
            db.session.delete(user)
            db.session.commit()
            flash('Usuário excluído com sucesso!', 'success')
        elif action == 'update':
            new_password = request.form.get('new_password')
            if new_password:
                user.password = generate_password_hash(new_password)
            user.is_admin = 'is_admin' in request.form
            db.session.commit()
            flash('Usuário atualizado com sucesso!', 'success')
    
    users = User.query.all()
    return render_template('gerenciar_logins.html', users=users)

@app.route('/cadastrar_usuario', methods=['GET', 'POST'])
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
            password=generate_password_hash(password), 
            is_admin=is_admin
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Usuário cadastrado com sucesso!', 'success')
        return redirect(url_for('gerenciar_logins'))

    return render_template('cadastrar_usuario.html')

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
            
        setting.foreground = request.form['foreground']
        setting.background = request.form['background']
        setting.font_family = request.form['font_family']
        setting.font_size = int(request.form['font_size'])
        db.session.commit()
        flash('Layout atualizado com sucesso!', 'success')
        
    settings = {s.element: s for s in LayoutSetting.query.all()}
    return render_template('editar_layout.html', settings=settings)

# =====================================
# ROTAS DE INC 
# =====================================

@app.route('/cadastro_inc', methods=['GET', 'POST'])
@login_required
def cadastro_inc():
    representantes = ["Gabriel Rodrigues da Silva", "Marcos Vinicius Gomes Teixeira", "Aleksandro Carvalho Leão"]
    fornecedores = Fornecedor.query.all()

    if request.method == 'POST':
        nf = int(request.form['nf'])
        representante = request.form['representante']
        fornecedor = request.form['fornecedor']
        item = request.form['item'].upper()
        quantidade_recebida = int(request.form['quantidade_recebida'])
        quantidade_com_defeito = int(request.form['quantidade_com_defeito'])

        if not validate_item_format(item):
            flash('Formato do item inválido. Deve ser 3 letras maiúsculas, ponto e 5 dígitos, ex: MPR.02199', 'danger')
            return render_template('cadastro_inc.html', representantes=representantes, fornecedores=fornecedores)

        if quantidade_com_defeito > quantidade_recebida:
            flash('Quantidade com defeito não pode ser maior que a quantidade recebida.', 'danger')
            return render_template('cadastro_inc.html', representantes=representantes, fornecedores=fornecedores)

        # Gerar número OC sequencial
        last_inc = INC.query.order_by(INC.oc.desc()).first()
        new_oc = (last_inc.oc + 1) if last_inc and last_inc.oc else 1

        inc = INC(
            nf=nf,
            data=datetime.today().strftime("%d-%m-%Y"),
            representante=representante,
            fornecedor=fornecedor,
            item=item,
            quantidade_recebida=quantidade_recebida,
            quantidade_com_defeito=quantidade_com_defeito,
            descricao_defeito=request.form.get('descricao_defeito', ''),
            urgencia=request.form.get('urgencia', 'Moderada'),
            acao_recomendada=request.form.get('acao_recomendada', ''),
            fotos=json.dumps([]),
            oc=new_oc,
            status="Em andamento"
        )

        # Adicionar fotos, se houver
        if 'fotos' in request.files:
            files = request.files.getlist('fotos')
            fotos = []
            for file in files:
                if file and file.filename:
                    filepath = save_file(file, ['png', 'jpg', 'jpeg', 'gif'])
                    if filepath:
                        fotos.append(filepath)
            inc.fotos = json.dumps(fotos)

        db.session.add(inc)
        db.session.commit()
        flash('INC cadastrada com sucesso!', 'success')
        return redirect(url_for('visualizar_incs'))

    return render_template('cadastro_inc.html', representantes=representantes, fornecedores=fornecedores)

@app.route('/visualizar_incs')
@login_required
def visualizar_incs():
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

    return render_template('visualizar_incs.html', incs=incs, pagination=pagination)

@app.route('/detalhes_inc/<int:inc_id>')
@login_required
def detalhes_inc(inc_id):
    inc = INC.query.get_or_404(inc_id)
    fotos = json.loads(inc.fotos)
    return render_template('detalhes_inc.html', inc=inc, fotos=fotos)

@app.route('/editar_inc/<int:inc_id>', methods=['GET', 'POST'])
@login_required
def editar_inc(inc_id):
    inc = INC.query.get_or_404(inc_id)
    representantes = ["Gabriel Rodrigues da Silva", "Marcos Vinicius Gomes Teixeira", "Aleksandro Carvalho Leão"]
    fotos = json.loads(inc.fotos) if inc.fotos else []

    if request.method == 'POST':
        # Debug output
        print(f"POST request received to edit INC #{inc_id}")
        print(f"Form data: {request.form}")
        
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
        if 'fotos' in request.files:
            files = request.files.getlist('fotos')
            for file in files:
                if file and file.filename:
                    filepath = save_file(file, ['png', 'jpg', 'jpeg', 'gif'])
                    if filepath:
                        fotos.append(filepath)

        inc.fotos = json.dumps(fotos)
        
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
            
            break
    
    # Atualizar o campo de fotos na INC
    inc.fotos = json.dumps(fotos)
    db.session.commit()
    
    flash('Foto removida com sucesso!', 'success')
    return redirect(url_for('editar_inc', inc_id=inc_id))

@app.route('/excluir_inc/<int:inc_id>', methods=['POST'])
@login_required
def excluir_inc(inc_id):
    inc = INC.query.get_or_404(inc_id)
    
    # Remover fotos associadas
    fotos = json.loads(inc.fotos) if inc.fotos else []
    for foto in fotos:
        remove_file(foto)
    
    db.session.delete(inc)
    db.session.commit()
    flash('INC excluída com sucesso!', 'success')
    return redirect(url_for('visualizar_incs'))

@app.route('/expiracao_inc')
@login_required
def expiracao_inc():
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
    return render_template('expiracao_inc.html', vencidas=vencidas)

@app.route('/print_inc_label/<int:inc_id>')
@login_required
def print_inc_label(inc_id):
    inc = INC.query.get_or_404(inc_id)
    
    # Montar o ZPL com layout ajustado
    zpl = f"""^XA
^PW800          ; Largura: 100 mm = 800 pontos (203 DPI)
^LL976          ; Altura: 122 mm = 976 pontos (203 DPI)
^CF0,30         ; Fonte padrão, tamanho 20 pontos
^FO50,50^FDNF-e:^FS
^FO300,50^FD{inc.nf}^FS
^FO50,100^FDData:^FS
^FO300,100^FD{inc.data}^FS
^FO50,150^FDRepresentante:^FS
^FO300,150^FD{inc.representante[:20]}^FS    ; Limitar a 20 caracteres
^FO50,200^FDFornecedor:^FS
^FO300,200^FD{inc.fornecedor[:20]}^FS      ; Limitar a 20 caracteres
^FO50,250^FDItem:^FS
^FO300,250^FD{inc.item}^FS
^FO50,300^FDQtd. Recebida:^FS
^FO300,300^FD{inc.quantidade_recebida}^FS
^FO50,350^FDQtd. Defeituosa:^FS
^FO300,350^FD{inc.quantidade_com_defeito}^FS
^FO50,400^FDDescricao:^FS
^FO300,400^FB600,6,N,10^FD{inc.descricao_defeito}^FS  ; Bloco de texto com quebra de linha
^FO50,650^FDUrgencia:^FS
^FO300,650^FD{inc.urgencia}^FS
^FO50,720^FDAcao Recomendada:^FS
^FO300,720^FB600,3,N,10^FD{inc.acao_recomendada}^FS  ; Bloco de texto com quebra de linha
^FO50,830^FDStatus:^FS
^FO300,830^FD{inc.status}^FS
^XZ"""

    printer_ip = app.config.get('PRINTER_IP', "192.168.1.48")
    printer_port = app.config.get('PRINTER_PORT', 9100)
    
    try:
        logging.debug(f"Tentando conectar a {printer_ip}:{printer_port}")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)  # Timeout de 5 segundos
            s.connect((printer_ip, printer_port))
            logging.debug("Conexão estabelecida, enviando ZPL")
            s.send(zpl.encode('utf-8'))
            logging.debug("ZPL enviado com sucesso")
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
    output.seek(0)
    return send_file(output, mimetype='text/csv', as_attachment=True, download_name='incs.csv')

@app.route('/export_pdf/<int:inc_id>')
@login_required
def export_pdf(inc_id):
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
    buffer.seek(0)
    return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=f'inc_{inc.nf}.pdf')

@app.route('/monitorar_fornecedores', methods=['GET', 'POST'])
@login_required
def monitorar_fornecedores():
    fornecedores = Fornecedor.query.all()
    incs = []
    graph_url = None  # Inicializar graph_url como None

    if request.method == 'POST':
        fornecedor = request.form.get('fornecedor')
        item = request.form.get('item')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')

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
            db.session.delete(fornecedor)
            db.session.commit()
            flash('Fornecedor excluído com sucesso!', 'success')
        elif action == 'update':
            fornecedor.razao_social = request.form['razao_social']
            fornecedor.cnpj = request.form['cnpj']
            fornecedor.fornecedor_logix = request.form['fornecedor_logix']
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
        flash('Fornecedor cadastrado com sucesso!', 'success')
        return redirect(url_for('gerenciar_fornecedores'))

    return render_template('cadastrar_fornecedor.html')

# =====================================
# ROTAS DE INSPEÇÃO
# =====================================

@app.route('/set_crm_token', methods=['GET', 'POST'])
@login_required
def set_crm_token():
    if request.method == 'POST':
        crm_link = request.form['crm_link']
        token_match = re.search(r'token=([a-f0-9]+)', crm_link)
        
        if token_match:
            token = token_match.group(1)
            session['crm_token'] = token
            session['inspecao_crm_token'] = token  # Atualiza o token da inspeção também
            flash('Token CRM atualizado com sucesso!', 'success')
            return redirect(url_for('visualizar_registros_inspecao'))
        else:
            flash('Link CRM inválido. Verifique o link.', 'danger')
            return redirect(url_for('visualizar_registros_inspecao'))
    
    return render_template('set_crm_token.html')

@app.route('/api/historico_incs/<path:item>', methods=['GET'])
@login_required
def api_historico_incs(item):
    # Decodificar o item, pois pode conter caracteres especiais
    item = item.upper().strip()
    
    # Buscar histórico de INCs para este item
    incs = INC.query.filter_by(item=item).order_by(INC.id.desc()).all()
    
    # Converter para JSON
    incs_json = []
    for inc in incs:
        incs_json.append({
            'id': inc.id,
            'nf': inc.nf,
            'data': inc.data,
            'representante': inc.representante,
            'fornecedor': inc.fornecedor,
            'quantidade_recebida': inc.quantidade_recebida,
            'quantidade_com_defeito': inc.quantidade_com_defeito,
            'descricao_defeito': inc.descricao_defeito[:100] + '...' if len(inc.descricao_defeito) > 100 else inc.descricao_defeito,
            'urgencia': inc.urgencia,
            'status': inc.status,
            'oc': inc.oc
        })
    
    return jsonify({
        'item': item, 
        'incs': incs_json, 
        'total': len(incs_json)
    })

@app.route('/rotina_inspecao', methods=['GET', 'POST'])
@login_required
def rotina_inspecao():
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
                flash(f'Item {registros[registro_global_index]["item"]} marcado como inspecionado.', 'success')
            elif action == 'adiar':
                registros[registro_global_index]['inspecionado'] = False
                registros[registro_global_index]['adiado'] = True
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
    rotinas = RotinaInspecao.query.all()
    # Converter registros de JSON para Python para cada rotina
    for rotina in rotinas:
        rotina.registros_python = json.loads(rotina.registros)
    return render_template('listar_rotinas_inspecao.html', rotinas=rotinas)

@app.route('/salvar_rotina_inspecao', methods=['POST'])
@login_required
def salvar_rotina_inspecao():
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
    
    rotina = RotinaInspecao(
        inspetor_id=current_user.id,
        registros=json.dumps(registros)
    )
    db.session.add(rotina)
    db.session.commit()
    
    flash('Rotina de inspeção salva com sucesso!', 'success')
    session.pop('inspecao_registros', None)
    return redirect(url_for('main_menu'))

# =====================================
# API ENDPOINTS
# =====================================

@app.route('/api/update_inc_status/<int:inc_id>', methods=['POST'])
@login_required
def update_inc_status(inc_id):
    inc = INC.query.get_or_404(inc_id)
    
    # Obter dados da solicitação
    data = request.json
    new_status = data.get('status')
    
    if not new_status:
        return jsonify({'success': False, 'error': 'Status não fornecido'}), 400
    
    # Atualizar status da INC
    inc.status = new_status
    db.session.commit()
    
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