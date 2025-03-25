"""
Script para executar o aplicativo web_inc_manager
"""
import os
import sys
import importlib.util

# Obter o caminho absoluto do diretório atual
base_dir = os.path.abspath(os.path.dirname(__file__))

# Adicionar o caminho ao PYTHONPATH para importações absolutas funcionarem
sys.path.insert(0, base_dir)

try:
    # Importar o módulo app.py da pasta web_inc_manager
    spec = importlib.util.spec_from_file_location(
        "app", 
        os.path.join(base_dir, "web_inc_manager", "app.py")
    )
    app_module = importlib.util.module_from_spec(spec)
    sys.modules["app"] = app_module
    spec.loader.exec_module(app_module)
    
    # Iniciar o servidor Flask
    if __name__ == '__main__':
        print("Iniciando o servidor Flask...")
        app_module.app.run(debug=True, host='0.0.0.0', port=5000)
except Exception as e:
    print(f"Erro ao iniciar o aplicativo: {e}")
    import traceback
    traceback.print_exc() 