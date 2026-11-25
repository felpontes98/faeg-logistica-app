# Arquitetura do banco de dados

A persistência utiliza PostgreSQL (Neon), SQLAlchemy ORM e sessões definidas em `database/connection.py`. A estrutura das entidades e a rotina de sincronização estão em [`database/models.py`](../database/models.py). O modelo contém **19 tabelas**.

## Inventário das tabelas

| Tabela | Chave primária | Finalidade e vínculo principal |
| --- | --- | --- |
| `motoristas` | `id_motorista` | Cadastro de motoristas, incluindo CPF e CNH |
| `veiculos` | `id_veiculo` | Cadastro de veículo, placa e RENAVAM |
| `clientes` | `id_cliente` | Contratantes, documentos e contatos |
| `locais` | `id_local` | Endereços de coleta/entrega; `id_cliente` é opcional |
| `fornecedores` | `id_fornecedor` | Postos e prestadores de serviço |
| `ciclos_operacionais` | `id_ciclo` | Nome, cliente de referência, datas, status, total `km_deslocamentos_operacionais` e componentes opcionais `km_saida_entre_coletas` e `km_retorno_operacional` (únicos por ciclo) |
| `ciclos_financeiro` | `id_ciclo` (também FK) | Valores legados do ciclo; mantidos para compatibilidade histórica |
| `viagens` | `id_viagem` | Frete/viagem com código, motorista, veículo, rota e documentos; `id_ciclo` pode ser compartilhado |
| `fretes_financeiro` | `id_viagem` (também FK) | Cadastro de negociação com cliente, negociação, percentuais e parcelas específicos do frete |
| `recebimentos_frete` | `id_recebimento` | Pagamentos efetivos, cada um associado a um frete via `id_viagem`, com data, valor, forma, referência e status de cancelamento |
| `viagens_despesas` | `id_despesa` | Despesa financeira ligada a `id_viagem`; fornecedor e campo legado `odometro_abastecimento` são opcionais |
| `ciclos_despesas` | `id_despesa_ciclo` | Despesa compartilhada associada uma vez ao `id_ciclo`, com fornecedor opcional e cancelamento auditável; não é distribuída por frete |
| `veiculos_despesas` | `id_despesa_veiculo` | Origem de gasto do veículo: **pendente fora dos resultados** ou atribuído a frete/ciclo (contabilizado apenas no destino), com cancelamento auditável |
| `veiculos_despesas_atribuicoes` | `id_evento` | Eventos imutáveis de atribuição/estorno com destino, data/hora e justificativa |
| `abastecimentos` | `id_abastecimento` | Visão operacional de Diesel/ARLA por veículo, criada a partir da **mesma despesa**, com vínculo à despesa de frete/ciclo/veículo, odômetro e cancelamento |
| `saidas_operacionais` | `id_saida` | Saídas físicas de um ciclo (inclusive individual), com veículo, motorista opcional, datas, três componentes de KM planejado, odômetros e total calculado |
| `rascunhos_viagens` | `id_rascunho` | Formulário parcialmente preenchido, incluindo saídas e despesas provisórias, sem afetar a DRE antes do salvamento definitivo |
| `trechos_operacionais` | `id_trecho` | Trechos físicos pertencentes a uma saída; usados como KM planejado quando cadastrados |
| `parametros_consumo_veiculo` | `id_veiculo` (também FK) | km/L e preço/litro referenciais por veículo para estimativa de consumo |

## Relacionamentos e integridade

- Cada frete em `viagens` possui identificador próprio e pode estar associado ao `id_ciclo` de `ciclos_operacionais`; o cliente e a negociação individuais ficam em `fretes_financeiro`.
- `saidas_operacionais` pertence ao ciclo operacional, inclusive em operações individuais. Uma saída pode ter vários `trechos_operacionais`. O KM planejado dos trechos, quando presente, substitui o KM manual da mesma saída.
- `recebimentos_frete` registra pagamentos efetivos separadamente das parcelas previstas; cancelamentos não apagam o histórico.
- Os custos de `viagens_despesas` pertencem ao frete e os de `ciclos_despesas` pertencem ao ciclo. Não há rateio automático dos custos compartilhados.
- `veiculos_despesas` permite registrar gastos provisórios sem frete. A atribuição a frete/ciclo possui histórico em `veiculos_despesas_atribuicoes`; a origem provisória não é novamente somada ao resultado.
- `abastecimentos` mantém o histórico operacional de Diesel/ARLA vinculado ao lançamento financeiro que lhe deu origem, sem gerar outra despesa.
- `rascunhos_viagens` guarda formulários incompletos. Antes do salvamento definitivo, esses registros ficam fora da DRE.
- `parametros_consumo_veiculo` guarda referências de km/L e preço/litro para estimativa gerencial, sem impacto automático no resultado financeiro.

Os relacionamentos e os campos principais estão nos [diagramas ER](diagramas/entidade_relacionamento.md) e [de classes](diagramas/classes.md). As classes SQLAlchemy são a referência para atributos e restrições efetivamente definidos pela aplicação.

## Quilometragem e resultado

As saídas físicas são cadastradas na Etapa 2. Cada uma possui KM planejado, odômetros de saída e retorno à base, datas e veículo. A Etapa 8 consolida os quilômetros das saídas de cada ciclo e sinaliza leituras incompletas ou inconsistentes. Os campos históricos de quilômetros dos fretes permanecem disponíveis para compatibilidade quando uma operação ainda não contém saídas.

A receita do ciclo é a soma das negociações individuais dos fretes vinculados. O custo consolidado reúne despesas de frete e despesas compartilhadas do ciclo sem dupla contagem. Compras de combustível e consumo estimado por KM são indicadores distintos.

## Criação e evolução do esquema

Na inicialização, `sincronizar_colunas_banco()` cria estruturas ausentes e realiza ajustes de colunas e índices. A evolução do esquema utiliza atualmente essa sincronização; migrações versionadas integram o planejamento técnico. Alterações estruturais seguem o procedimento de backup e execução em PostgreSQL isolado.

O comando `python -m database.diagnostico_ciclos` executa o diagnóstico de ciclos com a conexão definida em `DATABASE_URL`. A importação de planilha disponibiliza prévia e conferência; a gravação automática não integra o fluxo regular do MVP.

Os cenários de integridade, conciliação financeira e regressão estão organizados no [plano de testes](plano_testes.md). As regras detalhadas estão em [regras de negócio](regras_negocio.md), e o procedimento de publicação em [guia de execução](guia_execucao.md).
