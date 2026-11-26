# Diagramas de sequência UML

Os fluxos representam a criação do frete, o registro das saídas e a persistência das despesas. As validações e transações estão agrupadas por responsabilidade.

## 1. Cadastro do frete e vínculo à saída

```mermaid
sequenceDiagram
    actor Operador
    participant UI as Interface Streamlit
    participant ID as Identificacao de fretes
    participant ORM as SQLAlchemy
    participant DB as PostgreSQL
    Operador->>UI: Preenche cadastro e seleciona ciclo e saida
    UI->>ORM: Inicia transacao de salvamento
    alt Novo frete
        ORM->>ID: Reserva codigo interno e ID Frete
        ID->>DB: Consulta codigos com bloqueio transacional
        DB-->>ID: Proxima sequencia disponivel
        ID-->>ORM: Codigos V e FV
    else Edicao de frete
        ORM->>ORM: Preserva os codigos existentes
    end
    ORM->>DB: Localiza ou cria o ciclo operacional
    ORM->>DB: Valida saida e veiculo do mesmo ciclo
    alt Vinculo valido
        ORM->>DB: Grava frete e vinculo da saida de coleta
        ORM->>DB: Grava financeiro individual
        ORM->>DB: Confirma a transacao
        ORM-->>UI: Frete salvo
        UI-->>Operador: Exibe identificadores e saida vinculada
    else Dados inconsistentes
        ORM->>DB: Desfaz a transacao
        UI-->>Operador: Exibe motivo da validacao
    end
```

**Regra:** cada frete recebe um ID `FV` único e contínuo. Uma saída admite vários fretes, mantendo seus dados comerciais individuais. A quilometragem permanece registrada somente na saída.

## 2. Despesa e abastecimento sem duplicação

```mermaid
sequenceDiagram
    actor Operador
    participant UI as Etapa 7
    participant ORM as SQLAlchemy
    participant DB as PostgreSQL
    Operador->>UI: Informa combustivel ou despesa e destino
    UI->>ORM: Verifica dados e possiveis duplicidades
    alt Despesa exclusiva do frete
        ORM->>DB: Cria ViagemDespesa
    else Despesa compartilhada do ciclo
        ORM->>DB: Cria CicloDespesa
    else Despesa pendente do veiculo
        ORM->>DB: Cria VeiculoDespesa
    end
    opt Diesel ou ARLA
        ORM->>DB: Cria historico de Abastecimento vinculado a despesa
    end
    ORM->>DB: Confirma a transacao
    ORM-->>UI: Lancamento persistido
    UI-->>Operador: Atualiza historico e saldo
    opt Cancelamento de despesa direta
        Operador->>UI: Informa o motivo
        UI->>DB: Cancela a despesa e o abastecimento vinculado
    end
```

**Regra:** `abastecimentos` registra o histórico operacional da compra e não acrescenta uma segunda despesa ao DRE.

## 3. Cadastro de saída e quilometragem

```mermaid
sequenceDiagram
    actor Operador
    participant UI as Etapa 2
    participant S as Servico de saidas
    participant ORM as SQLAlchemy
    Operador->>UI: Informa datas e quilometragem da saida
    UI->>S: Valida dados da saida
    opt Novo frete
        UI->>UI: Guarda a saída no rascunho até salvar o frete
    end
    S->>ORM: Salva SaidaOperacional no ciclo
    ORM-->>UI: Identificador da saida
    opt Novo frete do mesmo ciclo
        Operador->>UI: Seleciona a saida ja cadastrada
        UI->>ORM: Registra vinculo de coleta do frete
        ORM-->>UI: Frete associado sem nova saida
    end
    UI->>S: Consulta resumo das saidas
    S-->>UI: KM planejado e real do ciclo
    UI-->>Operador: Exibe operacao consolidada
```

**Regra:** os odômetros de saída e chegada à base determinam o KM real. Uma saída com múltiplos fretes contribui apenas uma vez para os totais físicos do ciclo.
