# Diagramas de estados — operação e financeiro

Os diagramas representam o fluxo de estados do negócio. As opções disponíveis na interface incluem “Aguardando Adiantamento”, “Adiantamento Recebido”, “Em Transporte”, “Entregue / Aguardando Saldo”, “Quitada / Concluída” e “Cancelada”.

## 1. Estado operacional conceitual

```mermaid
stateDiagram-v2
    [*] --> Planejada
    Planejada --> Coletas : Iniciar coletas
    Coletas --> Transporte : Liberar carga
    Transporte --> Entregas : Chegar ao destino
    Entregas --> Retorno : Concluir entregas
    Retorno --> Concluida : Encerrar deslocamentos
    Coletas --> Coletas : Nova saída preparatória
    Transporte --> Coletas : Coleta adicional na operação
    Planejada --> Cancelada : Cancelamento
    Coletas --> Cancelada : Cancelamento autorizado
    Concluida --> [*]
    Cancelada --> [*]
```

## 2. Estado financeiro conceitual (independente)

```mermaid
stateDiagram-v2
    [*] --> SemRecebimento
    SemRecebimento --> Parcial : Recebimento parcial confirmado
    Parcial --> Quitado : Total confirmado cobre negociado
    SemRecebimento --> Quitado : Pagamento integral confirmado
    Parcial --> Parcial : Novas parcelas ou cancelamentos
    Quitado --> Parcial : Cancelamento de pagamento com saldo restante
    Quitado --> [*]
```

O estado operacional e o acompanhamento financeiro são independentes: uma entrega pode estar concluída com recebimentos ainda pendentes. Os diagramas representam transições de negócio e não uma máquina de estados integralmente automatizada.
