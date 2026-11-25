# Documentação — Sistema Web FAEG

A documentação apresenta os requisitos, as regras operacionais, a arquitetura de **19 tabelas ORM** e os registros de desenvolvimento do sistema. O projeto foi desenvolvido como MVP no contexto do Startup Challenge UMC 2026 e utiliza uma estrutura modular de 11 etapas.

## Produto e operação

| Documento | Conteúdo |
| --- | --- |
| [Visão do produto](resumo_faeg.md) | Problema, objetivos, solução e equipe |
| [Guia operacional](guia_preenchimento_operacional.md) | Sequência de cadastro, saídas, despesas e fechamento |
| [Requisitos](requisitos.md) | Funcionalidades e critérios de aceite |
| [Regras de negócio](regras_negocio.md) | Ciclos, fretes, quilômetros e critérios financeiros |
| [Glossário](glossario.md) | Terminologia utilizada no projeto |

## Arquitetura, manutenção e qualidade

| Documento | Conteúdo |
| --- | --- |
| [Arquitetura da aplicação](arquitetura_aplicacao.md) | Módulos Streamlit e fluxo de execução |
| [Modelo de dados](arquitetura_banco.md) | Tabelas ORM, vínculos e persistência |
| [Diagramas técnicos](diagramas/README.md) | Classes, ER, sequências, atividades, estados, componentes e implantação |
| [Rastreabilidade](rastreabilidade.md) | Relação entre requisitos, código e cenários de teste |
| [Plano de testes](plano_testes.md) | Verificações automatizadas e funcionais |
| [Execução e implantação](guia_execucao.md) | Instalação, ambientes, CI e publicação |
| [Segurança e privacidade](seguranca_privacidade.md) | Credenciais, dados, exportações e ambiente público |
| [Planejamento técnico](planejamento_tecnico.md) | Evoluções de arquitetura e produto |
| [Licenciamento](licenciamento.md) | Direitos autorais e histórico MIT |
| [Decisões de arquitetura](decisoes/README.md) | Registros de decisões técnicas (ADRs) |

## Histórico de desenvolvimento

- [Reunião de início](reunioes/reuniao_01_kickoff.md)
- [Revisão do protótipo](reunioes/reuniao_02_prototipo_visual.md)
- [Demonstração do MVP](reunioes/reuniao_03_demonstracao_mvp.md)
- [Protótipo HTML inicial](prototipo/prototipo_inicial.html)
- [Histórico de alterações](../CHANGELOG.md)

As atas registram decisões de cada fase. Para o comportamento vigente, prevalecem os requisitos, as regras de negócio e o código da aplicação.
