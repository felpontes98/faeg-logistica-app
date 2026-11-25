# Diagrama de implantação — desenvolvimento e execução

```mermaid
flowchart TB
    subgraph DEV["Estação de desenvolvimento"]
        IDE["VSCode e ambiente Python"]
        GIT["Git local"]
    end
    subgraph CLOUD["Serviços externos"]
        GH["GitHub - repositório"]
        ST["Hospedagem Streamlit"]
        DB[("Neon - PostgreSQL")]
    end
    USER["Navegador do operador"]
    IDE --> GIT
    GIT -->|"git push"| GH
    GH -->|"Publicação configurada"| ST
    USER <-->|"HTTPS"| ST
    ST <-->|"Conexão SQLAlchemy"| DB
```

- O GitHub armazena o código. O provedor Streamlit executa a aplicação e utiliza a `DATABASE_URL` configurada fora do repositório.
- A publicação do código, a inicialização da aplicação e a sincronização do banco constituem etapas distintas do ciclo de implantação.
- A hospedagem e os controles de infraestrutura são configurados no ambiente de execução. A autenticação por perfil integra o planejamento técnico.
