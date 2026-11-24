# Documentação — Sistema Web FAEG

**Referência técnica e acadêmica** do MVP, baseada no código da versão de 24/11/2026 (Ajuste 27). A distinção entre funcionalidades implementadas e itens pendentes é intencional: a existência de código não constitui prova de homologação.

## 1. Produto e requisitos

| Documento | Conteúdo |
| --- | --- |
| [Resumo do projeto](resumo_faeg.md) | Problema, objetivo, escopo e evolução |
| [Requisitos](requisitos.md) | Requisitos funcionais e critérios de aceite |
| [Regras de negócio](regras_negocio.md) | IDs, negociações, ciclos, despesas, KM e abastecimento |
| [Glossário](glossario.md) | Linguagem padronizada para operação, TI e banca |

## 2. Projeto técnico

| Documento | Conteúdo |
| --- | --- |
| [Arquitetura do banco](arquitetura_banco.md) | 18 entidades, relacionamentos, integridade e transição de esquema |
| [Avaliação do repositório](avaliacao_repositorio.md) | Inventário, lacunas e prioridades de engenharia |
| [Matriz de rastreabilidade](rastreabilidade.md) | Relação entre RFs, módulos e testes |
| [Diagramas de modelagem](diagramas/README.md) | Classes, sequência, DER, componentes, atividades, estados, casos de uso e implantação |
| [Guia de execução](guia_execucao.md) | Instalação local, banco isolado, testes e implantação |
| [Plano de testes](plano_testes.md) | Matriz de testes e homologação |
| [Segurança e privacidade](seguranca_privacidade.md) | Controles identificados, limitações e recomendações |
| [Licenciamento e histórico](licenciamento.md) | Regra atual, preservação da MIT e direitos das versões anteriores |
| [Decisões de arquitetura](decisoes/README.md) | Histórico de justificativas técnicas (ADRs) |

## 3. Histórico acadêmico do desenvolvimento

- [Reunião 01 — Kickoff](reunioes/reuniao_01_kickoff.md)
- [Reunião 02 — Protótipo visual](reunioes/reuniao_02_prototipo_visual.md)
- [Reunião 03 — Demonstração do MVP](reunioes/reuniao_03_demonstracao_mvp.md)
- [Protótipo HTML original](prototipo/prototipo_inicial.html)
- [Histórico das alterações](../CHANGELOG.md)

**Nota:** documentos históricos de reuniões registram o conhecimento existente na respectiva data. Não foram reescritos para simular funcionalidades posteriores.

## Organização da aplicação após modularização

- [Arquitetura dos módulos Python e sequência de execução](arquitetura_aplicacao.md)
- [ADR-004 — Refatoração incremental do Streamlit](decisoes/ADR-004-refatoracao-streamlit.md)
