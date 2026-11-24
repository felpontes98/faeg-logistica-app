# Diagrama de atividades — operação e fechamento

```mermaid
flowchart TD
    A([Início]) --> B[Definir operação individual ou ciclo]
    B --> C[Cadastrar e salvar primeiro frete]
    C --> D{Surge outro frete na mesma operação física?}
    D -- Sim --> E[Vincular novo frete ao ciclo]
    E --> D
    D -- Não / continuar --> F[Registrar saídas operacionais]
    F --> G{Possui trechos detalhados?}
    G -- Sim --> H[KM planejado da saída = soma de trechos]
    G -- Não --> I[KM planejado da saída = valor manual]
    H --> J[Registrar odômetros e gastos]
    I --> J
    J --> K{Todas as saídas com odômetros válidos e sem sobreposição?}
    K -- Não --> L[KM real pendente de conferência]
    K -- Sim --> M[Somar KM real por saída]
    L --> N[Consolidar financeiro do ciclo]
    M --> N
    N --> O[Somar receitas negociadas por frete]
    O --> P[Subtrair despesas exclusivas e compartilhadas uma vez]
    P --> Q[Apresentar resultado operacional parcial]
    Q --> R{Todas as entregas concluídas?}
    R -- Não --> F
    R -- Sim --> S([Encerramento operacional; recebimentos podem seguir pendentes])
```

A sequência mostra as decisões conceituais relevantes. O encerramento formal automático do ciclo **ainda não foi homologado** e não deve ser inferido deste diagrama.
