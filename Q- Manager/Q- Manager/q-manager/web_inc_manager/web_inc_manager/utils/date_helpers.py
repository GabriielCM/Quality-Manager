from datetime import datetime

# Formatos utilizados no sistema
DATE_FORMAT = "%d-%m-%Y"
DATE_FORMAT_HTML = "%Y-%m-%d"

def format_date_for_db(date_str):
    """Converte uma string de data para o formato armazenado no banco"""
    if isinstance(date_str, str):
        # Verifica se o formato é YYYY-MM-DD (do input HTML)
        if len(date_str) == 10 and date_str[4] == '-':
            date_obj = datetime.strptime(date_str, DATE_FORMAT_HTML)
            return date_obj.strftime(DATE_FORMAT)
        return date_str
    elif isinstance(date_str, datetime):
        return date_str.strftime(DATE_FORMAT)
    return None

def parse_date(date_str):
    """Converte uma string de data para um objeto datetime"""
    if not date_str:
        return None
    try:
        # Tenta formato DD-MM-YYYY
        return datetime.strptime(date_str, DATE_FORMAT)
    except ValueError:
        try:
            # Tenta formato YYYY-MM-DD
            return datetime.strptime(date_str, DATE_FORMAT_HTML)
        except ValueError:
            return None

def date_to_html_input(date_str):
    """Converte uma data no formato do banco para o formato input HTML"""
    if not date_str:
        return ""
    date_obj = parse_date(date_str)
    if date_obj:
        return date_obj.strftime(DATE_FORMAT_HTML)
    return ""