import os
import json
import re
import chardet
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import db, RotinaInspecao

inspecao_bp = Blueprint('inspecao', __name__)

@inspecao_bp.route('/set_crm_token', methods=['GET', 'POST'])
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
            return redirect(url_for('inspecao.visualizar_registros_inspecao'))
        else:
            flash('Link CRM inválido. Verifique o link.', 'danger')
            return redirect(url_for('inspecao.visualizar_registros_inspecao'))
    
    return render_template('set_crm_token.html')

@inspecao_bp.route('/rotina_inspecao', methods=['GET', 'POST'])
@login_required
def rotina_inspecao():
    # Verificar se o token CRM está definido
    if 'crm_token' not in session:
        flash('Você precisa importar o token do CRM primeiro.')
        return redirect(url_for('inspecao.set_crm_token'))
    
    if request.method == 'POST':
        # Verificar se o arquivo foi enviado
        if 'file' not in request.files:
            flash('Nenhum arquivo selecionado')
            return redirect(request.url)
        
        file = request.files['file']
        
        # Se nenhum arquivo foi selecionado
        if file.filename == '':
            flash('Nenhum arquivo selecionado')
            return redirect(request.url)
        
        # Verificar extensão do arquivo
        if not file.filename.lower().endswith('.lst'):
            flash('Apenas arquivos .lst são permitidos')
            return redirect(request.url)
        
        # Salvar o arquivo temporariamente
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            # Analisar o arquivo .lst
            registros = ler_arquivo_lst(filepath)
            
            if registros:
                # Armazenar os registros analisados na sessão
                session['inspecao_registros'] = registros
                # Armazenar o token CRM atual com os registros
                session['inspecao_crm_token'] = session['crm_token']
                flash(f'Foram importados {len(registros)} registros.')
                return redirect(url_for('inspecao.visualizar_registros_inspecao'))
            else:
                flash('Nenhum registro válido foi importado.')
                return redirect(request.url)
        
        except Exception as e:
            flash(f'Erro ao importar arquivo: {str(e)}')
            return redirect(request.url)
        finally:
            # Limpar o arquivo temporário
            if os.path.exists(filepath):
                os.remove(filepath)
    
    return render_template('rotina_inspecao.html')

@inspecao_bp.route('/visualizar_registros_inspecao', methods=['GET', 'POST'])
@login_required
def visualizar_registros_inspecao():
    registros = session.get('inspecao_registros', [])
    
    if not registros:
        flash('Nenhum registro para inspeção.')
        return redirect(url_for('inspecao.rotina_inspecao'))
    
    scroll_position = None
    if request.method == 'POST':
        action = request.form.get('action')
        item_index = int(request.form.get('item_index'))
        ar = int(request.form.get('ar'))
        scroll_position = request.form.get('scroll_position')
        
        registros_no_grupo = [r for r in registros if r['num_aviso'] == ar]
        
        if 0 <= item_index < len(registros_no_grupo):
            registro_global_index = registros.index(registros_no_grupo[item_index])
            if action == 'inspecionar':
                registros[registro_global_index]['inspecionado'] = True
                registros[registro_global_index]['adiado'] = False
            elif action == 'adiar':
                registros[registro_global_index]['inspecionado'] = False
                registros[registro_global_index]['adiado'] = True
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
    if scroll_position:
        return redirect(url_for('inspecao.visualizar_registros_inspecao', scroll_position=scroll_position))
    
    return render_template('visualizar_registros_inspecao.html', grupos_ar=grupos_ar_ordenados)

@inspecao_bp.route('/listar_rotinas_inspecao')
@login_required
def listar_rotinas_inspecao():
    rotinas = RotinaInspecao.query.all()
    # Converter registros de JSON para Python para cada rotina
    for rotina in rotinas:
        rotina.registros_python = json.loads(rotina.registros)
    return render_template('listar_rotinas_inspecao.html', rotinas=rotinas)

@inspecao_bp.route('/salvar_rotina_inspecao', methods=['POST'])
@login_required
def salvar_rotina_inspecao():
    registros = session.get('inspecao_registros', [])
    
    if not registros:
        flash('Nenhum registro para salvar.')
        return redirect(url_for('inspecao.rotina_inspecao'))
    
    # Verificar se todos os registros foram processados
    for registro in registros:
        inspecionado = registro.get('inspecionado', False)
        adiado = registro.get('adiado', False)
        if not inspecionado and not adiado:
            flash('Todos os registros devem ser inspecionados ou adiados antes de salvar a rotina.', 'danger')
            return redirect(url_for('inspecao.visualizar_registros_inspecao'))
    
    rotina = RotinaInspecao(
        inspetor_id=current_user.id,
        registros=json.dumps(registros)
    )
    db.session.add(rotina)
    db.session.commit()
    
    flash('Rotina de inspeção salva com sucesso!', 'success')
    session.pop('inspecao_registros', None)
    return redirect(url_for('main_menu'))

def ler_arquivo_lst(caminho):
    """
    Lê o arquivo .lst, filtra e processa os registros.
    """
    registros = []
    
    # Detectar codificação
    with open(caminho, "rb") as f:
        conteudo = f.read()
    encoding = chardet.detect(conteudo)['encoding']
    
    try:
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
                    # Logar ou tratar o erro apropriadamente
                    continue
        
        return registros
    
    except Exception as e:
        # Logar ou tratar o erro apropriadamente
        print(f"Erro ao ler o arquivo: {e}")
        return []