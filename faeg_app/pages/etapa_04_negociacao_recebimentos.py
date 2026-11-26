"""Etapa 4 — Negociação, parcelas e recebimentos do frete do Sistema Web FAEG."""
import pandas as pd
import streamlit as st

from database.connection import SessionLocal
from database.models import RecebimentoFrete
from datetime import date
from faeg_app.core import (
    OPCOES_ORIGEM_FRETE,
    carregar_recebimentos_viagem,
    carregar_todas_viagens_consulta,
    carregar_todos_recebimentos,
    exibir_indicadores,
    fmt_brl,
    get_campo,
    inicializar_widgets_previsao_financeira,
    on_perc_adiant_change,
    on_perc_saldo_change,
    on_val_adiant_change,
    on_val_saldo_change,
    on_valor_negociado_change,
    render_navegacao_rodape,
    sync_campo,
    to_float,
)


def render(ctx):
    MENU_ITENS = ctx.menu_itens
    viagem_sel_id = ctx.viagem_sel_id

    if get_campo("legado_pendente", False):
        st.warning("O ciclo tem valores históricos compartilhados. Informe a negociação própria deste frete e confirme a individualização para gravá-la.")
        st.checkbox("Confirmo os valores individuais deste frete", key="w_confirmar_individualizacao",
                    value=get_campo("confirmar_individualizacao", False), on_change=sync_campo,
                    args=("w_confirmar_individualizacao", "confirmar_individualizacao"))
    inicializar_widgets_previsao_financeira()
    st.markdown(
        """
            <div class="tab-header-wrap">
                <div class="tab-title"><i class="fa-solid fa-hand-holding-dollar"></i> Negociação e Recebimentos</div>
                <span class="tab-step-pill">Etapa 4 de 11</span>
            </div>
            """,
        unsafe_allow_html=True,
    )

    n1, n2, n3 = st.columns([1.8, 1.2, 1.2])
    with n1:
        fc_atual = get_campo("forma_contrat", OPCOES_ORIGEM_FRETE[0])
        st.selectbox(
            "ORIGEM DE FRETE",
            OPCOES_ORIGEM_FRETE,
            index=OPCOES_ORIGEM_FRETE.index(fc_atual) if fc_atual in OPCOES_ORIGEM_FRETE else 0,
            key="w_forma_contrat",
            on_change=sync_campo,
            args=("w_forma_contrat", "forma_contrat"),
        )
    with n2:
        st.number_input(
            "VALOR DIVULGADO (R$)",
            min_value=0.0,
            step=100.0,
            format="%.2f",
            value=to_float(get_campo("valor_divulgado", 0.0)),
            key="w_valor_divulgado",
            on_change=sync_campo,
            args=("w_valor_divulgado", "valor_divulgado"),
        )
    with n3:
        st.number_input(
            "VALOR NEGOCIADO (R$)",
            min_value=0.0,
            step=100.0,
            format="%.2f",
            key="w_val_negociado",
            on_change=on_valor_negociado_change,
        )

    st.markdown('<div class="sec-subtitle">Adiantamento</div>', unsafe_allow_html=True)
    a1, a2, a3, _ = st.columns([0.9, 1.1, 1.3, 1.0])
    with a1:
        st.number_input(
            "% ADIANTAMENTO",
            min_value=0.0,
            max_value=100.0,
            step=5.0,
            format="%.2f",
            key="w_perc_adiant",
            on_change=on_perc_adiant_change,
        )
    with a2:
        st.date_input(
            "DATA ADIANTAMENTO (DD/MM/AAAA)",
            value=get_campo("data_adiant"),
            format="DD/MM/YYYY",
            key="w_data_adiant",
            help="Formato brasileiro: dia/mês/ano. No calendário, YYYY equivale a AAAA (ano com quatro dígitos).",
            on_change=sync_campo,
            args=("w_data_adiant", "data_adiant"),
        )
    with a3:
        st.number_input(
            "VALOR ADIANTAMENTO (R$)",
            min_value=0.0,
            step=100.0,
            format="%.2f",
            key="w_val_adiant",
            on_change=on_val_adiant_change,
        )

    st.markdown('<div class="sec-subtitle">Saldo a Receber</div>', unsafe_allow_html=True)
    s1, s2, s3, _ = st.columns([0.9, 1.1, 1.3, 1.0])
    with s1:
        st.number_input(
            "% SALDO",
            min_value=0.0,
            max_value=100.0,
            step=5.0,
            format="%.2f",
            key="w_perc_saldo",
            on_change=on_perc_saldo_change,
        )
    with s2:
        st.date_input(
            "DATA SALDO (DD/MM/AAAA)",
            value=get_campo("data_saldo"),
            format="DD/MM/YYYY",
            key="w_data_saldo",
            help="Formato brasileiro: dia/mês/ano. No calendário, YYYY equivale a AAAA (ano com quatro dígitos).",
            on_change=sync_campo,
            args=("w_data_saldo", "data_saldo"),
        )
    with s3:
        st.number_input(
            "VALOR SALDO (R$)",
            min_value=0.0,
            step=100.0,
            format="%.2f",
            key="w_val_saldo",
            on_change=on_val_saldo_change,
        )

    total_previsto_now = to_float(get_campo("valor_adiant", 0.0)) + to_float(get_campo("valor_saldo", 0.0))
    st.markdown(
        f"""
            <div class="faeg-recebimento-banner">
                <span class="faeg-recebimento-label">Total Previsto (Adiant. + Saldo):</span>
                <span class="faeg-recebimento-val">{fmt_brl(total_previsto_now)}</span>
            </div>
            """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="sec-subtitle">Recebimentos Efetivamente Confirmados</div>', unsafe_allow_html=True)
    st.caption(
        "Os valores de adiantamento e saldo acima são PREVISÕES da negociação. "
        "Registre abaixo cada entrada realmente recebida, com data e valor próprios; "
        "o saldo em aberto será atualizado pela soma desses pagamentos."
    )

    if viagem_sel_id == 0:
        st.info("Primeiro salve o frete. Os recebimentos reais são vinculados ao ID do frete já cadastrado.")
    else:
        recebimentos_frete = carregar_recebimentos_viagem(viagem_sel_id)
        recebimentos_ativos = [r for r in recebimentos_frete if not r["cancelado"]]
        total_recebido_agora = round(sum(r["valor_recebido"] for r in recebimentos_ativos), 2)
        valor_contratado_agora = to_float(get_campo("valor_negociado", 0.0))
        saldo_em_aberto_agora = round(max(0.0, valor_contratado_agora - total_recebido_agora), 2)
        excedente_agora = round(max(0.0, total_recebido_agora - valor_contratado_agora), 2)

        exibir_indicadores(
            [
                ("VALOR NEGOCIADO", fmt_brl(valor_contratado_agora)),
                ("TOTAL RECEBIDO DE FATO", fmt_brl(total_recebido_agora)),
                ("SALDO A RECEBER", fmt_brl(saldo_em_aberto_agora), "destaque"),
            ],
            colunas=3,
        )
        if excedente_agora > 0:
            st.warning(f"Recebimentos excedem o valor negociado em {fmt_brl(excedente_agora)}. Confira os lançamentos ou a negociação.")
        st.caption("O valor negociado nesta tela pode ter alterações ainda não salvas; os recebimentos exibidos já estão registrados no banco.")

        with st.form("form_recebimento_frete", clear_on_submit=False):
            r1, r2, r3, r4 = st.columns([1.2, 1.2, 1.2, 1.4])
            with r1:
                data_receb = st.date_input("DATA DO RECEBIMENTO *", value=date.today(), format="DD/MM/YYYY", key="rec_data")
            with r2:
                tipo_receb = st.selectbox("PARCELA / ORIGEM *", ["Adiantamento", "Saldo", "Pagamento Parcial", "Outros"], key="rec_tipo")
            with r3:
                valor_receb = st.number_input("RECEBIDO (R$) *", min_value=0.01, value=0.01, step=50.0, format="%.2f", key="rec_valor")
            with r4:
                forma_receb = st.selectbox("FORMA DE PAGAMENTO", ["Pix", "Transferência", "TED", "Depósito", "Boleto", "Dinheiro", "Outros"], key="rec_forma")
            ref_col, obs_col = st.columns(2)
            with ref_col:
                ref_receb = st.text_input("REFERÊNCIA / COMPROVANTE", placeholder="Ex: ID da transação Pix", max_chars=120, key="rec_ref")
            with obs_col:
                obs_receb = st.text_input("OBSERVAÇÃO", placeholder="Ex: parcela recebida do cliente", max_chars=200, key="rec_obs")

            acima_negociado = (
                valor_contratado_agora > 0
                and total_recebido_agora + valor_receb > valor_contratado_agora + 0.01
            )
            confirmar_excedente = st.checkbox(
                "Confirmo que o recebimento ultrapassa o valor negociado",
                value=False,
                key="rec_confirmar_excedente",
            ) if acima_negociado else False
            registrar_receb = st.form_submit_button("Registrar Recebimento Confirmado", use_container_width=True)

        if registrar_receb:
            if acima_negociado and not confirmar_excedente:
                st.warning("Confirme expressamente o valor acima do negociado antes de registrar.")
            else:
                valor_novo = round(float(valor_receb), 2)
                ref_normalizada = ref_receb.strip()
                with SessionLocal() as session:
                    lancamentos_anteriores = session.query(RecebimentoFrete).filter_by(
                        id_viagem=viagem_sel_id, cancelado=False
                    ).all()
                    duplicado = any(
                        (
                            (ref_normalizada and (p.referencia or "").strip().casefold() == ref_normalizada.casefold())
                            or (
                                not ref_normalizada and not (p.referencia or "").strip()
                                and p.data_recebimento == data_receb
                                and p.tipo_parcela == tipo_receb
                                and round(float(p.valor_recebido), 2) == valor_novo
                            )
                        )
                        for p in lancamentos_anteriores
                    )
                    if duplicado:
                        st.warning("Possível pagamento já registrado. Confira o histórico; se forem dois pagamentos iguais, informe uma referência distinta.")
                    else:
                        session.add(RecebimentoFrete(
                            id_viagem=viagem_sel_id,
                            data_recebimento=data_receb,
                            tipo_parcela=tipo_receb,
                            forma_pagamento=forma_receb,
                            referencia=ref_normalizada or None,
                            observacao=obs_receb.strip() or None,
                            valor_recebido=valor_novo,
                        ))
                        session.commit()
                        carregar_todos_recebimentos.clear()
                        carregar_recebimentos_viagem.clear()
                        carregar_todas_viagens_consulta.clear()
                        st.toast("Recebimento confirmado registrado!", icon="✅")
                        st.rerun()

        if recebimentos_frete:
            st.dataframe(
                pd.DataFrame([
                    {
                        "ID": r["id_recebimento"],
                        "Data": r["data_recebimento"].strftime("%d/%m/%Y"),
                        "Parcela": r["tipo_parcela"],
                        "Forma": r["forma_pagamento"],
                        "Referência": r["referencia"] or "-",
                        "Valor (R$)": r["valor_recebido"],
                        "Situação": "Cancelado" if r["cancelado"] else "Confirmado",
                        "Motivo cancelamento": r["motivo_cancelamento"] or "",
                    }
                    for r in reversed(recebimentos_frete)
                ]),
                hide_index=True,
                use_container_width=True,
            )
            if recebimentos_ativos:
                with st.expander("Corrigir lançamento: cancelar recebimento sem apagar histórico"):
                    opcoes_cancelamento = {r["id_recebimento"]: r for r in recebimentos_ativos}
                    cancelar_id = st.selectbox(
                        "RECEBIMENTO A CANCELAR",
                        options=list(opcoes_cancelamento),
                        format_func=lambda i: (
                            f"#{i} — {opcoes_cancelamento[i]['data_recebimento'].strftime('%d/%m/%Y')} "
                            f"— {fmt_brl(opcoes_cancelamento[i]['valor_recebido'])}"
                        ),
                        key="rec_cancelar_id",
                    )
                    motivo_cancelamento = st.text_input(
                        "MOTIVO DO CANCELAMENTO *",
                        max_chars=200,
                        placeholder="Ex: lançamento repetido / valor informado incorretamente",
                        key="rec_motivo_cancelamento",
                    )
                    if st.button("Confirmar Cancelamento do Recebimento", key="rec_btn_cancelar"):
                        if len(motivo_cancelamento.strip()) < 6:
                            st.warning("Informe o motivo do cancelamento com pelo menos 6 caracteres.")
                        else:
                            with SessionLocal() as session:
                                recebido_db = session.query(RecebimentoFrete).filter_by(
                                    id_recebimento=cancelar_id, id_viagem=viagem_sel_id, cancelado=False
                                ).first()
                                if recebido_db is not None:
                                    recebido_db.cancelado = True
                                    recebido_db.data_cancelamento = date.today()
                                    recebido_db.motivo_cancelamento = motivo_cancelamento.strip()
                                    session.commit()
                            carregar_todos_recebimentos.clear()
                            carregar_recebimentos_viagem.clear()
                            carregar_todas_viagens_consulta.clear()
                            st.toast("Recebimento cancelado, mantendo histórico.", icon="🧾")
                            st.rerun()
        else:
            st.info("Nenhum recebimento efetivamente confirmado para este frete.")

    render_navegacao_rodape(3, MENU_ITENS)
