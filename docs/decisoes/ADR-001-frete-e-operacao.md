# ADR-001 — Separar frete comercial da operação física

- **Data:** 24/11/2026
- **Status:** adotada na implementação do Ajuste 27, sujeita a validação operacional

## Contexto

Um ciclo pode ter fretes simultâneos, sequenciais ou de retorno e várias saídas da base. Concentrar todos os KM e custos em apenas um frete distorce sua leitura individual. A receita, contudo, nasce de contratos separados.

## Decisão

Manter `Viagem`/`FreteFinanceiro` como unidade comercial e `CicloOperacional` como agrupador. Registrar a execução física em `SaidaOperacional` e `TrechoOperacional`. O KM planejado físico será medido pelas saídas (se cadastradas) e não pela soma indiscriminada das distâncias comerciais dos fretes. Custos comuns permanecem no ciclo; não ratear sem critério aprovado.

## Consequências

- Mais fidelidade à operação e menor risco de KM duplicado.
- Necessidade de registrar saídas e trechos para obter o novo cálculo.
- Compatibilidade com o modo legado enquanto não existem saídas.
- Relatórios por frete de ciclos não podem anunciar margem líquida sem alocação de custos.
