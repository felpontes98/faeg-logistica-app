"""Etapa 6 — Dados e horários de entrega do Sistema Web FAEG."""
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
                <div class="tab-title"><i class="fa-solid fa-flag-checkered"></i> Local de Entrega (Destino)</div>
                <span class="tab-step-pill">Etapa 6 de 11</span>
            </div>
            """,
        unsafe_allow_html=True,
    )

    cli_map_local = {c["id_cliente"]: c for c in clientes_db}
    loc_ops = {0: "Selecione um local cadastrado..."}
    for l in locais_db:
        loc_ops[l["id_local"]] = formatar_rotulo_local(l, cli_map_local)

    ent_atual = get_campo("ent_id", 0)
    idx_ent = list(loc_ops.keys()).index(ent_atual) if ent_atual in loc_ops else 0

    ent_sel = st.selectbox(
        "BASE / EMPRESA CADASTRADA (ENTREGA) *",
        options=list(loc_ops.keys()),
        index=idx_ent,
        format_func=lambda x: loc_ops[x],
        key="w_ent_id",
        on_change=on_local_select_change,
        args=("w_ent_id", "ent_id", locais_db),
    )
    ent_obj = next((l for l in locais_db if l["id_local"] == ent_sel), None)

    le1, le2, le3, le4 = st.columns([0.9, 2.3, 1.3, 0.55])
    le1.text_input("CEP", value=(ent_obj.get("cep") or "") if ent_obj else "", disabled=True, key=f"p_ent_cep_{ent_sel}")
    le2.text_input(
        "ENDEREÇO COMPLETO",
        value=(ent_obj.get("endereco_completo") or "") if ent_obj else "",
        disabled=True,
        key=f"p_ent_end_{ent_sel}",
    )
    le3.text_input(
        "CIDADE",
        value=(ent_obj.get("cidade") or "") if ent_obj else "",
        disabled=True,
        key=f"p_ent_cid_{ent_sel}",
    )
    le4.text_input("UF", value=(ent_obj.get("uf") or "") if ent_obj else "", disabled=True, key=f"p_ent_uf_{ent_sel}")

    if ent_obj and (ent_obj.get("contato_portaria") or ent_obj.get("restricao_horario")):
        st.markdown(
            f"""
                <div class="cliente-coleta-banner">
                    <strong>Portaria / Contato:</strong> {ent_obj.get('contato_portaria') or '-'}
                    &nbsp;|&nbsp; <strong>Restrição de Horário:</strong> {ent_obj.get('restricao_horario') or 'Não há restrição'}
                </div>
                """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="sec-subtitle">Horários da Operação de Entrega</div>', unsafe_allow_html=True)
    he1, he2, he3, _ = st.columns([1.15, 1.0, 1.0, 1.3])
    with he1:
        st.date_input(
            "DATA ENTREGA",
            value=get_campo("data_entrega", date.today()),
            format="DD/MM/YYYY",
            key="w_data_entrega",
            on_change=sync_campo,
            args=("w_data_entrega", "data_entrega"),
        )
    with he2:
        st.time_input(
            "HORA PLANEJADA",
            value=get_campo("hora_plan_ent"),
            key="w_hora_plan_ent",
            on_change=sync_campo,
            args=("w_hora_plan_ent", "hora_plan_ent"),
        )
    with he3:
        st.time_input(
            "HORA REAL",
            value=get_campo("hora_real_ent"),
            key="w_hora_real_ent",
            on_change=sync_campo,
            args=("w_hora_real_ent", "hora_real_ent"),
        )

    render_navegacao_rodape(5, MENU_ITENS)
