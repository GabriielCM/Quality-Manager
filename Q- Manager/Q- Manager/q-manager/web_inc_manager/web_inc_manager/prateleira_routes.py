from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, PrateleiraNaoConforme, INC, ItemSolicitacaoFaturamento, SolicitacaoFaturamento
from utils import log_user_activity, display_file_preview, diagnosticar_linha_lst
from werkzeug.utils import secure_filename
import os
import json
import re
import chardet

prateleira_bp = Blueprint('prateleira', __name__, url_prefix='/prateleira')

@prateleira_bp.route('/listar')
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
            from datetime import datetime
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

@prateleira_bp.route('/atualizar', methods=['GET', 'POST'])
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
        from flask import current_app
        filename = secure_filename(arquivo.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        arquivo.save(filepath)
        
        try:
            # Exibir prévia do conteúdo para depuração
            current_app.logger.info(f"Processando arquivo: {filename}")
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
                    f'<a href="{url_for("faturamento.visualizar_solicitacao_faturamento", solicitacao_id=notificacao["solicitacao_id"])}">Ver solicitação</a>', 
                    'warning'
                )
            
            flash(f'Prateleira não conforme atualizada com sucesso! {len(itens_processados)} itens processados.', 'success')
            return redirect(url_for('prateleira.listar_prateleira_nao_conforme'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao processar arquivo: {str(e)}", exc_info=True)
            flash(f'Erro ao processar arquivo: {str(e)}', 'danger')
            return redirect(request.url)
        finally:
            # Remover o arquivo temporário
            if os.path.exists(filepath):
                os.remove(filepath)
    
    return render_template('atualizar_prateleira.html')

def processar_arquivo_lst_prateleira(filepath):
    """Processa um arquivo LST e retorna os itens para a prateleira não conforme"""
    from flask import current_app
    from datetime import datetime
    
    itens = []
    notificacoes_faturamento = []  # Lista para armazenar notificações
    
    # Detectar a codificação do arquivo
    with open(filepath, 'rb') as f:
        raw_data = f.read()
        encoding = chardet.detect(raw_data)['encoding'] or 'latin-1'
    
    current_app.logger.debug(f"Usando codificação: {encoding}")
    
    # Ler o conteúdo do arquivo
    with open(filepath, 'r', encoding=encoding) as file:
        lines = file.readlines()
    
    current_app.logger.debug(f"Arquivo LST lido com sucesso. Total de linhas: {len(lines)}")
    
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
                current_app.logger.debug(f"Analisando linha {i+1} que parece conter um item")
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
                            current_app.logger.warning(f"Não foi possível encontrar quantidade na linha {i+1}")
                            continue
                    
                    # Descrição é tudo entre o código e a quantidade
                    desc_end_idx = quantidade_idx
                    desc_parts = parts[1:desc_end_idx]
                    item_desc = ' '.join(desc_parts)
                    
                    # Validações adicionais
                    if not re.match(r'\d{2}/\d{2}/\d{4}', item_date):
                        current_app.logger.warning(f"Data inválida na linha {i+1}: {item_date}")
                        continue
                    
                    current_app.logger.debug(f"Item extraído: código={item_code}, desc={item_desc}, qtd={item_qty}, data={item_date}")
                    
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
                        current_app.logger.debug(f"Item {item_code} associado à INC #{inc.id} (Recebimento)")
                    else:
                        tipo_defeito = "Produção"
                        inc_id = None
                        current_app.logger.debug(f"Item {item_code} classificado como defeito de Produção")
                    
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
                    current_app.logger.warning(f"Linha {i+1} não tem campos suficientes: {stripped_line}")
            
            except Exception as e:
                current_app.logger.error(f"Erro ao processar linha {i+1}: {str(e)}")
                current_app.logger.error(f"Linha com erro: {line}")
    
    current_app.logger.info(f"Total de itens processados: {len(itens)}")
    
    # Retornar tanto os itens quanto as notificações
    return itens, notificacoes_faturamento

@prateleira_bp.route('/api/atualizar_status', methods=['POST'])
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