# Q-Manager - Sistema de Gestão de Qualidade

O Q-Manager é um sistema para gestão de qualidade que permite controlar Informes de Não Conformidade (INCs), Inspeções, Fornecedores, Solicitações de Faturamento e Prateleiras Não Conformes.

## Nova Estrutura do Projeto

A aplicação foi reestruturada para seguir um padrão mais modular, separando as funcionalidades em arquivos específicos para facilitar a manutenção:

```
web_inc_manager/
├── app.py                # Arquivo principal (simplificado, importa dos módulos)
├── config.py             # Configuração
├── models.py             # Modelos de banco de dados
├── auth.py               # Rotas de autenticação
├── inc_routes.py         # Rotas de gerenciamento de INC
├── fornecedor_routes.py  # Rotas de gerenciamento de fornecedores
├── prateleira_routes.py  # Rotas de prateleira não conforme
├── inspecao_routes.py    # Rotas de inspeção
├── faturamento_routes.py # Rotas de solicitação de faturamento
├── log_routes.py         # Rotas de logs de atividade
├── api_routes.py         # Endpoints da API
├── utils.py              # Funções utilitárias gerais
├── static/               # Arquivos estáticos
└── templates/            # Templates
```

## Instruções para Migração

Para migrar da estrutura anterior (monolítica) para a estrutura modular:

1. **Backup do Projeto**: Crie uma cópia de segurança da versão atual
2. **Preparar a Nova Estrutura**: Crie os novos arquivos conforme a estrutura acima
3. **Migrar o Banco de Dados**: Não é necessário alterar a estrutura do banco de dados
4. **Testar**: Execute a aplicação e teste todas as funcionalidades

## Funcionalidades Principais

- **Autenticação**: Gerenciamento de usuários e login
- **INCs**: Gestão de Informes de Não Conformidade
- **Fornecedores**: Cadastro e monitoramento de fornecedores
- **Prateleira Não Conforme**: Controle de itens não conformes
- **Inspeção**: Rotinas e planos de inspeção
- **Faturamento**: Solicitações de faturamento
- **Logs**: Registro e visualização de atividades no sistema

## Requisitos

- Python 3.8+
- Flask 2.3.3
- Flask-SQLAlchemy 3.0.5
- Flask-Login 0.6.3
- Reportlab 4.0.6
- Pillow 10.0.1
- Chardet 5.2.0

## Instalação

1. Clone o repositório:
```
git clone [URL_DO_REPOSITORIO]
```

2. Crie um ambiente virtual:
```
python -m venv venv
```

3. Ative o ambiente virtual:
```
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

4. Instale as dependências:
```
pip install -r requirements.txt
```

5. Execute a aplicação:
```
python app.py
```

## Vantagens da Nova Estrutura

- **Manutenção mais fácil**: Cada módulo tem responsabilidades bem definidas
- **Código mais organizado**: Separação clara de funcionalidades
- **Testabilidade melhorada**: Módulos isolados são mais fáceis de testar
- **Escalabilidade**: Facilidade para adicionar novas funcionalidades
- **Trabalho em equipe**: Diferentes desenvolvedores podem trabalhar em diferentes módulos
- **Melhor legibilidade**: Arquivos menores são mais fáceis de entender

## Guia de Blueprints

A nova estrutura utiliza Flask Blueprints para organizar as rotas:

- `auth_bp`: Rotas relacionadas à autenticação (/auth/*)
- `inc_bp`: Rotas para gestão de INCs (/inc/*)
- `fornecedor_bp`: Rotas para gestão de fornecedores (/fornecedor/*)
- `prateleira_bp`: Rotas para controle da prateleira não conforme (/prateleira/*)
- `inspecao_bp`: Rotas para rotinas de inspeção (/inspecao/*)
- `faturamento_bp`: Rotas para solicitações de faturamento (/faturamento/*)
- `log_bp`: Rotas para visualização de logs (/log/*)
- `api_bp`: Endpoints da API (/api/*)

## Notas para Desenvolvedores

- Os módulos compartilham o mesmo modelo de banco de dados definido em `models.py`
- Funções utilitárias comuns estão em `utils.py`
- Configurações da aplicação estão centralizadas em `config.py`
- O arquivo principal `app.py` inicializa a aplicação e registra os blueprints