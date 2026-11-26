# Diagrama de atividades — preenchimento e fechamento

O processo apresenta a organização vigente das telas e os caminhos de salvamento provisório ou definitivo.

```mermaid
flowchart TD
    A([Início]) --> B["Etapa 1: definir operação, veículo e motorista"]
    B --> C["Etapa 2: dados do frete, carga, documentos e saídas"]
    C --> C1["Selecionar a saida de coleta deste frete"]
    C1 --> D{"Dados suficientes para salvar o frete?"}
    D -->|"Não"| E["Salvar rascunho"]
    E --> F["Retomar e completar etapas 1 a 6"]
    F --> C
    D -->|"Sim"| G["Salvar frete e saídas da operação"]
    G --> H{"Outros fretes no mesmo ciclo?"}
    H -->|"Sim"| I["Cadastrar outro frete sem duplicar o percurso"]
    I --> H
    H -->|"Não"| J["Etapa 7: lançar despesas e abastecimentos uma única vez"]
    J --> K["Etapa 8: conferir KM, receitas, despesas e recebimentos"]
    K --> L{"Operação concluída?"}
    L -->|"Não"| M["Complementar informações operacionais"]
    M --> J
    L -->|"Sim"| N(["Encerramento operacional"])
```

A operação individual e o ciclo utilizam o mesmo cadastro de saídas. O ciclo permite mais fretes e mais saídas preparatórias. As leituras finais de odômetro são informadas na chegada à base, na Etapa 2. Os recebimentos financeiros podem continuar em acompanhamento após a conclusão operacional.
