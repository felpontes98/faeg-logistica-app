# Diagrama de atividades — ciclo, saídas e fechamento

```mermaid
flowchart TD
    A(["Início"]) --> B["Definir operação individual ou ciclo"]
    B --> C["Cadastrar e salvar frete"]
    C --> D{"Novo frete na mesma operação?"}
    D -->|"Sim"| E["Vincular outro frete ao ciclo"]
    E --> D
    D -->|"Não ou continuar"| F["Registrar saídas operacionais"]
    F --> G{"Saída possui trechos?"}
    G -->|"Sim"| H["KM planejado: soma dos trechos"]
    G -->|"Não"| I["KM planejado: valor da saída"]
    H --> J["Registrar leituras e despesas"]
    I --> J
    J --> K{"Odômetros válidos e sem sobreposição?"}
    K -->|"Não"| L["KM real pendente"]
    K -->|"Sim"| M["Somar KM real das saídas"]
    L --> N["Consolidar receitas e custos uma vez"]
    M --> N
    N --> O["Exibir resultado gerencial parcial"]
    O --> P{"Operação concluída?"}
    P -->|"Não"| F
    P -->|"Sim"| Q(["Encerramento operacional"])
```

**Modelo conceitual:** o encerramento automático do ciclo e todos os rótulos operacionais ainda dependem de validação. Os recebimentos podem permanecer pendentes após a entrega.
