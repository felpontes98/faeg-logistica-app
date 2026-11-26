# Diagramas de estados — operação e financeiro

Acompanhamos a execução pelas situações Planejada, Em Transporte, Entregue, Concluída e Cancelada. Apuramos a situação financeira pelos recebimentos confirmados de cada frete.

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
    Quitado --> SemRecebimento : Cancelar pagamento integral
    Parcial --> SemRecebimento : Cancelar último pagamento
```

O estado operacional e o acompanhamento financeiro são independentes: uma entrega pode estar concluída com recebimentos ainda pendentes. Os diagramas representam transições de negócio e não uma máquina de estados integralmente automatizada.
