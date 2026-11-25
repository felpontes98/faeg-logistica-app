# Diagramas de modelagem

Os diagramas representam a arquitetura e os fluxos do Sistema Web FAEG. Foram criados em [Mermaid](https://mermaid.js.org/), formato compatível com a visualização de arquivos Markdown no GitHub.

| Diagrama | Finalidade | Notação |
| --- | --- | --- |
| [Casos de uso](casos_uso.md) | Funcionalidades e atores | Fluxograma funcional |
| [Componentes](componentes.md) | Dependências entre os módulos | Fluxograma de componentes |
| [Classes](classes.md) | Estruturas de domínio e associações | `classDiagram` |
| [Entidade-relacionamento](entidade_relacionamento.md) | Tabelas, chaves e cardinalidades | `erDiagram` |
| [Sequências](sequencias.md) | Cadastro, abastecimento e saídas | `sequenceDiagram` |
| [Atividades](atividades.md) | Preenchimento e fechamento | Fluxograma de atividades |
| [Estados](estados.md) | Situações operacionais e financeiras | `stateDiagram-v2` |
| [Implantação](implantacao.md) | Aplicação, navegador e banco | Fluxograma de implantação |

**Escopo da modelagem:** a aplicação utiliza Streamlit e SQLAlchemy, sem API REST intermediária. Os diagramas de estados e casos de uso são representações conceituais; o DER acompanha as 19 tabelas ORM definidas no código.
