# Execução e implantação

## Requisitos

- Python 3.11 ou superior.
- PostgreSQL com conexão definida em `DATABASE_URL`.
- Dependências de [`requirements.txt`](../requirements.txt).

## Execução local (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

A conferência desta revisão utilizou Python 3.12, PostgreSQL 16.2, Streamlit 1.67.0, SQLAlchemy 2.1.9 e psycopg 3.3.9. Usamos o prefixo `postgresql+psycopg://` no exemplo de conexão.

A configuração local do banco fica no arquivo `.env`, que não integra o controle de versões. O modelo de configuração está em [`.env.example`](../.env.example).

```powershell
python -m streamlit run app.py
```

## Testes

```powershell
python -m pip install -r requirements-dev.txt
python -m compileall -q app.py faeg_app database views tests
python -m pytest -q tests
```

A suíte automatizada utiliza cenários isolados, incluindo SQLite em memória. O fluxo de integração contínua é definido em [`.github/workflows/ci.yml`](../.github/workflows/ci.yml).

## Implantação

O Streamlit executa a aplicação, e o PostgreSQL mantém os dados persistentes. A sincronização do esquema ocorre na inicialização e pode incluir criação de tabelas e ajustes de colunas. Mudanças estruturais são acompanhadas de cópia de segurança do banco, verificação dos modelos e execução controlada no ambiente correspondente.

| Ambiente | Finalidade | Dados |
| --- | --- | --- |
| Desenvolvimento | Implementação e testes | Exemplos e registros de teste |
| Demonstração | Acesso público temporário | Registros fictícios ou anonimizados em banco independente |
| Operação | Uso da FAEG | Dados operacionais, com acesso restrito |

A aplicação não implementa autenticação individual nesta versão. A segregação das bases e o acesso ao ambiente são definidos na [política de segurança](../SECURITY.md).

## Diagnóstico

O diagnóstico de ciclos pode ser executado em uma conexão de teste configurada na variável `DATABASE_URL`:

```powershell
python -m database.diagnostico_ciclos
```

## Recuperação

A recuperação de código utiliza uma revisão validada do repositório. A recuperação de dados e de alterações de esquema utiliza os mecanismos de backup e restauração do PostgreSQL/Neon. Os dois procedimentos são independentes.
