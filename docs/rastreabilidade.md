# Matriz de rastreabilidade — requisitos, implementação e verificação

**Base:** requisitos históricos `RF-01` a `RF-47`, documento [`requisitos.md`](requisitos.md); referências às classes e métodos do ZIP recebido. A tabela apresenta **módulos identificados**, não certificação de testes integrados.

| Conjunto de requisitos | Implementação principal | Verificação disponível | Estado de aceite |
| --- | --- | --- | --- |
| RF-01–04 | `faeg_app/pages/etapa_01_frota.py`, `etapa_02_frete_documentos.py`, `etapa_03_cliente.py`, `etapa_04_negociacao_recebimentos.py`, `database/models.py` | Roteiro manual TI-01/TI-02 | Homologação pendente |
| RF-05–07, RF-34, RF-37–41 | `faeg_app/pages/etapa_02_frete_documentos.py`, `etapa_08_fechamento.py`, `faeg_app/core.py` (KM legado) | Roteiro TI-06/TI-07 | Usar somente sem saída cadastrada |
| RF-08–10, RF-20, RF-22 | `faeg_app/pages/etapa_07_despesas.py`, `database/controle_abastecimentos.py` | Roteiro TI-04 | Homologação pendente |
| RF-11, RF-21, RF-24, RF-29 | `faeg_app/pages/etapa_09_relatorios.py`, `faeg_app/reporting.py` | Roteiro TI-09 | Homologação pendente |
| RF-12 | `database/importador_planilha.py`, `database/conciliacao_planilha.py` | Roteiro TI-10 | Prévia disponível; gravação bloqueada |
| RF-13, RF-17–18 | `faeg_app/pages/etapa_04_negociacao_recebimentos.py`, `database/models.py` | Roteiro TI-02 | Homologação pendente |
| RF-14–16, RF-19, RF-28, RF-30 | `database/fechamento_ciclos.py`, `faeg_app/pages/etapa_08_fechamento.py`, `etapa_09_relatorios.py` | Roteiro TI-03/TI-08 | Homologação pendente |
| RF-23, RF-25–27 | `database/atribuicao_despesas.py`, `faeg_app/pages/etapa_07_despesas.py` | Roteiro TI-05 | Homologação pendente |
| RF-31–33, RF-35–36 | `database/conferencia_duplicidades.py`, `faeg_app/pages/etapa_07_despesas.py` | Roteiro TI-11 | Homologação pendente |
| RF-42–45 | `database/saidas_operacionais.py`, `views/saidas_operacionais.py` | TU-01, TU-02, TU-03, TU-05, TU-06 | Unitário disponível; integrado pendente |
| RF-46 | `database/saidas_operacionais.py` (`estimar_consumo`) | TU-04 | Unitário disponível; conciliação real pendente |
| RF-47 | `faeg_app/reporting.py`, `faeg_app/pages/etapa_09_relatorios.py` (exportação) | Roteiro TI-09 | Homologação pendente |

**Observação:** as regras operacionais estão em [`regras_negocio.md`](regras_negocio.md). Teste unitário não comprova desempenho, acesso, autorização ou persistência PostgreSQL/Neon.
