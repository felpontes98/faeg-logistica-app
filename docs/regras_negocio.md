# Regras de Negócio — Operação FAEG

Este documento traduz as decisões da operação em comportamento esperado do sistema. **As regras abaixo descrevem o objetivo do produto; nem todas estão implementadas nesta versão.** Eduardo valida as regras operacionais; Felipe e Larissa definem a implementação técnica e os testes.

## Fluxo de preenchimento do MVP

- **Etapa 1:** identificação da operação, veículo e motorista.
- **Etapa 2:** frete, carga, documentos e cadastro sequencial de saídas. Cada saída começa na base, recebe KM de saída/coletas, rota e retorno e é encerrada com o odômetro de chegada à base.
- **Etapas 3 a 6:** cliente, negociação e recebimentos, coleta e entrega, sem alterações na lógica comercial.
- **Etapa 7:** despesa lançada uma vez; gastos compartilhados de ciclo não são multiplicados pelo número de fretes. O odômetro do abastecimento é independente dos odômetros de saída/retorno.
- **Etapa 8:** indicadores, prévia financeira e fechamento, sem cadastro de saídas ou repetição de odômetros.
- **Etapa 11:** parâmetros de consumo de referência por veículo.
- **Salvamento parcial:** rascunhos são recuperáveis e não entram no resultado financeiro até o cadastro definitivo.

Os registros históricos permanecem no banco, mas os campos legados de KM não fazem parte do preenchimento normal. As RN-04 e RN-05 abaixo registram também as regras do modelo anterior para interpretação do histórico.

## RN-01 — Identificação de fretes e ciclos

- Um **frete** é um serviço comercial individual com cliente, carga, rota, valor e documentação próprios. Padrão de referência: `F26-000001`.
- Um **ciclo operacional** agrupa um ou mais fretes e possui código próprio. Padrão de referência: `V26-000001`.
- O código de um frete não deve substituir o código do ciclo. O identificador interno numérico do banco é separado de ambos.
- Um frete individual pode ser fechado isoladamente. Um frete associado a um ciclo participa do fechamento consolidado desse ciclo.
- Uma linha de **FECHAMENTO** não é um novo frete remunerado: é uma consolidação dos registros já existentes.

### Exemplo de agrupamento

| Código do frete | Código do ciclo | Interpretação |
| --- | --- | --- |
| `F26-000002` | `V26-000002` | Primeiro frete do ciclo |
| `F26-000003` | `V26-000002` | Segundo frete do mesmo ciclo |
| `F26-000004` | `V26-000002` | Terceiro frete do mesmo ciclo |
| `F26-000005` | `V26-000002` | Quarto frete do mesmo ciclo |
| `F26-000006` | `V26-000002` | Quinto frete do mesmo ciclo |

No fechamento, a receita será a soma negociada dos cinco fretes e não a soma desses valores **mais** o valor da linha de fechamento.

## RN-02 — Classificações comerciais independentes

| Campo | Exemplos | Finalidade |
| --- | --- | --- |
| Modalidade operacional | Individual / Ciclo | Definir agrupamento e forma de fechamento |
| Tipo de frete | Dedicado, Complemento, Fracionado, Retorno, Transferência | Caracterizar o serviço |
| Origem do frete | Aplicativo, Redes Sociais, Cliente Fixo, Cliente Recorrente, Indicação | Identificar o canal que gerou a contratação |

Uma alteração em uma classificação não deve apagar o cliente, o preço, a identificação do frete nem um ciclo já válido sem confirmação explícita.

## RN-03 — Valor divulgado, negociado, adiantamento e saldo

- **Valor divulgado:** preço anunciado na plataforma ou negociação inicial; preenchimento manual.
- **Valor negociado:** preço efetivamente fechado; preenchimento manual e base do parcelamento.
- **Adiantamento e saldo:** cada um pode ser informado como percentual ou valor em reais; o último campo editado determina o complemento automático dos demais.
- Quando uma parcela é alterada, a outra precisa completar exatamente o valor negociado, respeitando os centavos.
- Percentual total das parcelas: 100%, exceto se o negócio exigir uma condição especial documentada.

