# Requisitos do Sistema Web FAEG

**Escopo:** operação de fretes individuais, ciclos, despesas, abastecimentos, consulta e exportação.  
**Estado:** requisitos consolidados em novembro de 2026; as alterações de código estão **pendentes de testes integrados**.  
**Origem das regras:** planilha de controle e definições operacionais de Eduardo, inclusive a conversa “Explicar cálculo automático”.

Este documento descreve comportamentos esperados, não uma certificação de que todos já funcionam no banco publicado. Consultar as [regras de negócio](regras_negocio.md) para fórmulas e ressalvas e a [arquitetura](arquitetura_banco.md) para persistência.

## Requisitos funcionais

| ID | Requisito | Estado no código preparado |
| --- | --- | --- |
| RF-01 | Cadastrar motoristas, veículos, clientes, locais e fornecedores | Existente; teste pendente |
| RF-02 | Cadastrar frete com ID próprio, rota, documentos, cliente, motorista e veículo | Existente; teste pendente |
| RF-03 | Agrupar vários fretes por ID de ciclo sem duplicar fretes de fechamento | Implementação parcial; teste pendente |
| RF-04 | Conservar negociação, adiantamento e saldo por frete, mesmo em ciclos com clientes diferentes | Proposto em `fretes_financeiro`; teste pendente |
| RF-05 | Registrar KM Individual/Ciclo manual por frete na Etapa 2 | Proposto; teste pendente |
| RF-06 | Na Etapa 8, somar KM dos fretes do ciclo + saída/entre coletas e retorno informados uma só vez na Etapa 2 | Proposto; teste pendente |
| RF-07 | Registrar odômetros inicial/final opcionais da operação na Etapa 2 ou 8, usando os mesmos valores salvos, sem confundir com abastecimento | Proposto; teste pendente |
| RF-08 | Registrar Diesel ou ARLA no formulário único da Etapa 7, inclusive sem viagem (destino provisório Veículo) | Proposto; teste pendente |
| RF-09 | Exibir distância e KM/L/custo por KM indicativos entre abastecimentos consecutivos de Diesel do mesmo veículo | Proposto; teste pendente |
| RF-10 | Associar a despesa de combustível a um único destino e gerar simultaneamente seu histórico operacional, sem duplicar no DRE | Proposto; teste pendente |
| RF-11 | Consultar, gerar relatórios e exportar dados operacionais; o Excel inclui aba própria `Abastecimentos_Veiculos` | Proposto; revisão de indicadores ainda pendente |
| RF-12 | Importar Excel distinguindo fretes, fechamentos e totais gerais | Apenas prévia/auditoria; **gravação bloqueada** |
| RF-13 | Registrar pagamentos efetivamente recebidos, com data, valor, tipo e referência, sem confundir com parcelas previstas | Proposto em `recebimentos_frete`; teste pendente |
| RF-14 | Registrar despesas compartilhadas por ciclo e somá-las uma única vez no fechamento gerencial | Proposto em `ciclos_despesas`; teste pendente; **rateio não aprovado** |
| RF-15 | Consolidar receita negociada e despesas de cada frete por ID interno de ciclo, sem duplicar lançamentos | Proposto em `fechamento_ciclos.py`; teste pendente |
| RF-16 | Exibir prévia do ciclo na Etapa 8 e relatório na Etapa 9; exportar `Fechamento_Ciclos` | Proposto; teste pendente |
| RF-17 | Somar pagamentos efetivos por frete e ciclo; mostrar saldo a receber e possível excedente | Proposto; teste pendente |
| RF-18 | Cancelar recebimento lançado incorretamente com motivo obrigatório e sem apagar histórico | Proposto; teste pendente |
| RF-19 | Registrar despesas compartilhadas em ciclo salvo e cancelá-las com histórico e motivo, sem rateá-las pelos fretes | Proposto em `ciclos_despesas`; teste pendente |
| RF-20 | Exibir odômetro de abastecimento como campo numérico normal, visível na Etapa 7, sem checkbox | Proposto; teste visual pendente |
| RF-21 | Exportar `Despesas_Ciclo` com histórico e `Fechamento_Ciclos` com despesas de fretes e compartilhadas separadas | Proposto; teste pendente |
| RF-22 | Usar apenas um formulário de despesa com destino Frete/Ciclo/Veículo e odômetro numérico para Diesel/ARLA; histórico somente consulta | Proposto; teste visual e integrado pendente |
| RF-23 | Registrar custos provisoriamente vinculados ao veículo, inclusive sem frete, mantendo-os fora do DRE e permitindo cancelamento auditável | Proposto em `veiculos_despesas`; teste pendente |
| RF-24 | Exportar despesas do veículo (pendentes/atribuídas) e a origem financeira/cancelamento dos abastecimentos | Proposto; teste pendente |
| RF-25 | Atribuir despesa pendente a frete/ciclo salvo do mesmo veículo, sem segundo histórico de abastecimento nem duplicação no DRE | Proposto em `atribuicao_despesas.py`; teste pendente |
| RF-26 | Estornar atribuição, devolver o custo ao veículo e guardar histórico de ações com justificativa | Proposto em `veiculos_despesas_atribuicoes`; teste pendente |
| RF-27 | Manter único cadastro de despesas, com seções de vínculo e detalhes; permitir consulta/atribuição/cancelamento em áreas separadas de histórico | Proposto; teste visual pendente |
| RF-28 | Reconciliar resultado financeiro gerencial de toda a base, separando custo direto de frete, compartilhado de ciclo, gasto pendente de veículo e gasto já atribuído sem dupla soma | Proposto em `fechamento_ciclos.py`; teste pendente |
| RF-29 | Disponibilizar `Conferencia_Financeira` no Excel e exportar base completa coerente na Etapa 10, independentemente dos filtros da tabela da tela | Proposto; teste pendente |
| RF-30 | Mostrar margem como não calculável sem receita confiável, e avisar sobre despesas compartilhadas sem fretes do tipo Ciclo | Proposto; teste pendente |
| RF-31 | Sinalizar despesas semelhantes entre frete e ciclo do mesmo ID e solicitar confirmação explícita quando forem comprovantes distintos | Proposto em `conferencia_duplicidades.py`; teste pendente |
| RF-32 | Consultar indícios de repetição já cadastrados, sem alterar histórico, e exportar `Possiveis_Duplicidades` | Proposto; teste pendente |
| RF-33 | Verificar repetição cruzada também durante atribuição de despesa provisória e impedir repetição imediata de gasto comum idêntico no mesmo frete | Proposto; teste pendente |
| RF-34 | Na Etapa 8, somar KM planejado por ID interno do ciclo (não pelo nome), preservar o valor manual da Etapa 2 e sinalizar falta de KM no frete atual | Proposto; teste pendente |
| RF-35 | Impedir salvar dois fretes distintos com o mesmo ID Frete e bloquear vínculo novo a nome de ciclo que identifique mais de um ID legado | Proposto; teste pendente |
| RF-36 | Proteger vínculo histórico quando o último frete sair de um ciclo com despesa comum ativa ou quando a placa mudar com abastecimento já registrado | Proposto; teste pendente |
| RF-37 | Acrescentar na Tela 2 os campos manuais de KM saída/entre coletas e KM retorno operacional, preservando o KM individual do frete e seu título de seção | Proposto; teste pendente |
| RF-38 | Calcular KM Deslocamentos Operacionais somente na Tela 8 pela soma dos componentes da Tela 2, sem duplicar por frete do mesmo ciclo | Proposto; teste pendente |
| RF-39 | Preservar o total de deslocamentos legado até discriminação manual e exportar componentes e leituras operacionais sem misturar odômetro de combustível | Proposto; teste pendente |
| RF-40 | Exibir a Tela 8 em dois grupos visuais de KM (planejado e realizado), com totais destacados, fórmula resumida e explicações expansíveis, preservando os cálculos | Proposto; teste visual pendente |
| RF-41 | Manter na Tela 8 DRE e situação dos recebimentos visíveis; agrupar detalhes de parcelas/fretes do ciclo e indicadores de consumo do veículo em áreas expansíveis | Proposto; teste visual pendente |

