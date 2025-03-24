import os
import re
import json
import chardet
import logging
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from flask import request, current_app
from functools import wraps
from typing import List, Dict, Any, Optional, Union, Tuple

def log_user_activity(user_id: int, action: str, entity_type: str, entity_id: Optional[int] = None, 
                      details: Optional[Dict[str, Any]] = None) -> bool:
    """
    Registra uma ação do usuário no sistema
    
    Args:
        user_id (int): ID do usuário que realizou a ação
        action (str): Tipo de ação (login, logout, edit, delete, create, etc.)
        entity_type (str): Tipo de entidade afetada (user, inc, fornecedor, etc.)
        entity_id (int, optional): ID da entidade afetada
        details (dict, optional): Detalhes adicionais da ação
        
    Returns:
        bool: True se o log foi registrado com sucesso, False caso contrário
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
        return True
        
    except Exception as e:
        # Não deixar um erro de log interromper a operação principal
        current_app.logger.error(f"Erro ao registrar atividade do usuário: {str(e)}")
        db.session.rollback()
        return False

def display_file_preview(filepath: str, num_lines: int = 20) -> List[str]:
    """
    Exibe uma prévia do conteúdo do arquivo para depuração
    
    Args:
        filepath (str): Caminho do arquivo
        num_lines (int): Número de linhas a serem exibidas
        
    Returns:
        List[str]: Lista com as linhas lidas
    """
    lines = []
    try:
        # Verificar se o arquivo está dentro do diretório permitido
        if not os.path.realpath(filepath).startswith(os.path.realpath(current_app.config['UPLOAD_FOLDER'])):
            current_app.logger.error(f"Tentativa de ler arquivo fora do diretório permitido: {filepath}")
            return []
            
        # Detectar codificação
        with open(filepath, 'rb') as f:
            raw_data = f.read()
            encoding = chardet.detect(raw_data)['encoding'] or 'latin-1'
        
        with open(filepath, 'r', encoding=encoding) as file:
            lines = [line.rstrip() for line in file.readlines()[:num_lines]]
            
        current_app.logger.debug(f"Prévia do arquivo ({encoding}):")
        for i, line in enumerate(lines):
            current_app.logger.debug(f"{i+1:3d}: {line}")
            
        return lines
            
    except Exception as e:
        current_app.logger.error(f"Erro ao ler prévia do arquivo: {str(e)}")
        return []

def diagnosticar_linha_lst(line: str, linha_numero: int) -> Dict[str, Any]:
    """
    Diagnostica uma linha do arquivo LST para ajudar na depuração
    
    Args:
        line (str): Linha a ser diagnosticada
        linha_numero (int): Número da linha no arquivo
        
    Returns:
        Dict[str, Any]: Dicionário com os resultados do diagnóstico
    """
    results = {
        'length': 0,
        'content': '',
        'leading_spaces': 0,
        'patterns': {
            'pattern1': False,
            'pattern2': False,
            'pattern3': False
        },
        'matches': {}
    }
    
    try:
        results['length'] = len(line)
        results['content'] = line
        
        # Contar espaços iniciais
        results['leading_spaces'] = len(line) - len(line.lstrip(' '))
        
        # Testar expressões regulares específicas
        item_pattern1 = re.compile(r'\s+([A-Z]{3}\.\d{5})\s+')
        item_pattern2 = re.compile(r'\s{20,}([A-Z]{3}\.\d{5})')
        item_pattern3 = re.compile(r'\s+([A-Z]{3}\.\d{5})\s+(.*?)\s+(\d+(?:\.\d+)*,\d+)\s+\d+,\d+\s+(\d{2}/\d{2}/\d{4})')
        
        m1 = item_pattern1.search(line)
        m2 = item_pattern2.match(line)
        m3 = item_pattern3.search(line)
        
        results['patterns']['pattern1'] = bool(m1)
        results['patterns']['pattern2'] = bool(m2)
        results['patterns']['pattern3'] = bool(m3)
        
        if m1:
            results['matches']['pattern1'] = m1.group(1)
            
        if m2:
            results['matches']['pattern2'] = m2.group(1)
            
        if m3:
            results['matches']['pattern3'] = {
                'item': m3.group(1),
                'descricao': m3.group(2),
                'quantidade': m3.group(3),
                'data': m3.group(4)
            }
        
        # Registrar resultados no log
        current_app.logger.debug(f"Diagnóstico da linha {linha_numero}: {json.dumps(results, ensure_ascii=False)}")
        
        return results
    
    except Exception as e:
        current_app.logger.error(f"Erro no diagnóstico da linha {linha_numero}: {str(e)}")
        return results

def validate_item_format(item: str) -> bool:
    """
    Valida o formato do item - 3 letras maiúsculas, ponto e 5 dígitos
    
    Args:
        item (str): Código do item a ser validado
        
    Returns:
        bool: True se o formato for válido, False caso contrário
    """
    pattern = r'^[A-Z]{3}\.\d{5}$'
    return re.match(pattern, item) is not None

def format_date_for_db(date_str: Union[str, datetime]) -> Optional[str]:
    """
    Converte uma string de data para o formato armazenado no banco (DD-MM-YYYY)
    
    Args:
        date_str (Union[str, datetime]): Data no formato string ou objeto datetime
        
    Returns:
        Optional[str]: Data formatada ou None se inválida
    """
    if isinstance(date_str, str):
        # Verifica se o formato é YYYY-MM-DD (do input HTML)
        if len(date_str) == 10 and date_str[4] == '-':
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                return date_obj.strftime('%d-%m-%Y')
            except ValueError:
                current_app.logger.error(f"Erro ao converter data: {date_str}")
                return None
        return date_str
    elif isinstance(date_str, datetime):
        return date_str.strftime('%d-%m-%Y')
    return None

def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """
    Converte uma string de data para um objeto datetime
    
    Args:
        date_str (Optional[str]): String de data a ser convertida
        
    Returns:
        Optional[datetime]: Objeto datetime ou None se inválido
    """
    if not date_str:
        return None
    
    formats = ['%d-%m-%Y', '%Y-%m-%d', '%d/%m/%Y']
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    current_app.logger.error(f"Formato de data não reconhecido: {date_str}")
    return None

def save_file(file, allowed_extensions: Optional[List[str]] = None) -> Optional[str]:
    """
    Salva um arquivo enviado com verificação de segurança
    
    Args:
        file: Objeto de arquivo do Flask
        allowed_extensions (Optional[List[str]]): Lista de extensões permitidas
        
    Returns:
        Optional[str]: Caminho relativo do arquivo salvo ou None se falhar
    """
    if not file or file.filename == '':
        return None
        
    # Se não forem especificadas extensões, usar as padrão da config
    if allowed_extensions is None:
        allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', 
                                                  {'pdf', 'png', 'jpg', 'jpeg', 'gif'})
    
    # Extrair extensão e validar
    extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    if allowed_extensions and extension not in allowed_extensions:
        current_app.logger.warning(f"Tentativa de upload de arquivo com extensão não permitida: {extension}")
        return None
    
    # Gerar nome de arquivo seguro com timestamp para evitar colisões
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    original_filename = secure_filename(file.filename)
    filename = f"{timestamp}_{original_filename}"
    
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    current_app.logger.info(f"Arquivo salvo com sucesso: {filepath}")
    return f"uploads/{filename}"

def remove_file(filepath: str) -> bool:
    """
    Remove um arquivo com verificação de segurança
    
    Args:
        filepath (str): Caminho relativo do arquivo a ser removido
        
    Returns:
        bool: True se o arquivo foi removido com sucesso, False caso contrário
    """
    if not filepath:
        return False
        
    # Extrair apenas o nome do arquivo da URL/caminho
    filename = os.path.basename(filepath)
    
    # Verificar se é um arquivo de upload
    if not filepath.startswith('uploads/') and not filepath.startswith('/uploads/'):
        current_app.logger.warning(f"Tentativa de remover arquivo fora do diretório de uploads: {filepath}")
        return False
        
    full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    
    # Verificar se o caminho está dentro do diretório permitido
    if not os.path.realpath(full_path).startswith(
            os.path.realpath(current_app.config['UPLOAD_FOLDER'])):
        current_app.logger.warning(f"Tentativa de remover arquivo fora do diretório permitido: {full_path}")
        return False
    
    if os.path.exists(full_path):
        os.remove(full_path)
        current_app.logger.info(f"Arquivo removido com sucesso: {full_path}")
        return True
        
    current_app.logger.warning(f"Arquivo não encontrado para remoção: {full_path}")
    return False

def ler_arquivo_lst(caminho: str) -> List[Dict[str, Any]]:
    """
    Lê o arquivo .lst, filtra e processa os registros.
    
    Args:
        caminho (str): Caminho do arquivo .lst
        
    Returns:
        List[Dict[str, Any]]: Lista de registros processados
    """
    registros = []
    
    try:
        # Verificar se o arquivo existe
        if not os.path.exists(caminho):
            current_app.logger.error(f"Arquivo não encontrado: {caminho}")
            return registros
            
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
        
        current_app.logger.info(f"Usando codificação: {encoding}")
        
        with open(caminho, "r", encoding=encoding) as arquivo:
            for linha_num, linha in enumerate(arquivo, 1):
                linha_str = linha.strip()
                if not linha_str:
                    continue
                
                try:
                    # Dividir por múltiplos espaços
                    campos = re.split(r"\s{2,}", linha_str)
                    
                    # Validar e processar colunas
                    if len(campos) < 9:
                        continue
                    
                    # Consolidar colunas se mais de 9
                    while len(campos) > 9:
                        campos[3] = campos[3] + " " + campos[4]
                        del campos[4]
                    
                    # Analisar dados
                    data_entrada = campos[0]
                    
                    try:
                        num_aviso = int(campos[1])
                    except ValueError:
                        current_app.logger.warning(f"Número de aviso inválido na linha {linha_num}: {campos[1]}")
                        continue
                    
                    # Analisar código do item
                    parts_item = re.split(r"\s+", campos[2], maxsplit=1)
                    item_code = parts_item[1].strip() if len(parts_item) > 1 else parts_item[0].strip()
                    
                    # Validar formato do item
                    if not validate_item_format(item_code):
                        current_app.logger.warning(f"Formato de item inválido na linha {linha_num}: {item_code}")
                        continue
                    
                    descricao = campos[3]
                    
                    # Analisar quantidade
                    try:
                        qtd_str = campos[5].replace(",", ".")
                        qtd_recebida = float(qtd_str)
                    except ValueError:
                        current_app.logger.warning(f"Quantidade inválida na linha {linha_num}: {campos[5]}")
                        continue
                    
                    # Analisar fornecedor
                    splitted_6 = re.split(r"\s+", campos[6], maxsplit=1)
                    fornecedor = splitted_6[1] if len(splitted_6) == 2 else "DESCONHECIDO"
                    
                    # Analisar O.C.
                    try:
                        oc_str = campos[-1].strip()
                        oc_int = int(oc_str)
                    except ValueError:
                        current_app.logger.warning(f"OC inválida na linha {linha_num}: {campos[-1]}")
                        continue
                    
                    # Pular se O.C. é 0
                    if oc_int == 0:
                        continue
                    
                    # Criar registro processado
                    registro = {
                        "fornecedor": fornecedor,
                        "razao_social": fornecedor,
                        "item": item_code,
                        "descricao": descricao,
                        "data_entrada": data_entrada,
                        "num_aviso": num_aviso,
                        "qtd_recebida": qtd_recebida,
                        "oc": oc_int
                    }
                    
                    registros.append(registro)
                except Exception as e:
                    current_app.logger.error(f"Erro ao processar linha {linha_num}: {str(e)}")
                    continue
        
        current_app.logger.info(f"Processados {len(registros)} registros do arquivo LST")
        return registros
    
    except Exception as e:
        current_app.logger.error(f"Erro ao ler arquivo LST: {str(e)}")
        return registros

def limpar_arquivos_temporarios(idade_maxima_horas: int = 24) -> Tuple[int, int]:
    """
    Remove arquivos temporários antigos do diretório de uploads
    
    Args:
        idade_maxima_horas (int): Idade máxima em horas que um arquivo pode ter
        
    Returns:
        Tuple[int, int]: Quantidade de arquivos analisados e removidos
    """
    try:
        now = datetime.now()
        total_arquivos = 0
        arquivos_removidos = 0
        
        upload_dir = current_app.config['UPLOAD_FOLDER']
        
        for filename in os.listdir(upload_dir):
            if os.path.isfile(os.path.join(upload_dir, filename)):
                total_arquivos += 1
                file_path = os.path.join(upload_dir, filename)
                file_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
                
                # Calcular idade do arquivo em horas
                idade_horas = (now - file_modified).total_seconds() / 3600
                
                if idade_horas > idade_maxima_horas:
                    # Verificar se não é um arquivo permanente
                    if 'permanent' not in filename.lower():
                        try:
                            os.remove(file_path)
                            arquivos_removidos += 1
                            current_app.logger.info(f"Arquivo temporário removido: {filename} (idade: {idade_horas:.1f}h)")
                        except Exception as e:
                            current_app.logger.error(f"Erro ao remover arquivo temporário: {filename} - {str(e)}")
        
        current_app.logger.info(f"Limpeza de arquivos: {arquivos_removidos} removidos de um total de {total_arquivos}")
        return total_arquivos, arquivos_removidos
    
    except Exception as e:
        current_app.logger.error(f"Erro na limpeza de arquivos temporários: {str(e)}")
        return 0, 0

def gerar_relatorio_atividade(dias: int = 7) -> Dict[str, Any]:
    """
    Gera um relatório de atividade do sistema nos últimos dias
    
    Args:
        dias (int): Número de dias a considerar no relatório
        
    Returns:
        Dict[str, Any]: Dicionário com estatísticas de atividade
    """
    from models import UserActivityLog, User, INC, db
    
    try:
        data_inicial = datetime.now() - timedelta(days=dias)
        
        # Atividades por usuário
        atividades_por_usuario = db.session.query(
            UserActivityLog.user_id,
            User.username,
            db.func.count(UserActivityLog.id).label('total')
        ).join(User).filter(
            UserActivityLog.timestamp >= data_inicial
        ).group_by(
            UserActivityLog.user_id,
            User.username
        ).order_by(
            db.func.count(UserActivityLog.id).desc()
        ).all()
        
        # Atividades por tipo
        atividades_por_tipo = db.session.query(
            UserActivityLog.entity_type,
            db.func.count(UserActivityLog.id).label('total')
        ).filter(
            UserActivityLog.timestamp >= data_inicial
        ).group_by(
            UserActivityLog.entity_type
        ).order_by(
            db.func.count(UserActivityLog.id).desc()
        ).all()
        
        # Atividades por ação
        atividades_por_acao = db.session.query(
            UserActivityLog.action,
            db.func.count(UserActivityLog.id).label('total')
        ).filter(
            UserActivityLog.timestamp >= data_inicial
        ).group_by(
            UserActivityLog.action
        ).order_by(
            db.func.count(UserActivityLog.id).desc()
        ).all()
        
        # Total de atividades por dia
        atividades_por_dia = db.session.query(
            db.func.date(UserActivityLog.timestamp).label('dia'),
            db.func.count(UserActivityLog.id).label('total')
        ).filter(
            UserActivityLog.timestamp >= data_inicial
        ).group_by(
            db.func.date(UserActivityLog.timestamp)
        ).order_by(
            db.func.date(UserActivityLog.timestamp)
        ).all()
        
        # Formatar resultados
        relatorio = {
            'periodo': {
                'inicio': data_inicial.strftime('%d/%m/%Y'),
                'fim': datetime.now().strftime('%d/%m/%Y'),
                'dias': dias
            },
            'usuarios': [
                {'usuario': username, 'id': user_id, 'total': total}
                for user_id, username, total in atividades_por_usuario
            ],
            'tipos': [
                {'tipo': entity_type, 'total': total}
                for entity_type, total in atividades_por_tipo
            ],
            'acoes': [
                {'acao': action, 'total': total}
                for action, total in atividades_por_acao
            ],
            'diario': [
                {'data': dia.strftime('%d/%m/%Y'), 'total': total}
                for dia, total in atividades_por_dia
            ],
            'total': sum(total for _, total in atividades_por_dia)
        }
        
        return relatorio
    
    except Exception as e:
        current_app.logger.error(f"Erro ao gerar relatório de atividade: {str(e)}")
        return {
            'erro': str(e),
            'periodo': {'dias': dias}
        }