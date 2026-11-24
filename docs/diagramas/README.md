# Diagramas de modelagem — FAEG

Os diagramas representam os componentes, as entidades e os fluxos do Sistema Web FAEG, incluindo o Ajuste 27 e a organização modular de 24/11/2026. Foram elaborados em [Mermaid](https://mermaid.js.org/) para visualização diretamente no GitHub.

| Diagrama | Finalidade | Notação |
| --- | --- | --- |
| [Casos de uso](casos_uso.md) | Atores, funcionalidades e limites do escopo | Representação funcional em fluxograma Mermaid |
| [Componentes](componentes.md) | Camadas, módulos e dependências | Diagrama de componentes conceitual |
| [Classes](classes.md) | Entidades ORM e relações de domínio | UML — `classDiagram` |
| [Entidade-relacionamento](entidade_relacionamento.md) | Chaves e cardinalidades do banco | `erDiagram` |
| [Sequência](sequencias.md) | Salvar frete, lançar combustível, registrar saída | UML — `sequenceDiagram` |
| [Atividades](atividades.md) | Registro de ciclo e fechamento gerencial | Fluxograma de atividades |
| [Estados](estados.md) | Situação operacional e financeira | UML — `stateDiagram-v2`, modelo conceitual |
| [Implantação](implantacao.md) | Navegador, Streamlit e PostgreSQL/Neon | Visão conceitual de implantação |

**Convenções:** os estados propostos representam possibilidades de evolução, enquanto os relacionamentos de banco refletem os modelos ORM. A aplicação utiliza Streamlit conectado a serviços Python, sem API REST independente. O teste `tests/test_documentacao.py` verifica a estrutura dos diagramas e os links internos.
