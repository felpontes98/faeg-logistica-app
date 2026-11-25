# Requisitos do Sistema Web FAEG

**Escopo:** operação de fretes individuais, ciclos, despesas, abastecimentos, consulta e exportação.
**Fluxo operacional:** saídas na Etapa 2 e rascunhos recuperáveis.
**Origem das regras:** planilha de controle operacional da FAEG e definições registradas nas reuniões com o representante da empresa.

Os requisitos documentam o escopo funcional do MVP. Fórmulas e critérios de apuração estão detalhados em [regras de negócio](regras_negocio.md); a persistência, em [arquitetura do banco](arquitetura_banco.md).

## Requisitos funcionais

| ID | Requisito | Situação no MVP |
| --- | --- | --- |
| RF-01 | Cadastrar motoristas, veículos, clientes, locais e fornecedores | Implementado no MVP |
| RF-02 | Cadastrar frete com ID próprio, rota, documentos, cliente, motorista e veículo | Implementado no MVP |
| RF-03 | Agrupar vários fretes por ID de ciclo sem duplicar fretes de fechamento | Em evolução |
| RF-04 | Conservar negociação, adiantamento e saldo por frete, mesmo em ciclos com clientes diferentes | Implementado no MVP |
| RF-05 | Registrar os três componentes do KM planejado por saída operacional na Etapa 2 | Implementado no MVP |
| RF-06 | Sem saídas cadastradas, calcular KM legado dos fretes do ciclo e deslocamentos informados uma só vez na Etapa 2 | Implementado no MVP |
| RF-07 | Registrar odômetros da saída e da chegada à base na Etapa 2, separados do odômetro do abastecimento na Etapa 7 | Implementado no MVP |
| RF-08 | Registrar Diesel ou ARLA no formulário único da Etapa 7, inclusive sem viagem (destino provisório Veículo) | Implementado no MVP |
| RF-09 | Exibir distância e KM/L/custo por KM indicativos entre abastecimentos consecutivos de Diesel do mesmo veículo | Implementado no MVP |
| RF-10 | Associar a despesa de combustível a um único destino e gerar simultaneamente seu histórico operacional, sem duplicar no DRE | Implementado no MVP |
| RF-11 | Consultar, gerar relatórios e exportar dados operacionais; o Excel inclui aba própria `Abastecimentos_Veiculos` | Implementado no MVP |
| RF-12 | Importar Excel distinguindo fretes, fechamentos e totais gerais | Prévia e conferência disponíveis; gravação automática não habilitada |
| RF-13 | Registrar pagamentos efetivamente recebidos, com data, valor, tipo e referência, sem confundir com parcelas previstas | Implementado no MVP |
| RF-14 | Registrar despesas compartilhadas por ciclo e somá-las uma única vez no fechamento gerencial | Implementado no MVP |
| RF-15 | Consolidar receita negociada e despesas de cada frete por ID interno de ciclo, sem duplicar lançamentos | Implementado no MVP |
| RF-16 | Exibir prévia do ciclo na Etapa 8 e relatório na Etapa 9; exportar `Fechamento_Ciclos` | Implementado no MVP |
| RF-17 | Somar pagamentos efetivos por frete e ciclo; mostrar saldo a receber e possível excedente | Implementado no MVP |
| RF-18 | Cancelar recebimento lançado incorretamente com motivo obrigatório e sem apagar histórico | Implementado no MVP |
| RF-19 | Registrar despesas compartilhadas em ciclo salvo e cancelá-las com histórico e motivo, sem rateá-las pelos fretes | Implementado no MVP |
| RF-20 | Exibir odômetro de abastecimento como campo numérico normal, visível na Etapa 7, sem checkbox | Implementado no MVP |
| RF-21 | Exportar `Despesas_Ciclo` com histórico e `Fechamento_Ciclos` com despesas de fretes e compartilhadas separadas | Implementado no MVP |
| RF-22 | Usar apenas um formulário de despesa com destino Frete/Ciclo/Veículo e odômetro numérico para Diesel/ARLA; histórico somente consulta | Implementado no MVP |
| RF-23 | Registrar custos provisoriamente vinculados ao veículo, inclusive sem frete, mantendo-os fora do DRE e permitindo cancelamento auditável | Implementado no MVP |
| RF-24 | Exportar despesas do veículo (pendentes/atribuídas) e a origem financeira/cancelamento dos abastecimentos | Implementado no MVP |
| RF-25 | Atribuir despesa pendente a frete/ciclo salvo do mesmo veículo, sem segundo histórico de abastecimento nem duplicação no DRE | Implementado no MVP |
| RF-26 | Estornar atribuição, devolver o custo ao veículo e guardar histórico de ações com justificativa | Implementado no MVP |
| RF-27 | Manter único cadastro de despesas, com seções de vínculo e detalhes; permitir consulta/atribuição/cancelamento em áreas separadas de histórico | Implementado no MVP |
| RF-28 | Reconciliar resultado financeiro gerencial de toda a base, separando custo direto de frete, compartilhado de ciclo, gasto pendente de veículo e gasto já atribuído sem dupla soma | Implementado no MVP |
| RF-29 | Disponibilizar `Conferencia_Financeira` no Excel e exportar base completa coerente na Etapa 10, independentemente dos filtros da tabela da tela | Implementado no MVP |
| RF-30 | Mostrar margem como não calculável sem receita confiável, e avisar sobre despesas compartilhadas sem fretes do tipo Ciclo | Implementado no MVP |
| RF-31 | Sinalizar despesas semelhantes entre frete e ciclo do mesmo ID e solicitar confirmação explícita quando forem comprovantes distintos | Implementado no MVP |
| RF-32 | Consultar indícios de repetição já cadastrados, sem alterar histórico, e exportar `Possiveis_Duplicidades` | Implementado no MVP |
| RF-33 | Verificar repetição cruzada também durante atribuição de despesa provisória e impedir repetição imediata de gasto comum idêntico no mesmo frete | Implementado no MVP |
| RF-34 | Consolidar na Etapa 8 o KM das saídas da operação por ID interno do ciclo; apresentar campos antigos somente para compatibilidade histórica | Implementado no MVP |
| RF-35 | Impedir salvar dois fretes distintos com o mesmo ID Frete e bloquear vínculo novo a nome de ciclo que identifique mais de um ID legado | Implementado no MVP |
| RF-36 | Proteger vínculo histórico quando o último frete sair de um ciclo com despesa comum ativa ou quando a placa mudar com abastecimento já registrado | Implementado no MVP |
| RF-37 | Organizar KM de saída/coletas, rota principal e retorno à base no formulário de cada saída da Etapa 2 | Implementado no MVP |
| RF-38 | Calcular automaticamente o KM planejado de cada saída e consolidá-lo no fechamento sem multiplicar o percurso pelos fretes do ciclo | Implementado no MVP |
| RF-39 | Manter a leitura histórica dos campos antigos sem exigir seu preenchimento nas novas saídas, separando odômetro de combustível | Implementado no MVP |
| RF-40 | Exibir na Etapa 8 os KM planejado e real consolidados, as diferenças e os indicadores, sem editar os odômetros novamente | Implementado no MVP |
| RF-41 | Manter na Etapa 8 DRE, situação dos recebimentos e prévia financeira do ciclo para conferência | Implementado no MVP |
| RF-42 | Permitir várias saídas operacionais de um ciclo, com cadastro na Etapa 2 | Implementado no MVP |
| RF-43 | Permitir trechos físicos por saída; a soma dos trechos substitui o KM manual, sem dupla contagem | Implementado no MVP |
| RF-44 | Consolidar KM real das saídas somente com odômetros completos e intervalos sem sobreposição no mesmo veículo | Implementado no MVP |
| RF-45 | Priorizar KM das saídas sobre o modelo de KM comercial/legado quando existir ao menos uma saída cadastrada | Implementado no MVP |
| RF-46 | Estimar Diesel por veículo com km/L e preço de referência, sem lançar nova despesa na DRE | Implementado no MVP |
| RF-47 | Exportar saídas, trechos e KM operacional de ciclos em abas específicas de Excel | Implementado no MVP |
| RF-48 | Salvar e retomar rascunhos incompletos, sem incluí-los na DRE antes do salvamento definitivo | Implementado no MVP |
| RF-49 | Permitir uma ou várias saídas por operação individual ou ciclo, com os mesmos campos e totais calculados na Etapa 2 | Implementado no MVP |
| RF-50 | Manter os parâmetros de consumo referencial por veículo no cadastro (Etapa 11), sem lançamento financeiro automático | Implementado no MVP |
| RF-51 | Reservar a Etapa 8 para situação operacional, indicadores e fechamento, sem recadastrar saídas ou odômetros | Implementado no MVP |

