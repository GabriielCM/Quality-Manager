from flask import (
    Blueprint, 
    render_template, 
    request, 
    redirect, 
    url_for, 
    flash, 
    send_file, 
    jsonify, 
    current_app
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from models import db, User, INC, Fornecedor, Notification
from utils import (
    validate_item_format, 
    save_file, 
    remove_file, 
    log_user_activity, 
    parse_date, 
    format_date_for_db
)
from datetime import datetime, timedelta
import json
import os
import socket
import logging
import base64
import matplotlib.pyplot as plt

inc_bp = Blueprint('inc', __name__, url_prefix='/inc')


@inc_bp.route('/api/update_inc_status/<int:inc_id>', methods=['POST'])
@login_required
def api_update_inc_status(inc_id):
    """API for updating INC status from the frontend"""
    try:
        # Check permissions
        if not current_user.is_admin and not current_user.has_permission('visualizar_incs'):
            return jsonify({
                'success': False,
                'error': 'Acesso negado. Você não tem permissão para atualizar o status.'
            }), 403
        
        # Get data from request
        data = request.json
        if not data or 'status' not in data:
            return jsonify({'success': False, 'error': 'Status não fornecido'}), 400
        
        new_status = data.get('status')
        valid_statuses = ['Em andamento', 'Concluída', 'Vencida']
        
        if new_status not in valid_statuses:
            return jsonify({'success': False, 'error': 'Status inválido'}), 400
        
        # Get the INC
        inc = INC.query.get_or_404(inc_id)
        
        # Record original status for the log
        old_status = inc.status
        
        # Update INC status
        inc.status = new_status

        # Se status está mudando para Concluída, adicionar dados de concessão
        if new_status == 'Concluída' and old_status != 'Concluída':
            concessao_data = {
                'justificativa': 'Atualizado via API',
                'data_concessao': datetime.now().isoformat(),
                'usuario_aprovacao': current_user.username,
                'usuario_id': current_user.id,
                'metodo': 'api'
            }
            inc.set_concessao_data(concessao_data)
        
        db.session.commit()
        
        # Record the status update
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
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@inc_bp.route('/editar_inc/<int:inc_id>', methods=['GET', 'POST'])
@login_required
def editar_inc(inc_id):
    """
    Função para editar uma INC existente.
    Permite a atualização de todos os campos e processamento de concessão para encerramento da INC.
    """
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('cadastro_inc'):
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('main_menu'))
    
    inc = INC.query.get_or_404(inc_id)
    representantes = User.query.filter_by(is_representante=True).all()
    fotos = json.loads(inc.fotos) if inc.fotos else []

    if request.method == 'POST':
        try:
            # Salvar valores originais para o log
            original_values = {
                'item': inc.item,
                'representante_id': inc.representante_id,
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
            representante_id = int(request.form['representante'])
            fornecedor = request.form['fornecedor']
            quantidade_recebida = int(request.form['quantidade_recebida'])
            quantidade_com_defeito = int(request.form['quantidade_com_defeito'])
            descricao_defeito = request.form['descricao_defeito']
            urgencia = request.form['urgencia']
            acao_recomendada = request.form['acao_recomendada']
            status = request.form['status']
            
            # Verificar se é uma concessão
            metodo_conclusao = request.form.get('metodo_conclusao', '')
            
            # Status changed to Concluída manually
            if status == 'Concluída' and inc.status != 'Concluída' and metodo_conclusao == 'concessao':
                # Validate concessao form data
                justificativa = request.form.get('justificativa_conclusao', '').strip()
                email_file = request.files.get('email_aprovacao')
                
                if not justificativa or not email_file:
                    flash('É necessário fornecer justificativa e email de aprovação.', 'danger')
                    return render_template('editar_inc.html', inc=inc, representantes=representantes, fotos=fotos)
                
                # Prepare concessao data
                concessao_data = {
                    'justificativa': justificativa,
                    'email_filename': secure_filename(email_file.filename),
                    'data_concessao': datetime.now().isoformat(),
                    'usuario_aprovacao': current_user.username,  # Adiciona o usuário que aprovou
                    'usuario_id': current_user.id,              # Adiciona o ID do usuário para referência
                    'metodo': 'concessao'
                }
                
                # Save email file
                email_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'emails')
                os.makedirs(email_folder, exist_ok=True)
                email_path = os.path.join(email_folder, concessao_data['email_filename'])
                email_file.save(email_path)
                concessao_data['email_path'] = email_path
                
                # Use the new set_concessao_data method
                inc.set_concessao_data(concessao_data)
            
            # Processar novas fotos, se houver
            if 'fotos' in request.files:
                files = request.files.getlist('fotos')
                for file in files:
                    if file and file.filename:
                        filepath = save_file(file, ['png', 'jpg', 'jpeg', 'gif'])
                        if filepath:
                            fotos.append(filepath)
            
            # Update INC data
            inc.representante_id = representante_id
            inc.representante_nome = User.query.get(representante_id).username
            inc.fornecedor = fornecedor
            inc.item = item
            inc.quantidade_recebida = quantidade_recebida
            inc.quantidade_com_defeito = quantidade_com_defeito
            inc.descricao_defeito = descricao_defeito
            inc.urgencia = urgencia
            inc.acao_recomendada = acao_recomendada
            inc.status = status
            inc.fotos = json.dumps(fotos)
            
            # Registrar mudanças para o log
            changes = {}
            for key, value in original_values.items():
                new_value = getattr(inc, key)
                if key == 'representante_id':
                    new_value = int(new_value)
                if new_value != value:
                    changes[key] = {'old': value, 'new': new_value}
            
            # Registrar a edição da INC
            if changes:
                log_user_activity(
                    user_id=current_user.id,
                    action="update",
                    entity_type="inc",
                    entity_id=inc.id,
                    details={
                        "changes": changes,
                        "concessao": bool(metodo_conclusao == 'concessao' and status == 'Concluída' and original_values['status'] != 'Concluída')
                    }
                )
            
            # Commit changes
            db.session.commit()
            
            flash('INC atualizada com sucesso!', 'success')
            return redirect(url_for('inc.visualizar_incs'))
            
        except Exception as e:
            db.session.rollback()
            print(f"ERROR: {str(e)}")
            flash(f'Erro ao atualizar INC: {str(e)}', 'danger')
            return render_template('editar_inc.html', inc=inc, representantes=representantes, fotos=fotos)
    
    # GET request - just render the form
    return render_template('editar_inc.html', inc=inc, representantes=representantes, fotos=fotos)

