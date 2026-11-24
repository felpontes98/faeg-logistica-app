# FAEG — Sistema Web de Gestão Logística

**FAEG — Soluções Empresariais e Logísticas** · Projeto acadêmico aplicado à operação real de transporte de cargas · Startup Challenge UMC 2026.

Aplicação web para cadastrar fretes, agrupar serviços em ciclos operacionais, controlar receitas e despesas, acompanhar deslocamentos e emitir consultas e relatórios gerenciais. O projeto evoluiu de uma planilha de controle de viagens para um MVP em **Python/Streamlit**, com persistência em **PostgreSQL (Neon)**.

> **Estado em 24/11/2026:** MVP implantado e acessível em Streamlit/Neon, com o Ajuste 27 (saídas operacionais e trechos). A publicação **não equivale a homologação completa**: testes integrados, segurança de acesso e cenários de dados históricos ainda exigem validação. Não utilizar indicadores parciais como demonstrações contábeis oficiais.

## Visão geral

- **Frete:** serviço comercial individual, com cliente, carga, documentos, negociação e recebimentos próprios.
- **Ciclo operacional:** agrupa um ou mais fretes; consolida receitas e despesas compartilhadas sem rateio automático.
- **Saída operacional:** deslocamento físico com veículo, datas, KM planejado e leituras de odômetro; um ciclo pode ter várias saídas.
- **Trecho:** etapa de uma saída, por exemplo base → coleta → entrega → retorno. Se houver trechos, o KM planejado é a soma dos trechos, sem duplicar o KM manual da saída.
- **Abastecimento:** compra efetiva de Diesel/ARLA registrada uma vez; o consumo por KM é uma **estimativa gerencial separada** da DRE.

### As 11 etapas da aplicação

| Etapas | Atividades |
| --- | --- |
| 1–3 | Frota/viagem, frete/documentos e cliente contratante |
| 4–6 | Negociação/recebimentos, coleta e entrega |
| 7 | Despesas de frete/ciclo/veículo e histórico de abastecimentos |
| 8 | Saídas/trechos, quilometragem, situação operacional e fechamento |
| 9 | Relatórios, indicadores, conferência financeira e exportações |
| 10–11 | Consultas gerais e cadastros de referência |

## Tecnologias e arquitetura

| Camada | Tecnologias | Arquivos principais |
| --- | --- | --- |
| Interface web | Python, Streamlit | [`app.py`](app.py), [`faeg_app/pages/`](faeg_app/pages/), [`views/`](views/) |
| Lógica compartilhada e callbacks | Python | [`faeg_app/core.py`](faeg_app/core.py) |
| Regras, dados e serviços | Python | [`database/`](database/) |
| Persistência | SQLAlchemy ORM | [`database/models.py`](database/models.py) |
| Banco relacional | PostgreSQL — Neon | Configurado por `DATABASE_URL` |
| Dados e exportações | Pandas, OpenPyXL, geração PDF | [`faeg_app/reporting.py`](faeg_app/reporting.py) e módulos de importação |
| Testes automatizados | Pytest + SQLite em memória | [`tests/`](tests/) |

```mermaid
flowchart LR
    U["Usuário operacional"] --> UI["Interface Streamlit"]
    UI --> PAG["11 etapas em faeg_app/pages"]
    PAG --> CORE["faeg_app/core - regras compartilhadas"]
    CORE --> DOM["Serviços em database"]
    DOM --> ORM["SQLAlchemy ORM"]
    ORM --> DB[("PostgreSQL - Neon")]
    PAG --> REL["reporting - PDF e Excel"]
```

O `app.py` é somente o ponto de entrada (74 linhas na refatoração de 24/11/2026). As 11 etapas estão em `faeg_app/pages/`, as consultas/callbacks compartilhadas em `faeg_app/core.py`, a identidade visual em `faeg_app/theme.py` e os relatórios em `faeg_app/reporting.py`. Detalhes: [estrutura de módulos](docs/arquitetura_aplicacao.md).

O projeto **não implementa uma API REST independente**: a interface chama diretamente funções Python e sessões SQLAlchemy. O modelo atual possui **18 tabelas ORM**. Consulte os [diagramas técnicos](docs/diagramas/README.md) e o [inventário do banco](docs/arquitetura_banco.md).

## Orientações para avaliação acadêmica

Para conhecer o MVP e as evidências documentadas, sugerimos o seguinte percurso de leitura:

