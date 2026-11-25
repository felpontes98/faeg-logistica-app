"""Barra lateral e cabeçalho institucional: renderização original isolada."""
from html import escape

import streamlit as st

from faeg_app.core import (
    calcular_proximo_codigo_viagem, carregar_recebimentos_viagem,
    formatar_rota_exibicao, get_campo, salvar_viagem_completa,
    situacao_financeira_por_recebimentos, _iniciar_nova_viagem,
)
from faeg_app.reporting import carregar_logo_base64


def render_sidebar(ctx):
    """Retorna aba ativa, próximo código e a lista de etapas."""
    viagens_db = ctx.viagens_db
    viagem_sel_id = ctx.viagem_sel_id
    with st.sidebar:
        logo_b64 = carregar_logo_base64()
        if logo_b64:
            icone_marca_html = f'<img src="{logo_b64}" class="sidebar-logo-img" alt="FAEG" />'
        else:
            icone_marca_html = '<div class="sidebar-monogram-fallback">FAEG</div>'

        st.markdown(
            f"""
        <div class="sidebar-brand">
            {icone_marca_html}
        </div>
        """,
            unsafe_allow_html=True,
        )

        prox_cod_sidebar = calcular_proximo_codigo_viagem(viagens_db)
        cod_ativo_sidebar = get_campo("id_viagem_label", prox_cod_sidebar)
        tag_modo_sidebar = "Criando Nova Viagem" if viagem_sel_id == 0 else "Editando Viagem Salva"

        st.markdown(
            f"""
        <div class="sidebar-active-trip-card">
            <div class="sidebar-active-trip-tag">{tag_modo_sidebar}</div>
            <div class="sidebar-active-trip-code">{cod_ativo_sidebar}</div>
        </div>
        """,
            unsafe_allow_html=True,
        )

        if viagem_sel_id != 0:
            st.button(
                "➕ Iniciar Nova Viagem",
                type="secondary",
                use_container_width=True,
                on_click=_iniciar_nova_viagem,
            )

        st.markdown(
            "<hr style='margin: 0.7rem 0 0.6rem 0; border-color: rgba(171, 206, 225, 0.2);'>",
            unsafe_allow_html=True,
        )

        MENU_ITENS = [
            "1. Frota FAEG",
            "2. Frete e Docs",
            "3. Cliente",
            "4. Negociação / Pgto",
            "5. Coleta (Origem)",
            "6. Entrega (Destino)",
            "7. Despesas de Viagem",
            "8. Fechamento Final",
            "9. Relatórios / Exportar",
            "10. Consultas Gerais",
            "11. Cadastros Gerais",
        ]
        aba_ativa = st.radio(
            "Menu Operacional",
            MENU_ITENS,
            key="menu_operacional_radio",
            label_visibility="collapsed",
        )

        st.markdown(
            "<hr style='margin: 0.9rem 0 0.9rem 0; border-color: rgba(171, 206, 225, 0.2);'>",
            unsafe_allow_html=True,
        )

        from faeg_app.rascunhos_ui import controles_rascunho
        controles_rascunho(viagem_sel_id)

        if st.button("Salvar Viagem", type="primary", use_container_width=True):
            salvar_viagem_completa(viagem_sel_id, viagens_db)

    return aba_ativa, prox_cod_sidebar, MENU_ITENS


def render_top_context(ctx):
    """Apresenta dados do frete; mantém rótulos e regras financeiras originais."""
    clientes_db = ctx.clientes_db
    motoristas_db = ctx.motoristas_db
    viagem_sel_id = ctx.viagem_sel_id
    prox_cod_sidebar = ctx.prox_cod_sidebar
    cli_obj_ctx = next((c for c in clientes_db if c["id_cliente"] == get_campo("cli_id", 0)), None)
    cli_nome_ctx = (
        f"{cli_obj_ctx['razao_social']}"
        + (f" ({cli_obj_ctx['nome_fantasia']})" if cli_obj_ctx.get("nome_fantasia") else "")
        if cli_obj_ctx
        else "Não selecionado"
    )
    mot_nome_ctx = next(
        (m["nome_completo"] for m in motoristas_db if m["id_motorista"] == get_campo("mot_id", 0)),
        "Não selecionado",
    )
    rota_ctx = (
        formatar_rota_exibicao(get_campo("rota_origem", ""), get_campo("rota_destino", ""))
        or "Rota não definida"
    )
    status_ctx = get_campo("status_viagem", "Aguardando Adiantamento")
    id_label_ctx = get_campo("id_viagem_label", prox_cod_sidebar)
    status_financeiro_ctx = None
    if viagem_sel_id != 0:
        recebimentos_ctx = carregar_recebimentos_viagem(viagem_sel_id)
        total_recebido_ctx = sum(r["valor_recebido"] for r in recebimentos_ctx if not r["cancelado"])
        status_financeiro_ctx = situacao_financeira_por_recebimentos(
            get_campo("valor_negociado", 0.0), total_recebido_ctx
        )

    if status_financeiro_ctx:
        texto_principal_ctx = status_financeiro_ctx
        classe_financeira_ctx = " ctx-badge--paid" if status_financeiro_ctx == "Pagamento Quitado" else ""
        # A Etapa 8 mantém seu status operacional. Se o rótulo antigo conflita
        # com pagamentos confirmados, pedir revisão sem alterar dados salvos.
        if status_ctx in {"Aguardando Adiantamento", "Adiantamento Recebido"}:
            texto_operacional_ctx = "Situação operacional: conferir na Etapa 8"
        else:
            texto_operacional_ctx = f"Operação: {status_ctx}"
    else:
        texto_principal_ctx = status_ctx
        classe_financeira_ctx = ""
        texto_operacional_ctx = "Situação da operação · Etapa 8"

    st.markdown(
        f"""
    <div class="top-context-bar">
        <div class="ctx-item">
            <span class="ctx-label">Código da Viagem</span>
            <span class="ctx-val">{escape(str(id_label_ctx))}</span>
        </div>
        <div class="ctx-item">
            <span class="ctx-label">Cliente Contratante</span>
            <span class="ctx-val">{escape(str(cli_nome_ctx))}</span>
        </div>
        <div class="ctx-item">
            <span class="ctx-label">Motorista Responsável</span>
            <span class="ctx-val">{escape(str(mot_nome_ctx))}</span>
        </div>
        <div class="ctx-item">
            <span class="ctx-label">Trecho / Rota</span>
            <span class="ctx-val">{escape(str(rota_ctx))}</span>
        </div>
        <div class="ctx-status-group">
            <span class="ctx-badge{classe_financeira_ctx}">{escape(texto_principal_ctx)}</span>
            <span class="ctx-operation-note">{escape(texto_operacional_ctx)}</span>
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    ctx.cli_nome_ctx = cli_nome_ctx
    ctx.id_label_ctx = id_label_ctx
    ctx.mot_nome_ctx = mot_nome_ctx
    ctx.status_ctx = status_ctx
