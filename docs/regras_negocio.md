# Regras de Negócio — Operação FAEG

Este documento traduz as decisões da operação em comportamento esperado do sistema. **As regras abaixo descrevem o objetivo do produto; nem todas estão implementadas nesta versão.** Eduardo valida as regras operacionais; Felipe e Larissa definem a implementação técnica e os testes.

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

**Atenção:** adiantamento e saldo negociados não significam dinheiro recebido. Pagamentos confirmados precisam ter valor, data e referência próprios. O indicador **Total recebido** soma apenas recebimentos confirmados; **A receber** é o negociado menos o recebido, com tratamento separado para estornos e cancelamentos.

## RN-04 — Quilometragem planejada por frete e ciclo

Conforme a proposta operacional apresentada por Eduardo para o sistema:

1. Na **Etapa 2 — Frete**, **KM X ROTA PLANEJADO** é somente o título; **KM INDIVIDUAL / CICLO** é o campo numérico preenchido manualmente para o trecho do frete.
2. Em um **frete individual**, o KM Planejado corresponde a esse campo.
3. Em um **ciclo**, cada frete tem seu próprio KM Individual / Ciclo. Na Etapa 8, **KM PLANEJADO** é a soma dos KM dos fretes associados ao mesmo número de ciclo, considerando o valor ainda não salvo do frete em edição.
4. **KM DESLOCAMENTOS OPERACIONAIS** é informado manualmente **uma vez por ciclo**, abrangendo os deslocamentos de saída, entre coletas/entregas e retorno que não estejam incluídos nos trechos individuais. O campo é independente do odômetro.
5. **KM TOTAL PLANEJADO = KM PLANEJADO + KM DESLOCAMENTOS OPERACIONAIS**.
6. Antes de homologar, garantir que os trechos foram definidos sem lacunas ou sobreposições. Não incluir duas vezes a mesma distância no frete e nos deslocamentos operacionais.

**Exemplo ilustrativo:** três fretes com 280, 120 e 85 km = **485 km planejados**. Se os deslocamentos operacionais não incluídos nesses fretes somarem 65 km, o **KM Total Planejado será 550 km**.

Esse valor é estimado, não uma leitura real de odômetro. A ausência de KM deve ser sinalizada como dado faltante, não considerada automaticamente zero.

## RN-05 — Odômetro de saída, chegada e abastecimento

Manter três conceitos independentes:

| Leitura | Onde registrar | Utilidade |
| --- | --- | --- |
| KM planejado (Maps) | Frete / trechos do ciclo | Planejamento e análise operacional |
| Odômetro saída e chegada (opcionais) | Fechamento do individual ou ciclo | Apurar percurso real e comparar com o planejado |
| Odômetro no abastecimento (quando disponível) | Registro independente de Diesel/ARLA por veículo na Etapa 7 | Histórico do veículo, consumo e manutenção |

Se saída e chegada forem preenchidos para o mesmo veículo e intervalo, **KM real do percurso = odômetro de chegada − odômetro de saída**. Validar que a chegada não é inferior à saída e que leituras pertencem ao veículo correto. Se uma leitura faltar, mostrar **“KM real não informado”**.

Leituras de abastecimento podem ajudar a conferir o histórico e, quando houver duas leituras confiáveis consecutivas, calcular a distância entre abastecimentos. **Não presumir** que essa distância seja automaticamente igual ao KM do ciclo ou do frete: abastecimentos podem ocorrer no meio de vários serviços.

Na implementação preparada, a Etapa 7 contém um **histórico de abastecimentos independente de ID de frete**, identificado por `id_veiculo`. Cada registro de `abastecimentos` conserva a data, tipo (Diesel/ARLA), litros, preço por litro, total, fornecedor opcional e odômetro opcional. Pode ser registrado mesmo com **zero viagens** no banco. ARLA fica no histórico, mas não entra na estimativa de consumo de Diesel.

O indicador `KM entre abastecimentos` é a diferença positiva entre odômetros de **dois registros consecutivos de Diesel do mesmo veículo**. O `KM/L indicativo` divide essa distância pelos litros do abastecimento mais recente, e `R$/KM indicativo` divide seu valor total pela distância. Somente são estimativas úteis quando há histórico completo de abastecimentos de **tanque cheio**; abastecimento parcial, registro omitido ou odômetro inconsistente invalidam a interpretação de consumo real. Sem duas leituras válidas, exibir indicador **não disponível**, nunca `0 km/L` fictício.

