from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from models import db, SolicitacaoFaturamento, ItemSolicitacaoFaturamento, Fornecedor, INC
from utils import log_user_activity
from datetime import datetime
import textwrap
from io import BytesIO
import json

faturamento_bp = Blueprint('faturamento', __name__, url_prefix='/faturamento')

@faturamento_bp.route('/solicitacoes')
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

@faturamento_bp.route('/nova_solicitacao', methods=['GET', 'POST'])
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
                return redirect(url_for('faturamento.nova_solicitacao_faturamento'))
            
            if not quantidades:
                flash('Informe as quantidades para as INCs selecionadas', 'danger')
                return redirect(url_for('faturamento.nova_solicitacao_faturamento'))
                
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
                        return redirect(url_for('faturamento.nova_solicitacao_faturamento'))
                    
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
            return redirect(url_for('faturamento.visualizar_solicitacao_faturamento', solicitacao_id=solicitacao.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar solicitação: {str(e)}', 'danger')
            return redirect(url_for('faturamento.nova_solicitacao_faturamento'))
    
    # Processar solicitação GET
    # Buscar fornecedores e INCs em andamento
    fornecedores = Fornecedor.query.all()
    incs = INC.query.filter_by(status='Em andamento').all()
    
    return render_template('nova_solicitacao_faturamento.html', 
                          fornecedores=fornecedores, 
                          incs=incs)

@faturamento_bp.route('/solicitacao/<int:solicitacao_id>')
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

@faturamento_bp.route('/exportar_pdf_solicitacao/<int:solicitacao_id>')
@login_required
def exportar_pdf_solicitacao(solicitacao_id):
    """Exporta uma solicitação de faturamento para PDF"""
    # Verificar se o usuário tem permissão
    if not current_user.is_admin and not current_user.has_permission('faturamento'):
        flash('Acesso negado. Você não tem permissão para acessar esta funcionalidade.', 'danger')
        return redirect(url_for('main_menu'))
    
    # Importar bibliotecas necessárias
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    
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

@faturamento_bp.route('/api/incs_por_fornecedor/<fornecedor>')
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
                'representante': inc.representante_nome
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
        
        return json.dumps({
            'success': True,
            'incs': incs_json
        })
    except Exception as e:
        return json.dumps({
            'success': False,
            'error': str(e)
        }), 500