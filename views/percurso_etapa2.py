"""Cadastro único das saídas na Etapa 2, para individual e ciclo.

Nunca soma KM de fretes; uma saída pertence à operação física, independentemente
quantos serviços comerciais compartilhem o veículo e o percurso.
"""
from datetime import date
from uuid import uuid4

import pandas as pd
import streamlit as st

from database.connection import SessionLocal
from database.models import Viagem
from database.saidas_operacionais import consultar_saidas, resumo_saidas, salvar_saida, validar_saida
from faeg_app.core import get_campo


def _as_float(value):
    return float(value or 0)


def _obter_contexto(viagem_id):
    if not viagem_id:
        return None, []
    with SessionLocal() as db:
        viagem = db.get(Viagem, viagem_id)
        if not viagem:
            return None, []
        cid = viagem.id_ciclo
        saidas = consultar_saidas(db, cid)
        return cid, [{
            "id": s.id_saida,
            "descricao": s.descricao,
            "id_veiculo": s.id_veiculo,
            "id_motorista": s.id_motorista,
            "data_inicio": s.data_inicio,
            "data_fim": s.data_fim,
            "odometro_inicial": s.odometro_inicial,
            "odometro_final": s.odometro_final,
            "km_saida_coletas": _as_float(s.km_saida_coletas),
            "km_rota_principal": _as_float(s.km_rota_principal),
            "km_retorno_base": _as_float(s.km_retorno_base),
            "km_planejado_manual": _as_float(s.km_planejado_manual),
            "km_planejado_exibido": sum(_as_float(t.km_planejado) for t in s.trechos) if s.trechos else _as_float(s.km_planejado_manual),
            "tem_trechos_legados": bool(s.trechos),
            "observacoes": s.observacoes or "",
        } for s in saidas]


def validar_preenchimento_saida(item):
    validar_saida({
        "descricao": item.get("descricao"),
        "data_inicio": item.get("data_inicio"),
        "data_fim": item.get("data_fim"),
        "odometro_inicial": item.get("odometro_inicial"),
        "odometro_final": item.get("odometro_final"),
        "km_planejado_manual": item.get("km_planejado_manual"),
    })
    if not item.get("id_veiculo"):
        raise ValueError("Selecione o veículo na Etapa 1 antes de registrar a saída.")
    componentes = ("km_saida_coletas", "km_rota_principal", "km_retorno_base")
    if any(_as_float(item.get(k)) < 0 for k in componentes):
        raise ValueError("Os três campos de KM planejado devem ser positivos ou zero.")
    if item.get("odometro_final") and not item.get("odometro_inicial"):
        raise ValueError("Preencha o odômetro inicial antes de informar a chegada à base.")
    if item.get("data_fim") and not item.get("data_inicio"):
        raise ValueError("Informe a data de saída antes de informar a chegada.")
    return True


def _exibir_resumo(saidas, *, rascunho=False):
    if not saidas:
        st.caption("Nenhuma saída cadastrada. Registre a primeira saída abaixo.")
        return
    linhas = []
    for n, s in enumerate(saidas, 1):
        inicio = s.get("odometro_inicial")
        fim = s.get("odometro_final")
        linhas.append({
            "Saída": f"{n:02d}",
            "Finalidade": s.get("descricao"),
            "KM planejado": round(_as_float(s.get("km_planejado_exibido", s.get("km_planejado_manual"))), 2),
            "Odômetro inicial": inicio or "—",
            "Odômetro final": fim or "—",
            "KM real": (fim - inicio) if inicio and fim else "Em andamento",
        })
    st.dataframe(pd.DataFrame(linhas), hide_index=True, use_container_width=True)
    st.caption("Todas as saídas pertencem à mesma operação; não é necessário cadastrá-las novamente nos outros fretes do ciclo.")


