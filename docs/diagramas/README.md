# Diagramas de modelagem — FAEG

Os diagramas abaixo foram revisados com base no **Ajuste 27 e na modularização de 24/11/2026** e suas regras documentadas. Usam sintaxe [Mermaid](https://mermaid.js.org/) para visualização direta no GitHub. São modelos de arquitetura e comportamento, não evidências de teste integrado.

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

**Cuidados de leitura:** os estados marcados como propostos não devem ser interpretados como transições automáticas já implementadas; não existe API REST própria no repositório. As associações opcionais são mostradas conforme o ORM, sem prometer restrições adicionais do banco físico.

## Conferência de renderização

Os blocos usam notações Mermaid convencionais e foram revisados para evitar rótulos multilinha ambíguos e erros de separação de chaves no DER. O repositório possui uma **verificação estática automatizada** da documentação (`tests/test_documentacao.py`), mas ela **não substitui** uma renderização real pelo GitHub. Após publicar, abrir cada um dos oito links acima e confirmar a exibição dos gráficos.
