# Diagrama de componentes — arquitetura implementada

```mermaid
flowchart LR
    Pessoa[Operador ou gestor]
    subgraph APP["Processo Python - Streamlit"]
        UI["app.py - 11 etapas"]
        V["views/saidas_operacionais.py"]
        B["database/
Regras de negócio e consultas"]
        M["database/models.py
18 modelos ORM"]
        C["database/connection.py
SessionLocal"]
    end
    NEON[(PostgreSQL / Neon)]
    SAIDA[PDF e planilhas Excel]
    FILE[Planilha Excel de entrada]
    Pessoa --> UI
    UI --> V
    UI --> B
    V --> B
    B --> M
    UI --> M
    M --> C
    C --> NEON
    UI --> SAIDA
    FILE --> UI
    UI -->|Prévia e auditoria; escrita bloqueada| B
```

**Características reais:** o aplicativo opera como processo Streamlit com acesso ao banco via SQLAlchemy; não há camada HTTP REST independente entre `app.py` e a persistência. A geração de relatórios ocorre na aplicação. A sincronização de tabelas/colunas é chamada no início de `app.py`.

**Nota histórica:** na revisão documental anterior, `app.py` ainda tinha mais de 7 mil linhas. A modularização conservadora foi realizada posteriormente; consulte o complemento abaixo e a [arquitetura da aplicação](../arquitetura_aplicacao.md).

## Complemento — módulos após refatoração

```mermaid
flowchart TB
    A[app.py] --> B[faeg_app/layout.py]
    A --> C[faeg_app/pages — 11 etapas]
    A --> D[faeg_app/bootstrap.py]
    A --> E[faeg_app/theme.py]
    C --> F[faeg_app/core.py]
    C --> G[faeg_app/reporting.py]
    F --> H[database/ — ORM e regras]
    G --> H
    H --> I[(PostgreSQL / Neon)]
    C --> J[views/saidas_operacionais.py]
    E --> K[assets/faeg_styles.html]
```

A modularização é interna ao mesmo processo Streamlit; **não cria API REST nem novos microserviços**.
