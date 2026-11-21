# FAEG — Sistema de Gestão Logística

Sistema web de apoio ao controle operacional e financeiro da FAEG — Soluções Empresariais e Logísticas, desenvolvido a partir de planilha de viagens no contexto do Startup Challenge UMC 2026.

**Status:** ajustes de código em preparação; **verificações iniciais de segurança e estrutura do banco realizadas, com testes funcionais integrados e homologação ainda pendentes**. Não considerar este repositório homologado para dados de produção.

## O que o sistema contempla

- Cadastros de veículos, motoristas, clientes, locais e fornecedores.
- Fretes com rota, documentos e negociação individual; agrupamento por ciclo operacional.
- **Tela 2:** “KM X ROTA PLANEJADO” é somente um título; os campos de **KM saída/entre coletas**, **KM individual/ciclo**, **KM retorno operacional** e **odômetros inicial/final da operação** são manuais. **Tela 8:** “KM PLANEJADO” soma os fretes do mesmo **ID interno do ciclo**, “KM DESLOCAMENTOS OPERACIONAIS” soma saída/entre coletas + retorno apenas uma vez por ciclo, e “KM TOTAL PLANEJADO” soma planejado + deslocamentos. O **KM REAL RODADO** do topo é final − inicial do frete atual; **KM TOTAL REAL** consolida os intervalos válidos dos fretes do ciclo sem sobreposição no mesmo veículo. A diferença é total real − planejado. Registros históricos com deslocamento apenas total são mantidos até discriminação explícita.
- **Organização visual da Tela 8:** painel responsivo com dois grupos de indicadores (**Planejado** e **Realizado e comparação**), memória resumida da fórmula, DRE financeiro mantido em destaque e explicações detalhadas em seções expansíveis. A consulta de consumo por abastecimentos e o detalhamento das parcelas do ciclo continuam disponíveis, mas não disputam espaço com o fechamento principal. As demais telas não receberam alterações estéticas sem necessidade comprovada.
- Ao editar fretes, há proteções contra reutilização de ID Frete, associação automática a nomes de ciclo históricos repetidos, troca da placa com abastecimento ativo e saída do último frete de ciclo com despesas compartilhadas ativas. Essas situações são apresentadas para correção humana, sem migrar dados silenciosamente.
- Odômetros de saída/chegada da operação podem ser digitados na Tela 2 ou na Tela 8, **usando os mesmos dois campos persistidos**, distintos das leituras de abastecimento. Na Etapa 7, ao selecionar Diesel ou ARLA, **ODÔMETRO NO ABASTECIMENTO (KM)** aparece como campo numérico direto, sem checkbox; `0` significa leitura não informada (`NULL`). Abastecimentos não substituem automaticamente a leitura de início/fim da operação.
- **Um único formulário para despesas e abastecimentos** na Etapa 7: informar litros, preço e odômetro no mesmo lançamento. O custo é atribuído a **um frete, a um ciclo ou provisoriamente a um veículo**, sem duas áreas para cadastrar combustível.
- Histórico de Diesel e ARLA por **veículo**, inclusive sem frete selecionado, preenchido pelo próprio lançamento de despesa. A área de histórico é **somente consulta**, com estimativas de distância, km/L e R$/km entre registros consecutivos de Diesel.
- Despesas financeiras por frete, **despesas compartilhadas por ciclo** e **despesas provisórias por veículo**. É possível atribuir explicitamente um gasto pendente a um frete/ciclo do mesmo veículo e estornar a atribuição com justificativa, preservando o registro original e uma trilha de eventos. Só o destino ativo entra no DRE.
- Prévia financeira do ciclo na Etapa 8 e relatório de fechamento gerencial por ciclo na Etapa 9: soma receitas negociadas, despesas dos fretes e **uma única vez** os gastos compartilhados do ID Ciclo. O BI filtrável por frete/cliente exclui gastos compartilhados enquanto não existir critério de rateio aprovado.
- A Etapa 9 também possui **Conferência Financeira Geral**, independente dos filtros do BI: reconcilia receita negociada considerada, despesas por frete, compartilhadas e resultado gerencial. Separa gastos provisórios do veículo que ainda estão fora do resultado e identifica os já atribuídos, sem contá-los uma segunda vez.
- **Conferência cruzada de possíveis despesas duplicadas** entre frete e ciclo do mesmo ID: o lançamento avisa sobre coincidências relevantes e solicita confirmação de que são custos distintos; a atribuição de gasto provisório também exige confirmação se encontrar semelhanças. Os indícios históricos aparecem na Etapa 9 para conferência de comprovantes; nenhum custo antigo é alterado automaticamente.
- Registro de recebimentos efetivamente confirmados por frete na Etapa 4, com histórico de cancelamentos, total recebido e saldo em aberto por frete e por ciclo. O Excel inclui `Recebimentos_Fretes`.
- Exportação Excel com `Fechamento_Ciclos` (despesas dos fretes e compartilhadas em colunas distintas, KM de saída/entre coletas e retorno), `Viagens_e_Ciclos` (KM individuais e odômetros), `Conferencia_Financeira`, `Possiveis_Duplicidades`, `Despesas_Ciclo`, `Despesas_Veiculo`, `Atribuicoes_Despesas` e `Abastecimentos_Veiculos` com origem e situação. Na Etapa 10, o botão **Exportar Base Completa** reúne um conjunto coerente de toda a base, independentemente dos filtros visuais da consulta.
- Prévia e auditoria da planilha Excel. **A importação com gravação no banco permanece bloqueada.**

