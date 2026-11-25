"""Painel de saídas operacionais da Etapa 8, sem mudar o fluxo de fretes.

Somente salva se o usuário acionar o botão. Nenhuma migração de histórico.
"""
from datetime import date

import pandas as pd
import streamlit as st

from database.connection import SessionLocal
from database.models import ParametroConsumoVeiculo, TrechoOperacional, Viagem
from database.saidas_operacionais import (
    consultar_saidas, estimativas_por_veiculo, resumo_saidas,
    salvar_saida, salvar_trecho,
)


def _valor(val, default=0.0):
    return float(val) if val is not None else default


def render_saidas_operacionais(id_ciclo, veiculos, motoristas, *, exibir_formulario=True):
    """Retorna resumo válido ou None quando não há saídas no ciclo.

    A navegação segue dentro da Etapa 8; cada saída é compartilhada pelos fretes
    do mesmo ID interno. Usar odômetro de abastecimento para consumo histórico,
    nunca como início/fim automáticos de uma saída.
    """
    with SessionLocal() as db:
        saidas = consultar_saidas(db, id_ciclo)
        resumo = resumo_saidas(saidas)
        saidas_dados = [{
            "id": s.id_saida,
            "descricao": s.descricao,
            "data_inicio": s.data_inicio,
            "data_fim": s.data_fim,
            "id_veiculo": s.id_veiculo,
            "id_motorista": s.id_motorista,
            "km_manual": _valor(s.km_planejado_manual),
            "km_planejado": sum(_valor(t.km_planejado) for t in s.trechos) if s.trechos else _valor(s.km_planejado_manual),
            "odo_ini": s.odometro_inicial, "odo_fim": s.odometro_final,
            "obs": s.observacoes,
            "trechos": [{"id": t.id_trecho, "tipo": t.tipo_trecho, "origem": t.origem,
                        "destino": t.destino, "km": _valor(t.km_planejado), "obs": t.observacoes}
                       for t in s.trechos],
        } for s in saidas]
        estimativas, avisos_consumo = estimativas_por_veiculo(db, resumo)
        parametros = {p.id_veiculo: (_valor(p.km_por_litro), _valor(p.preco_litro_referencia))
                      for p in db.query(ParametroConsumoVeiculo).all()}

    st.markdown("#### Saídas e trechos da operação")
    st.caption(
        "Registre cada saída real da base — inclusive coletas preparatórias, entregas e retorno. "
        "Os quilômetros são da operação, e NÃO de um frete isolado. "
        "Os registros antigos de KM e despesas não são alterados automaticamente."
    )
    if saidas_dados:
        st.dataframe(pd.DataFrame([{
            "Saída": s["descricao"],
            "Data início": s["data_inicio"],
            "Data fim": s["data_fim"],
            "Placa": next((v["placa"] for v in veiculos if v["id_veiculo"] == s["id_veiculo"]), "-"),
            "KM planejado (trechos ou manual)": s["km_planejado"],
            "Odômetro inicial": s["odo_ini"],
            "Odômetro final": s["odo_fim"],
            "KM real": (s["odo_fim"] - s["odo_ini"]) if s["odo_ini"] is not None and s["odo_fim"] is not None else None,
            "Trechos": len(s["trechos"]),
        } for s in saidas_dados]), use_container_width=True, hide_index=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("Saídas registradas", resumo["qtd_saidas"])
        c2.metric("KM planejado operacional", f'{resumo["km_planejado"]:.2f} km')
        c3.metric("KM real operacional", f'{resumo["km_real"]:.0f} km' if resumo["km_real"] is not None else "Pendente")
        for aviso in resumo["avisos"]:
            st.warning(aviso)
        if not resumo["completo"]:
            st.caption("A soma dos odômetros informados até agora é parcial; não é usada para calcular desvio ou custo por KM.")
    else:
        st.info("Nenhuma saída operacional cadastrada. O fechamento continua exibindo o cálculo anterior até que você cadastre uma saída.")

    if not exibir_formulario:
        return resumo if resumo["qtd_saidas"] else None

    with st.expander("Cadastrar ou corrigir saída operacional", expanded=False):
        if not veiculos:
            st.warning("Cadastre um veículo antes de registrar uma saída.")
        else:
            opcoes = {0: "Nova saída"}
            opcoes.update({s["id"]: f'Editar saída {s["id"]} — {s["descricao"]}' for s in saidas_dados})
            escolha = st.selectbox("REGISTRO", list(opcoes), format_func=opcoes.get,
                                   key=f"faeg_saida_escolha_{id_ciclo}")
            atual = next((s for s in saidas_dados if s["id"] == escolha), None)
            veic_ids = [v["id_veiculo"] for v in veiculos]
            mot_ids = [None] + [m["id_motorista"] for m in motoristas]
            with st.form(f"faeg_saida_form_{id_ciclo}_{escolha}"):
                descricao = st.text_input("DESCRIÇÃO DA SAÍDA *", value=atual["descricao"] if atual else "",
                                          placeholder="Coletas preparatórias / Entregas / Retorno")
                c1, c2 = st.columns(2)
                id_veiculo = c1.selectbox("VEÍCULO *", veic_ids,
                    index=veic_ids.index(atual["id_veiculo"]) if atual and atual["id_veiculo"] in veic_ids else 0,
                    format_func=lambda vid: next((f'{v["placa"]} — {v["descricao_marca"]}' for v in veiculos if v["id_veiculo"] == vid), str(vid)))
                id_motorista = c2.selectbox("MOTORISTA", mot_ids,
                    index=mot_ids.index(atual["id_motorista"]) if atual and atual["id_motorista"] in mot_ids else 0,
                    format_func=lambda mid: next((m["nome_completo"] for m in motoristas if m["id_motorista"] == mid), "Não informado") if mid else "Não informado")
                c3, c4 = st.columns(2)
                data_inicio = c3.date_input("DATA DE INÍCIO", value=atual["data_inicio"] if atual else date.today(), format="DD/MM/YYYY")
                data_fim = c4.date_input("DATA DE ENCERRAMENTO", value=atual["data_fim"] if atual else None, format="DD/MM/YYYY")
                c5, c6, c7 = st.columns(3)
                km_plano = c5.number_input("KM PLANEJADO DA SAÍDA", min_value=0.0, step=1.0, format="%.2f",
                                           value=atual["km_manual"] if atual else 0.0,
                                           help="Use este valor quando não registrar os trechos detalhados. Se houver trechos, a soma deles prevalece.")
                odo_ini = c6.number_input("ODÔMETRO INICIAL", min_value=0, step=1,
                                           value=atual["odo_ini"] if atual and atual["odo_ini"] is not None else 0)
                odo_fim = c7.number_input("ODÔMETRO FINAL", min_value=0, step=1,
                                           value=atual["odo_fim"] if atual and atual["odo_fim"] is not None else 0)
                st.caption("Odômetro zero significa não informado; deixe o final vazio/zero enquanto a saída estiver em andamento.")
                obs = st.text_area("OBSERVAÇÕES DA SAÍDA", value=atual["obs"] or "" if atual else "")
                submitted = st.form_submit_button("Salvar saída operacional", type="primary")
            if submitted:
                try:
                    with SessionLocal() as db:
                        salvar_saida(db, id_ciclo=id_ciclo, id_saida=atual["id"] if atual else None,
                                    id_veiculo=id_veiculo, id_motorista=id_motorista,
                                    descricao=descricao, data_inicio=data_inicio, data_fim=data_fim,
                                    odometro_inicial=odo_ini or None, odometro_final=odo_fim or None,
                                    km_planejado_manual=km_plano, observacoes=obs)
                        db.commit()
                    st.success("Saída salva. Os registros anteriores de frete continuam preservados.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Não foi possível salvar a saída: {exc}")

    if saidas_dados:
        with st.expander("Cadastrar/corrigir trechos e paradas", expanded=False):
            by_id = {s["id"]: s for s in saidas_dados}
            sid = st.selectbox("SAÍDA", list(by_id),
                format_func=lambda n: f'{n} — {by_id[n]["descricao"]}', key=f"faeg_trecho_saida_{id_ciclo}")
            s_atual = by_id[sid]
            opts = {0: "Novo trecho"}
            opts.update({t["id"]: f'{t["tipo"]}: {t["origem"]} → {t["destino"]}' for t in s_atual["trechos"]})
            tid = st.selectbox("TRECHO", list(opts), format_func=opts.get,
                               key=f"faeg_trecho_escolha_{id_ciclo}_{sid}")
            t_atual = next((t for t in s_atual["trechos"] if t["id"] == tid), None)
            with st.form(f"faeg_trecho_form_{id_ciclo}_{sid}_{tid}"):
                tipos = ["Saída da base", "Coleta", "Entrega", "Entre paradas", "Retorno à base", "Outros"]
                tipo = st.selectbox("TIPO DE TRECHO", tipos,
                    index=tipos.index(t_atual["tipo"]) if t_atual and t_atual["tipo"] in tipos else 0)
                tc1, tc2 = st.columns(2)
                origem = tc1.text_input("ORIGEM *", value=t_atual["origem"] if t_atual else "")
                destino = tc2.text_input("DESTINO *", value=t_atual["destino"] if t_atual else "")
                km_trecho = st.number_input("KM PLANEJADO DESTE TRECHO", min_value=0.0,
                    value=t_atual["km"] if t_atual else 0.0, step=1.0, format="%.2f")
                obs_trecho = st.text_input("OBSERVAÇÃO", value=t_atual["obs"] or "" if t_atual else "")
                salvar_tr = st.form_submit_button("Salvar trecho", type="primary")
            if salvar_tr:
                try:
                    with SessionLocal() as db:
                        salvar_trecho(db, id_saida=sid, id_trecho=tid or None,
                                     tipo_trecho=tipo, origem=origem, destino=destino,
                                     km_planejado=km_trecho, observacoes=obs_trecho)
                        db.commit()
                    st.rerun()
                except Exception as exc:
                    st.error(f"Não foi possível salvar trecho: {exc}")
            if t_atual:
                confirm = st.checkbox("Confirmo que desejo remover este trecho (não remove a saída)",
                                      key=f"faeg_confirm_del_trecho_{tid}")
                if st.button("Remover trecho", disabled=not confirm, key=f"faeg_del_trecho_{tid}"):
                    with SessionLocal() as db:
                        registro = db.get(TrechoOperacional, tid)
                        if registro is not None and registro.id_saida == sid:
                            db.delete(registro)
                            db.commit()
                    st.rerun()
            st.caption("Se houver trechos, a soma dos quilômetros deles substitui o KM manual da saída no fechamento — nunca se somam os dois.")

    if estimativas:
        st.dataframe(pd.DataFrame([{
            "Veículo": next((v["placa"] for v in veiculos if v["id_veiculo"] == e["id_veiculo"]), e["id_veiculo"]),
            "KM real da operação": e["km"],
            "Litros estimados": e["litros_estimados"],
            "Custo estimado (R$) — NÃO SOMAR À DRE": e["custo_estimado"],
        } for e in estimativas]), hide_index=True, use_container_width=True)
    for av in avisos_consumo:
        st.caption(av)
    return resumo if resumo["qtd_saidas"] else None
