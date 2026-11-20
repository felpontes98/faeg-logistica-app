# FAEG — Sistema de Gestão Logística

Sistema web de apoio ao controle operacional de fretes, viagens, ciclos, despesas e relatórios da **FAEG — Soluções Empresariais e Logísticas**.

Projeto desenvolvido por Felipe Pontes e Larissa do Espírito Santo no contexto do **Startup Challenge UMC 2026 — Trilha T2: Indústria e Logística**, com levantamento de processos e regras operacionais de Eduardo Pontes.

> **Estado do projeto:** MVP em evolução. Esta documentação descreve o código existente e diferencia funcionalidades implementadas de ajustes pendentes. A análise documental não equivale à homologação do sistema com o banco de produção.

## O que existe nesta versão

Pela leitura do código-fonte, o aplicativo contempla:

- Cadastros de motoristas, veículos, clientes, locais e fornecedores.
- Registro e edição de viagens, rotas, carga, documentos e negociação.
- Lançamento de despesas associadas às viagens.
- Consulta de registros, indicadores, gráficos e exportações em Excel e PDF.
- Modelos de dados SQLAlchemy com nove tabelas e conexão PostgreSQL.

**Pontos em revisão antes do uso operacional definitivo:** vínculo real entre vários fretes e um ciclo; importação e conciliação do Excel; recebimentos efetivos separados dos valores previstos; quilometragem por ciclo e abastecimento; autenticação e permissões. Consulte os [Requisitos](docs/requisitos.md) e a [Arquitetura do banco](docs/arquitetura_banco.md) para os detalhes.

## Tecnologias

| Camada | Implementação encontrada |
| --- | --- |
| Interface | Python e Streamlit |
| Manipulação e exportação | Pandas e openpyxl |
| Persistência | SQLAlchemy e PostgreSQL (`psycopg`) |
| Configuração local | `python-dotenv` e `DATABASE_URL` |
| Hospedagem prevista | Streamlit Community Cloud |

## Estrutura atual do repositório

| Caminho | Finalidade |
| --- | --- |
| `app.py` | Entrada do Streamlit; contém atualmente as telas, a navegação, cálculos e relatórios |
| `database/connection.py` | Criação da conexão e das sessões SQLAlchemy |
| `database/models.py` | Nove modelos ORM e sincronização de esquema |
| `database/importador_planilha.py` | Leitura e tentativa de importação da planilha FAEG |
| `assets/logo_faeg.png` | Logomarca |
| `.streamlit/config.toml` | Cores e tema do Streamlit |
| `docs/` | Documentação funcional, técnica e roteiro de melhorias |
| `requirements.txt` | Bibliotecas Python necessárias |

**Observação:** não existe a pasta `views/` nesta versão. A separação do `app.py` em módulos é uma melhoria proposta, ainda não executada.

## Execução local no VSCode

Requisitos: Python 3.11 (ambiente de desenvolvimento utilizado no projeto), VSCode e acesso a um **banco de testes** PostgreSQL.

1. Abra a pasta do repositório no VSCode.
2. Crie um ambiente virtual e instale as dependências:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

   No Linux/macOS, substitua a ativação por `source .venv/bin/activate` e use `python3 -m venv .venv` quando necessário.

3. Crie um arquivo `.env` local com base em `.env.example` e preencha `DATABASE_URL` **somente com a conexão do banco de testes**. Nunca publique `.env` nem credenciais no GitHub.
4. Execute:

   ```powershell
   streamlit run app.py
   ```

5. Acesse o endereço local informado pelo Streamlit.

**Atenção:** ao iniciar, `app.py` chama `sincronizar_colunas_banco()`, que pode criar tabelas e executar comandos `ALTER TABLE`. Portanto, **não execute pela primeira vez apontando ao banco de produção** sem um backup e uma revisão prévia do esquema. A área de importação de Excel contém uma incompatibilidade conhecida de interface e não deve ser usada até a correção e os testes.

## Documentação

| Documento | O que consultar |
| --- | --- |
| [Resumo do projeto](docs/resumo_faeg.md) | Objetivo, módulos existentes e limitações |
| [Kickoff](docs/kickoff.md) | Contexto e decisões do início do projeto |
| [Requisitos](docs/requisitos.md) | Requisitos funcionais e critérios de aceite |
| [Regras de negócio](docs/regras_negocio.md) | Definições de frete, ciclo, pagamentos, despesas e quilometragem |
| [Arquitetura do banco](docs/arquitetura_banco.md) | Esquema atual e mudanças propostas |

## Equipe e contribuição

- **Felipe Pontes** — Desenvolvimento de software.
- **Larissa do Espírito Santo** — Desenvolvimento de software.
- **Eduardo Pontes** — Processos operacionais, planilha-base e validação das regras de negócio.

Antes de uma mudança em banco ou cálculo financeiro, registrar a regra, criar um exemplo de teste e avaliar o impacto nos dados existentes. A atualização documental não modifica o código de produção nem os dados gravados.