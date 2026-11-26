# Guia de preenchimento operacional

A aplicação mantém 11 etapas, com cadastro de informações operacionais e comerciais antes do fechamento. Cada quilômetro, odômetro ou despesa possui um local de registro.

## Sequência de preenchimento

| Etapa | Informações |
| --- | --- |
| **1 — Frota** | Operação individual ou ciclo, motorista e veículo |
| **2 — Frete e documentos** | Dados do frete, carga, documentos fiscais, saídas operacionais, KM planejado e odômetros |
| **3 — Cliente** | Contratante |
| **4 — Negociação** | Valores negociados, parcelas previstas e recebimentos confirmados |
| **5 — Coleta** | Local e horários de coleta |
| **6 — Entrega** | Local e horários de entrega |
| **7 — Despesas** | Combustível, pedágios, alimentação e demais custos por frete, ciclo ou veículo |
| **8 — Fechamento** | Totais, indicadores, situação operacional e conferência do frete |
| **9 — Relatórios** | Indicadores, demonstrativos e exportação |
| **10 — Consultas** | Pesquisa e histórico das operações |
| **11 — Cadastros** | Clientes, veículos, motoristas, fornecedores e consumo de referência |

## Saídas e quilometragem — Etapa 2

Cada saída representa um deslocamento da base até o retorno à base. O mesmo cadastro atende a operações individuais e ciclos com vários fretes.

1. Registrar a finalidade da saída, como *Coletas preparatórias* ou *Entregas e retorno*.
2. Informar data de partida e os três componentes de KM planejado: deslocamento entre coletas, rota principal e retorno à base.
3. Registrar o odômetro inicial na partida.
4. Registrar data de chegada e odômetro final no retorno. O KM real resulta da diferença entre as leituras.
5. Acrescentar outras saídas quando a operação exigir deslocamentos adicionais.

Os trechos compartilhados não são multiplicados pela quantidade de fretes. O KM de uma operação corresponde à soma das saídas válidas.

## Salvamento parcial

A opção **Salvar rascunho / continuar depois** registra informações ainda incompletas, que podem ser recuperadas em **Retomar rascunho**. Rascunhos não compõem o resultado financeiro. O salvamento definitivo estabelece os vínculos com cliente, motorista, veículo, coleta e entrega.

## Despesas e abastecimentos — Etapa 7; consolidação na Etapa 8

O destino da despesa define sua contabilização: **Frete** para gasto exclusivo, **Ciclo** para gasto compartilhado ou **Veículo** para custo provisório ainda não atribuído. O número interno do ciclo é utilizado pela aplicação; o cadastro apresenta sua identificação operacional.

Abastecimentos são registrados na Etapa 7 com data, litros, preço e odômetro no posto. Essa leitura integra o histórico do veículo e não acrescenta quilômetros à operação. O fechamento apresenta os dados consolidados sem duplicar os lançamentos.

## Associação de fretes a saídas

1. Informe o nome do ciclo na Etapa 1. O código interno `V` e o ID `FV` são gerados automaticamente no salvamento.
2. Cadastre uma saída na Etapa 2, com datas, veículo e quilômetros. Se ela já existe no ciclo, não crie outra.
3. Em **Saída de coleta deste frete**, escolha a saída correspondente. Preencha os detalhes de carga e os demais dados do frete individualmente.
4. Para outra carga coletada na mesma saída, inicie um novo frete, informe o mesmo nome de ciclo e selecione a saída existente.
5. Abra o frete salvo para alterar seu vínculo ou os detalhes de carga, se necessário. A edição não cria nova saída e não soma KM novamente. As consultas e a exportação incluem a saída de coleta associada.

Os fretes com entrega pendente continuam vinculados ao ciclo original. Não é necessário gerar novo ID para entregas posteriores aproveitando outros percursos.

Na Etapa 4, confirme a individualização quando um ciclo antigo tiver negociação compartilhada. Na Etapa 7, informe o motivo para cancelar uma despesa salva. O Excel conserva a data e o motivo do cancelamento. Na Etapa 8, a estimativa de Diesel usa os parâmetros do veículo e as leituras válidas das saídas salvas.
