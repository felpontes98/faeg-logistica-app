# Projeto: FAEG - Sistema de Gestão Logística
**Documento:** Acompanhamento das Funcionalidades do MVP
**Data / Versão:** 13/11/2026 - v1.1
**Participantes:** Felipe Pontes e Eduardo Pontes

---

## 1. Contexto e Objetivo da Reunião

Esta reunião dá continuidade à apresentação do protótipo visual, documentando a evolução para uma versão mais completa do sistema web FAEG.

O fluxo foi ampliado para reunir registro de viagens, controle de fretes, acompanhamento financeiro, consultas históricas e manutenção de cadastros.

O objetivo é revisar o funcionamento previsto para as onze etapas, a integração entre elas e os requisitos a conferir antes de iniciar os testes de utilização e persistência de dados.

## 2. Funcionalidades e Fluxo Operacional do Sistema

### Evolução da Estrutura do Sistema

* **Identidade visual FAEG:** Interface institucional com menu lateral, identificação da viagem ativa e navegação sequencial.

* **Ampliação do fluxo:** Além das nove áreas do protótipo inicial, a versão evoluída incorpora consultas históricas e cadastros gerais como etapas próprias.

* **Integração operacional e financeira:** As informações de motorista, veículo, cliente, frete, rota, negociação e despesas são relacionadas ao registro da viagem e, quando aplicável, ao ciclo operacional.

### Descrição das Onze Etapas

* **Etapa 1 — Frota FAEG:** Identificação única da viagem, data operacional, definição entre viagem individual e ciclo, seleção do motorista e do veículo, com apresentação automática de informações dos cadastros de apoio.

* **Etapa 2 — Frete, Carga e Documentos:** ID do frete, tipo, origem e destino, quilômetros de saída e deslocamento entre coletas, quilômetros individuais do frete, retorno operacional, odômetros inicial e final, quantidade de volumes, peso, volume em m³ e documentos fiscais (NF-e, CT-e, MDF-e e CIOT).

* **Etapa 3 — Cliente Contratante:** Seleção da empresa contratante, com razão social, nome fantasia, endereço, responsável e contato vinculados ao cadastro do cliente.

* **Etapa 4 — Negociação e Recebimentos:** Registro manual dos valores divulgado e negociado, cálculo correlacionado entre percentuais e valores previstos de adiantamento e saldo, datas previstas e controle separado dos recebimentos efetivamente confirmados.

* **Etapa 5 — Coleta (Origem):** Seleção da base ou local de coleta, apresentação de CEP, endereço, cidade e UF, informações de contato, restrições de horário e dados de programação e realização da coleta.

* **Etapa 6 — Entrega (Destino):** Seleção da base ou local de entrega, apresentação do endereço e dos contatos, restrições operacionais e registro das informações de programação e realização da entrega.

* **Etapa 7 — Despesas de Viagem:** Lançamento de combustível, pedágios e demais despesas com tipo, descrição, fornecedor, quantidade, valor unitário e total. O abastecimento inclui informações de consumo e odômetro; a classificação identifica despesas de frete, ciclo ou veículo para evitar duplicidade nos resultados.

* **Etapa 8 — Fechamento Final e DRE:** Consolidação da quilometragem planejada e real, comparação entre trajetos e odômetros, situação da operação e demonstrativo de receitas, despesas e resultado líquido. Nos ciclos, o cálculo considera os componentes compartilhados de deslocamento e retorno.

* **Etapa 9 — Relatórios e Exportação:** Relatório da viagem ativa, painéis gerenciais consolidados, análise de indicadores de receita, custos, margem e custo por quilômetro, visão por ciclo e opções de exportação em Excel e PDF.

* **Etapa 10 — Consultas Gerais:** Pesquisa no histórico por código da viagem, frete, cliente, motorista, rota ou ciclo, com filtros operacionais, visualização de indicadores e recuperação de registros salvos para consulta ou edição controlada.

* **Etapa 11 — Cadastros Gerais:** Gestão dos dados de referência em cinco áreas: motoristas, veículos, clientes, locais/bases e fornecedores/postos, com recursos de inclusão, consulta e atualização cadastral.

O sistema diferencia **frete individual** e **ciclo operacional**, permitindo organizar mais de um frete dentro de uma operação, sem repetir automaticamente despesas compartilhadas.

As previsões de pagamento permanecem separadas dos valores efetivamente recebidos, preservando a análise financeira.

## 3. Análise e Pontos para Validação

* **Fluxo completo da viagem:** Confirmar que os dados inseridos permanecem consistentes ao avançar, retornar, salvar e reabrir um registro.

* **Identificação de fretes e ciclos:** Conferir os vínculos entre código da viagem, ID do frete e número do ciclo, evitando agrupamentos e duplicações incorretos.

* **Cálculos de quilometragem:** Comparar a soma dos trechos planejados com a diferença entre odômetros e verificar eventuais inconsistências de leitura.

* **Negociação e recebimentos:** Conferir a conversão entre percentual e valor em reais, o total previsto, os pagamentos confirmados e o saldo efetivamente em aberto.

* **Despesas e DRE:** Verificar se combustível, despesas de viagem, despesas de ciclo e despesas de veículo são classificados corretamente e contabilizados sem duplicidade.

* **Cadastros de apoio:** Testar a seleção e a reutilização de motoristas, veículos, clientes, locais e fornecedores nos formulários da operação.

* **Consultas e relatórios:** Conferir se indicadores, filtros, relatórios e arquivos exportados refletem os dados realmente gravados.

* **Persistência e segurança:** Confirmar integridade de relacionamentos, controle de acesso e estabilidade da conexão com o PostgreSQL.

Esses aspectos formam um roteiro de validação funcional. A existência das funcionalidades na interface não substitui a execução de testes práticos com registros de exemplo.

## 4. Próximos Passos e Alinhamentos Propostos

* **Consolidação das funcionalidades:** Revisar a integração entre as onze etapas, preservando o fluxo de digitação e as regras já definidas.

* **Preparação do banco:** Conferir tabelas, relacionamentos e integridade das informações antes do cadastro definitivo, sem alterar dados durante a verificação inicial.

* **Roteiro de testes:** Executar cenários de viagem individual e ciclo com múltiplos fretes, incluindo negociação, recebimentos, despesas, quilometragem, fechamento e relatórios.

* **Conferência de resultados:** Comparar os indicadores e arquivos exportados com os registros lançados e com as regras financeiras do projeto.

* **Registro de ajustes:** Documentar eventuais falhas e melhorias identificadas durante os testes, preservando a rastreabilidade das alterações.

---