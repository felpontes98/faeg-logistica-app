# ADR-003 — Compatibilidade histórica sem migração automática

- **Data:** 24/11/2026
- **Status:** aplicada na implantação do Ajuste 27; melhoria arquitetural pendente

## Contexto

A base contém fretes anteriores ao novo controle de saídas, despesas e odômetros, inclusive agrupamentos com custos concentrados em um único frete. Não é possível deduzir com segurança o rateio histórico.

## Decisão

Criar três novas tabelas ORM no Ajuste 27 sem redistribuir registros antigos. Até a primeira saída de uma operação, preservar o cálculo anterior. A inicialização da aplicação atual utiliza `sincronizar_colunas_banco()` para criar estruturas ausentes; **essa prática não é um sistema de migrações versionadas**.

## Consequências e evolução

- Implanta nova funcionalidade sem alterar automaticamente custos de ciclos anteriores.
- Os indicadores legados continuam sujeitos a conferência humana.
- Planejar migrações versionadas (ex.: Alembic), estratégia de rollback, backup validado e trilha de alterações antes de mudanças estruturais adicionais.
