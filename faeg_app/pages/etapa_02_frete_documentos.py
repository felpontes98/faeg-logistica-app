"""Etapa 2 da interface FAEG (corpo original, sem reescrever regras)."""
import streamlit as st

from faeg_app.core import (
    get_campo,
    on_km_componente_change,
    render_navegacao_rodape,
    sync_campo,
    to_float,
    to_int,
)


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
            "ID FRETE",
            value=get_campo("id_frete", ""),
            placeholder="Ex: FRT-102",
            help="Identificador próprio e único do serviço, independente do ID Ciclo. Não reutilize o mesmo ID em outro frete.",
            key="w_id_frete",
            on_change=sync_campo,
            args=("w_id_frete", "id_frete"),
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
    st.markdown('<div class="sec-subtitle">KM X ROTA PLANEJADO</div>', unsafe_allow_html=True)
    st.caption(
        "O KM deste frete é uma referência comercial. Para operações com várias saídas, "
        "registre o percurso físico e seus odômetros na Etapa 8 — Saídas Operacionais. "
        "Quando houver saídas cadastradas, o sistema NÃO somará KM de diferentes fretes. "
        "Os campos antigos de saída e retorno são preservados para conferência."
    )
    km1, km2, km3 = st.columns(3)
    with km1:
        st.number_input(
            "KM DE SAÍDA E DESLOCAMENTO ENTRE COLETAS",
            min_value=0.0,
            step=1.0,
            format="%.2f",
            value=to_float(get_campo("km_saida_entre_coletas", 0.0)),
            key="w_km_saida_entre_coletas",
            on_change=on_km_componente_change,
            args=("w_km_saida_entre_coletas", "km_saida_entre_coletas"),
            help="KM adicionais até a primeira coleta e entre coletas, excluindo os trechos já previstos em cada frete.",
        )
    with km2:
        st.number_input(
            "KM INDIVIDUAL / CICLO",
            min_value=0.0,
            step=1.0,
            format="%.2f",
            help=(
                "Campo manual: informe o KM previsto deste ID Frete. "
                "Se a viagem fizer parte de um ciclo, a Etapa 8 somará o KM "
                "dos fretes do mesmo ID interno do ciclo, sem repetir este trecho."
            ),
            value=to_float(get_campo("km_rota", 0.0)),
            key="w_km_rota",
            on_change=sync_campo,
            args=("w_km_rota", "km_rota"),
        )
    with km3:
        st.number_input(
            "KM OPERACIONAL DE RETORNO",
            min_value=0.0,
            step=1.0,
            format="%.2f",
            value=to_float(get_campo("km_retorno_operacional", 0.0)),
            key="w_km_retorno_operacional",
            on_change=on_km_componente_change,
            args=("w_km_retorno_operacional", "km_retorno_operacional"),
            help="KM adicional de retorno após a última entrega, excluindo trechos já associados a fretes.",
        )
    if not get_campo("km_componentes_discriminados", True) and to_float(get_campo("km_deslocamentos", 0.0)) > 0:
        st.info(
            "Este ciclo tem KM de deslocamentos registrado na versão anterior, sem separar "
            "saída e retorno. O total antigo será preservado até você preencher os dois "
            "campos novos; confira a distribuição antes de salvar."
        )

    st.markdown('<div class="sec-subtitle">Odômetros da Operação</div>', unsafe_allow_html=True)
    st.caption(
        "Registre as leituras reais de início e fim da operação. Na Etapa 8, os valores "
        "serão exibidos para calcular o KM real. O odômetro de cada abastecimento "
        "continua no lançamento único da Etapa 7."
    )
    od1, od2 = st.columns(2)
    with od1:
        st.number_input(
            "KM ODÔMETRO INICIAL",
            min_value=0,
            step=1,
            value=to_int(get_campo("odo_ini", 0)),
            key="w_odo_ini",
            on_change=sync_campo,
            args=("w_odo_ini", "odo_ini"),
        )
    with od2:
        st.number_input(
            "KM ODÔMETRO FINAL",
            min_value=0,
            step=1,
            value=to_int(get_campo("odo_fin", 0)),
            key="w_odo_fin",
            on_change=sync_campo,
            args=("w_odo_fin", "odo_fin"),
        )

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
