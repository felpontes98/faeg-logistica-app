"""Etapa 9 da interface FAEG (corpo original, sem reescrever regras)."""
import pandas as pd
import streamlit as st

from database.connection import SessionLocal
from database.fechamento_ciclos import consolidar_ciclos, reconciliar_resultado_gerencial
from database.saidas_operacionais import consultar_todas_saidas, resumo_saidas
from datetime import date
from faeg_app.core import (
    OPCOES_SITUACAO_OPERACAO,
    carregar_alertas_despesas_cruzadas,
    carregar_despesas_viagem,
    carregar_historico_atribuicoes_veiculo,
    carregar_recebimentos_viagem,
    carregar_todas_despesas_ciclo,
    carregar_todas_despesas_veiculo,
    carregar_todas_viagens_consulta,
    carregar_todos_abastecimentos,
    carregar_todos_recebimentos,
    exibir_indicadores,
    fmt_brl,
    fmt_km,
    get_campo,
    render_navegacao_rodape,
    to_float,
    to_int,
)
from faeg_app.reporting import gerar_excel_base_completa, gerar_pdf_relatorio, gerar_pdf_relatorio_consolidado


def render(ctx):
    MENU_ITENS = ctx.menu_itens
    cli_nome_ctx = ctx.cli_nome_ctx
    clientes_db = ctx.clientes_db
    fornecedores_db = ctx.fornecedores_db
    id_label_ctx = ctx.id_label_ctx
    locais_db = ctx.locais_db
    mot_nome_ctx = ctx.mot_nome_ctx
    motoristas_db = ctx.motoristas_db
    status_ctx = ctx.status_ctx
    veiculos_db = ctx.veiculos_db
    viagem_sel_id = ctx.viagem_sel_id

    st.markdown(
        """
            <div class="tab-header-wrap">
                <div class="tab-title"><i class="fa-solid fa-chart-pie"></i> Relatórios e Exportação</div>
                <span class="tab-step-pill">Etapa 9 de 11</span>
            </div>
            """,
        unsafe_allow_html=True,
    )

    todas_vg_exp, desp_det_exp = carregar_todas_viagens_consulta()
    todos_abast_exp = carregar_todos_abastecimentos()
    xlsx_bytes_completo = gerar_excel_base_completa(
        todas_vg_exp, desp_det_exp, motoristas_db, veiculos_db, clientes_db, locais_db, fornecedores_db,
        abastecimentos=todos_abast_exp,
        fechamentos_ciclos=consolidar_ciclos(todas_vg_exp, carregar_todas_despesas_ciclo()),
        recebimentos=carregar_todos_recebimentos(),
        despesas_ciclo=carregar_todas_despesas_ciclo(),
        despesas_veiculo=carregar_todas_despesas_veiculo(),
        atribuicoes_veiculo=carregar_historico_atribuicoes_veiculo(),
        alertas_despesas=carregar_alertas_despesas_cruzadas(),
    )

    tab_rel_viagem, tab_rel_geral, tab_rel_ciclos, tab_rel_conferencia = st.tabs(
        [
            "📄 Relatório da Viagem Ativa",
            "📊 Painel Geral (BI Consolidado)",
            "📚 Fechamento por Ciclo",
            "🧾 Conferência Financeira Geral",
        ]
    )

    # ----------------------------------------------------------------------
    # SUB-ABA 1: RELATÓRIO DA VIAGEM ATIVA
    # ----------------------------------------------------------------------
    with tab_rel_viagem:
        v_neg_r = to_float(get_campo("valor_negociado", 0.0))
        v_rec_r = to_float(get_campo("valor_adiant", 0.0)) + to_float(get_campo("valor_saldo", 0.0))
        receita_r = v_neg_r
        receb_real_r = round(sum(
            r["valor_recebido"] for r in carregar_recebimentos_viagem(viagem_sel_id)
            if not r["cancelado"]
        ), 2)
        saldo_real_r = max(0.0, receita_r - receb_real_r)

        if viagem_sel_id == 0:
            desps_r = st.session_state.get("despesas_temp", [])
        else:
            desps_r = carregar_despesas_viagem(viagem_sel_id)

        custos_r = sum(to_float(d["valor_total"]) for d in desps_r)
        resultado_r = receita_r - custos_r
        od_inicio_rel = to_int(get_campo("odo_ini", 0))
        od_final_rel = to_int(get_campo("odo_fin", 0))
        km_r = (
            od_final_rel - od_inicio_rel
            if od_inicio_rel > 0 and od_final_rel >= od_inicio_rel
            else None
        )
        custo_km_r = (custos_r / km_r) if km_r else None
        frete_ativo_em_ciclo = get_campo("tipo_viagem", "Individual") == "Ciclo"
        if frete_ativo_em_ciclo:
            st.info("Esta é a visão COMERCIAL do frete: os custos compartilhados do ciclo "
                    "não são distribuídos artificialmente. Não interprete o saldo exibido "
                    "como lucro individual. Consulte o Fechamento por Ciclo.")
            # KM e margem por frete isolado são distorcidos em percursos compartilhados.
            custo_km_r = None
        margem_r = ((resultado_r / receita_r) * 100.0) if receita_r > 0 and not frete_ativo_em_ciclo else None

        exibir_indicadores(
            [
                ("Receita Negociada", fmt_brl(receita_r)),
                ("Custos Totais", fmt_brl(custos_r)),
                ("Saldo antes dos custos comuns" if frete_ativo_em_ciclo else "Resultado Operacional Parcial", fmt_brl(resultado_r), "destaque"),
                ("Custo por KM", fmt_brl(custo_km_r) if custo_km_r is not None else "Não informado"),
                ("Margem Operacional", f"{margem_r:.1f}%" if margem_r is not None else "Não calculável"),
            ],
            colunas=5,
        )
        exibir_indicadores(
            [
                ("Recebido de Fato", fmt_brl(receb_real_r)),
                ("Saldo a Receber", fmt_brl(saldo_real_r), "destaque"),
                ("Parcelas Previstas", fmt_brl(v_rec_r)),
            ],
            colunas=3,
        )

        st.markdown('<div class="sec-subtitle">Exportação da Viagem Atual</div>', unsafe_allow_html=True)
        vei_obj_r = next((v for v in veiculos_db if v["id_veiculo"] == get_campo("vei_id", 0)), None)
        dados_pdf = {
            "codigo": id_label_ctx,
            "id_frete": get_campo("id_frete") or "-",
            "cliente": cli_nome_ctx,
            "ciclo": get_campo("ciclo_nome") or "Individual",
            "motorista": mot_nome_ctx,
            "veiculo": f"{vei_obj_r['descricao_marca']} ({vei_obj_r['placa']})" if vei_obj_r else "-",
            "origem": get_campo("rota_origem") or "-",
            "destino": get_campo("rota_destino") or "-",
            "tipo_viagem": get_campo("tipo_viagem", "Individual"),
            "frete_info": f"{get_campo('tipo_frete', 'Dedicado')} / {get_campo('forma_contrat', '-')}",
            "status": status_ctx,
            "km_real_fmt": f"{km_r} km" if km_r is not None else "Não informado",
            "receita_fmt": fmt_brl(receita_r),
            "despesa_fmt": fmt_brl(custos_r),
            "resultado_fmt": fmt_brl(resultado_r),
            "custo_km_fmt": fmt_brl(custo_km_r) if custo_km_r is not None else "Não informado",
            "margem_fmt": f"{margem_r:.1f}%" if margem_r is not None else "Não calculável",
            "parcelas_previstas_fmt": fmt_brl(v_rec_r),
            "recebido_real_fmt": fmt_brl(receb_real_r),
            "saldo_receber_fmt": fmt_brl(saldo_real_r),
        }
        desps_pdf = [
            {
                "tipo": d["tipo_despesa"],
                "desc": d.get("descricao_detalhe") or "-",
                "qtd": to_float(d["quantidade"]),
                "unit_fmt": fmt_brl(d["valor_unitario"]),
                "total_fmt": fmt_brl(d["valor_total"]),
            }
            for d in desps_r
        ]
        pdf_bytes = gerar_pdf_relatorio(dados_pdf, desps_pdf)

        b_pdf, b_xls = st.columns(2)
        with b_pdf:
            st.download_button(
                "📄 Baixar Relatório PDF (Viagem)",
                data=pdf_bytes,
                file_name=f"Relatorio_{id_label_ctx}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key="dl_pdf_viagem_ativa",
            )
        with b_xls:
            st.download_button(
                "📥 Exportar Base Completa (.xlsx)",
                data=xlsx_bytes_completo,
                file_name="Base_Completa_FAEG.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="dl_xlsx_viagem_ativa",
            )

        if desps_r:
            st.markdown('<div class="sec-subtitle">Distribuição de Gastos por Categoria</div>', unsafe_allow_html=True)
            df_chart = (
                pd.DataFrame(desps_r)
                .groupby("tipo_despesa", as_index=False)["valor_total"]
                .sum()
                .rename(columns={"tipo_despesa": "Categoria", "valor_total": "Total (R$)"})
            )
            st.bar_chart(df_chart.set_index("Categoria"), color="#F34D25")
        else:
            st.info("Nenhuma despesa registrada nesta viagem para exibir o gráfico de categorias.")

    # ----------------------------------------------------------------------
    # SUB-ABA 2: PAINEL GERAL (BI CONSOLIDADO DE TODAS AS VIAGENS)
    # ----------------------------------------------------------------------
    with tab_rel_geral:
        if not todas_vg_exp:
            st.info("Nenhuma viagem salva no banco até o momento para consolidar indicadores.")
        else:
            st.markdown('<div class="sec-subtitle">Filtros do Painel Executivo</div>', unsafe_allow_html=True)
            fg1, fg2, fg3 = st.columns([1.4, 1.3, 2.3])
            with fg1:
                bi_status = st.selectbox(
                    "SITUAÇÃO DA OPERAÇÃO",
                    ["Todas"] + OPCOES_SITUACAO_OPERACAO,
                    key="bi_filtro_status",
                )
            with fg2:
                bi_tipo = st.selectbox(
                    "TIPO DE VIAGEM",
                    ["Todos", "Individual", "Ciclo"],
                    key="bi_filtro_tipo",
                )
            with fg3:
                clientes_bi_ops = ["Todos"] + sorted(
                    list({v["cliente"] for v in todas_vg_exp if v["cliente"] and v["cliente"] != "-"})
                )
                bi_cliente = st.selectbox(
                    "CLIENTE CONTRATANTE",
                    clientes_bi_ops,
                    key="bi_filtro_cliente",
                )

            vg_bi_filtradas = todas_vg_exp
            if bi_status != "Todas":
                vg_bi_filtradas = [v for v in vg_bi_filtradas if v["status"] == bi_status]
            if bi_tipo != "Todos":
                vg_bi_filtradas = [v for v in vg_bi_filtradas if v["tipo_viagem"] == bi_tipo]
            if bi_cliente != "Todos":
                vg_bi_filtradas = [v for v in vg_bi_filtradas if v["cliente"] == bi_cliente]

            cods_bi_ativos = {v["codigo_viagem"] for v in vg_bi_filtradas}
            desps_bi_filtradas = [
                d for d in desp_det_exp if d.get("Código Viagem") in cods_bi_ativos
            ]

            rec_global = sum(v["receita_base"] for v in vg_bi_filtradas)
            desp_global = sum(v["total_despesas"] for v in vg_bi_filtradas)
            res_global = rec_global - desp_global
            recebimentos_global = round(sum(v["total_recebido"] for v in vg_bi_filtradas), 2)
            saldo_global_confiavel = all(v["saldo_a_receber"] is not None for v in vg_bi_filtradas)
            saldo_global = round(sum(v["saldo_a_receber"] or 0 for v in vg_bi_filtradas), 2)
            mistura_ciclos_bi = any(v["tipo_viagem"] == "Ciclo" for v in vg_bi_filtradas)
            margem_global = (
                (res_global / rec_global) * 100.0
                if rec_global > 0 and not mistura_ciclos_bi
                and not any(v["financeiro_legado_ambiguo"] for v in vg_bi_filtradas)
                else None
            )
            if mistura_ciclos_bi:
                st.caption("O BI por frete não atribui despesas nem KM comuns aos serviços. "
                           "A margem e o custo por KM do conjunto filtrado devem ser consultados "
                           "no fechamento por ciclo, não por frete.")
            km_global = sum(v["km_rodado"] or 0 for v in vg_bi_filtradas)
            quantos_com_odometro = sum(v["km_rodado"] is not None for v in vg_bi_filtradas)
            km_completo = quantos_com_odometro == len(vg_bi_filtradas) and bool(vg_bi_filtradas)
            custo_km_global = ((desp_global / km_global)
                                if km_global > 0 and km_completo and not mistura_ciclos_bi else None)
            km_global_fmt = (
                f"{km_global:,} km".replace(",", ".") + (" (parcial)" if not km_completo else "")
                if quantos_com_odometro else "Não informado"
            )

            st.markdown('<div class="sec-subtitle">Indicadores Globais Consolidados</div>', unsafe_allow_html=True)
            exibir_indicadores(
                [
                    ("Viagens Analisadas", len(vg_bi_filtradas)),
                    ("Receita Consolidada", fmt_brl(rec_global)),
                    ("Despesas dos Fretes", fmt_brl(desp_global)),
                ],
                colunas=3,
            )
            exibir_indicadores(
                [
                    ("Resultado Operacional Parcial", fmt_brl(res_global), "destaque"),
                    ("Margem Operacional", f"{margem_global:.1f}%" if margem_global is not None else "Não calculável"),
                    ("KM Registrado / Custo Médio KM", f"{km_global_fmt} / {fmt_brl(custo_km_global) if custo_km_global is not None else 'Não informado'}"),
                ],
                colunas=3,
            )
            exibir_indicadores(
                [
                    ("Recebimentos Confirmados", fmt_brl(recebimentos_global)),
                    ("Saldo em Aberto", fmt_brl(saldo_global) if saldo_global_confiavel else "Conferir financeiro legado", "destaque"),
                ],
                colunas=2,
            )
            st.caption(
                "Este BI é filtrado por frete/cliente e não inclui despesas compartilhadas do ciclo, "
                "pois não há rateio aprovado. Consulte 'Fechamento por Ciclo' para o resultado "
                "que inclui esses gastos uma única vez. Não some os dois painéis."
            )
            if not km_completo:
                st.caption("KM total parcial: existem fretes sem as duas leituras de odômetro. Custo médio por KM global fica indisponível.")
            if any(v["financeiro_legado_ambiguo"] for v in vg_bi_filtradas):
                st.warning("Alguns fretes antigos compartilham o financeiro do ciclo. Esses valores foram excluídos dos totais por frete até a conferência, evitando receita duplicada.")

            # Agrupamento por Cliente
            ranking_cli_lista = []
            if vg_bi_filtradas:
                df_bi_vg = pd.DataFrame(vg_bi_filtradas)
                grp_cli = (
                    df_bi_vg.groupby("cliente", as_index=False)
                    .agg(
                        viagens=("id_viagem", "count"),
                        receita=("receita_base", "sum"),
                        recebido=("total_recebido", "sum"),
                        despesas=("total_despesas", "sum"),
                        resultado=("resultado_liquido", "sum"),
                    )
                    .sort_values("resultado", ascending=False)
                )
                for _, row_c in grp_cli.iterrows():
                    cliente_legado_ambiguo = any(
                        v["financeiro_legado_ambiguo"] and v["cliente"] == row_c["cliente"]
                        for v in vg_bi_filtradas
                    )
                    mg_c = (
                        (row_c["resultado"] / row_c["receita"]) * 100.0
                        if row_c["receita"] > 0 and not cliente_legado_ambiguo else None
                    )
                    ranking_cli_lista.append(
                        {
                            "cliente": row_c["cliente"],
                            "viagens": int(row_c["viagens"]),
                            "receita": float(row_c["receita"]),
                            "recebido": float(row_c["recebido"]),
                            "despesas": float(row_c["despesas"]),
                            "resultado": float(row_c["resultado"]),
                            "margem": mg_c,
                            "receita_fmt": fmt_brl(row_c["receita"]),
                            "recebido_fmt": fmt_brl(row_c["recebido"]),
                            "despesa_fmt": fmt_brl(row_c["despesas"]),
                            "resultado_fmt": fmt_brl(row_c["resultado"]),
                            "margem_fmt": f"{mg_c:.1f}%" if mg_c is not None else "Não calculável",
                        }
                    )

            # Agrupamento de Despesas por Categoria
            desp_cat_lista = []
            if desps_bi_filtradas:
                df_bi_desp = pd.DataFrame(desps_bi_filtradas)
                grp_cat = (
                    df_bi_desp.groupby("Tipo Despesa", as_index=False)["Valor Total (R$)"]
                    .sum()
                    .sort_values("Valor Total (R$)", ascending=False)
                )
                tot_cat_soma = float(grp_cat["Valor Total (R$)"].sum())
                for _, row_d in grp_cat.iterrows():
                    val_cat = float(row_d["Valor Total (R$)"])
                    pct_cat = ((val_cat / tot_cat_soma) * 100.0) if tot_cat_soma > 0 else 0.0
                    desp_cat_lista.append(
                        {
                            "categoria": row_d["Tipo Despesa"],
                            "total": val_cat,
                            "total_fmt": fmt_brl(val_cat),
                            "pct_fmt": f"{pct_cat:.1f}%",
                        }
                    )

            g_col1, g_col2 = st.columns(2)
            with g_col1:
                st.markdown('<div class="sec-subtitle">Despesas por Categoria (Consolidado)</div>', unsafe_allow_html=True)
                if desp_cat_lista:
                    df_chart_cat_bi = pd.DataFrame(desp_cat_lista)[["categoria", "total"]].rename(
                        columns={"categoria": "Categoria", "total": "Total (R$)"}
                    )
                    st.bar_chart(df_chart_cat_bi.set_index("Categoria"), color="#F34D25")
                else:
                    st.info("Sem despesas registradas para o filtro selecionado.")

            with g_col2:
                st.markdown('<div class="sec-subtitle">Resultado Operacional Parcial por Cliente</div>', unsafe_allow_html=True)
                if ranking_cli_lista:
                    df_chart_cli_bi = pd.DataFrame(ranking_cli_lista)[["cliente", "resultado"]].rename(
                        columns={"cliente": "Cliente", "resultado": "Resultado Operacional Parcial (R$)"}
                    )
                    st.bar_chart(df_chart_cli_bi.set_index("Cliente"), color="#0D263C")
                else:
                    st.info("Sem viagens filtradas para exibir o ranking por cliente.")

            if ranking_cli_lista:
                st.markdown('<div class="sec-subtitle">Resumo Executivo por Cliente</div>', unsafe_allow_html=True)
                df_tabela_cli = pd.DataFrame(
                    [
                        {
                            "Cliente": r["cliente"],
                            "Viagens": r["viagens"],
                            "Receita Total": r["receita_fmt"],
                            "Recebido de Fato": r["recebido_fmt"],
                            "Despesas dos Fretes": r["despesa_fmt"],
                            "Resultado Operacional Parcial": r["resultado_fmt"],
                            "Margem (%)": r["margem_fmt"],
                        }
                        for r in ranking_cli_lista
                    ]
                )
                st.dataframe(df_tabela_cli, use_container_width=True, hide_index=True)

            st.markdown('<div class="sec-subtitle">Exportação Executiva Consolidada</div>', unsafe_allow_html=True)
            resumo_pdf_bi = {
                "filtro_desc": f"Situacao: {bi_status} | Tipo: {bi_tipo} | Cliente: {bi_cliente}",
                "qtd_viagens": len(vg_bi_filtradas),
                "km_total_fmt": km_global_fmt,
                "receita_fmt": fmt_brl(rec_global),
                "despesa_fmt": fmt_brl(desp_global),
                "resultado_fmt": fmt_brl(res_global),
                "recebido_fmt": fmt_brl(recebimentos_global),
                "saldo_fmt": fmt_brl(saldo_global) if saldo_global_confiavel else "Conferir legado",
                "margem_fmt": f"{margem_global:.1f}%" if margem_global is not None else "Não calculável",
            }
            pdf_bi_bytes = gerar_pdf_relatorio_consolidado(
                resumo_pdf_bi, ranking_cli_lista, desp_cat_lista
            )

            eb1, eb2, _ = st.columns([1.8, 1.7, 2.0])
            with eb1:
                st.download_button(
                    "📄 Baixar Relatório Executivo PDF",
                    data=pdf_bi_bytes,
                    file_name=f"Relatorio_Consolidado_FAEG_{date.today().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="dl_pdf_consolidado_bi",
                )
            with eb2:
                st.download_button(
                    "📥 Exportar Base Completa (.xlsx)",
                    data=xlsx_bytes_completo,
                    file_name="Base_Completa_FAEG.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="dl_xlsx_consolidado_bi",
                )

    # ----------------------------------------------------------------------
    # SUB-ABA 3: CONSOLIDAÇÃO POR ID INTERNO DO CICLO
    # ----------------------------------------------------------------------
    with tab_rel_ciclos:
        fechamentos_salvos = consolidar_ciclos(todas_vg_exp, carregar_todas_despesas_ciclo())
        with SessionLocal() as db:
            saidas_todas = consultar_todas_saidas(db)
            saidas_por_ciclo = {}
            for saida in saidas_todas:
                saidas_por_ciclo.setdefault(saida.id_ciclo, []).append(saida)
            resumos_por_ciclo = {
                cid: resumo_saidas(lista) for cid, lista in saidas_por_ciclo.items()
            }
        st.caption(
            "Cada despesa por ID Frete é somada uma vez e cada despesa compartilhada "
            "por ID Ciclo entra uma vez, sem rateio. O BI por frete não inclui os gastos "
            "compartilhados; não some os resultados dos dois painéis."
        )
        if not fechamentos_salvos:
            st.info("Ainda não existem fretes do tipo Ciclo salvos para consolidar.")
        else:
            exibir_indicadores(
                [
                    ("CICLOS COM FRETES", len(fechamentos_salvos)),
                    ("FRETES AGRUPADOS", sum(f["qtd_fretes"] for f in fechamentos_salvos)),
                    ("DESPESAS ATRIBUÍDAS AOS CICLOS", fmt_brl(sum(f["despesas_total"] for f in fechamentos_salvos)), "destaque"),
                ],
                colunas=3,
            )
            st.dataframe(
                pd.DataFrame([
                    {
                        "Ciclo": f["ciclo"],
                        "Fretes": f["qtd_fretes"],
                        "Receita Negociada": fmt_brl(f["valor_negociado_total"]),
                        "Parcelas Previstas": fmt_brl(f["parcelas_previstas"]),
                        "Recebido de Fato": fmt_brl(f["total_recebido"]),
                        "Saldo em Aberto": fmt_brl(f["saldo_a_receber"]) if f["saldo_a_receber"] is not None else "Conferir legado",
                        "Despesas Fretes": fmt_brl(f["despesas_fretes_total"]),
                        "Despesas Compartilhadas": fmt_brl(f["despesas_compartilhadas_total"]),
                        "Despesas Totais": fmt_brl(f["despesas_total"]),
                        "Resultado Parcial": fmt_brl(f["resultado_operacional_parcial"]),
                        "KM Total Planejado": fmt_km(resumos_por_ciclo[f["id_ciclo"]]["km_planejado"])
                        if f["id_ciclo"] in resumos_por_ciclo else fmt_km(f["km_total_planejado"]),
                        "KM Real Operacional": (
                            fmt_km(resumos_por_ciclo[f["id_ciclo"]]["km_real"])
                            if f["id_ciclo"] in resumos_por_ciclo and resumos_por_ciclo[f["id_ciclo"]]["km_real"] is not None
                            else "Pendente" if f["id_ciclo"] in resumos_por_ciclo else "Legado"
                        ),
                        "Conferência Financeira": "Pendente" if f["qtd_financeiros_legados_ambiguos"] else "Por frete",
                    }
                    for f in fechamentos_salvos
                ]),
                hide_index=True,
                use_container_width=True,
            )
            opcoes_ciclos = {f["id_ciclo"]: f for f in fechamentos_salvos}
            ciclo_abrir_id = st.selectbox(
                "VER DETALHAMENTO DO CICLO",
                options=list(opcoes_ciclos),
                format_func=lambda x: f"{opcoes_ciclos[x]['ciclo']} — {opcoes_ciclos[x]['qtd_fretes']} frete(s)",
                key="rel_ciclo_detalhe",
            )
            ciclo_aberto = opcoes_ciclos[ciclo_abrir_id]
            if ciclo_abrir_id in resumos_por_ciclo:
                rz = resumos_por_ciclo[ciclo_abrir_id]
                st.info(f"KM operacional por {rz['qtd_saidas']} saída(s) e {rz['qtd_trechos']} trecho(s): "
                        f"{rz['km_planejado']:.2f} km planejados; "
                        + (f"{rz['km_real']:.0f} km realizados." if rz['km_real'] is not None
                           else "KM real pendente de odômetros completos."))
            st.caption(
                f"Ciclo {ciclo_aberto['ciclo']}: despesas dos fretes "
                f"{fmt_brl(ciclo_aberto['despesas_fretes_total'])} + despesas compartilhadas "
                f"{fmt_brl(ciclo_aberto['despesas_compartilhadas_total'])} "
                f"= {fmt_brl(ciclo_aberto['despesas_total'])}."
            )
            st.dataframe(
                pd.DataFrame([
                    {
                        "ID Frete": f["id_frete"],
                        "Código Viagem": f["codigo_viagem"],
                        "Cliente": f["cliente"],
                        "Negociado Considerado (R$)": to_float(f["negociado_considerado"]),
                        "Recebido de Fato (R$)": to_float(f["total_recebido"]),
                        "Despesas (R$)": to_float(f["total_despesas"]),
                        "Situação Financeira": "Legado para conferir" if f["financeiro_legado_ambiguo"] else "Individualizado",
                    }
                    for f in ciclo_aberto["fretes"]
                ]),
                hide_index=True,
                use_container_width=True,
            )
            if ciclo_aberto["qtd_financeiros_legados_ambiguos"]:
                st.warning(
                    "Atenção: este ciclo contém registros financeiros antigos sem separação "
                    "por frete. Esses valores não foram repetidos na receita consolidada; "
                    "a conferência e a individualização ainda são necessárias."
                )
            st.caption("O Excel da Etapa 9 inclui Fechamento_Ciclos (com os dois componentes de despesa) e Despesas_Ciclo (lançamentos ativos e cancelados).")

    # ----------------------------------------------------------------------
    # SUB-ABA 4: CONFERÊNCIA FINANCEIRA DA BASE INTEIRA (SEM FILTROS DO BI)
    # ----------------------------------------------------------------------
    with tab_rel_conferencia:
        geral = reconciliar_resultado_gerencial(
            todas_vg_exp, carregar_todas_despesas_ciclo(), carregar_todas_despesas_veiculo(),
        )
        st.info(
            "Conferência de TODA a base salva, independente dos filtros do Painel Geral. "
            "O resultado inclui custos diretos dos fretes e compartilhados dos ciclos "
            "uma única vez. Não soma novamente abastecimentos ou despesas de veículo atribuídas."
        )
        exibir_indicadores(
            [
                ("RECEITA NEGOCIADA CONSIDERADA", fmt_brl(geral["receita_negociada_considerada"])),
                ("DESPESAS DOS FRETES", fmt_brl(geral["despesas_fretes"])),
                ("DESPESAS COMPARTILHADAS", fmt_brl(geral["despesas_compartilhadas"])),
                ("DESPESAS TOTAIS CONTABILIZADAS", fmt_brl(geral["despesas_financeiras_totais"])),
            ],
            colunas=4,
        )
        exibir_indicadores(
            [
                ("RESULTADO OPERACIONAL PARCIAL", fmt_brl(geral["resultado_operacional_parcial"]), "destaque"),
                ("MARGEM OPERACIONAL", f"{geral['margem_operacional_pct']:.1f}%" if geral["margem_operacional_pct"] is not None else "Não calculável"),
                ("RECEBIDO DE FATO", fmt_brl(geral["total_recebido"])),
                ("SALDO A RECEBER", fmt_brl(geral["saldo_a_receber"]) if geral["saldo_a_receber"] is not None else "Conferir financeiro legado"),
            ],
            colunas=4,
        )
        st.markdown("**Despesas vinculadas ao veículo — controle separado**")
        exibir_indicadores(
            [
                ("PENDENTES — FORA DO RESULTADO", fmt_brl(geral["despesas_veiculo_pendentes"]), "destaque"),
                ("JÁ ATRIBUÍDAS — NÃO SOMAR DE NOVO", fmt_brl(geral["despesas_veiculo_ja_atribuidas"])),
            ],
            colunas=2,
        )
        st.caption(
            "Os gastos pendentes ainda não pertencem a frete/ciclo. Os já atribuídos "
            "estão incluídos nas despesas financeiras de seus destinos, não são uma terceira despesa."
        )
        if geral["qtd_financeiros_legados_ambiguos"]:
            st.warning(
                f"{geral['qtd_financeiros_legados_ambiguos']} frete(s) com financeiro legado "
                "ambíguo: a receita desses registros não foi considerada; portanto o "
                "resultado gerencial é incompleto até a individualização."
            )
        if geral["qtd_despesas_ciclo_sem_fretes"]:
            st.warning(
                f"{geral['qtd_despesas_ciclo_sem_fretes']} despesa(s) compartilhada(s) ativa(s) "
                "pertencem a ciclos sem fretes do tipo Ciclo. Estão incluídas na conferência "
                "geral, mas exigem verificação do vínculo antes do fechamento."
            )
        st.caption(
            "Recebido de fato é fluxo de caixa, não outra receita a somar ao negociado. "
            "A planilha completa reproduz esta ponte na aba Conferencia_Financeira. "
            "A conferência separa fontes financeiras; lançamentos manuais iguais em "
            "destinos diferentes ainda exigem verificação humana."
        )
        st.markdown("**Possíveis duplicidades entre despesas do frete e do ciclo**")
        alertas_cruzados = carregar_alertas_despesas_cruzadas()
        if alertas_cruzados:
            st.warning(
                f"{len(alertas_cruzados)} coincidência(s) de data, categoria, valor "
                "e demais campos entre despesas de frete e do respectivo ciclo. "
                "Confira comprovantes antes de corrigir: duas despesas podem ser legítimas."
            )
            st.dataframe(
                pd.DataFrame([
                    {
                        **a,
                        "Data": a["Data"].strftime("%d/%m/%Y") if a["Data"] else None,
                    }
                    for a in alertas_cruzados
                ]),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption(
                "Nenhuma coincidência encontrada pelo critério atual. Isso não comprova "
                "ausência de outros lançamentos repetidos; confira os comprovantes."
            )
        st.caption(
            "Esta lista é somente leitura. O Excel disponibiliza os indícios "
            "na aba Possiveis_Duplicidades; nenhum registro é excluído automaticamente."
        )

    render_navegacao_rodape(8, MENU_ITENS)
