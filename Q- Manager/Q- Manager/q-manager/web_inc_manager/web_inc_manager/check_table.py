from app import app
from models import db
from sqlalchemy import text

# Executar dentro do contexto da aplicação
with app.app_context():
    print("Verificando a estrutura da tabela registro_nao_conformidade...")
    
    try:
        # Obter informações da tabela
        result = db.session.execute(text("PRAGMA table_info(registro_nao_conformidade);")).fetchall()
        
        # Mostrar informações da tabela
        print("\nEstrutura da tabela registro_nao_conformidade:")
        print("=" * 70)
        print(f"{'CID':<5}{'Nome':<25}{'Tipo':<15}{'NotNull':<10}{'DefaultValue':<20}{'PK'}")
        print("-" * 70)
        
        reincidencia_exists = False
        
        for column in result:
            cid, name, type_, notnull, dflt_value, pk = column
            print(f"{cid:<5}{name:<25}{type_:<15}{notnull:<10}{str(dflt_value):<20}{pk}")
            
            if name == 'reincidencia':
                reincidencia_exists = True
        
        print("=" * 70)
        
        if reincidencia_exists:
            print("\nA coluna 'reincidencia' EXISTE na tabela!")
        else:
            print("\nA coluna 'reincidencia' NÃO EXISTE na tabela!")
            
    except Exception as e:
        print(f"Erro ao verificar a estrutura da tabela: {str(e)}") 