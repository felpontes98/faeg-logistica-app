# Casos de uso do Sistema FAEG

**Tipo:** visão funcional de casos de uso, em fluxograma Mermaid. Para um diagrama UML formal de casos de uso seria necessário um renderizador específico; aqui foi priorizada a leitura diretamente pelo GitHub.

```mermaid
flowchart LR
    O([Operador FAEG])
    G([Gestor / responsável pela operação])
    T([Equipe de desenvolvimento])
    subgraph SYS["Sistema Web FAEG"]
        UC1([Manter cadastros])
        UC2([Cadastrar frete])
        UC3([Agrupar fretes em ciclo])
        UC4([Registrar negociação e recebimentos])
        UC5([Registrar coleta e entrega])
        UC6([Lançar despesas e abastecimentos])
        UC7([Registrar saídas e trechos])
        UC8([Consultar fechamento e indicadores])
        UC9([Exportar relatórios])
        UC10([Analisar dados e testar alterações])
    end
    O --> UC1
    O --> UC2
    O --> UC3
    O --> UC4
    O --> UC5
    O --> UC6
    O --> UC7
    G --> UC8
    G --> UC9
    G --> UC3
    T --> UC10
```

**Limite do escopo:** não estão modelados autenticação por perfil, conciliação bancária automatizada, emissão fiscal automática ou rastreamento de carga, porque tais funcionalidades não foram comprovadas no código inspecionado.
