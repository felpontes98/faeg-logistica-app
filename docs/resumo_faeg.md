# Resumo do Projeto — FAEG Logística

## Objetivo

Desenvolver um sistema web para substituir progressivamente o preenchimento operacional em Excel, mantendo a rastreabilidade de fretes individuais e ciclos, facilitando os cadastros, as consultas, os controles de gastos e os relatórios.

O projeto nasceu da operação real da **FAEG — Soluções Empresariais e Logísticas**, com processos e planilha-base apresentados por Eduardo Pontes. O desenvolvimento é conduzido por Felipe Pontes e Larissa do Espírito Santo no contexto do Startup Challenge UMC 2026.

## Estado da versão preparada (pendente de homologação no banco)

Foi realizada uma leitura estática do código e da planilha de referência. O aplicativo possui onze etapas na navegação:

| Etapa | Função presente na interface |
| --- | --- |
| 1 | Frota FAEG e área de importação Excel |
| 2 | Frete, rota, carga e documentos |
| 3 | Cliente contratante |
| 4 | Negociação e pagamento |
| 5 | Coleta |
| 6 | Entrega |
| 7 | Despesas de viagem |
| 8 | Fechamento final |
| 9 | Relatórios, indicadores e exportação |
| 10 | Consultas gerais |
| 11 | Cadastros gerais |

Os formulários, cadastros, consultas e relatórios estão presentes no código. A proposta inclui `fretes_financeiro`, o histórico por veículo `abastecimentos`, `recebimentos_frete`, `ciclos_despesas` e `veiculos_despesas`, totalizando **quatorze tabelas no ORM**. **A presença de uma tela ou de um modelo não equivale a homologação:** este código ainda precisa ser testado com uma cópia do PostgreSQL.

## Decisões operacionais da FAEG

1. **Frete e ciclo possuem identificadores diferentes.** O código do frete identifica cada serviço; o código do ciclo agrupa vários serviços.
2. **O ciclo tem um único fechamento operacional.** Receitas dos fretes são somadas; despesas comuns e quilometragem são registradas sem duplicação.
3. **A quilometragem do Maps é estimada.** A leitura de odômetro da saída/chegada e a do abastecimento são informações reais distintas e podem não estar disponíveis.
4. **Negociação e recebimento não são a mesma coisa.** Percentual e valor das parcelas podem ser calculados automaticamente, mas só valores confirmados representam dinheiro recebido.
5. **Resultado operacional não é automaticamente lucro líquido.** A nomenclatura deve refletir os gastos efetivamente considerados.

Exemplos e critérios de aceite estão documentados em [Regras de negócio](regras_negocio.md) e [Requisitos](requisitos.md).

## Atenções identificadas

| Tema | Situação |
| --- | --- |
| Importação Excel | Prévia sem gravação validada com 34 fretes e 13 ciclos. Das 13 linhas marcadas `FECHAMENTO`, a auditoria encontrou 12 fechamentos de fretes e 1 possível total geral. Gravação continua **bloqueada** |
| Agrupamento | Novo cadastro reutiliza ciclo existente pelo número; mantém negociação e cliente independentes em `fretes_financeiro`. **Ciclos históricos repetidos não foram migrados** |
| Fechamento | A auditoria Excel compara os fechamentos com os fretes e identifica códigos divergentes. A Etapa 8 possui prévia financeira do ciclo; a Etapa 9 e o Excel mostram receita negociada, despesas por frete, despesas compartilhadas e resultado operacional parcial por ID interno do ciclo. Pagamentos efetivos e despesas comuns podem ser lançados manualmente; rateio e fechamento formal ainda não foram implementados |
| Recebimentos | Adiantamento mais saldo são **parcelas previstas**, nunca tratados como pagamentos confirmados ou substitutos do negociado. A Etapa 4 ganhou registro manual de pagamentos efetivos por frete, com data, forma, referência e cancelamento auditável. Etapas 8 e 9, consultas e Excel exibem recebido e saldo a receber; a conciliação bancária ainda não existe |
| KM e abastecimento | Etapa 2 mantém o KM manual do frete; Etapa 8 soma os trechos do ciclo e deslocamentos, compara com odômetros válidos e exibe consumo indicativo do veículo. Na Etapa 7, **não há duas áreas para registrar Diesel/ARLA**: litros, preço e odômetro numérico estão no lançamento único de despesa, que gera histórico por veículo automaticamente. O Excel exporta `Abastecimentos_Veiculos` com a origem do custo |
| Despesas comuns | A Etapa 7 permite lançar e cancelar despesas por ID do ciclo, separadas de `viagens_despesas`. O fechamento do ciclo soma os dois componentes uma vez; o BI filtrável por cliente/frete não rateia custos comuns. O Excel exporta `Despesas_Ciclo` e detalha os componentes em `Fechamento_Ciclos` |
| Gastos sem operação definida | O mesmo lançamento permite vincular provisoriamente o custo a um veículo (`veiculos_despesas`), mesmo com zero fretes. O valor fica fora de DRE/BI e aparece em `Despesas_Veiculo_Pendentes`; transferência posterior para frete/ciclo não foi implementada |
| Segurança | Não foi identificada autenticação ou autorização de usuários no código revisado |
| Testes | Não havia suíte automatizada de testes no pacote recebido |

**Atenção antes do deploy:** o app cria tabelas ausentes na inicialização. Portanto, a nova tabela será criada assim que o app modificado abrir uma conexão com o banco configurado. É obrigatório validar a versão em um banco de testes e ter backup antes de conectar ao banco oficial. Para as próximas tarefas, a equipe pode usar as Issues do GitHub, com base nos [Requisitos](requisitos.md) e na [Arquitetura do banco](arquitetura_banco.md).

Na planilha de referência de setembro/2026, a auditoria apontou: linha 10 sem ID do ciclo no fechamento, linha 43 com ciclo declarado `V26-000008` embora os quatro fretes imediatamente anteriores indiquem `V26-000009`, linha 44 como possível total geral e frete `F26-000034` sem linha posterior de fechamento. **São avisos para conferência humana; nenhum código foi corrigido automaticamente.**

## Tecnologia e identidade visual

- Python, Streamlit, Pandas, SQLAlchemy, `psycopg` e PostgreSQL.
- Código atual concentrado em `app.py`, com persistência em `database/`.
- Tema com azul estrutural `#0D263C`, laranja `#F34D25`, branco e cinza, além do logotipo em `assets/logo_faeg.png`.
- Marca institucional: **FAEG — Soluções Empresariais e Logísticas**.

## Próxima verificação após concluir os ajustes

Eduardo decidiu reunir primeiro os ajustes e deixar os testes integrados para o final. Nessa fase deverão ser avaliados, em PostgreSQL de testes: vínculo frete/ciclo, soma de KM, odômetros opcionais, **lançamento único de combustível e despesa** sem formulário duplicado, cadastro provisório por veículo sem frete, indicadores consecutivos de Diesel/ARLA, fechamento parcial de ciclos, despesas compartilhadas/provisórias ativas/canceladas, recebimentos confirmados/cancelados e DRE sem duplicação. A gravação Excel, a conciliação bancária, a **atribuição posterior** de gastos provisórios e o rateio de custos compartilhados continuam pendentes. **As novas rotinas de abastecimentos, ciclos, despesas e recebimentos estão no código, mas não foram homologadas.**

Para apresentação geral e instalação, consulte o [README](../README.md). Para a arquitetura técnica, consulte [Arquitetura do banco](arquitetura_banco.md).
