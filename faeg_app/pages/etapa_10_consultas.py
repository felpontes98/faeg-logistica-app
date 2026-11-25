"""Etapa 10 — Consulta de fretes e ciclos do Sistema Web FAEG."""
import pandas as pd
import streamlit as st

from database.fechamento_ciclos import consolidar_ciclos
from faeg_app.core import (
    OPCOES_ORIGEM_FRETE,
    OPCOES_SITUACAO_OPERACAO,
    _abrir_viagem_para_edicao,
    carregar_alertas_despesas_cruzadas,
    carregar_historico_atribuicoes_veiculo,
    carregar_todas_despesas_ciclo,
    carregar_todas_despesas_veiculo,
    carregar_todas_viagens_consulta,
    carregar_todos_abastecimentos,
    carregar_todos_recebimentos,
    exibir_indicadores,
    fmt_brl,
    render_navegacao_rodape,
)
from faeg_app.reporting import gerar_excel_base_completa


def render(ctx):
    MENU_ITENS = ctx.menu_itens
    clientes_db = ctx.clientes_db
    fornecedores_db = ctx.fornecedores_db
    locais_db = ctx.locais_db
    motoristas_db = ctx.motoristas_db
    veiculos_db = ctx.veiculos_db

    st.markdown(
        """
            <div class="tab-header-wrap">
                <div class="tab-title"><i class="fa-solid fa-magnifying-glass-chart"></i> Consultas Gerais e Histórico</div>
                <span class="tab-step-pill">Etapa 10 de 11</span>
            </div>
            """,
        unsafe_allow_html=True,
    )

    todas_viagens, desp_detalhadas = carregar_todas_viagens_consulta()

    f1, f2, f3, f4 = st.columns([2.6, 1.3, 1.3, 1.4])
    with f1:
        termo_busca = st.text_input(
            "BUSCA GERAL (CÓDIGO, CLIENTE, MOTORISTA, ROTA, CICLO, NF-E)",
            placeholder="Digite para filtrar instantaneamente...",
            key="consulta_busca",
        )
    with f2:
        filtro_tipo_vg = st.selectbox(
            "TIPO DE VIAGEM",
            ["Todos", "Individual", "Ciclo"],
            key="consulta_tipo",
        )
    with f3:
        filtro_situacao = st.selectbox(
            "SITUAÇÃO",
            ["Todas"] + OPCOES_SITUACAO_OPERACAO,
            key="consulta_situacao",
        )
    with f4:
        filtro_origem = st.selectbox(
            "ORIGEM DE FRETE",
            ["Todas"] + OPCOES_ORIGEM_FRETE,
            key="consulta_origem",
        )

    filtradas = todas_viagens
    if termo_busca.strip():
        tb = termo_busca.strip().lower()
        filtradas = [
            v
            for v in filtradas
            if tb in v["codigo_viagem"].lower()
            or tb in v["cliente"].lower()
            or tb in v["cliente_fantasia"].lower()
            or tb in v["motorista"].lower()
            or tb in v["rota"].lower()
            or tb in v["ciclo"].lower()
            or tb in v["nfe"].lower()
            or tb in v["id_frete"].lower()
        ]
    if filtro_tipo_vg != "Todos":
        filtradas = [v for v in filtradas if v["tipo_viagem"] == filtro_tipo_vg]
    if filtro_situacao != "Todas":
        filtradas = [v for v in filtradas if v["status"] == filtro_situacao]
    if filtro_origem != "Todas":
        filtradas = [v for v in filtradas if v["origem_frete"] == filtro_origem]

    tot_rec_f = sum(v["receita_base"] for v in filtradas)
    tot_desp_f = sum(v["total_despesas"] for v in filtradas)
    tot_res_f = sum(v["resultado_liquido"] for v in filtradas)
    possui_fretes_ciclo = any(v["tipo_viagem"] == "Ciclo" for v in filtradas)
    tot_recebido_f = sum(v["total_recebido"] for v in filtradas)
    saldos_consulta_validos = all(v["saldo_a_receber"] is not None for v in filtradas)
    tot_saldo_f = sum(v["saldo_a_receber"] or 0 for v in filtradas)

    exibir_indicadores(
        [
            ("Viagens Filtradas", len(filtradas)),
            ("Receita Consolidada", fmt_brl(tot_rec_f)),
            ("Despesas dos Fretes", fmt_brl(tot_desp_f)),
            ("Saldo antes dos custos compartilhados" if possui_fretes_ciclo
             else "Resultado Operacional Parcial", fmt_brl(tot_res_f), "destaque"),
        ],
        colunas=4,
    )
    exibir_indicadores(
        [
            ("Recebido de Fato (Fretes Filtrados)", fmt_brl(tot_recebido_f)),
            ("Saldo a Receber", fmt_brl(tot_saldo_f) if saldos_consulta_validos else "Conferir financeiro legado", "destaque"),
        ],
        colunas=2,
    )
    st.caption(
        "Os indicadores filtrados por frete não incluem despesas compartilhadas do ciclo. "
        "Para a visão operacional com esses custos, consulte o Fechamento por Ciclo na Etapa 9."
    )

    if not filtradas:
        st.info("Nenhuma viagem encontrada para os filtros aplicados.")
    else:
        df_cons = pd.DataFrame(
            [
                {
                    "Código": v["codigo_viagem"],
                    "Situação": v["status"],
                    "Tipo": v["tipo_viagem"],
                    "Ciclo": v["ciclo"],
                    "Cliente": v["cliente"],
                    "Motorista": v["motorista"],
                    "Origem": v["rota_origem"] or "-",
                    "Destino": v["rota_destino"] or "-",
                    "Receita": fmt_brl(v["receita_base"]),
                    "Recebido de Fato": fmt_brl(v["total_recebido"]),
                    "Saldo a Receber": fmt_brl(v["saldo_a_receber"]) if v["saldo_a_receber"] is not None else "Conferir legado",
                    "Despesas": fmt_brl(v["total_despesas"]),
                    "Saldo parcial (sem custos comuns)": fmt_brl(v["resultado_liquido"]),
                }
                for v in filtradas
            ]
        )
        st.dataframe(df_cons, use_container_width=True, hide_index=True)

        st.markdown('<div class="sec-subtitle">Abrir Viagem para Visualizar ou Editar</div>', unsafe_allow_html=True)
        ac1, ac2, ac3 = st.columns([2.6, 1.5, 1.5])
        opcoes_abrir = {
            v["id_viagem"]: f"{v['codigo_viagem']} — {v['cliente']} ({v['rota']})" for v in filtradas
        }
        with ac1:
            vg_escolhida_abrir = st.selectbox(
                "SELECIONE A VIAGEM",
                options=list(opcoes_abrir.keys()),
                format_func=lambda x: opcoes_abrir[x],
                key="sel_abrir_viagem_consulta",
            )
        with ac2:
            st.markdown('<div style="padding-top:1.35rem;"></div>', unsafe_allow_html=True)
            st.button(
                "✏️ Editar Viagem",
                key="btn_editar_viagem_consulta",
                use_container_width=True,
                on_click=_abrir_viagem_para_edicao,
                args=(vg_escolhida_abrir, "1. Frota FAEG"),
            )
        with ac3:
            st.markdown('<div style="padding-top:1.35rem;"></div>', unsafe_allow_html=True)
            xlsx_cons = gerar_excel_base_completa(
                todas_viagens, desp_detalhadas, motoristas_db, veiculos_db, clientes_db, locais_db, fornecedores_db,
                abastecimentos=carregar_todos_abastecimentos(),
                fechamentos_ciclos=consolidar_ciclos(todas_viagens, carregar_todas_despesas_ciclo()),
                recebimentos=carregar_todos_recebimentos(),
                despesas_ciclo=carregar_todas_despesas_ciclo(),
                despesas_veiculo=carregar_todas_despesas_veiculo(),
                atribuicoes_veiculo=carregar_historico_atribuicoes_veiculo(),
                alertas_despesas=carregar_alertas_despesas_cruzadas(),
            )
            st.download_button(
                "📥 Exportar Base Completa (.xlsx)",
                data=xlsx_cons,
                file_name="Base_Completa_FAEG.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        st.caption(
            "Os filtros acima alteram apenas a consulta na tela. "
            "A exportação é da base completa, com fretes, despesas e fechamentos "
            "do mesmo conjunto de registros, inclusive a aba Conferencia_Financeira."
        )

    render_navegacao_rodape(9, MENU_ITENS)
