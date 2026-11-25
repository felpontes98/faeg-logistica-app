"""Etapa 7 da interface FAEG (corpo original, sem reescrever regras)."""
import pandas as pd
import streamlit as st
import zlib

from database.atribuicao_despesas import atribuir_despesa_veiculo, estornar_atribuicao_veiculo
from database.conferencia_duplicidades import procurar_semelhancas_cruzadas
from database.connection import SessionLocal
from database.models import Abastecimento, CicloDespesa, CicloOperacional, VeiculoDespesa, Viagem, ViagemDespesa
from datetime import date
from faeg_app.core import (
    CATEGORIAS_DESPESA_FORNECEDOR,
    carregar_abastecimentos_veiculo,
    carregar_alertas_despesas_cruzadas,
    carregar_despesas_viagem,
    carregar_historico_atribuicoes_veiculo,
    carregar_todas_despesas_ciclo,
    carregar_todas_despesas_veiculo,
    carregar_todas_viagens_consulta,
    carregar_todos_abastecimentos,
    exibir_indicadores,
    fmt_brl,
    get_campo,
    limpar_caches_atribuicao,
    localizar_ciclo_operacional,
    registrar_abastecimento_do_lancamento,
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

    st.info(
        "Um único lançamento para qualquer despesa, inclusive Diesel/ARLA. "
        "Selecione abaixo se pertence ao frete, ao ciclo inteiro ou provisoriamente "
        "ao veículo. O histórico de consumo é preenchido pelo mesmo registro de combustível, "
        "sem cadastrar o gasto novamente."
    )

    st.markdown('<div class="sec-subtitle">Adicionar Nova Despesa</div>', unsafe_allow_html=True)

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
    opcoes_destino = ["Frete atual (ID Frete)"]
    if ciclos_destino or get_campo("tipo_viagem", "Individual") == "Ciclo":
        opcoes_destino.append("Ciclo inteiro (ID Ciclo)")
    if veiculos_destino:
        opcoes_destino.append("Veículo (sem frete/ciclo definido)")
    st.markdown("**Vínculo financeiro**")
    # O destino habitual de gastos comuns é o ciclo (se o frete já estiver salvo).
    # O usuário pode selecionar explicitamente o frete para custos exclusivos.
    destino_padrao = (
        "Ciclo inteiro (ID Ciclo)"
        if get_campo("tipo_viagem", "Individual") == "Ciclo"
        and "Ciclo inteiro (ID Ciclo)" in opcoes_destino
        else "Frete atual (ID Frete)"
    )
    if st.session_state.get("desp_destino_viagem_anterior") != viagem_sel_id:
        st.session_state["desp_destino_lancamento"] = destino_padrao
        st.session_state["desp_destino_viagem_anterior"] = viagem_sel_id
    destino_desp = st.selectbox(
        "DESTINO DO CUSTO *", opcoes_destino,
        index=opcoes_destino.index(destino_padrao),
        key="desp_destino_lancamento",
        help="No ciclo, gastos comuns pertencem à operação. Use o ID Frete somente para custos comprovadamente exclusivos.",
    )
    ciclo_desp_id = None
    veiculo_desp_id = None
    if destino_desp.startswith("Ciclo inteiro"):
        # Mostrar a identificação comercial; o ID interno não é necessário
        # para quem cadastra a despesa. Nunca vincular a outro ciclo por engano.
        if get_campo("tipo_viagem", "Individual") == "Ciclo" and (get_campo("ciclo_nome") or "").strip():
            nome_atual = (get_campo("ciclo_nome") or "").strip()
            ids_iguais = [cid for cid, nome in ciclos_destino.items()
                          if nome.strip().casefold() == nome_atual.casefold()]
            ciclo_desp_id = ids_iguais[0] if len(ids_iguais) == 1 else None
            st.caption(f"Despesa compartilhada da operação: **{nome_atual}**")
            if len(ids_iguais) > 1:
                st.error("Há ciclos com nomes repetidos; confira a operação antes de lançar despesas.")
            if viagem_sel_id == 0:
                st.caption("Este custo permanecerá no rascunho até o frete ser salvo.")
        elif ciclos_destino:
            ciclo_desp_id = st.selectbox(
                "CICLO QUE RECEBERÁ ESTE CUSTO *", options=list(ciclos_destino),
                format_func=lambda x: ciclos_destino[x], key="desp_ciclo_destino_unico",
            )
        else:
            st.warning("Informe o nome do ciclo na Etapa 1 para vincular esta despesa.")
    elif destino_desp.startswith("Veículo"):
        veiculo_desp_id = st.selectbox(
            "VEÍCULO / PLACA *", options=list(veiculos_destino),
            format_func=lambda x: veiculos_destino[x], key="desp_veiculo_destino_unico",
        )

    # Um só formulário: vínculo, dados financeiros e complemento operacional.
    st.markdown("**Dados da despesa**")
    # Os campos de digitação são reiniciados somente após lançar com sucesso.
    # Categoria, fornecedor, vínculo e data permanecem para lançamentos em sequência.
    versao_campos_despesa = st.session_state.get("versao_campos_despesa", 0)
    c_d1, c_d2, c_d3 = st.columns([2.1, 2.5, 2.1])
    with c_d1:
        tipo_desp = st.selectbox("TIPO DE DESPESA", CATEGORIAS_DESPESA_FORNECEDOR, key="desp_tipo")
    with c_d2:
        desc_desp = st.text_input(
            "DESCRIÇÃO / LOCAL",
            placeholder="Ex: Abastecimento KM 120 / Pedágio",
            key=f"desp_desc_{versao_campos_despesa}",
        )
    with c_d3:
        forn_ops = {0: "Não informado"}
        for f in fornecedores_db:
            forn_ops[f["id_fornecedor"]] = f"{f['nome_fantasia']} ({f['categoria_servico']})"
        forn_sel = st.selectbox(
            "FORNECEDOR / POSTO",
            options=list(forn_ops.keys()),
            format_func=lambda x: forn_ops[x],
            key="desp_forn",
        )

    eh_combustivel = tipo_desp in {"Posto de Combustível", "Abast. ARLA"}
    if eh_combustivel:
        st.caption("Abastecimento: litros, preço e odômetro no mesmo lançamento financeiro.")
    # Sem campos vazios em despesas que não são combustível.
    colunas_valores = st.columns([1.3, 1.4, 1.6] if eh_combustivel else [1, 1])
    c_d4, c_d5 = colunas_valores[:2]
    with c_d4:
        qtd_desp = st.number_input("LITROS *" if eh_combustivel else "QUANTIDADE *", min_value=0.01, value=1.00, step=1.0, format="%.2f", key=f"desp_qtd_{versao_campos_despesa}")
    with c_d5:
        unit_desp = st.number_input("PREÇO / LITRO (R$) *" if eh_combustivel else "UNITÁRIO (R$) *", min_value=0.00, value=0.00, step=0.1 if eh_combustivel else 10.0, format="%.4f" if eh_combustivel else "%.2f", key=f"desp_unit_{versao_campos_despesa}")
    if eh_combustivel:
        c_d6 = colunas_valores[2]
        with c_d6:
            odometro_digitado = st.number_input(
                "ODÔMETRO NO ABASTECIMENTO (KM)", min_value=0, value=0,
                step=1, key=f"desp_odometro_abastecimento_{versao_campos_despesa}",
                help="Digite diretamente a leitura do painel. Deixe 0 para não informado.",
            )
    else:
        odometro_digitado = 0
    odometro_abast = int(odometro_digitado) if odometro_digitado > 0 else None

    veiculo_abast_id = veiculo_desp_id
    if eh_combustivel and destino_desp.startswith("Frete"):
        veiculo_abast_id = get_campo("vei_id", 0)
        st.caption(
            "Abastecimento do veículo do frete atual: "
            + veiculos_destino.get(veiculo_abast_id, "veículo ainda não selecionado na Etapa 1")
        )
    elif eh_combustivel and destino_desp.startswith("Ciclo"):
        veiculo_abast_id = st.selectbox(
            "VEÍCULO QUE FOI ABASTECIDO *", options=list(veiculos_destino),
            format_func=lambda x: veiculos_destino[x], key="desp_veiculo_abast_ciclo",
            index=list(veiculos_destino).index(get_campo("vei_id", 0)) if get_campo("vei_id", 0) in veiculos_destino else 0,
        ) if veiculos_destino else None

    data_despesa_unica = st.date_input(
        "DATA DO ABASTECIMENTO *" if eh_combustivel else "DATA DA DESPESA *",
        value=date.today(), format="DD/MM/YYYY", key="desp_data_unica",
    )
    total_previsto_desp = round(qtd_desp * unit_desp, 2)
    st.markdown(f"**VALOR TOTAL DESTE LANÇAMENTO: {fmt_brl(total_previsto_desp)}**")
    if destino_desp.startswith("Veículo"):
        st.caption("Este gasto permanecerá pendente por veículo e NÃO comporá o resultado de fretes/ciclos até uma vinculação explícita futura.")
    elif destino_desp.startswith("Ciclo"):
        st.caption("Este custo será contabilizado uma única vez no resultado do ciclo, sem rateio por frete.")

    # Um indício de repetição entre frete e ciclo exige conferência explícita,
    # sem apagar, atribuir ou bloquear definitivamente gastos legítimos.
    possiveis_duplicidades = []
    confirmar_despesa_distinta = True
    if total_previsto_desp > 0 and not destino_desp.startswith("Veículo"):
        dados_conferencia = {
            "tipo_despesa": tipo_desp,
            "descricao_detalhe": desc_desp.strip() or tipo_desp,
            "id_fornecedor": forn_sel or None,
            "data_despesa": data_despesa_unica,
            "quantidade": round(qtd_desp, 2),
            "valor_unitario": round(unit_desp, 4 if eh_combustivel else 2),
            "valor_total": total_previsto_desp,
            "odometro_abastecimento": odometro_abast,
            "id_veiculo_abast": veiculo_abast_id,
        }
        with SessionLocal() as db:
            if destino_desp.startswith("Ciclo"):
                id_ciclo_conferencia = ciclo_desp_id
                tipo_conferencia = "Ciclo"
            else:
                tipo_conferencia = "Frete"
                if viagem_sel_id:
                    id_ciclo_conferencia = db.query(Viagem.id_ciclo).filter_by(
                        id_viagem=viagem_sel_id,
                    ).scalar()
                elif get_campo("tipo_viagem", "Individual") == "Ciclo":
                    ciclo_conferencia = localizar_ciclo_operacional(
                        db, get_campo("ciclo_nome", "") or "",
                    )
                    id_ciclo_conferencia = (
                        ciclo_conferencia.id_ciclo if ciclo_conferencia else None
                    )
                else:
                    id_ciclo_conferencia = None
            possiveis_duplicidades = procurar_semelhancas_cruzadas(
                db, tipo_conferencia, id_ciclo_conferencia, dados_conferencia,
            )
        if possiveis_duplicidades:
            referencias = ", ".join(
                f"{item['origem']} (despesa #{item['id_lancamento']})"
                for item in possiveis_duplicidades[:4]
            )
            st.warning(
                "Existe lançamento semelhante em outro destino financeiro deste ciclo: "
                f"{referencias}. Confira nota/comprovante, veículo e a natureza do custo. "
                "Pode ser despesa distinta; o sistema não faz alteração automática."
            )
            chave_confirmacao = zlib.crc32(
                repr((dados_conferencia, tipo_conferencia, id_ciclo_conferencia,
                      tuple((d["origem"], d["id_lancamento"]) for d in possiveis_duplicidades))).encode()
            )
            confirmar_despesa_distinta = st.checkbox(
                "Conferi o comprovante: este é um gasto distinto, não um segundo lançamento do mesmo custo.",
                key=f"desp_similar_confirmar_{chave_confirmacao}_{st.session_state.get('desp_similar_versao', 0)}",
            )
    btn_add_desp = st.button("Registrar Despesa", use_container_width=True, key="btn_add_despesa")

    if btn_add_desp:
        if possiveis_duplicidades and not confirmar_despesa_distinta:
            st.warning("Confirme primeiro a conferência do comprovante para evitar contagem duplicada.")
        elif unit_desp <= 0:
            st.warning("Informe um valor unitário maior que R$ 0,00.")
        elif eh_combustivel and not veiculo_abast_id:
            st.warning("Selecione primeiro o veículo correto para registrar o abastecimento.")
        else:
            v_tot_item = round(qtd_desp * unit_desp, 2)
            dados_desp = {
                "id_fornecedor": forn_sel or None,
                "tipo_despesa": tipo_desp,
                "descricao_detalhe": desc_desp.strip() or tipo_desp,
                "quantidade": round(qtd_desp, 2),
                "valor_unitario": round(unit_desp, 4 if eh_combustivel else 2),
                "valor_total": v_tot_item,
                "odometro_abastecimento": odometro_abast,
                "data_despesa": data_despesa_unica,
                "id_veiculo_abast": veiculo_abast_id if eh_combustivel else None,
            }
            if viagem_sel_id == 0 and (destino_desp.startswith("Frete") or destino_desp.startswith("Ciclo")):
                dados_desp["destino_temp"] = "ciclo" if destino_desp.startswith("Ciclo") else "frete"
                pendentes = st.session_state.setdefault("despesas_temp", [])
                chaves_duplicidade_temp = (
                    "tipo_despesa", "data_despesa", "quantidade", "valor_total",
                    "odometro_abastecimento", "id_veiculo_abast",
                ) if eh_combustivel else (
                    "tipo_despesa", "data_despesa", "quantidade", "valor_total",
                    "descricao_detalhe", "id_fornecedor",
                )
                ja_existe = any(
                    all(d.get(k) == dados_desp[k] for k in (
                        chaves_duplicidade_temp
                    )) for d in pendentes
                )
                if ja_existe:
                    st.warning("Esta despesa já está nos lançamentos provisórios.")
                    st.stop()
                pendentes.append(dados_desp)
                st.session_state["versao_campos_despesa"] = versao_campos_despesa + 1
                st.session_state["desp_similar_versao"] = st.session_state.get("desp_similar_versao", 0) + 1
                st.toast("Despesa registrada no preenchimento atual. Salve o rascunho ou o frete.", icon="🧾")
                st.rerun()
            else:
                with SessionLocal() as db:
                    if destino_desp.startswith("Frete"):
                        consulta_existente = db.query(ViagemDespesa).filter_by(
                            id_viagem=viagem_sel_id,
                            tipo_despesa=tipo_desp,
                            data_despesa=data_despesa_unica,
                            quantidade=dados_desp["quantidade"],
                            valor_total=v_tot_item,
                        )
                        if eh_combustivel:
                            consulta_existente = consulta_existente.filter_by(
                                odometro_abastecimento=odometro_abast,
                            )
                        else:
                            consulta_existente = consulta_existente.filter_by(
                                descricao_detalhe=dados_desp["descricao_detalhe"],
                                id_fornecedor=dados_desp["id_fornecedor"],
                            )
                        existente = consulta_existente.first()
                        if existente:
                            st.warning(
                                "Esta despesa já consta neste frete. Se forem gastos "
                                "distintos, diferencie a descrição/comprovante antes de registrar."
                            )
                            st.stop()
                        desp_obj = ViagemDespesa(
                            id_viagem=viagem_sel_id,
                            id_fornecedor=forn_sel if forn_sel != 0 else None,
                            tipo_despesa=tipo_desp,
                            descricao_detalhe=desc_desp.strip() or tipo_desp,
                            quantidade=round(qtd_desp, 2),
                            valor_unitario=dados_desp["valor_unitario"],
                            valor_total=v_tot_item,
                            odometro_abastecimento=odometro_abast,
                            data_despesa=data_despesa_unica,
                        )
                        db.add(desp_obj)
                        db.flush()
                        origem_campo, origem_id = "id_despesa_viagem", desp_obj.id_despesa
                    elif destino_desp.startswith("Ciclo"):
                        existente = db.query(CicloDespesa).filter_by(
                            id_ciclo=ciclo_desp_id,
                            tipo_despesa=tipo_desp,
                            descricao_detalhe=dados_desp["descricao_detalhe"],
                            data_despesa=data_despesa_unica,
                            valor_total=v_tot_item,
                            cancelado=False,
                        ).first()
                        if existente:
                            st.warning("Esta despesa já consta no ciclo. Confira antes de registrá-la novamente.")
                            st.stop()
                        desp_obj = CicloDespesa(id_ciclo=ciclo_desp_id, **{
                            k: dados_desp[k] for k in (
                                "id_fornecedor", "tipo_despesa", "descricao_detalhe",
                                "quantidade", "valor_unitario", "valor_total", "data_despesa",
                            )
                        })
                        db.add(desp_obj)
                        db.flush()
                        origem_campo, origem_id = "id_despesa_ciclo", desp_obj.id_despesa_ciclo
                    else:
                        existente = db.query(VeiculoDespesa).filter_by(
                            id_veiculo=veiculo_desp_id,
                            tipo_despesa=tipo_desp,
                            descricao_detalhe=dados_desp["descricao_detalhe"],
                            data_despesa=data_despesa_unica,
                            valor_total=v_tot_item,
                            cancelado=False,
                        ).first()
                        if existente:
                            st.warning("Esta despesa já está pendente para este veículo.")
                            st.stop()
                        desp_obj = VeiculoDespesa(id_veiculo=veiculo_desp_id, **{
                            k: dados_desp[k] for k in (
                                "id_fornecedor", "tipo_despesa", "descricao_detalhe",
                                "quantidade", "valor_unitario", "valor_total", "data_despesa",
                            )
                        })
                        db.add(desp_obj)
                        db.flush()
                        origem_campo, origem_id = "id_despesa_veiculo", desp_obj.id_despesa_veiculo
                    registrar_abastecimento_do_lancamento(db, dados_desp, origem_campo, origem_id)
                    db.commit()
                st.session_state["versao_campos_despesa"] = versao_campos_despesa + 1
                carregar_despesas_viagem.clear()
                carregar_todas_viagens_consulta.clear()
                carregar_todas_despesas_ciclo.clear()
                carregar_todas_despesas_veiculo.clear()
                carregar_alertas_despesas_cruzadas.clear()
                carregar_todos_abastecimentos.clear()
                carregar_abastecimentos_veiculo.clear()
                st.session_state["desp_similar_versao"] = st.session_state.get("desp_similar_versao", 0) + 1
                st.toast("Despesa registrada uma única vez no destino escolhido!", icon="✅")
                st.rerun()

    st.markdown('<div class="sec-subtitle">Despesas Lançadas na Viagem</div>', unsafe_allow_html=True)
    forn_map = {f["id_fornecedor"]: f["nome_fantasia"] for f in fornecedores_db}

    if viagem_sel_id == 0:
        lista_desp_atual = [
            {
                "idx": idx,
                "id_despesa": None,
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
                f"**{item['tipo_despesa']}**  \n<span style='font-size:0.78rem;color:#64748B;'>{item['fornecedor']}</span>",
                unsafe_allow_html=True,
            )
            col_t2.markdown(f"{item['descricao_detalhe']}")
            if item.get("data_despesa"):
                data_tipo_rotulo = "Data do abastecimento" if item["tipo_despesa"] in {"Posto de Combustível", "Abast. ARLA"} else "Data da despesa"
                col_t2.caption(f"{data_tipo_rotulo}: {item['data_despesa'].strftime('%d/%m/%Y')}")
            if item.get("odometro_abastecimento") is not None:
                col_t2.caption(f"Odômetro no abastecimento: {item['odometro_abastecimento']} km")
            col_t3.markdown(f"{item['quantidade']:.2f} × {fmt_brl(item['valor_unitario'])}")
            col_t4.markdown(f"**{fmt_brl(item['valor_total'])}**")
            if col_t5.button("🗑️", key=f"del_desp_{viagem_sel_id}_{item['idx']}", help="Remover despesa"):
                if viagem_sel_id == 0:
                    st.session_state["despesas_temp"].pop(item["idx"])
                    st.rerun()
                else:
                    with SessionLocal() as db:
                        obj_d = db.query(ViagemDespesa).filter_by(id_despesa=item["id_despesa"]).first()
                        if obj_d:
                            origem_provisoria = db.query(VeiculoDespesa).filter_by(
                                id_despesa_viagem_destino=obj_d.id_despesa
                            ).first()
                            if origem_provisoria:
                                st.warning(
                                    "Esta despesa veio de um veículo. Para corrigir, use "
                                    "'Estornar atribuição' no histórico de despesas do veículo, "
                                    "preservando a rastreabilidade."
                                )
                            else:
                                # Abastecimento derivado sai junto com o custo
                                # removido; não deixar medição órfã no histórico.
                                db.query(Abastecimento).filter_by(
                                    id_despesa_viagem=obj_d.id_despesa
                                ).delete(synchronize_session=False)
                                db.delete(obj_d)
                                db.commit()
                                limpar_caches_atribuicao()
                                st.toast("Despesa removida!", icon="🗑️")
                                st.rerun()

        st.markdown(
            f"""
                <div class="faeg-recebimento-banner" style="border-left-color:#F34D25;">
                    <span class="faeg-recebimento-label">Custo Total Acumulado na Viagem:</span>
                    <span class="faeg-recebimento-val" style="color:#F34D25;">{fmt_brl(soma_desp)}</span>
                </div>
                """,
            unsafe_allow_html=True,
        )

    with st.expander("🧾 Histórico das despesas compartilhadas dos ciclos (consulta/cancelamento)", expanded=False):
        st.caption(
            "Para NOVOS lançamentos, use apenas 'Adicionar Nova Despesa' acima, "
            "selecionando 'Ciclo inteiro'. Esta área permite conferir e cancelar lançamentos."
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
                    with st.expander("Corrigir lançamento compartilhado (mantendo histórico)"):
                        opcoes_cancelar_dc = {d["id_despesa_ciclo"]: d for d in ativas_ciclo}
                        dc_cancel_id = st.selectbox(
                            "DESPESA A CANCELAR", options=list(opcoes_cancelar_dc),
                            format_func=lambda x: f"#{x} — {fmt_brl(opcoes_cancelar_dc[x]['valor_total'])}",
                            key="desp_ciclo_cancel_id",
                        )
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
                                    ).first()
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
            "Registre novas despesas SOMENTE no formulário acima. Aqui é possível "
            "vincular uma despesa provisória a frete/ciclo salvo ou estornar a atribuição. "
            "O histórico original e o abastecimento do veículo são preservados."
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

    render_navegacao_rodape(6, MENU_ITENS)