O campo legado `viagens_despesas.odometro_abastecimento` não é excluído (compatibilidade com eventuais registros da versão anterior), mas **novos lançamentos** de odômetro são feitos em `abastecimentos`. Nada é migrado ou duplicado automaticamente; a Etapa 8 apresenta apenas um resumo indicativo de consumo do veículo, separado do fechamento do frete/ciclo.

## RN-06 — Despesas e abastecimento

- Cada despesa deve ter categoria, descrição, data, valor e associação clara a um **frete individual** ou a **um ciclo**.
- Despesa de uso comum no ciclo entra **uma vez** no fechamento consolidado, sem cópia integral em cada frete.
- Caso seja necessário mostrar custo individual de cada frete do ciclo, estabelecer antes um critério de rateio acordado (por exemplo, participação na receita ou quilômetros), identificando o valor rateado como estimativa gerencial. **O rateio ainda não foi definido.**
- Um abastecimento deve registrar data, veículo, posto/fornecedor, litros, preço por litro, valor e odômetro quando disponível. Diesel e ARLA devem ser distinguíveis.
- Evitar lançamento em duplicidade quando o abastecimento também aparece como despesa financeira.
- O histórico operacional `abastecimentos` **não gera automaticamente** um lançamento em `viagens_despesas` nem entra no DRE; quando o custo pertencer claramente a um frete, registrar a despesa financeira na Etapa 7 separadamente. Alocação automática por ciclo depende de regra de rateio ainda não aprovada.

## RN-07 — Fechamento e resultado operacional

**Frete individual:** receita negociada do frete − despesas atribuídas ao frete = resultado operacional apurado com os custos disponíveis.

**Ciclo:** soma da receita negociada dos fretes vinculados − despesas dos fretes − despesas compartilhadas do ciclo = resultado operacional do ciclo.

**Implementação parcial proposta:** a Etapa 8 apresenta uma **prévia** financeira do ciclo considerando os fretes já salvos e o formulário atual, sem somá-lo duas vezes. A Etapa 9 reúne os fretes salvos por `id_ciclo` e a exportação inclui a aba `Fechamento_Ciclos`. O cálculo inclui somente as despesas vinculadas a cada frete. **Ainda não existe lançamento independente de despesa compartilhada no ciclo**, nem rateio.

Em vários fretes antigos que compartilham a mesma linha de `ciclos_financeiro`, não é possível saber a receita negociada de cada frete: a prévia/relatório os **marca para conferência e exclui a receita financeira legada ambígua**, evitando multiplica-la pelo número de fretes. Nenhum dado histórico é apagado ou redistribuído. Valor de adiantamento e saldo negociados são **parcelas previstas**, não comprovam pagamento efetivo.

Resultados por frete e por ciclo não devem ser somados simultaneamente em um dashboard de totais, porque representariam os mesmos valores em níveis diferentes.

Usar **“Resultado Operacional”** ou **“Resultado Operacional Parcial”** em vez de “Lucro Líquido” enquanto impostos, salários, seguros, custos fixos e demais itens necessários ao lucro líquido não estiverem incluídos.

## RN-08 — Situação do serviço e situação financeira

São controles diferentes:

- **Operacional:** Negociado, Aguardando Coleta, Em Transporte, Entregue, Cancelado, Fechado (rótulos finais a validar).
- **Financeiro:** Sem Recebimento, Parcialmente Recebido, Quitado, Em Atraso (rótulos finais a validar).

Um frete pode estar **entregue e ainda com saldo pendente**. A entrega não deve marcar automaticamente a quitação.

## RN-09 — Importação da planilha original

O importador precisa reconhecer os IDs de frete e ciclo, as linhas de fechamento, as colunas de receitas, despesas, KM e os campos de observação. A linha “FECHAMENTO” deve alimentar a conferência do ciclo, **sem se tornar outro frete**.

Campos ausentes não devem ser substituídos por datas atuais ou valores zero sem regra explícita. Antes de gravar, apresentar divergências e solicitar confirmação; em uma reimportação, não apagar despesas editadas manualmente sem autorização.

## RN-10 — Validação antes de programar mudanças

- [x] Eduardo definiu a separação entre KM Individual/Ciclo, deslocamentos operacionais e total planejado. A implementação ainda precisa de teste integrado.
- [ ] A equipe decide como registrar gastos comuns e se haverá rateio individual.
- [ ] A equipe aprova a nomenclatura final das situações operacional e financeira.
- [ ] São preparados cenários reais anonimizados para teste individual e por ciclo.
- [ ] Todas as alterações preservam histórico já cadastrado após teste de migração.
