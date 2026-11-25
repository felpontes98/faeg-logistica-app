# Guia de execução e implantação

Aplicação modular com saídas na Etapa 2, despesas na Etapa 7 e fechamento na Etapa 8.

## Requisitos

- Python 3.11+ (versão recomendada para execução local e CI; demais versões requerem validação).
- PostgreSQL de testes ou branch isolada do Neon; conexão em `DATABASE_URL`.
- Pacotes em [`requirements.txt`](../requirements.txt).
- Acesso ao código e ao ambiente de implantação sob controle da equipe.

## Instalação (PowerShell / Windows)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Editar o `.env` local **sem versionar** suas credenciais:

```dotenv
DATABASE_URL=postgresql+psycopg://usuario:SENHA@host:5432/banco_de_testes?sslmode=require
```

Essa URL é apenas um **exemplo estrutural**, não uma credencial válida. Em Neon, utilizar exatamente o formato de conexão fornecido pelo painel do projeto. Nunca copiar credenciais para capturas, commits, issues ou arquivos de teste.

```powershell
python -m streamlit run app.py
```

## Testes automatizados

```powershell
python -m pip install -r requirements-dev.txt
python -m compileall -q app.py faeg_app database views tests
python -m pytest -q tests
```

A suíte inclui testes de saídas, organização dos módulos, relatórios, fluxos simulados das 11 etapas e consistência da documentação. Nos cenários de persistência isolada, utiliza SQLite em memória.

## Procedimento de publicação no Streamlit/Neon

1. Verificar `git diff --check`, `git status` e o resultado da CI.
2. Criar branch/backup do banco Neon e verificar sua estratégia de restauração.
3. Revisar mudanças em `database/models.py` e em `sincronizar_colunas_banco()`; esta função roda na inicialização e pode alterar o esquema.
4. Confirmar que as variáveis de ambiente estão configuradas apenas nos mecanismos de segredo da implantação, nunca em `.env` versionado. Para acesso público temporário, apontar a aplicação para **banco de demonstração separado e com dados fictícios/anonimizados**; clonar uma branch de produção não elimina os dados originais.
5. Conferir o carregamento das 11 etapas, especialmente edição de fretes antigos, saídas do ciclo e despesas.
6. Depois do deploy, verificar registros de erro e contagem de tabelas antes de inserir dados definitivos.

**Publicação:** o versionamento do código e a recuperação do banco são procedimentos independentes. Alterações de esquema e dados exigem plano de backup próprio. Sem login próprio, um endereço público permite a qualquer visitante operar as funções habilitadas na interface. Consulte as [diretrizes de segurança](seguranca_privacidade.md).

## Diagnóstico de ciclos (leitura)

```powershell
python -m database.diagnostico_ciclos
```

Executar preferencialmente em uma conexão de leitura autorizada. O diagnóstico implementa transação somente leitura, mas o operador deve conferir o ambiente e não combinar esse comando com execução automática de `app.py` em produção.

## Procedimento de rollback

1. Em erro de código, interromper a implantação ou reverter para um commit validado do Git.
2. Em mudança de esquema ou dados, utilizar **plano específico de recuperação do Neon**; um rollback de código não desfaz DDL.
3. Nunca apagar tabelas ou registros para “corrigir” um deploy sem cópia de segurança, conferência e autorização.

Consulte [segurança](seguranca_privacidade.md), [arquitetura](arquitetura_banco.md) e [plano de testes](plano_testes.md).
