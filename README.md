# FAEG — Sistema Web de Gestão Logística

**Soluções Empresariais e Logísticas**

Sistema web para gerenciamento operacional e financeiro de fretes individuais e ciclos de transporte. O projeto reúne registros de frota, cargas, clientes, negociações, coletas, entregas, despesas, recebimentos, quilometragem e indicadores em uma plataforma integrada.

O produto foi desenvolvido a partir da rotina logística da FAEG, inicialmente controlada por planilhas, como MVP no contexto do **Startup Challenge UMC 2026**.

**Aplicação:** [Sistema Web FAEG](https://testefaeg.streamlit.app/)

## Funcionalidades

- **Fretes e ciclos:** cadastro comercial independente por frete, com agrupamento de operações e consolidação dos custos compartilhados.
- **Planejamento e execução:** saídas operacionais, quilômetros planejados por percurso e odômetros de partida e retorno à base.
- **Gestão financeira:** valores negociados, parcelas previstas, recebimentos confirmados, despesas e resultados operacionais.
- **Abastecimentos:** histórico de Diesel e ARLA por veículo, com litros, valores e leitura do odômetro. As estimativas de consumo são apresentadas separadamente das despesas registradas.
- **Rascunhos:** salvamento parcial e retomada de cadastros não concluídos.
- **Consultas e relatórios:** indicadores, histórico operacional e exportação em PDF e Excel.

## Fluxo do sistema

| Etapa | Função |
| --- | --- |
| 1 — Frota | Identificação da operação, motorista e veículo |
| 2 — Frete e documentos | Dados do frete, carga, documentação, saídas, KM planejado e odômetros |
| 3 — Cliente | Contratante do frete |
| 4 — Negociação | Valores contratados e recebimentos |
| 5 — Coleta | Local, data e horários |
| 6 — Entrega | Local, data e horários |
| 7 — Despesas | Custos de frete, ciclo ou veículo, incluindo abastecimentos |
| 8 — Fechamento | Conferência dos resultados e encerramento operacional |
| 9 — Relatórios | Indicadores e exportações |
| 10 — Consultas | Histórico e pesquisa de registros |
| 11 — Cadastros | Clientes, motoristas, veículos, fornecedores e parâmetros de consumo |

As saídas são registradas na **Etapa 2**. O fechamento utiliza os registros operacionais e financeiros já cadastrados, sem exigir novo lançamento de quilômetros ou odômetros. O procedimento está descrito no [guia de preenchimento](docs/guia_preenchimento_operacional.md).

## Tecnologias e arquitetura

| Componente | Tecnologia |
| --- | --- |
| Interface | Python e Streamlit |
| Persistência | PostgreSQL (Neon) e SQLAlchemy ORM |
| Tratamento de dados | Pandas e OpenPyXL |
| Relatórios | Exportação PDF e Excel |
| Testes | pytest e GitHub Actions |

A aplicação possui 11 módulos de interface em [`faeg_app/pages/`](faeg_app/pages/), serviços compartilhados em [`faeg_app/`](faeg_app/), componentes de operação em [`views/`](views/) e regras de persistência em [`database/`](database/). O modelo de dados contém **19 tabelas ORM**.

A [documentação técnica](docs/README.md) inclui requisitos, regras de negócio, diagramas UML, modelo de dados, decisões arquiteturais e testes.

## Instalação local

Pré-requisitos: Python 3.11 ou superior e PostgreSQL de desenvolvimento com conexão configurada em `DATABASE_URL`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Configurar DATABASE_URL no arquivo .env do ambiente de desenvolvimento.
python -m streamlit run app.py
```

Linux/macOS: ativar o ambiente com `source .venv/bin/activate` e copiar as configurações com `cp .env.example .env`.

A inicialização utiliza sincronização de esquema. Os procedimentos de preparação do banco, publicação e recuperação estão definidos no [guia de execução](docs/guia_execucao.md).

### Testes automatizados

```powershell
python -m pip install -r requirements-dev.txt
python -m compileall -q app.py faeg_app database views tests
python -m pytest -q tests
```

## Documentação

- [Índice técnico](docs/README.md)
- [Requisitos funcionais](docs/requisitos.md) e [regras de negócio](docs/regras_negocio.md)
- [Arquitetura](docs/arquitetura_aplicacao.md) e [modelo de dados](docs/arquitetura_banco.md)
- [Diagramas](docs/diagramas/README.md) e [decisões arquiteturais](docs/decisoes/README.md)
- [Plano de testes](docs/plano_testes.md) e [histórico de alterações](CHANGELOG.md)
- [Política de segurança](SECURITY.md) e [licenciamento](docs/licenciamento.md)

## Equipe

- **Felipe Pontes** — desenvolvimento de software.
- **Larissa do Espírito Santo** — desenvolvimento de software.
- **Eduardo Pontes** — definição dos processos operacionais e validação do produto pela FAEG.

## Licenciamento

As contribuições originais posteriores à mudança de política seguem o aviso de [direitos reservados](LICENSE). Os materiais anteriormente disponibilizados sob MIT permanecem sujeitos aos termos daquela licença, disponíveis em [`licenses/`](licenses/). O histórico está documentado em [licenciamento](docs/licenciamento.md).
