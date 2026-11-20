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
| RF-06 | Na Etapa 8, somar KM dos fretes do ciclo + deslocamentos operacionais digitados uma só vez | Proposto; teste pendente |
| RF-07 | Registrar odômetro inicial/final opcional da operação, sem confundir com estimativa de KM | Proposto; teste pendente |
| RF-08 | Registrar Diesel ou ARLA por veículo na Etapa 7, mesmo sem qualquer viagem cadastrada | Proposto em `abastecimentos`; teste pendente |
| RF-09 | Exibir distância e KM/L/custo por KM indicativos entre abastecimentos consecutivos de Diesel do mesmo veículo | Proposto; teste pendente |
| RF-10 | Associar despesas financeiras a fretes sem somar duas vezes o registro informativo de combustível | Parcial: sem alocação automática por ciclo |
| RF-11 | Consultar, gerar relatórios e exportar dados operacionais; o Excel inclui aba própria `Abastecimentos_Veiculos` | Proposto; revisão de indicadores ainda pendente |
| RF-12 | Importar Excel distinguindo fretes, fechamentos e totais gerais | Apenas prévia/auditoria; **gravação bloqueada** |
| RF-13 | Registrar pagamentos efetivamente recebidos, com data, valor, tipo e referência, sem confundir com parcelas previstas | Proposto em `recebimentos_frete`; teste pendente |
| RF-14 | Fechar ciclos com despesas compartilhadas e regra de rateio aprovada | **Pendente** |
| RF-15 | Consolidar receita negociada e despesas de cada frete por ID interno de ciclo, sem duplicar lançamentos | Proposto em `fechamento_ciclos.py`; teste pendente |
| RF-16 | Exibir prévia do ciclo na Etapa 8 e relatório na Etapa 9; exportar `Fechamento_Ciclos` | Proposto; teste pendente |
| RF-17 | Somar pagamentos efetivos por frete e ciclo; mostrar saldo a receber e possível excedente | Proposto; teste pendente |
| RF-18 | Cancelar recebimento lançado incorretamente com motivo obrigatório e sem apagar histórico | Proposto; teste pendente |

## Critérios de aceite dos cálculos

1. **Frete individual:** `KM Planejado` recebe `KM Individual / Ciclo` do próprio frete.
2. **Ciclo:** `KM Planejado` é a soma de `KM Individual / Ciclo` de todos os fretes do ID Ciclo, incluindo o valor ainda não salvo do frete em edição, sem contá-lo duas vezes.
3. **Deslocamentos:** `KM Deslocamentos Operacionais` é um valor manual único do ciclo, referente a trechos ainda não incluídos nos fretes.
4. **Total:** `KM Total Planejado = KM Planejado + KM Deslocamentos Operacionais`.
5. **Real:** quando os dois odômetros operacionais forem válidos, `KM Real = odômetro final − odômetro inicial`; sem as duas leituras, mostrar “Não informado”. Não aceitar final menor que inicial.
6. **Desvio:** quando o KM real estiver disponível, `Diferença = KM Real − KM Total Planejado`; exibir desvio percentual somente com planejado maior que zero.
7. **Abastecimento:** o registro pertence ao **veículo**, não exige `id_viagem`/ID Frete e não modifica os odômetros operacionais.
8. **Consumo:** apenas dois abastecimentos *consecutivos de Diesel* do mesmo veículo com odômetros crescentes permitem `KM entre abastecimentos`; `KM/L = distância / litros do abastecimento atual` e `R$/KM = valor atual / distância`. Informar que essa média é indicativa e pressupõe tanque cheio; ARLA é monitorado separadamente.
9. **DRE:** histórico de abastecimentos não gera automaticamente despesa; somente despesas financeiras associadas à viagem são contabilizadas nesse resultado parcial. Rateio de custos comuns continua pendente.
10. **Fechamento parcial do ciclo:** `Receita negociada do ciclo = soma dos valores negociados dos fretes`, `Despesas do ciclo = soma das despesas financeiras atribuídas aos respectivos fretes` e `Resultado Operacional Parcial = receita negociada − despesas do ciclo`; não contabilizar uma linha de fechamento como frete adicional.
11. **Proteção de registros legados:** se dois ou mais fretes compartilham o mesmo financeiro legado de ciclo, não somar o valor legado uma vez por frete; avisar sobre a necessidade de individualização, sem excluir o histórico.
12. **Parcelas previstas:** adiantamento e saldo são campos contratuais previstos, não equivalem a recebimento efetivo. Não somar o fechamento por ciclo uma segunda vez ao total geral por fretes.
13. **Recebido de fato:** cada lançamento só pode ser atribuído a frete já salvo e deve indicar data, valor positivo, tipo de parcela e meio de pagamento. Referência/comprovante e observação são opcionais; pagamentos idênticos sem referência são tratados como possível duplicidade.
14. **Saldo:** `Recebido de fato = soma dos pagamentos confirmados (não cancelados)` e `Saldo a receber do frete = máximo(0, valor negociado − recebido de fato)`. O saldo do ciclo é a soma dos saldos de seus fretes, sem compensar automaticamente excedente de um frete com outro. Indicar excedentes separadamente; saldos de fretes com financeiro legado ambíguo não devem ser apresentados como exatos.
15. **Correções:** cancelamento exige motivo, preserva o registro, data de cancelamento e valor original. A exportação em Excel deve incluir linhas canceladas com situação identificada, sem computá-las nos totais.

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
- [ ] Confirmar que o DRE não ganhou despesa automaticamente ao salvar abastecimento do veículo.
- [ ] Cadastrar dois fretes no mesmo ciclo e conferir soma de KM e deslocamentos informados uma vez.
- [ ] Cadastrar três fretes de um ciclo, com receitas e despesas diferentes; conferir prévia na Etapa 8, relatório na Etapa 9 e planilha `Fechamento_Ciclos`.
- [ ] Simular dois fretes legados com um único financeiro de ciclo; conferir aviso e receita não duplicada.
- [ ] Registrar adiantamento recebido real, saldo recebido e um pagamento parcial adicional; conferir valores por frete/ciclo.
- [ ] Cancelar pagamento com motivo e conferir exclusão dos totais, sem apagar o histórico na Etapa 4 ou na aba `Recebimentos_Fretes`.
- [ ] Simular reenvio do mesmo comprovante, lançamento acima do negociado e frete ainda não salvo; conferir as proteções.
- [ ] Conferir ausência de valor negociado, adiantamento/saldo previstos e ausência de odômetros sem contabilizar valores fictícios.
- [ ] Salvar operação sem odômetros, com odômetros válidos e com odômetro final inferior ao inicial.
- [ ] Conferir cenário de fechamento e exportação sem viagens e com viagens.
- [ ] Conciliar amostra com a planilha, inspecionar as divergências já relatadas e verificar que nada foi importado sem autorização.
- [ ] Realizar backup e ensaio de migração em banco de testes; somente depois avaliar o deploy no banco oficial.

## Escopo explicitamente não encerrado

Não presumir que a aplicação esteja pronta para produção por existir código. Faltam ao menos: homologação integrada, fechamento **formal** dos ciclos (status/confirmação), despesas compartilhadas e regra de rateio, conciliação bancária e automatização de situações de pagamento, segurança de acesso e importação com gravação autorizada. A consolidação **gerencial parcial** por ciclo e o registro manual de recebimentos já estão propostos.
