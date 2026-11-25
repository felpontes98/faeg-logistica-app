# Diagramas de classes UML — modelo de domínio

As classes abaixo são **entidades ORM reais** de [`database/models.py`](../../database/models.py). Os atributos ilustram campos relevantes; o arquivo Python é a fonte integral de tipos e restrições.

## Núcleo comercial e operacional

```mermaid
classDiagram
    class RascunhoViagem {
      +int id_rascunho
      +str titulo
      +str conteudo_json
    }
    class Cliente {
      +int id_cliente
      +str razao_social
      +str cnpj_cpf
    }
    class CicloOperacional {
      +int id_ciclo
      +str nome_operacao
      +str status_ciclo
      +date data_abertura
    }
    class Viagem {
      +int id_viagem
      +str codigo_viagem
      +int id_ciclo
      +str tipo_viagem
      +str rota_resumo
      +decimal km_rota_planejado
    }
    class FreteFinanceiro {
      +int id_viagem
      +decimal valor_negociado_total
      +decimal valor_adiantamento
      +decimal valor_saldo
    }
    class RecebimentoFrete {
      +int id_recebimento
      +int id_viagem
      +decimal valor_recebido
      +bool cancelado
    }
    class SaidaOperacional {
      +int id_saida
      +int id_ciclo
      +int id_veiculo
      +decimal km_planejado_manual
      +decimal km_saida_coletas
      +decimal km_rota_principal
      +decimal km_retorno_base
      +int odometro_inicial
      +int odometro_final
    }
    class TrechoOperacional {
      +int id_trecho
      +int id_saida
      +str origem
      +str destino
      +decimal km_planejado
    }
    class Veiculo {
      +int id_veiculo
      +str placa
      +str tipo_veiculo
    }
    class Motorista {
      +int id_motorista
      +str nome_completo
    }
    Cliente "1" --> "0..*" CicloOperacional : referencia
    CicloOperacional "1" --> "0..*" Viagem : agrupa
    Viagem "1" --> "0..1" FreteFinanceiro : possui
    Viagem "1" --> "0..*" RecebimentoFrete : recebe
    CicloOperacional "1" --> "0..*" SaidaOperacional : executa
    SaidaOperacional "1" *-- "0..*" TrechoOperacional : detalha
    Veiculo "1" --> "0..*" Viagem : vinculado
    Veiculo "1" --> "0..*" SaidaOperacional : realiza
    Motorista "0..1" --> "0..*" SaidaOperacional : opcional
```

## Custos, abastecimentos e atribuições

```mermaid
classDiagram
    class ViagemDespesa {
      +int id_despesa
      +int id_viagem
      +decimal valor_total
      +str tipo_despesa
    }
    class CicloDespesa {
      +int id_despesa_ciclo
      +int id_ciclo
      +decimal valor_total
      +bool cancelado
    }
    class VeiculoDespesa {
      +int id_despesa_veiculo
      +int id_veiculo
      +decimal valor_total
      +bool cancelado
    }
    class VeiculoDespesaAtribuicao {
      +int id_evento
      +str acao
      +str tipo_destino
      +str motivo
    }
    class Abastecimento {
      +int id_abastecimento
      +int id_veiculo
      +int odometro
      +decimal litros
      +decimal valor_total
    }
    class ParametroConsumoVeiculo {
      +int id_veiculo
      +decimal km_por_litro
      +decimal preco_litro_referencia
    }
    class Fornecedor {
      +int id_fornecedor
      +str nome_fantasia
    }
    class Viagem {
      +int id_viagem
    }
    class CicloOperacional {
      +int id_ciclo
    }
    class Veiculo {
      +int id_veiculo
    }
    Viagem "1" --> "0..*" ViagemDespesa
    CicloOperacional "1" --> "0..*" CicloDespesa
    Veiculo "1" --> "0..*" VeiculoDespesa
    VeiculoDespesa "1" --> "0..*" VeiculoDespesaAtribuicao
    Veiculo "1" --> "0..*" Abastecimento
    Veiculo "1" --> "0..1" ParametroConsumoVeiculo
    Fornecedor "0..1" --> "0..*" ViagemDespesa : opcional
    Fornecedor "0..1" --> "0..*" CicloDespesa : opcional
```

**Observação:** `Abastecimento` guarda referência a **uma** despesa de origem de frete, ciclo ou veículo. Esta associação polimórfica por FKs opcionais está detalhada no [DER](entidade_relacionamento.md). Não significa um novo custo financeiro.
