"""Parâmetros de consumo pertencem ao cadastro do veículo (Etapa 11)."""
import streamlit as st
from database.connection import SessionLocal
from database.models import ParametroConsumoVeiculo


def render_parametros_consumo(veiculos):
    with st.expander("Consumo de referência dos veículos (estimativa gerencial)", expanded=False):
        st.caption("Esses parâmetros podem ser revistos conforme o consumo real muda. "
                   "A estimativa não cria despesa financeira nem altera a DRE.")
        if not veiculos:
            st.info("Cadastre um veículo para informar os parâmetros.")
            return
        ids = [v["id_veiculo"] for v in veiculos]
        selecionado = st.selectbox("VEÍCULO", ids,
            format_func=lambda vid: next((f'{v["descricao_marca"]} — {v["placa"]}'
                                        for v in veiculos if v["id_veiculo"] == vid), str(vid)),
            key="consumo_veiculo_cadastro")
        with SessionLocal() as db:
            registro = db.get(ParametroConsumoVeiculo, selecionado)
            media_atual = float(registro.km_por_litro) if registro else 10.0
            preco_atual = float(registro.preco_litro_referencia) if registro else 6.0
        with st.form(f"form_consumo_referencia_{selecionado}"):
            a,b = st.columns(2)
            media = a.number_input("MÉDIA DE REFERÊNCIA (KM/L)", min_value=0.01,
                value=media_atual, step=0.1, format="%.2f")
            preco = b.number_input("PREÇO DE REFERÊNCIA (R$/L)", min_value=0.01,
                value=preco_atual, step=0.01, format="%.2f")
            salvar = st.form_submit_button("Salvar parâmetros deste veículo")
        if salvar:
            with SessionLocal() as db:
                obj = db.get(ParametroConsumoVeiculo, selecionado)
                if obj is None:
                    obj = ParametroConsumoVeiculo(id_veiculo=selecionado)
                    db.add(obj)
                obj.km_por_litro = media
                obj.preco_litro_referencia = preco
                db.commit()
            st.toast("Parâmetros do veículo atualizados.", icon="✅")
            st.rerun()