## Critérios de aceite dos cálculos

A fonte principal de KM físico da operação são as **saídas cadastradas na Etapa 2**. Registros anteriores sem saídas continuam consultáveis pela regra histórica, sem exigir duplicação de lançamentos.

1. **Frete individual:** a operação pode ter uma ou mais saídas vinculadas ao seu ciclo interno; a quilometragem física é registrada uma única vez por saída.
2. **Ciclo operacional:** reúne os fretes negociados individualmente e as saídas compartilhadas. O fechamento não multiplica o mesmo percurso pela quantidade de fretes.
3. **KM planejado:** cada saída recebe KM de saída/entre coletas, KM da rota principal e KM de retorno à base. O total planejado é a soma desses três componentes; se houver trechos detalhados antigos, prevalece a soma dos trechos.
4. **Odômetros:** o odômetro inicial é registrado na saída da base e o final na chegada à base, ambos na Etapa 2. O KM real da saída é a diferença entre leituras válidas. Enquanto houver leitura final ausente ou inconsistência, o total real da operação fica pendente.
5. **Retorno e novas saídas:** o retorno integra a saída correspondente; quando o veículo sai novamente da base para a mesma operação, cria-se outra saída, sem replicar KM nos demais fretes.
6. **Fechamento e desvio:** na Etapa 8, são exibidos os KM planejados e reais consolidados; o desvio depende de leitura real válida e de KM planejado positivo. Não existem campos para recadastrar odômetros nessa etapa.
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
25. **Etapas 2, 7 e 8:** o cadastro de saídas, KM planejados e odômetros inicial/final ocorre na Etapa 2. O odômetro do abastecimento é lançado independentemente na Etapa 7. A Etapa 8 apresenta os valores consolidados e o fechamento, sem solicitar novamente os mesmos dados.
26. **Compatibilidade com lançamentos anteriores:** o histórico de KM e odômetros antigos permanece acessível. Os novos percursos utilizam as saídas e seus componentes, sem copiar automaticamente os valores antigos nem zerar registros históricos.

