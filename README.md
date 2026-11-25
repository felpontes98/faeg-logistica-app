# FAEG — Sistema Web de Gestão Logística

**FAEG — Soluções Empresariais e Logísticas**

O FAEG é um sistema web para o controle operacional e financeiro de fretes. Reúne cadastros, negociações, coletas, entregas, saídas do veículo, despesas, recebimentos e relatórios em uma única aplicação. O projeto surgiu da necessidade de substituir a planilha de acompanhamento utilizada na operação da empresa e foi desenvolvido como MVP no contexto do **Startup Challenge UMC 2026**.

**Aplicação:** [Abrir o sistema FAEG](https://testefaeg.streamlit.app/) · A disponibilidade e o acesso dependem da configuração de implantação.

## Funcionalidades

- **Fretes individuais e ciclos:** cada frete possui negociação, cliente e documentos próprios. Um ciclo agrupa fretes e concentra os custos compartilhados, sem rateio automático.
- **Saídas operacionais:** cada saída registra o planejamento de coleta, rota e retorno à base, além de odômetros de partida e chegada. Os totais são consolidados por operação, sem repetir a quilometragem dos fretes simultâneos.
- **Financeiro:** registro individual dos valores negociados, recebimentos confirmados, despesas de frete e despesas compartilhadas; saldos e resultados são calculados com critérios distintos.
- **Abastecimentos:** lançamento único de Diesel ou ARLA, com data, litros, preço e leitura do odômetro no posto. As estimativas de consumo não constituem nova despesa.
- **Continuidade do cadastro:** salvamento e retomada de rascunhos, separados dos registros financeiros definitivos.
- **Gestão e relatórios:** consultas, indicadores, fechamento por ciclo e exportações PDF/Excel.

### Organização do preenchimento

| Etapa | Responsabilidade |
| --- | --- |
| 1 — Frota | Identificação da operação, veículo e motorista |
| 2 — Frete e documentos | Frete, carga, documentação, saídas, KM planejado e odômetros operacionais |
| 3 — Cliente | Contratante |
| 4 — Negociação | Valores previstos e recebimentos confirmados |
| 5 — Coleta | Local, data e horário |
| 6 — Entrega | Local, data e horário |
| 7 — Despesas | Gastos de frete, ciclo ou veículo; abastecimentos e odômetro no posto |
| 8 — Fechamento | Conferência dos totais e encerramento operacional |
| 9 — Relatórios | Indicadores e exportações |
| 10 — Consultas | Histórico e localização dos registros |
| 11 — Cadastros | Clientes, motoristas, veículos, fornecedores e parâmetros de consumo |

As saídas são registradas uma vez na **Etapa 2**. A **Etapa 8** apresenta os resultados sem exigir o recadastro dos mesmos quilômetros e odômetros. Consulte o [guia operacional](docs/guia_preenchimento_operacional.md).

## Arquitetura

| Camada | Implementação |
| --- | --- |
| Interface | Streamlit e módulos de tela em [`faeg_app/pages/`](faeg_app/pages/) |
| Inicialização e navegação | [`app.py`](app.py), [`faeg_app/bootstrap.py`](faeg_app/bootstrap.py) e [`faeg_app/layout.py`](faeg_app/layout.py) |
| Estado e serviços compartilhados | [`faeg_app/core.py`](faeg_app/core.py), [`views/`](views/) |
| Regras e persistência | [`database/`](database/) — SQLAlchemy ORM |
| Banco | PostgreSQL (Neon), configurado por variável `DATABASE_URL` |
| Relatórios | [`faeg_app/reporting.py`](faeg_app/reporting.py) |
| Testes | [`tests/`](tests/) — pytest, com cenários em SQLite isolado |

O acesso ao banco é realizado por sessões SQLAlchemy; **não há API REST intermediária**. O mapeamento atual reúne **19 tabelas ORM**. Consulte a [arquitetura da aplicação](docs/arquitetura_aplicacao.md), a [modelagem do banco](docs/arquitetura_banco.md) e os [diagramas](docs/diagramas/README.md).

## Execução local

Requisitos: Python 3.11 ou superior, acesso autorizado a um banco **isolado de desenvolvimento** e as variáveis de ambiente correspondentes.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Configure DATABASE_URL no .env para um banco de desenvolvimento, nunca para produção.
python -m streamlit run app.py
```

Em Linux/macOS, ative o ambiente com `source .venv/bin/activate` e use `cp .env.example .env`.

**Cuidado:** a inicialização sincroniza estruturas do banco e pode executar comandos DDL. Utilize um ambiente isolado e siga o [guia de implantação](docs/guia_execucao.md) antes de conectar a aplicação a qualquer base existente.

### Testes

```powershell
python -m pip install -r requirements-dev.txt
python -m compileall -q app.py faeg_app database views tests
python -m pytest -q tests
```

A integração contínua executa a suíte automatizada sem credenciais do Neon. Testes locais em SQLite não substituem a validação do fluxo com PostgreSQL em ambiente separado. Consulte o [plano de testes](docs/plano_testes.md).

## Documentação

O [índice técnico](docs/README.md) reúne o [escopo e requisitos](docs/requisitos.md), as [regras operacionais](docs/regras_negocio.md), os [diagramas](docs/diagramas/README.md), as [decisões de arquitetura](docs/decisoes/README.md), o [histórico de reuniões](docs/reunioes/) e o [protótipo inicial](docs/prototipo/prototipo_inicial.html).

## Segurança e acesso

A versão atual **não implementa autenticação própria por usuário**. Uma implantação pública com acesso de escrita e conexão ao banco operacional não é adequada para armazenar dados reais de clientes e motoristas. Para demonstrações públicas, utilizar uma base separada, com registros fictícios ou anonimizados. As credenciais permanecem fora do repositório. A restrição de acesso à implantação e o controle de usuários integram o planejamento de segurança.

Diretrizes: [Segurança](SECURITY.md) · [Privacidade e publicação](docs/seguranca_privacidade.md).

## Equipe e licenciamento

- **Felipe Pontes:** desenvolvimento de software.
- **Larissa do Espírito Santo:** desenvolvimento de software.
- **Eduardo Pontes:** representante da FAEG, definição do processo operacional e validação do produto.

As contribuições originais futuras seguem o [aviso de direitos reservados](LICENSE), respeitadas as condições das versões anteriormente disponibilizadas sob MIT. Consulte o [histórico de licenciamento](docs/licenciamento.md).
