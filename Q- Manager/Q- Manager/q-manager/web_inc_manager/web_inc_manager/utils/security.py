import re
from werkzeug.security import generate_password_hash, check_password_hash

def validate_item_format(item):
    """Valida o formato do item - 3 letras maiúsculas, ponto e 5 dígitos"""
    pattern = r'^[A-Z]{3}\.\d{5}$'
    return re.match(pattern, item) is not None

def hash_password(password):
    """Gera um hash seguro para a senha"""
    return generate_password_hash(password)

def verify_password(hashed_password, password):
    """Verifica se a senha corresponde ao hash"""
    return check_password_hash(hashed_password, password)