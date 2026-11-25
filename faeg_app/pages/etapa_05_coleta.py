"""Etapa 5 — Dados e horários de coleta do Sistema Web FAEG."""
from html import escape

import streamlit as st

from datetime import date
from faeg_app.core import (
    formatar_rotulo_local,
    get_campo,
    on_local_select_change,
    render_navegacao_rodape,
    sync_campo,
)


def render(ctx):
    MENU_ITENS = ctx.menu_itens
    clientes_db = ctx.clientes_db
    locais_db = ctx.locais_db

    st.markdown(
        """
            <div class="tab-header-wrap">
                <div class="tab-title"><i class="fa-solid fa-location-arrow"></i> Local de Coleta (Origem)</div>
                <span class="tab-step-pill">Etapa 5 de 11</span>
            </div>
            """,
        unsafe_allow_html=True,
    )

    cli_map_local = {c["id_cliente"]: c for c in clientes_db}
    loc_ops = {0: "Selecione um local cadastrado..."}
    for l in locais_db:
        loc_ops[l["id_local"]] = formatar_rotulo_local(l, cli_map_local)

    col_atual = get_campo("col_id", 0)
    idx_col = list(loc_ops.keys()).index(col_atual) if col_atual in loc_ops else 0

    col_sel = st.selectbox(
        "BASE / EMPRESA CADASTRADA (COLETA) *",
        options=list(loc_ops.keys()),
        index=idx_col,
        format_func=lambda x: loc_ops[x],
        key="w_col_id",
        on_change=on_local_select_change,
        args=("w_col_id", "col_id", locais_db),
    )
    col_obj = next((l for l in locais_db if l["id_local"] == col_sel), None)

    lc1, lc2, lc3, lc4 = st.columns([0.9, 2.3, 1.3, 0.55])
    lc1.text_input("CEP", value=(col_obj.get("cep") or "") if col_obj else "", disabled=True, key=f"p_col_cep_{col_sel}")
    lc2.text_input(
        "ENDEREÇO COMPLETO",
        value=(col_obj.get("endereco_completo") or "") if col_obj else "",
        disabled=True,
        key=f"p_col_end_{col_sel}",
    )
    lc3.text_input(
        "CIDADE",
        value=(col_obj.get("cidade") or "") if col_obj else "",
        disabled=True,
        key=f"p_col_cid_{col_sel}",
    )
    lc4.text_input("UF", value=(col_obj.get("uf") or "") if col_obj else "", disabled=True, key=f"p_col_uf_{col_sel}")

    if col_obj and (col_obj.get("contato_portaria") or col_obj.get("restricao_horario")):
        st.markdown(
            f"""
                <div class="cliente-coleta-banner">
                    <strong>Portaria / Contato:</strong> {escape(str(col_obj.get('contato_portaria') or '-'))}
                    &nbsp;|&nbsp; <strong>Restrição de Horário:</strong> {escape(str(col_obj.get('restricao_horario') or 'Não há restrição'))}
                </div>
                """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="sec-subtitle">Horários da Operação de Coleta</div>', unsafe_allow_html=True)
    hc1, hc2, hc3, _ = st.columns([1.15, 1.0, 1.0, 1.3])
    with hc1:
        st.date_input(
            "DATA COLETA",
            value=get_campo("data_coleta", date.today()),
            format="DD/MM/YYYY",
            key="w_data_coleta",
            on_change=sync_campo,
            args=("w_data_coleta", "data_coleta"),
        )
    with hc2:
        st.time_input(
            "HORA PLANEJADA",
            value=get_campo("hora_plan_col"),
            key="w_hora_plan_col",
            on_change=sync_campo,
            args=("w_hora_plan_col", "hora_plan_col"),
        )
    with hc3:
        st.time_input(
            "HORA REAL",
            value=get_campo("hora_real_col"),
            key="w_hora_real_col",
            on_change=sync_campo,
            args=("w_hora_real_col", "hora_real_col"),
        )

    render_navegacao_rodape(4, MENU_ITENS)
