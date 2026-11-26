"""Etapa 2 — Fretes, carga, documentos e saídas operacionais do Sistema Web FAEG."""
import streamlit as st

from faeg_app.core import (
    get_campo,
    render_navegacao_rodape,
    sync_campo,
    to_float,
    to_int,
)
from database.identificacao_fretes import previsualizar_frete


def render(ctx):
    MENU_ITENS = ctx.menu_itens

    st.markdown(
        """
            <div class="tab-header-wrap">
                <div class="tab-title"><i class="fa-solid fa-file-invoice"></i> Frete, Carga e Documentos</div>
                <span class="tab-step-pill">Etapa 2 de 11</span>
            </div>
            """,
        unsafe_allow_html=True,
    )

    f1, f2, f3, f4 = st.columns([1.1, 1.3, 1.6, 1.6])
    with f1:
        st.text_input(
            "ID FRETE (AUTOMÁTICO)",
            value=get_campo("id_frete", "") or previsualizar_frete(get_campo("id_viagem_label", "")),
            help="Sequência global FV sem ano. No primeiro salvamento o código é reservado no banco; históricos permanecem iguais.",
            disabled=True,
            key="w_id_frete",
        )
    with f2:
        tipos_frete_ops = ["Dedicado", "Complemento", "Fracionado", "Retorno", "Transferência"]
        tf_atual = get_campo("tipo_frete", "Dedicado")
        st.selectbox(
            "TIPO DE FRETE",
            tipos_frete_ops,
            index=tipos_frete_ops.index(tf_atual) if tf_atual in tipos_frete_ops else 0,
            key="w_tipo_frete",
            on_change=sync_campo,
            args=("w_tipo_frete", "tipo_frete"),
        )
    with f3:
        st.text_input(
            "ORIGEM (CIDADE / UF)",
            value=get_campo("rota_origem", ""),
            placeholder="Ex: Suzano/SP",
            key="w_rota_origem",
            on_change=sync_campo,
            args=("w_rota_origem", "rota_origem"),
        )
    with f4:
        st.text_input(
            "DESTINO (CIDADE / UF)",
            value=get_campo("rota_destino", ""),
            placeholder="Ex: Rio de Janeiro/RJ",
            key="w_rota_destino",
            on_change=sync_campo,
            args=("w_rota_destino", "rota_destino"),
        )
    # A operação física é lançada uma só vez, tanto no Individual como no Ciclo.
    from views.percurso_etapa2 import render_percurso
    render_percurso(ctx)

    # Informações históricas permanecem disponíveis sem pedir novo preenchimento.
    if any(to_float(get_campo(c, 0)) for c in
           ("km_rota", "km_saida_entre_coletas", "km_retorno_operacional", "odo_ini", "odo_fin")):
        with st.expander("Consultar KM e odômetros antigos do frete", expanded=False):
            st.caption("Registros anteriores à organização por saídas. Não são somados aos novos percursos.")
            st.write({
                "KM rota (histórico)": get_campo("km_rota", 0),
                "KM saída / coletas (histórico)": get_campo("km_saida_entre_coletas", 0),
                "KM retorno (histórico)": get_campo("km_retorno_operacional", 0),
                "Odômetro inicial (histórico)": get_campo("odo_ini", 0),
                "Odômetro final (histórico)": get_campo("odo_fin", 0),
            })

    st.markdown('<div class="sec-subtitle">Detalhes da Carga</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([2.4, 1.0, 1.0, 1.2])
    with c1:
        st.text_input(
            "TIPO DE MATERIAL",
            value=get_campo("tipo_material", ""),
            placeholder="Ex: Bobinas, Paletes, Peças",
            key="w_tipo_material",
            on_change=sync_campo,
            args=("w_tipo_material", "tipo_material"),
        )
    with c2:
        st.number_input(
            "QT VOLUMES",
            min_value=0,
            step=1,
            value=to_int(get_campo("qt_volumes", 0)),
            key="w_qt_volumes",
            on_change=sync_campo,
            args=("w_qt_volumes", "qt_volumes"),
        )
    with c3:
        st.number_input(
            "VOLUME (M³)",
            min_value=0.0,
            step=1.0,
            format="%.2f",
            value=to_float(get_campo("volume_m3", 0.0)),
            key="w_volume_m3",
            on_change=sync_campo,
            args=("w_volume_m3", "volume_m3"),
        )
    with c4:
        st.number_input(
            "PESO BRUTO (KG)",
            min_value=0.0,
            step=100.0,
            format="%.2f",
            value=to_float(get_campo("peso_kg", 0.0)),
            key="w_peso_kg",
            on_change=sync_campo,
            args=("w_peso_kg", "peso_kg"),
        )

    st.markdown('<div class="sec-subtitle">Documentos Fiscais</div>', unsafe_allow_html=True)
    d1, d2, d3, d4 = st.columns(4)
    with d1:
        st.text_input(
            "NF-E / CARGA",
            value=get_campo("nfe", ""),
            placeholder="Número da NF-e",
            key="w_nfe",
            on_change=sync_campo,
            args=("w_nfe", "nfe"),
        )
    with d2:
        st.text_input(
            "CT-E (CONHECIMENTO)",
            value=get_campo("cte", ""),
            placeholder="Número do CT-e",
            key="w_cte",
            on_change=sync_campo,
            args=("w_cte", "cte"),
        )
    with d3:
        st.text_input(
            "MDF-E (MANIFESTO)",
            value=get_campo("mdfe", ""),
            placeholder="Número do MDF-e",
            key="w_mdfe",
            on_change=sync_campo,
            args=("w_mdfe", "mdfe"),
        )
    with d4:
        st.text_input(
            "CIOT",
            value=get_campo("ciot", ""),
            placeholder="Código CIOT",
            key="w_ciot",
            on_change=sync_campo,
            args=("w_ciot", "ciot"),
        )

    render_navegacao_rodape(1, MENU_ITENS)
