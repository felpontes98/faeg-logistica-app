"""Rascunho recuperável: formulário parcial sem criar viagem incompleta na DRE."""
import streamlit as st

from faeg_app.erros import informar_falha
from database.connection import SessionLocal
from database.models import RascunhoViagem
from database.rascunhos import abrir_rascunho, salvar_rascunho


def salvar_rascunho_ativo():
    # Callbacks sincronizam os widgets; este espelho cobre a última alteração
    # digitada imediatamente antes de clicar em salvar.
    form = dict(st.session_state.get("form_data") or {})
    for chave in list(form):
        widget = f"w_{chave}"
        if widget in st.session_state:
            form[chave] = st.session_state[widget]
    try:
        with SessionLocal() as db:
            rid = salvar_rascunho(
                db, id_rascunho=st.session_state.get("rascunho_ativo_id"),
                titulo=f'{form.get("id_viagem_label") or "Novo frete"} — {form.get("ciclo_nome") or "Individual"}',
                form=form,
                saidas=st.session_state.get("saidas_provisorias", []),
                despesas=st.session_state.get("despesas_temp", []),
            )
            db.commit()
        st.session_state["rascunho_ativo_id"] = rid
        st.toast("Rascunho salvo. Você poderá retomá-lo depois.", icon="✅")
    except Exception:
        informar_falha("salvar o rascunho")


def retomar_rascunho(id_rascunho):
    from faeg_app.core import limpar_widgets_viagem
    with SessionLocal() as db:
        registro = db.get(RascunhoViagem, int(id_rascunho))
        if not registro:
            st.error("Rascunho não encontrado.")
            return
        form, saidas, despesas = abrir_rascunho(registro.conteudo_json)
    limpar_widgets_viagem()
    st.session_state["form_data"] = form
    st.session_state["saidas_provisorias"] = saidas
    st.session_state["despesas_temp"] = despesas
    st.session_state["rascunho_ativo_id"] = int(id_rascunho)
    st.session_state["viagem_ativa_id"] = 0
    st.session_state["loaded_viagem_id"] = 0
    st.session_state["menu_operacional_radio"] = "1. Frota FAEG"
    st.rerun()


def controles_rascunho(viagem_id):
    if viagem_id:
        return
    if st.button("💾 Salvar rascunho / continuar depois", use_container_width=True):
        salvar_rascunho_ativo()
    with SessionLocal() as db:
        lista = db.query(RascunhoViagem).order_by(RascunhoViagem.atualizado_em.desc()).limit(40).all()
        opcoes = {r.id_rascunho: r.titulo for r in lista}
    if opcoes:
        with st.expander(f"Retomar rascunho ({len(opcoes)})"):
            selecionado = st.selectbox("Rascunho salvo", list(opcoes), format_func=opcoes.get, key="faeg_rascunho_selecionado")
            if st.button("Retomar preenchimento", use_container_width=True):
                retomar_rascunho(selecionado)
