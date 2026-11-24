# ADR-002 — Não confundir compra de combustível com consumo por ciclo

- **Data:** 24/11/2026
- **Status:** adotada como separação gerencial; conciliação de estoque pendente

## Contexto

Um abastecimento próximo ao fim do ciclo pode repor combustível já usado ou aumentar o saldo do tanque para viagens futuras. Associar todo o valor da nota ao ciclo da data, ou ao próximo ciclo, pode distorcer resultados.

## Decisão

Registrar cada compra de Diesel/ARLA uma única vez no lançamento de despesa e no histórico de abastecimento referenciado. Apresentar uma **estimativa** de Diesel por veículo com `KM real / km por litro × preço de referência`. **Não lançar essa estimativa novamente na DRE** nem declarar estoque de combustível sem aferição.

## Consequências

- Preserva despesas financeiras e evita dupla contagem.
- A margem gerencial continua baseada nos gastos efetivamente atribuídos.
- Aferição de estoque inicial/final e eventual mudança de regime de custeio exigem desenho e migração específicos.
