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
- O `git push` **não garante** que o aplicativo iniciou ou que houve sucesso no banco. A sincronização do esquema executada na abertura também exige cautela.
- Autenticação por perfil dentro do aplicativo, configuração exata da hospedagem e controles de rede **não foram auditados** no ZIP recebido.
