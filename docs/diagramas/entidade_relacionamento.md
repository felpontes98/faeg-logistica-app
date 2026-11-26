# Modelo entidade-relacionamento — 19 tabelas

O diagrama deriva das classes em [`database/models.py`](../../database/models.py), com as chaves e os relacionamentos principais. Inclui todas as 19 tabelas, embora nem todos os atributos e FKs opcionais estejam desenhados para preservar a legibilidade.

```mermaid
erDiagram
    CLIENTES ||--o{ CICLOS_OPERACIONAIS : referencia
    CLIENTES |o--o{ LOCAIS : referencia_opcional
    CLIENTES |o--o{ FRETES_FINANCEIRO : contratante
    CICLOS_OPERACIONAIS ||--o| CICLOS_FINANCEIRO : legado
    CICLOS_OPERACIONAIS ||--o{ VIAGENS : agrupa
    CICLOS_OPERACIONAIS ||--o{ CICLOS_DESPESAS : compartilha
    CICLOS_OPERACIONAIS ||--o{ SAIDAS_OPERACIONAIS : executa
    VIAGENS ||--o| FRETES_FINANCEIRO : negocia
    VIAGENS ||--o{ RECEBIMENTOS_FRETE : registra
    VIAGENS ||--o{ VIAGENS_DESPESAS : possui
    VEICULOS ||--o{ VIAGENS : aloca
    MOTORISTAS ||--o{ VIAGENS : conduz
    VEICULOS ||--o{ SAIDAS_OPERACIONAIS : desloca
    MOTORISTAS |o--o{ SAIDAS_OPERACIONAIS : opcional
    SAIDAS_OPERACIONAIS ||--o{ TRECHOS_OPERACIONAIS : detalha
    SAIDAS_OPERACIONAIS |o--o{ VIAGENS : coleta
    VEICULOS ||--o| PARAMETROS_CONSUMO_VEICULO : parametriza
    VEICULOS ||--o{ VEICULOS_DESPESAS : origina
    VEICULOS_DESPESAS ||--o{ VEICULOS_DESPESAS_ATRIBUICOES : audita
    VEICULOS ||--o{ ABASTECIMENTOS : compra
    FORNECEDORES |o--o{ VIAGENS_DESPESAS : fornece
    FORNECEDORES |o--o{ CICLOS_DESPESAS : fornece
    FORNECEDORES |o--o{ VEICULOS_DESPESAS : fornece
    FORNECEDORES |o--o{ ABASTECIMENTOS : fornece
    VIAGENS_DESPESAS |o--o| ABASTECIMENTOS : origem_opcional
    CICLOS_DESPESAS |o--o| ABASTECIMENTOS : origem_opcional
    VEICULOS_DESPESAS |o--o| ABASTECIMENTOS : origem_opcional
    CLIENTES {
        int id_cliente PK
        string razao_social
        string cnpj_cpf UK
    }
    MOTORISTAS {
        int id_motorista PK
        string nome_completo
    }
    VEICULOS {
        int id_veiculo PK
        string placa UK
    }
    LOCAIS {
        int id_local PK
        int id_cliente FK
    }
    FORNECEDORES {
        int id_fornecedor PK
        string nome_fantasia
    }
    CICLOS_OPERACIONAIS {
        int id_ciclo PK
        int id_cliente FK
        string nome_operacao
    }
    CICLOS_FINANCEIRO {
        int id_ciclo PK
        decimal valor_negociado_total
    }
    VIAGENS {
        int id_viagem PK
        int id_ciclo FK
        int id_saida_coleta FK
        string codigo_viagem UK
    }
    FRETES_FINANCEIRO {
        int id_viagem PK
        int id_cliente FK
        decimal valor_negociado_total
    }
    RECEBIMENTOS_FRETE {
        int id_recebimento PK
        int id_viagem FK
        decimal valor_recebido
    }
    VIAGENS_DESPESAS {
        int id_despesa PK
        int id_viagem FK
        decimal valor_total
    }
    CICLOS_DESPESAS {
        int id_despesa_ciclo PK
        int id_ciclo FK
        decimal valor_total
    }
    VEICULOS_DESPESAS {
        int id_despesa_veiculo PK
        int id_veiculo FK
        decimal valor_total
    }
    VEICULOS_DESPESAS_ATRIBUICOES {
        int id_evento PK
        int id_despesa_veiculo FK
    }
    ABASTECIMENTOS {
        int id_abastecimento PK
        int id_veiculo FK
        int odometro
    }
    SAIDAS_OPERACIONAIS {
        int id_saida PK
        int id_ciclo FK
        int id_veiculo FK
    }
    TRECHOS_OPERACIONAIS {
        int id_trecho PK
        int id_saida FK
        decimal km_planejado
    }
    RASCUNHOS_VIAGENS {
        int id_rascunho PK
        string titulo
        string conteudo_json
    }
    PARAMETROS_CONSUMO_VEICULO {
        int id_veiculo PK
        decimal km_por_litro
    }
```

**Vínculos não desenhados:** `viagens` referencia `locais` duas vezes (coleta e entrega); os campos de origem de `abastecimentos` são FKs opcionais e alternativas; `veiculos_despesas` mantém possíveis FKs para despesas de destino após atribuição. Verificar restrições efetivas no PostgreSQL antes de afirmar exclusividade transacional completa.

As chaves primárias de `CICLOS_FINANCEIRO`, `FRETES_FINANCEIRO` e `PARAMETROS_CONSUMO_VEICULO` também participam de relacionamentos por chave estrangeira.

`RASCUNHOS_VIAGENS` é independente dos registros definitivos: um rascunho ainda não representa um frete fechado ou lançamento financeiro.