**Exemplo:** divulgado = R$ 500,00; negociado = R$ 500,00. Informar `10%` de adiantamento, `R$ 50,00` de adiantamento, `90%` de saldo ou `R$ 450,00` de saldo deve sempre produzir:

| Campo | Resultado |
| --- | ---: |
| Adiantamento | 10% = R$ 50,00 |
| Saldo | 90% = R$ 450,00 |
| Total negociado | R$ 500,00 |

**Atenção:** adiantamento e saldo negociados não significam dinheiro recebido. Na Etapa 4, depois de salvar o frete, os pagamentos recebidos de fato possuem lançamento próprio com data, valor, tipo de parcela, forma de pagamento, referência opcional e observação. O **Total recebido** soma somente lançamentos confirmados; **A receber = máximo entre zero e (valor negociado − total recebido)**. Recebimento acima do negociado exige confirmação explícita e aparece como excedente para conferência. Um lançamento incorreto pode ser cancelado mediante motivo obrigatório, permanecendo no histórico, mas deixa de compor os totais. Não se presume quitação operacional/financeira automaticamente com base na soma.

## RN-04 — Quilometragem planejada por frete e ciclo (modo legado)

> **Prioridade da versão atual:** as regras de soma por frete abaixo aplicam-se **somente enquanto não existir saída operacional cadastrada** para a operação. Com saídas, prevalece a RN-11 e o KM comercial dos fretes não é somado novamente.

Conforme a proposta operacional apresentada por Eduardo para o sistema:

1. Na **Etapa 2 — Frete**, **KM X ROTA PLANEJADO** é somente o título. O usuário informa manualmente **KM DE SAÍDA E DESLOCAMENTO ENTRE COLETAS**, **KM INDIVIDUAL / CICLO** e **KM OPERACIONAL DE RETORNO**. Os dois campos de deslocamento não podem incluir trechos já computados no KM individual do frete.
2. Em um **frete individual**, o KM Planejado corresponde a esse campo.
3. Em um **ciclo**, cada frete tem seu próprio KM Individual / Ciclo. Na Etapa 8, **KM PLANEJADO** é a soma dos KM dos fretes associados ao mesmo **ID interno do ciclo**, considerando o valor ainda não salvo do frete em edição. Nomes iguais em ciclos históricos diferentes **não** autorizam somá-los.
4. **KM DESLOCAMENTOS OPERACIONAIS** é calculado na Etapa 8: **KM de saída/entre coletas + KM operacional de retorno** informados na Etapa 2. Em ciclo, os dois componentes são compartilhados por **ID interno do ciclo**, cadastrados uma única vez e **não** somados novamente para cada frete. No individual, pertencem somente àquela operação.
5. **KM TOTAL PLANEJADO = KM PLANEJADO + KM DESLOCAMENTOS OPERACIONAIS**.
6. Antes de homologar, garantir que os trechos foram definidos sem lacunas ou sobreposições. Não incluir duas vezes a mesma distância no frete e nos deslocamentos operacionais.
7. **Compatibilidade:** ciclos antigos que contêm apenas `km_deslocamentos_operacionais` mantêm o total salvo enquanto os dois componentes novos ainda não forem discriminados. Ao editar os novos campos na Etapa 2, o novo total substitui o legado; conferir ambos os valores antes de salvar.

**Exemplo ilustrativo:** três fretes com 280, 120 e 85 km = **485 km planejados**. Se os deslocamentos operacionais não incluídos nesses fretes somarem 65 km, o **KM Total Planejado será 550 km**.

Esse valor é estimado, não uma leitura real de odômetro. A ausência de KM deve ser sinalizada como dado faltante, não considerada automaticamente zero.

