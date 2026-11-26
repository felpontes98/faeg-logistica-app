# Glossário — FAEG

| Termo | Definição no projeto |
| --- | --- |
| **Operação** | Planejamento físico completo, que pode abranger saídas sucessivas e um ou mais fretes. |
| **Frete** | Serviço comercial individual com cliente, carga, rota, documentos e negociação. Persistido em `viagens`. |
| **Ciclo** | Agrupador operacional de fretes que compartilham planejamento ou recursos, identificado internamente por `id_ciclo`. |
| **Saída operacional** | Deslocamento do veículo ligado a um ciclo, com data, KM planejado e odômetros. |
| **Trecho** | Percurso delimitado dentro de uma saída operacional. |
| **KM comercial** | Distância de referência de um frete; não é o total físico automaticamente percorrido por um ciclo. |
| **KM planejado físico** | Soma dos trechos de uma saída, ou KM manual dessa saída quando não existirem trechos. |
| **KM real** | Diferença de leituras válidas de odômetro por saída, consolidada sem sobreposição. |
| **Despesa exclusiva** | Custo identificável de determinado frete, registrado em `viagens_despesas`. |
| **Despesa compartilhada** | Custo do ciclo não rateado automaticamente, registrado em `ciclos_despesas`. |
| **Despesa provisória** | Gasto vinculado inicialmente ao veículo, fora do resultado até atribuição explícita. |
| **Abastecimento** | Compra de Diesel/ARLA ligada ao lançamento financeiro original; não cria custo adicional. |
| **Consumo estimado** | Simulação de Diesel a partir de KM real, km/L e preço de referência; não representa compra nem estoque apurado. |
| **Receita negociada** | Valor comercial fechado; independente de haver pagamento. |
| **Recebimento confirmado** | Entrada efetivamente informada, registrada por frete. |
| **DRE gerencial parcial** | Receitas menos os custos considerados na aplicação; não equivale ao lucro líquido contábil. |
| **ORM** | Mapeamento objeto-relacional SQLAlchemy que associa classes Python às tabelas. |
| **CI** | Integração contínua: verificações automáticas disparadas por push/pull request. |
| **Neon** | Plataforma PostgreSQL utilizada para persistência da aplicação publicada. |


A situação operacional acompanha a execução. Para o financeiro, distinguimos fretes sem recebimento, com recebimento parcial, quitados ou sujeitos a conferência.
