# Matriz de rastreabilidade — requisitos, implementação e verificação

**Base:** requisitos `RF-01` a `RF-53` documentados em [`requisitos.md`](requisitos.md). A matriz relaciona cada conjunto à implementação e aos cenários de verificação do [plano de testes](plano_testes.md).

| Conjunto de requisitos | Implementação principal | Cenário de verificação |
| --- | --- | --- |
| RF-01–04 | `faeg_app/pages/etapa_01_frota.py`, `etapa_02_frete_documentos.py`, `etapa_03_cliente.py`, `etapa_04_negociacao_recebimentos.py`, `database/models.py` | Roteiro manual TI-01/TI-02 |
| RF-05–07, RF-34, RF-37–40 | `faeg_app/pages/etapa_02_frete_documentos.py`, `views/percurso_etapa2.py`, `database/saidas_operacionais.py` e `faeg_app/pages/etapa_08_fechamento.py` (consolidação) | Roteiro TI-06/TI-07 |
| RF-08–10, RF-20, RF-22 | `faeg_app/pages/etapa_07_despesas.py`, `database/controle_abastecimentos.py` | Roteiro TI-04 |
| RF-11, RF-21, RF-24, RF-29 | `faeg_app/pages/etapa_09_relatorios.py`, `faeg_app/reporting.py` | Roteiro TI-09 |
| RF-12 | `database/importador_planilha.py`, `database/conciliacao_planilha.py` | Roteiro TI-10 |
| RF-13, RF-17–18 | `faeg_app/pages/etapa_04_negociacao_recebimentos.py`, `database/models.py` | Roteiro TI-02 |
| RF-14–16, RF-19, RF-28, RF-30 | `database/fechamento_ciclos.py`, `faeg_app/pages/etapa_08_fechamento.py`, `etapa_09_relatorios.py` | Roteiro TI-03/TI-08 |
| RF-23, RF-25–27 | `database/atribuicao_despesas.py`, `faeg_app/pages/etapa_07_despesas.py` | Roteiro TI-05 |
| RF-31–33, RF-35–36 | `database/conferencia_duplicidades.py`, `faeg_app/pages/etapa_07_despesas.py` | Roteiros TI-03, TI-05 e TI-11 |
| RF-42–45 | `database/saidas_operacionais.py`, `views/percurso_etapa2.py`, `database/models.py` | TU-01, TU-02, TU-03, TU-05, TU-06 |
| RF-46 | `database/saidas_operacionais.py` (`estimar_consumo`) | TU-04 |
| RF-47 | `faeg_app/reporting.py`, `faeg_app/pages/etapa_09_relatorios.py` (exportação) | Roteiro TI-09 |
| RF-48 | `database/rascunhos.py`, `faeg_app/rascunhos_ui.py`, `faeg_app/layout.py` | `tests/test_fluxo_operacional.py` |
| RF-49 | `views/percurso_etapa2.py`, `database/saidas_operacionais.py` | `tests/test_fluxo_operacional.py` e TI-06 |
| RF-50 | `views/parametros_veiculo.py`, `faeg_app/pages/etapa_11_cadastros.py` | Roteiro TI-08 |
| RF-41, RF-51 | `faeg_app/pages/etapa_08_fechamento.py`, `database/fechamento_ciclos.py` | TI-02/TI-03 |
| RF-52–53 | `database/identificacao_fretes.py`, `views/percurso_etapa2.py`, `faeg_app/pages/etapa_01_frota.py`, `faeg_app/pages/etapa_02_frete_documentos.py` e `faeg_app/core.py` | `tests/test_identificacao_e_vinculos.py` e TI-13/TI-14 |

**Referências:** regras operacionais em [`regras_negocio.md`](regras_negocio.md); cenários TU/TI descritos em [`plano_testes.md`](plano_testes.md).