**Proteções de edição:** se o KM manual do frete atual permanece zero, a Etapa 8 alerta que a estimativa pode estar incompleta. Ao editar um frete já salvo, a prévia usa o ID interno de seu ciclo atual, enquanto um novo frete com número de ciclo homônimo em mais de um ID não é vinculado automaticamente. O KM compartilhado não é copiado de um ciclo ambíguo; ao transformar uma operação em Individual, os deslocamentos do ciclo antigo não devem ser carregados indevidamente.

## RN-05 — Odômetro de saída, chegada e abastecimento (modo legado e histórico)

> **Prioridade da versão atual:** com saídas operacionais, o KM real físico é a soma das diferenças dos odômetros das saídas, com verificação de dados ausentes e sobreposição. As leituras legadas dos fretes permanecem preservadas e distintas das leituras de abastecimento. Consulte a RN-11.

Manter três conceitos independentes:

| Leitura | Onde registrar | Utilidade |
| --- | --- | --- |
| KM planejado (Maps) | Frete / trechos do ciclo | Planejamento e análise operacional |
| Odômetro inicial e final da operação (opcionais) | Entrada manual na Etapa 2 **ou** na Etapa 8, no mesmo registro persistido | Apurar percurso real e comparar com o planejado |
| Odômetro no abastecimento (quando disponível) | Campo numérico do lançamento único de Diesel/ARLA na Etapa 7 | Alimentar o histórico por veículo, consumo e manutenção |

Se saída e chegada forem preenchidos para o mesmo veículo e intervalo, **KM real do percurso = odômetro de chegada − odômetro de saída**. Validar que a chegada não é inferior à saída e que leituras pertencem ao veículo correto. Se uma leitura faltar, mostrar **“KM real não informado”**. No ciclo, **KM TOTAL REAL** é a soma dos intervalos reais dos seus fretes, desde que todos tenham dois odômetros válidos e **não haja sobreposição de intervalos no mesmo veículo**; caso contrário, o consolidado não é calculável até conferência. **DIF. KM TOTAL PLANEJADO X REAL = total real − total planejado**. O campo superior `KM REAL RODADO` continua referindo-se ao frete em edição.

Leituras de abastecimento podem ajudar a conferir o histórico e, quando houver duas leituras confiáveis consecutivas, calcular a distância entre abastecimentos. **Não presumir** que essa distância seja automaticamente igual ao KM do ciclo ou do frete: abastecimentos podem ocorrer no meio de vários serviços.

Na implementação preparada, a Etapa 7 contém **um único formulário para registrar despesa**, inclusive combustível, e um **histórico de abastecimentos somente para consulta**, identificado por `id_veiculo`. Ao selecionar Diesel/ARLA, aparecem juntos litros, preço por litro e o campo numérico **ODÔMETRO NO ABASTECIMENTO (KM)**, sem checkbox. Digitar `0` significa leitura não informada (`NULL`), nunca um odômetro medido de zero. O registro do custo gera simultaneamente a linha operacional `abastecimentos`, sem segundo lançamento manual. Pode ser registrado com **zero viagens** no banco escolhendo o destino provisório "Veículo". ARLA fica no histórico, mas não entra na estimativa de consumo de Diesel.

O indicador `KM entre abastecimentos` é a diferença positiva entre odômetros de **dois registros consecutivos de Diesel do mesmo veículo**. O `KM/L indicativo` divide essa distância pelos litros do abastecimento mais recente, e `R$/KM indicativo` divide seu valor total pela distância. Somente são estimativas úteis quando há histórico completo de abastecimentos de **tanque cheio**; abastecimento parcial, registro omitido ou odômetro inconsistente invalidam a interpretação de consumo real. Sem duas leituras válidas, exibir indicador **não disponível**, nunca `0 km/L` fictício.

O campo `viagens_despesas.odometro_abastecimento` não é excluído. Em novos lançamentos vinculados ao frete, a leitura é guardada nessa despesa e projetada no registro operacional `abastecimentos`, **pelo mesmo clique**, sem segunda entrada. Abastecimentos legados independentes são mantidos, sem migração ou reclassificação automática; a Etapa 8 apresenta apenas resumo indicativo de consumo do veículo, separado do fechamento financeiro.

## RN-06 — Despesas e abastecimento

