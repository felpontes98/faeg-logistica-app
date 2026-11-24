# Diagramas de estados — operação e financeiro

O modelo apresenta **estados de negócio** e ajuda a documentar transições desejadas. **Não é uma máquina de estados automática implementada integralmente em `app.py`**; as opções atuais da interface incluem rótulos como “Aguardando Adiantamento”, “Adiantamento Recebido”, “Em Transporte”, “Entregue / Aguardando Saldo”, “Quitada / Concluída” e “Cancelada”.

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

**Cuidado:** o código controla recebimentos e saldos efetivos, mas a implantação do controle financeiro de estados, com todas essas transições e permissões, depende de validação. Uma entrega pode estar concluída mesmo com cobrança pendente.
