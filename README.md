# FAEG — Sistema de Gestão Logística

Sistema web de apoio ao controle operacional e financeiro da FAEG — Soluções Empresariais e Logísticas, desenvolvido a partir de planilha de viagens no contexto do Startup Challenge UMC 2026.

**Status:** ajustes de código em preparação; **testes integrados e homologação do banco ainda não realizados**. Não considerar este repositório homologado para dados de produção.

## O que o sistema contempla

- Cadastros de veículos, motoristas, clientes, locais e fornecedores.
- Fretes com rota, documentos e negociação individual; agrupamento por ciclo operacional.
- KM Individual/Ciclo preenchido manualmente na Etapa 2 e soma dos KM do ciclo na Etapa 8, acrescida de deslocamentos operacionais informados uma vez.
- Odômetros de saída/chegada da operação, distintos das leituras de abastecimento.
- Histórico de Diesel e ARLA por **veículo**, inclusive sem frete selecionado, com métricas indicativas de distância, km/L e R$/km entre registros consecutivos de Diesel.
- Despesas financeiras por viagem e demonstrativo de resultado operacional parcial, sem lançamento automático de combustível a partir do histórico do veículo.
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
| [`database/importador_planilha.py`](database/importador_planilha.py) | Prévia controlada da importação Excel |
| [`database/conciliacao_planilha.py`](database/conciliacao_planilha.py) | Auditoria de fretes e fechamentos na planilha |
| [`database/diagnostico_ciclos.py`](database/diagnostico_ciclos.py) | Diagnóstico somente leitura dos ciclos no PostgreSQL |
| [`assets/`](assets/) | Identidade visual |
| [`docs/`](docs/) | Documentação do produto e do banco |

Não existe pasta `views/` neste pacote. Guias locais de VSCode ou planos pessoais de melhoria não integram o repositório.

## Preparação local — quando iniciar a rodada de testes

1. Abra a pasta oficial do repositório no VSCode.
2. Crie um ambiente Python virtual, ative-o e instale `pip install -r requirements.txt`.
3. Configure `DATABASE_URL` para um **banco PostgreSQL de testes**, usando variável de ambiente ou arquivo `.env` local, nunca versionado.
4. Inicie com `python -m streamlit run app.py`.
5. Execute os critérios documentados em [Requisitos](docs/requisitos.md) após concluir os ajustes.

**Atenção:** a inicialização de `app.py` chama `sincronizar_colunas_banco()` e pode **criar tabelas/alterar colunas** no banco indicado por `DATABASE_URL`. Faça backup e ensaio em banco de testes antes de apontar o app para o banco oficial. O diagnóstico de ciclos, por sua vez, é somente leitura.

## Documentação

- [Resumo do projeto](docs/resumo_faeg.md)
- [Requisitos e checklist de homologação](docs/requisitos.md)
- [Regras de negócio e fórmulas de KM](docs/regras_negocio.md)
- [Arquitetura e integridade do banco](docs/arquitetura_banco.md)
- [Kickoff do projeto](docs/kickoff.md)

## Equipe

- Felipe Pontes — desenvolvimento
- Larissa do Espírito Santo — desenvolvimento
- Eduardo Pontes — referência operacional e validação de regras de negócio
