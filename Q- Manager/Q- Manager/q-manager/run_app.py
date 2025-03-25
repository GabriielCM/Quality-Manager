#!/usr/bin/env python
"""
Script para iniciar a aplicação web_inc_manager
"""
import os
import sys
import importlib.util

# Obter o caminho absoluto do diretório atual e adicionar ao PYTHONPATH
base_dir = os.path.abspath(os.path.dirname(__file__))
web_inc_manager_dir = os.path.join(base_dir, 'web_inc_manager')
sys.path.insert(0, base_dir)
sys.path.insert(0, web_inc_manager_dir)

# Vamos corrigir as importações modificando temporariamente o app.py
app_path = os.path.join(web_inc_manager_dir, "web_inc_manager", "app.py")

try:
    print("Iniciando a aplicação...")
    
    # Carregar o módulo app.py diretamente
    os.chdir(web_inc_manager_dir)  # Mudar para o diretório web_inc_manager
    
    sys.path.append(os.path.join(web_inc_manager_dir, "web_inc_manager"))
    
    # Importar o módulo app.py diretamente
    from web_inc_manager import app
    
    print("Servidor iniciando em http://127.0.0.1:5000/")
    print("Use as seguintes credenciais para acessar:")
    print("Usuário: admin")
    print("Senha: SenhaComplexaInicial123!")
    
    # Iniciar o aplicativo Flask
    if __name__ == '__main__':
        app.run(debug=True, host='0.0.0.0', port=5000)
except Exception as e:
    print(f"Erro ao iniciar o aplicativo: {e}")
    import traceback
    traceback.print_exc() 