## Tecnologia

Python, Streamlit, Pandas, SQLAlchemy, PostgreSQL (`psycopg`) e OpenPyXL. O app pode ser executado localmente e foi preparado para uso com PostgreSQL/Neon, desde que o ambiente seja configurado corretamente.

## Estrutura real do repositório

| Caminho | Finalidade |
| --- | --- |
| [`app.py`](app.py) | Interface Streamlit com as onze etapas |
| [`database/connection.py`](database/connection.py) | Configuração da conexão SQLAlchemy |
| [`database/models.py`](database/models.py) | Modelos, criação de tabelas e atualização de colunas |
| [`database/controle_abastecimentos.py`](database/controle_abastecimentos.py) | Indicadores de consumo a partir do histórico por veículo |
| [`database/fechamento_ciclos.py`](database/fechamento_ciclos.py) | Consolidação gerencial por ID de ciclo e conferência financeira da base inteira, sem duplicação de despesas |
| [`database/atribuicao_despesas.py`](database/atribuicao_despesas.py) | Atribuição e estorno auditáveis de despesas provisórias do veículo para frete/ciclo |
| [`database/conferencia_duplicidades.py`](database/conferencia_duplicidades.py) | Sinalização conservadora de gastos semelhantes entre frete e ciclo do mesmo ID, sem alterar histórico |
| [`database/importador_planilha.py`](database/importador_planilha.py) | Prévia controlada da importação Excel |
| [`database/conciliacao_planilha.py`](database/conciliacao_planilha.py) | Auditoria de fretes e fechamentos na planilha |
| [`database/diagnostico_ciclos.py`](database/diagnostico_ciclos.py) | Diagnóstico somente leitura dos ciclos no PostgreSQL |
| [`assets/`](assets/) | Identidade visual |
| [`docs/`](docs/) | Documentação do produto e do banco |

## Preparação local — quando iniciar a rodada de testes

1. Abra a pasta oficial do repositório no VSCode.
2. Crie um ambiente Python virtual, ative-o e instale `pip install -r requirements.txt`.
3. Configure `DATABASE_URL` para um **banco PostgreSQL de testes**, usando variável de ambiente ou arquivo `.env` local, nunca versionado.
4. Inicie com `python -m streamlit run app.py`.
5. Execute os critérios documentados em [Requisitos](docs/requisitos.md) após concluir os ajustes.

**Atenção:** a inicialização de `app.py` chama `sincronizar_colunas_banco()` e pode **criar tabelas/alterar colunas** no banco indicado por `DATABASE_URL`. Faça backup e ensaio em banco de testes antes de apontar o app para o banco oficial. O diagnóstico de ciclos, por sua vez, é somente leitura.

## Documentação

### Documentação técnica

- [Resumo do projeto](docs/resumo_faeg.md)
- [Requisitos e checklist de homologação](docs/requisitos.md)
- [Regras de negócio e fórmulas de KM](docs/regras_negocio.md)
- [Arquitetura e integridade do banco](docs/arquitetura_banco.md)

### Histórico de reuniões

- [Reunião 01 — Kickoff do projeto](docs/reunioes/reuniao_01_kickoff.md)
- [Reunião 02 — Apresentação do protótipo visual](docs/reunioes/reuniao_02_prototipo_visual.md)
- [Reunião 03 — Acompanhamento das funcionalidades do MVP](docs/reunioes/reuniao_03_demonstracao_mvp.md)

### Protótipo inicial

- [Protótipo visual em HTML](docs/prototipo/prototipo_inicial.html)

## Equipe

- Felipe Pontes — desenvolvimento
- Larissa do Espírito Santo — desenvolvimento
- Eduardo Pontes — cliente, referência operacional e validação de regras de negócio