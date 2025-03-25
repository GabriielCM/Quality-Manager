from flask import (
    Blueprint, 
    render_template, 
    request, 
    redirect, 
    url_for, 
    flash, 
    jsonify, 
    current_app,
    abort,
    send_file
)
from flask_login import login_required, current_user
from models import db, User, INC, RegistroNaoConformidade, Notification
from utils import log_user_activity, save_file, remove_file
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import json
import os
import secrets
import io
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import textwrap
from config import Config
import uuid
import hashlib

rnc_bp = Blueprint('rnc', __name__, url_prefix='/rnc')

def gerar_numero_rnc():
    """Gera um número para o novo RNC no formato 001/ANO"""
    ano_atual = datetime.now().year
    ultimo_rnc = RegistroNaoConformidade.query.filter(
        RegistroNaoConformidade.numero.like(f'%/{ano_atual}')).order_by(
        RegistroNaoConformidade.id.desc()).first()
        
    if ultimo_rnc:
        try:
            ultimo_numero = int(ultimo_rnc.numero.split('/')[0])
            novo_numero = ultimo_numero + 1
        except (ValueError, IndexError):
            novo_numero = 1
    else:
        novo_numero = 1
        
    return f"{novo_numero:03d}/{ano_atual}"

def gerar_token_acesso():
    """Gera um token seguro para acesso do fornecedor"""
    return secrets.token_hex(32)  # 64 caracteres

