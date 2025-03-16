import os
import re
import json
import chardet
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import request, current_app

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
    from models import UserActivityLog, db
    
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
        current_app.logger.error(f"Erro ao registrar atividade do usuário: {str(e)}")
        db.session.rollback()

def display_file_preview(filepath, num_lines=20):
    """Exibe uma prévia do conteúdo do arquivo para depuração"""
    try:
        with open(filepath, 'rb') as f:
            raw_data = f.read()
            encoding = chardet.detect(raw_data)['encoding'] or 'latin-1'
        
        with open(filepath, 'r', encoding=encoding) as file:
            lines = [line.rstrip() for line in file.readlines()[:num_lines]]
            
        current_app.logger.debug(f"Prévia do arquivo ({encoding}):")
        for i, line in enumerate(lines):
            current_app.logger.debug(f"{i+1:3d}: {line}")
            
    except Exception as e:
        current_app.logger.error(f"Erro ao ler prévia do arquivo: {str(e)}")

def diagnosticar_linha_lst(line, linha_numero):
    """Diagnostica uma linha do arquivo LST para ajudar na depuração"""
    try:
        current_app.logger.debug(f"Diagnóstico da linha {linha_numero}:")
        current_app.logger.debug(f"  Comprimento: {len(line)} caracteres")
        current_app.logger.debug(f"  Conteúdo: '{line}'")
        
        # Contar espaços iniciais
        espacos_iniciais = len(line) - len(line.lstrip(' '))
        current_app.logger.debug(f"  Espaços iniciais: {espacos_iniciais}")
        
        # Exibir caracteres posicionalmente (índices)
        posicoes = ""
        for i in range(0, min(130, len(line)), 10):
            posicoes += f"{i:10d}"
        current_app.logger.debug(f"  Posições: {posicoes}")
        
        # Exibir os primeiros caracteres em detalhes
        chars = ""
        for i in range(min(130, len(line))):
            chars += line[i]
        current_app.logger.debug(f"  Chars:    {chars}")
        
        # Testar expressões regulares específicas
        item_pattern1 = re.compile(r'\s+([A-Z]{3}\.\d{5})\s+')
        item_pattern2 = re.compile(r'\s{20,}([A-Z]{3}\.\d{5})')
        item_pattern3 = re.compile(r'\s+([A-Z]{3}\.\d{5})\s+(.*?)\s+(\d+(?:\.\d+)*,\d+)\s+\d+,\d+\s+(\d{2}/\d{2}/\d{4})')
        
        m1 = item_pattern1.search(line)
        m2 = item_pattern2.match(line)
        m3 = item_pattern3.search(line)
        
        current_app.logger.debug(f"  Padrão 1 (r'\\s+([A-Z]{{3}}\\.\\d{{5}})\\s+'): {m1.group(1) if m1 else 'Não corresponde'}")
        current_app.logger.debug(f"  Padrão 2 (r'\\s{{20,}}([A-Z]{{3}}\\.\\d{{5}})'): {m2.group(1) if m2 else 'Não corresponde'}")
        current_app.logger.debug(f"  Padrão 3 (completo): {bool(m3)}")
        
        if m3:
            current_app.logger.debug(f"    Item: {m3.group(1)}")
            current_app.logger.debug(f"    Descrição: {m3.group(2)}")
            current_app.logger.debug(f"    Quantidade: {m3.group(3)}")
            current_app.logger.debug(f"    Data: {m3.group(4)}")
    
    except Exception as e:
        current_app.logger.error(f"Erro no diagnóstico da linha {linha_numero}: {str(e)}")

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
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    return f"uploads/{filename}"

def remove_file(filepath):
    """Remove um arquivo com verificação de segurança"""
    if not filepath:
        return False
        
    filename = os.path.basename(filepath)
    full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    
    if not os.path.realpath(full_path).startswith(
            os.path.realpath(current_app.config['UPLOAD_FOLDER'])):
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