1. [Guia de avaliação da banca](docs/guia_avaliacao_banca.md), [resumo do problema](docs/resumo_faeg.md) e [requisitos funcionais](docs/requisitos.md).
2. [Protótipo inicial](docs/prototipo/prototipo_inicial.html) e [registro de reuniões](docs/reunioes/).
3. [Diagramas de classes, sequência, DER e arquitetura](docs/diagramas/README.md).
4. [Organização do código modular](docs/arquitetura_aplicacao.md), [testes](docs/plano_testes.md) e [auditoria final do repositório](docs/auditoria_final_2026-11-24.md).

O endereço e as credenciais de acesso a uma demonstração operacional, caso sejam necessários, devem ser fornecidos **separadamente e por canal autorizado**, evitando exposição de clientes, placas, contatos ou valores reais em um ambiente público.

## Executar localmente

**Pré-requisitos:** Python 3.11 ou superior recomendado, Git, acesso autorizado a um banco de **teste** PostgreSQL e credenciais próprias. Não compartilhe a `DATABASE_URL`.

```powershell
# Na pasta do repositório (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edite .env e configure DATABASE_URL com o driver postgresql+psycopg
# para um banco DE TESTES, nunca para o Neon de produção.
python -m streamlit run app.py
```

Em Linux/macOS, ative o ambiente com `source .venv/bin/activate` e use `cp .env.example .env`.

**Atenção ao banco:** `app.py` executa `sincronizar_colunas_banco()` ao iniciar e pode **criar tabelas ou adicionar colunas**. Use primeiro uma branch isolada do Neon ou PostgreSQL de teste; faça backup antes de qualquer mudança em produção. **Não execute o aplicativo local apontando acidentalmente para a base produtiva.** Mais informações: [instalação e operação](docs/guia_execucao.md).

## Testes de desenvolvimento

```powershell
python -m pip install pytest
python -m compileall -q app.py faeg_app database views tests
python -m pytest -q tests
```

Os testes verificam seis cenários da estrutura de saídas com **SQLite em memória** e verificações de estrutura, imports, relatórios e simulação das 11 etapas, sem conexão com o Neon. A rotina de CI em [`.github/workflows/ci.yml`](.github/workflows/ci.yml) executa essas verificações em pushes e pull requests; **não** certifica integração completa com o PostgreSQL. Consulte o [plano de testes](docs/plano_testes.md).

## Documentação do projeto

O [índice da documentação](docs/README.md) organiza os materiais técnicos e acadêmicos, incluindo:

- [Requisitos funcionais e critérios de aceite](docs/requisitos.md) · [Regras de negócio](docs/regras_negocio.md)
- [Arquitetura da aplicação](docs/arquitetura_aplicacao.md) · [Arquitetura e modelo de dados](docs/arquitetura_banco.md) · [Diagramas UML e de arquitetura](docs/diagramas/README.md)
- [Plano de testes](docs/plano_testes.md) · [Matriz de rastreabilidade](docs/rastreabilidade.md) · [Avaliação técnica](docs/avaliacao_repositorio.md)
- [Histórico das reuniões](docs/reunioes/) · [Protótipo inicial](docs/prototipo/prototipo_inicial.html)
- [Registro de decisões técnicas](docs/decisoes/README.md) · [Histórico de versões](CHANGELOG.md)

## Limitações e próximos passos

- Autenticação/autorização própria não foi identificada no código analisado; restringir o acesso à implantação e às credenciais.
- A sincronização automática do esquema deve evoluir para migrações versionadas após planejamento.
- Não há rateio aprovado de custos compartilhados; **saldo comercial por frete de um ciclo não representa lucro individual**.
- O consumo de Diesel por KM é estimativo e **não substitui** a conciliação do combustível comprado e consumido.
- Importação Excel: existem prévia e auditoria; a gravação automática permanece bloqueada.
- Faltam testes end-to-end, verificação de restauração de backup e homologação abrangente com base isolada.

## Equipe e licença

- **Felipe Pontes:** desenvolvimento de software.
- **Larissa do Espírito Santo:** desenvolvimento de software.
- **Eduardo Pontes:** cliente/representante da FAEG, regras operacionais e validação do negócio.

**Licenciamento:** política de [direitos reservados para novas contribuições](LICENSE), **respeitando a MIT das versões anteriores**. Consulte o [histórico de licenciamento](docs/licenciamento.md) e a [MIT previamente publicada](licenses/MIT-VERSOES-ANTERIORES.txt). A marca e os dados institucionais da FAEG não são abrangidos por autorização de uso do código.
