# Requisitos do Sistema FAEG

**Objetivo:** consolidar as necessidades da operação de transportes da FAEG em requisitos verificáveis. Este documento distingue o comportamento identificado no código de ajustes solicitados para versões futuras.

**Estado:** especificação de trabalho. “Existente no código” não significa que foi homologado com banco de dados. As regras detalhadas estão em [Regras de negócio](regras_negocio.md); o desenho atual e as alterações necessárias ao banco estão em [Arquitetura do banco](arquitetura_banco.md). As tarefas de implementação podem ser acompanhadas nas Issues do GitHub.

## 1. Termos utilizados

| Termo | Significado |
| --- | --- |
| Frete | Serviço comercial com cliente, valor, coleta, entrega e documentos próprios |
| Frete individual | Frete executado e analisado isoladamente |
| Ciclo operacional | Conjunto de um ou vários fretes realizados dentro de um mesmo percurso/agrupamento operacional |
| Fechamento | Consolidação de receitas, despesas e quilometragem de um frete individual ou de um ciclo, sem criar receita duplicada |
| Origem do frete | Canal comercial de captação: aplicativo, rede social, cliente fixo etc. |
| Tipo de frete | Característica do serviço: dedicado, complemento, fracionado, retorno ou transferência |
| Valor previsto | Parcela acordada ou programada, sem comprovação de recebimento |
| Valor recebido | Entrada financeira confirmada, com data e valor registrado |

## 2. Requisitos funcionais

| ID | Requisito e critério principal | Situação no código analisado |
| --- | --- | --- |
| RF-01 | Cadastrar, consultar e editar motoristas, veículos, clientes, locais e fornecedores | Existe interface e persistência; requer testes |
| RF-02 | Registrar um frete com cliente, motorista, veículo, carga, rota, datas e documentos fiscais | Existe interface e persistência; requer testes |
| RF-03 | Usar código único e permanente para cada frete (padrão desejado `F26-000001`) | Parcial: código da viagem `V1`, `V2` e campo externo de frete |
| RF-04 | Identificar o ciclo por código distinto do frete (`V26-000001`) | Parcial: campo livre de ciclo; agrupamento ainda inadequado |
| RF-05 | Vincular vários fretes ao mesmo ciclo sem repetir despesas e fechamento | **Pendente**: código cria um ciclo por viagem |
| RF-06 | Distinguir tipo de operação, tipo de frete e origem/canal de captação | Parcial: listas separadas na interface, revisar nomes e dados |
| RF-07 | Calcular adiantamento e saldo a partir de percentual ou valor monetário | Existe lógica de interação; exige testes de limites e arredondamento |
| RF-08 | Registrar parcelas previstas e recebimentos efetivos separadamente | **Pendente**: o total de parcelas é exibido como “recebido” |
| RF-09 | Registrar despesas de viagens individuais e despesas do ciclo sem duplicidade | Parcial: despesas estão associadas apenas a viagens |
| RF-10 | Somar KM planejado por trecho e exibir o total do ciclo no fechamento | **Pendente**: não há soma consolidada por ciclo |
| RF-11 | Registrar odômetro opcional na saída, chegada e abastecimentos | Parcial: há odômetro inicial/final da viagem, sem cadastro próprio de abastecimentos |
| RF-12 | Apresentar fechamento individual ou de ciclo, custos, receita e resultado operacional | Parcial: painel calcula por viagem; fechamento do ciclo precisa revisão |
| RF-13 | Consultar, editar e exportar dados em relatórios Excel e PDF | Existe interface; requer testes e conciliação |
| RF-14 | Importar planilha com prévia, validação e conciliação antes de gravar | **Pendente**: chamadas do app incompatíveis com o importador |
| RF-15 | Diferenciar situação operacional do frete e situação de recebimento | **Pendente**: situação atual mistura os dois conceitos |
| RF-16 | Controlar quem pode consultar, alterar, importar e excluir informações | **Pendente**: não foi identificada autenticação nesta versão |

## 3. Requisitos não funcionais