@rnc_bp.route('/criar/<int:inc_id>', methods=['GET', 'POST'])
@login_required
def criar_rnc(inc_id):
    """Cria um Registro de Não Conformidade (RNC) a partir de uma INC"""
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('visualizar_incs'):
        flash('Você não tem permissão para acessar esta funcionalidade.', 'danger')
        return redirect(url_for('main_menu'))
        
    inc = INC.query.get_or_404(inc_id)
    
    # Verificar se a INC está concluída
    if inc.status != 'Concluída':
        flash('Só é possível criar um RNC para INCs concluídas.', 'warning')
        return redirect(url_for('inc.detalhes_inc', inc_id=inc_id))
    
    # Verificar se já existe um RNC para esta INC
    rnc_existente = RegistroNaoConformidade.query.filter_by(inc_id=inc_id).first()
    if rnc_existente:
        flash(f'Já existe um RNC (#{rnc_existente.numero}) para esta INC.', 'warning')
        return redirect(url_for('rnc.visualizar_rnc', rnc_id=rnc_existente.id))
    
    if request.method == 'POST':
        try:
            # Obter dados do formulário
            descricao = request.form['descricao_nao_conformidade']
            nf_oc = request.form['nf_ordem_compra']
            reincidencia = 'reincidencia' in request.form  # Novo campo
            
            # Criar novo RNC
            novo_rnc = RegistroNaoConformidade(
                inc_id=inc.id,
                numero=gerar_numero_rnc(),
                fornecedor=inc.fornecedor,
                descricao_nao_conformidade=descricao,
                nf_ordem_compra=nf_oc,
                reincidencia=reincidencia,  # Novo campo
                data_emissao=datetime.utcnow(),
                data_expiracao=datetime.utcnow() + timedelta(days=7),
                token_acesso=gerar_token_acesso()
            )
            
            # Importar fotos da INC, se houver
            if inc.fotos:
                novo_rnc.fotos = inc.fotos
            
            # Desenhos técnicos, se enviados
            desenhos = []
            if 'desenhos' in request.files:
                files = request.files.getlist('desenhos')
                for file in files:
                    if file and file.filename:
                        filepath = save_file(file, ['png', 'jpg', 'jpeg', 'gif', 'pdf'])
                        if filepath:
                            desenhos.append(filepath)
            
            if desenhos:
                novo_rnc.desenhos_list = desenhos
            
            db.session.add(novo_rnc)
            db.session.commit()
            
            # Registrar a criação do RNC
            log_user_activity(
                user_id=current_user.id,
                action="create",
                entity_type="rnc",
                entity_id=novo_rnc.id,
                details={
                    "inc_id": inc.id,
                    "numero": novo_rnc.numero,
                    "fornecedor": novo_rnc.fornecedor
                }
            )
            
            flash(f'RNC #{novo_rnc.numero} criado com sucesso!', 'success')
            return redirect(url_for('rnc.visualizar_rnc', rnc_id=novo_rnc.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar RNC: {str(e)}', 'danger')
    
    # Template para criar RNC
    return render_template('criar_rnc.html', inc=inc)

@rnc_bp.route('/visualizar/<int:rnc_id>')
@login_required
def visualizar_rnc(rnc_id):
    """Exibe os detalhes de um RNC"""
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('visualizar_incs'):
        flash('Você não tem permissão para acessar esta funcionalidade.', 'danger')
        return redirect(url_for('main_menu'))
        
    rnc = RegistroNaoConformidade.query.get_or_404(rnc_id)
    
    # Gerar link para o fornecedor
    link_fornecedor = url_for('rnc.responder_rnc', token=rnc.token_acesso, _external=True)
    
    return render_template('visualizar_rnc.html', rnc=rnc, link_fornecedor=link_fornecedor)

@rnc_bp.route('/listar')
@login_required
def listar_rncs():
    """Lista todos os RNCs cadastrados"""
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('visualizar_incs'):
        flash('Você não tem permissão para acessar esta funcionalidade.', 'danger')
        return redirect(url_for('main_menu'))
    
    rncs = RegistroNaoConformidade.query.order_by(RegistroNaoConformidade.data_emissao.desc()).all()
    return render_template('listar_rncs.html', rncs=rncs)

@rnc_bp.route('/responder/<token>', methods=['GET', 'POST'])
def responder_rnc(token):
    """Rota pública para o fornecedor responder ao RNC"""
    # Buscar RNC pelo token
    rnc = RegistroNaoConformidade.query.filter_by(token_acesso=token).first_or_404()
    
    # Verificar se o RNC expirou
    if rnc.expirado:
        return render_template('rnc_expirado.html', rnc=rnc)
    
    # Verificar se o RNC já foi respondido
    if rnc.status != 'Pendente':
        return render_template('rnc_ja_respondido.html', rnc=rnc)
    
    if request.method == 'POST':
        try:
            # Obter dados da resposta
            causa_problema = request.form['causa_problema']
            plano_contingencia = request.form['plano_contingencia']
            acoes_propostas = request.form['acoes_propostas']
            
            # Atualizar RNC
            rnc.causa_problema = causa_problema
            rnc.plano_contingencia = plano_contingencia
            rnc.acoes_propostas = acoes_propostas
            rnc.respondido_em = datetime.utcnow()
            rnc.status = 'Respondido'
            
            db.session.commit()
            
            # Criar notificação para usuários administradores
            admin_users = User.query.filter_by(is_admin=True).all()
            for admin in admin_users:
                notificacao = Notification(
                    user_id=admin.id,
                    title=f'RNC #{rnc.numero} foi respondido',
                    message=f'O fornecedor {rnc.fornecedor} respondeu ao RNC #{rnc.numero}',
                    category='alert',
                    entity_type='rnc',
                    entity_id=rnc.id,
                    action_text='Visualizar RNC'
                )
                db.session.add(notificacao)
            
            db.session.commit()
            
            # Exportar PDF da resposta e anexar à INC original
            gerar_pdf_rnc(rnc)
            
            return render_template('rnc_respondido_sucesso.html')
            
        except Exception as e:
            db.session.rollback()
            return render_template('rnc_responder.html', rnc=rnc, erro=str(e))
    
    return render_template('rnc_responder.html', rnc=rnc)

@rnc_bp.route('/avaliar/<int:rnc_id>', methods=['POST'])
@login_required
def avaliar_rnc(rnc_id):
    """Avalia a resposta do fornecedor"""
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('visualizar_incs'):
        return jsonify({'success': False, 'error': 'Permissão negada'}), 403
        
    rnc = RegistroNaoConformidade.query.get_or_404(rnc_id)
    
    # Verificar se o RNC foi respondido
    if rnc.status != 'Respondido':
        return jsonify({'success': False, 'error': 'Este RNC ainda não foi respondido ou já foi avaliado'}), 400
    
    try:
        # Obter dados da avaliação
        data = request.json
        avaliacao = data.get('avaliacao')
        comentario = data.get('comentario', '')
        
        if avaliacao is None:
            return jsonify({'success': False, 'error': 'Avaliação não informada'}), 400
        
        # Atualizar RNC
        rnc.avaliacao = avaliacao
        rnc.comentario_avaliacao = comentario
        rnc.avaliado_em = datetime.utcnow()
        rnc.avaliado_por = current_user.id
        rnc.status = 'Encerrado' if avaliacao else 'Rejeitado'
        
        db.session.commit()
        
        # Registrar a avaliação
        log_user_activity(
            user_id=current_user.id,
            action="update",
            entity_type="rnc_avaliacao",
            entity_id=rnc.id,
            details={
                "avaliacao": "aprovado" if avaliacao else "rejeitado",
                "comentario": comentario
            }
        )
        
        return jsonify({
            'success': True, 
            'rnc_id': rnc.id,
            'status': rnc.status
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@rnc_bp.route('/exportar_pdf/<int:rnc_id>')
@login_required
def exportar_pdf_rnc(rnc_id):
    """Exporta um RNC para PDF"""
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('visualizar_incs'):
        flash('Você não tem permissão para exportar dados.', 'danger')
        return redirect(url_for('main_menu'))
        
    rnc = RegistroNaoConformidade.query.get_or_404(rnc_id)
    
    # Gerar PDF
    buffer = gerar_pdf_rnc(rnc)
    
    # Registrar exportação
    log_user_activity(
        user_id=current_user.id,
        action="export",
        entity_type="rnc_pdf",
        entity_id=rnc.id,
        details={
            "numero": rnc.numero,
            "format": "pdf"
        }
    )
    
    return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=f'rnc_{rnc.numero.replace("/", "_")}.pdf')

def gerar_pdf_rnc(rnc):
    """Gera um PDF do RNC"""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Cabeçalho
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, f"Registro de Não Conformidade #{rnc.numero}")
    
    # Dados do fornecedor
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 80, f"Fornecedor: {rnc.fornecedor}")
    c.drawString(50, height - 100, f"NF/OC: {rnc.nf_ordem_compra}")
    c.drawString(50, height - 120, f"Data de Emissão: {rnc.data_emissao.strftime('%d/%m/%Y')}")
    
    # Descrição da não conformidade
    c.drawString(50, height - 150, "Descrição da Não Conformidade:")
    c.setFont("Helvetica", 10)
    
    # Quebrar texto longo em múltiplas linhas
    wrapped_text = textwrap.fill(rnc.descricao_nao_conformidade, width=80)
    y = height - 170
    for line in wrapped_text.split('\n'):
        c.drawString(50, y, line)
        y -= 15
    
    # Fotos, se houver
    if rnc.fotos:
        c.showPage()
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, height - 50, f"Fotos - RNC #{rnc.numero}")
        
        x, y = 50, height - 100
        for foto in rnc.fotos_list:
            full_path = os.path.join(Config.UPLOAD_FOLDER, os.path.basename(foto))
            if os.path.exists(full_path):
                c.drawImage(full_path, x, y, width=200, height=200, preserveAspectRatio=True)
                x += 250
                if x > width - 200:
                    x = 50
                    y -= 220
                    if y < 50:
                        c.showPage()
                        c.setFont("Helvetica-Bold", 12)
                        c.drawString(50, height - 50, f"Fotos (continuação) - RNC #{rnc.numero}")
                        y = height - 100
    
    # Se houver resposta do fornecedor
    if rnc.status in ['Respondido', 'Avaliado', 'Encerrado', 'Rejeitado']:
        c.showPage()
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, height - 50, f"Resposta do Fornecedor - RNC #{rnc.numero}")
        
        # Data da resposta
        c.setFont("Helvetica", 10)
        c.drawString(50, height - 80, f"Respondido em: {rnc.respondido_em.strftime('%d/%m/%Y %H:%M')}")
        
        # Causa do problema
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, height - 110, "Causa do Problema:")
        c.setFont("Helvetica", 10)
        
        wrapped_text = textwrap.fill(rnc.causa_problema or "", width=80)
        y = height - 130
        for line in wrapped_text.split('\n'):
            c.drawString(50, y, line)
            y -= 15
        
        # Plano de contingência
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y - 20, "Plano de Contingência:")
        c.setFont("Helvetica", 10)
        
        wrapped_text = textwrap.fill(rnc.plano_contingencia or "", width=80)
        y = y - 40
        for line in wrapped_text.split('\n'):
            c.drawString(50, y, line)
            y -= 15
        
        # Ações propostas
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y - 20, "Ações Propostas para Evitar Reincidência:")
        c.setFont("Helvetica", 10)
        
        wrapped_text = textwrap.fill(rnc.acoes_propostas or "", width=80)
        y = y - 40
        for line in wrapped_text.split('\n'):
            c.drawString(50, y, line)
            y -= 15
        
        # Avaliação, se houver
        if rnc.status in ['Avaliado', 'Encerrado', 'Rejeitado'] and rnc.avaliado_em:
            c.setFont("Helvetica-Bold", 12)
            resultado = "APROVADO" if rnc.avaliacao else "REJEITADO"
            c.drawString(50, y - 30, f"Avaliação Cristófoli: {resultado}")
            
            if rnc.comentario_avaliacao:
                c.setFont("Helvetica", 10)
                c.drawString(50, y - 50, "Comentários:")
                
                wrapped_text = textwrap.fill(rnc.comentario_avaliacao, width=80)
                y = y - 70
                for line in wrapped_text.split('\n'):
                    c.drawString(50, y, line)
                    y -= 15
            
            # Avaliador e data
            avaliador = User.query.get(rnc.avaliado_por)
            if avaliador:
                c.drawString(50, y - 30, f"Avaliado por: {avaliador.username} em {rnc.avaliado_em.strftime('%d/%m/%Y %H:%M')}")
    
    c.save()
    buffer.seek(0)
    return buffer 