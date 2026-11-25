"""Etapa 11 — Cadastros gerais e parâmetros de veículos do Sistema Web FAEG."""
from html import escape

import streamlit as st

from database.connection import SessionLocal
from database.models import Cliente, Fornecedor, Local, Motorista, Veiculo
from sqlalchemy.exc import IntegrityError
from faeg_app.core import (
    CATEGORIAS_DESPESA_FORNECEDOR,
    carregar_listas_base,
    render_navegacao_rodape,
    to_float,
    to_int,
)


def render(ctx):
    MENU_ITENS = ctx.menu_itens
    clientes_db = ctx.clientes_db
    fornecedores_db = ctx.fornecedores_db
    locais_db = ctx.locais_db
    motoristas_db = ctx.motoristas_db
    veiculos_db = ctx.veiculos_db

    st.markdown(
        """
            <div class="tab-header-wrap">
                <div class="tab-title"><i class="fa-solid fa-address-book"></i> Cadastros Gerais (Base de Dados)</div>
                <span class="tab-step-pill">Etapa 11 de 11</span>
            </div>
            """,
        unsafe_allow_html=True,
    )

    cli_map_cad = {c["id_cliente"]: c for c in clientes_db}

    tab_mot, tab_vei, tab_cli, tab_loc, tab_forn = st.tabs(
        [
            "🧑‍✈️ Motoristas",
            "🚛 Veículos",
            "🏢 Clientes",
            "📍 Locais / Bases",
            "⛽ Fornecedores / Postos",
        ]
    )

    # ----------------------------------------------------------------------
    # ABA 1: MOTORISTAS
    # ----------------------------------------------------------------------
    with tab_mot:
        with st.container(border=True):
            st.markdown('<div class="card-faeg-azul"></div>', unsafe_allow_html=True)
            st.markdown(
                "<div style='font-size:0.85rem;font-weight:800;color:#0D263C;text-transform:uppercase;margin-bottom:0.8rem;'>"
                "<i class='fa-solid fa-id-card' style='color:#F34D25;margin-right:0.4rem;'></i> Cadastro de Motoristas</div>",
                unsafe_allow_html=True,
            )

            edit_mot_id = st.session_state.get("edit_mot_id", None)
            mot_edit_obj = next((m for m in motoristas_db if m["id_motorista"] == edit_mot_id), None)

            if mot_edit_obj:
                st.markdown(
                    f"<div class='edit-banner-pill'>✏️ Editando Motorista: {escape(str(mot_edit_obj['nome_completo']))}</div>",
                    unsafe_allow_html=True,
                )

            # Chaves mudam apenas após sucesso ou troca de registro editado.
            # Em erro de validação/duplicidade, todos os campos permanecem preenchidos.
            prefixo_mot = f"cad_mot_{edit_mot_id or 'novo'}_{st.session_state.get('versao_cad_mot', 0)}"
            with st.form("form_cad_mot", clear_on_submit=False):
                mc1, mc2, mc3 = st.columns([2.6, 1.3, 1.3])
                m_nome = mc1.text_input(
                    "Nome Completo *",
                    key=f"{prefixo_mot}_nome",
                    placeholder="Ex: Carlos Eduardo Mendes",
                    value=mot_edit_obj["nome_completo"] if mot_edit_obj else "",
                )
                m_cpf = mc2.text_input(
                    "CPF *",
                    key=f"{prefixo_mot}_cpf",
                    placeholder="000.000.000-00",
                    value=mot_edit_obj["cpf"] if mot_edit_obj else "",
                )
                m_tel = mc3.text_input(
                    "Telefone / WhatsApp",
                    key=f"{prefixo_mot}_telefone",
                    placeholder="(11) 99999-9999",
                    value=(mot_edit_obj.get("telefone_contato") or "") if mot_edit_obj else "",
                )

                mc4, mc5, mc6, mc7 = st.columns([1.4, 0.9, 1.2, 1.7])
                m_cnh = mc4.text_input(
                    "Número CNH *",
                    key=f"{prefixo_mot}_cnh",
                    placeholder="00000000000",
                    value=mot_edit_obj["cnh_numero"] if mot_edit_obj else "",
                )
                cats_cnh = ["C", "D", "E", "AE", "B"]
                idx_cat_m = (
                    cats_cnh.index(mot_edit_obj["cnh_categoria"])
                    if mot_edit_obj and mot_edit_obj.get("cnh_categoria") in cats_cnh
                    else 2
                )
                m_cat = mc5.selectbox("Categoria", cats_cnh, index=idx_cat_m, key=f"{prefixo_mot}_categoria")
                m_val_cnh = mc6.date_input(
                    "Validade CNH",
                    key=f"{prefixo_mot}_validade_cnh",
                    value=mot_edit_obj.get("cnh_validade") if mot_edit_obj else None,
                    format="DD/MM/YYYY",
                )
                vinculos_ops = ["Frota Própria (CLT)", "Agregado", "Terceiro (TAC)", "Outros"]
                idx_vinc = (
                    vinculos_ops.index(mot_edit_obj["vinculo"])
                    if mot_edit_obj and mot_edit_obj.get("vinculo") in vinculos_ops
                    else 0
                )
                m_vinc = mc7.selectbox("Vínculo", vinculos_ops, index=idx_vinc, key=f"{prefixo_mot}_vinculo")

                btn_txt_mot = "Atualizar Motorista" if mot_edit_obj else "Cadastrar Motorista"
                if st.form_submit_button(btn_txt_mot, use_container_width=True):
                    if not m_nome.strip() or not m_cpf.strip() or not m_cnh.strip():
                        st.error("Preencha Nome Completo, CPF e Número da CNH.")
                    else:
                        try:
                            with SessionLocal() as db:
                                if mot_edit_obj:
                                    obj_m = db.query(Motorista).filter_by(id_motorista=edit_mot_id).first()
                                    if obj_m:
                                        obj_m.nome_completo = m_nome.strip()
                                        obj_m.cpf = m_cpf.strip()
                                        obj_m.telefone_contato = m_tel.strip()
                                        obj_m.cnh_numero = m_cnh.strip()
                                        obj_m.cnh_categoria = m_cat
                                        obj_m.cnh_validade = m_val_cnh
                                        obj_m.vinculo = m_vinc
                                    st.session_state["edit_mot_id"] = None
                                else:
                                    db.add(
                                        Motorista(
                                            nome_completo=m_nome.strip(),
                                            cpf=m_cpf.strip(),
                                            telefone_contato=m_tel.strip(),
                                            cnh_numero=m_cnh.strip(),
                                            cnh_categoria=m_cat,
                                            cnh_validade=m_val_cnh,
                                            vinculo=m_vinc,
                                        )
                                    )
                                db.commit()
                            carregar_listas_base.clear()
                            st.session_state["versao_cad_mot"] = st.session_state.get("versao_cad_mot", 0) + 1
                            st.toast("Motorista salvo com sucesso!", icon="✅")
                            st.rerun()
                        except IntegrityError:
                            st.error("CPF ou CNH já cadastrado para outro motorista.")

            if mot_edit_obj:
                if st.button("Cancelar Edição de Motorista", key="cancel_ed_mot", use_container_width=True):
                    st.session_state["edit_mot_id"] = None
                    st.rerun()

            if motoristas_db:
                with st.expander(f"📋 Gerenciar Motoristas ({len(motoristas_db)})", expanded=True):
                    for m in motoristas_db:
                        mid = m["id_motorista"]
                        lm1, lm2, lm3 = st.columns([5.8, 0.7, 0.7])
                        lm1.markdown(
                            f"**{escape(str(m['nome_completo']))}** <span style='color:#64748B;font-size:0.78rem;'>| CNH: {escape(str(m['cnh_numero']))} ({escape(str(m['cnh_categoria']))}) | {escape(str(m.get('vinculo') or '-'))}</span>",
                            unsafe_allow_html=True,
                        )
                        if lm2.button("✏️", key=f"ed_m_{mid}", help="Editar"):
                            st.session_state["confirm_ed_mot"] = mid
                            st.session_state["confirm_dl_mot"] = None
                            st.rerun()
                        if lm3.button("🗑️", key=f"dl_m_{mid}", help="Excluir"):
                            st.session_state["confirm_dl_mot"] = mid
                            st.session_state["confirm_ed_mot"] = None
                            st.rerun()

                        if st.session_state.get("confirm_ed_mot") == mid:
                            st.markdown(
                                f"<div class='confirm-box-edit'>⚠️ Confirmar edição de <strong>{escape(str(m['nome_completo']))}</strong>?</div>",
                                unsafe_allow_html=True,
                            )
                            b_ok, b_no = st.columns(2)
                            if b_ok.button("✅ Sim, Editar", key=f"ok_ed_m_{mid}", use_container_width=True):
                                st.session_state["edit_mot_id"] = mid
                                st.session_state["confirm_ed_mot"] = None
                                st.rerun()
                            if b_no.button("❌ Cancelar", key=f"no_ed_m_{mid}", use_container_width=True):
                                st.session_state["confirm_ed_mot"] = None
                                st.rerun()

                        if st.session_state.get("confirm_dl_mot") == mid:
                            st.markdown(
                                f"<div class='confirm-box-del'>🚨 Excluir permanentemente <strong>{escape(str(m['nome_completo']))}</strong>?</div>",
                                unsafe_allow_html=True,
                            )
                            b_ok, b_no = st.columns(2)
                            if b_ok.button("🗑️ Sim, Excluir", key=f"ok_dl_m_{mid}", use_container_width=True):
                                try:
                                    with SessionLocal() as db:
                                        obj = db.query(Motorista).filter_by(id_motorista=mid).first()
                                        if obj:
                                            db.delete(obj)
                                            db.commit()
                                    st.session_state["confirm_dl_mot"] = None
                                    carregar_listas_base.clear()
                                    st.toast("Motorista excluído!", icon="🗑️")
                                    st.rerun()
                                except IntegrityError:
                                    st.error("Não é possível excluir: motorista já possui viagens vinculadas.")
                            if b_no.button("❌ Cancelar", key=f"no_dl_m_{mid}", use_container_width=True):
                                st.session_state["confirm_dl_mot"] = None
                                st.rerun()

    # ----------------------------------------------------------------------
    # ABA 2: VEÍCULOS
    # ----------------------------------------------------------------------
    with tab_vei:
        with st.container(border=True):
            st.markdown('<div class="card-faeg-laranja"></div>', unsafe_allow_html=True)
            st.markdown(
                "<div style='font-size:0.85rem;font-weight:800;color:#0D263C;text-transform:uppercase;margin-bottom:0.8rem;'>"
                "<i class='fa-solid fa-truck-front' style='color:#F34D25;margin-right:0.4rem;'></i> Cadastro de Veículos (Frota)</div>",
                unsafe_allow_html=True,
            )

            edit_vei_id = st.session_state.get("edit_vei_id", None)
            vei_edit_obj = next((v for v in veiculos_db if v["id_veiculo"] == edit_vei_id), None)

            if vei_edit_obj:
                st.markdown(
                    f"<div class='edit-banner-pill'>✏️ Editando Veículo: {escape(str(vei_edit_obj['descricao_marca']))} ({escape(str(vei_edit_obj['placa']))})</div>",
                    unsafe_allow_html=True,
                )

            prefixo_vei = f"cad_vei_{edit_vei_id or 'novo'}_{st.session_state.get('versao_cad_vei', 0)}"
            with st.form("form_cad_vei", clear_on_submit=False):
                vc1, vc2, vc3 = st.columns([2.6, 1.2, 1.4])
                v_desc = vc1.text_input(
                    "Descrição / Marca / Modelo *",
                    key=f"{prefixo_vei}_descricao",
                    placeholder="Ex: Scania R450 Highline",
                    value=vei_edit_obj["descricao_marca"] if vei_edit_obj else "",
                )
                v_placa = vc2.text_input(
                    "Placa *",
                    key=f"{prefixo_vei}_placa",
                    placeholder="ABC1D23",
                    value=vei_edit_obj["placa"] if vei_edit_obj else "",
                )
                tipos_v = ["Carreta", "Bitrem", "Rodotrem", "Truck", "Toco", "3/4", "VUC", "Utilitário"]
                idx_tv = (
                    tipos_v.index(vei_edit_obj["tipo_veiculo"])
                    if vei_edit_obj and vei_edit_obj.get("tipo_veiculo") in tipos_v
                    else 0
                )
                v_tipo = vc3.selectbox("Tipo de Veículo", tipos_v, index=idx_tv, key=f"{prefixo_vei}_tipo")

                vc4, vc5, vc6, vc7 = st.columns([1.6, 1.0, 1.3, 1.3])
                v_renavam = vc4.text_input(
                    "RENAVAM",
                    key=f"{prefixo_vei}_renavam",
                    placeholder="00000000000",
                    value=(vei_edit_obj.get("renavam") or "") if vei_edit_obj else "",
                )
                v_ano = vc5.number_input(
                    "Ano",
                    key=f"{prefixo_vei}_ano",
                    min_value=1980,
                    max_value=2035,
                    step=1,
                    value=to_int(vei_edit_obj.get("ano_fabricacao"), 2024) if vei_edit_obj else 2024,
                )
                v_cap_kg = vc6.number_input(
                    "Capacidade (KG)",
                    key=f"{prefixo_vei}_capacidade_kg",
                    min_value=0.0,
                    step=500.0,
                    format="%.2f",
                    value=to_float(vei_edit_obj.get("capacidade_carga_kg"), 0.0) if vei_edit_obj else 0.0,
                )
                v_cap_m3 = vc7.number_input(
                    "Volume (m³)",
                    key=f"{prefixo_vei}_capacidade_m3",
                    min_value=0.0,
                    step=5.0,
                    format="%.2f",
                    value=to_float(vei_edit_obj.get("capacidade_volume_m3"), 0.0) if vei_edit_obj else 0.0,
                )

                btn_txt_vei = "Atualizar Veículo" if vei_edit_obj else "Cadastrar Veículo"
                if st.form_submit_button(btn_txt_vei, use_container_width=True):
                    if not v_desc.strip() or not v_placa.strip():
                        st.error("Preencha Descrição/Modelo e Placa.")
                    else:
                        try:
                            with SessionLocal() as db:
                                if vei_edit_obj:
                                    obj_v = db.query(Veiculo).filter_by(id_veiculo=edit_vei_id).first()
                                    if obj_v:
                                        obj_v.descricao_marca = v_desc.strip()
                                        obj_v.placa = v_placa.strip().upper()
                                        obj_v.tipo_veiculo = v_tipo
                                        obj_v.renavam = v_renavam.strip() if v_renavam.strip() else None
                                        obj_v.ano_fabricacao = to_int(v_ano, 2024)
                                        obj_v.capacidade_carga_kg = to_float(v_cap_kg, 0.0)
                                        obj_v.capacidade_volume_m3 = to_float(v_cap_m3, 0.0)
                                    st.session_state["edit_vei_id"] = None
                                else:
                                    db.add(
                                        Veiculo(
                                            descricao_marca=v_desc.strip(),
                                            placa=v_placa.strip().upper(),
                                            tipo_veiculo=v_tipo,
                                            renavam=v_renavam.strip() if v_renavam.strip() else None,
                                            ano_fabricacao=to_int(v_ano, 2024),
                                            capacidade_carga_kg=to_float(v_cap_kg, 0.0),
                                            capacidade_volume_m3=to_float(v_cap_m3, 0.0),
                                        )
                                    )
                                db.commit()
                            carregar_listas_base.clear()
                            st.session_state["versao_cad_vei"] = st.session_state.get("versao_cad_vei", 0) + 1
                            st.toast("Veículo salvo com sucesso!", icon="✅")
                            st.rerun()
                        except IntegrityError:
                            st.error("Placa ou RENAVAM já cadastrado para outro veículo.")

            if vei_edit_obj:
                if st.button("Cancelar Edição de Veículo", key="cancel_ed_vei", use_container_width=True):
                    st.session_state["edit_vei_id"] = None
                    st.rerun()

            if veiculos_db:
                with st.expander(f"📋 Gerenciar Veículos ({len(veiculos_db)})", expanded=True):
                    for v in veiculos_db:
                        vid = v["id_veiculo"]
                        lv1, lv2, lv3 = st.columns([5.8, 0.7, 0.7])
                        lv1.markdown(
                            f"**{escape(str(v['descricao_marca']))}** <span style='color:#64748B;font-size:0.78rem;'>| Placa: {escape(str(v['placa']))} | {escape(str(v.get('tipo_veiculo') or '-'))}</span>",
                            unsafe_allow_html=True,
                        )
                        if lv2.button("✏️", key=f"ed_v_{vid}", help="Editar"):
                            st.session_state["confirm_ed_vei"] = vid
                            st.session_state["confirm_dl_vei"] = None
                            st.rerun()
                        if lv3.button("🗑️", key=f"dl_v_{vid}", help="Excluir"):
                            st.session_state["confirm_dl_vei"] = vid
                            st.session_state["confirm_ed_vei"] = None
                            st.rerun()

                        if st.session_state.get("confirm_ed_vei") == vid:
                            st.markdown(
                                f"<div class='confirm-box-edit'>⚠️ Confirmar edição de <strong>{escape(str(v['descricao_marca']))} ({escape(str(v['placa']))})</strong>?</div>",
                                unsafe_allow_html=True,
                            )
                            b_ok, b_no = st.columns(2)
                            if b_ok.button("✅ Sim, Editar", key=f"ok_ed_v_{vid}", use_container_width=True):
                                st.session_state["edit_vei_id"] = vid
                                st.session_state["confirm_ed_vei"] = None
                                st.rerun()
                            if b_no.button("❌ Cancelar", key=f"no_ed_v_{vid}", use_container_width=True):
                                st.session_state["confirm_ed_vei"] = None
                                st.rerun()

                        if st.session_state.get("confirm_dl_vei") == vid:
                            st.markdown(
                                f"<div class='confirm-box-del'>🚨 Excluir permanentemente <strong>{escape(str(v['descricao_marca']))} ({escape(str(v['placa']))})</strong>?</div>",
                                unsafe_allow_html=True,
                            )
                            b_ok, b_no = st.columns(2)
                            if b_ok.button("🗑️ Sim, Excluir", key=f"ok_dl_v_{vid}", use_container_width=True):
                                try:
                                    with SessionLocal() as db:
                                        obj = db.query(Veiculo).filter_by(id_veiculo=vid).first()
                                        if obj:
                                            db.delete(obj)
                                            db.commit()
                                    st.session_state["confirm_dl_vei"] = None
                                    carregar_listas_base.clear()
                                    st.toast("Veículo excluído!", icon="🗑️")
                                    st.rerun()
                                except IntegrityError:
                                    st.error("Não é possível excluir: veículo já possui viagens vinculadas.")
                            if b_no.button("❌ Cancelar", key=f"no_dl_v_{vid}", use_container_width=True):
                                st.session_state["confirm_dl_vei"] = None
                                st.rerun()

        from views.parametros_veiculo import render_parametros_consumo
        render_parametros_consumo(veiculos_db)

    # ----------------------------------------------------------------------
    # ABA 3: CLIENTES CONTRATANTES
    # ----------------------------------------------------------------------
    with tab_cli:
        with st.container(border=True):
            st.markdown('<div class="card-faeg-expansao"></div>', unsafe_allow_html=True)
            st.markdown(
                "<div style='font-size:0.85rem;font-weight:800;color:#0D263C;text-transform:uppercase;margin-bottom:0.8rem;'>"
                "<i class='fa-solid fa-building' style='color:#F34D25;margin-right:0.4rem;'></i> Cadastro de Clientes Contratantes</div>",
                unsafe_allow_html=True,
            )

            edit_cli_id = st.session_state.get("edit_cli_id", None)
            cli_edit_obj = next((c for c in clientes_db if c["id_cliente"] == edit_cli_id), None)

            if cli_edit_obj:
                st.markdown(
                    f"<div class='edit-banner-pill'>✏️ Editando Cliente: {escape(str(cli_edit_obj['razao_social']))}</div>",
                    unsafe_allow_html=True,
                )

            prefixo_cli = f"cad_cli_{edit_cli_id or 'novo'}_{st.session_state.get('versao_cad_cli', 0)}"
            with st.form("form_cad_cli", clear_on_submit=False):
                cc1, cc2 = st.columns(2)
                c_razao = cc1.text_input(
                    "Razão Social *",
                    key=f"{prefixo_cli}_razao",
                    placeholder="Ex: Indústria Metalúrgica Suzano Ltda",
                    value=cli_edit_obj["razao_social"] if cli_edit_obj else "",
                )
                c_fantasia = cc2.text_input(
                    "Nome Fantasia",
                    key=f"{prefixo_cli}_fantasia",
                    placeholder="Ex: MetalSuzano",
                    value=(cli_edit_obj.get("nome_fantasia") or "") if cli_edit_obj else "",
                )

                cc3, cc4, cc5 = st.columns([1.6, 1.4, 1.0])
                c_doc = cc3.text_input(
                    "CNPJ / CPF *",
                    key=f"{prefixo_cli}_doc",
                    placeholder="00.000.000/0001-00",
                    value=cli_edit_obj["cnpj_cpf"] if cli_edit_obj else "",
                )
                c_ie = cc4.text_input(
                    "Inscrição Estadual",
                    key=f"{prefixo_cli}_ie",
                    placeholder="Isento ou número IE",
                    value=(cli_edit_obj.get("inscricao_estadual") or "") if cli_edit_obj else "",
                )
                c_prazo = cc5.number_input(
                    "Prazo Pgto (Dias)",
                    key=f"{prefixo_cli}_prazo",
                    min_value=0,
                    step=5,
                    value=to_int(cli_edit_obj.get("prazo_pagamento_dias"), 30) if cli_edit_obj else 30,
                )

                cc6, cc7, cc8 = st.columns([1.6, 1.3, 1.8])
                c_resp = cc6.text_input(
                    "Responsável",
                    key=f"{prefixo_cli}_responsavel",
                    placeholder="Ex: Mariana Costa",
                    value=(cli_edit_obj.get("responsavel_comercial") or "") if cli_edit_obj else "",
                )
                c_tel = cc7.text_input(
                    "Telefone",
                    key=f"{prefixo_cli}_telefone",
                    placeholder="(11) 4748-9000",
                    value=(cli_edit_obj.get("telefone_comercial") or "") if cli_edit_obj else "",
                )
                c_email = cc8.text_input(
                    "E-mail",
                    key=f"{prefixo_cli}_email",
                    placeholder="contato@empresa.com.br",
                    value=(cli_edit_obj.get("email_financeiro") or "") if cli_edit_obj else "",
                )

                ce1, ce2, ce3, ce4 = st.columns([1.1, 2.7, 1.5, 0.7])
                c_cep = ce1.text_input(
                    "CEP",
                    key=f"{prefixo_cli}_cep",
                    placeholder="00000-000",
                    value=(cli_edit_obj.get("cep") or "") if cli_edit_obj else "",
                )
                c_end = ce2.text_input(
                    "Endereço Completo",
                    key=f"{prefixo_cli}_endereco",
                    placeholder="Av. Principal, 1000 - Centro",
                    value=(cli_edit_obj.get("endereco_completo") or "") if cli_edit_obj else "",
                )
                c_cid = ce3.text_input(
                    "Cidade",
                    key=f"{prefixo_cli}_cidade",
                    placeholder="Ex: Suzano",
                    value=(cli_edit_obj.get("cidade") or "") if cli_edit_obj else "",
                )
                c_uf = ce4.text_input(
                    "UF",
                    key=f"{prefixo_cli}_uf",
                    max_chars=2,
                    placeholder="SP",
                    value=(cli_edit_obj.get("uf") or "") if cli_edit_obj else "",
                )

                btn_txt_cli = "Atualizar Cliente" if cli_edit_obj else "Cadastrar Cliente"
                if st.form_submit_button(btn_txt_cli, use_container_width=True):
                    if not c_razao.strip() or not c_doc.strip():
                        st.error("Preencha Razão Social e CNPJ / CPF.")
                    else:
                        try:
                            with SessionLocal() as db:
                                if cli_edit_obj:
                                    obj_c = db.query(Cliente).filter_by(id_cliente=edit_cli_id).first()
                                    if obj_c:
                                        obj_c.razao_social = c_razao.strip()
                                        obj_c.nome_fantasia = c_fantasia.strip() if c_fantasia.strip() else None
                                        obj_c.cnpj_cpf = c_doc.strip()
                                        obj_c.inscricao_estadual = c_ie.strip()
                                        obj_c.responsavel_comercial = c_resp.strip()
                                        obj_c.telefone_comercial = c_tel.strip()
                                        obj_c.email_financeiro = c_email.strip()
                                        obj_c.prazo_pagamento_dias = to_int(c_prazo, 30)
                                        obj_c.cep = c_cep.strip()
                                        obj_c.endereco_completo = c_end.strip()
                                        obj_c.cidade = c_cid.strip()
                                        obj_c.uf = c_uf.strip().upper()
                                    st.session_state["edit_cli_id"] = None
                                else:
                                    db.add(
                                        Cliente(
                                            razao_social=c_razao.strip(),
                                            nome_fantasia=c_fantasia.strip() if c_fantasia.strip() else None,
                                            cnpj_cpf=c_doc.strip(),
                                            inscricao_estadual=c_ie.strip(),
                                            responsavel_comercial=c_resp.strip(),
                                            telefone_comercial=c_tel.strip(),
                                            email_financeiro=c_email.strip(),
                                            prazo_pagamento_dias=to_int(c_prazo, 30),
                                            cep=c_cep.strip(),
                                            endereco_completo=c_end.strip(),
                                            cidade=c_cid.strip(),
                                            uf=c_uf.strip().upper(),
                                        )
                                    )
                                db.commit()
                            carregar_listas_base.clear()
                            st.session_state["versao_cad_cli"] = st.session_state.get("versao_cad_cli", 0) + 1
                            st.toast("Cliente salvo com sucesso!", icon="✅")
                            st.rerun()
                        except IntegrityError:
                            st.error("CNPJ / CPF já cadastrado para outro cliente.")

            if cli_edit_obj:
                if st.button("Cancelar Edição de Cliente", key="cancel_ed_cli", use_container_width=True):
                    st.session_state["edit_cli_id"] = None
                    st.rerun()

            if clientes_db:
                with st.expander(f"📋 Gerenciar Clientes ({len(clientes_db)})", expanded=True):
                    for c in clientes_db:
                        cid = c["id_cliente"]
                        lc1, lc2, lc3 = st.columns([5.8, 0.7, 0.7])
                        ft_txt = f" ({c['nome_fantasia']})" if c.get("nome_fantasia") else ""
                        cid_txt = f" — {c['cidade']}/{c['uf']}" if (c.get("cidade") or c.get("uf")) else ""
                        lc1.markdown(
                            f"**{escape(str(c['razao_social']))}**{escape(str(ft_txt))} <span style='color:#64748B;font-size:0.78rem;'>| Doc: {escape(str(c['cnpj_cpf']))}{escape(str(cid_txt))}</span>",
                            unsafe_allow_html=True,
                        )
                        if lc2.button("✏️", key=f"ed_c_{cid}", help="Editar"):
                            st.session_state["confirm_ed_cli"] = cid
                            st.session_state["confirm_dl_cli"] = None
                            st.rerun()
                        if lc3.button("🗑️", key=f"dl_c_{cid}", help="Excluir"):
                            st.session_state["confirm_dl_cli"] = cid
                            st.session_state["confirm_ed_cli"] = None
                            st.rerun()

                        if st.session_state.get("confirm_ed_cli") == cid:
                            st.markdown(
                                f"<div class='confirm-box-edit'>⚠️ Confirmar edição de <strong>{escape(str(c['razao_social']))}</strong>?</div>",
                                unsafe_allow_html=True,
                            )
                            b_ok, b_no = st.columns(2)
                            if b_ok.button("✅ Sim, Editar", key=f"ok_ed_c_{cid}", use_container_width=True):
                                st.session_state["edit_cli_id"] = cid
                                st.session_state["confirm_ed_cli"] = None
                                st.rerun()
                            if b_no.button("❌ Cancelar", key=f"no_ed_c_{cid}", use_container_width=True):
                                st.session_state["confirm_ed_cli"] = None
                                st.rerun()

                        if st.session_state.get("confirm_dl_cli") == cid:
                            st.markdown(
                                f"<div class='confirm-box-del'>🚨 Excluir permanentemente <strong>{escape(str(c['razao_social']))}</strong>?</div>",
                                unsafe_allow_html=True,
                            )
                            b_ok, b_no = st.columns(2)
                            if b_ok.button("🗑️ Sim, Excluir", key=f"ok_dl_c_{cid}", use_container_width=True):
                                try:
                                    with SessionLocal() as db:
                                        obj = db.query(Cliente).filter_by(id_cliente=cid).first()
                                        if obj:
                                            db.delete(obj)
                                            db.commit()
                                    st.session_state["confirm_dl_cli"] = None
                                    carregar_listas_base.clear()
                                    st.toast("Cliente excluído!", icon="🗑️")
                                    st.rerun()
                                except IntegrityError:
                                    st.error("Não é possível excluir: cliente já possui viagens ou locais vinculados.")
                            if b_no.button("❌ Cancelar", key=f"no_dl_c_{cid}", use_container_width=True):
                                st.session_state["confirm_dl_cli"] = None
                                st.rerun()

    # ----------------------------------------------------------------------
    # ABA 4: LOCAIS DE COLETA E ENTREGA
    # ----------------------------------------------------------------------
    with tab_loc:
        with st.container(border=True):
            st.markdown('<div class="card-faeg-azul"></div>', unsafe_allow_html=True)
            st.markdown(
                "<div style='font-size:0.85rem;font-weight:800;color:#0D263C;text-transform:uppercase;margin-bottom:0.8rem;'>"
                "<i class='fa-solid fa-map-location-dot' style='color:#F34D25;margin-right:0.4rem;'></i> Locais de Coleta e Entrega</div>",
                unsafe_allow_html=True,
            )

            edit_loc_id = st.session_state.get("edit_loc_id", None)
            loc_edit_obj = next((l for l in locais_db if l["id_local"] == edit_loc_id), None)

            if loc_edit_obj:
                st.markdown(
                    f"<div class='edit-banner-pill'>✏️ Editando Local: {escape(str(loc_edit_obj['nome_local']))}</div>",
                    unsafe_allow_html=True,
                )

            cli_vinc_ops = {0: "Nenhum (Local Geral / Independente)"}
            for c in clientes_db:
                ft = f" ({c['nome_fantasia']})" if c.get("nome_fantasia") else ""
                cli_vinc_ops[c["id_cliente"]] = f"{c['razao_social']}{ft}"

            idx_cli_vinc = (
                list(cli_vinc_ops.keys()).index(loc_edit_obj["id_cliente"])
                if loc_edit_obj and loc_edit_obj.get("id_cliente") in cli_vinc_ops
                else 0
            )
            l_cli_id = st.selectbox(
                "Cliente / Transportadora Correspondente (Opcional)",
                options=list(cli_vinc_ops.keys()),
                index=idx_cli_vinc,
                format_func=lambda x: cli_vinc_ops[x],
                key=f"cad_loc_cli_{edit_loc_id or 'new'}",
            )

            ll1, ll2 = st.columns([3.5, 2.5])
            l_nome = ll1.text_input(
                "Nome do Local / CD *",
                placeholder="Ex: CD Dunlop Guarulhos",
                value=loc_edit_obj["nome_local"] if loc_edit_obj else "",
                key=f"cad_loc_nome_{edit_loc_id or 'new'}",
            )
            tipos_loc = ["CD / Armazém", "Fábrica", "Loja / Varejo", "Porto / Aeroporto", "Cliente Final", "Outros"]
            idx_tl = (
                tipos_loc.index(loc_edit_obj["tipo_instalacao"])
                if loc_edit_obj and loc_edit_obj.get("tipo_instalacao") in tipos_loc
                else 0
            )
            l_tipo = ll2.selectbox(
                "Tipo de Instalação",
                tipos_loc,
                index=idx_tl,
                key=f"cad_loc_tipo_{edit_loc_id or 'new'}",
            )

            le1, le2 = st.columns([1.8, 4.2])
            l_cep = le1.text_input(
                "CEP",
                placeholder="00000-000",
                value=(loc_edit_obj.get("cep") or "") if loc_edit_obj else "",
                key=f"cad_loc_cep_{edit_loc_id or 'new'}",
            )
            l_end = le2.text_input(
                "Endereço Completo",
                placeholder="Rua, Número, Bairro",
                value=(loc_edit_obj.get("endereco_completo") or "") if loc_edit_obj else "",
                key=f"cad_loc_end_{edit_loc_id or 'new'}",
            )

            lc_c, lc_u, lc_ct = st.columns([2.6, 1.0, 2.4])
            l_cid = lc_c.text_input(
                "Cidade",
                placeholder="Ex: Guarulhos",
                value=(loc_edit_obj.get("cidade") or "") if loc_edit_obj else "",
                key=f"cad_loc_cid_{edit_loc_id or 'new'}",
            )
            l_uf = lc_u.text_input(
                "UF",
                max_chars=2,
                placeholder="SP",
                value=(loc_edit_obj.get("uf") or "") if loc_edit_obj else "",
                key=f"cad_loc_uf_{edit_loc_id or 'new'}",
            )
            l_contato = lc_ct.text_input(
                "Contato / Portaria",
                placeholder="Nome / Telefone",
                value=(loc_edit_obj.get("contato_portaria") or "") if loc_edit_obj else "",
                key=f"cad_loc_cont_{edit_loc_id or 'new'}",
            )

            opcoes_rest = ["Não há restrição", "Horário Comercial", "Outros"]
            rest_atual = (
                (loc_edit_obj.get("restricao_horario") or "Não há restrição")
                if loc_edit_obj
                else "Não há restrição"
            )
            if rest_atual in ["Não há restrição", "Horário Comercial"]:
                idx_rest = opcoes_rest.index(rest_atual)
                rest_custom_init = ""
            else:
                idx_rest = 2
                rest_custom_init = rest_atual

            lr1, lr2 = st.columns([2.8, 3.2])
            l_rest_sel = lr1.selectbox(
                "Restrição de Horário",
                opcoes_rest,
                index=idx_rest,
                key=f"cad_loc_rest_{edit_loc_id or 'new'}",
            )
            eh_outros_rest = l_rest_sel == "Outros"
            l_rest_manual = lr2.text_input(
                "Horário Manual (se Outros)",
                value=rest_custom_init if eh_outros_rest else "",
                placeholder="Ex: 08:00 às 17:00" if eh_outros_rest else "Selecione 'Outros' ao lado",
                disabled=not eh_outros_rest,
                key=f"cad_loc_rest_man_{edit_loc_id or 'new'}",
            )

            btn_txt_loc = "Atualizar Local" if loc_edit_obj else "Cadastrar Local"
            if st.button(btn_txt_loc, key="btn_salvar_local", use_container_width=True):
                if not l_nome.strip():
                    st.error("Preencha o Nome do Local / CD.")
                elif eh_outros_rest and not l_rest_manual.strip():
                    st.error("Informe manualmente a restrição de horário.")
                else:
                    restricao_final = l_rest_manual.strip() if eh_outros_rest else l_rest_sel
                    with SessionLocal() as db:
                        if loc_edit_obj:
                            obj_l = db.query(Local).filter_by(id_local=edit_loc_id).first()
                            if obj_l:
                                obj_l.id_cliente = l_cli_id if l_cli_id != 0 else None
                                obj_l.nome_local = l_nome.strip()
                                obj_l.tipo_instalacao = l_tipo
                                obj_l.cep = l_cep.strip()
                                obj_l.endereco_completo = l_end.strip()
                                obj_l.cidade = l_cid.strip()
                                obj_l.uf = l_uf.strip().upper()
                                obj_l.contato_portaria = l_contato.strip()
                                obj_l.restricao_horario = restricao_final
                            st.session_state["edit_loc_id"] = None
                        else:
                            db.add(
                                Local(
                                    id_cliente=l_cli_id if l_cli_id != 0 else None,
                                    nome_local=l_nome.strip(),
                                    tipo_instalacao=l_tipo,
                                    cep=l_cep.strip(),
                                    endereco_completo=l_end.strip(),
                                    cidade=l_cid.strip(),
                                    uf=l_uf.strip().upper(),
                                    contato_portaria=l_contato.strip(),
                                    restricao_horario=restricao_final,
                                )
                            )
                        db.commit()
                    for wk in list(st.session_state.keys()):
                        if wk.startswith("cad_loc_"):
                            del st.session_state[wk]
                    carregar_listas_base.clear()
                    st.toast("Local salvo com sucesso!", icon="✅")
                    st.rerun()

            if loc_edit_obj:
                if st.button("Cancelar Edição de Local", key="cancel_ed_loc", use_container_width=True):
                    st.session_state["edit_loc_id"] = None
                    st.rerun()

            if locais_db:
                with st.expander(f"📋 Gerenciar Locais ({len(locais_db)})", expanded=True):
                    for l in locais_db:
                        lid = l["id_local"]
                        ll_1, ll_2, ll_3 = st.columns([5.8, 0.7, 0.7])
                        cid_l_txt = f" ({l['cidade']}/{l['uf']})" if (l.get("cidade") or l.get("uf")) else ""
                        cli_l = cli_map_cad.get(l.get("id_cliente"))
                        cli_tag = f" [Cli: {cli_l['razao_social']}]" if cli_l else ""
                        ll_1.markdown(
                            f"**{escape(str(l['nome_local']))}**{escape(str(cid_l_txt))} <span style='color:#64748B;font-size:0.78rem;'>| {escape(str(l.get('restricao_horario') or 'Sem restrição'))}{escape(str(cli_tag))}</span>",
                            unsafe_allow_html=True,
                        )
                        if ll_2.button("✏️", key=f"ed_l_{lid}", help="Editar"):
                            st.session_state["confirm_ed_loc"] = lid
                            st.session_state["confirm_dl_loc"] = None
                            st.rerun()
                        if ll_3.button("🗑️", key=f"dl_l_{lid}", help="Excluir"):
                            st.session_state["confirm_dl_loc"] = lid
                            st.session_state["confirm_ed_loc"] = None
                            st.rerun()

                        if st.session_state.get("confirm_ed_loc") == lid:
                            st.markdown(
                                f"<div class='confirm-box-edit'>⚠️ Confirmar edição de <strong>{escape(str(l['nome_local']))}</strong>?</div>",
                                unsafe_allow_html=True,
                            )
                            b_ok, b_no = st.columns(2)
                            if b_ok.button("✅ Sim, Editar", key=f"ok_ed_l_{lid}", use_container_width=True):
                                st.session_state["edit_loc_id"] = lid
                                st.session_state["confirm_ed_loc"] = None
                                st.rerun()
                            if b_no.button("❌ Cancelar", key=f"no_ed_l_{lid}", use_container_width=True):
                                st.session_state["confirm_ed_loc"] = None
                                st.rerun()

                        if st.session_state.get("confirm_dl_loc") == lid:
                            st.markdown(
                                f"<div class='confirm-box-del'>🚨 Excluir permanentemente <strong>{escape(str(l['nome_local']))}</strong>?</div>",
                                unsafe_allow_html=True,
                            )
                            b_ok, b_no = st.columns(2)
                            if b_ok.button("🗑️ Sim, Excluir", key=f"ok_dl_l_{lid}", use_container_width=True):
                                try:
                                    with SessionLocal() as db:
                                        obj = db.query(Local).filter_by(id_local=lid).first()
                                        if obj:
                                            db.delete(obj)
                                            db.commit()
                                    st.session_state["confirm_dl_loc"] = None
                                    carregar_listas_base.clear()
                                    st.toast("Local excluído!", icon="🗑️")
                                    st.rerun()
                                except IntegrityError:
                                    st.error("Não é possível excluir: local já está vinculado a viagens.")
                            if b_no.button("❌ Cancelar", key=f"no_dl_l_{lid}", use_container_width=True):
                                st.session_state["confirm_dl_loc"] = None
                                st.rerun()

    # ----------------------------------------------------------------------
    # ABA 5: FORNECEDORES E POSTOS
    # ----------------------------------------------------------------------
    with tab_forn:
        with st.container(border=True):
            st.markdown('<div class="card-faeg-azul"></div>', unsafe_allow_html=True)
            st.markdown(
                "<div style='font-size:0.85rem;font-weight:800;color:#0D263C;text-transform:uppercase;margin-bottom:0.8rem;'>"
                "<i class='fa-solid fa-gas-pump' style='color:#F34D25;margin-right:0.4rem;'></i> Fornecedores e Postos</div>",
                unsafe_allow_html=True,
            )

            edit_forn_id = st.session_state.get("edit_forn_id", None)
            forn_edit_obj = next((f for f in fornecedores_db if f["id_fornecedor"] == edit_forn_id), None)

            if forn_edit_obj:
                st.markdown(
                    f"<div class='edit-banner-pill'>✏️ Editando Fornecedor: {escape(str(forn_edit_obj['nome_fantasia']))}</div>",
                    unsafe_allow_html=True,
                )

            prefixo_forn = f"cad_forn_{edit_forn_id or 'novo'}_{st.session_state.get('versao_cad_forn', 0)}"
            with st.form("form_cad_forn", clear_on_submit=False):
                fn1, fn2 = st.columns(2)
                f_razao = fn1.text_input(
                    "Razão Social",
                    key=f"{prefixo_forn}_razao",
                    placeholder="Ex: Auto Posto Graal Ltda",
                    value=(forn_edit_obj.get("razao_social") or "") if forn_edit_obj else "",
                )
                f_fantasia = fn2.text_input(
                    "Nome Fantasia *",
                    key=f"{prefixo_forn}_fantasia",
                    placeholder="Ex: Posto Graal Dutra",
                    value=forn_edit_obj["nome_fantasia"] if forn_edit_obj else "",
                )

                fc1, fc2 = st.columns(2)
                f_cnpj = fc1.text_input(
                    "CNPJ",
                    key=f"{prefixo_forn}_cnpj",
                    placeholder="00.000.000/0001-00",
                    value=(forn_edit_obj.get("cnpj") or "") if forn_edit_obj else "",
                )
                idx_cat_f = (
                    CATEGORIAS_DESPESA_FORNECEDOR.index(forn_edit_obj["categoria_servico"])
                    if forn_edit_obj and forn_edit_obj.get("categoria_servico") in CATEGORIAS_DESPESA_FORNECEDOR
                    else 0
                )
                f_cat = fc2.selectbox("Categoria", CATEGORIAS_DESPESA_FORNECEDOR,
                                      index=idx_cat_f, key=f"{prefixo_forn}_categoria")

                fc3, fc4 = st.columns([4, 1.5])
                f_cid = fc3.text_input(
                    "Cidade",
                    key=f"{prefixo_forn}_cidade",
                    placeholder="Ex: Resende",
                    value=(forn_edit_obj.get("cidade") or "") if forn_edit_obj else "",
                )
                f_uf = fc4.text_input(
                    "UF",
                    key=f"{prefixo_forn}_uf",
                    max_chars=2,
                    placeholder="RJ",
                    value=(forn_edit_obj.get("uf") or "") if forn_edit_obj else "",
                )

                btn_txt_forn = "Atualizar Fornecedor" if forn_edit_obj else "Cadastrar Fornecedor"
                if st.form_submit_button(btn_txt_forn, use_container_width=True):
                    if not f_fantasia.strip():
                        st.error("Preencha o Nome Fantasia do fornecedor.")
                    else:
                        try:
                            with SessionLocal() as db:
                                if forn_edit_obj:
                                    obj_f = db.query(Fornecedor).filter_by(id_fornecedor=edit_forn_id).first()
                                    if obj_f:
                                        obj_f.razao_social = f_razao.strip() if f_razao.strip() else None
                                        obj_f.nome_fantasia = f_fantasia.strip()
                                        obj_f.cnpj = f_cnpj.strip() if f_cnpj.strip() else None
                                        obj_f.categoria_servico = f_cat
                                        obj_f.cidade = f_cid.strip()
                                        obj_f.uf = f_uf.strip().upper()
                                    st.session_state["edit_forn_id"] = None
                                else:
                                    db.add(
                                        Fornecedor(
                                            razao_social=f_razao.strip() if f_razao.strip() else None,
                                            nome_fantasia=f_fantasia.strip(),
                                            cnpj=f_cnpj.strip() if f_cnpj.strip() else None,
                                            categoria_servico=f_cat,
                                            cidade=f_cid.strip(),
                                            uf=f_uf.strip().upper(),
                                        )
                                    )
                                db.commit()
                            carregar_listas_base.clear()
                            st.session_state["versao_cad_forn"] = st.session_state.get("versao_cad_forn", 0) + 1
                            st.toast("Fornecedor salvo com sucesso!", icon="✅")
                            st.rerun()
                        except IntegrityError:
                            st.error("CNPJ já cadastrado para outro fornecedor.")

            if forn_edit_obj:
                if st.button("Cancelar Edição de Fornecedor", key="cancel_ed_forn", use_container_width=True):
                    st.session_state["edit_forn_id"] = None
                    st.rerun()

            if fornecedores_db:
                with st.expander(f"📋 Gerenciar Fornecedores ({len(fornecedores_db)})", expanded=True):
                    for f in fornecedores_db:
                        fid = f["id_fornecedor"]
                        lf1, lf2, lf3 = st.columns([5.8, 0.7, 0.7])
                        rz_f_txt = f" ({f['razao_social']})" if f.get("razao_social") else ""
                        lf1.markdown(
                            f"**{escape(str(f['nome_fantasia']))}**{escape(str(rz_f_txt))} <span style='color:#64748B;font-size:0.78rem;'>| {escape(str(f.get('categoria_servico') or '-'))}</span>",
                            unsafe_allow_html=True,
                        )
                        if lf2.button("✏️", key=f"ed_f_{fid}", help="Editar"):
                            st.session_state["confirm_ed_forn"] = fid
                            st.session_state["confirm_dl_forn"] = None
                            st.rerun()
                        if lf3.button("🗑️", key=f"dl_f_{fid}", help="Excluir"):
                            st.session_state["confirm_dl_forn"] = fid
                            st.session_state["confirm_ed_forn"] = None
                            st.rerun()

                        if st.session_state.get("confirm_ed_forn") == fid:
                            st.markdown(
                                f"<div class='confirm-box-edit'>⚠️ Confirmar edição de <strong>{escape(str(f['nome_fantasia']))}</strong>?</div>",
                                unsafe_allow_html=True,
                            )
                            b_ok, b_no = st.columns(2)
                            if b_ok.button("✅ Sim, Editar", key=f"ok_ed_f_{fid}", use_container_width=True):
                                st.session_state["edit_forn_id"] = fid
                                st.session_state["confirm_ed_forn"] = None
                                st.rerun()
                            if b_no.button("❌ Cancelar", key=f"no_ed_f_{fid}", use_container_width=True):
                                st.session_state["confirm_ed_forn"] = None
                                st.rerun()

                        if st.session_state.get("confirm_dl_forn") == fid:
                            st.markdown(
                                f"<div class='confirm-box-del'>🚨 Excluir permanentemente <strong>{escape(str(f['nome_fantasia']))}</strong>?</div>",
                                unsafe_allow_html=True,
                            )
                            b_ok, b_no = st.columns(2)
                            if b_ok.button("🗑️ Sim, Excluir", key=f"ok_dl_f_{fid}", use_container_width=True):
                                try:
                                    with SessionLocal() as db:
                                        obj = db.query(Fornecedor).filter_by(id_fornecedor=fid).first()
                                        if obj:
                                            db.delete(obj)
                                            db.commit()
                                    st.session_state["confirm_dl_forn"] = None
                                    carregar_listas_base.clear()
                                    st.toast("Fornecedor excluído!", icon="🗑️")
                                    st.rerun()
                                except IntegrityError:
                                    st.error("Não é possível excluir: fornecedor já possui despesas vinculadas.")
                            if b_no.button("❌ Cancelar", key=f"no_dl_f_{fid}", use_container_width=True):
                                st.session_state["confirm_dl_forn"] = None
                                st.rerun()

    render_navegacao_rodape(10, MENU_ITENS)
