"""Etapa 8 da interface FAEG (corpo original, sem reescrever regras)."""
import pandas as pd
import streamlit as st

from database.connection import SessionLocal
from database.models import Viagem
from views.saidas_operacionais import render_saidas_operacionais
from faeg_app.core import (
    OPCOES_SITUACAO_OPERACAO,
    calcular_km_deslocamentos_formulario,
    calcular_km_planejado_operacao,
    calcular_km_total_real_operacao,
    carregar_abastecimentos_veiculo,
    carregar_despesas_viagem,
    carregar_recebimentos_viagem,
    exibir_indicadores,
    fmt_brl,
    fmt_km,
    get_campo,
    montar_previa_financeira_ciclo,
    render_navegacao_rodape,
    sync_campo,
    to_float,
    to_int,
)


def render(ctx):
    MENU_ITENS = ctx.menu_itens
    motoristas_db = ctx.motoristas_db
    veiculos_db = ctx.veiculos_db
    viagem_sel_id = ctx.viagem_sel_id

    st.markdown(
        """
            <div class="tab-header-wrap">
                <div class="tab-title"><i class="fa-solid fa-calculator"></i> Fechamento Final e DRE</div>
                <span class="tab-step-pill">Etapa 8 de 11</span>
            </div>
            """,
        unsafe_allow_html=True,
    )

    # Saídas são a fonte operacional de KM quando cadastradas. Cada frete
    # permanece com sua receita própria, mas não recebe KM compartilhados.
    resumo_saidas_atual = None
    if viagem_sel_id:
        with SessionLocal() as db:
            viagem_operacional = db.get(Viagem, viagem_sel_id)
            ciclo_atual_id = viagem_operacional.id_ciclo if viagem_operacional is not None else None
        if ciclo_atual_id is not None:
            resumo_saidas_atual = render_saidas_operacionais(
                ciclo_atual_id, veiculos_db, motoristas_db
            )
    else:
        st.info("Para cadastrar saídas operacionais, primeiro salve o frete na Etapa 1. "
                "Na sequência, registre as saídas no fechamento; os demais fretes do ciclo usarão os mesmos percursos.")
    st.markdown('<div class="sec-subtitle">Leituras e situação da operação</div>', unsafe_allow_html=True)
    if resumo_saidas_atual:
        st.caption("Leituras históricas por frete, mantidas para consulta. "
                   "Com saídas cadastradas, os indicadores de KM usam exclusivamente os odômetros das saídas abaixo, "
                   "sem somar o mesmo percurso dos fretes.")
    f1, f2, f3, f4 = st.columns([1.1, 1.1, 1.1, 1.7])
    odo_ini_v = to_int(get_campo("odo_ini", 0))
    odo_fin_v = to_int(get_campo("odo_fin", 0))
    with f1:
        odo_ini_v = st.number_input(
            "ODÔMETRO INICIAL (HISTÓRICO DO FRETE)" if resumo_saidas_atual else "ODÔMETRO INICIAL",
            min_value=0,
            step=1,
            value=odo_ini_v,
            key="w_odo_ini",
            on_change=sync_campo,
            args=("w_odo_ini", "odo_ini"),
        )
    with f2:
        odo_fin_v = st.number_input(
            "ODÔMETRO FINAL (HISTÓRICO DO FRETE)" if resumo_saidas_atual else "ODÔMETRO FINAL",
            min_value=0,
            step=1,
            value=odo_fin_v,
            key="w_odo_fin",
            on_change=sync_campo,
            args=("w_odo_fin", "odo_fin"),
        )
    km_real_calc = (
        to_int(odo_fin_v) - to_int(odo_ini_v)
        if to_int(odo_ini_v) > 0 and to_int(odo_fin_v) >= to_int(odo_ini_v)
        else None
    )
    with f3:
        st.text_input(
            "KM REAL RODADO",
            value=f"{km_real_calc} km" if km_real_calc is not None else "Não informado",
            disabled=True,
            key=f"prev_km_{km_real_calc}",
        )
    if odo_ini_v > 0 and odo_fin_v > 0 and odo_fin_v < odo_ini_v:
        st.error("Leituras inconsistentes: odômetro final menor que o inicial.")
    with f4:
        st_atual = get_campo("status_viagem", "Aguardando Adiantamento")
        st.selectbox(
            "SITUAÇÃO DA OPERAÇÃO",
            OPCOES_SITUACAO_OPERACAO,
            index=OPCOES_SITUACAO_OPERACAO.index(st_atual) if st_atual in OPCOES_SITUACAO_OPERACAO else 0,
            key="w_status_viagem",
            on_change=sync_campo,
            args=("w_status_viagem", "status_viagem"),
        )

    st.caption(
        "Os odômetros da operação são compartilhados com a Etapa 2. "
        "O odômetro de cada abastecimento permanece independente na Etapa 7."
    )

    modo_saidas = resumo_saidas_atual is not None
    if modo_saidas:
        # Fonte física única: não chamar cálculos legados que podem gerar
        # alertas indevidos para odômetros por frete de uma mesma rota.
        km_planejado_op = resumo_saidas_atual["km_planejado"]
        km_deslocamentos_op = 0.0
        km_total_previsto_op = km_planejado_op
        km_total_real_op = resumo_saidas_atual["km_real"]
        st.info("**KM da operação por saídas operacionais.** Os campos de KM dos fretes "
                "e os deslocamentos antigos não entram nessa soma. "
                "Não transfira valores históricos sem conferência.")
    else:
        km_planejado_op = calcular_km_planejado_operacao(viagem_sel_id)
        km_deslocamentos_op = calcular_km_deslocamentos_formulario()
        km_total_previsto_op = round(km_planejado_op + km_deslocamentos_op, 2)
        km_total_real_op = calcular_km_total_real_operacao(viagem_sel_id, odo_ini_v, odo_fin_v)

    if km_total_real_op is not None:
        diferenca_km = km_total_real_op - km_total_previsto_op
        diferenca_formatada = ("+" if diferenca_km > 0 else "") + fmt_km(diferenca_km)
        if km_total_previsto_op > 0:
            desvio_percentual = (diferenca_km / km_total_previsto_op) * 100
            desvio_formatado = (
                f"{desvio_percentual:+.1f}%" if abs(desvio_percentual) >= 0.05
                else "0,0%"
            ).replace(".", ",")
        else:
            desvio_formatado = "Não calculável"
        cor_diferenca = " is-warning" if diferenca_km > 0 else ""
        classe_real = ""
        nota_diferenca = "Positivo indica KM acima do previsto."
    else:
        diferenca_km = None
        diferenca_formatada = "Não calculável"
        desvio_formatado = "Não calculável"
        cor_diferenca = ""
        classe_real = " is-unavailable"
        nota_diferenca = "Aguardando odômetros válidos."

    descricao_real = (
        "Soma das saídas físicas, sem intervalos sobrepostos."
        if modo_saidas else
        "Soma dos intervalos válidos dos fretes do ciclo."
        if get_campo("tipo_viagem", "Individual") == "Ciclo"
        else "Diferença entre os dois odômetros da operação."
    )
    etiqueta_operacao = (
        "Ciclo operacional" if get_campo("tipo_viagem", "Individual") == "Ciclo"
        else "Frete individual"
    )
    rotulo_km_planejado = "KM planejado das saídas" if modo_saidas else "KM planejado dos fretes"
    nota_km_planejado = "Trechos físicos, sem duplicar fretes." if modo_saidas else "Trechos informados na Etapa 2."
    nota_km_deslocamentos = "Incluído nas saídas físicas." if modo_saidas else "Saída / entre coletas + retorno."
    nota_km_total = "Saídas físicas, sem duplicações." if modo_saidas else "Fretes + deslocamentos, sem repetição."
    st.markdown(
        f"""
            <section class="faeg-km-dashboard" aria-label="Resumo da quilometragem da operação">
                <div class="faeg-km-heading">
                    <div>
                        <div class="faeg-km-eyebrow">Planejamento e execução</div>
                        <div class="faeg-km-title">Resumo da quilometragem</div>
                    </div>
                    <span class="faeg-km-tag">{etiqueta_operacao}</span>
                </div>
                <div class="faeg-km-group-label">Planejado</div>
                <div class="faeg-km-grid">
                    <article class="faeg-km-card">
                        <div class="faeg-km-card-label">{rotulo_km_planejado}</div>
                        <div class="faeg-km-card-value">{fmt_km(km_planejado_op)}</div>
                        <div class="faeg-km-card-note">{nota_km_planejado}</div>
                    </article>
                    <article class="faeg-km-card">
                        <div class="faeg-km-card-label">KM deslocamentos operacionais</div>
                        <div class="faeg-km-card-value">{fmt_km(km_deslocamentos_op)}</div>
                        <div class="faeg-km-card-note">{nota_km_deslocamentos}</div>
                    </article>
                    <article class="faeg-km-card is-primary">
                        <div class="faeg-km-card-label">KM total planejado</div>
                        <div class="faeg-km-card-value">{fmt_km(km_total_previsto_op)}</div>
                        <div class="faeg-km-card-note">{nota_km_total}</div>
                    </article>
                </div>
                <div class="faeg-km-formula">
                    Memória: {fmt_km(km_planejado_op)} + {fmt_km(km_deslocamentos_op)}
                    = {fmt_km(km_total_previsto_op)} planejados.
                </div>
                <div class="faeg-km-group-label">Realizado e comparação</div>
                <div class="faeg-km-grid">
                    <article class="faeg-km-card{classe_real}">
                        <div class="faeg-km-card-label">KM total real</div>
                        <div class="faeg-km-card-value">{fmt_km(km_total_real_op) if km_total_real_op is not None else 'Não informado'}</div>
                        <div class="faeg-km-card-note">{descricao_real}</div>
                    </article>
                    <article class="faeg-km-card{cor_diferenca}">
                        <div class="faeg-km-card-label">Diferença: real − planejado</div>
                        <div class="faeg-km-card-value">{diferenca_formatada}</div>
                        <div class="faeg-km-card-note">{nota_diferenca}</div>
                    </article>
                    <article class="faeg-km-card">
                        <div class="faeg-km-card-label">Desvio do planejado</div>
                        <div class="faeg-km-card-value">{desvio_formatado}</div>
                        <div class="faeg-km-card-note">Percentual sobre o total planejado.</div>
                    </article>
                </div>
            </section>
            """,
        unsafe_allow_html=True,
    )

    if not modo_saidas and to_float(get_campo("km_rota", 0.0)) <= 0:
        st.warning(
            "O campo KM INDIVIDUAL / CICLO do frete atual ainda está zerado "
            "na Etapa 2. Confira se o trecho foi realmente planejado antes "
            "de considerar o KM Total Planejado como completo."
        )

    with st.expander("Ver detalhes dos cálculos de KM", expanded=False):
        if modo_saidas:
            st.info("Para a operação atual, os quilômetros são calculados pelas saídas/trechos "
                    "cadastrados acima. Os textos abaixo descrevem somente o método legado dos fretes.")
        st.markdown(
            "**KM planejado (modo legado):** no frete individual, usa o KM manual da Etapa 2; "
            "no ciclo, soma os fretes vinculados ao mesmo ID interno."
        )
        if get_campo("km_componentes_discriminados", True):
            st.markdown(
                f"**Deslocamentos operacionais:** saída / entre coletas "
                f"({fmt_km(get_campo('km_saida_entre_coletas', 0.0))}) + "
                f"retorno ({fmt_km(get_campo('km_retorno_operacional', 0.0))}) "
                f"= **{fmt_km(km_deslocamentos_op)}**, contados uma única vez por ciclo."
            )
        else:
            st.info(
                "Os KM de deslocamentos foram registrados antes da separação dos campos. "
                "O valor anterior foi preservado; a discriminação deve ser feita na Etapa 2."
            )
        st.markdown(
            "**KM total real:** diferença dos odômetros para frete individual; "
            "no ciclo, soma dos intervalos válidos dos fretes, sem sobreposição no mesmo veículo. "
            "**Diferença:** KM total real menos KM total planejado."
        )
    if km_total_real_op is None:
        st.info(
            "O KM real consolidado fica indisponível até haver odômetros válidos "
            + ("para TODAS as saídas, sem intervalos sobrepostos."
               if modo_saidas else
               "para os fretes envolvidos, sem intervalos sobrepostos.")
        )

    v_neg_dre = to_float(get_campo("valor_negociado", 0.0))
    v_rec_dre = to_float(get_campo("valor_adiant", 0.0)) + to_float(get_campo("valor_saldo", 0.0))
    receita_dre = v_neg_dre

    if viagem_sel_id == 0:
        custos_dre = sum(to_float(d["valor_total"]) for d in st.session_state.get("despesas_temp", []))
    else:
        custos_dre = sum(to_float(d["valor_total"]) for d in carregar_despesas_viagem(viagem_sel_id))

    resultado_dre = receita_dre - custos_dre
    eh_frete_em_ciclo = get_campo("tipo_viagem", "Individual") == "Ciclo"
    titulo_resultado_frete = (
        "Saldo comercial do frete antes dos custos compartilhados" if eh_frete_em_ciclo
        else "Resultado operacional parcial da viagem"
    )
    cor_res = "#4ADE80" if resultado_dre >= 0 else "#F87171"

    st.markdown(
        f"""
            <div class="dre-box">
                <div class="dre-header">{titulo_resultado_frete} (FAEG)</div>
                <div class="dre-row">
                    <span style="color:#ABCEE1;">Receita Prevista (Frete Negociado)</span>
                    <span style="font-weight:800; font-size:1.15rem;">{fmt_brl(receita_dre)}</span>
                </div>
                <div class="dre-row">
                    <span style="color:#ABCEE1;">Custos Totais (Combustível, Pedágios e Outras Despesas)</span>
                    <span style="font-weight:800; font-size:1.15rem; color:#F34D25;">- {fmt_brl(custos_dre)}</span>
                </div>
                <div class="dre-total-row">
                    <span style="font-weight:800; text-transform:uppercase; letter-spacing:0.04em;">{titulo_resultado_frete}</span>
                    <span style="font-weight:900; font-size:1.85rem; color:{cor_res};">{fmt_brl(resultado_dre)}</span>
                </div>
            </div>
            """,
        unsafe_allow_html=True,
    )
    st.caption(
        "Este painel inclui apenas despesas lançadas diretamente no frete. "
        "Em ciclos, NÃO representa lucro por frete: despesas comuns e combustível "
        "da operação são consolidados no fechamento do ciclo. "
        "O custo estimado por consumo é uma simulação independente e NÃO é somado à DRE."
        if eh_frete_em_ciclo else
        "Custos do histórico de abastecimentos por veículo não são somados aqui; "
        "apenas despesas financeiras vinculadas à viagem entram no resultado."
    )

    st.markdown('<div class="sec-subtitle">Situação dos Recebimentos Efetivos do Frete</div>', unsafe_allow_html=True)
    reais_recebidos = sum(
        r["valor_recebido"] for r in carregar_recebimentos_viagem(viagem_sel_id)
        if not r["cancelado"]
    )
    exibir_indicadores(
        [
            ("NEGOCIADO", fmt_brl(v_neg_dre)),
            ("RECEBIDO DE FATO", fmt_brl(reais_recebidos)),
            ("SALDO A RECEBER", fmt_brl(max(0.0, v_neg_dre - reais_recebidos)), "destaque"),
        ],
        colunas=3,
    )
    if viagem_sel_id == 0:
        st.caption("Para registrar pagamentos efetivos na Etapa 4, primeiro salve o frete.")
    elif reais_recebidos > v_neg_dre + 0.01:
        st.warning("O total recebido supera o valor negociado. Confira os lançamentos e o contrato.")

    if get_campo("tipo_viagem", "Individual") == "Ciclo":
        st.markdown('<div class="sec-subtitle">Prévia do Fechamento Financeiro do Ciclo</div>', unsafe_allow_html=True)
        previa = montar_previa_financeira_ciclo(viagem_sel_id, custos_dre)
        if previa is None:
            st.info(
                "Informe o Nº do Ciclo Operacional na Etapa 1. "
                "Se houver ciclos homônimos no banco, confira os respectivos IDs internos."
            )
        else:
            st.caption(
                "Consolida os fretes do mesmo ID Ciclo, incluindo os valores ainda não salvos "
                "deste formulário. Despesas dos fretes são somadas individualmente; "
                "despesas compartilhadas entram uma única vez por ID do ciclo."
            )
            exibir_indicadores(
                [
                    ("FRETES NO CICLO", previa["qtd_fretes"]),
                    ("RECEITA NEGOCIADA DO CICLO", fmt_brl(previa["valor_negociado_total"])),
                    ("DESPESAS FINANCEIRAS DO CICLO", fmt_brl(previa["despesas_total"])),
                    ("RESULTADO OPERACIONAL PARCIAL", fmt_brl(previa["resultado_operacional_parcial"]), "destaque"),
                ],
                colunas=4,
            )
            st.caption(
                f"Composição das despesas: fretes {fmt_brl(previa['despesas_fretes_total'])} "
                f"+ compartilhadas {fmt_brl(previa['despesas_compartilhadas_total'])}. "
                "Gastos compartilhados não são rateados entre os fretes."
            )

            with st.expander("Ver parcelas, recebimentos e fretes do ciclo", expanded=False):
                exibir_indicadores(
                    [
                        ("ADIANTAMENTOS PREVISTOS", fmt_brl(previa["adiantamentos_previstos"])),
                        ("SALDOS PREVISTOS", fmt_brl(previa["saldos_previstos"])),
                        ("PARCELAS PREVISTAS", fmt_brl(previa["parcelas_previstas"])),
                    ],
                    colunas=3,
                )
                exibir_indicadores(
                    [
                        ("RECEBIDO EFETIVAMENTE NO CICLO", fmt_brl(previa["total_recebido"])),
                        ("SALDO A RECEBER DO CICLO", fmt_brl(previa["saldo_a_receber"]) if previa["saldo_a_receber"] is not None else "Conferir financeiro legado", "destaque"),
                    ],
                    colunas=2,
                )
                st.caption("Adiantamento e saldo previstos não comprovam recebimento. O ciclo soma apenas pagamentos realmente registrados na Etapa 4 de cada frete.")

                st.dataframe(
                    pd.DataFrame([
                        {
                            "ID Frete": i["id_frete"],
                            "Código Viagem": i["codigo_viagem"],
                            "Cliente": i["cliente"],
                            "Negociado Considerado (R$)": to_float(i["negociado_considerado"]),
                            "Recebido de Fato (R$)": to_float(i["total_recebido"]),
                            "Despesas (R$)": to_float(i["total_despesas"]),
                            "Situação Financeira": "Legado para conferir" if i["financeiro_legado_ambiguo"] else "Individualizado",
                        }
                        for i in previa["fretes"]
                    ]),
                    hide_index=True,
                    use_container_width=True,
                )
            if previa["qtd_financeiros_legados_ambiguos"]:
                st.warning(
                    "Há frete(s) com dados financeiros legados compartilhados por vários "
                    "fretes. Seus valores negociados não entraram na soma para impedir "
                    "duplicação; confira e salve os dados financeiros individualmente."
                )

    vei_km_id = get_campo("vei_id", 0)
    if vei_km_id:
        with st.expander("Indicadores de consumo do veículo · abastecimentos", expanded=False):
            historico_km = carregar_abastecimentos_veiculo(vei_km_id)
            ultima_medicao = next(
                (a for a in reversed(historico_km) if a["km_por_litro"] is not None),
                None,
            )
            if ultima_medicao:
                exibir_indicadores(
                    [
                        ("KM ENTRE ABASTECIMENTOS", fmt_km(ultima_medicao["km_intervalo"])),
                        ("MÉDIA INDICATIVA DE DIESEL", f"{ultima_medicao['km_por_litro']:.2f} km/L"),
                        ("CUSTO INDICATIVO DE DIESEL/KM", fmt_brl(ultima_medicao["custo_por_km"])),
                    ],
                    colunas=3,
                )
                st.caption("Base: abastecimentos consecutivos de Diesel do veículo na Etapa 7, com tanque cheio. Não é o KM da viagem ou do ciclo.")
            else:
                st.caption("Registre ao menos dois abastecimentos consecutivos de Diesel com odômetros válidos na Etapa 7 para calcular o consumo.")

    render_navegacao_rodape(7, MENU_ITENS)