## Requisitos de integridade e implantação

- **RI-01:** não reescrever automaticamente fretes, despesas, códigos de ciclo ou fechamentos históricos por aproximação de linhas da planilha.
- **RI-02:** a importação de Excel mantém prévia e conferência; a gravação de dados importados depende de execução autorizada e tratamento de inconsistências.
- **RI-03:** conservar compatibilidade com tabelas/colunas já publicadas; novas estruturas devem ser ensaiadas em cópia do PostgreSQL antes da produção.
- **RI-04:** validar a identidade do veículo em cada abastecimento; não misturar leituras de veículos distintos nem intervalos de ARLA com Diesel.
- **RI-05:** não usar `0` como leitura medida quando o campo foi deixado em branco; manter ausência de medição distinta de zero real.
- **RI-06:** o MVP não implementa autenticação individual; os dados operacionais ficam em ambiente de acesso restrito e as demonstrações utilizam dados fictícios ou anonimizados.

## Validação dos requisitos

Os cenários de teste ficam centralizados no [plano de testes](plano_testes.md) e nos arquivos de [`tests/`](../tests/). A verificação funcional cobre cadastro de fretes e ciclos, rascunhos, saídas, odômetros, despesas únicas, recebimentos efetivos, fechamento, consultas e exportações.

## Funcionalidades previstas para evolução

A evolução contempla autenticação e permissões individuais, conciliação bancária, importação em lote autorizada e migrações versionadas. O MVP oferece consolidação gerencial por ciclo, sem rateio automático de custos compartilhados.
