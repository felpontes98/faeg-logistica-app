# Plano de testes e critérios de homologação

**Objetivo:** definir cenários automatizados e funcionais para assegurar consistência dos dados, cálculos e fluxos operacionais durante a evolução do MVP.

## Testes automatizados disponíveis

Arquivo: [`tests/test_saidas_operacionais.py`](../tests/test_saidas_operacionais.py). Os cenários de persistência utilizam SQLite em memória.

| Código | Cenário | Evidência no código |
| --- | --- | --- |
| TU-01 | Várias saídas no ciclo somadas uma única vez | `test_varias_saidas_na_mesma_operacao_sem_somar_duas_vezes` |
| TU-02 | Trechos prevalecem sobre KM manual da saída | `test_trechos_substituem_plano_manual_sem_dupla_soma` |
| TU-03 | Odômetros ausentes ou sobrepostos não geram KM real falso | `test_odometros_ausentes_ou_sobrepostos_nao_viram_zero` |
| TU-04 | Estimativa de Diesel não cria despesa | `test_estimar_diesel_nao_e_lancamento_financeiro` |
| TU-05 | Datas, odômetros e ciclo inexistente são rejeitados | `test_validacao_datas_odometros_e_estrangeiros` |
| TU-06 | Cadastro de saída não reescreve KM legado | `test_legacy_cycle_fields_remain_unchanged` |

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q tests/test_saidas_operacionais.py
```

## Testes de estrutura, rascunhos e fluxo unificado

A suíte `tests/` também inclui verificações da modularização, importação das 11 etapas, geração de relatórios, links e diagramas, salvamento e retomada de rascunhos e persistência de saídas e despesa única por ciclo.

```powershell
python -m pytest -q tests
```

## Matriz de integração e critérios de aceite

| Código | Requisitos | Cenário / resultado esperado | Evidência a registrar |
| --- | --- | --- | --- |
| TI-01 | RF-01–04 | Criar frete individual e reabrir sem perder cliente, veículo, documentos e negociação | Capturas e identificadores de teste |
| TI-02 | RF-03, RF-13–19 | Criar ciclo com 3 fretes e clientes distintos; receitas e recebimentos individuais corretamente somados | Extrato financeiro do ciclo |
| TI-03 | RF-14, RF-22–28 | Lançar despesa compartilhada e despesa exclusiva; não duplicar custo | Demonstrativo e consulta SQL |
| TI-04 | RF-08–10 | Abastecer Diesel/ARLA uma vez; visualizar histórico sem novo custo na DRE | Histórico e resultado |
| TI-05 | RF-25–26 | Atribuir e estornar despesa provisória com trilha; custo ativo em um único destino | Eventos de auditoria |
| TI-06 | RF-42–45 | Cadastrar saídas preparatórias, entregas e retorno no mesmo ciclo | Etapa 2 e tabelas de saídas |
| TI-07 | RF-43–44 | Somar trechos uma vez; manter o KM real indisponível com intervalos sobrepostos ou incompletos | Comparação com odômetros |
| TI-08 | RF-46 | Estimar consumo sem alterar custo contabilizado | Painel de consumo e DRE |
| TI-09 | RF-11, RF-29, RF-47 | Exportar relatórios do ciclo, saídas e trechos; conferir totais com banco | Arquivos de teste |
| TI-10 | RF-12 | Prévia de Excel funciona; gravação no banco permanece bloqueada | Captura/relatório de prévia |
| TI-11 | RF-35–36 | Tentar IDs repetidos, ciclo ambíguo e troca de veículo com abastecimento | Mensagens e registros preservados |
| TI-12 | RI-01–06 | Revisar permissões, restauração do backup e dados pessoais | Plano de segurança e ata de aceite |
| TI-13 | RF-52–53 | Registrar dois fretes na mesma saída e outros em uma segunda saída do mesmo ciclo; verificar IDs automáticos e KM físico não duplicado | Teste de vínculos e conferência de KM |
| TI-14 | RF-52–53 | Impedir vínculo de frete a saída de outro ciclo ou veículo; preservar identificadores anteriores | Testes de integridade e histórico |
| TI-15 | RF-54 | Editar um custo, conferir total e histórico, corrigir Diesel e testar estorno após edição de uma despesa atribuída | Etapas 7 a 9 e aba Edicoes_Despesas |

### Processo de execução

1. Criar dados **fictícios** em PostgreSQL isolado. Se for utilizada uma branch clonada de produção, remover ou anonimizar os registros antes de liberar acesso; não usar dados pessoais reais em issues ou relatórios públicos.
2. Registrar ambiente, versão/commit, data, responsável, entrada, resultado esperado, resultado observado e evidências sanitizadas.
3. Distinguir falha do código, regra em validação e divergência de dados legados; não corrigir histórico automaticamente.
4. Executar restauração de backup de ensaio antes de aceitar uma migração de produção.
5. Formalizar aprovação operacional pela FAEG e revisão técnica pelos desenvolvedores.

**Critério de aceite:** registrar resultado, responsável e eventuais ajustes para os cenários críticos, garantindo rastreabilidade das alterações.


### Conferências de regressão

1. Salvar dois fretes com negociação histórica compartilhada e conferir que a receita só entra após individualização expressa.
2. Comparar uma saída individual de 120 km no fechamento, relatório, BI e Excel.
3. Conferir uma despesa de ciclo no rascunho e após o salvamento.
4. Registrar o pagamento integral e verificar os filtros financeiro e operacional.
5. Cancelar Diesel do frete e conferir motivo, resultado ativo e medição no histórico.
