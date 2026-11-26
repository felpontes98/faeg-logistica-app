"""Etapa 7 — Despesas e histórico de abastecimentos do Sistema Web FAEG."""
import pandas as pd
from html import escape

import streamlit as st
from views.formulario_despesa import abrir_edicao, render_formulario_despesa
from database.despesas import consultar_edicoes

from database.atribuicao_despesas import atribuir_despesa_veiculo, estornar_atribuicao_veiculo
from database.conferencia_duplicidades import procurar_semelhancas_cruzadas
from database.connection import SessionLocal
from database.models import Abastecimento, CicloDespesa, CicloOperacional, VeiculoDespesa, ViagemDespesa
from datetime import date
from faeg_app.core import (
    carregar_abastecimentos_veiculo,
    carregar_despesas_viagem,
    carregar_historico_atribuicoes_veiculo,
    carregar_todas_despesas_ciclo,
    carregar_todas_despesas_veiculo,
    carregar_todas_viagens_consulta,
    exibir_indicadores,
    fmt_brl,
    limpar_caches_atribuicao,
    render_navegacao_rodape,
    to_float,
)


def render(ctx):
    MENU_ITENS = ctx.menu_itens
    fornecedores_db = ctx.fornecedores_db
    veiculos_db = ctx.veiculos_db
    viagem_sel_id = ctx.viagem_sel_id

    st.markdown(
        """
            <div class="tab-header-wrap">
                <div class="tab-title"><i class="fa-solid fa-receipt"></i> Despesas de Viagem</div>
                <span class="tab-step-pill">Etapa 7 de 11</span>
            </div>
            """,
        unsafe_allow_html=True,
    )

    with SessionLocal() as db:
        ciclos_destino = {
            c.id_ciclo: c.nome_operacao
            for c in db.query(CicloOperacional)
            .order_by(CicloOperacional.nome_operacao, CicloOperacional.id_ciclo).all()
            if not c.nome_operacao.startswith("Individual - ")
        }
    veiculos_destino = {
        v["id_veiculo"]: f"{v['descricao_marca']} ({v['placa']})"
        for v in veiculos_db
    }
    try:
        render_formulario_despesa(ctx, ciclos_destino, veiculos_destino)
    except ValueError as exc:
        st.warning(str(exc))
        if st.session_state.get("edicao_despesa") and st.button("Fechar edição"):
            st.session_state.pop("edicao_despesa")
            st.rerun()
    if st.session_state.get("edicao_despesa"):
        render_navegacao_rodape(6, MENU_ITENS)
        return

    st.subheader("Despesas do frete" if viagem_sel_id else "Despesas do rascunho")
    forn_map = {f["id_fornecedor"]: f["nome_fantasia"] for f in fornecedores_db}

    if viagem_sel_id == 0:
        lista_desp_atual = [
            {
                "idx": idx,
                "id_despesa": None,
                "destino": "Ciclo" if d.get("destino_temp") == "ciclo" else "Frete",
                "tipo_despesa": d["tipo_despesa"],
                "descricao_detalhe": d["descricao_detalhe"],
                "fornecedor": forn_map.get(d["id_fornecedor"], "Não informado"),
                "quantidade": to_float(d["quantidade"]),
                "valor_unitario": to_float(d["valor_unitario"]),
                "valor_total": to_float(d["valor_total"]),
                "odometro_abastecimento": d.get("odometro_abastecimento"),
                "data_despesa": d.get("data_despesa"),
            }
            for idx, d in enumerate(st.session_state.get("despesas_temp", []))
        ]
    else:
        desps_db = carregar_despesas_viagem(viagem_sel_id)
        lista_desp_atual = [
            {
                "idx": idx,
                "id_despesa": d["id_despesa"],
                "tipo_despesa": d["tipo_despesa"],
                "descricao_detalhe": d["descricao_detalhe"] or "-",
                "fornecedor": forn_map.get(d["id_fornecedor"], "Não informado"),
                "quantidade": to_float(d["quantidade"]),
                "valor_unitario": to_float(d["valor_unitario"]),
                "valor_total": to_float(d["valor_total"]),
                "odometro_abastecimento": d.get("odometro_abastecimento"),
                "data_despesa": d.get("data_despesa"),
            }
            for idx, d in enumerate(desps_db)
        ]

    if not lista_desp_atual:
        st.info("Nenhuma despesa lançada até o momento nesta viagem.")
    else:
        soma_desp = 0.0
        for item in lista_desp_atual:
            soma_desp += item["valor_total"]
            col_t1, col_t2, col_t3, col_t4, col_t5 = st.columns([2.2, 2.4, 1.2, 1.3, 0.7])
            col_t1.markdown(
                f"**{escape(str(item['tipo_despesa']))}**  \n<span style='font-size:0.78rem;color:#64748B;'>{escape(str(item['fornecedor']))}</span>",
                unsafe_allow_html=True,
            )
            col_t2.markdown(f"{item['descricao_detalhe']}")
            if item.get("data_despesa"):
                data_tipo_rotulo = "Data do abastecimento" if item["tipo_despesa"] in {"Posto de Combustível", "Abast. ARLA"} else "Data da despesa"
                col_t2.caption(f"{data_tipo_rotulo}: {item['data_despesa'].strftime('%d/%m/%Y')}")
            if item.get("odometro_abastecimento") is not None:
                col_t2.caption(f"Odômetro no abastecimento: {item['odometro_abastecimento']} km")
            casas = 4 if item["tipo_despesa"] in {"Posto de Combustível", "Abast. ARLA"} else 2
            preco = f"{item['valor_unitario']:.{casas}f}".replace(".", ",")
            quantidade = f"{item['quantidade']:.2f}".replace(".", ",")
            col_t3.markdown(f"{quantidade} × R$ {preco}")
            col_t4.markdown(f"**{fmt_brl(item['valor_total'])}**")
            if not viagem_sel_id:
                col_t2.caption(item["destino"])
            col_t5.button("Editar", key=f"editar_item_{item['idx']}", on_click=abrir_edicao,
                          args=("Frete" if viagem_sel_id else "Rascunho",
                                item["id_despesa"] if viagem_sel_id else item["idx"], viagem_sel_id))
            motivo = st.text_input("Motivo do cancelamento", max_chars=200, key=f"motivo_desp_{item['id_despesa']}") if viagem_sel_id else ""
            if col_t5.button("🗑️", key=f"del_desp_{viagem_sel_id}_{item['idx']}", help="Cancelar despesa salva" if viagem_sel_id else "Remover do rascunho"):
                if viagem_sel_id == 0:
                    st.session_state["despesas_temp"].pop(item["idx"])
                    st.rerun()
                else:
                    with SessionLocal() as db:
                        obj_d = db.query(ViagemDespesa).filter_by(id_despesa=item["id_despesa"], cancelado=False).with_for_update().first()
                        if obj_d:
                            origem_provisoria = db.query(VeiculoDespesa).filter_by(
                                id_despesa_viagem_destino=obj_d.id_despesa
                            ).first()
                            if origem_provisoria:
                                st.warning(
                                    "Esta despesa veio de um veículo. Para devolver o custo ao veículo, use "
                                    "'Estornar atribuição' no histórico de despesas do veículo, "
                                    "preservando a rastreabilidade."
                                )
                            elif not motivo.strip():
                                st.warning("Informe o motivo para cancelar a despesa.")
                            else:
                                # O custo e o abastecimento compartilham o motivo do cancelamento.
                                db.query(Abastecimento).filter_by(
                                    id_despesa_viagem=obj_d.id_despesa
                                ).update({"cancelado": True, "data_cancelamento": date.today(),
                                          "motivo_cancelamento": motivo.strip()}, synchronize_session=False)
                                obj_d.cancelado = True
                                obj_d.data_cancelamento = date.today()
                                obj_d.motivo_cancelamento = motivo.strip()
                                db.commit()
                                limpar_caches_atribuicao()
                                st.toast("Despesa cancelada.", icon="🗑️")
                                st.rerun()

        st.markdown(
            f"""
                <div class="faeg-recebimento-banner" style="border-left-color:#F34D25;">
                    <span class="faeg-recebimento-label">{"Total do frete" if viagem_sel_id else "Total do rascunho"}</span>
                    <span class="faeg-recebimento-val" style="color:#F34D25;">{fmt_brl(soma_desp)}</span>
                </div>
                """,
            unsafe_allow_html=True,
        )

    with st.expander("🧾 Histórico das despesas compartilhadas dos ciclos", expanded=False):
        st.caption(
            "Selecione o ciclo para consultar, editar ou cancelar uma despesa compartilhada."
        )
        if not ciclos_destino:
            st.info("Ainda não há ciclos salvos. Salve primeiro um frete do tipo Ciclo para registrar uma despesa compartilhada.")
        else:
            ciclo_historico_id = st.selectbox(
                "SELECIONE O CICLO PARA CONFERÊNCIA", options=list(ciclos_destino),
                format_func=lambda x: f"{ciclos_destino[x]} (ID interno {x})",
                key="desp_ciclo_historico_id",
            )
            historico_desp_ciclo = [
                d for d in carregar_todas_despesas_ciclo() if d["id_ciclo"] == ciclo_historico_id
            ]
            if historico_desp_ciclo:
                st.dataframe(
                    pd.DataFrame([
                        {
                            "Data": d["data_despesa"].strftime("%d/%m/%Y"),
                            "Tipo": d["tipo_despesa"],
                            "Descrição": d["descricao_detalhe"] or "-",
                            "Valor (R$)": d["valor_total"],
                            "Situação": "Cancelada" if d["cancelado"] else "Ativa",
                        }
                        for d in reversed(historico_desp_ciclo)
                    ]),
                    hide_index=True,
                    use_container_width=True,
                )
                ativas_ciclo = [d for d in historico_desp_ciclo if not d["cancelado"]]
                exibir_indicadores(
                    [("DESPESAS COMPARTILHADAS ATIVAS DESTE CICLO", fmt_brl(sum(d["valor_total"] for d in ativas_ciclo)))],
                    colunas=3,
                )
                if ativas_ciclo:
                    with st.expander("Editar ou cancelar despesa do ciclo"):
                        despesas_ativas_por_id = {d["id_despesa_ciclo"]: d for d in ativas_ciclo}
                        dc_cancel_id = st.selectbox(
                            "Despesa compartilhada", options=list(despesas_ativas_por_id),
                            format_func=lambda x: f"#{x} · {despesas_ativas_por_id[x]['descricao_detalhe']} · {fmt_brl(despesas_ativas_por_id[x]['valor_total'])}",
                            key="desp_ciclo_cancel_id",
                        )
                        st.button("Editar despesa do ciclo", key="editar_desp_ciclo", on_click=abrir_edicao,
                                  args=("Ciclo", dc_cancel_id, viagem_sel_id))
                        dc_cancel_motivo = st.text_input(
                            "MOTIVO DO CANCELAMENTO *", max_chars=200,
                            key="desp_ciclo_cancel_motivo",
                        )
                        if st.button("Confirmar Cancelamento da Despesa", key="desp_ciclo_cancel_btn"):
                            if len(dc_cancel_motivo.strip()) < 6:
                                st.warning("Informe um motivo com pelo menos 6 caracteres.")
                            else:
                                with SessionLocal() as session:
                                    objeto = session.query(CicloDespesa).filter_by(
                                        id_despesa_ciclo=dc_cancel_id, id_ciclo=ciclo_historico_id, cancelado=False,
                                    ).with_for_update().first()
                                    if objeto:
                                        origem_provisoria = session.query(VeiculoDespesa).filter_by(
                                            id_despesa_ciclo_destino=dc_cancel_id
                                        ).first()
                                        if origem_provisoria:
                                            st.warning(
                                                "Esta despesa foi atribuída a partir de um veículo. "
                                                "Use 'Estornar atribuição' no histórico do veículo "
                                                "para devolver o valor ao estado pendente."
                                            )
                                        else:
                                            objeto.cancelado = True
                                            objeto.data_cancelamento = date.today()
                                            objeto.motivo_cancelamento = dc_cancel_motivo.strip()
                                            for ab in session.query(Abastecimento).filter_by(id_despesa_ciclo=dc_cancel_id).all():
                                                ab.cancelado = True
                                                ab.data_cancelamento = date.today()
                                                ab.motivo_cancelamento = dc_cancel_motivo.strip()
                                            session.commit()
                                            limpar_caches_atribuicao()
                                            st.toast("Despesa cancelada, mantendo histórico!", icon="🧾")
                                            st.rerun()
            else:
                st.info("Nenhuma despesa compartilhada neste ciclo.")

    with st.expander("🚐 Despesas do veículo — conferir, atribuir ou estornar", expanded=False):
        st.caption(
            "Edite o lançamento, atribua o custo a um frete ou ciclo, ou estorne a atribuição. "
            "A edição de uma despesa atribuída atualiza o valor no destino."
        )
        pendentes_veiculo = carregar_todas_despesas_veiculo()
        pendentes_ativos = {
            d["id_despesa_veiculo"]: d for d in pendentes_veiculo
            if not d["cancelado"] and not d["id_despesa_viagem_destino"] and not d["id_despesa_ciclo_destino"]
        }
        despesas_atribuidas = {
            d["id_despesa_veiculo"]: d for d in pendentes_veiculo
            if not d["cancelado"] and (d["id_despesa_viagem_destino"] or d["id_despesa_ciclo_destino"])
        }
        exibir_indicadores(
            [(
                "TOTAL DE DESPESAS AINDA NÃO ATRIBUÍDAS",
                fmt_brl(sum(d["valor_total"] for d in pendentes_ativos.values())),
                "destaque",
            )],
            colunas=3,
        )
        if pendentes_veiculo:
            st.dataframe(
                pd.DataFrame([
                    {
                        "ID": d["id_despesa_veiculo"],
                        "Data": d["data_despesa"].strftime("%d/%m/%Y"),
                        "Veículo": veiculos_destino.get(d["id_veiculo"], f"#{d['id_veiculo']}"),
                        "Categoria": d["tipo_despesa"],
                        "Descrição": d["descricao_detalhe"],
                        "Valor (R$)": d["valor_total"],
                        "Situação": (
                            "Cancelada" if d["cancelado"] else
                            "Atribuída a frete" if d["id_despesa_viagem_destino"] else
                            "Atribuída a ciclo" if d["id_despesa_ciclo_destino"] else
                            "Pendente"
                        ),
                        "Data Atribuição": d["data_atribuicao"].strftime("%d/%m/%Y") if d["data_atribuicao"] else None,
                    }
                    for d in reversed(pendentes_veiculo)
                ]), hide_index=True, use_container_width=True,
            )
            editaveis = {**pendentes_ativos, **despesas_atribuidas}
            if editaveis:
                item_veiculo = st.selectbox("Despesa do veículo para edição", list(editaveis),
                    format_func=lambda i: f"#{i} · {editaveis[i]['descricao_detalhe']} · {fmt_brl(editaveis[i]['valor_total'])}",
                    key="editar_veiculo_selecao")
                st.button("Editar despesa do veículo", key="editar_desp_veiculo", on_click=abrir_edicao,
                          args=("Veículo", item_veiculo, viagem_sel_id))
            if pendentes_ativos:
                with st.expander("🔗 Atribuir despesa pendente a um frete ou ciclo", expanded=False):
                    atribuir_id = st.selectbox(
                        "DESPESA DE ORIGEM *", options=list(pendentes_ativos),
                        format_func=lambda x: (
                            f"#{x} — {veiculos_destino.get(pendentes_ativos[x]['id_veiculo'], '-')} "
                            f"— {fmt_brl(pendentes_ativos[x]['valor_total'])}"
                        ), key="atribuir_desp_veiculo_id",
                    )
                    atribuir_origem = pendentes_ativos[atribuir_id]
                    atribuir_tipo = st.selectbox(
                        "DESTINO FINANCEIRO *", ["Frete", "Ciclo"], key="atribuir_desp_tipo",
                    )
                    viagens_disponiveis, _ = carregar_todas_viagens_consulta()
                    viagens_compativeis = [
                        v for v in viagens_disponiveis if v["id_veiculo"] == atribuir_origem["id_veiculo"]
                    ]
                    if atribuir_tipo == "Frete":
                        opcoes_atribuir = {
                            v["id_viagem"]: f"{v['id_frete']} / {v['codigo_viagem']} — {v['cliente']}"
                            for v in viagens_compativeis
                        }
                    else:
                        opcoes_atribuir = {
                            v["id_ciclo"]: f"{ciclos_destino[v['id_ciclo']]} (ID {v['id_ciclo']})"
                            for v in viagens_compativeis
                            if v["tipo_viagem"] == "Ciclo" and v["id_ciclo"] in ciclos_destino
                        }
                    if not opcoes_atribuir:
                        st.info(
                            "Não há destino compatível com este veículo. Salve antes um "
                            "frete/ciclo que utilize a mesma placa. Nenhum custo será transferido."
                        )
                    else:
                        atribuir_destino_id = st.selectbox(
                            "ID DE DESTINO *", options=list(opcoes_atribuir),
                            format_func=lambda x: opcoes_atribuir[x],
                            key=f"atribuir_desp_destino_{atribuir_tipo}",
                        )
                        atribuir_motivo = st.text_input(
                            "JUSTIFICATIVA DA ATRIBUIÇÃO *", max_chars=200,
                            key="atribuir_desp_motivo",
                            help="Descreva por que este custo pertence ao destino escolhido.",
                        )
                        st.caption(
                            "Ao confirmar, o valor passará do estado pendente ao resultado do "
                            f"{atribuir_tipo.lower()} selecionado. O histórico do abastecimento "
                            "não será recriado nem somado duas vezes."
                        )
                        ciclo_da_atribuicao = (
                            next(
                                (v["id_ciclo"] for v in viagens_compativeis
                                 if v["id_viagem"] == atribuir_destino_id),
                                None,
                            ) if atribuir_tipo == "Frete" else atribuir_destino_id
                        )
                        with SessionLocal() as db:
                            ab_origem = db.query(Abastecimento).filter_by(
                                id_despesa_veiculo=atribuir_id,
                            ).one_or_none()
                            dados_atribuicao = {
                                **atribuir_origem,
                                "id_veiculo_abast": atribuir_origem["id_veiculo"],
                                "odometro_abastecimento": ab_origem.odometro if ab_origem else None,
                            }
                            coincidencias_atribuicao = procurar_semelhancas_cruzadas(
                                db, atribuir_tipo, ciclo_da_atribuicao, dados_atribuicao,
                            )
                        confirmar_atribuicao_distinta = False
                        if coincidencias_atribuicao:
                            st.warning(
                                "Há custo semelhante no outro destino financeiro deste ciclo "
                                f"(despesa #{coincidencias_atribuicao[0]['id_lancamento']}). "
                                "Confira o comprovante antes de transferir. Se for o mesmo gasto, "
                                "corrija o lançamento anterior em vez de duplicá-lo."
                            )
                            confirmar_atribuicao_distinta = st.checkbox(
                                "Conferi: são gastos distintos e a justificativa informa a diferença.",
                                key=(
                                    f"atribuir_similar_confirmar_{atribuir_id}_"
                                    f"{atribuir_tipo}_{atribuir_destino_id}"
                                ),
                            )
                        if st.button("Confirmar Atribuição", key="atribuir_desp_confirmar"):
                            try:
                                with SessionLocal() as db:
                                    atribuir_despesa_veiculo(
                                        db, atribuir_id, atribuir_tipo,
                                        atribuir_destino_id, atribuir_motivo,
                                        confirmar_despesa_distinta=confirmar_atribuicao_distinta,
                                    )
                                    db.commit()
                            except ValueError as exc:
                                st.warning(str(exc))
                            except Exception:
                                st.error("Não foi possível atribuir a despesa. Nenhuma transferência foi confirmada.")
                            else:
                                limpar_caches_atribuicao()
                                st.toast("Despesa atribuída ao destino, com histórico preservado!", icon="✅")
                                st.rerun()

                with st.expander("Cancelar despesa provisória incorreta"):
                    desp_veic_cancel_id = st.selectbox(
                        "DESPESA PENDENTE", options=list(pendentes_ativos),
                        format_func=lambda x: f"#{x} — {fmt_brl(pendentes_ativos[x]['valor_total'])}",
                        key="desp_veic_cancel_id",
                    )
                    motivo_veic_cancel = st.text_input(
                        "MOTIVO DO CANCELAMENTO *", key="desp_veic_cancel_motivo", max_chars=200,
                    )
                    if st.button("Confirmar Cancelamento da Despesa Pendente", key="desp_veic_cancel_btn"):
                        if len(motivo_veic_cancel.strip()) < 6:
                            st.warning("Informe um motivo com pelo menos 6 caracteres.")
                        else:
                            with SessionLocal() as db:
                                pendente_obj = db.query(VeiculoDespesa).filter_by(
                                    id_despesa_veiculo=desp_veic_cancel_id, cancelado=False,
                                    id_despesa_viagem_destino=None, id_despesa_ciclo_destino=None,
                                ).with_for_update().first()
                                if pendente_obj:
                                    pendente_obj.cancelado = True
                                    pendente_obj.data_cancelamento = date.today()
                                    pendente_obj.motivo_cancelamento = motivo_veic_cancel.strip()
                                    for ab in db.query(Abastecimento).filter_by(id_despesa_veiculo=desp_veic_cancel_id).all():
                                        ab.cancelado = True
                                        ab.data_cancelamento = date.today()
                                        ab.motivo_cancelamento = motivo_veic_cancel.strip()
                                    db.commit()
                                    limpar_caches_atribuicao()
                                    st.toast("Despesa provisória cancelada, mantendo histórico.", icon="🧾")
                                    st.rerun()

            if despesas_atribuidas:
                with st.expander("↩️ Estornar atribuição e devolver a pendente", expanded=False):
                    estornar_id = st.selectbox(
                        "DESPESA ATRIBUÍDA *", options=list(despesas_atribuidas),
                        format_func=lambda x: (
                            f"#{x} — {fmt_brl(despesas_atribuidas[x]['valor_total'])} "
                            f"— {'Frete' if despesas_atribuidas[x]['id_despesa_viagem_destino'] else 'Ciclo'}"
                        ), key="estornar_desp_veiculo_id",
                    )
                    estornar_motivo = st.text_input(
                        "JUSTIFICATIVA DO ESTORNO *", max_chars=200,
                        key="estornar_desp_motivo",
                    )
                    st.caption(
                        "O custo deixará o resultado do destino e voltará a ficar pendente "
                        "no veículo. O histórico operacional de abastecimento não será "
                        "duplicado. A movimentação será registrada para auditoria."
                    )
                    if st.button("Confirmar Estorno da Atribuição", key="estornar_desp_confirmar"):
                        try:
                            with SessionLocal() as db:
                                estornar_atribuicao_veiculo(db, estornar_id, estornar_motivo)
                                db.commit()
                        except ValueError as exc:
                            st.warning(str(exc))
                        except Exception:
                            st.error("Não foi possível estornar a atribuição. Nenhuma mudança foi confirmada.")
                        else:
                            limpar_caches_atribuicao()
                            st.toast("Atribuição estornada; despesa voltou a pendente!", icon="✅")
                            st.rerun()

            historico_movimentacoes = carregar_historico_atribuicoes_veiculo()
            if historico_movimentacoes:
                st.markdown("**Histórico de atribuições e estornos**")
                st.dataframe(pd.DataFrame([
                    {
                        "Data e Hora": e["data_evento"].strftime("%d/%m/%Y %H:%M"),
                        "ID Despesa Veículo": e["id_despesa_veiculo"],
                        "Ação": e["acao"],
                        "Destino": e["tipo_destino"],
                        "ID Frete/Ciclo Interno": e["id_destino"],
                        "ID Lançamento no Destino": e["id_lancamento_destino"],
                        "Justificativa": e["motivo"],
                    }
                    for e in reversed(historico_movimentacoes)
                ]), hide_index=True, use_container_width=True)
        else:
            st.info("Nenhuma despesa provisória vinculada a veículos.")

    with st.expander("⛽ Histórico de abastecimentos e consumo (somente consulta)", expanded=False):
        st.caption(
            "Não é necessário lançar combustível aqui. Cada abastecimento aparece quando "
            "a despesa de Diesel ou ARLA é registrada acima, com veículo e odômetro. "
            "A tabela operacional não acrescenta valor ao DRE."
        )
        if not veiculos_destino:
            st.info("Cadastre um veículo na Etapa 11 para obter o histórico.")
        else:
            consulta_veic_id = st.selectbox(
                "VEÍCULO PARA CONSULTA", options=list(veiculos_destino),
                format_func=lambda x: veiculos_destino[x], key="desp_historico_veiculo",
            )
            abast_historico = carregar_abastecimentos_veiculo(consulta_veic_id)
            if not abast_historico:
                st.info("Nenhum abastecimento registrado para este veículo.")
            else:
                st.dataframe(pd.DataFrame([
                    {
                        "Data": a["data_abastecimento"].strftime("%d/%m/%Y"),
                        "Combustível": a["tipo_combustivel"],
                        "Odômetro (km)": a["odometro"],
                        "Litros": a["litros"],
                        "Valor (R$)": a["valor_total"],
                        "KM entre Diesel": a["km_intervalo"],
                        "KM/L (indicativo)": a["km_por_litro"],
                        "R$/KM (indicativo)": a["custo_por_km"],
                        "Origem": a["origem_financeira"],
                        "Situação": "Cancelado" if a["cancelado"] else "Ativo",
                        "Observação": a["observacao"],
                    }
                    for a in reversed(abast_historico)
                ]), hide_index=True, use_container_width=True)
                st.caption(
                    "KM/L e R$/KM são apenas indicadores entre dois registros consecutivos "
                    "de Diesel do mesmo veículo. Abastecimentos parciais, registros faltantes "
                    "ou odômetros inconsistentes não permitem afirmar consumo real; "
                    "ARLA não entra no KM/L."
                )

    with st.expander("Histórico de edições de despesas"):
        with SessionLocal() as db:
            edicoes = consultar_edicoes(db, limite=30)
        if edicoes:
            st.caption("Campos alterados nas últimas 30 edições.")
            st.dataframe(pd.DataFrame(edicoes), hide_index=True, use_container_width=True)
        else:
            st.info("Nenhuma despesa salva foi editada.")

    render_navegacao_rodape(6, MENU_ITENS)