## Critérios de aceite dos cálculos

1. **Frete individual:** `KM Planejado` recebe `KM Individual / Ciclo` do próprio frete.
2. **Ciclo:** `KM Planejado` é a soma de `KM Individual / Ciclo` de todos os fretes do mesmo **ID interno do ciclo**, incluindo o valor ainda não salvo do frete em edição, sem contá-lo duas vezes. Ciclos com nome igual e IDs internos diferentes não são somados em conjunto.
3. **Deslocamentos:** `KM Deslocamentos Operacionais = KM de Saída e Deslocamento Entre Coletas + KM Operacional de Retorno`, digitados na **Etapa 2**. Os componentes são guardados uma só vez por ID de ciclo. Para registros históricos ainda sem componentes, mostrar o total antigo até discriminação manual.
4. **Total:** `KM Total Planejado = KM Planejado + KM Deslocamentos Operacionais`.
5. **Real:** odômetros de início/fim podem ser digitados na Etapa 2 ou 8, compartilhando a mesma dupla de valores por frete. O KM real do frete é `odômetro final − odômetro inicial`, quando ambos são válidos. Para **KM Total Real do ciclo**, somar os intervalos reais de seus fretes apenas quando todos têm leituras válidas e os intervalos não se sobrepõem no mesmo veículo. Na ausência ou sobreposição, mostrar “Não calculável” e aviso; não comparar planejado do ciclo com real de um único frete.
6. **Desvio:** quando o KM real estiver disponível, `Diferença = KM Real − KM Total Planejado`; exibir desvio percentual somente com planejado maior que zero.
7. **Abastecimento:** é cadastrado **uma vez no formulário de despesas**, atribuído ao frete, ciclo ou provisoriamente ao veículo. O reflexo operacional por `id_veiculo` não exige que haja fretes no banco e não altera os odômetros iniciais/finais da operação.
8. **Consumo:** apenas dois abastecimentos *consecutivos de Diesel* do mesmo veículo com odômetros crescentes permitem `KM entre abastecimentos`; `KM/L = distância / litros do abastecimento atual` e `R$/KM = valor atual / distância`. Informar que essa média é indicativa e pressupõe tanque cheio; ARLA é monitorado separadamente.
9. **DRE:** o lançamento único cria a despesa financeira e, se Diesel/ARLA, seu reflexo em `abastecimentos`; **não somar os dois registros**. O resultado de um frete inclui apenas suas despesas financeiras e o resultado por ciclo inclui também os gastos comuns ativos daquele ID Ciclo. Custos provisórios só do veículo ficam excluídos. Rateio continua pendente; o BI filtrado por frete/cliente não inclui custos compartilhados.
10. **Fechamento parcial do ciclo:** `Receita negociada do ciclo = soma dos valores negociados dos fretes`, `Despesas do ciclo = soma das despesas financeiras atribuídas aos respectivos fretes + despesas compartilhadas ativas do ID Ciclo (uma única vez)` e `Resultado Operacional Parcial = receita negociada − despesas do ciclo`; não contabilizar linha de fechamento como frete adicional.
11. **Proteção de registros legados:** se dois ou mais fretes compartilham o mesmo financeiro legado de ciclo, não somar o valor legado uma vez por frete; avisar sobre a necessidade de individualização, sem excluir o histórico.
12. **Parcelas previstas:** adiantamento e saldo são campos contratuais previstos, não equivalem a recebimento efetivo. Não somar o fechamento por ciclo uma segunda vez ao total geral por fretes.
13. **Recebido de fato:** cada lançamento só pode ser atribuído a frete já salvo e deve indicar data, valor positivo, tipo de parcela e meio de pagamento. Referência/comprovante e observação são opcionais; pagamentos idênticos sem referência são tratados como possível duplicidade.
14. **Saldo:** `Recebido de fato = soma dos pagamentos confirmados (não cancelados)` e `Saldo a receber do frete = máximo(0, valor negociado − recebido de fato)`. O saldo do ciclo é a soma dos saldos de seus fretes, sem compensar automaticamente excedente de um frete com outro. Indicar excedentes separadamente; saldos de fretes com financeiro legado ambíguo não devem ser apresentados como exatos.
15. **Correções:** cancelamento exige motivo, preserva o registro, data de cancelamento e valor original. A exportação em Excel deve incluir linhas canceladas com situação identificada, sem computá-las nos totais.
16. **Odômetro visível no lançamento de combustível:** campo numérico ao lado de litros/preço no **mesmo formulário de despesas**, sem checkbox ou segunda área de lançamento. `0` representa **não informado** e deve persistir como `NULL`; a ausência não permite estimar km/L.
17. **Despesa compartilhada:** somente em ciclo previamente salvo. Registrar uma vez por `id_ciclo`, sem lançar a mesma despesa no frete; lançar custo novo e cancelar custo incorreto sem exclusão física. A exportação deve mostrar todos os lançamentos e os dois componentes do total do ciclo. Não realizar rateio automático.
18. **Despesa provisória por veículo:** cadastrar mesmo com zero fretes, mantendo valor, data, fornecedor, categoria, placa e eventual odômetro. O valor não integra DRE até a atribuição futura por processo aprovado. Cancelamento mantém data/motivo e exclui o abastecimento associado dos cálculos de consumo.
19. **Atribuição:** somente registro pendente ativo; selecionar frete salvo do mesmo veículo, ou ciclo salvo com ao menos um frete desse veículo. Confirmar com justificativa mínima; criar o lançamento financeiro de destino e marcar a origem como atribuída. O `abastecimentos` existente permanece único. Recusar aparente duplicidade e segunda atribuição da mesma origem.
20. **Estorno:** devolver despesa atribuída ao estado pendente com justificativa e evento permanente. O lançamento financeiro do frete é removido; o do ciclo é cancelado mantendo histórico. O custo não deve permanecer contabilizado no destino após o estorno. Despesas atribuídas não podem ser excluídas por atalhos das telas de frete/ciclo. Enquanto houver gasto de veículo atribuído a um frete, alterar o veículo desse frete exige estornar a atribuição antes.
21. **Conferência da base inteira:** a despesa financeira gerencial é a soma das despesas diretas de fretes com as despesas compartilhadas ativas de ciclos. A receita considerada de fretes com financeiro legado ambíguo deve permanecer excluída, com aviso de resultado parcial/incompleto. Despesas de veículo pendentes são exibidas separadamente e não entram na soma; despesas atribuídas já constam no destino, nunca como uma segunda linha de custo. Se um ciclo possui despesa ativa, mas nenhum frete do tipo Ciclo, manter esse custo na conferência global e avisar sobre a necessidade de revisão. Margem só é calculável quando a receita é positiva e não há ambiguidade financeira na base considerada.
22. **Exportação coerente:** a opção **Base Completa** da Etapa 10 exporta fretes, despesas, fechamentos e conferência da base inteira, mesmo que a tabela de consultas esteja filtrada. A aba `Conferencia_Financeira` discrimina o tratamento de cada parcela e recebido de fato não é somado à receita negociada.
23. **Possíveis duplicidades:** comparar despesas de frete e despesas compartilhadas do ciclo correspondente por data, categoria, quantidade, valor, descrição, fornecedor e, quando possível, veículo/odômetro. Uma coincidência deve gerar aviso e exigir confirmação explícita de que os comprovantes são diferentes, sem alterar os registros automaticamente. A atribuição de despesa provisória também aplica a conferência e conserva sua justificativa. A etapa de relatórios deve listar as coincidências conhecidas e exportá-las em `Possiveis_Duplicidades`; a ausência de alertas não certifica que todos os custos sejam únicos.
24. **Identificadores e histórico:** ID Frete preenchido não pode ser reutilizado por outro frete (independentemente de caixa/espaços); ciclos legados com mesmo nome e IDs diferentes não são escolhidos automaticamente para novo vínculo. Ao editar um frete existente, preservar a identidade do ciclo atual se o nome não mudou. O último frete de ciclo com despesas compartilhadas ativas não pode sair/renomear o ciclo sem tratamento explícito dessas despesas. A troca de placa é bloqueada se houver abastecimento ativo associado ao veículo anterior. O salvamento de frete novo também rejeita abastecimento temporário que pertença à outra placa.
25. **Tela 2 e Tela 8:** `KM X ROTA PLANEJADO` é só título; a Tela 2 contém entradas manuais de KM saída/entre coletas, KM individual do frete, KM retorno e odômetros operacionais inicial/final. A Tela 8 calcula os agregados, o KM total real e o desvio, mas **mantém** os dois odômetros operacionais editáveis, sincronizados com a Tela 2 sobre os mesmos campos do banco. O odômetro no abastecimento continua na Tela 7 e não preenche automaticamente os odômetros do frete, pois pode corresponder a um momento intermediário. KM individual zerado deve ser sinalizado.
26. **Migração dos deslocamentos legados:** quando os dois novos componentes de ciclo estão nulos no banco, preservar o valor antigo agregado, com aviso visual. Somente substituir por nova composição após edição explícita do formulário. Uma atualização de outro frete do ciclo não pode zerar silenciosamente o total anterior.

