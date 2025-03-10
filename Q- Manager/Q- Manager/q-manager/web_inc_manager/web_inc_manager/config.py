import os
import secrets

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(16)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///web_inc_manager.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static/uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    PRINTER_IP = os.environ.get('PRINTER_IP') or '192.168.1.48'
    PRINTER_PORT = int(os.environ.get('PRINTER_PORT') or 9100)
    CRM_BASE_URL = os.environ.get('CRM_BASE_URL') or 'http://192.168.1.47/crm/index.php?route=engenharia/produto/update'
    ITEMS_PER_PAGE = 10