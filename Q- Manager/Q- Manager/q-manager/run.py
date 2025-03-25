"""
Script para executar o aplicativo web_inc_manager
"""
from web_inc_manager.app import app

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 