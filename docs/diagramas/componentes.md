# Diagrama de componentes — arquitetura do FAEG

A aplicação é executada em um único processo Streamlit, com interface modularizada,
regras de negócio em Python e persistência no PostgreSQL (Neon) por SQLAlchemy.
Não existe uma API REST intermediária.

## Visão lógica

```mermaid
flowchart LR
    P["Operador ou gestor"]
    subgraph S["Aplicação FAEG - Streamlit"]
        UI["Interface e 11 etapas"]
        REG["Regras de negócio e consultas"]
        REL["Relatórios PDF e Excel"]
        ORM["Modelos SQLAlchemy"]
        CON["Conexão e sessões"]
    end
    DB[("PostgreSQL - Neon")]
    P --> UI
    UI --> REG
    UI --> REL
    REG --> ORM
    ORM --> CON
    CON --> DB
```

## Organização dos módulos Python

```mermaid
flowchart TB
    A["app.py"] --> BOOT["faeg_app/bootstrap.py"]
    A --> L["faeg_app/layout.py"]
    A --> T["faeg_app/theme.py"]
    A --> P["faeg_app/pages - 11 etapas"]
    P --> CORE["faeg_app/core.py"]
    P --> V["views - percurso, saídas e parâmetros"]
    P --> R["faeg_app/reporting.py"]
    CORE --> D["database - modelos e operações"]
    V --> D
    R --> D
    D --> C["database/connection.py"]
    C --> N[("PostgreSQL - Neon")]
    T --> CSS["assets/faeg_styles.html"]
```

Os módulos de interface compartilham o contexto do Streamlit. O código de
persistência e os modelos ORM permanecem na pasta `database/`; a pasta `views/`
contém componentes operacionais reutilizáveis. Os diagramas representam a
organização do código, não serviços independentes.
