# ADR-004 — Refatoração conservadora do Streamlit

- **Data:** 24/11/2026
- **Status:** decisão implementada na arquitetura do MVP

## Contexto

O `app.py` do Ajuste 27 concentrava mais de 7 mil linhas de interface, consultas, callbacks, relatórios e CSS. A necessidade de manutenção profissional convive com a exigência de preservar os 11 passos, os dados existentes e as regras financeiras.

## Decisão

Manter `app.py` como entrada Streamlit e extrair cada etapa para uma função `render(ctx)` em módulo próprio. Compartilhar apenas dados de apresentação pelo `PageContext`, manter os callbacks/consultas originais em `core.py`, colocar relatórios em `reporting.py` e visual em `theme.py`/`assets/faeg_styles.html`. Não alterar o ORM ou os serviços operacionais.

## Alternativas consideradas

1. Reescrever cada etapa com novos formulários: rejeitada pelo risco de perda de estado e alterações involuntárias em cálculos.
2. Multipáginas nativas Streamlit: adiada porque mudaria navegação e chaves de widgets.
3. Mover apenas CSS: insuficiente para facilitar manutenção.

## Consequências

- `app.py` pequeno, 11 páginas com responsabilidades claras.
- `core.py` concentra funções compartilhadas e será dividido de forma incremental.
- Implantação exige publicar os novos módulos e o CSS junto com `app.py`.
- A modularização preserva os modelos e os vínculos operacionais do banco.
- A suíte automatizada acompanha a manutenção da estrutura modular e dos serviços existentes.
