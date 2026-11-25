# Histórico de alterações

Este arquivo registra as principais entregas funcionais e técnicas do Sistema Web FAEG. Alterações pontuais e seus responsáveis permanecem disponíveis no histórico de commits do Git.

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

O detalhamento histórico está disponível nas [reuniões](docs/reunioes/), nas [decisões de arquitetura](docs/decisoes/README.md) e no histórico do repositório.