- Cada despesa deve ter categoria, descrição, data, valor e associação clara a **um frete**, **um ciclo** ou, provisoriamente, **um veículo**.
- Despesa de uso comum no ciclo entra **uma vez** no fechamento consolidado, sem cópia integral em cada frete.
- A Etapa 7 possui **um formulário único** para despesas, com campos agrupados em **Vínculo financeiro** e **Dados da despesa**: padrão **Ciclo inteiro quando o frete pertence a ciclo**, ou **Frete atual em operação individual**, opção **Ciclo inteiro** (`ciclos_despesas`, apenas ciclo salvo), opção **Veículo sem frete/ciclo** (`veiculos_despesas`, pendente). Despesas provisórias não entram em DRE/BI enquanto pendentes. A **atribuição posterior** a frete/ciclo é uma ação explícita, com justificativa, exclusiva para destinos do mesmo veículo; o custo passa ao destino, nunca é duplicado. Cancelamentos de gastos comuns/provisórios preservam histórico e motivo. A proteção de lançamentos semelhantes não elimina a necessidade de conferência humana.
- Caso seja necessário mostrar custo individual de cada frete do ciclo, estabelecer antes um critério de rateio acordado (por exemplo, participação na receita ou quilômetros), identificando o valor rateado como estimativa gerencial. **O rateio ainda não foi definido.**
- Um abastecimento deve registrar data, veículo, posto/fornecedor, litros, preço por litro, valor e odômetro quando disponível. Diesel e ARLA devem ser distinguíveis.
- Evitar lançamento em duplicidade quando o abastecimento também aparece como despesa financeira.
- **Ao lançar o combustível uma única vez**, a aplicação grava a despesa financeira no destino escolhido e um reflexo operacional no histórico `abastecimentos`. **Só a despesa financeira de frete ou ciclo entra no respectivo DRE**, não a linha de abastecimento. Para veículo ainda sem destino, o custo fica pendente, fora do DRE. Quando for atribuído a um frete/ciclo salvo do mesmo veículo, o lançamento financeiro passa a contar no destino **sem recriar a linha de abastecimento**. Um estorno devolve o custo ao estado pendente, com evento auditável. Não lançar a mesma nota manualmente em destinos diferentes.
- **Conferência cruzada de possível duplicação:** na Etapa 7, despesas financeiramente atribuídas a um frete são comparadas com despesas compartilhadas ativas do **mesmo ID Ciclo**, e vice-versa. A comparação considera data, categoria, quantidade, valor unitário, valor total, descrição e fornecedor; quando há informações disponíveis, também compara veículo e odômetro no combustível. Coincidência é **indício, não prova**: exige conferência do comprovante e confirmação explícita de gasto distinto antes de continuar o lançamento. A atribuição de uma despesa provisória já existente possui a mesma proteção; a justificativa da atribuição registra a razão. Repetição imediata de despesas idênticas dentro do mesmo frete também é bloqueada. Isso não substitui identificação única de NF-e/comprovante nem conciliação humana.

## RN-07 — Fechamento e resultado operacional

**Frete individual:** receita negociada do frete − despesas atribuídas ao frete = resultado operacional apurado com os custos disponíveis.

**Ciclo:** soma da receita negociada dos fretes vinculados − despesas dos fretes − despesas compartilhadas do ciclo = resultado operacional do ciclo.

**Implementação parcial proposta:** a Etapa 8 apresenta uma **prévia** financeira do ciclo considerando os fretes já salvos, o formulário atual e despesas comuns ativas vinculadas a esse `id_ciclo`, sem somar nada duas vezes. A Etapa 9 reúne os fretes salvos por `id_ciclo`; a aba `Fechamento_Ciclos` separa despesas por frete e compartilhadas, e `Despesas_Ciclo` mantém o histórico auditável. **Não existe rateio:** o BI por frete/cliente não incorpora as despesas compartilhadas, enquanto o fechamento do ciclo as incorpora uma vez. Não somar ambos os painéis.

