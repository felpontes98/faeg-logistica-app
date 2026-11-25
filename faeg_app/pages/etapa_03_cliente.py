"""Etapa 3 — Dados do cliente contratante do Sistema Web FAEG."""
import streamlit as st

from faeg_app.core import (
    formatar_rotulo_cliente,
    get_campo,
    on_cliente_select_change,
    render_navegacao_rodape,
)


def render(ctx):
    MENU_ITENS = ctx.menu_itens
    clientes_db = ctx.clientes_db
    locais_db = ctx.locais_db

    st.markdown(
        """
            <div class="tab-header-wrap">
                <div class="tab-title"><i class="fa-solid fa-building"></i> Cliente Contratante</div>
                <span class="tab-step-pill">Etapa 3 de 11</span>
            </div>
            """,
        unsafe_allow_html=True,
    )

    cli_ops = {0: "Selecione um cliente..."}
    for c in clientes_db:
        cli_ops[c["id_cliente"]] = formatar_rotulo_cliente(c)

    cli_atual = get_campo("cli_id", 0)
    idx_cli = list(cli_ops.keys()).index(cli_atual) if cli_atual in cli_ops else 0

    cli_sel = st.selectbox(
        "EMPRESA CLIENTE (RAZÃO SOCIAL / NOME FANTASIA) *",
        options=list(cli_ops.keys()),
        index=idx_cli,
        format_func=lambda x: cli_ops[x],
        key="w_cli_id",
        on_change=on_cliente_select_change,
        args=(locais_db,),
    )
    cli_obj = next((c for c in clientes_db if c["id_cliente"] == cli_sel), None)

    # Mesmo desenho das Etapas 5 e 6: cada dado cadastral em seu campo.
    ce1, ce2, ce3, ce4 = st.columns([0.9, 2.3, 1.3, 0.55])
    ce1.text_input("CEP", value=(cli_obj.get("cep") or "") if cli_obj else "", disabled=True, key=f"p_cli_cep_{cli_sel}")
    ce2.text_input(
        "ENDEREÇO COMPLETO",
        value=(cli_obj.get("endereco_completo") or "") if cli_obj else "",
        disabled=True,
        key=f"p_cli_end_{cli_sel}",
    )
    ce3.text_input(
        "CIDADE",
        value=(cli_obj.get("cidade") or "") if cli_obj else "",
        disabled=True,
        key=f"p_cli_cid_{cli_sel}",
    )
    ce4.text_input("UF", value=(cli_obj.get("uf") or "") if cli_obj else "", disabled=True, key=f"p_cli_uf_{cli_sel}")

    cc1, cc2, cc3 = st.columns([1.2, 1.0, 1.6])
    cc1.text_input(
        "RESPONSÁVEL",
        value=(cli_obj.get("responsavel_comercial") or "") if cli_obj else "",
        disabled=True,
        key=f"prev_cli_resp_{cli_sel}",
    )
    cc2.text_input(
        "TELEFONE / CONTATO",
        value=(cli_obj.get("telefone_comercial") or "") if cli_obj else "",
        disabled=True,
        key=f"prev_cli_tel_{cli_sel}",
    )
    cc3.text_input(
        "E-MAIL FINANCEIRO",
        value=(cli_obj.get("email_financeiro") or "") if cli_obj else "",
        disabled=True,
        key=f"prev_cli_email_{cli_sel}",
    )

    render_navegacao_rodape(2, MENU_ITENS)
