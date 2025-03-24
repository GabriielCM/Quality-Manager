# Sistema de Gestão de Qualidade (Q-Manager)

O Q-Manager é um sistema de gestão de qualidade desenvolvido para gerenciar informações de não-conformidade (INCs), fornecedores, inspeções de qualidade e outros processos relacionados à gestão da qualidade.

## Características Principais

- Gestão de Informações de Não-Conformidade (INCs)
- Cadastro e gerenciamento de fornecedores
- Rotinas de inspeção de qualidade
- Controle de prateleiras não-conformes
- Solicitações de faturamento
- Registro de atividades de usuários
- Relatórios e estatísticas

## Tecnologias Utilizadas

- **Backend**: Flask (Python)
- **Banco de Dados**: SQLAlchemy (SQLite em desenvolvimento, configurável para PostgreSQL/MySQL em produção)
- **Frontend**: HTML5, CSS3, JavaScript (Bootstrap)
- **Segurança**: Werkzeug, Flask-Login
- **Migrações**: Flask-Migrate (Alembic)

## Requisitos

- Python 3.9 ou superior
- Pip (gerenciador de pacotes Python)
- Dependências listadas em `requirements.txt`

## Instalação

1. Clone o repositório:
   ```
   git clone https://github.com/seu-usuario/q-manager.git
   cd q-manager
   ```

2. Crie e ative um ambiente virtual:
   ```
   python -m venv venv
   # No Windows:
   venv\Scripts\activate
   # No Linux/Mac:
   source venv/bin/activate
   ```

3. Instale as dependências:
   ```
   pip install -r requirements.txt
   ```

4. Configure as variáveis de ambiente (ou crie um arquivo `.env`):
   ```
   export FLASK_APP=app.py
   export FLASK_ENV=development
   export SECRET_KEY=sua_chave_secreta_aqui
   ```

5. Inicialize o banco de dados:
   ```
   flask db init
   flask db migrate -m "Initial migration"
   flask db upgrade
   ```

6. Execute o aplicativo:
   ```
   flask run
   ```

7. Acesse a aplicação em `http://localhost:5000`

## Configuração para Produção

Para configurar o sistema em ambiente de produção, siga estes passos adicionais:

1. Configure as variáveis de ambiente adequadamente:
   ```
   export FLASK_ENV=production
   export SECRET_KEY=chave_secreta_segura_gerada
   export DATABASE_URL=postgresql://usuario:senha@localhost/q_manager
   ```

2. Use um servidor WSGI como o Gunicorn:
   ```
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```

3. Configure um proxy reverso (Nginx ou Apache) para servir a aplicação.

## Estrutura do Projeto

- `app.py`: Arquivo principal do aplicativo Flask
- `config.py`: Configurações da aplicação
- `models.py`: Modelos do banco de dados
- `utils.py`: Funções utilitárias
- `auth.py`: Rotas de autenticação
- `inc_routes.py`: Rotas para gerenciamento de INCs
- `fornecedor_routes.py`: Rotas para gerenciamento de fornecedores
- `prateleira_routes.py`: Rotas para gerenciamento de prateleiras não-conformes
- `inspecao_routes.py`: Rotas para inspeções de qualidade
- `faturamento_routes.py`: Rotas para solicitações de faturamento
- `log_routes.py`: Rotas para logs e atividades
- `api_routes.py`: Rotas de API para integração
- `templates/`: Templates HTML
- `static/`: Arquivos estáticos (CSS, JS, imagens)

## Segurança

Este sistema implementa diversas medidas de segurança:

- Autenticação de usuários com Flask-Login
- Senhas armazenadas com hash seguro
- Proteção contra CSRF
- Validação de formulários e entradas
- Sanitização de saídas
- Controle de acesso baseado em permissões
- Logging de atividades

## Contribuição

Se deseja contribuir com o projeto, siga estas etapas:

1. Faça um fork do repositório
2. Crie uma branch para sua feature (`git checkout -b feature/nova-funcionalidade`)
3. Faça commit das mudanças (`git commit -am 'Adiciona nova funcionalidade'`)
4. Faça push para a branch (`git push origin feature/nova-funcionalidade`)
5. Crie um novo Pull Request

## Licença

Este projeto está licenciado sob a licença MIT - veja o arquivo LICENSE para mais detalhes.

## Contato

Para suporte ou dúvidas, entre em contato pelo email: suporte@empresa.com.br 