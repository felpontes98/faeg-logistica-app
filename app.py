from datetime import date, datetime, time
from io import BytesIO
import re
import pandas as pd
import streamlit as st
from sqlalchemy.orm import joinedload

from database.connection import Base, SessionLocal, engine
from database.importador_planilha import (
    extrair_registros_planilha,
    importar_registros_para_banco,
    listar_abas_planilha,
)
from database.models import (
    CicloFinanceiro,
    CicloOperacional,
    Cliente,
    Fornecedor,
    Local,
    Motorista,
    Veiculo,
    Viagem,
    ViagemDespesa,
    gerar_proximo_codigo_viagem,
    separar_rota,
    sincronizar_colunas_banco,
)

# ==============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA E INICIALIZAÇÃO DO BANCO
# ==============================================================================

st.set_page_config(
    page_title="FAEG LOG | Controle Operacional",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def inicializar_banco():
    Base.metadata.create_all(bind=engine)
    sincronizar_colunas_banco()
    return True


inicializar_banco()

CATEGORIAS_UNIFICADAS = [
    "Posto de Combustível",
    "Abast. ARLA",
    "Oficina Mecânica",
    "Borracharia",
    "Hospedagem",
    "Concessionária Pedágio",
    "Auxiliar",
    "Alimentação",
    "Lava-jato",
    "Outros",
]

OPCOES_TIPO_FRETE = ["Dedicado", "Complemento", "Cheio", "Fracionado", "Agregado"]
OPCOES_STATUS_VIAGEM = ["Planejada", "Em Trânsito", "Descarregando", "Concluída", "Cancelada"]

st.markdown(
    """
    <style>
        .stApp { background-color: #f8fafc; }
        section[data-testid="stSidebar"] {
            background-color: #ffffff;
            border-right: 1px solid #e2e8f0;
        }
        .faeg-logo {
            font-size: 1.55rem;
            font-weight: 800;
            color: #1d4ed8;
            letter-spacing: -0.02em;
            margin-bottom: 0;
        }
        .faeg-sub {
            font-size: 0.72rem;
            font-weight: 700;
            color: #64748b;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 1rem;
        }
        .dre-card {
            background-color: #0f172a;
            color: #f8fafc;
            border-radius: 12px;
            padding: 1.5rem;
            margin-top: 1rem;
        }
        .kpi-box {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 1rem 1.2rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ==============================================================================
# 2. FORMATAÇÃO E ESTADO DA SESSÃO
# ==============================================================================


def fmt_brl(valor) -> str:
    val = float(valor or 0.0)
    return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def inicializar_estado_formulario(db, forcar_novo: bool = False):
    if "form_inicializado" in st.session_state and not forcar_novo:
        return

    proximo_cod = gerar_proximo_codigo_viagem(db)
    st.session_state["form_inicializado"] = True
    st.session_state["viagem_editando_id"] = None
    st.session_state["f_codigo_viagem"] = proximo_cod
    st.session_state["f_status_viagem"] = "Planejada"
    st.session_state["f_tipo_viagem"] = "Individual"
    st.session_state["f_tipo_frete"] = "Dedicado"
    st.session_state["f_id_ciclo_existente"] = None
    st.session_state["f_nome_operacao"] = ""
    st.session_state["f_id_motorista"] = None
    st.session_state["f_id_veiculo"] = None

    # Frete e Docs
    st.session_state["f_id_frete"] = ""
    st.session_state["f_data_frete"] = date.today()
    st.session_state["f_rota_origem"] = ""
    st.session_state["f_rota_destino"] = ""
    st.session_state["f_km_planejado"] = 0.0
    st.session_state["f_tipo_material"] = ""
    st.session_state["f_qtde_volumes"] = 0
    st.session_state["f_volume_m3"] = 0.0
    st.session_state["f_peso_kg"] = 0.0
    st.session_state["f_nfe"] = ""
    st.session_state["f_cte"] = ""
    st.session_state["f_mdfe"] = ""
    st.session_state["f_ciot"] = ""

    # Cliente
    st.session_state["f_id_cliente"] = None

    # Negociação / Pagamento
    st.session_state["f_forma_contratacao"] = "Viagem Fechada"
    st.session_state["f_valor_divulgado"] = 0.0
    st.session_state["f_valor_negociado"] = 0.0
    st.session_state["f_perc_adiantamento"] = 0.0
    st.session_state["f_valor_adiantamento"] = 0.0
    st.session_state["f_data_adiantamento"] = date.today()
    st.session_state["f_perc_saldo"] = 100.0
    st.session_state["f_valor_saldo"] = 0.0
    st.session_state["f_data_saldo"] = date.today()
    st.session_state["f_forma_pagamento"] = "Pix"
    st.session_state["f_banco_conta"] = ""
    st.session_state["f_obs_saldo"] = ""

    # Coleta e Entrega
    st.session_state["f_id_local_coleta"] = None
    st.session_state["f_data_coleta"] = date.today()
    st.session_state["f_hora_plan_coleta"] = time(8, 0)
    st.session_state["f_hora_real_coleta"] = time(8, 0)
    st.session_state["f_obs_coleta"] = ""

    st.session_state["f_id_local_entrega"] = None
    st.session_state["f_data_entrega"] = date.today()
    st.session_state["f_hora_plan_entrega"] = time(17, 0)
    st.session_state["f_hora_real_entrega"] = time(17, 0)
    st.session_state["f_documento_entrega"] = ""
    st.session_state["f_obs_entrega"] = ""

    # Despesas temporárias (quando viagem ainda não foi salva no banco)
    st.session_state["despesas_rascunho"] = []
    st.session_state["despesa_edit_idx"] = None

    # Fechamento
    st.session_state["f_odometro_ini"] = 0
    st.session_state["f_odometro_fin"] = 0
    st.session_state["f_obs_geral"] = ""


def carregar_viagem_no_formulario(db, id_viagem: int):
    v = (
        db.query(Viagem)
        .options(
            joinedload(Viagem.ciclo).joinedload(CicloOperacional.financeiro),
            joinedload(Viagem.despesas),
        )
        .filter(Viagem.id_viagem == id_viagem)
        .first()
    )
    if not v:
        return

    ciclo = v.ciclo
    fin = ciclo.financeiro if ciclo else None

    orig = v.rota_origem or ""
    dest = v.rota_destino or ""
    if (not orig or not dest) and v.rota_resumo:
        o_sp, d_sp = separar_rota(v.rota_resumo)
        orig = orig or o_sp
        dest = dest or d_sp

    st.session_state["form_inicializado"] = True
    st.session_state["viagem_editando_id"] = v.id_viagem
    st.session_state["f_codigo_viagem"] = v.codigo_viagem or f"V{v.id_viagem}"
    st.session_state["f_status_viagem"] = (
        v.status_viagem if v.status_viagem in OPCOES_STATUS_VIAGEM else "Planejada"
    )
    st.session_state["f_tipo_viagem"] = (
        v.tipo_viagem if v.tipo_viagem in ["Individual", "Ciclo"] else "Individual"
    )
    st.session_state["f_tipo_frete"] = (
        v.tipo_frete if v.tipo_frete in OPCOES_TIPO_FRETE else "Dedicado"
    )
    st.session_state["f_id_ciclo_existente"] = v.id_ciclo
    st.session_state["f_nome_operacao"] = ciclo.nome_operacao if ciclo else ""
    st.session_state["f_id_motorista"] = v.id_motorista
    st.session_state["f_id_veiculo"] = v.id_veiculo

    st.session_state["f_id_frete"] = v.id_frete_externo or ""
    st.session_state["f_data_frete"] = v.data_frete or (
        ciclo.data_abertura if ciclo and ciclo.data_abertura else date.today()
    )
    st.session_state["f_rota_origem"] = orig
    st.session_state["f_rota_destino"] = dest
    st.session_state["f_km_planejado"] = float(v.km_rota_planejado or 0.0)
    st.session_state["f_tipo_material"] = v.tipo_material or ""
    st.session_state["f_qtde_volumes"] = int(v.qtde_volumes or 0)
    st.session_state["f_volume_m3"] = float(v.volume_m3 or 0.0)
    st.session_state["f_peso_kg"] = float(v.peso_bruto_kg or 0.0)
    st.session_state["f_nfe"] = v.nfe_carga or ""
    st.session_state["f_cte"] = v.cte_numero or ""
    st.session_state["f_mdfe"] = v.mdfe_numero or ""
    st.session_state["f_ciot"] = v.ciot_numero or ""

    st.session_state["f_id_cliente"] = ciclo.id_cliente if ciclo else None

    if fin:
        val_neg = float(fin.valor_negociado_total or 0.0)
        val_adiant = float(fin.valor_adiantamento or 0.0)
        perc_adiant = float(fin.perc_adiantamento or 0.0)
        if perc_adiant == 0.0 and val_neg > 0 and val_adiant > 0:
            perc_adiant = round((val_adiant / val_neg) * 100.0, 2)
        perc_saldo = float(fin.perc_saldo) if fin.perc_saldo is not None else round(100.0 - perc_adiant, 2)
        val_saldo = float(fin.valor_saldo) if fin.valor_saldo is not None else round(val_neg - val_adiant, 2)

        st.session_state["f_forma_contratacao"] = fin.forma_contratacao or "Viagem Fechada"
        st.session_state["f_valor_divulgado"] = float(fin.valor_divulgado or 0.0)
        st.session_state["f_valor_negociado"] = val_neg
        st.session_state["f_perc_adiantamento"] = perc_adiant
        st.session_state["f_valor_adiantamento"] = val_adiant
        st.session_state["f_data_adiantamento"] = fin.data_prevista_adiantamento or date.today()
        st.session_state["f_perc_saldo"] = perc_saldo
        st.session_state["f_valor_saldo"] = val_saldo
        st.session_state["f_data_saldo"] = fin.data_prevista_saldo or date.today()
        st.session_state["f_forma_pagamento"] = fin.forma_pagamento or "Pix"
        st.session_state["f_banco_conta"] = fin.banco_conta or ""
        st.session_state["f_obs_saldo"] = fin.obs_saldo or ""

    st.session_state["f_id_local_coleta"] = v.id_local_coleta
    st.session_state["f_data_coleta"] = v.data_coleta or date.today()
    st.session_state["f_hora_plan_coleta"] = v.hora_planejada_coleta or time(8, 0)
    st.session_state["f_hora_real_coleta"] = v.hora_real_coleta or time(8, 0)
    st.session_state["f_obs_coleta"] = v.obs_coleta or ""

    st.session_state["f_id_local_entrega"] = v.id_local_entrega
    st.session_state["f_data_entrega"] = v.data_entrega or date.today()
    st.session_state["f_hora_plan_entrega"] = v.hora_planejada_entrega or time(17, 0)
    st.session_state["f_hora_real_entrega"] = v.hora_real_entrega or time(17, 0)
    st.session_state["f_documento_entrega"] = v.documento_entrega or ""
    st.session_state["f_obs_entrega"] = v.obs_entrega or ""

    st.session_state["despesas_rascunho"] = [
        {
            "id_despesa": d.id_despesa,
            "id_fornecedor": d.id_fornecedor,
            "tipo_despesa": d.tipo_despesa,
            "descricao_detalhe": d.descricao_detalhe or "",
            "quantidade": float(d.quantidade or 1.0),
            "valor_unitario": float(d.valor_unitario or 0.0),
            "valor_total": float(d.valor_total or 0.0),
            "data_despesa": d.data_despesa or date.today(),
        }
        for d in v.despesas
    ]
    st.session_state["despesa_edit_idx"] = None

    st.session_state["f_odometro_ini"] = int(v.odometro_inicial or 0)
    st.session_state["f_odometro_fin"] = int(v.odometro_final or 0)
    st.session_state["f_obs_geral"] = v.observacao_geral or ""


# ==============================================================================
# 3. CALLBACKS DE CÁLCULO FINANCEIRO AUTOMÁTICO (ETAPA 4)
# ==============================================================================


def recalcular_por_percentual():
    neg = float(st.session_state.get("f_valor_negociado", 0.0))
    p_adiant = float(st.session_state.get("f_perc_adiantamento", 0.0))
    v_adiant = round(neg * (p_adiant / 100.0), 2)
    p_saldo = round(max(0.0, 100.0 - p_adiant), 2)
    v_saldo = round(max(0.0, neg - v_adiant), 2)
    st.session_state["f_valor_adiantamento"] = v_adiant
    st.session_state["f_perc_saldo"] = p_saldo
    st.session_state["f_valor_saldo"] = v_saldo


def recalcular_por_valor_adiantamento():
    neg = float(st.session_state.get("f_valor_negociado", 0.0))
    v_adiant = float(st.session_state.get("f_valor_adiantamento", 0.0))
    p_adiant = round((v_adiant / neg) * 100.0, 2) if neg > 0 else 0.0
    p_saldo = round(max(0.0, 100.0 - p_adiant), 2)
    v_saldo = round(max(0.0, neg - v_adiant), 2)
    st.session_state["f_perc_adiantamento"] = p_adiant
    st.session_state["f_perc_saldo"] = p_saldo
    st.session_state["f_valor_saldo"] = v_saldo


# ==============================================================================
# 4. FUNÇÃO DE SALVAMENTO DA VIAGEM NO NEON (POSTGRESQL)
# ==============================================================================


def salvar_viagem_completa(db) -> tuple[bool, str]:
    codigo_v = str(st.session_state.get("f_codigo_viagem", "")).strip().upper()
    if not codigo_v:
        return False, "Informe o Código da Viagem (ex: V1, V2...)."

    viagem_id = st.session_state.get("viagem_editando_id")

    # Validação de unicidade do Código da Viagem
    query_dup = db.query(Viagem).filter(Viagem.codigo_viagem.ilike(codigo_v))
    if viagem_id:
        query_dup = query_dup.filter(Viagem.id_viagem != viagem_id)
    if query_dup.first():
        return (
            False,
            f"O código de viagem '{codigo_v}' já está cadastrado em outra viagem. "
            "Escolha um código único.",
        )

    id_motorista = st.session_state.get("f_id_motorista")
    id_veiculo = st.session_state.get("f_id_veiculo")
    id_cliente = st.session_state.get("f_id_cliente")
    id_coleta = st.session_state.get("f_id_local_coleta")
    id_entrega = st.session_state.get("f_id_local_entrega")

    if not id_motorista or not id_veiculo:
        return False, "Selecione o Motorista e o Veículo na aba '1. Frota FAEG'."
    if not id_cliente:
        return False, "Selecione o Cliente na aba '3. Cliente'."
    if not id_coleta or not id_entrega:
        return False, "Selecione o Local de Coleta e o Local de Entrega nas abas 5 e 6."

    origem = str(st.session_state.get("f_rota_origem", "")).strip()
    destino = str(st.session_state.get("f_rota_destino", "")).strip()
    rota_resumo = f"{origem} -> {destino}".strip(" ->")

    tipo_viagem = st.session_state.get("f_tipo_viagem", "Individual")
    id_ciclo_sel = (
        st.session_state.get("f_id_ciclo_existente") if tipo_viagem == "Ciclo" else None
    )

    # 1. Cria ou atualiza Ciclo Operacional e Financeiro
    if viagem_id:
        viagem = db.query(Viagem).filter(Viagem.id_viagem == viagem_id).first()
        ciclo = (
            db.query(CicloOperacional).filter(CicloOperacional.id_ciclo == id_ciclo_sel).first()
            if id_ciclo_sel
            else viagem.ciclo
        )
    else:
        viagem = None
        ciclo = (
            db.query(CicloOperacional).filter(CicloOperacional.id_ciclo == id_ciclo_sel).first()
            if id_ciclo_sel
            else None
        )

    if not ciclo:
        nome_op = (
            st.session_state.get("f_nome_operacao", "").strip()
            or f"{codigo_v} - {rota_resumo or 'Operação FAEG'}"
        )
        ciclo = CicloOperacional(
            id_cliente=id_cliente,
            nome_operacao=nome_op[:150],
            data_abertura=st.session_state.get("f_data_frete") or date.today(),
            data_fechamento=st.session_state.get("f_data_entrega"),
            status_ciclo=st.session_state.get("f_status_viagem", "Planejada"),
        )
        db.add(ciclo)
        db.flush()
    else:
        ciclo.id_cliente = id_cliente
        if st.session_state.get("f_nome_operacao", "").strip():
            ciclo.nome_operacao = st.session_state["f_nome_operacao"].strip()[:150]
        ciclo.status_ciclo = st.session_state.get("f_status_viagem", "Planejada")

    fin = ciclo.financeiro
    if not fin:
        fin = CicloFinanceiro(id_ciclo=ciclo.id_ciclo)
        db.add(fin)

    fin.forma_contratacao = st.session_state.get("f_forma_contratacao", "Viagem Fechada")
    fin.valor_divulgado = round(float(st.session_state.get("f_valor_divulgado", 0.0)), 2)
    fin.valor_negociado_total = round(float(st.session_state.get("f_valor_negociado", 0.0)), 2)
    fin.perc_adiantamento = round(float(st.session_state.get("f_perc_adiantamento", 0.0)), 2)
    fin.data_prevista_adiantamento = st.session_state.get("f_data_adiantamento")
    fin.valor_adiantamento = round(float(st.session_state.get("f_valor_adiantamento", 0.0)), 2)
    fin.perc_saldo = round(float(st.session_state.get("f_perc_saldo", 0.0)), 2)
    fin.data_prevista_saldo = st.session_state.get("f_data_saldo")
    fin.valor_saldo = round(float(st.session_state.get("f_valor_saldo", 0.0)), 2)
    fin.forma_pagamento = st.session_state.get("f_forma_pagamento", "")
    fin.banco_conta = st.session_state.get("f_banco_conta", "")
    fin.obs_saldo = st.session_state.get("f_obs_saldo", "")

    # 2. Cria ou atualiza Viagem
    if not viagem:
        viagem = Viagem(id_ciclo=ciclo.id_ciclo)
        db.add(viagem)

    km_ini = int(st.session_state.get("f_odometro_ini", 0))
    km_fin = int(st.session_state.get("f_odometro_fin", 0))
    km_real = max(0, km_fin - km_ini) if km_fin >= km_ini and km_ini > 0 else 0

    viagem.codigo_viagem = codigo_v
    viagem.id_ciclo = ciclo.id_ciclo
    viagem.id_motorista = id_motorista
    viagem.id_veiculo = id_veiculo
    viagem.id_frete_externo = str(st.session_state.get("f_id_frete", "")).strip()
    viagem.data_frete = st.session_state.get("f_data_frete")
    viagem.status_viagem = st.session_state.get("f_status_viagem", "Planejada")
    viagem.tipo_viagem = tipo_viagem
    viagem.tipo_frete = st.session_state.get("f_tipo_frete", "Dedicado")
    viagem.rota_origem = origem[:100]
    viagem.rota_destino = destino[:100]
    viagem.rota_resumo = rota_resumo[:210]
    viagem.km_rota_planejado = round(float(st.session_state.get("f_km_planejado", 0.0)), 2)

    viagem.id_local_coleta = id_coleta
    viagem.data_coleta = st.session_state.get("f_data_coleta")
    viagem.hora_planejada_coleta = st.session_state.get("f_hora_plan_coleta")
    viagem.hora_real_coleta = st.session_state.get("f_hora_real_coleta")
    viagem.obs_coleta = str(st.session_state.get("f_obs_coleta", ""))[:300]

    viagem.id_local_entrega = id_entrega
    viagem.data_entrega = st.session_state.get("f_data_entrega")
    viagem.hora_planejada_entrega = st.session_state.get("f_hora_plan_entrega")
    viagem.hora_real_entrega = st.session_state.get("f_hora_real_entrega")
    viagem.documento_entrega = str(st.session_state.get("f_documento_entrega", ""))[:100]
    viagem.obs_entrega = str(st.session_state.get("f_obs_entrega", ""))[:300]

    viagem.tipo_material = str(st.session_state.get("f_tipo_material", ""))[:150]
    viagem.qtde_volumes = int(st.session_state.get("f_qtde_volumes", 0))
    viagem.peso_bruto_kg = round(float(st.session_state.get("f_peso_kg", 0.0)), 2)
    viagem.volume_m3 = round(float(st.session_state.get("f_volume_m3", 0.0)), 2)
    viagem.nfe_carga = str(st.session_state.get("f_nfe", ""))[:100]
    viagem.cte_numero = str(st.session_state.get("f_cte", ""))[:50]
    viagem.mdfe_numero = str(st.session_state.get("f_mdfe", ""))[:50]
    viagem.ciot_numero = str(st.session_state.get("f_ciot", ""))[:50]

    viagem.odometro_inicial = km_ini
    viagem.odometro_final = km_fin
    viagem.km_real_rodado = km_real
    viagem.observacao_geral = str(st.session_state.get("f_obs_geral", ""))[:500]

    db.flush()

    # 3. Sincroniza Despesas da Viagem
    db.query(ViagemDespesa).filter(ViagemDespesa.id_viagem == viagem.id_viagem).delete()
    for item in st.session_state.get("despesas_rascunho", []):
        db.add(
            ViagemDespesa(
                id_viagem=viagem.id_viagem,
                id_fornecedor=item.get("id_fornecedor"),
                tipo_despesa=item["tipo_despesa"],
                descricao_detalhe=item.get("descricao_detalhe", "")[:150],
                quantidade=round(float(item.get("quantidade", 1.0)), 2),
                valor_unitario=round(float(item.get("valor_unitario", 0.0)), 2),
                valor_total=round(float(item.get("valor_total", 0.0)), 2),
                data_despesa=item.get("data_despesa") or date.today(),
            )
        )

    db.commit()
    st.session_state["viagem_editando_id"] = viagem.id_viagem
    return True, f"Viagem **{codigo_v}** salva com sucesso no banco de dados!"


# ==============================================================================
# 5. EXPORTAÇÃO EXCEL E PDF
# ==============================================================================


def gerar_excel_relatorio(df_export: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_export.to_excel(writer, index=False, sheet_name="Controle_Viagens_FAEG")
    return output.getvalue()


def gerar_pdf_relatorio(df_export: pd.DataFrame, kpis: dict) -> tuple[bytes, str, str]:
    try:
        from fpdf import FPDF

        pdf = FPDF(orientation="L", unit="mm", format="A4")
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "FAEG LOG - Relatorio Operacional e Financeiro de Viagens", ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(
            0,
            7,
            f"Receita Total: {fmt_brl(kpis['receita'])}   |   "
            f"Despesas Totais: {fmt_brl(kpis['despesa'])}   |   "
            f"Resultado Liquido: {fmt_brl(kpis['resultado'])}   |   "
            f"Margem: {kpis['margem']:.1f}%",
            ln=True,
        )
        pdf.ln(3)

        cols = [
            ("Codigo", 18),
            ("Data", 22),
            ("Cliente", 42),
            ("Motorista", 36),
            ("Placa", 22),
            ("Origem", 36),
            ("Destino", 36),
            ("Receita", 22),
            ("Despesas", 22),
            ("Resultado", 22),
        ]
        pdf.set_font("Helvetica", "B", 8)
        for titulo, largura in cols:
            pdf.cell(largura, 7, titulo, border=1)
        pdf.ln()

        pdf.set_font("Helvetica", "", 7)
        for _, r in df_export.iterrows():
            vals = [
                str(r.get("Código Viagem", ""))[:10],
                str(r.get("Data", ""))[:10],
                str(r.get("Cliente", ""))[:22],
                str(r.get("Motorista", ""))[:19],
                str(r.get("Placa", ""))[:10],
                str(r.get("Origem", ""))[:19],
                str(r.get("Destino", ""))[:19],
                fmt_brl(r.get("Receita Negociada (R$)", 0)),
                fmt_brl(r.get("Despesas (R$)", 0)),
                fmt_brl(r.get("Resultado Líquido (R$)", 0)),
            ]
            for (_, largura), txt in zip(cols, vals):
                txt_latin = txt.encode("latin-1", "replace").decode("latin-1")
                pdf.cell(largura, 6, txt_latin, border=1)
            pdf.ln()

        return bytes(pdf.output()), "relatorio_viagens_faeg.pdf", "application/pdf"
    except ImportError:
        html_tbl = df_export.to_html(index=False)
        html_doc = f"""
        <html><head><meta charset="utf-8"><title>Relatório FAEG LOG</title></head>
        <body style="font-family:Arial,sans-serif;">
        <h2>FAEG LOG - Relatório Operacional e Financeiro</h2>
        <p><strong>Receita:</strong> {fmt_brl(kpis['receita'])} |
           <strong>Despesas:</strong> {fmt_brl(kpis['despesa'])} |
           <strong>Resultado:</strong> {fmt_brl(kpis['resultado'])}</p>
        {html_tbl}
        </body></html>
        """.encode("utf-8")
        return html_doc, "relatorio_viagens_faeg.html", "text/html"


# ==============================================================================
# 6. INTERFACE PRINCIPAL (SIDEBAR + 11 TELAS)
# ==============================================================================


def main():
    db = SessionLocal()
    try:
        inicializar_estado_formulario(db)

        # ----- MENU LATERAL -----
        with st.sidebar:
            st.markdown('<p class="faeg-logo">🚚 FAEG LOG</p>', unsafe_allow_html=True)
            st.markdown('<p class="faeg-sub">Controle Operacional</p>', unsafe_allow_html=True)

            if st.button("➕ Nova Viagem (Próximo Código)", use_container_width=True):
                inicializar_estado_formulario(db, forcar_novo=True)
                st.rerun()

            viagens_lista = (
                db.query(Viagem)
                .order_by(Viagem.id_viagem.desc())
                .limit(100)
                .all()
            )
            if viagens_lista:
                opcoes_v = {
                    f"{v.codigo_viagem or f'V{v.id_viagem}'} | {v.rota_origem or '?'} -> {v.rota_destino or '?'}": v.id_viagem
                    for v in viagens_lista
                }
                sel_v_label = st.selectbox(
                    "Carregar Viagem para Edição",
                    options=["-- Selecione --"] + list(opcoes_v.keys()),
                    key="sidebar_select_viagem",
                )
                if sel_v_label != "-- Selecione --":
                    if st.button("📂 Abrir Viagem Selecionada", use_container_width=True):
                        carregar_viagem_no_formulario(db, opcoes_v[sel_v_label])
                        st.rerun()

            st.divider()

            menu = st.radio(
                "Etapas Operacionais",
                options=[
                    "1. Frota FAEG",
                    "2. Frete e Docs",
                    "3. Cliente",
                    "4. Negociação / Pgto",
                    "5. Coleta (Origem)",
                    "6. Entrega (Destino)",
                    "7. Despesas de Viagem",
                    "8. Fechamento Final",
                    "9. Relatórios / Exportar",
                    "10. Consultas Gerais",
                    "11. Cadastros Gerais",
                ],
                label_visibility="collapsed",
            )

            st.divider()
            cod_atual = st.session_state.get("f_codigo_viagem", "V1")
            modo_txt = (
                f"Editando **{cod_atual}**"
                if st.session_state.get("viagem_editando_id")
                else f"Nova Viagem **{cod_atual}**"
            )
            st.caption(f"Registro ativo: {modo_txt}")

            if st.button("💾 Salvar Viagem no Banco", type="primary", use_container_width=True):
                ok, msg = salvar_viagem_completa(db)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

        # ----- CARREGAMENTO DE DOMÍNIOS -----
        motoristas = db.query(Motorista).order_by(Motorista.nome_completo.asc()).all()
        veiculos = db.query(Veiculo).order_by(Veiculo.placa.asc()).all()
        clientes = db.query(Cliente).order_by(Cliente.razao_social.asc()).all()
        locais = db.query(Local).order_by(Local.nome_local.asc()).all()
        fornecedores = db.query(Fornecedor).order_by(Fornecedor.nome_fantasia.asc()).all()

        # ======================================================================
        # TELA 1: FROTA FAEG + UPLOAD DE PLANILHA ANTIGA
        # ======================================================================
        if menu == "1. Frota FAEG":
            st.subheader("🚚 1. Informações FAEG & Identificação da Viagem")

            c1, c2, c3, c4 = st.columns([1.1, 1.3, 1.3, 1.3])
            with c1:
                st.text_input(
                    "Código da Viagem (Único)",
                    key="f_codigo_viagem",
                    help="Gerado automaticamente em sequência (V1, V2, V3...), mas editável caso precise registrar uma viagem pulada da planilha.",
                )
            with c2:
                st.selectbox("Status da Viagem", OPCOES_STATUS_VIAGEM, key="f_status_viagem")
            with c3:
                st.selectbox("Tipo de Viagem", ["Individual", "Ciclo"], key="f_tipo_viagem")
            with c4:
                st.selectbox("Tipo de Frete", OPCOES_TIPO_FRETE, key="f_tipo_frete")

            # Controle de Ciclo Operacional quando Tipo de Viagem == "Ciclo"
            if st.session_state["f_tipo_viagem"] == "Ciclo":
                ciclos_disp = (
                    db.query(CicloOperacional)
                    .order_by(CicloOperacional.id_ciclo.desc())
                    .limit(50)
                    .all()
                )
                mapa_ciclos = {"➕ Criar Novo Ciclo Operacional": None}
                for c in ciclos_disp:
                    mapa_ciclos[f"Ciclo #{c.id_ciclo} - {c.nome_operacao or 'Sem nome'}"] = c.id_ciclo

                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    ciclo_escolhido = st.selectbox(
                        "Vincular a Ciclo Existente ou Novo",
                        options=list(mapa_ciclos.keys()),
                    )
                    st.session_state["f_id_ciclo_existente"] = mapa_ciclos[ciclo_escolhido]
                with col_c2:
                    st.text_input(
                        "Nome / Nº do Ciclo Operacional",
                        key="f_nome_operacao",
                        placeholder="Ex: C26-001 - Operação Sudeste",
                    )
            else:
                st.session_state["f_id_ciclo_existente"] = None

            st.markdown("---")
            col_m, col_v = st.columns(2)

            with col_m:
                st.markdown("**Condutor / Motorista**")
                if not motoristas:
                    st.warning("Nenhum motorista cadastrado. Cadastre na aba '11. Cadastros Gerais' ou importe uma planilha abaixo.")
                else:
                    mapa_mot = {f"{m.nome_completo} (CPF: {m.cpf})": m.id_motorista for m in motoristas}
                    labels_mot = list(mapa_mot.keys())
                    idx_mot = 0
                    if st.session_state["f_id_motorista"] in mapa_mot.values():
                        idx_mot = list(mapa_mot.values()).index(st.session_state["f_id_motorista"])
                    sel_mot = st.selectbox("Selecione o Motorista", labels_mot, index=idx_mot)
                    st.session_state["f_id_motorista"] = mapa_mot[sel_mot]

                    mot_obj = next(m for m in motoristas if m.id_motorista == st.session_state["f_id_motorista"])
                    mc1, mc2 = st.columns(2)
                    mc1.text_input("CNH", value=mot_obj.cnh_numero or "", disabled=True)
                    mc2.text_input("Categoria / Vínculo", value=f"{mot_obj.cnh_categoria or '-'} | {mot_obj.vinculo or '-'}", disabled=True)

            with col_v:
                st.markdown("**Veículo / Frota**")
                if not veiculos:
                    st.warning("Nenhum veículo cadastrado. Cadastre na aba '11. Cadastros Gerais' ou importe uma planilha abaixo.")
                else:
                    mapa_vei = {f"{v.placa} - {v.descricao_marca}": v.id_veiculo for v in veiculos}
                    labels_vei = list(mapa_vei.keys())
                    idx_vei = 0
                    if st.session_state["f_id_veiculo"] in mapa_vei.values():
                        idx_vei = list(mapa_vei.values()).index(st.session_state["f_id_veiculo"])
                    sel_vei = st.selectbox("Selecione o Veículo", labels_vei, index=idx_vei)
                    st.session_state["f_id_veiculo"] = mapa_vei[sel_vei]

                    vei_obj = next(v for v in veiculos if v.id_veiculo == st.session_state["f_id_veiculo"])
                    vc1, vc2 = st.columns(2)
                    vc1.text_input("Placa", value=vei_obj.placa or "", disabled=True)
                    vc2.text_input("Tipo / Capacidade", value=f"{vei_obj.tipo_veiculo or '-'} ({vei_obj.capacidade_carga_kg or 0} kg)", disabled=True)

            # ----- BLOCO DE IMPORTAÇÃO DA PLANILHA ANTIGA NA PRIMEIRA TELA -----
            st.markdown("---")
            with st.expander("📥 Importar Planilha de Controle de Fretes (Excel / CSV)", expanded=False):
                st.caption(
                    "Faça o upload da planilha utilizada anteriormente (ex: FAEG_Controle_Operacional_Viagens.xlsx). "
                    "O sistema importa todas as viagens, receitas e despesas mantendo os mesmos totais financeiros "
                    "e permite editar qualquer campo pendente depois."
                )

                arquivo_up = st.file_uploader(
                    "Selecione o arquivo (.xlsx, .xls ou .csv)",
                    type=["xlsx", "xls", "csv"],
                    key="uploader_planilha_faeg",
                )

                if arquivo_up is not None:
                    raw_bytes = arquivo_up.getvalue()
                    abas_disponiveis = listar_abas_planilha(BytesIO(raw_bytes), arquivo_up.name)
                    abas_padrao = [a for a in abas_disponiveis if "PARÂMETRO" not in a.upper() and "PARAMETRO" not in a.upper()]
                    if not abas_padrao:
                        abas_padrao = abas_disponiveis

                    abas_sel = st.multiselect(
                        "Abas da planilha para importar",
                        options=abas_disponiveis,
                        default=abas_padrao,
                    )
                    ignorar_dup = st.checkbox(
                        "Ignorar viagens já importadas anteriormente (evitar duplicidade por ID Frete / Data+Placa)",
                        value=True,
                    )

                    if abas_sel:
                        registros_preview = extrair_registros_planilha(
                            BytesIO(raw_bytes), arquivo_up.name, abas_sel
                        )
                        st.info(f"Foram identificados **{len(registros_preview)}** registros válidos nas abas selecionadas.")

                        if registros_preview:
                            df_prev = pd.DataFrame(
                                [
                                    {
                                        "Aba": r["aba_origem"],
                                        "ID Planilha": r["id_planilha"],
                                        "ID Frete": r["id_frete"],
                                        "Data": r["data_frete"],
                                        "Placa": r["placa"],
                                        "Motorista": r["motorista"],
                                        "Cliente": r["cliente_empresa"],
                                        "Origem": r["origem"],
                                        "Destino": r["destino"],
                                        "Valor Negociado": r["valor_negociado"],
                                        "Total Despesas": r["total_despesas_planilha"],
                                        "Resultado": r["resultado_planilha"],
                                    }
                                    for r in registros_preview
                                ]
                            )
                            st.dataframe(df_prev, use_container_width=True, hide_index=True)

                            if st.button("🚀 Confirmar Importação e Salvar no Banco", type="primary"):
                                resumo_imp = importar_registros_para_banco(
                                    db, registros_preview, ignorar_duplicados=ignorar_dup
                                )
                                st.success(
                                    f"Importação concluída! **{resumo_imp['importados']}** viagens salvas "
                                    f"({', '.join(resumo_imp['codigos_gerados'])}) | "
                                    f"**{resumo_imp['ignorados']}** duplicadas ignoradas."
                                )

                                # Tabela de Conciliação Financeira (Planilha vs. Sistema)
                                st.markdown("**Conferência de Valores (Planilha vs. Sistema)**")
                                df_conc = pd.DataFrame(
                                    [
                                        {
                                            "Indicador": "Receita Negociada Total",
                                            "Planilha": fmt_brl(resumo_imp["receita_planilha"]),
                                            "Sistema": fmt_brl(resumo_imp["receita_sistema"]),
                                            "Diferença": fmt_brl(resumo_imp["receita_sistema"] - resumo_imp["receita_planilha"]),
                                        },
                                        {
                                            "Indicador": "Despesas Totais",
                                            "Planilha": fmt_brl(resumo_imp["despesa_planilha"]),
                                            "Sistema": fmt_brl(resumo_imp["despesa_sistema"]),
                                            "Diferença": fmt_brl(resumo_imp["despesa_sistema"] - resumo_imp["despesa_planilha"]),
                                        },
                                        {
                                            "Indicador": "Resultado Líquido",
                                            "Planilha": fmt_brl(resumo_imp["resultado_planilha"]),
                                            "Sistema": fmt_brl(resumo_imp["resultado_sistema"]),
                                            "Diferença": fmt_brl(resumo_imp["resultado_sistema"] - resumo_imp["resultado_planilha"]),
                                        },
                                    ]
                                )
                                st.dataframe(df_conc, use_container_width=True, hide_index=True)

                                if resumo_imp["pendencias"]:
                                    with st.expander("⚠️ Itens com dados provisórios/faltantes para editar depois", expanded=True):
                                        for p in resumo_imp["pendencias"]:
                                            st.write(f"- {p}")

                                # Atualiza próximo código sequencial no formulário ativo
                                if not st.session_state.get("viagem_editando_id"):
                                    st.session_state["f_codigo_viagem"] = gerar_proximo_codigo_viagem(db)

        # ======================================================================
        # TELA 2: FRETE, ROTA (ORIGEM / DESTINO) E DOCUMENTOS FISCAIS
        # ======================================================================
        elif menu == "2. Frete e Docs":
            st.subheader("📦 2. Frete, Rota (Origem e Destino) e Documentos Fiscais")

            r1c1, r1c2, r1c3 = st.columns(3)
            with r1c1:
                st.text_input("ID Frete (Embarcador / Plataforma)", key="f_id_frete", placeholder="Ex: F26-000001")
            with r1c2:
                st.date_input("Data do Frete", key="f_data_frete")
            with r1c3:
                st.number_input("KM Planejado da Rota", min_value=0.0, step=1.0, key="f_km_planejado")

            # Campos separados de Origem e Destino
            ro1, ro2 = st.columns(2)
            with ro1:
                st.text_input(
                    "Origem (Cidade/UF ou Ponto de Partida)",
                    key="f_rota_origem",
                    placeholder="Ex: Curitiba/PR",
                )
            with ro2:
                st.text_input(
                    "Destino (Cidade/UF ou Ponto Final)",
                    key="f_rota_destino",
                    placeholder="Ex: Guarulhos/SP",
                )

            st.markdown("**Detalhes da Carga**")
            cg1, cg2, cg3, cg4 = st.columns([2, 1, 1, 1])
            with cg1:
                st.text_input("Tipo de Material", key="f_tipo_material", placeholder="Ex: 36 Pneus e uma caixa")
            with cg2:
                st.number_input("Qtde. Volumes", min_value=0, step=1, key="f_qtde_volumes")
            with cg3:
                st.number_input("Volume (m³)", min_value=0.0, step=0.1, key="f_volume_m3")
            with cg4:
                st.number_input("Peso Bruto (KG)", min_value=0.0, step=10.0, key="f_peso_kg")

            st.markdown("**Documentos Fiscais**")
            dc1, dc2, dc3, dc4 = st.columns(4)
            with dc1:
                st.text_input("NF-e / Carga", key="f_nfe")
            with dc2:
                st.text_input("CT-e", key="f_cte")
            with dc3:
                st.text_input("MDF-e", key="f_mdfe")
            with dc4:
                st.text_input("CIOT", key="f_ciot")

        # ======================================================================
        # TELA 3: CLIENTE
        # ======================================================================
        elif menu == "3. Cliente":
            st.subheader("🤝 3. Cliente Contratante")
            if not clientes:
                st.warning("Nenhum cliente cadastrado. Cadastre na aba '11. Cadastros Gerais' ou importe uma planilha na aba 1.")
            else:
                mapa_cli = {
                    f"{c.nome_fantasia or c.razao_social} ({c.cnpj_cpf})": c.id_cliente
                    for c in clientes
                }
                labels_cli = list(mapa_cli.keys())
                idx_cli = 0
                if st.session_state["f_id_cliente"] in mapa_cli.values():
                    idx_cli = list(mapa_cli.values()).index(st.session_state["f_id_cliente"])
                sel_cli = st.selectbox("Selecione o Cliente", labels_cli, index=idx_cli)
                st.session_state["f_id_cliente"] = mapa_cli[sel_cli]

                cli_obj = next(c for c in clientes if c.id_cliente == st.session_state["f_id_cliente"])
                cc1, cc2, cc3 = st.columns(3)
                cc1.text_input("Razão Social", value=cli_obj.razao_social or "", disabled=True)
                cc2.text_input("Responsável Comercial", value=cli_obj.responsavel_comercial or "", disabled=True)
                cc3.text_input("Telefone / Contato", value=cli_obj.telefone_comercial or "", disabled=True)

        # ======================================================================
        # TELA 4: NEGOCIAÇÃO E RECEBIMENTOS (CÁLCULOS AUTOMÁTICOS)
        # ======================================================================
        elif menu == "4. Negociação / Pgto":
            st.subheader("💰 4. Negociação e Recebimentos")

            ng1, ng2, ng3 = st.columns(3)
            with ng1:
                st.selectbox(
                    "Forma de Contratação",
                    ["Viagem Fechada", "Por Tonelada", "Por KM", "Diária", "Complemento"],
                    key="f_forma_contratacao",
                )
            with ng2:
                st.number_input("Valor Divulgado (R$)", min_value=0.0, step=50.0, key="f_valor_divulgado")
            with ng3:
                st.number_input(
                    "Valor Negociado Total (R$)",
                    min_value=0.0,
                    step=50.0,
                    key="f_valor_negociado",
                    on_change=recalcular_por_percentual,
                )

            st.markdown("**Adiantamento e Saldo (Preenchimento Automático)**")
            pg1, pg2, pg3 = st.columns(3)
            with pg1:
                st.number_input(
                    "Adiantamento (%)",
                    min_value=0.0,
                    max_value=100.0,
                    step=5.0,
                    key="f_perc_adiantamento",
                    on_change=recalcular_por_percentual,
                )
            with pg2:
                st.number_input(
                    "Valor Adiantamento (R$)",
                    min_value=0.0,
                    step=50.0,
                    key="f_valor_adiantamento",
                    on_change=recalcular_por_valor_adiantamento,
                )
            with pg3:
                st.date_input("Data Adiantamento", key="f_data_adiantamento")

            sl1, sl2, sl3 = st.columns(3)
            with sl1:
                st.number_input("Saldo (%)", min_value=0.0, max_value=100.0, key="f_perc_saldo", disabled=True)
            with sl2:
                st.number_input("Valor Saldo (R$)", min_value=0.0, key="f_valor_saldo", disabled=True)
            with sl3:
                st.date_input("Data Saldo a Receber", key="f_data_saldo")

            tot_recebido = float(st.session_state.get("f_valor_adiantamento", 0.0)) + float(
                st.session_state.get("f_valor_saldo", 0.0)
            )
            st.success(f"**Valor Total Recebido / Previsto (Adiantamento + Saldo): {fmt_brl(tot_recebido)}**")

            fp1, fp2, fp3 = st.columns(3)
            with fp1:
                st.text_input("Forma de Pagamento", key="f_forma_pagamento", placeholder="Ex: Pix, Fretebras, TED")
            with fp2:
                st.text_input("Banco / Conta", key="f_banco_conta")
            with fp3:
                st.text_input("Observação referente ao Saldo", key="f_obs_saldo")

        # ======================================================================
        # TELA 5: COLETA (ORIGEM DETALHADA)
        # ======================================================================
        elif menu == "5. Coleta (Origem)":
            st.subheader("📍 5. Coleta (Ponto de Origem)")
            if not locais:
                st.warning("Nenhum local cadastrado. Cadastre na aba '11. Cadastros Gerais' ou importe uma planilha.")
            else:
                mapa_loc = {
                    f"{l.nome_local} ({l.cidade or '-'}/{l.uf or '-'})": l.id_local
                    for l in locais
                }
                labels_loc = list(mapa_loc.keys())
                idx_col = 0
                if st.session_state["f_id_local_coleta"] in mapa_loc.values():
                    idx_col = list(mapa_loc.values()).index(st.session_state["f_id_local_coleta"])
                sel_col = st.selectbox("Local / Empresa de Coleta", labels_loc, index=idx_col)
                st.session_state["f_id_local_coleta"] = mapa_loc[sel_col]

                loc_c = next(l for l in locais if l.id_local == st.session_state["f_id_local_coleta"])
                lc1, lc2, lc3 = st.columns([2, 1, 1])
                lc1.text_input("Endereço Coleta", value=loc_c.endereco_completo or "", disabled=True)
                lc2.text_input("Cidade / UF", value=f"{loc_c.cidade or ''}/{loc_c.uf or ''}", disabled=True)
                lc3.text_input("CEP", value=loc_c.cep or "", disabled=True)

            hc1, hc2, hc3 = st.columns(3)
            with hc1:
                st.date_input("Data da Coleta", key="f_data_coleta")
            with hc2:
                st.time_input("Horário Planejado Coleta", key="f_hora_plan_coleta")
            with hc3:
                st.time_input("Horário Real Coletado", key="f_hora_real_coleta")
            st.text_area("Observação referente à Coleta", key="f_obs_coleta", height=80)

        # ======================================================================
        # TELA 6: ENTREGA (DESTINO DETALHADO)
        # ======================================================================
        elif menu == "6. Entrega (Destino)":
            st.subheader("🏁 6. Entrega (Ponto de Destino)")
            if not locais:
                st.warning("Nenhum local cadastrado. Cadastre na aba '11. Cadastros Gerais' ou importe uma planilha.")
            else:
                mapa_loc = {
                    f"{l.nome_local} ({l.cidade or '-'}/{l.uf or '-'})": l.id_local
                    for l in locais
                }
                labels_loc = list(mapa_loc.keys())
                idx_ent = 0
                if st.session_state["f_id_local_entrega"] in mapa_loc.values():
                    idx_ent = list(mapa_loc.values()).index(st.session_state["f_id_local_entrega"])
                sel_ent = st.selectbox("Local / Empresa de Entrega", labels_loc, index=idx_ent)
                st.session_state["f_id_local_entrega"] = mapa_loc[sel_ent]

                loc_e = next(l for l in locais if l.id_local == st.session_state["f_id_local_entrega"])
                le1, le2, le3 = st.columns([2, 1, 1])
                le1.text_input("Endereço Entrega", value=loc_e.endereco_completo or "", disabled=True)
                le2.text_input("Cidade / UF", value=f"{loc_e.cidade or ''}/{loc_e.uf or ''}", disabled=True)
                le3.text_input("CEP", value=loc_e.cep or "", disabled=True)

            he1, he2, he3, he4 = st.columns(4)
            with he1:
                st.date_input("Data da Entrega", key="f_data_entrega")
            with he2:
                st.time_input("Horário Planejado Entrega", key="f_hora_plan_entrega")
            with he3:
                st.time_input("Horário Real Entrega", key="f_hora_real_entrega")
            with he4:
                st.text_input("Documento Comprovante", key="f_documento_entrega")
            st.text_area("Observação referente à Entrega", key="f_obs_entrega", height=80)

        # ======================================================================
        # TELA 7: DESPESAS DE VIAGEM (UNIFICADAS)
        # ======================================================================
        elif menu == "7. Despesas de Viagem":
            st.subheader("🧾 7. Despesas de Viagem (Abastecimentos, Pedágios e Custos)")

            edit_idx = st.session_state.get("despesa_edit_idx")
            lista_desp = st.session_state["despesas_rascunho"]
            item_atual = lista_desp[edit_idx] if edit_idx is not None and edit_idx < len(lista_desp) else None

            mapa_forn = {"Avulso / Não informado": None}
            for f in fornecedores:
                mapa_forn[f"{f.nome_fantasia} ({f.categoria_servico or 'Geral'})"] = f.id_fornecedor

            d1, d2, d3 = st.columns([1.2, 1.3, 1.5])
            with d1:
                idx_cat = (
                    CATEGORIAS_UNIFICADAS.index(item_atual["tipo_despesa"])
                    if item_atual and item_atual["tipo_despesa"] in CATEGORIAS_UNIFICADAS
                    else 0
                )
                tipo_d = st.selectbox("Tipo de Despesa (Categoria)", CATEGORIAS_UNIFICADAS, index=idx_cat)
            with d2:
                forn_keys = list(mapa_forn.keys())
                idx_f = 0
                if item_atual and item_atual.get("id_fornecedor") in mapa_forn.values():
                    idx_f = list(mapa_forn.values()).index(item_atual["id_fornecedor"])
                sel_forn = st.selectbox("Fornecedor / Posto", forn_keys, index=idx_f)
            with d3:
                desc_d = st.text_input(
                    "Descrição / Detalhe",
                    value=item_atual["descricao_detalhe"] if item_atual else "",
                    placeholder="Ex: Diesel S10 Posto Graal / Pedágio",
                )

            q1, q2, q3, q4 = st.columns([1, 1, 1, 1])
            with q1:
                qtd_d = st.number_input(
                    "Quantidade (Litros / Unid.)",
                    min_value=0.01,
                    step=1.0,
                    value=float(item_atual["quantidade"]) if item_atual else 1.0,
                )
            with q2:
                unit_d = st.number_input(
                    "Valor Unitário (R$)",
                    min_value=0.0,
                    step=1.0,
                    value=float(item_atual["valor_unitario"]) if item_atual else 0.0,
                )
            with q3:
                total_d = round(qtd_d * unit_d, 2)
                st.text_input("Total do Item (Automático)", value=fmt_brl(total_d), disabled=True)
            with q4:
                data_d = st.date_input(
                    "Data da Despesa",
                    value=item_atual["data_despesa"] if item_atual else date.today(),
                )

            btn_label = "✅ Atualizar Despesa" if item_atual else "➕ Adicionar Despesa à Viagem"
            if st.button(btn_label):
                novo_item = {
                    "id_fornecedor": mapa_forn[sel_forn],
                    "tipo_despesa": tipo_d,
                    "descricao_detalhe": desc_d,
                    "quantidade": round(qtd_d, 2),
                    "valor_unitario": round(unit_d, 2),
                    "valor_total": total_d,
                    "data_despesa": data_d,
                }
                if item_atual is not None:
                    lista_desp[edit_idx] = novo_item
                    st.session_state["despesa_edit_idx"] = None
                else:
                    lista_desp.append(novo_item)
                st.rerun()

            st.markdown("---")
            if lista_desp:
                df_d = pd.DataFrame(
                    [
                        {
                            "#": i + 1,
                            "Categoria": x["tipo_despesa"],
                            "Descrição": x["descricao_detalhe"],
                            "Qtd": x["quantidade"],
                            "Unitário": fmt_brl(x["valor_unitario"]),
                            "Total": fmt_brl(x["valor_total"]),
                            "Data": x["data_despesa"],
                        }
                        for i, x in enumerate(lista_desp)
                    ]
                )
                st.dataframe(df_d, use_container_width=True, hide_index=True)

                ac1, ac2, ac3 = st.columns([1.2, 1, 1])
                with ac1:
                    idx_acao = st.selectbox(
                        "Selecionar item para editar/excluir",
                        options=list(range(len(lista_desp))),
                        format_func=lambda i: f"#{i + 1} - {lista_desp[i]['tipo_despesa']} ({fmt_brl(lista_desp[i]['valor_total'])})",
                    )
                with ac2:
                    if st.button("✏️ Editar Item", use_container_width=True):
                        st.session_state["despesa_edit_idx"] = idx_acao
                        st.rerun()
                with ac3:
                    if st.button("🗑️ Excluir Item", use_container_width=True):
                        lista_desp.pop(idx_acao)
                        st.session_state["despesa_edit_idx"] = None
                        st.rerun()

            total_geral_desp = sum(float(x["valor_total"]) for x in lista_desp)
            st.error(f"**Total de Despesas da Viagem: {fmt_brl(total_geral_desp)}**")

        # ======================================================================
        # TELA 8: FECHAMENTO FINAL & DRE
        # ======================================================================
        elif menu == "8. Fechamento Final":
            st.subheader("🏁 8. Fechamento da Viagem & DRE")

            od1, od2, od3 = st.columns(3)
            with od1:
                st.number_input("Odômetro Inicial (KM)", min_value=0, step=10, key="f_odometro_ini")
            with od2:
                st.number_input("Odômetro Final (KM)", min_value=0, step=10, key="f_odometro_fin")
            with od3:
                km_ini = int(st.session_state.get("f_odometro_ini", 0))
                km_fin = int(st.session_state.get("f_odometro_fin", 0))
                km_rodado = max(0, km_fin - km_ini) if km_fin >= km_ini and km_ini > 0 else 0
                st.text_input("KM Real Rodado (Automático)", value=f"{km_rodado} km", disabled=True)

            st.text_area("Observação Geral da Viagem", key="f_obs_geral", height=90)

            receita_dre = float(st.session_state.get("f_valor_negociado", 0.0))
            despesa_dre = sum(float(x["valor_total"]) for x in st.session_state.get("despesas_rascunho", []))
            resultado_dre = receita_dre - despesa_dre
            margem_dre = (resultado_dre / receita_dre * 100.0) if receita_dre > 0 else 0.0
            custo_km = (despesa_dre / km_rodado) if km_rodado > 0 else 0.0
            cor_res = "#34d399" if resultado_dre >= 0 else "#f87171"

            st.markdown(
                f"""
                <div class="dre-card">
                    <div style="font-size:0.85rem;text-transform:uppercase;color:#94a3b8;font-weight:700;margin-bottom:0.8rem;">
                        DRE Consolidado — Viagem {st.session_state.get('f_codigo_viagem', 'V1')}
                        ({st.session_state.get('f_rota_origem', '')} → {st.session_state.get('f_rota_destino', '')})
                    </div>
                    <div style="display:flex;justify-content:space-between;margin-bottom:0.5rem;">
                        <span>Receita Negociada (Frete):</span>
                        <span style="color:#34d399;font-weight:700;font-size:1.15rem;">{fmt_brl(receita_dre)}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;margin-bottom:0.8rem;">
                        <span>Custos Totais (Despesas):</span>
                        <span style="color:#f87171;font-weight:700;font-size:1.15rem;">- {fmt_brl(despesa_dre)}</span>
                    </div>
                    <hr style="border-color:#334155;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-top:0.8rem;">
                        <span style="font-size:1.1rem;font-weight:800;">RESULTADO LÍQUIDO:</span>
                        <span style="color:{cor_res};font-size:1.8rem;font-weight:900;">{fmt_brl(resultado_dre)}</span>
                    </div>
                    <div style="margin-top:0.6rem;font-size:0.85rem;color:#cbd5e1;">
                        Margem Líquida: <strong>{margem_dre:.1f}%</strong> &nbsp;|&nbsp;
                        Custo por KM Rodado: <strong>{fmt_brl(custo_km)}/km</strong>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # ======================================================================
        # TELA 9: RELATÓRIOS E EXPORTAÇÃO (EXCEL E PDF)
        # ======================================================================
        elif menu == "9. Relatórios / Exportar":
            st.subheader("📊 9. Relatórios Gerenciais & Exportação")

            todas_viagens = (
                db.query(Viagem)
                .options(
                    joinedload(Viagem.ciclo).joinedload(CicloOperacional.cliente),
                    joinedload(Viagem.ciclo).joinedload(CicloOperacional.financeiro),
                    joinedload(Viagem.motorista),
                    joinedload(Viagem.veiculo),
                    joinedload(Viagem.despesas),
                )
                .order_by(Viagem.id_viagem.asc())
                .all()
            )

            if not todas_viagens:
                st.info("Nenhuma viagem registrada no banco de dados ainda.")
            else:
                linhas = []
                desp_por_cat = {}
                for v in todas_viagens:
                    fin = v.ciclo.financeiro if v.ciclo else None
                    rec = float(fin.valor_negociado_total or 0.0) if fin else 0.0
                    desp = sum(float(d.valor_total or 0.0) for d in v.despesas)
                    for d in v.despesas:
                        desp_por_cat[d.tipo_despesa] = desp_por_cat.get(d.tipo_despesa, 0.0) + float(d.valor_total or 0.0)

                    orig = v.rota_origem or separar_rota(v.rota_resumo or "")[0]
                    dest = v.rota_destino or separar_rota(v.rota_resumo or "")[1]
                    linhas.append(
                        {
                            "Código Viagem": v.codigo_viagem or f"V{v.id_viagem}",
                            "ID Frete": v.id_frete_externo or "",
                            "Data": str(v.data_frete or ""),
                            "Tipo Viagem": v.tipo_viagem or "Individual",
                            "Tipo Frete": v.tipo_frete or "",
                            "Cliente": (v.ciclo.cliente.nome_fantasia or v.ciclo.cliente.razao_social) if v.ciclo and v.ciclo.cliente else "",
                            "Motorista": v.motorista.nome_completo if v.motorista else "",
                            "Placa": v.veiculo.placa if v.veiculo else "",
                            "Origem": orig,
                            "Destino": dest,
                            "KM Real": int(v.km_real_rodado or 0),
                            "Status": v.status_viagem or "",
                            "Receita Negociada (R$)": round(rec, 2),
                            "Despesas (R$)": round(desp, 2),
                            "Resultado Líquido (R$)": round(rec - desp, 2),
                        }
                    )

                df_rel = pd.DataFrame(linhas)

                rec_tot = df_rel["Receita Negociada (R$)"].sum()
                desp_tot = df_rel["Despesas (R$)"].sum()
                res_tot = df_rel["Resultado Líquido (R$)"].sum()
                margem_tot = (res_tot / rec_tot * 100.0) if rec_tot > 0 else 0.0

                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Receita Total", fmt_brl(rec_tot))
                k2.metric("Despesas Totais", fmt_brl(desp_tot))
                k3.metric("Resultado Líquido", fmt_brl(res_tot))
                k4.metric("Margem Média", f"{margem_tot:.1f}%")

                g1, g2 = st.columns(2)
                with g1:
                    st.markdown("**Despesas por Categoria**")
                    if desp_por_cat:
                        df_cat = pd.DataFrame(
                            {"Categoria": list(desp_por_cat.keys()), "Valor": list(desp_por_cat.values())}
                        ).set_index("Categoria")
                        st.bar_chart(df_cat)
                with g2:
                    st.markdown("**Receita vs. Despesas por Viagem**")
                    df_vchart = df_rel.set_index("Código Viagem")[["Receita Negociada (R$)", "Despesas (R$)"]]
                    st.bar_chart(df_vchart)

                st.dataframe(df_rel, use_container_width=True, hide_index=True)

                ex1, ex2 = st.columns(2)
                with ex1:
                    st.download_button(
                        "📥 Exportar Excel (.xlsx)",
                        data=gerar_excel_relatorio(df_rel),
                        file_name="relatorio_faeg_log.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
                with ex2:
                    pdf_bytes, pdf_nome, pdf_mime = gerar_pdf_relatorio(
                        df_rel,
                        {
                            "receita": rec_tot,
                            "despesa": desp_tot,
                            "resultado": res_tot,
                            "margem": margem_tot,
                        },
                    )
                    st.download_button(
                        "📄 Exportar Relatório (PDF / Impressão)",
                        data=pdf_bytes,
                        file_name=pdf_nome,
                        mime=pdf_mime,
                        use_container_width=True,
                    )

        # ======================================================================
        # TELA 10: CONSULTAS GERAIS (PESQUISA E EDIÇÃO COMPLETA)
        # ======================================================================
        elif menu == "10. Consultas Gerais":
            st.subheader("🔎 10. Consultas Gerais & Edição de Registros")

            f1, f2, f3 = st.columns([2, 1, 1])
            with f1:
                termo = st.text_input(
                    "Buscar por Código (V1), ID Frete, Cliente, Motorista, Placa, Origem ou Destino",
                    placeholder="Ex: V1, Curitiba, Guarulhos, SEZ3F87...",
                ).strip().lower()
            with f2:
                filtro_status = st.selectbox("Filtrar Status", ["Todos"] + OPCOES_STATUS_VIAGEM)
            with f3:
                filtro_frete = st.selectbox("Filtrar Tipo de Frete", ["Todos"] + OPCOES_TIPO_FRETE)

            viagens_q = (
                db.query(Viagem)
                .options(
                    joinedload(Viagem.ciclo).joinedload(CicloOperacional.cliente),
                    joinedload(Viagem.ciclo).joinedload(CicloOperacional.financeiro),
                    joinedload(Viagem.motorista),
                    joinedload(Viagem.veiculo),
                    joinedload(Viagem.despesas),
                )
                .order_by(Viagem.id_viagem.asc())
                .all()
            )

            filtradas = []
            for v in viagens_q:
                cod = v.codigo_viagem or f"V{v.id_viagem}"
                cli_nome = (
                    (v.ciclo.cliente.nome_fantasia or v.ciclo.cliente.razao_social)
                    if v.ciclo and v.ciclo.cliente
                    else ""
                )
                mot_nome = v.motorista.nome_completo if v.motorista else ""
                placa = v.veiculo.placa if v.veiculo else ""
                orig = v.rota_origem or separar_rota(v.rota_resumo or "")[0]
                dest = v.rota_destino or separar_rota(v.rota_resumo or "")[1]
                id_fr = v.id_frete_externo or ""

                if filtro_status != "Todos" and v.status_viagem != filtro_status:
                    continue
                if filtro_frete != "Todos" and v.tipo_frete != filtro_frete:
                    continue
                if termo:
                    blob = f"{cod} {id_fr} {cli_nome} {mot_nome} {placa} {orig} {dest}".lower()
                    if termo not in blob:
                        continue

                fin = v.ciclo.financeiro if v.ciclo else None
                rec = float(fin.valor_negociado_total or 0.0) if fin else 0.0
                desp = sum(float(d.valor_total or 0.0) for d in v.despesas)

                filtradas.append(
                    {
                        "id_viagem": v.id_viagem,
                        "Código": cod,
                        "ID Frete": id_fr,
                        "Data": str(v.data_frete or ""),
                        "Cliente": cli_nome,
                        "Motorista": mot_nome,
                        "Placa": placa,
                        "Origem": orig,
                        "Destino": dest,
                        "Tipo Frete": v.tipo_frete or "",
                        "Status": v.status_viagem or "",
                        "Receita": round(rec, 2),
                        "Despesas": round(desp, 2),
                        "Resultado": round(rec - desp, 2),
                    }
                )

            if not filtradas:
                st.info("Nenhum registro encontrado com os filtros informados.")
            else:
                df_q = pd.DataFrame(filtradas)
                st.dataframe(
                    df_q.drop(columns=["id_viagem"]),
                    use_container_width=True,
                    hide_index=True,
                )

                sel_c1, sel_c2 = st.columns([2, 1])
                with sel_c1:
                    opcoes_edicao = {
                        f"{r['Código']} | {r['Origem']} -> {r['Destino']} | {r['Cliente']} ({fmt_brl(r['Receita'])})": r["id_viagem"]
                        for r in filtradas
                    }
                    escolha_edit = st.selectbox("Selecione uma viagem para editar", list(opcoes_edicao.keys()))
                with sel_c2:
                    st.write("")
                    st.write("")
                    if st.button("✏️ Abrir / Editar Viagem Selecionada", type="primary", use_container_width=True):
                        carregar_viagem_no_formulario(db, opcoes_edicao[escolha_edit])
                        st.success("Viagem carregada! Navegue pelas abas 1 a 8 para editar e clique em 'Salvar Viagem no Banco'.")

        # ======================================================================
        # TELA 11: CADASTROS GERAIS (MASTER DATA + EDIÇÃO DE PENDÊNCIAS)
        # ======================================================================
        elif menu == "11. Cadastros Gerais":
            st.subheader("🗂️ 11. Cadastros Gerais (Motoristas, Veículos, Clientes, Locais e Fornecedores)")

            tab_m, tab_v, tab_c, tab_l, tab_f = st.tabs(
                ["Motoristas", "Veículos", "Clientes", "Locais", "Fornecedores / Postos"]
            )

            # --- MOTORISTAS ---
            with tab_m:
                modo_m = st.radio("Ação Motorista", ["Novo Cadastro", "Editar Existente"], horizontal=True)
                mot_edit = None
                if modo_m == "Editar Existente" and motoristas:
                    mapa_me = {f"{m.nome_completo} ({m.cpf})": m for m in motoristas}
                    mot_edit = mapa_me[st.selectbox("Motorista para Editar", list(mapa_me.keys()))]

                with st.form("form_motorista"):
                    mc1, mc2, mc3 = st.columns(3)
                    m_nome = mc1.text_input("Nome Completo*", value=mot_edit.nome_completo if mot_edit else "")
                    m_cpf = mc2.text_input("CPF*", value=mot_edit.cpf if mot_edit else "")
                    m_tel = mc3.text_input("Telefone", value=mot_edit.telefone_contato or "" if mot_edit else "")

                    mc4, mc5, mc6 = st.columns(3)
                    m_cnh = mc4.text_input("Número CNH*", value=mot_edit.cnh_numero if mot_edit else "")
                    m_cat = mc5.text_input("Categoria CNH", value=mot_edit.cnh_categoria or "E" if mot_edit else "E")
                    m_vinc = mc6.selectbox("Vínculo", ["CLT / Próprio", "Agregado", "Autônomo / Terceiro"])

                    if st.form_submit_button("💾 Salvar Motorista"):
                        if not m_nome or not m_cpf or not m_cnh:
                            st.error("Preencha Nome, CPF e CNH.")
                        else:
                            obj = mot_edit or Motorista()
                            obj.nome_completo = m_nome.strip()
                            obj.cpf = m_cpf.strip()
                            obj.telefone_contato = m_tel.strip()
                            obj.cnh_numero = m_cnh.strip()
                            obj.cnh_categoria = m_cat.strip().upper()
                            obj.vinculo = m_vinc
                            if not mot_edit:
                                db.add(obj)
                            db.commit()
                            st.success("Motorista salvo com sucesso!")
                            st.rerun()

                if motoristas:
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "Nome": m.nome_completo,
                                    "CPF": m.cpf,
                                    "CNH": m.cnh_numero,
                                    "Cat.": m.cnh_categoria,
                                    "Vínculo": m.vinculo,
                                }
                                for m in motoristas
                            ]
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

            # --- VEÍCULOS ---
            with tab_v:
                modo_v = st.radio("Ação Veículo", ["Novo Cadastro", "Editar Existente"], horizontal=True)
                vei_edit = None
                if modo_v == "Editar Existente" and veiculos:
                    mapa_ve = {f"{v.placa} - {v.descricao_marca}": v for v in veiculos}
                    vei_edit = mapa_ve[st.selectbox("Veículo para Editar", list(mapa_ve.keys()))]

                with st.form("form_veiculo"):
                    vc1, vc2, vc3 = st.columns(3)
                    v_desc = vc1.text_input("Descrição / Modelo*", value=vei_edit.descricao_marca if vei_edit else "")
                    v_placa = vc2.text_input("Placa*", value=vei_edit.placa if vei_edit else "")
                    v_tipo = vc3.text_input("Tipo Veículo", value=vei_edit.tipo_veiculo or "Utilitário / Caminhão" if vei_edit else "Utilitário / Caminhão")

                    vc4, vc5, vc6 = st.columns(3)
                    v_ren = vc4.text_input("RENAVAM", value=vei_edit.renavam or "" if vei_edit else "")
                    v_kg = vc5.number_input("Capacidade (KG)", min_value=0.0, value=float(vei_edit.capacidade_carga_kg or 0.0) if vei_edit else 0.0)
                    v_m3 = vc6.number_input("Capacidade (m³)", min_value=0.0, value=float(vei_edit.capacidade_volume_m3 or 0.0) if vei_edit else 0.0)

                    if st.form_submit_button("💾 Salvar Veículo"):
                        if not v_desc or not v_placa:
                            st.error("Preencha Descrição e Placa.")
                        else:
                            obj = vei_edit or Veiculo()
                            obj.descricao_marca = v_desc.strip()
                            obj.placa = re.sub(r"[^A-Z0-9]", "", v_placa.upper())
                            obj.tipo_veiculo = v_tipo.strip()
                            obj.renavam = v_ren.strip() or None
                            obj.capacidade_carga_kg = v_kg
                            obj.capacidade_volume_m3 = v_m3
                            if not vei_edit:
                                db.add(obj)
                            db.commit()
                            st.success("Veículo salvo com sucesso!")
                            st.rerun()

                if veiculos:
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "Placa": v.placa,
                                    "Descrição": v.descricao_marca,
                                    "Tipo": v.tipo_veiculo,
                                    "Cap. KG": float(v.capacidade_carga_kg or 0),
                                    "Cap. m³": float(v.capacidade_volume_m3 or 0),
                                }
                                for v in veiculos
                            ]
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

            # --- CLIENTES ---
            with tab_c:
                modo_c = st.radio("Ação Cliente", ["Novo Cadastro", "Editar Existente"], horizontal=True)
                cli_edit = None
                if modo_c == "Editar Existente" and clientes:
                    mapa_ce = {f"{c.nome_fantasia or c.razao_social} ({c.cnpj_cpf})": c for c in clientes}
                    cli_edit = mapa_ce[st.selectbox("Cliente para Editar", list(mapa_ce.keys()))]

                with st.form("form_cliente"):
                    cc1, cc2, cc3 = st.columns(3)
                    c_razao = cc1.text_input("Razão Social*", value=cli_edit.razao_social if cli_edit else "")
                    c_fant = cc2.text_input("Nome Fantasia", value=cli_edit.nome_fantasia or "" if cli_edit else "")
                    c_cnpj = cc3.text_input("CNPJ / CPF*", value=cli_edit.cnpj_cpf if cli_edit else "")

                    cc4, cc5, cc6 = st.columns(3)
                    c_resp = cc4.text_input("Responsável Comercial", value=cli_edit.responsavel_comercial or "" if cli_edit else "")
                    c_tel = cc5.text_input("Telefone Contato", value=cli_edit.telefone_comercial or "" if cli_edit else "")
                    c_cid = cc6.text_input("Cidade", value=cli_edit.cidade or "" if cli_edit else "")

                    if st.form_submit_button("💾 Salvar Cliente"):
                        if not c_razao or not c_cnpj:
                            st.error("Preencha Razão Social e CNPJ/CPF.")
                        else:
                            obj = cli_edit or Cliente()
                            obj.razao_social = c_razao.strip()
                            obj.nome_fantasia = (c_fant or c_razao).strip()
                            obj.cnpj_cpf = c_cnpj.strip()
                            obj.responsavel_comercial = c_resp.strip()
                            obj.telefone_comercial = c_tel.strip()
                            obj.cidade = c_cid.strip()
                            if not cli_edit:
                                db.add(obj)
                            db.commit()
                            st.success("Cliente salvo com sucesso!")
                            st.rerun()

                if clientes:
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "Nome Fantasia": c.nome_fantasia,
                                    "Razão Social": c.razao_social,
                                    "CNPJ/CPF": c.cnpj_cpf,
                                    "Responsável": c.responsavel_comercial,
                                    "Contato": c.telefone_comercial,
                                }
                                for c in clientes
                            ]
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

            # --- LOCAIS ---
            with tab_l:
                with st.form("form_local"):
                    lc1, lc2, lc3 = st.columns(3)
                    l_nome = lc1.text_input("Nome do Local / Empresa*")
                    l_tipo = lc2.selectbox("Tipo", ["Coleta", "Entrega", "Coleta e Entrega", "CD / Terminal"])
                    l_cep = lc3.text_input("CEP")

                    lc4, lc5, lc6 = st.columns([2, 1, 0.6])
                    l_end = lc4.text_input("Endereço Completo")
                    l_cid = lc5.text_input("Cidade")
                    l_uf = lc6.text_input("UF", max_chars=2)

                    if st.form_submit_button("💾 Salvar Local"):
                        if not l_nome:
                            st.error("Preencha o Nome do Local.")
                        else:
                            db.add(
                                Local(
                                    nome_local=l_nome.strip(),
                                    tipo_instalacao=l_tipo,
                                    cep=l_cep.strip(),
                                    endereco_completo=l_end.strip(),
                                    cidade=l_cid.strip(),
                                    uf=l_uf.strip().upper(),
                                )
                            )
                            db.commit()
                            st.success("Local cadastrado com sucesso!")
                            st.rerun()

                if locais:
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "Local": l.nome_local,
                                    "Tipo": l.tipo_instalacao,
                                    "Endereço": l.endereco_completo,
                                    "Cidade": l.cidade,
                                    "UF": l.uf,
                                    "CEP": l.cep,
                                }
                                for l in locais
                            ]
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

            # --- FORNECEDORES ---
            with tab_f:
                with st.form("form_fornecedor"):
                    fc1, fc2, fc3 = st.columns(3)
                    f_nome = fc1.text_input("Nome Fantasia / Posto*")
                    f_cat = fc2.selectbox("Categoria", CATEGORIAS_UNIFICADAS)
                    f_cnpj = fc3.text_input("CNPJ")

                    fc4, fc5 = st.columns([2, 1])
                    f_cid = fc4.text_input("Cidade")
                    f_uf = fc5.text_input("UF", max_chars=2)

                    if st.form_submit_button("💾 Salvar Fornecedor"):
                        if not f_nome:
                            st.error("Preencha o Nome do Fornecedor.")
                        else:
                            db.add(
                                Fornecedor(
                                    nome_fantasia=f_nome.strip(),
                                    categoria_servico=f_cat,
                                    cnpj=f_cnpj.strip() or None,
                                    cidade=f_cid.strip(),
                                    uf=f_uf.strip().upper(),
                                )
                            )
                            db.commit()
                            st.success("Fornecedor cadastrado com sucesso!")
                            st.rerun()

                if fornecedores:
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "Nome": f.nome_fantasia,
                                    "Categoria": f.categoria_servico,
                                    "CNPJ": f.cnpj,
                                    "Cidade/UF": f"{f.cidade or ''}/{f.uf or ''}",
                                }
                                for f in fornecedores
                            ]
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

    finally:
        db.close()


if __name__ == "__main__":
    main()