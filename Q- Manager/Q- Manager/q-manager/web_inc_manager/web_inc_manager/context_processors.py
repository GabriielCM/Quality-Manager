"""
Processadores de contexto global do Jinja2 para a aplicação
"""
from datetime import datetime
from models import LayoutSetting

def inject_now():
    """Injeta a função now() no contexto global do Jinja2"""
    return {'now': datetime.utcnow}

def inject_settings(app):
    """Injeta as configurações no contexto global do Jinja2"""
    settings = {s.element: s for s in LayoutSetting.query.all()}
    return dict(settings=settings, config=app.config) 