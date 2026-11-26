# Histórico de alterações

Este arquivo registra as principais entregas funcionais e técnicas do Sistema Web FAEG. Alterações pontuais e seus responsáveis permanecem disponíveis no histórico de commits do Git.

## 2026-11-26 — Edição de despesas

- Incluímos a edição de despesas no rascunho, no frete, no ciclo e no veículo. Cada correção de uma despesa salva fica disponível na Etapa 7 e na exportação Excel.
- A correção de combustível atualiza o abastecimento vinculado. Quando o veículo já tem uma atribuição, atualizamos também o custo no destino.
- Alinhamos os finais de linha do Git ao padrão LF do projeto, inclusive no Windows.
- Atualizamos a geração das datas de criação e alteração em UTC, mantendo o formato das colunas existentes.
- Concentramos as regras vigentes nos documentos de arquitetura e de negócio.

## 2026-11-26 — Fechamento e rastreabilidade

- Unificamos a leitura de KM nas consultas e nos relatórios e incluímos a estimativa de Diesel no fechamento.
- Separamos os filtros operacionais e financeiros, preservamos despesas canceladas e passamos a exigir confirmação para individualizar negociações históricas compartilhadas.
- Ajustamos a prévia do ciclo e a publicação das saídas provisórias. Incluímos Van e HR no cadastro da frota.

## 2026-11-26 — Identificação automática e vínculos de coleta

- Numeração automática global dos fretes, com código interno `V` e ID comercial `FV` sem referência ao ano.
- Seleção da saída de coleta no cadastro de cada frete, permitindo vários fretes na mesma saída do ciclo.
- Verificação de compatibilidade do ciclo e do veículo no vínculo, com preservação dos códigos históricos.
- Inclusão do vínculo nas consultas e exportações, sem repetir quilômetros nem despesas.
- Atualização dos diagramas, requisitos e testes de identificação e vínculo.

## 2026-11-25 — Fluxo operacional e persistência parcial

- Saídas, quilômetros planejados e odômetros da operação concentrados na Etapa 2; fechamento consolidado na Etapa 8.
- Componentes de KM por saída: deslocamento entre coletas, rota principal e retorno à base.
- Salvamento e retomada de rascunhos sem incorporar registros incompletos ao resultado financeiro.
- Parâmetros referenciais de consumo vinculados aos cadastros dos veículos.
- Atualização da documentação, dos diagramas e dos cenários automatizados.

## 2026-11-24 — Arquitetura modular e controle de saídas

- Modularização das 11 etapas, com `app.py` como ponto de entrada e serviços compartilhados em `faeg_app/` e `database/`.
- Registro de saídas e trechos físicos associados às operações, com consolidação de quilômetros e controle de leituras.
- Estimativa de consumo apresentada separadamente dos lançamentos financeiros de combustível.
- Organização de documentação, modelagem de dados, decisões de arquitetura e execução de testes em CI.
- Atualização da política de licenciamento para novas contribuições, preservando as versões anteriormente disponibilizadas sob MIT.

## 2026 — Construção do MVP

- Evolução da planilha operacional para uma aplicação Streamlit com persistência PostgreSQL.
- Cadastros de frota, motoristas, clientes, locais e fornecedores.
- Gestão de fretes individuais e ciclos, negociações, pagamentos, despesas e abastecimentos.
- Consultas, relatórios, exportações e mecanismos de prevenção de lançamentos duplicados.

O detalhamento histórico está disponível nas [reuniões](docs/reunioes/) e no histórico do repositório.
