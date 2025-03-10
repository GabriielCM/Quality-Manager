import os
import json
import socket
import logging
from datetime import datetime, timedelta
from io import BytesIO
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app, session
from flask_login import login_required, current_user
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import matplotlib.pyplot as plt
import base64
from models import db, INC, Fornecedor
from utils.date_helpers import parse_date, format_date_for_db
from utils.file_handlers import save_uploaded_file, remove_file, temp_file
from utils.security import validate_item_format

inc_bp = Blueprint('inc', __name__)

# Configuração de logging
logging.basicConfig(level=logging.DEBUG)

@inc_bp.route('/cadastro_inc', methods=['GET', 'POST'])
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
            flash('Formato do item inválido. Deve ser 3 letras maiúsculas, ponto e 5 dígitos, ex: MPR.02199')
            return render_template('cadastro_inc.html', representantes=representantes, fornecedores=fornecedores)

        if quantidade_com_defeito > quantidade_recebida:
            flash('Quantidade com defeito não pode ser maior que a quantidade recebida.')
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
                    filepath = save_uploaded_file(file, ['png', 'jpg', 'jpeg', 'gif'])
                    if filepath:
                        fotos.append(filepath)
            inc.fotos = json.dumps(fotos)

        db.session.add(inc)
        db.session.commit()
        flash('INC cadastrada com sucesso!')
        return redirect(url_for('inc.visualizar_incs'))

    return render_template('cadastro_inc.html', representantes=representantes, fornecedores=fornecedores)

@inc_bp.route('/visualizar_incs')
@login_required
def visualizar_incs():
    # Obter parâmetros de filtro
    nf = request.args.get('nf')
    item = request.args.get('item')
    fornecedor = request.args.get('fornecedor')
    status = request.args.get('status')
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config['ITEMS_PER_PAGE']

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

@inc_bp.route('/detalhes_inc/<int:inc_id>')
@login_required
def detalhes_inc(inc_id):
    inc = INC.query.get_or_404(inc_id)
    fotos = json.loads(inc.fotos)
    return render_template('detalhes_inc.html', inc=inc, fotos=fotos)

@inc_bp.route('/editar_inc/<int:inc_id>', methods=['GET', 'POST'])
@login_required
def editar_inc(inc_id):
    inc = INC.query.get_or_404(inc_id)
    representantes = ["Gabriel Rodrigues da Silva", "Marcos Vinicius Gomes Teixeira", "Aleksandro Carvalho Leão"]
    fotos = json.loads(inc.fotos) if inc.fotos else []

    if request.method == 'POST':
        # Atualizar campos existentes
        item = request.form['item'].upper()
        if not validate_item_format(item):
            flash('Formato do item inválido. Deve ser 3 letras maiúsculas, ponto e 5 dígitos, ex: MPR.02199')
            return render_template('editar_inc.html', inc=inc, representantes=representantes, fotos=fotos)
        
        quantidade_recebida = int(request.form['quantidade_recebida'])
        quantidade_com_defeito = int(request.form['quantidade_com_defeito'])
        if quantidade_com_defeito > quantidade_recebida:
            flash('Quantidade com defeito não pode ser maior que a quantidade recebida.')
            return render_template('editar_inc.html', inc=inc, representantes=representantes, fotos=fotos)

        inc.representante = request.form['representante']
        inc.fornecedor = request.form['fornecedor']
        inc.item = item
        inc.quantidade_recebida = quantidade_recebida
        inc.quantidade_com_defeito = quantidade_com_defeito
        inc.descricao_defeito = request.form['descricao_defeito']
        inc.urgencia = request.form['urgencia']
        inc.acao_recomendada = request.form['acao_recomendada']
        inc.status = request.form['status']

        # Adicionar novas fotos
        if 'fotos' in request.files:
            files = request.files.getlist('fotos')
            for file in files:
                if file and file.filename:
                    filepath = save_uploaded_file(file, ['png', 'jpg', 'jpeg', 'gif'])
                    if filepath:
                        fotos.append(filepath)

        inc.fotos = json.dumps(fotos)
        db.session.commit()
        flash('INC atualizada com sucesso!')
        return redirect(url_for('inc.visualizar_incs'))

    return render_template('editar_inc.html', inc=inc, representantes=representantes, fotos=fotos)

@inc_bp.route('/remover_foto_inc/<int:inc_id>/<path:foto>', methods=['POST'])
@login_required
def remover_foto_inc(inc_id, foto):
    inc = INC.query.get_or_404(inc_id)
    fotos = json.loads(inc.fotos) if inc.fotos else []
    if foto in fotos:
        fotos.remove(foto)
        # Remover o arquivo físico
        remove_file(foto)
    inc.fotos = json.dumps(fotos)
    db.session.commit()
    flash('Foto removida com sucesso!')
    return redirect(url_for('inc.editar_inc', inc_id=inc_id))

@inc_bp.route('/excluir_inc/<int:inc_id>', methods=['POST'])
@login_required
def excluir_inc(inc_id):
    inc = INC.query.get_or_404(inc_id)
    
    # Remover fotos associadas
    fotos = json.loads(inc.fotos) if inc.fotos else []
    for foto in fotos:
        remove_file(foto)
    
    db.session.delete(inc)
    db.session.commit()
    flash('INC excluída com sucesso!')
    return redirect(url_for('inc.visualizar_incs'))

@inc_bp.route('/expiracao_inc')
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

@inc_bp.route('/print_inc_label/<int:inc_id>')
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

    printer_ip = current_app.config.get('PRINTER_IP')
    printer_port = current_app.config.get('PRINTER_PORT')
    
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

    return redirect(url_for('inc.detalhes_inc', inc_id=inc_id))

@inc_bp.route('/export_csv')
@login_required
def export_csv():
    import csv
    
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

@inc_bp.route('/export_pdf/<int:inc_id>')
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
            full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], os.path.basename(foto))
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

@inc_bp.route('/monitorar_fornecedores', methods=['GET', 'POST'])
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

@inc_bp.route('/export_monitor_pdf', methods=['GET'])
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
        return redirect(url_for('inc.monitorar_fornecedores'))

    # Usar context manager para gerenciar o arquivo temporário
    with temp_file(suffix='.png') as temp_path:
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
        return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name='monitor_fornecedores.pdf')