| ID | Requisito | Verificação de aceite |
| --- | --- | --- |
| RNF-01 | Segurança | Autenticação e autorização de operações antes de disponibilizar dados reais a usuários externos |
| RNF-02 | Integridade | Chaves únicas, relacionamentos válidos e transações para salvar dados consistentes |
| RNF-03 | Rastreabilidade | Registrar criação, edição, exclusão e importação com data e responsável, conforme necessidade operacional |
| RNF-04 | Recuperação | Existência de backup testado e procedimento de restauração antes de migrações ou importações grandes |
| RNF-05 | Privacidade | Restringir acesso a CPF, CNH, contatos, valores, documentos e informações comerciais |
| RNF-06 | Confiabilidade | Testes automatizados de cálculos, agrupamentos e importação por amostra real da planilha |
| RNF-07 | Manutenção | Separar gradualmente interface, regras de negócio, persistência e relatórios |
| RNF-08 | Compatibilidade | Definir versões de dependências e testar execução no ambiente local e de hospedagem |

## 4. Critérios de aceite operacionais (exemplos)

### CA-01 — Negociação bidirecional

**Dado** um frete de R$ 500,00, **quando** o operador informar qualquer uma destas entradas:

- Adiantamento de 10%: sistema calcula R$ 50,00 de adiantamento e R$ 450,00 de saldo (90%).
- Adiantamento de R$ 50,00: calcula 10% e completa os outros campos.
- Saldo de 90%: calcula R$ 450,00 e R$ 50,00 de adiantamento (10%).
- Saldo de R$ 450,00: calcula 90% e completa adiantamento.

**Então** o total negociado permanece R$ 500,00. Campos negativos ou acima do valor negociado devem ser rejeitados/avisados. **Importante:** nenhum desses cálculos comprova o efetivo recebimento.

### CA-02 — Vários fretes em um ciclo

**Dado** o ciclo `V26-000002`, contendo `F26-000002`, `F26-000003`, `F26-000004`, `F26-000005` e `F26-000006`, **quando** o fechamento for consultado, **então**:

1. O ciclo aparece uma única vez como agrupador.
2. A receita do fechamento corresponde à soma dos valores negociados dos cinco fretes, sem adicionar novamente a linha “FECHAMENTO”.
3. Despesas comuns do ciclo são somadas somente uma vez.
4. O operador consegue abrir cada frete e também consultar o resultado consolidado do ciclo.

### CA-03 — Quilometragem planejada e real

**Dado** um ciclo com três trechos estimados de 150 km, 100 km e 80 km, **quando** o operador visualizar a etapa de fechamento, **então** o KM planejado do ciclo deve ser **330 km**. O KM real, se informado por odômetro de saída/chegada, deve aparecer como um indicador independente, com eventual diferença para o planejado.

Se não houver leitura real, o sistema deve exibir **“não informado”**, sem transformar a ausência em zero quilômetro rodado. Leituras obtidas em abastecimentos permanecem vinculadas ao abastecimento e ao veículo.

### CA-04 — Conciliação da importação

**Dado** um arquivo Excel com linhas de fretes, linhas de fechamento e despesas, **quando** o usuário solicitar importação, **então** o sistema deve:

1. Apresentar o número de fretes e ciclos detectados e eventuais campos não reconhecidos.
2. Exibir uma prévia das receitas, despesas e diferenças para conferência.
3. Pedir confirmação antes de alterar dados.
4. Não substituir despesas já editadas sem confirmação explícita e plano de recuperação.
5. Manter os totais consolidados sem duplicar a linha de fechamento.

### CA-05 — Recebimentos reais

Um frete negociado por R$ 500,00, com adiantamento planejado de R$ 50,00 e saldo de R$ 450,00, deve exibir **R$ 0,00 recebido** até existir confirmação. Após registrar o primeiro pagamento, deve exibir **R$ 50,00 recebido** e **R$ 450,00 a receber**.

## 5. Validações antes da homologação

- [ ] Eduardo confirma os conceitos e exemplos deste documento.
- [ ] Felipe e Larissa identificam onde cada requisito será implementado.
- [ ] Banco de testes contém cenário individual, ciclo com vários fretes e despesas compartilhadas.
- [ ] Totais são conciliados com a planilha original.
- [ ] Testes de segurança, importação, edição e exclusão são realizados antes da produção.