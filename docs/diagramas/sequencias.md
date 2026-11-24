# Diagramas de sequência UML

Os diagramas descrevem **fluxos resumidos** observáveis no código. Transações, validações e mensagens foram agrupadas para legibilidade; não representam linha a linha todas as ramificações.

## 1. Cadastro de frete e vínculo a ciclo

```mermaid
sequenceDiagram
    actor Operador
    participant UI as Streamlit (app.py)
    participant ORM as SQLAlchemy / SessionLocal
    participant DB as PostgreSQL / Neon
    Operador->>UI: Preenche etapas 1 a 6 e solicita salvar
    UI->>UI: Valida ID Frete, dados e situação do ciclo
    UI->>ORM: Localiza ou cria CicloOperacional
    ORM->>DB: SELECT / INSERT de ciclo
    DB-->>ORM: ID interno do ciclo
    UI->>ORM: Cria/atualiza Viagem e FreteFinanceiro
    ORM->>DB: INSERT / UPDATE na transação
    alt Gravação confirmada
        DB-->>ORM: Commit
        ORM-->>UI: Identificadores persistidos
        UI-->>Operador: Confirmação da viagem salva
    else Violação ou erro
        DB-->>ORM: Falha/rollback
        UI-->>Operador: Aviso; não considerar salvo
    end
```

**Regra:** o ID comercial de cada frete é independente do ID interno do ciclo; pagamentos confirmados têm registros próprios, não são inferidos a partir do adiantamento previsto.

## 2. Despesa e abastecimento sem duplicação

```mermaid
sequenceDiagram
    actor Operador
    participant UI as Etapa 7 / app.py
    participant ORM as SQLAlchemy
    participant DB as PostgreSQL
    Operador->>UI: Informa Diesel/ARLA, litros, preço, odômetro e destino
    UI->>UI: Valida destino e verifica possíveis custos semelhantes
    alt Custo de um frete
        UI->>ORM: Cria ViagemDespesa
    else Compartilhado do ciclo
        UI->>ORM: Cria CicloDespesa
    else Pendente do veículo
        UI->>ORM: Cria VeiculoDespesa
    end
    ORM->>DB: Persiste despesa financeira de origem
    UI->>ORM: Vincula Abastecimento à mesma despesa
    ORM->>DB: Persiste histórico operacional e efetua commit
    DB-->>UI: Transação confirmada
    UI-->>Operador: Histórico e custo sem lançamento financeiro duplo
```

**Regra:** a linha de `abastecimentos` é apenas uma projeção operacional da despesa original e não entra novamente na DRE.

## 3. Registrar saída e atualizar KM físico

```mermaid
sequenceDiagram
    actor Operador
    participant UI as Etapa 8 / views
    participant S as database/saidas_operacionais.py
    participant DB as SQLAlchemy / PostgreSQL
    Operador->>UI: Informa saída, datas, veículo, KM e odômetros
    UI->>S: salvar_saida(...)
    S->>S: validar_saida(...)
    S->>DB: INSERT/UPDATE SaidaOperacional
    DB-->>S: ID da saída
    UI->>DB: Commit da transação
    opt Registrar trechos
        Operador->>UI: Informa origem, destino e KM de cada trecho
        UI->>S: salvar_trecho(...)
        S->>DB: INSERT/UPDATE TrechoOperacional
        UI->>DB: Commit
    end
    UI->>S: consultar_saidas() e resumo_saidas()
    S-->>UI: KM planejado e KM real (ou pendente)
    UI-->>Operador: Fechamento físico do ciclo
```

**Regra:** se há trechos, eles prevalecem sobre o KM manual da saída; odômetro parcial impede total real definitivo.