**Conferência Financeira Geral:** a Etapa 9 apresenta uma visão independente dos filtros do BI, baseada na base inteira salva. `Resultado operacional parcial gerencial = receita negociada considerada dos fretes − despesas diretas dos fretes − despesas compartilhadas ativas dos ciclos`. As fontes financeiras são `viagens_despesas` e `ciclos_despesas`; `abastecimentos` serve ao histórico de consumo e **não é somado novamente**. Despesas de veículo **pendentes** ficam fora desse resultado; despesas de veículo **já atribuídas** são apenas informação de origem e **já estão contadas no destino financeiro**. A conferência inclui custos ativos de ciclos mesmo que, por inconsistência cadastral, não haja fretes do tipo Ciclo associados, e sinaliza essa situação. A planilha exporta a mesma composição em `Conferencia_Financeira`.

A mesma seção mostra uma lista somente leitura dos **possíveis custos repetidos entre frete e ciclo**, com IDs financeiros para rastreio e exportação em `Possiveis_Duplicidades`. Não existe cancelamento, estorno ou transferência automática em decorrência desses indícios. Descrições genéricas iguais e abastecimentos distintos podem gerar alertas, que exigem verificação operacional antes de qualquer correção.

O novo cadastro `recebimentos_frete` pertence a um único frete. O resumo por ciclo soma exclusivamente pagamentos confirmados dos seus fretes; cancelados não contribuem. **Saldo a receber do ciclo = soma dos saldos não negativos de cada frete**. Valores recebidos acima do negociado em um frete são mostrados como excedentes e **não abatem automaticamente** o saldo de outro frete. Quando houver financeiro legado ambíguo, o saldo do ciclo fica marcado como pendente de conferência. Os registros completos, incluindo cancelamentos, são exportados separadamente em `Recebimentos_Fretes`.

Em vários fretes antigos que compartilham a mesma linha de `ciclos_financeiro`, não é possível saber a receita negociada de cada frete: a prévia/relatório os **marca para conferência e exclui a receita financeira legada ambígua**, evitando multiplica-la pelo número de fretes. Nenhum dado histórico é apagado ou redistribuído. Valor de adiantamento e saldo negociados são **parcelas previstas**, não comprovam pagamento efetivo.

Quando a receita considerada é zero, a margem percentual fica **não calculável**, e não `0%` fictício. Na conferência geral e no BI, a margem também é omitida quando há financeiro legado ambíguo, pois o denominador conhecido não representa a receita completa.

Resultados por frete e por ciclo não devem ser somados simultaneamente em um dashboard de totais, porque representariam os mesmos valores em níveis diferentes.

Usar **“Resultado Operacional”** ou **“Resultado Operacional Parcial”** em vez de “Lucro Líquido” enquanto impostos, salários, seguros, custos fixos e demais itens necessários ao lucro líquido não estiverem incluídos.

## RN-08 — Situação do serviço e situação financeira

São controles diferentes:

- **Operacional:** Negociado, Aguardando Coleta, Em Transporte, Entregue, Cancelado, Fechado (rótulos finais a validar).
- **Financeiro:** Sem Recebimento, Parcialmente Recebido, Quitado, Em Atraso (rótulos finais a validar). Os valores efetivamente recebidos agora são registrados, mas a situação financeira automática ainda não foi implementada.

Um frete pode estar **entregue e ainda com saldo pendente**. A entrega não deve marcar automaticamente a quitação.

## RN-09 — Importação da planilha original

O importador precisa reconhecer os IDs de frete e ciclo, as linhas de fechamento, as colunas de receitas, despesas, KM e os campos de observação. A linha “FECHAMENTO” deve alimentar a conferência do ciclo, **sem se tornar outro frete**.

Campos ausentes não devem ser substituídos por datas atuais ou valores zero sem regra explícita. Antes de gravar, apresentar divergências e solicitar confirmação; em uma reimportação, não apagar despesas editadas manualmente sem autorização.

## RN-10 — Validação e decisões ainda pendentes

