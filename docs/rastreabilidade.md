# Matriz de rastreabilidade — requisitos, implementação e verificação

**Base:** requisitos históricos `RF-01` a `RF-47`, documento [`requisitos.md`](requisitos.md); referências às classes e métodos do ZIP recebido. A tabela apresenta **módulos identificados**, não certificação de testes integrados.

| Conjunto de requisitos | Implementação principal | Verificação disponível | Estado de aceite |
| --- | --- | --- | --- |
| RF-01–04 | `app.py`, `database/models.py` (cadastros, viagem, negociação) | Roteiro manual TI-01/TI-02 | Homologação pendente |
| RF-05–07, RF-34, RF-37–41 | `app.py` (KM legado) | Roteiro TI-06/TI-07 | Usar somente sem saída cadastrada |
| RF-08–10, RF-20, RF-22 | `app.py`, `database/controle_abastecimentos.py` | Roteiro TI-04 | Homologação pendente |
| RF-11, RF-21, RF-24, RF-29 | `app.py` (relatórios/Excel) | Roteiro TI-09 | Homologação pendente |
| RF-12 | `database/importador_planilha.py`, `database/conciliacao_planilha.py` | Roteiro TI-10 | Prévia disponível; gravação bloqueada |
| RF-13, RF-17–18 | `app.py`, `database/models.py` (recebimentos) | Roteiro TI-02 | Homologação pendente |
| RF-14–16, RF-19, RF-28, RF-30 | `database/fechamento_ciclos.py`, `app.py` | Roteiro TI-03/TI-08 | Homologação pendente |
| RF-23, RF-25–27 | `database/atribuicao_despesas.py`, `app.py` | Roteiro TI-05 | Homologação pendente |
| RF-31–33, RF-35–36 | `database/conferencia_duplicidades.py`, `app.py` | Roteiro TI-11 | Homologação pendente |
| RF-42–45 | `database/saidas_operacionais.py`, `views/saidas_operacionais.py` | TU-01, TU-02, TU-03, TU-05, TU-06 | Unitário disponível; integrado pendente |
| RF-46 | `database/saidas_operacionais.py` (`estimar_consumo`) | TU-04 | Unitário disponível; conciliação real pendente |
| RF-47 | `app.py` (exportação de saídas/trechos/KM) | Roteiro TI-09 | Homologação pendente |

**Observação:** as regras operacionais estão em [`regras_negocio.md`](regras_negocio.md). Teste unitário não comprova desempenho, acesso, autorização ou persistência PostgreSQL/Neon.
