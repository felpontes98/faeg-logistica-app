# Resumo do Projeto — FAEG Logística

**Projeto acadêmico aplicado:** Startup Challenge UMC 2026 · **Produto:** Sistema Web FAEG.

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

O código ORM contém **19 tabelas**, conforme o [inventário técnico](arquitetura_banco.md), incluindo uma tabela específica para rascunhos. As saídas, os quilômetros e os odômetros são preenchidos na Etapa 2; a Etapa 8 concentra conferência e fechamento.

## Tecnologia e organização

- **Interface:** Python e Streamlit; entrada em `app.py`, onze módulos em `faeg_app/pages/`, recursos compartilhados em `faeg_app/` e módulo visual específico em `views/`.
- **Persistência:** SQLAlchemy e PostgreSQL/Neon, configurados por `DATABASE_URL`.
- **Dados:** Pandas e OpenPyXL; importação Excel com prévia, sem gravação automática liberada.
- **Relatórios:** exportações Excel e PDF; indicadores financeiros parciais.
- **Modelagem:** [diagramas UML e de arquitetura](diagramas/README.md).

## Regra operacional central

Um **ciclo** pode iniciar com um frete principal, agregar novos contratos ao longo da rota ou em dias distintos e conter várias saídas da base. As receitas pertencem aos fretes; os custos compartilhados e o KM físico pertencem à operação. Não é permitido inventar rateio por frete. A despesa é registrada uma única vez; a estimativa de combustível não substitui o gasto contabilizado.

## Escopo implementado e evolução técnica

| Área | Situação do MVP |
| --- | --- |
| Interface | 11 etapas em módulos Streamlit, com cadastro e consulta de operações |
| Banco de dados | PostgreSQL/Neon com **19 tabelas ORM** declaradas |
| Fretes e ciclos | Negociações por frete; receitas e custos consolidados por ciclo |
| KM e odômetros | Saídas registradas na Etapa 2; fechamento consolidado na Etapa 8 |
| Salvamento | Rascunhos recuperáveis e salvamento definitivo com vínculos operacionais |
| Testes automatizados | Suíte Pytest para regras de saída, rascunhos, modularização e documentação |
| Segurança | Autenticação própria por usuário e perfis prevista para a evolução do produto |
| Gestão do banco | Migrações versionadas previstas para substituir a sincronização atual |

## Equipe e registros acadêmicos

- **Felipe Pontes:** desenvolvimento.
- **Larissa do Espírito Santo:** desenvolvimento.
- **Eduardo Pontes:** cliente/representante da FAEG, referência operacional e validação das regras.

O [histórico de reuniões](reunioes/) documenta o kickoff, o protótipo inicial e a evolução até o MVP. Para evidências de validação, consulte o [plano de testes](plano_testes.md).

## Importação e conciliação da planilha original

O importador oferece prévia e conferência das informações da planilha de referência. A gravação automática em lote não integra o fluxo atual de produção. Os registros operacionais são cadastrados e mantidos no sistema conforme as regras de cada etapa.

A visão atual do projeto está no [README principal](../README.md) e no [índice documental](README.md).