- [x] Eduardo definiu a separação entre KM Individual/Ciclo, deslocamentos operacionais e total planejado. A implementação ainda precisa de teste integrado.
- [x] Gastos comuns podem ser registrados uma vez por ID do ciclo, sem rateio automático (implementação pendente de testes).
- [x] Registro provisório de despesas sem operação identificada por veículo, fora do DRE (implementação pendente de testes).
- [x] Atribuição manual e estorno auditável de despesas provisórias por veículo a fretes/ciclos compatíveis (implementação pendente de testes).
- [ ] A equipe decide se haverá rateio de custos compartilhados entre os fretes e aprova seu critério.
- [ ] A equipe aprova a nomenclatura final das situações operacional e financeira.
- [ ] São preparados cenários reais anonimizados para teste individual e por ciclo.
- [ ] Todas as alterações preservam histórico já cadastrado após teste de migração.
## RN-11 — Saídas operacionais, trechos e custo de combustível (Ajuste 27)

**Regra prioritária quando existem saídas cadastradas no mesmo ID interno da operação** (individual ou ciclo):

1. **Operação/Ciclo:** representa o planejamento físico de saída e retorno à base, podendo englobar dias e várias saídas preparatórias. **Frete:** representa cada contrato comercial, com cliente, negociação, recebimentos e documentos independentes. O mesmo ciclo pode ter fretes simultâneos ou sequenciais, inclusive de retorno.
2. **Saída operacional:** representa um deslocamento físico identificável da van, com veículo, motorista opcional, data inicial/final, KM planejado e odômetros inicial/final. São admitidas diversas saídas no mesmo ciclo, mesmo com retorno intermediário à base.
3. **Trechos:** permitem detalhar uma saída em deslocamentos entre base, coletas, entregas e retorno. Se houver trechos detalhados, o KM planejado físico da saída é a **soma dos trechos**; o KM manual da saída não se soma novamente. Sem trechos, usa-se o KM manual da saída.
4. **KM operacional planejado:** soma os KM das saídas vinculadas ao ID interno do ciclo, uma vez cada. Não soma automaticamente os KM comerciais dos fretes quando existem saídas registradas. Esses KM por frete permanecem preservados para consulta/comparação.
5. **KM real:** diferença entre os odômetros de cada saída, somada no ciclo **apenas se todas as saídas tiverem leituras válidas** e não houver sobreposição de intervalos no mesmo veículo. Sem esse requisito, o consolidado é **pendente**, não zero.
6. **Despesas:** gastos comuns pertencem ao ciclo. Custos comprovadamente exclusivos podem pertencer a um frete. O relatório por frete de um ciclo **não representa lucro individual** e não recebe rateio artificial.
7. **Abastecimento versus consumo:** cada compra de Diesel/ARLA mantém data, litros, odômetro, veículo e valor efetivamente pago no lançamento único original. Para estimar Diesel consumido na operação, usa-se **KM real por veículo ÷ consumo médio em km/L × preço de referência por litro**. Trata-se de **simulação gerencial**, não de um segundo lançamento financeiro.
8. **Transição financeira:** a DRE existente continua apresentando as despesas efetivamente vinculadas a fretes/ciclos. O valor **estimado** de consumo não é somado nem subtraído novamente. Uma futura mudança para regime de combustível consumido deve antes reconciliar estoque inicial/final e compras existentes, com migração revisada.
9. **Compatibilidade:** não migrar automaticamente KM, odômetros ou despesas do primeiro frete do Ciclo 001 (ou qualquer registro anterior). As novas saídas são cadastradas separadamente; até a criação da primeira saída o fechamento utiliza o cálculo anterior por frete.
10. **Conversão individual → ciclo:** continua dependendo das validações e dos vínculos já existentes; não há conversão automática de históricos/recebimentos/despesas nesta implementação.

**Cuidado:** a tela de controle de consumo é estimativa operacional; não é apuração de estoque contábil, fiscal ou de custo de combustível efetivo por tanque. As compras continuam no histórico real. As diferenças exigem conferência posterior antes de adotar novos resultados contábeis.
