"""Etapa 1 da interface FAEG (corpo original, sem reescrever regras)."""
import streamlit as st

from database.importador_planilha import preparar_previa_importacao_faeg
from datetime import date
from faeg_app.core import (
    fmt_brl,
    get_campo,
    on_ciclo_nome_change,
    on_tipo_viagem_change,
    render_navegacao_rodape,
    sync_campo,
)


def render(ctx):
    MENU_ITENS = ctx.menu_itens
    motoristas_db = ctx.motoristas_db
    prox_cod_sidebar = ctx.prox_cod_sidebar
    veiculos_db = ctx.veiculos_db

    st.markdown(
        """
            <div class="tab-header-wrap">
                <div class="tab-title"><i class="fa-solid fa-truck"></i> Informações FAEG</div>
                <span class="tab-step-pill">Etapa 1 de 11</span>
            </div>
            """,
        unsafe_allow_html=True,
    )

    # Prévia de leitura sem gravação. A importação depende da correção dos ciclos.
    with st.expander("📥 Conferir Planilha de Controle de Fretes (.xlsx)", expanded=False):
        st.caption(
            "Selecione a planilha FAEG para conferir fretes, ciclos e linhas de fechamento. "
            "Esta análise não altera o banco de dados."
        )
        up_file = st.file_uploader(
            "Selecione o arquivo Excel (.xlsx)",
            type=["xlsx"],
            key="uploader_planilha_faeg",
        )
        if up_file is not None:
            file_bytes = up_file.getvalue()
            analise = preparar_previa_importacao_faeg(file_bytes)
            if analise.get("erro"):
                st.error(analise["erro"])
            else:
                resumo_pl = analise["resumo"]
                kp1, kp2, kp3, kp4 = st.columns(4)
                kp1.metric("Fretes Identificados", resumo_pl["total_fretes"])
                kp2.metric("Ciclos Distintos", resumo_pl["total_ciclos"])
                kp3.metric("Linhas de Fechamento", resumo_pl["total_fechamentos"])
                kp4.metric("Receita dos Fretes", fmt_brl(resumo_pl["receita_fretes"]))

                st.info(
                    f"Ciclos com mais de um frete: {resumo_pl['ciclos_multifrete']}. "
                    f"Ciclos com clientes diferentes: {resumo_pl['ciclos_multicliente']}. "
                    "O cliente e os valores são próprios de cada frete."
                )
                st.caption(
                    "Despesas identificadas nas linhas dos fretes: "
                    f"{fmt_brl(resumo_pl['despesas_fretes'])}. "
                    "Os totais não incluem a conciliação de despesas dos fechamentos."
                )

                if analise.get("preview_df") is not None and not analise["preview_df"].empty:
                    st.dataframe(analise["preview_df"], use_container_width=True, hide_index=True)

                with st.expander("🔎 Conferência dos fechamentos e possíveis divergências", expanded=True):
                    st.caption(
                        f"Fechamentos associados a fretes: {resumo_pl['fechamentos_de_fretes']} | "
                        f"Possíveis totais gerais: {resumo_pl['possiveis_resumos_gerais']} | "
                        f"IDs de ciclo ausentes: {resumo_pl['ids_fechamento_ausentes']} | "
                        f"IDs divergentes: {resumo_pl['ids_fechamento_divergentes']} | "
                        f"Valores divergentes: {resumo_pl['valores_fechamento_divergentes']}"
                    )
                    fechamento_df = analise.get("preview_fechamentos_df")
                    if fechamento_df is not None and not fechamento_df.empty:
                        st.dataframe(fechamento_df, use_container_width=True, hide_index=True)
                    if resumo_pl["fretes_sem_fechamento"]:
                        st.info(
                            f"Fretes sem linha posterior de fechamento: "
                            f"{resumo_pl['fretes_sem_fechamento']}. "
                            "Podem ser operações ainda em andamento."
                        )

                for aviso in analise.get("avisos", []):
                    st.warning(aviso)

                st.button(
                    "Confirmar Importação no Banco (temporariamente indisponível)",
                    key="btn_confirmar_import_planilha",
                    use_container_width=True,
                    disabled=True,
                    help="A rotina de gravação aguarda a correção dos vínculos de fretes e ciclos.",
                )

    c_id, c_tipo_vg, c_ciclo, c_data = st.columns([1.2, 1.3, 1.8, 1.2])
    with c_id:
        st.text_input(
            "CÓDIGO DA VIAGEM (ÚNICO) *",
            value=get_campo("id_viagem_label", prox_cod_sidebar),
            placeholder=f"Ex: {prox_cod_sidebar}",
            key="w_id_viagem_label",
            on_change=sync_campo,
            args=("w_id_viagem_label", "id_viagem_label"),
        )
    with c_tipo_vg:
        tipos_vg = ["Individual", "Ciclo"]
        tv_atual = get_campo("tipo_viagem", "Individual")
        st.selectbox(
            "TIPO DE VIAGEM",
            tipos_vg,
            index=tipos_vg.index(tv_atual) if tv_atual in tipos_vg else 0,
            key="w_tipo_viagem",
            on_change=on_tipo_viagem_change,
        )
    with c_ciclo:
        eh_ciclo = get_campo("tipo_viagem", "Individual") == "Ciclo"
        st.text_input(
            "Nº DO CICLO OPERACIONAL",
            value=get_campo("ciclo_nome", "") if eh_ciclo else "",
            placeholder="Ex: CICLO-01" if eh_ciclo else "Bloqueado (Viagem Individual)",
            disabled=not eh_ciclo,
            key="w_ciclo_nome",
            on_change=on_ciclo_nome_change,
        )
    with c_data:
        st.date_input(
            "DATA OPERAÇÃO",
            value=get_campo("data_op", date.today()),
            format="DD/MM/YYYY",
            key="w_data_op",
            on_change=sync_campo,
            args=("w_data_op", "data_op"),
        )

    st.markdown('<div class="sec-subtitle">Dados do Motorista</div>', unsafe_allow_html=True)
    mot_ops = {0: "Selecione um motorista..."}
    for m in motoristas_db:
        mot_ops[m["id_motorista"]] = m["nome_completo"]

    mot_atual = get_campo("mot_id", 0)
    idx_mot = list(mot_ops.keys()).index(mot_atual) if mot_atual in mot_ops else 0

    m1, m2, m3 = st.columns([2.4, 1.3, 0.9])
    with m1:
        mot_sel = st.selectbox(
            "NOME DO MOTORISTA *",
            options=list(mot_ops.keys()),
            index=idx_mot,
            format_func=lambda x: mot_ops[x],
            key="w_mot_id",
            on_change=sync_campo,
            args=("w_mot_id", "mot_id"),
        )
    mot_obj = next((m for m in motoristas_db if m["id_motorista"] == mot_sel), None)
    with m2:
        st.text_input(
            "CNH (AUTOMÁTICO)",
            value=mot_obj["cnh_numero"] if mot_obj else "",
            disabled=True,
            key=f"prev_cnh_{mot_sel}",
        )
    with m3:
        st.text_input(
            "CATEGORIA",
            value=mot_obj["cnh_categoria"] if mot_obj else "",
            disabled=True,
            key=f"prev_cat_{mot_sel}",
        )

    st.markdown('<div class="sec-subtitle">Dados do Veículo</div>', unsafe_allow_html=True)
    vei_ops = {0: "Selecione o veículo..."}
    for v in veiculos_db:
        vei_ops[v["id_veiculo"]] = f"{v['descricao_marca']} ({v['placa']})"

    vei_atual = get_campo("vei_id", 0)
    idx_vei = list(vei_ops.keys()).index(vei_atual) if vei_atual in vei_ops else 0

    v1, v2, v3 = st.columns([2.4, 1.1, 1.1])
    with v1:
        vei_sel = st.selectbox(
            "VEÍCULO / CARRO *",
            options=list(vei_ops.keys()),
            index=idx_vei,
            format_func=lambda x: vei_ops[x],
            key="w_vei_id",
            on_change=sync_campo,
            args=("w_vei_id", "vei_id"),
        )
    vei_obj = next((v for v in veiculos_db if v["id_veiculo"] == vei_sel), None)
    with v2:
        st.text_input(
            "PLACA (AUTOMÁTICO)",
            value=vei_obj["placa"] if vei_obj else "",
            disabled=True,
            key=f"prev_placa_{vei_sel}",
        )
    with v3:
        st.text_input(
            "TIPO (AUTOMÁTICO)",
            value=vei_obj["tipo_veiculo"] if vei_obj else "",
            disabled=True,
            key=f"prev_tipo_{vei_sel}",
        )

    render_navegacao_rodape(0, MENU_ITENS)
