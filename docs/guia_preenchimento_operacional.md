# Guia de preenchimento operacional — FAEG

O sistema possui **11 etapas**. O registro da operação é feito em sequência. Cada informação é lançada uma vez e utilizada automaticamente no fechamento.

## Sequência de preenchimento

| Etapa | O que fazer |
|---|---|
| **1 — Frota** | Identificar a viagem, escolher **Individual** ou **Ciclo**, motorista e veículo. Em ciclo, informar o mesmo nome de ciclo nos fretes vinculados. |
| **2 — Frete e Documentos** | Registrar dados do serviço, carga e documentos fiscais. Na seção **Saídas operacionais**, adicionar a primeira saída com datas, KM planejados e odômetros; acrescentar outras saídas se a operação exigir. |
| **3 — Cliente** | Selecionar o contratante daquele frete. |
| **4 — Negociação** | Registrar os valores negociados e, quando ocorrerem, os recebimentos efetivos daquele frete. |
| **5 — Coleta** | Informar o local e os horários de coleta. |
| **6 — Entrega** | Informar o local e os horários de entrega. |
| **7 — Despesas** | Registrar cada gasto uma vez: **Ciclo inteiro** para custos compartilhados, **Frete atual** para custos exclusivos ou **Veículo** quando não houver operação definida. Diesel e ARLA incluem odômetro do abastecimento. |
| **8 — Fechamento** | Conferir KM planejados/reais, receitas, despesas, recebimentos e situação operacional. **Não há novo cadastro de KM ou odômetro nesta etapa.** |
| **9 e 10** | Consultar relatórios, histórico e indicadores. |
| **11 — Cadastros** | Manter clientes, veículos, motoristas, locais e parâmetros de referência de consumo dos veículos. |

## Saídas operacionais — Etapa 2

Cada saída é o **deslocamento físico entre a saída da base e o retorno à base**. O mesmo formulário serve tanto para uma operação individual quanto para um ciclo com vários fretes.

1. Informe uma finalidade livre: por exemplo, *Coletas preparatórias*.
2. Informe data de saída e KM previstos em três componentes: **saída/entre coletas**, **rota principal** e **retorno à base**. O total é automático.
3. Registre o **odômetro inicial ao sair da base**.
4. Ao retornar, preencha a data de chegada e o **odômetro final**; o KM real será calculado automaticamente.
5. Se a mesma operação exigir outra saída da base, clique em **Adicionar outra saída operacional**. Os dados permanecem vinculados ao mesmo ciclo.

O ciclo pode ter uma, duas ou várias saídas. Os fretes comerciais que compartilham um percurso **não repetem** os quilômetros daquela saída.

## Salvar sem concluir

Na barra lateral, clique em **Salvar rascunho / continuar depois** para guardar as informações parciais, inclusive saídas e despesas ainda provisórias. Use **Retomar rascunho** ao voltar. O rascunho não entra na DRE. Ao completar motorista, veículo, cliente, local de coleta e local de entrega, use **Salvar Viagem**. O sistema converte o rascunho em registro definitivo com os vínculos corretos.

## Abastecimento e custos — Etapa 7; conferência na Etapa 8

No abastecimento, o odômetro da Etapa 7 representa **a leitura no posto**, e não uma nova distância percorrida. Ele não substitui o odômetro inicial/final da saída e **não é somado ao KM real**. Uma compra de combustível é registrada uma vez; sua estimativa de consumo é um indicador gerencial à parte.

O campo de escolha do destino do custo existe para evitar atribuir diesel e pedágio de um ciclo inteiro a apenas um dos fretes. O **nome do ciclo** é exibido para facilitar a seleção; seu ID numérico é utilizado internamente pelo banco.