@inc_bp.route('/detalhes_inc/<int:inc_id>')
@login_required
def detalhes_inc(inc_id):
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('visualizar_incs'):
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('main_menu'))
    
    inc = INC.query.get_or_404(inc_id)
    fotos = json.loads(inc.fotos) if inc.fotos else []
    
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

@inc_bp.route('/cadastro_inc', methods=['GET', 'POST'])
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
        
        # Criar notificação para o representante
        
        # Determinar categoria baseado na urgência
        category = 'task'
        if urgencia.lower() == 'crítico':
            category = 'alert'
        
        # Criar notificação para o representante
        notification = Notification(
            user_id=representante_id,
            title=f'Nova INC para {item}',
            message=f'Nova INC criada: {item} - {quantidade_com_defeito} itens com defeito - {fornecedor}',
            category=category,
            entity_type='inc',
            entity_id=inc.id,
            action_text='Visualizar INC'
        )
        
        # Notificação para administradores
        admins = User.query.filter_by(is_admin=True).all()
        for admin in admins:
            if admin.id != current_user.id and admin.id != representante_id:  # Evitar duplicatas
                admin_notification = Notification(
                    user_id=admin.id,
                    title=f'Nova INC cadastrada: {item}',
                    message=f'INC criada por {current_user.username} para {fornecedor} - {quantidade_com_defeito} itens com defeito',
                    category=category,
                    entity_type='inc',
                    entity_id=inc.id,
                    action_text='Visualizar INC'
                )
                db.session.add(admin_notification)
        
        db.session.add(notification)
        db.session.commit()
        
        flash('INC cadastrada com sucesso!', 'success')
        return redirect(url_for('inc.visualizar_incs'))

    return render_template('cadastro_inc.html', representantes=representantes, fornecedores=fornecedores)

@inc_bp.route('/visualizar_incs')
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
    per_page = 10  # Ou obter da configuração da aplicação

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


@inc_bp.route('/remover_foto_inc/<int:inc_id>/<path:foto>', methods=['POST'])
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
            full_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static/uploads', filename)
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
    return redirect(url_for('inc.editar_inc', inc_id=inc_id))

@inc_bp.route('/excluir_inc/<int:inc_id>', methods=['POST'])
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
    return redirect(url_for('inc.visualizar_incs'))

@inc_bp.route('/expiracao_inc')
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

@inc_bp.route('/print_inc_label/<int:inc_id>')
@login_required
def print_inc_label(inc_id):
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('cadastro_inc'):
        flash('Você não tem permissão para realizar esta ação.', 'danger')
        return redirect(url_for('main_menu'))
    
    # Importar a configuração
    from config import Config
    
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
    representante_str = inc.representante_nome if inc.representante_nome else "Não definido"
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
^FO300,150^FD{sanitize_for_zpl(representante_str[:20])}^FS    ; Limitar a 20 caracteres
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

    printer_ip = Config.PRINTER_IP
    printer_port = Config.PRINTER_PORT
    
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

    return redirect(url_for('inc.detalhes_inc', inc_id=inc_id))

@inc_bp.route('/export_csv')
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
        writer.writerow([inc.nf, inc.data, inc.representante_nome, inc.fornecedor, inc.item, 
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

@inc_bp.route('/export_pdf/<int:inc_id>')
@login_required
def export_pdf(inc_id):
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('visualizar_incs'):
        flash('Você não tem permissão para exportar dados.', 'danger')
        return redirect(url_for('main_menu'))
    
    # Importar bibliotecas necessárias
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
        
    inc = INC.query.get_or_404(inc_id)
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 50
    c.setFont("Helvetica", 12)
    c.drawString(50, y, f"INC #{inc.oc}")
    y -= 20
    
    details = [
        f"NF-e: {inc.nf}", f"Data: {inc.data}", f"Representante: {inc.representante_nome}",
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
            from config import Config
            full_path = os.path.join(Config.UPLOAD_FOLDER, os.path.basename(foto))
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

@inc_bp.route('/monitorar_fornecedores', methods=['GET', 'POST'])
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

@inc_bp.route('/export_monitor_pdf', methods=['GET'])
@login_required
def export_monitor_pdf():
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('fornecedores'):
        flash('Você não tem permissão para exportar dados.', 'danger')
        return redirect(url_for('main_menu'))
    
    # Importar bibliotecas necessárias
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
        
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
        return redirect(url_for('inc.monitorar_fornecedores'))

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

    # Importar configuração
    from config import Config
    
    # Criar arquivo temporário
    temp_path = os.path.join(Config.UPLOAD_FOLDER, 'temp_graph.png')
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