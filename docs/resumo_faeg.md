# Resumo do Projeto — FAEG Logística

**Projeto acadêmico aplicado:** Startup Challenge UMC 2026 · **Produto:** Sistema Web FAEG · **Revisão documental:** 24/11/2026 (Ajuste 27).

## Problema e objetivo

O controle inicial de viagens da FAEG foi organizado em planilha, exigindo conciliar fretes, ciclos, recebimentos, custos e quilômetros. O projeto busca estruturar esses dados em aplicação web, com registro persistente, consultas, indicadores e relatórios, respeitando a dinâmica real de fretes simultâneos e sequenciais.

## Escopo funcional atual

O MVP possui **11 etapas**: Frota; Frete e Documentos; Cliente; Negociação e Recebimentos; Coleta; Entrega; Despesas; Fechamento; Relatórios; Consultas; Cadastros.

O domínio distingue:

1. **Frete:** serviço comercial e negociação individual.
2. **Ciclo:** agrupamento operacional com receitas dos fretes e gastos compartilhados.
3. **Saída:** deslocamento físico, inclusive coletas preparatórias e retorno.
4. **Trecho:** segmento planejado de uma saída, evitando soma de quilômetros sobrepostos.
5. **Abastecimento:** compra vinculada a despesa única; estimativa de consumo por KM é separada.

O código ORM contém **18 tabelas**, conforme o [inventário técnico](arquitetura_banco.md). A implantação das três tabelas de saídas/trechos/consumo foi confirmada no Neon em 24/11/2026; testes unitários locais para essas regras estão disponíveis. A confirmação das tabelas **não equivale** a homologação de todos os fluxos.

## Tecnologia e organização

- **Interface:** Python e Streamlit; código principal em `app.py`, com módulo visual em `views/`.
- **Persistência:** SQLAlchemy e PostgreSQL/Neon, configurados por `DATABASE_URL`.
- **Dados:** Pandas e OpenPyXL; importação Excel com prévia, sem gravação automática liberada.
- **Relatórios:** exportações Excel e PDF; indicadores financeiros parciais.
- **Modelagem:** [diagramas UML e de arquitetura](diagramas/README.md).

## Regra operacional central

Um **ciclo** pode iniciar com um frete principal, agregar novos contratos ao longo da rota ou em dias distintos e conter várias saídas da base. As receitas pertencem aos fretes; os custos compartilhados e o KM físico pertencem à operação. Não é permitido inventar rateio por frete. A despesa é registrada uma única vez; a estimativa de combustível não substitui o gasto contabilizado.

## Avaliação do estágio de maturidade

| Área | Situação documentada |
| --- | --- |
| Protótipo e requisitos | Documentados em reuniões e regras de negócio |
| Código com 11 etapas | Presente no ZIP revisado |
| PostgreSQL/Neon e 18 modelos | Código e implantação das novas tabelas confirmados |
| Testes de saídas | Seis cenários unitários existentes em SQLite |
| Testes integrados completos | Pendentes de evidência de homologação |
| Autenticação e autorização | Não identificadas no código revisado |
| Migrações versionadas | Pendentes; o app atualmente sincroniza o esquema ao iniciar |
| Conciliação bancária e rateio financeiro | Não implementados/homologados como fechamento definitivo |

## Equipe e registros acadêmicos

- **Felipe Pontes:** desenvolvimento.
- **Larissa do Espírito Santo:** desenvolvimento.
- **Eduardo Pontes:** cliente/representante da FAEG, referência operacional e validação das regras.

O [histórico de reuniões](reunioes/) documenta o kickoff, o protótipo inicial e a evolução até o MVP. Para evidências de validação, consulte o [plano de testes](plano_testes.md).

## Histórico de importação e conciliação

Em análise anterior da planilha de referência, foram apontadas divergências em linhas de fechamento e associação de ciclos. Essas observações são **registros de auditoria histórica, não correções efetuadas no Neon**. O importador mantém a prévia e a auditoria; a gravação em lote continua bloqueada.

A visão atual do projeto é descrita pelo [README principal](../README.md) e pelo [índice documental](README.md).
