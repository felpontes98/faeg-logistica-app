# Regras de negócio — Sistema Web FAEG

Este documento estabelece os critérios utilizados no cadastro, planejamento, execução e fechamento de fretes individuais e ciclos operacionais.

## RN-01 — Frete e ciclo

- **Frete:** contratação comercial individual, identificada por código, cliente, carga, documentos, coleta, entrega, negociação e recebimentos próprios.
- **Ciclo:** agrupamento operacional de um ou mais fretes que compartilham planejamento, deslocamentos ou despesas. A existência de um único frete de retorno já permite tratá-lo no mesmo ciclo da operação de ida.
- Cada frete mantém sua negociação individual. O ciclo consolida as receitas dos fretes vinculados e não distribui despesas comuns automaticamente.
- O vínculo ao ciclo usa o identificador interno do banco, evitando reunir ciclos históricos homônimos por aproximação textual.

## RN-02 — Cadastro e continuidade

O cadastro compreende identificação da frota, dados do frete e documentos, cliente, negociação, coleta, entrega e despesas. A aplicação permite salvar e retomar um **rascunho** com campos incompletos. O rascunho não integra receitas, despesas ou indicadores até seu salvamento definitivo. O salvamento como frete definitivo verifica os relacionamentos obrigatórios.

## RN-02A — Identificação dos fretes e saídas

- Cada frete salvo recebe um código interno `V` e um ID comercial `FV` gerados na mesma sequência numérica, sem referência ao ano. Por exemplo, `V11` e `FV000000011`.
- A sequência é global e não reinicia quando muda o ciclo, a saída ou o ano. A numeração é reservada durante a transação do primeiro salvamento. Uma prévia exibida durante o preenchimento pode mudar caso outro frete seja salvo antes.
- Os identificadores de fretes históricos não são alterados automaticamente. Códigos já utilizados não são reutilizados.
- A numeração exibida das saídas (`Saída 01`, `Saída 02`...) acompanha a ordem de cadastro por `id_saida` dentro do ciclo e não muda quando a data da saída é corrigida. O `id_saida` é a chave interna persistida no banco.
- Cada frete pode indicar a saída em que foi coletado. Uma saída pode atender vários fretes; cada frete mantém carga, cliente, coleta, entrega, documentos e negociação próprios.
- A identificação da saída de coleta não transfere o frete para outro ciclo nem adiciona KM ao cadastro comercial.

## RN-03 — Negociação e recebimentos

- Valor divulgado e valor negociado são informados manualmente por frete.
- Adiantamento e saldo **previstos** derivam de valores/percentuais negociados; não comprovam pagamento.
- Recebimentos **efetivos** são registrados em `recebimentos_frete`, com data e valor. Cancelamentos exigem motivo e não excluem o histórico.
- Saldo a receber é apurado a partir do valor negociado menos os recebimentos confirmados. Excedentes são identificados separadamente; não há compensação automática entre fretes.
- Financeiro legado ambíguo não é replicado para vários fretes como se fosse receita individual.

## RN-04 — Saídas e quilometragem planejada

- A Etapa 2 contém o planejamento das **saídas operacionais**, tanto para individual quanto para ciclo. Cada saída começa na base e termina ao retornar à base, mesmo quando uma operação exige várias saídas em dias distintos.
- O KM planejado da saída é composto por **saída/entre coletas + rota principal + retorno à base**. Se houver trechos detalhados cadastrados, sua soma prevalece sobre o KM manual daquela saída; os dois valores nunca são somados entre si.
- Fretes simultâneos não multiplicam o mesmo deslocamento. O total da operação é a soma das saídas vinculadas ao ciclo.
- O retorno sem frete adicional pertence à operação. Uma nova saída pode ser incluída para complementar a carga ou executar entregas posteriores.

## RN-05 — Odômetros

- Odômetro inicial: leitura ao sair da base. Odômetro final: leitura ao retornar à base. A diferença representa o KM real daquela saída.
- Enquanto não houver retorno, o odômetro final pode permanecer não informado; o sistema não deve apresentar quilometragem desconhecida como medição zero.
- Intervalos sobrepostos ou invertidos no mesmo veículo exigem correção antes do fechamento consolidado confiável.
- O odômetro do **abastecimento**, registrado na Etapa 7, representa a leitura no posto. Não acrescenta quilômetros à saída e não substitui o odômetro de partida/chegada.
- Campos históricos de quilometragem são preservados para consultas de registros anteriores. Novas operações utilizam o controle por saídas.

## RN-06 — Despesas e abastecimentos

- A Etapa 7 concentra o formulário de despesas. O destino pode ser **frete** (custo exclusivo), **ciclo** (custo compartilhado) ou **veículo** (gasto ainda não atribuído).
- Despesas de ciclo entram uma única vez no fechamento consolidado e não geram lucro líquido individual por frete.
- Diesel e ARLA são registrados como uma única despesa financeira, com litros, preço, data e odômetro no posto. O histórico de `abastecimentos` referencia o mesmo gasto, sem duplicação na DRE.
- Compras de combustível e estimativa de consumo por KM são informações distintas. Parâmetros referenciais de consumo não criam custo adicional.
- Cancelamentos mantêm o histórico. Despesas semelhantes devem ser conferidas antes de confirmar que se referem a comprovantes diferentes.

## RN-07 — Despesa provisória e atribuição

Despesas vinculadas inicialmente ao veículo ficam fora do resultado de frete/ciclo enquanto estiverem pendentes. A atribuição posterior exige destino compatível, evita duplicar o gasto financeiro e registra o evento. Estornos preservam justificativa e devolvem a origem ao estado pendente, sem deixar valor contabilizado no destino.

## RN-08 — Fechamento gerencial

A Etapa 8 consolida **receitas negociadas, recebimentos confirmados, despesas e KM** a partir dos cadastros anteriores. Não é uma segunda etapa de entrada de quilômetros ou odômetros. O resultado por ciclo pode ser apurado; a receita individual de um frete que compartilha custos não é apresentada como lucro líquido individual.

Os indicadores de margem dependem de receita positiva e dados financeiros suficientemente determinados. As despesas pendentes de veículo não são incluídas nos totais operacionais até sua atribuição.

## RN-09 — Relatórios e exportações

A Etapa 9 apresenta indicadores e exportações financeiras e operacionais. A Etapa 10 permite consultar os registros e exportar a base completa independentemente de filtros aplicados na lista da tela. Recebimentos cancelados e despesas canceladas permanecem identificáveis no histórico, mas fora dos resultados ativos.

## RN-10 — Importação e dados históricos

A importação da planilha disponibiliza prévia e conferência. A gravação automática no banco fica indisponível até definição de critérios e autorização. Dados históricos não são realocados ou reagrupados por semelhança de código, nome ou valor.

## RN-11 — Situações operacionais e parâmetros

A situação de execução da viagem e a situação financeira do frete são independentes: uma entrega concluída pode permanecer com saldo a receber. Os parâmetros de consumo por veículo ficam nos cadastros gerais e podem ser atualizados; são referências gerenciais, não medições diretas de estoque no tanque.

Os [requisitos](requisitos.md) especificam as funcionalidades e o [plano de testes](plano_testes.md) reúne os cenários de verificação do sistema.
