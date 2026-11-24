# Diagrama de componentes — arquitetura modular implementada

O projeto é um **monólito Streamlit modularizado**. `app.py` apenas inicializa e seleciona a etapa; os módulos Python compartilham a mesma aplicação e acessam o banco por SQLAlchemy. **Não existe API REST própria**, microsserviço ou autenticação por perfis implementada no código revisado.

```mermaid
flowchart LR
    P["Operador FAEG"]
    subgraph APP["Aplicação Streamlit - Python"]
        ENTRY["app.py - ponto de entrada"]
        BOOT["faeg_app/bootstrap.py"]
        LAYOUT["layout.py e theme.py"]
        PAGES["faeg_app/pages - 11 etapas"]
        CORE["faeg_app/core.py - lógica compartilhada"]
        REPORT["faeg_app/reporting.py - PDF e Excel"]
        VIEWS["views/saidas_operacionais.py"]
        SERVICES["database - serviços operacionais"]
        ORM["database/models.py e connection.py"]
    end
    DB[("PostgreSQL - Neon")]
    P --> ENTRY
    ENTRY --> BOOT
    ENTRY --> LAYOUT
    ENTRY --> PAGES
    PAGES --> CORE
    PAGES --> REPORT
    PAGES --> VIEWS
    CORE --> SERVICES
    VIEWS --> SERVICES
    REPORT --> SERVICES
    SERVICES --> ORM
    ORM --> DB
```

O diretório `assets/` fornece o logotipo e o estilo visual. O importador em `database/importador_planilha.py` permite **prévia e auditoria**, não importação persistente liberada. O serviço inicializa a sincronização de esquema já existente; ela não é equivalente a um controle de migrações versionadas.

Referência de implementação: [arquitetura da aplicação](../arquitetura_aplicacao.md).