def render_percurso(ctx):
    """Apresenta as saídas da operação no ponto natural de preenchimento."""
    st.markdown('<div class="sec-subtitle">Saídas operacionais, KM e odômetros</div>', unsafe_allow_html=True)
    tipo = get_campo("tipo_viagem", "Individual")
    st.caption(
        "O preenchimento é igual para Individual e Ciclo. Cada saída começa na base e termina "
        "quando o veículo retorna. Em ciclos, várias coletas e fretes podem compartilhar a mesma saída. "
        "Os quilômetros serão contabilizados uma única vez."
    )
    cid, salvas = _obter_contexto(ctx.viagem_sel_id)
    if not cid:
        saidas = st.session_state.setdefault("saidas_provisorias", [])
    else:
        saidas = salvas
        if st.session_state.get("saidas_provisorias"):
            st.info("Há saídas em rascunho. Conclua o salvamento do frete antes de registrar outras saídas.")
    _exibir_resumo(saidas, rascunho=not bool(cid))

    if cid and salvas:
        with SessionLocal() as db:
            resumo = resumo_saidas(consultar_saidas(db, cid))
        col_a, col_b = st.columns(2)
        col_a.metric("KM planejado da operação", f'{resumo["km_planejado"]:,.2f} km')
        col_b.metric("KM real", f'{resumo["km_real"]:,.0f} km' if resumo["km_real"] is not None else "Em andamento")
        for aviso in resumo["avisos"]:
            if "sobrepostos" in aviso or "inconsistentes" in aviso:
                st.warning(aviso)

    with st.expander("Adicionar ou atualizar uma saída", expanded=not saidas):
        choices = [("nova", None, "➕ Adicionar outra saída operacional")]
        for i, s in enumerate(saidas):
            codigo = str(s.get("id") or i)
            choices.append((codigo, i, f'Saída {i + 1:02d} — {s.get("descricao") or "Sem descrição"}'))
        seletor = f"faeg_percurso_selec_{cid or 'rascunho'}"
        labels = {c[0]: c[2] for c in choices}
        atual_keys = [c[0] for c in choices]
        if st.session_state.get(seletor) not in atual_keys:
            st.session_state.pop(seletor, None)
        selected = st.selectbox("REGISTRO", atual_keys, format_func=lambda k: labels[k], key=seletor)
        entry = next((s for c, idx, _ in choices if c == selected and idx is not None for s in [saidas[idx]]), None)
        if entry and entry.get("tem_trechos_legados"):
            st.warning("Esta saída possui trechos detalhados do formato anterior. Os trechos continuam válidos e não serão sobrescritos; a edição dos KM por componentes fica bloqueada até sua revisão.")
        prefix = f"faeg_percurso_form_{cid or 'novo'}_{selected}"
        veic_ids = [v["id_veiculo"] for v in ctx.veiculos_db]
        if not veic_ids:
            st.warning("Primeiro cadastre um veículo na Etapa 11.")
            return
        if not entry and not get_campo("vei_id", 0):
            st.info("Selecione primeiro o veículo na Etapa 1. Depois cadastre a saída aqui.")
            return
        veic_default = entry.get("id_veiculo") if entry else get_campo("vei_id", 0)
        mot_default = entry.get("id_motorista") if entry else get_campo("mot_id", 0)
        if veic_default not in veic_ids:
            veic_default = veic_ids[0]
        mot_ids = [None] + [m["id_motorista"] for m in ctx.motoristas_db]
        if mot_default not in mot_ids:
            mot_default = None
        with st.form(prefix):
            descricao = st.text_input("FINALIDADE DA SAÍDA *", value=entry["descricao"] if entry else "",
                                      placeholder="Ex.: Coletas preparatórias / Complementação / Entregas e retorno")
            a,b = st.columns(2)
            vid = a.selectbox("VEÍCULO *", veic_ids, index=veic_ids.index(veic_default),
                format_func=lambda v: next((f'{x["placa"]} — {x["descricao_marca"]}' for x in ctx.veiculos_db if x["id_veiculo"] == v), str(v)))
            mid = b.selectbox("MOTORISTA", mot_ids, index=mot_ids.index(mot_default),
                format_func=lambda m: next((x["nome_completo"] for x in ctx.motoristas_db if x["id_motorista"] == m), "Não informado") if m else "Não informado")
            d1,d2 = st.columns(2)
            data_inicio = d1.date_input("DATA DE SAÍDA DA BASE", value=entry["data_inicio"] if entry and entry.get("data_inicio") else get_campo("data_op", date.today()), format="DD/MM/YYYY")
            data_fim = d2.date_input("DATA DE CHEGADA À BASE", value=entry["data_fim"] if entry else None, format="DD/MM/YYYY")
            st.caption("Planejamento da saída: informe somente os trechos que realmente serão percorridos.")
            x,y,z = st.columns(3)
            bloqueado = bool(entry and entry.get("tem_trechos_legados"))
            km_coletas = x.number_input("KM saída / entre coletas", min_value=0., step=1., format="%.2f", value=_as_float(entry.get("km_saida_coletas")) if entry else 0., disabled=bloqueado)
            km_rota = y.number_input("KM rota principal", min_value=0., step=1., format="%.2f", value=_as_float(entry.get("km_rota_principal")) if entry else 0., disabled=bloqueado)
            km_retorno = z.number_input("KM retorno à base", min_value=0., step=1., format="%.2f", value=_as_float(entry.get("km_retorno_base")) if entry else 0., disabled=bloqueado)
            planejado = round(km_coletas + km_rota + km_retorno, 2)
            if bloqueado:
                planejado = _as_float(entry.get("km_planejado_manual"))
                st.caption("Os trechos detalhados desta saída histórica continuarão sendo a referência do fechamento.")
            else:
                st.caption(f"KM TOTAL PLANEJADO DESTA SAÍDA: **{planejado:,.2f} km**")
            o1,o2 = st.columns(2)
            odo_ini = o1.number_input("ODÔMETRO NA SAÍDA DA BASE", min_value=0, step=1,
                                      value=int(entry.get("odometro_inicial") or 0) if entry else 0)
            odo_fin = o2.number_input("ODÔMETRO NA CHEGADA À BASE", min_value=0, step=1,
                                      value=int(entry.get("odometro_final") or 0) if entry else 0)
            st.caption("Deixe a chegada e o odômetro final vazios/zero enquanto a saída estiver em andamento. O KM real é automático.")
            obs = st.text_area("OBSERVAÇÕES", value=entry.get("observacoes", "") if entry else "")
            submit = st.form_submit_button("Salvar esta saída", type="primary")
        if submit:
            valores = {
                "id_veiculo": vid, "id_motorista": mid, "descricao": descricao.strip(),
                "data_inicio": data_inicio, "data_fim": data_fim,
                "odometro_inicial": odo_ini or None, "odometro_final": odo_fin or None,
                "km_saida_coletas": km_coletas, "km_rota_principal": km_rota,
                "km_retorno_base": km_retorno, "km_planejado_manual": planejado,
                "observacoes": obs,
            }
            try:
                validar_preenchimento_saida(valores)
                if cid:
                    with SessionLocal() as db:
                        salvar_saida(db, id_ciclo=cid, id_saida=entry["id"] if entry else None,
                                    **valores)
                        db.commit()
                else:
                    if entry:
                        saidas[choices[[c[0] for c in choices].index(selected)][1]] = {**entry, **valores}
                    else:
                        saidas.append({"id": str(uuid4()), **valores})
                    st.session_state["saidas_provisorias"] = saidas
                st.session_state.pop(seletor, None)
                st.toast("Saída registrada. Adicione outra se necessário.", icon="✅")
                st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível registrar a saída: {exc}")
    if not cid and saidas:
        st.info("As saídas estão no preenchimento atual. Use **Salvar rascunho** na barra lateral para guardá-las ou **Salvar viagem** quando completar os dados obrigatórios.")
