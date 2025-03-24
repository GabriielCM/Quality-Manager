import os
import secrets
from datetime import timedelta

class Config:
    # Segurança - Gerando uma chave secreta aleatória se não existir no ambiente
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    
    # Configurações do banco de dados
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///web_inc_manager.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configurações de upload e arquivos
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static/uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'csv', 'txt', 'xlsx'}
    
    # Configurações de hardware/integração
    PRINTER_IP = os.environ.get('PRINTER_IP') or '192.168.1.48'
    PRINTER_PORT = int(os.environ.get('PRINTER_PORT') or 9100)
    CRM_BASE_URL = os.environ.get('CRM_BASE_URL') or 'http://192.168.1.47/crm/index.php?route=engenharia/produto/update'
    
    # Configurações de paginação
    ITEMS_PER_PAGE = int(os.environ.get('ITEMS_PER_PAGE') or 10)
    
    # Tempo limite para manter arquivos temporários (em horas)
    TEMP_FILE_TTL = int(os.environ.get('TEMP_FILE_TTL') or 24)
    
    # Configuração para modo de desenvolvimento
    DEBUG = os.environ.get('FLASK_DEBUG') == '1'
    
    # Configurações de sessão
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    PERMANENT_SESSION_LIFETIME = timedelta(hours=4)
    
    # Configurações de log
    LOG_LEVEL = os.environ.get('LOG_LEVEL') or 'INFO'
    LOG_FORMAT = '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    LOG_FILE = os.environ.get('LOG_FILE') or 'app.log'
    LOG_MAX_SIZE = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5


class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    DEBUG = False
    
    # Em produção, a SECRET_KEY deve ser obrigatoriamente definida no ambiente
    @property
    def SECRET_KEY(self):
        key = os.environ.get('SECRET_KEY')
        if not key:
            raise ValueError("A variável de ambiente SECRET_KEY deve ser definida em produção")
        return key


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


# Configuração a ser usada baseada na variável de ambiente
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig
}

# Configuração padrão
def get_config():
    env = os.environ.get('FLASK_ENV', 'development')
    return config_by_name.get(env, DevelopmentConfig)