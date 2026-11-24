# Diagramas entidade-relacionamento — 18 tabelas SQLAlchemy

**Fonte:** [`database/models.py`](../../database/models.py), versão do repositório de 24/11/2026. As 18 tabelas são divididas em duas visões para permitir leitura no GitHub; entidades compartilhadas aparecem em ambas. As chaves e relacionamentos destacados correspondem às FKs do ORM. Os diagramas **não substituem** a verificação das restrições físicas do Neon.

## 1. Cadastros, fretes, ciclos e percurso

```mermaid
erDiagram
    CLIENTES ||--o{ CICLOS_OPERACIONAIS : referencia
    CLIENTES |o--o{ LOCAIS : vincula_opcionalmente
    CLIENTES ||--o{ FRETES_FINANCEIRO : contrata
    CICLOS_OPERACIONAIS ||--o| CICLOS_FINANCEIRO : financeiro_legado
    CICLOS_OPERACIONAIS ||--o{ VIAGENS : agrupa
    CICLOS_OPERACIONAIS ||--o{ SAIDAS_OPERACIONAIS : inclui
    VIAGENS ||--o| FRETES_FINANCEIRO : negocia
    VIAGENS ||--o{ RECEBIMENTOS_FRETE : recebe
    MOTORISTAS ||--o{ VIAGENS : conduz
    MOTORISTAS |o--o{ SAIDAS_OPERACIONAIS : opcional
    VEICULOS ||--o{ VIAGENS : aloca
    VEICULOS ||--o{ SAIDAS_OPERACIONAIS : percorre
    LOCAIS ||--o{ VIAGENS : coleta_e_entrega
    SAIDAS_OPERACIONAIS ||--o{ TRECHOS_OPERACIONAIS : detalha
    VEICULOS ||--o| PARAMETROS_CONSUMO_VEICULO : parametriza
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
    CICLOS_OPERACIONAIS {
        int id_ciclo PK
        int id_cliente FK
        string nome_operacao
    }
    CICLOS_FINANCEIRO {
        int id_ciclo PK, FK
        decimal valor_negociado_total
    }
    VIAGENS {
        int id_viagem PK
        int id_ciclo FK
        int id_veiculo FK
        int id_motorista FK
        string codigo_viagem UK
    }
    FRETES_FINANCEIRO {
        int id_viagem PK, FK
        int id_cliente FK
        decimal valor_negociado_total
    }
    RECEBIMENTOS_FRETE {
        int id_recebimento PK
        int id_viagem FK
        decimal valor_recebido
    }
    SAIDAS_OPERACIONAIS {
        int id_saida PK
        int id_ciclo FK
        int id_veiculo FK
        int id_motorista FK
    }
    TRECHOS_OPERACIONAIS {
        int id_trecho PK
        int id_saida FK
        decimal km_planejado
    }
    PARAMETROS_CONSUMO_VEICULO {
        int id_veiculo PK, FK
        decimal km_por_litro
    }
```

**Observação:** `viagens` possui duas referências obrigatórias a `locais` (`id_local_coleta` e `id_local_entrega`), representadas por uma única ligação para preservar a leitura. `saidas_operacionais.id_motorista` e `locais.id_cliente` são opcionais. `ciclos_financeiro` mantém dados legados; a negociação atual é individualizada em `fretes_financeiro`.

## 2. Despesas e abastecimentos

```mermaid
erDiagram
    VIAGENS ||--o{ VIAGENS_DESPESAS : possui
    CICLOS_OPERACIONAIS ||--o{ CICLOS_DESPESAS : possui
    VEICULOS ||--o{ VEICULOS_DESPESAS : registra
    VEICULOS_DESPESAS ||--o{ VEICULOS_DESPESAS_ATRIBUICOES : historico
    VEICULOS ||--o{ ABASTECIMENTOS : abastece
    FORNECEDORES |o--o{ VIAGENS_DESPESAS : fornece
    FORNECEDORES |o--o{ CICLOS_DESPESAS : fornece
    FORNECEDORES |o--o{ VEICULOS_DESPESAS : fornece
    FORNECEDORES |o--o{ ABASTECIMENTOS : fornece
    VIAGENS_DESPESAS |o--o| ABASTECIMENTOS : origem_opcional
    CICLOS_DESPESAS |o--o| ABASTECIMENTOS : origem_opcional
    VEICULOS_DESPESAS |o--o| ABASTECIMENTOS : origem_opcional
    VEICULOS_DESPESAS |o--o| VIAGENS_DESPESAS : destino_opcional
    VEICULOS_DESPESAS |o--o| CICLOS_DESPESAS : destino_opcional
    VIAGENS {
        int id_viagem PK
    }
    CICLOS_OPERACIONAIS {
        int id_ciclo PK
    }
    VEICULOS {
        int id_veiculo PK
    }
    FORNECEDORES {
        int id_fornecedor PK
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
        decimal litros
    }
```

**Regra essencial:** cada abastecimento aponta para a despesa financeira de origem de frete, ciclo **ou** veículo. O histórico de abastecimento **não** é somado novamente à DRE. As três FKs de origem são opcionais no ORM; as validações de negócio devem impedir origens conflitantes. Atributos de cancelamento, fornecedores e atribuições estão resumidos no diagrama.
