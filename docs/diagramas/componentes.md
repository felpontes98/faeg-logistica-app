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

**Ponto de evolução:** separar o arquivo `app.py` (mais de 7 mil linhas na versão revisada) por páginas/serviços, mas somente com testes de regressão e sem reorganizar código produtivo nesta atualização documental.
