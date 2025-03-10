import os
import tempfile
import contextlib
from werkzeug.utils import secure_filename
from flask import current_app

@contextlib.contextmanager
def temp_file(suffix=None):
    """Context manager para criar e limpar automaticamente arquivos temporários"""
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        yield path
    finally:
        os.close(fd)
        if os.path.exists(path):
            os.remove(path)

def save_uploaded_file(file, allowed_extensions=None):
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
        
    # Extrai o nome do arquivo do caminho completo
    filename = os.path.basename(filepath)
    
    # Constrói o caminho completo
    full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    
    # Verifica se o arquivo está na pasta de uploads
    if not os.path.realpath(full_path).startswith(
            os.path.realpath(current_app.config['UPLOAD_FOLDER'])):
        return False
    
    # Remove o arquivo se existir
    if os.path.exists(full_path):
        os.remove(full_path)
        return True
    return False