## Requisitos de integridade e implantação

- **RI-01:** não reescrever automaticamente fretes, despesas, códigos de ciclo ou fechamentos históricos por aproximação de linhas da planilha.
- **RI-02:** não importar Excel para o banco antes de resolver divergências apontadas na auditoria e autorizar explicitamente a gravação.
- **RI-03:** conservar compatibilidade com tabelas/colunas já publicadas; novas estruturas devem ser ensaiadas em cópia do PostgreSQL antes da produção.
- **RI-04:** validar a identidade do veículo em cada abastecimento; não misturar leituras de veículos distintos nem intervalos de ARLA com Diesel.
- **RI-05:** não usar `0` como leitura medida quando o campo foi deixado em branco; manter ausência de medição distinta de zero real.
- **RI-06:** documentar o comportamento de segurança do app antes do uso com dados pessoais reais. Autenticação e autorização ainda precisam de projeto.

## Homologação — executar apenas quando a rodada de ajustes estiver concluída

- [ ] Abrir app e cadastrar um veículo sem viagem.
- [ ] Registrar dois abastecimentos de Diesel com odômetros crescentes; conferir KM de intervalo, KM/L e R$/KM.
- [ ] Registrar ARLA no meio dos Diesel; confirmar que não muda o cálculo de consumo.
- [ ] Registrar abastecimento sem leitura e uma leitura regressiva; confirmar indicador indisponível/aviso e nenhuma distância negativa.
- [ ] Registrar Diesel no **formulário único de despesas** com destino Frete: verificar uma despesa financeira e uma linha operacional derivada, com custo somado **uma só vez** ao DRE.
- [ ] Registrar Diesel com destino Veículo sem frete: conferir custo pendente fora do DRE e histórico de consumo criado automaticamente.
- [ ] Conferir visualmente que o odômetro do abastecimento é campo numérico direto (sem checkbox), registrar `0` como ausência e uma leitura real como número.
- [ ] Cadastrar dois fretes no mesmo ciclo e conferir soma de KM e deslocamentos informados uma vez.
- [ ] Cadastrar três fretes de um ciclo, com receitas e despesas diferentes; conferir prévia na Etapa 8, relatório na Etapa 9 e planilha `Fechamento_Ciclos`.
- [ ] Registrar uma despesa compartilhada em ciclo salvo e conferir que entra uma única vez no fechamento, sem aparecer no BI por frete/cliente.
- [ ] Cancelar despesa compartilhada com motivo; conferir saída do cálculo e manutenção do histórico cancelado em `Despesas_Ciclo`.
- [ ] Conferir impedimento de lançamento idêntico no mesmo ciclo e verificar manualmente que o custo não foi também lançado a um frete.
- [ ] Confirmar que não existe uma segunda área de cadastro de abastecimento, somente histórico para consulta e controle de cancelamentos.
- [ ] Cancelar despesa provisória ou compartilhada de combustível; verificar que o histórico é mantido como cancelado e não influencia KM/L.
- [ ] Atribuir provisória ao frete do mesmo veículo; conferir total do frete, do ciclo e ausência de segundo registro em `Abastecimentos_Veiculos`.
- [ ] Atribuir provisória a custo compartilhado do ciclo; confirmar que o BI filtrado por frete não ganhou custo alocado indevidamente.
- [ ] Estornar os dois destinos e conferir retorno a pendente, saída do DRE e permanência do histórico em `Atribuicoes_Despesas`.
- [ ] Verificar bloqueios de veículo divergente, atribuição duplicada e exclusão direta de custo já atribuído.
- [ ] Conferir os quatro blocos da Conferência Financeira Geral da Etapa 9 (fretes, compartilhadas, pendentes e já atribuídas) e a identidade receita − custos contabilizados = resultado parcial.
- [ ] Gerar Excel e confirmar correspondência com `Conferencia_Financeira`, inclusive com zero fretes e com despesas compartilhadas sem fretes do tipo Ciclo.
- [ ] Filtrar um cliente na Etapa 10, exportar **Base Completa** e confirmar que a planilha não mistura a lista filtrada com despesas de toda a base.
- [ ] Conferir margem “Não calculável” para receita zero ou legado ambíguo, inclusive nos gráficos e PDF do BI.
- [ ] Lançar custo semelhante em frete e ciclo do mesmo ID e comprovar o aviso, confirmação obrigatória e ausência de alteração automática do histórico.
- [ ] Repetir no sentido inverso e verificar IDs na aba `Possiveis_Duplicidades`, inclusive com dados vazios.
- [ ] Conferir Tela 2: título KM X ROTA PLANEJADO não digitável; saída/entre coletas, KM individual, retorno e dois odômetros são manuais; Tela 8: planejado por ID, saída + retorno única por ciclo, total planejado, total real e diferença calculados.
- [ ] Abrir ciclo legado com deslocamento total mas sem os dois novos campos; garantir preservação ao salvar outro frete, aviso para discriminar e total atualizado só após edição dos componentes.
- [ ] Conferir no Excel `Viagens_e_Ciclos` e `Fechamento_Ciclos` os campos discriminados, inclusive vazios em registros legados sem detalhamento.
- [ ] Simular dois IDs internos com mesmo nome de ciclo e evitar soma por nome ou novo vínculo automático; preservar o ID original ao editar frete salvo.
- [ ] Conferir alerta quando o KM manual na Etapa 2 ainda for zero e memória de cálculo na Etapa 8.
- [ ] Tentar duplicar ID Frete, trocar placa com Diesel registrado, ou retirar último frete de ciclo com despesa ativa; conferir bloqueios sem alteração do histórico.
- [ ] Tentar salvar novo frete com Diesel temporário de outro veículo e trocar Ciclo→Individual com deslocamentos; conferir proteção da placa e dos KM.
- [ ] Cadastrar dois abastecimentos legítimos com mesmo valor, mas leituras de odômetro diferentes, sem falso bloqueio de duplicidade cruzada.
- [ ] Atribuir despesa provisória semelhante a custo existente em outro destino; conferir exigência de confirmação e justificativa.
- [ ] Tentar lançar duas vezes a mesma despesa não combustível em frete salvo e em frete ainda temporário; verificar prevenção de repetição imediata.
- [ ] Tentar trocar o veículo de um frete que recebeu uma despesa provisória; confirmar bloqueio até que a atribuição seja estornada.
- [ ] Simular dois fretes legados com um único financeiro de ciclo; conferir aviso e receita não duplicada.
- [ ] Registrar adiantamento recebido real, saldo recebido e um pagamento parcial adicional; conferir valores por frete/ciclo.
- [ ] Cancelar pagamento com motivo e conferir exclusão dos totais, sem apagar o histórico na Etapa 4 ou na aba `Recebimentos_Fretes`.
- [ ] Simular reenvio do mesmo comprovante, lançamento acima do negociado e frete ainda não salvo; conferir as proteções.
- [ ] Conferir ausência de valor negociado, adiantamento/saldo previstos e ausência de odômetros sem contabilizar valores fictícios.
- [ ] Salvar operação sem odômetros, com odômetros válidos e com odômetro final inferior ao inicial.
- [ ] Em ciclo com dois fretes, verificar KM Real Rodado individual (topo da Tela 8) e KM Total Real consolidado, incluindo caso de odômetros ausentes e intervalos sobrepostos no mesmo veículo.
- [ ] Conferir no desktop e no celular que o painel da Tela 8 não corta valores/legendas, que as seis métricas estão legíveis e que as seções expansíveis preservam todas as informações existentes.
- [ ] Confirmar que os alertas de KM ausente, intervalos sobrepostos e financeiro legado continuam visíveis mesmo com os detalhes fechados.
- [ ] Conferir cenário de fechamento e exportação sem viagens e com viagens.
- [ ] Conciliar amostra com a planilha, inspecionar as divergências já relatadas e verificar que nada foi importado sem autorização.
- [ ] Realizar backup e ensaio de migração em banco de testes; somente depois avaliar o deploy no banco oficial.

## Escopo explicitamente não encerrado

Não presumir que a aplicação esteja pronta para produção por existir código. Faltam ao menos: homologação integrada, fechamento **formal** dos ciclos (status/confirmação), regra de rateio, conciliação bancária e automatização de situações de pagamento, segurança de acesso e importação com gravação autorizada. A consolidação **gerencial parcial** por ciclo, o lançamento único de combustível/despesas, a atribuição/estorno de gastos de veículo e o registro manual de recebimentos já estão propostos.
