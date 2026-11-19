import base64
import inspect
import io
import os
import re
import zlib
from datetime import date, datetime, time
from decimal import Decimal

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
import pandas as pd
import streamlit as st
from sqlalchemy import func

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
    sincronizar_colunas_banco,
)

# ==============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA E INICIALIZAÇÃO DO BANCO
# ==============================================================================
st.set_page_config(
    page_title="FAEG LOG — Gestão Operacional e Financeira",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource(show_spinner=False)
def inicializar_banco_seguro():
    Base.metadata.create_all(bind=engine)
    sincronizar_colunas_banco()
    return True


inicializar_banco_seguro()

# ==============================================================================
# 2. IDENTIDADE VISUAL OFICIAL FAEG (MANUAL DA MARCA 2026)
# ==============================================================================
MENU_ITENS = [
    "1. Frota FAEG",
    "2. Frete e Docs",
    "3. Cliente",
    "4. Negociação / Pgto",
    "5. Coleta (Origem)",
    "6. Entrega (Destino)",
    "7. Despesas de Viagem",
    "8. Fechamento Final",
    "9. Relatórios / Exportar",
    "10. Cadastros Gerais",
    "11. Consultas Gerais",
]

OPCOES_TIPO_VIAGEM = ["Individual", "Ciclo"]
OPCOES_TIPO_FRETE = ["Dedicado", "Complemento", "Cheio", "Fracionado", "Agregado"]
OPCOES_ORIGEM_FRETE = [
    "Aplicativo de Fretes",
    "Redes Sociais",
    "Cliente Fixo",
    "Cliente Recorrente",
    "Cliente Eventual",
    "Indicação",
    "Prospecção",
    "Transportadora Parceira",
    "Outros",
]
OPCOES_STATUS_VIAGEM = ["Planejada", "Em Trânsito", "Concluída", "Faturada", "Cancelada"]
OPCOES_TIPO_DESPESA = [
    "Combustível (Diesel)",
    "Combustível (ARLA 32)",
    "Pedágio",
    "Alimentação",
    "Hospedagem",
    "Manutenção Emergencial",
    "Chapa / Descarga",
    "Outras Despesas",
]


def carregar_logo_base64():
    """Carrega o logotipo oficial PNG sem cache travado para refletir atualizações imediatas."""
    caminhos = [
        os.path.join("assets", "logo_faeg.png"),
        "logo_faeg.png",
        os.path.join("assets", "logo.png"),
    ]
    for caminho in caminhos:
        if os.path.exists(caminho):
            with open(caminho, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
    return None


def injetar_css_faeg():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap');

        html, body, [class*="css"], .stApp {
            font-family: 'Montserrat', sans-serif !important;
        }

        /* Fundo geral Cinza Névoa (#E9E9E9) */
        .stApp, [data-testid="stAppViewContainer"] {
            background-color: #E9E9E9 !important;
            color: #0D263C !important;
        }

        [data-testid="stHeader"] {
            background-color: rgba(233, 233, 233, 0.85) !important;
        }

        .block-container {
            padding-top: 1.3rem !important;
            padding-bottom: 2.5rem !important;
            max-width: 1380px !important;
        }

        /* ==============================================================
           BARRA LATERAL — AZUL ESTRUTURAL (#0D263C)
           ============================================================== */
        [data-testid="stSidebar"] {
            background-color: #0D263C !important;
            border-right: 1px solid #163856 !important;
        }

        [data-testid="stSidebar"] * {
            color: #FFFFFF;
        }

        /* Bloco da Marca (Logo + Tipografia Oficial) */
        .sidebar-brand {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 0.4rem 0.2rem 1rem 0.2rem;
            border-bottom: 1px solid rgba(171, 206, 225, 0.22);
            margin-bottom: 1rem;
        }

        .sidebar-brand img {
            height: 50px;
            width: auto;
            max-width: 78px;
            object-fit: contain;
            border-radius: 6px;
            flex-shrink: 0;
        }

        .sidebar-monogram {
            width: 44px;
            height: 44px;
            background-color: #F34D25;
            color: #FFFFFF !important;
            font-weight: 800;
            font-size: 1.45rem;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }

        .sidebar-brand-text {
            display: flex;
            flex-direction: column;
            line-height: 1.15;
        }

        .sidebar-brand-title {
            font-size: 1.35rem;
            font-weight: 800;
            letter-spacing: 0.04em;
            color: #FFFFFF !important;
        }

        .sidebar-brand-sub {
            font-size: 0.66rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #ABCEE1 !important;
            margin-top: 3px;
        }

        /* Menu Radio na Sidebar */
        [data-testid="stSidebar"] div[role="radiogroup"] {
            gap: 4px !important;
        }

        [data-testid="stSidebar"] div[role="radiogroup"] label {
            background-color: transparent !important;
            padding: 8px 12px !important;
            border-radius: 6px !important;
            border-left: 4px solid transparent !important;
            transition: all 0.18s ease !important;
            margin: 0 !important;
            cursor: pointer !important;
        }

        [data-testid="stSidebar"] div[role="radiogroup"] label:hover {
            background-color: rgba(171, 206, 225, 0.14) !important;
        }

        [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
            background-color: rgba(171, 206, 225, 0.22) !important;
            border-left: 4px solid #F34D25 !important;
        }

        [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p {
            color: #FFFFFF !important;
            font-weight: 700 !important;
        }

        [data-testid="stSidebar"] div[role="radiogroup"] label p {
            font-size: 0.84rem !important;
            color: #E2E8F0 !important;
            font-weight: 500 !important;
        }

        /* Esconde bolinha padrão do radio na sidebar */
        [data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {
            display: none !important;
        }

        /* Seletor na Sidebar */
        [data-testid="stSidebar"] [data-baseweb="select"] > div {
            background-color: #153857 !important;
            border: 1px solid rgba(171, 206, 225, 0.35) !important;
            color: #FFFFFF !important;
            min-height: 38px !important;
        }

        [data-testid="stSidebar"] [data-baseweb="select"] span,
        [data-testid="stSidebar"] [data-baseweb="select"] div {
            color: #FFFFFF !important;
        }

        /* Botão Secundário na Sidebar (Nova Viagem) */
        [data-testid="stSidebar"] button[kind="secondary"] {
            background-color: #163B5C !important;
            color: #FFFFFF !important;
            border: 1px solid #ABCEE1 !important;
            font-weight: 600 !important;
            border-radius: 8px !important;
        }

        [data-testid="stSidebar"] button[kind="secondary"]:hover {
            background-color: #1E4D76 !important;
        }

        /* Botão Principal Laranja Energia (#F34D25) */
        button[kind="primary"] {
            background-color: #F34D25 !important;
            color: #FFFFFF !important;
            border: none !important;
            font-weight: 700 !important;
            border-radius: 8px !important;
            padding: 0.55rem 1.1rem !important;
            transition: background-color 0.2s ease !important;
        }

        button[kind="primary"]:hover {
            background-color: #D93D18 !important;
            color: #FFFFFF !important;
        }

        /* Botões Secundários na Área Principal */
        .main button[kind="secondary"],
        [data-testid="stMain"] button[kind="secondary"] {
            background-color: #0D263C !important;
            color: #FFFFFF !important;
            border: 1px solid #0D263C !important;
            font-weight: 600 !important;
            border-radius: 8px !important;
        }

        .main button[kind="secondary"]:hover,
        [data-testid="stMain"] button[kind="secondary"]:hover {
            background-color: #193E5E !important;
            color: #FFFFFF !important;
        }

        /* ==============================================================
           CAMPOS CLAROS, CONTRASTE TOTAL E SEM CORTES
           ============================================================== */
        label, [data-testid="stWidgetLabel"] p {
            color: #0D263C !important;
            font-weight: 700 !important;
            font-size: 0.76rem !important;
            text-transform: uppercase !important;
            letter-spacing: 0.03em !important;
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: unset !important;
            margin-bottom: 4px !important;
        }

        [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
            color: #ABCEE1 !important;
            font-size: 0.72rem !important;
        }

        /* Inputs editáveis: Branco Puro (#FFFFFF) com texto Azul Estrutural (#0D263C) */
        [data-testid="stMain"] input,
        [data-testid="stMain"] textarea,
        [data-testid="stMain"] [data-baseweb="input"] > div,
        [data-testid="stMain"] [data-baseweb="base-input"],
        [data-testid="stMain"] [data-baseweb="select"] > div {
            background-color: #FFFFFF !important;
            color: #0D263C !important;
            border-color: #CBD5E1 !important;
            border-radius: 8px !important;
            min-height: 42px !important;
        }

        [data-testid="stMain"] input::placeholder,
        [data-testid="stMain"] textarea::placeholder {
            color: #64748B !important;
            opacity: 1 !important;
        }

        [data-testid="stMain"] [data-baseweb="select"] span,
        [data-testid="stMain"] [data-baseweb="select"] div {
            color: #0D263C !important;
            font-weight: 500 !important;
        }

        /* Foco em Laranja Energia (#F34D25) */
        [data-testid="stMain"] [data-baseweb="input"] > div:focus-within,
        [data-testid="stMain"] [data-baseweb="select"] > div:focus-within,
        [data-testid="stMain"] textarea:focus {
            border-color: #F34D25 !important;
            box-shadow: 0 0 0 1px #F34D25 !important;
        }

        /* Campos Automáticos (disabled): Cinza Névoa suave com borda tracejada */
        [data-testid="stMain"] input:disabled,
        [data-testid="stMain"] [data-baseweb="input"]:has(input:disabled) > div {
            background-color: #F1F5F9 !important;
            color: #0D263C !important;
            -webkit-text-fill-color: #0D263C !important;
            font-weight: 600 !important;
            border: 1px dashed #94A3B8 !important;
            opacity: 1 !important;
        }

        /* Dropdowns / Listbox */
        ul[role="listbox"] {
            background-color: #FFFFFF !important;
            border: 1px solid #CBD5E1 !important;
        }

        ul[role="listbox"] li {
            background-color: #FFFFFF !important;
            color: #0D263C !important;
        }

        ul[role="listbox"] li:hover,
        ul[role="listbox"] li[aria-selected="true"] {
            background-color: #ABCEE1 !important;
            color: #0D263C !important;
            font-weight: 600 !important;
        }

        /* ==============================================================
           BARRA SUPERIOR EXECUTIVA E CARTÕES BRANCOS
           ============================================================== */
        .top-context-bar {
            background-color: #FFFFFF;
            border-left: 6px solid #0D263C;
            border-radius: 10px;
            padding: 0.9rem 1.3rem;
            margin-bottom: 1.1rem;
            box-shadow: 0 2px 6px rgba(13, 38, 60, 0.06);
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
        }

        .ctx-group {
            display: flex;
            flex-direction: column;
        }

        .ctx-label {
            font-size: 0.68rem;
            font-weight: 700;
            text-transform: uppercase;
            color: #64748B;
            letter-spacing: 0.04em;
        }

        .ctx-value {
            font-size: 0.98rem;
            font-weight: 800;
            color: #0D263C;
            margin-top: 2px;
        }

        .badge-codigo {
            background-color: #0D263C;
            color: #FFFFFF;
            padding: 3px 10px;
            border-radius: 6px;
            font-weight: 800;
            font-size: 0.92rem;
            display: inline-block;
        }

        .badge-status {
            background-color: #ABCEE1;
            color: #0D263C;
            padding: 3px 10px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 0.82rem;
            display: inline-block;
        }

        /* Cartão de Cabeçalho da Etapa */
        .etapa-header {
            background-color: #FFFFFF;
            border-radius: 10px;
            padding: 1.1rem 1.4rem;
            margin-bottom: 1rem;
            border-bottom: 3px solid #0D263C;
            box-shadow: 0 2px 6px rgba(13, 38, 60, 0.05);
        }

        .etapa-header h2 {
            margin: 0 !important;
            font-size: 1.32rem !important;
            font-weight: 800 !important;
            color: #0D263C !important;
        }

        .etapa-header p {
            margin: 4px 0 0 0 !important;
            font-size: 0.84rem !important;
            color: #475569 !important;
        }

        .secao-titulo {
            font-size: 0.85rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: #0D263C;
            border-left: 4px solid #F34D25;
            padding-left: 10px;
            margin: 1.1rem 0 0.7rem 0;
        }

        /* Cartões KPI / DRE */
        .kpi-card {
            background-color: #FFFFFF;
            border-radius: 10px;
            padding: 1rem 1.2rem;
            border-top: 4px solid #0D263C;
            box-shadow: 0 2px 6px rgba(13, 38, 60, 0.05);
        }

        .kpi-card.accent {
            border-top-color: #F34D25;
        }

        .kpi-card.info {
            border-top-color: #ABCEE1;
        }

        .kpi-title {
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            color: #64748B;
        }

        .kpi-num {
            font-size: 1.45rem;
            font-weight: 800;
            color: #0D263C;
            margin-top: 4px;
        }

        /* Containers com borda no Streamlit */
        [data-testid="stVerticalBlockBorderWrapper"] {
            background-color: #FFFFFF !important;
            border-radius: 10px !important;
            border: 1px solid #DCE3EA !important;
            padding: 1rem !important;
            box-shadow: 0 2px 6px rgba(13, 38, 60, 0.04) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


injetar_css_faeg()

# ==============================================================================
# 3. FUNÇÕES AUXILIARES DE NEGÓCIO, FORMATAÇÃO E ESTADO
# ==============================================================================


def fmt_moeda(valor) -> str:
    try:
        v = float(valor or 0.0)
    except (TypeError, ValueError):
        v = 0.0
    texto = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def to_float(valor, padrao: float = 0.0) -> float:
    if valor is None:
        return padrao
    try:
        return float(valor)
    except (TypeError, ValueError):
        return padrao


def to_int(valor, padrao: int = 0) -> int:
    if valor is None:
        return padrao
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return padrao


def parse_time_safe(val, padrao=time(8, 0)):
    if isinstance(val, time):
        return val
    if isinstance(val, datetime):
        return val.time()
    if isinstance(val, str) and ":" in val:
        partes = val.strip().split(":")
        try:
            return time(int(partes[0]), int(partes[1]))
        except ValueError:
            return padrao
    return padrao


def parse_date_safe(val, padrao=None):
    if padrao is None:
        padrao = date.today()
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str) and val.strip():
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(val.strip()[:10], fmt).date()
            except ValueError:
                continue
    return padrao


def separar_rota_texto(rota_resumo: str):
    if not rota_resumo:
        return "", ""
    for sep in ("->", "→", " x ", " X ", " - "):
        if sep in rota_resumo:
            partes = rota_resumo.split(sep, 1)
            return partes[0].strip(), partes[1].strip()
    return rota_resumo.strip(), ""


def gerar_proximo_codigo_viagem(db) -> str:
    """Calcula o próximo código único sequencial no formato V1, V2, V3..."""
    codigos = [
        c[0]
        for c in db.query(Viagem.codigo_viagem)
        .filter(Viagem.codigo_viagem.isnot(None))
        .all()
        if c[0]
    ]
    maior = 0
    for cod in codigos:
        m = re.match(r"^V(\d+)$", str(cod).strip(), re.IGNORECASE)
        if m:
            num = int(m.group(1))
            if num > maior:
                maior = num
    return f"V{maior + 1}"


def form_data_padrao(proximo_codigo: str = "V1") -> dict:
    hoje = date.today()
    return {
        "id_viagem": None,
        "id_ciclo": None,
        "codigo_viagem": proximo_codigo,
        "status_viagem": "Planejada",
        "tipo_viagem": "Individual",
        "tipo_frete": "Dedicado",
        "id_motorista": None,
        "id_veiculo": None,
        "id_frete_externo": "",
        "data_frete": hoje,
        "nome_operacao_ciclo": "",
        "rota_origem": "",
        "rota_destino": "",
        "km_rota_planejado": 0.0,
        "tipo_material": "",
        "qtde_volumes": 0,
        "volume_m3": 0.0,
        "peso_bruto_kg": 0.0,
        "nfe_carga": "",
        "cte_numero": "",
        "mdfe_numero": "",
        "ciot_numero": "",
        "id_cliente": None,
        "forma_contratacao": "Aplicativo de Fretes",
        "valor_divulgado": 0.0,
        "valor_negociado_total": 0.0,
        "perc_adiantamento": 70.0,
        "data_prevista_adiantamento": hoje,
        "valor_adiantamento": 0.0,
        "perc_saldo": 30.0,
        "data_prevista_saldo": hoje,
        "valor_saldo": 0.0,
        "id_local_coleta": None,
        "data_coleta": hoje,
        "hora_planejada_coleta": time(8, 0),
        "hora_real_coleta": time(8, 0),
        "id_local_entrega": None,
        "data_entrega": hoje,
        "hora_planejada_entrega": time(17, 0),
        "hora_real_entrega": time(17, 0),
        "odometro_inicial": 0,
        "odometro_final": 0,
        "observacao_geral": "",
    }


def carregar_viagem_para_estado(id_viagem: int):
    db = SessionLocal()
    try:
        vg = db.query(Viagem).filter(Viagem.id_viagem == id_viagem).first()
        if not vg:
            return
        ciclo = vg.ciclo
        fin = ciclo.financeiro if ciclo else None

        origem = getattr(vg, "rota_origem", None) or ""
        destino = getattr(vg, "rota_destino", None) or ""
        if not origem and not destino and vg.rota_resumo:
            origem, destino = separar_rota_texto(vg.rota_resumo)

        cod = getattr(vg, "codigo_viagem", None) or f"V{vg.id_viagem}"
        tipo_vg = getattr(vg, "tipo_viagem", None) or (
            "Ciclo" if ciclo and ciclo.nome_operacao and "Ciclo" in ciclo.nome_operacao else "Individual"
        )
        tipo_fr = vg.tipo_frete if vg.tipo_frete in OPCOES_TIPO_FRETE else "Dedicado"
        origem_fr = (
            fin.forma_contratacao
            if fin and fin.forma_contratacao in OPCOES_ORIGEM_FRETE
            else "Aplicativo de Fretes"
        )

        st.session_state["form_data"] = {
            "id_viagem": vg.id_viagem,
            "id_ciclo": vg.id_ciclo,
            "codigo_viagem": cod,
            "status_viagem": vg.status_viagem or "Planejada",
            "tipo_viagem": tipo_vg,
            "tipo_frete": tipo_fr,
            "id_motorista": vg.id_motorista,
            "id_veiculo": vg.id_veiculo,
            "id_frete_externo": vg.id_frete_externo or "",
            "data_frete": parse_date_safe(vg.data_coleta or vg.data_criacao),
            "nome_operacao_ciclo": ciclo.nome_operacao if ciclo else "",
            "rota_origem": origem,
            "rota_destino": destino,
            "km_rota_planejado": to_float(vg.km_rota_planejado),
            "tipo_material": vg.tipo_material or "",
            "qtde_volumes": to_int(vg.qtde_volumes),
            "volume_m3": to_float(vg.volume_m3),
            "peso_bruto_kg": to_float(vg.peso_bruto_kg),
            "nfe_carga": vg.nfe_carga or "",
            "cte_numero": vg.cte_numero or "",
            "mdfe_numero": vg.mdfe_numero or "",
            "ciot_numero": vg.ciot_numero or "",
            "id_cliente": ciclo.id_cliente if ciclo else None,
            "forma_contratacao": origem_fr,
            "valor_divulgado": to_float(fin.valor_divulgado if fin else 0.0),
            "valor_negociado_total": to_float(fin.valor_negociado_total if fin else 0.0),
            "perc_adiantamento": to_float(fin.perc_adiantamento if fin else 70.0, 70.0),
            "data_prevista_adiantamento": parse_date_safe(
                fin.data_prevista_adiantamento if fin else None
            ),
            "valor_adiantamento": to_float(fin.valor_adiantamento if fin else 0.0),
            "perc_saldo": to_float(fin.perc_saldo if fin else 30.0, 30.0),
            "data_prevista_saldo": parse_date_safe(fin.data_prevista_saldo if fin else None),
            "valor_saldo": to_float(fin.valor_saldo if fin else 0.0),
            "id_local_coleta": vg.id_local_coleta,
            "data_coleta": parse_date_safe(vg.data_coleta),
            "hora_planejada_coleta": parse_time_safe(vg.hora_planejada_coleta, time(8, 0)),
            "hora_real_coleta": parse_time_safe(vg.hora_real_coleta, time(8, 0)),
            "id_local_entrega": vg.id_local_entrega,
            "data_entrega": parse_date_safe(vg.data_entrega),
            "hora_planejada_entrega": parse_time_safe(vg.hora_planejada_entrega, time(17, 0)),
            "hora_real_entrega": parse_time_safe(vg.hora_real_entrega, time(17, 0)),
            "odometro_inicial": to_int(vg.odometro_inicial),
            "odometro_final": to_int(vg.odometro_final),
            "observacao_geral": getattr(vg, "observacao_geral", None) or "",
        }

        despesas_db = (
            db.query(ViagemDespesa)
            .filter(ViagemDespesa.id_viagem == vg.id_viagem)
            .order_by(ViagemDespesa.id_despesa)
            .all()
        )
        st.session_state["despesas_lista"] = [
            {
                "id_despesa": d.id_despesa,
                "id_fornecedor": d.id_fornecedor,
                "tipo_despesa": d.tipo_despesa,
                "descricao_detalhe": d.descricao_detalhe or "",
                "quantidade": to_float(d.quantidade, 1.0),
                "valor_unitario": to_float(d.valor_unitario, 0.0),
                "valor_total": to_float(d.valor_total, 0.0),
                "data_despesa": parse_date_safe(d.data_despesa),
            }
            for d in despesas_db
        ]
        st.session_state["despesa_edit_idx"] = None
    finally:
        db.close()


def iniciar_nova_viagem():
    db = SessionLocal()
    try:
        prox = gerar_proximo_codigo_viagem(db)
    finally:
        db.close()
    st.session_state["form_data"] = form_data_padrao(prox)
    st.session_state["despesas_lista"] = []
    st.session_state["despesa_edit_idx"] = None
    st.session_state["viagem_ativa_selector"] = None


# Inicialização do Session State
if "menu_operacional_radio" not in st.session_state:
    st.session_state["menu_operacional_radio"] = MENU_ITENS[0]

if "form_data" not in st.session_state:
    db_init = SessionLocal()
    try:
        prox_cod = gerar_proximo_codigo_viagem(db_init)
    finally:
        db_init.close()
    st.session_state["form_data"] = form_data_padrao(prox_cod)

if "despesas_lista" not in st.session_state:
    st.session_state["despesas_lista"] = []

if "despesa_edit_idx" not in st.session_state:
    st.session_state["despesa_edit_idx"] = None


# ==============================================================================
# 4. CARREGAMENTO DE DADOS BASE DO NEON
# ==============================================================================
def carregar_dados_base():
    db = SessionLocal()
    try:
        motoristas = db.query(Motorista).order_by(Motorista.nome_completo).all()
        veiculos = db.query(Veiculo).order_by(Veiculo.descricao_marca).all()
        clientes = db.query(Cliente).order_by(Cliente.razao_social).all()
        locais = db.query(Local).order_by(Local.nome_local).all()
        fornecedores = db.query(Fornecedor).order_by(Fornecedor.nome_fantasia).all()
        viagens = db.query(Viagem).order_by(Viagem.id_viagem.desc()).all()

        lista_mot = [
            {
                "id": m.id_motorista,
                "nome": m.nome_completo,
                "cpf": m.cpf,
                "telefone": m.telefone_contato or "",
                "cnh": m.cnh_numero,
                "categoria": m.cnh_categoria or "",
                "validade": m.cnh_validade,
                "vinculo": m.vinculo or "Próprio",
            }
            for m in motoristas
        ]
        lista_vei = [
            {
                "id": v.id_veiculo,
                "descricao": v.descricao_marca,
                "placa": v.placa,
                "tipo": v.tipo_veiculo or "",
                "renavam": v.renavam or "",
                "ano": v.ano_fabricacao or 2024,
                "cap_kg": to_float(v.capacidade_carga_kg),
                "cap_m3": to_float(v.capacidade_volume_m3),
            }
            for v in veiculos
        ]
        lista_cli = [
            {
                "id": c.id_cliente,
                "razao_social": c.razao_social,
                "nome_fantasia": getattr(c, "nome_fantasia", None) or c.razao_social,
                "cnpj_cpf": c.cnpj_cpf,
                "ie": c.inscricao_estadual or "",
                "responsavel": c.responsavel_comercial or "",
                "telefone": c.telefone_comercial or "",
                "email": c.email_financeiro or "",
                "prazo": c.prazo_pagamento_dias or 30,
                "cep": getattr(c, "cep", None) or "",
                "endereco": getattr(c, "endereco_completo", None) or "",
                "cidade": getattr(c, "cidade", None) or "",
                "uf": getattr(c, "uf", None) or "",
            }
            for c in clientes
        ]
        lista_loc = [
            {
                "id": l.id_local,
                "id_cliente": getattr(l, "id_cliente", None),
                "nome": l.nome_local,
                "tipo": l.tipo_instalacao or "Centro de Distribuição",
                "cep": l.cep or "",
                "endereco": l.endereco_completo or "",
                "cidade": l.cidade or "",
                "uf": l.uf or "",
                "contato": l.contato_portaria or "",
                "restricao": l.restricao_horario or "",
            }
            for l in locais
        ]
        lista_forn = [
            {
                "id": f.id_fornecedor,
                "razao_social": getattr(f, "razao_social", None) or f.nome_fantasia,
                "nome": f.nome_fantasia,
                "cnpj": f.cnpj or "",
                "categoria": f.categoria_servico or "Posto de Combustível",
                "cidade": f.cidade or "",
                "uf": f.uf or "",
            }
            for f in fornecedores
        ]
        lista_vg = []
        for vg in viagens:
            cod = getattr(vg, "codigo_viagem", None) or f"V{vg.id_viagem}"
            orig = getattr(vg, "rota_origem", None) or ""
            dest = getattr(vg, "rota_destino", None) or ""
            if not orig and not dest and vg.rota_resumo:
                orig, dest = separar_rota_texto(vg.rota_resumo)
            rota_lbl = f"{orig} → {dest}" if (orig or dest) else (vg.rota_resumo or "Sem rota")
            cli_nome = (
                vg.ciclo.cliente.razao_social
                if vg.ciclo and vg.ciclo.cliente
                else "Cliente não definido"
            )
            lista_vg.append(
                {
                    "id": vg.id_viagem,
                    "codigo": cod,
                    "rota": rota_lbl,
                    "origem": orig,
                    "destino": dest,
                    "cliente": cli_nome,
                    "status": vg.status_viagem or "Planejada",
                }
            )
        return lista_mot, lista_vei, lista_cli, lista_loc, lista_forn, lista_vg
    finally:
        db.close()


motoristas_list, veiculos_list, clientes_list, locais_list, fornecedores_list, viagens_list = (
    carregar_dados_base()
)

# ==============================================================================
# 5. SALVAMENTO DA VIAGEM E EXPORTAÇÕES (EXCEL E PDF NATIVO)
# ==============================================================================


def salvar_viagem_no_banco():
    fd = st.session_state["form_data"]
    codigo = str(fd.get("codigo_viagem") or "").strip().upper()

    if not codigo:
        st.error("Informe o Código da Viagem (ex.: V1, V2...) na etapa 1. Frota FAEG.")
        return
    if not fd.get("id_motorista"):
        st.error("Selecione um Motorista na etapa 1. Frota FAEG antes de salvar.")
        return
    if not fd.get("id_veiculo"):
        st.error("Selecione um Veículo na etapa 1. Frota FAEG antes de salvar.")
        return
    if not fd.get("id_cliente"):
        st.error("Selecione um Cliente na etapa 3. Cliente antes de salvar.")
        return
    if not fd.get("id_local_coleta") or not fd.get("id_local_entrega"):
        st.error("Selecione os locais de Coleta (etapa 5) e Entrega (etapa 6) antes de salvar.")
        return

    db = SessionLocal()
    try:
        # Valida unicidade do código da viagem (V1, V2...)
        conflito = (
            db.query(Viagem)
            .filter(func.upper(Viagem.codigo_viagem) == codigo)
            .filter(Viagem.id_viagem != (fd.get("id_viagem") or -1))
            .first()
        )
        if conflito:
            st.error(
                f"O código '{codigo}' já está em uso em outra viagem. Edite o código ou carregue o registro existente."
            )
            return

        # 1. Ciclo Operacional e Financeiro
        ciclo = None
        if fd.get("id_ciclo"):
            ciclo = (
                db.query(CicloOperacional)
                .filter(CicloOperacional.id_ciclo == fd["id_ciclo"])
                .first()
            )
        if not ciclo:
            nome_op = (
                fd.get("nome_operacao_ciclo").strip()
                if fd.get("tipo_viagem") == "Ciclo" and fd.get("nome_operacao_ciclo")
                else f"Operação {codigo}"
            )
            ciclo = CicloOperacional(
                id_cliente=fd["id_cliente"],
                nome_operacao=nome_op,
                data_abertura=fd.get("data_frete") or date.today(),
                status_ciclo="Em Andamento",
            )
            db.add(ciclo)
            db.flush()
        else:
            ciclo.id_cliente = fd["id_cliente"]
            if fd.get("tipo_viagem") == "Ciclo" and fd.get("nome_operacao_ciclo"):
                ciclo.nome_operacao = fd["nome_operacao_ciclo"].strip()

        fin = ciclo.financeiro
        if not fin:
            fin = CicloFinanceiro(id_ciclo=ciclo.id_ciclo)
            db.add(fin)

        fin.forma_contratacao = fd.get("forma_contratacao")
        fin.valor_divulgado = Decimal(str(to_float(fd.get("valor_divulgado"))))
        fin.valor_negociado_total = Decimal(str(to_float(fd.get("valor_negociado_total"))))
        fin.perc_adiantamento = Decimal(str(to_float(fd.get("perc_adiantamento"))))
        fin.data_prevista_adiantamento = fd.get("data_prevista_adiantamento")
        fin.valor_adiantamento = Decimal(str(to_float(fd.get("valor_adiantamento"))))
        fin.perc_saldo = Decimal(str(to_float(fd.get("perc_saldo"))))
        fin.data_prevista_saldo = fd.get("data_prevista_saldo")
        fin.valor_saldo = Decimal(str(to_float(fd.get("valor_saldo"))))

        # 2. Viagem
        vg = None
        if fd.get("id_viagem"):
            vg = db.query(Viagem).filter(Viagem.id_viagem == fd["id_viagem"]).first()
        if not vg:
            vg = Viagem(id_ciclo=ciclo.id_ciclo)
            db.add(vg)

        origem = str(fd.get("rota_origem") or "").strip()
        destino = str(fd.get("rota_destino") or "").strip()
        rota_resumo = f"{origem} → {destino}" if (origem and destino) else (origem or destino)

        odo_ini = to_int(fd.get("odometro_inicial"))
        odo_fim = to_int(fd.get("odometro_final"))
        km_real = max(0, odo_fim - odo_ini) if (odo_fim > 0 and odo_fim >= odo_ini) else 0

        vg.id_ciclo = ciclo.id_ciclo
        vg.codigo_viagem = codigo
        vg.status_viagem = fd.get("status_viagem") or "Planejada"
        if hasattr(vg, "tipo_viagem"):
            vg.tipo_viagem = fd.get("tipo_viagem") or "Individual"
        vg.tipo_frete = fd.get("tipo_frete") or "Dedicado"
        vg.id_motorista = fd["id_motorista"]
        vg.id_veiculo = fd["id_veiculo"]
        vg.id_frete_externo = str(fd.get("id_frete_externo") or "").strip()
        if hasattr(vg, "rota_origem"):
            vg.rota_origem = origem
        if hasattr(vg, "rota_destino"):
            vg.rota_destino = destino
        vg.rota_resumo = rota_resumo
        vg.km_rota_planejado = Decimal(str(to_float(fd.get("km_rota_planejado"))))

        vg.tipo_material = str(fd.get("tipo_material") or "").strip()
        vg.qtde_volumes = to_int(fd.get("qtde_volumes"))
        vg.volume_m3 = Decimal(str(to_float(fd.get("volume_m3"))))
        vg.peso_bruto_kg = Decimal(str(to_float(fd.get("peso_bruto_kg"))))
        vg.nfe_carga = str(fd.get("nfe_carga") or "").strip()
        vg.cte_numero = str(fd.get("cte_numero") or "").strip()
        vg.mdfe_numero = str(fd.get("mdfe_numero") or "").strip()
        vg.ciot_numero = str(fd.get("ciot_numero") or "").strip()

        vg.id_local_coleta = fd["id_local_coleta"]
        vg.data_coleta = fd.get("data_coleta")
        vg.hora_planejada_coleta = fd.get("hora_planejada_coleta")
        vg.hora_real_coleta = fd.get("hora_real_coleta")

        vg.id_local_entrega = fd["id_local_entrega"]
        vg.data_entrega = fd.get("data_entrega")
        vg.hora_planejada_entrega = fd.get("hora_planejada_entrega")
        vg.hora_real_entrega = fd.get("hora_real_entrega")

        vg.odometro_inicial = odo_ini
        vg.odometro_final = odo_fim
        vg.km_real_rodado = km_real
        if hasattr(vg, "observacao_geral"):
            vg.observacao_geral = str(fd.get("observacao_geral") or "").strip()

        db.flush()

        # 3. Despesas da Viagem
        db.query(ViagemDespesa).filter(ViagemDespesa.id_viagem == vg.id_viagem).delete()
        for item in st.session_state["despesas_lista"]:
            qtd = to_float(item.get("quantidade"), 1.0)
            v_unit = to_float(item.get("valor_unitario"), 0.0)
            v_tot = round(qtd * v_unit, 2)
            db.add(
                ViagemDespesa(
                    id_viagem=vg.id_viagem,
                    id_fornecedor=item.get("id_fornecedor"),
                    tipo_despesa=item.get("tipo_despesa") or "Outras Despesas",
                    descricao_detalhe=item.get("descricao_detalhe") or "",
                    quantidade=Decimal(str(qtd)),
                    valor_unitario=Decimal(str(v_unit)),
                    valor_total=Decimal(str(v_tot)),
                    data_despesa=item.get("data_despesa") or date.today(),
                )
            )

        db.commit()
        fd["id_viagem"] = vg.id_viagem
        fd["id_ciclo"] = ciclo.id_ciclo
        fd["codigo_viagem"] = codigo
        st.toast(f"Viagem {codigo} salva com sucesso no banco Neon!", icon="✅")
    except Exception as exc:
        db.rollback()
        st.error(f"Erro ao salvar viagem no banco: {exc}")
    finally:
        db.close()


def gerar_excel_viagem(fd: dict, despesas: list, cliente_nome: str, motorista_nome: str, veiculo_txt: str) -> bytes:
    wb = openpyxl.Workbook()
    ws_resumo = wb.active
    ws_resumo.title = "Resumo Viagem"

    header_fill = PatternFill(start_color="0D263C", end_color="0D263C", fill_type="solid")
    accent_fill = PatternFill(start_color="F34D25", end_color="F34D25", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    bold_font = Font(name="Calibri", size=11, bold=True, color="0D263C")

    ws_resumo["A1"] = f"FAEG LOG — RELATÓRIO OPERACIONAL E FINANCEIRO ({fd.get('codigo_viagem', 'V1')})"
    ws_resumo["A1"].font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
    ws_resumo["A1"].fill = header_fill
    ws_resumo.merge_cells("A1:D1")

    receita = to_float(fd.get("valor_negociado_total"))
    total_desp = sum(to_float(d.get("valor_total")) for d in despesas)
    lucro = receita - total_desp
    km_real = max(0, to_int(fd.get("odometro_final")) - to_int(fd.get("odometro_inicial")))

    linhas_info = [
        ("Código da Viagem", fd.get("codigo_viagem", ""), "Status", fd.get("status_viagem", "")),
        ("Tipo de Viagem", fd.get("tipo_viagem", ""), "Tipo de Frete", fd.get("tipo_frete", "")),
        ("Motorista", motorista_nome, "Veículo / Placa", veiculo_txt),
        ("Cliente", cliente_nome, "Origem de Frete", fd.get("forma_contratacao", "")),
        ("Origem", fd.get("rota_origem", ""), "Destino", fd.get("rota_destino", "")),
        ("NF-e / Carga", fd.get("nfe_carga", ""), "CT-e / MDF-e", f"{fd.get('cte_numero', '')} / {fd.get('mdfe_numero', '')}"),
        ("KM Planejado", to_float(fd.get("km_rota_planejado")), "KM Real Rodado", km_real),
        ("Receita Negociada (R$)", receita, "Total Despesas (R$)", total_desp),
        ("Resultado Líquido (R$)", lucro, "Margem (%)", round((lucro / receita * 100), 2) if receita > 0 else 0.0),
    ]

    for idx, (k1, v1, k2, v2) in enumerate(linhas_info, start=3):
        ws_resumo.cell(row=idx, column=1, value=k1).font = bold_font
        ws_resumo.cell(row=idx, column=2, value=v1)
        ws_resumo.cell(row=idx, column=3, value=k2).font = bold_font
        ws_resumo.cell(row=idx, column=4, value=v2)
        if "Receita" in k1 or "Resultado" in k1:
            ws_resumo.cell(row=idx, column=2).number_format = "R$ #,##0.00"
        if "Despesas" in k2:
            ws_resumo.cell(row=idx, column=4).number_format = "R$ #,##0.00"

    ws_desp = wb.create_sheet(title="Despesas Detalhadas")
    colunas = ["Data", "Categoria", "Descrição", "Quantidade", "Valor Unitário (R$)", "Valor Total (R$)"]
    for c_idx, titulo in enumerate(colunas, start=1):
        cell = ws_desp.cell(row=1, column=c_idx, value=titulo)
        cell.fill = accent_fill if c_idx == 6 else header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for r_idx, d in enumerate(despesas, start=2):
        ws_desp.cell(row=r_idx, column=1, value=str(d.get("data_despesa", "")))
        ws_desp.cell(row=r_idx, column=2, value=d.get("tipo_despesa", ""))
        ws_desp.cell(row=r_idx, column=3, value=d.get("descricao_detalhe", ""))
        ws_desp.cell(row=r_idx, column=4, value=to_float(d.get("quantidade"), 1.0))
        c_unit = ws_desp.cell(row=r_idx, column=5, value=to_float(d.get("valor_unitario")))
        c_tot = ws_desp.cell(row=r_idx, column=6, value=to_float(d.get("valor_total")))
        c_unit.number_format = "R$ #,##0.00"
        c_tot.number_format = "R$ #,##0.00"

    for sheet in (ws_resumo, ws_desp):
        for col in sheet.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            sheet.column_dimensions[col[0].column_letter].width = max(max_len + 4, 16)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def gerar_pdf_nativo_viagem(fd: dict, despesas: list, cliente_nome: str, motorista_nome: str, veiculo_txt: str) -> bytes:
    """Gera relatório executivo em PDF nativo (Python puro) com cabeçalho institucional FAEG."""

    def esc(txt: str) -> str:
        s = str(txt or "-").encode("latin-1", "replace").decode("latin-1")
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    receita = to_float(fd.get("valor_negociado_total"))
    total_desp = sum(to_float(d.get("valor_total")) for d in despesas)
    lucro = receita - total_desp
    km_real = max(0, to_int(fd.get("odometro_final")) - to_int(fd.get("odometro_inicial")))
    custo_km = (total_desp / km_real) if km_real > 0 else 0.0

    ops = []
    # Cabeçalho Azul Estrutural (#0D263C -> 0.051 0.149 0.235)
    ops.append("0.051 0.149 0.235 rg 36 742 523 64 re f")
    # Faixa Laranja Energia (#F34D25 -> 0.953 0.302 0.145)
    ops.append("0.953 0.302 0.145 rg 36 738 523 4 re f")

    ops.append("BT /F2 16 Tf 1 1 1 rg 50 780 Td (FAEG — SOLUCOES EMPRESARIAIS E LOGISTICAS) Tj ET")
    ops.append(
        f"BT /F1 10 Tf 0.671 0.808 0.882 rg 50 760 Td (Relatorio Operacional e DRE — Viagem {esc(fd.get('codigo_viagem', 'V1'))} | Status: {esc(fd.get('status_viagem', ''))}) Tj ET"
    )

    y = 712
    ops.append("BT /F2 11 Tf 0.051 0.149 0.235 rg 40 712 Td (1. DADOS OPERACIONAIS DA VIAGEM) Tj ET")
    y -= 18

    linhas_op = [
        f"Codigo: {fd.get('codigo_viagem', 'V1')}   |   Tipo: {fd.get('tipo_viagem', '')} ({fd.get('tipo_frete', '')})",
        f"Cliente: {cliente_nome}",
        f"Motorista: {motorista_nome}   |   Veiculo: {veiculo_txt}",
        f"Origem: {fd.get('rota_origem', '-')}   ->   Destino: {fd.get('rota_destino', '-')}",
        f"Material: {fd.get('tipo_material', '-')}   |   Volumes: {fd.get('qtde_volumes', 0)}   |   Peso: {fd.get('peso_bruto_kg', 0)} kg",
        f"NF-e: {fd.get('nfe_carga', '-')}   |   CT-e: {fd.get('cte_numero', '-')}   |   MDF-e: {fd.get('mdfe_numero', '-')}",
        f"KM Planejado: {fd.get('km_rota_planejado', 0)} km   |   KM Real Rodado: {km_real} km",
    ]
    for linha in linhas_op:
        ops.append(f"BT /F1 9.5 Tf 0.15 0.18 0.22 rg 44 {y} Td ({esc(linha)}) Tj ET")
        y -= 15

    y -= 10
    ops.append(f"BT /F2 11 Tf 0.051 0.149 0.235 rg 40 {y} Td (2. RESUMO FINANCEIRO [DRE]) Tj ET")
    y -= 18
    linhas_dre = [
        f"Receita Negociada: {fmt_moeda(receita)}   |   Adiantamento: {fmt_moeda(fd.get('valor_adiantamento'))}   |   Saldo: {fmt_moeda(fd.get('valor_saldo'))}",
        f"Total de Despesas: {fmt_moeda(total_desp)}   |   Custo por KM: {fmt_moeda(custo_km)}",
        f"RESULTADO LIQUIDO DA VIAGEM: {fmt_moeda(lucro)}",
    ]
    for idx_d, linha in enumerate(linhas_dre):
        cor = "0.953 0.302 0.145 rg" if idx_d == 2 else "0.15 0.18 0.22 rg"
        fonte = "/F2 10.5 Tf" if idx_d == 2 else "/F1 9.5 Tf"
        ops.append(f"BT {fonte} {cor} 44 {y} Td ({esc(linha)}) Tj ET")
        y -= 16

    y -= 10
    ops.append(f"BT /F2 11 Tf 0.051 0.149 0.235 rg 40 {y} Td (3. DESPESAS LANCADAS NA VIAGEM) Tj ET")
    y -= 16
    if not despesas:
        ops.append(f"BT /F1 9.5 Tf 0.4 0.45 0.5 rg 44 {y} Td (Nenhuma despesa registrada para esta viagem.) Tj ET")
    else:
        for d in despesas[:22]:
            if y < 55:
                break
            txt_d = (
                f"- [{d.get('tipo_despesa', '')}] {d.get('descricao_detalhe', '') or 'Sem descricao'} "
                f"| Qtd: {to_float(d.get('quantidade'), 1.0):.2f} x {fmt_moeda(d.get('valor_unitario'))} = {fmt_moeda(d.get('valor_total'))}"
            )
            ops.append(f"BT /F1 9 Tf 0.15 0.18 0.22 rg 44 {y} Td ({esc(txt_d)}) Tj ET")
            y -= 14

    ops.append(
        f"BT /F1 8 Tf 0.45 0.5 0.55 rg 40 30 Td (Documento gerado automaticamente pelo sistema FAEG LOG em {datetime.now().strftime('%d/%m/%Y %H:%M')}) Tj ET"
    )

    stream_bytes = "\n".join(ops).encode("latin-1")
    compressed = zlib.compress(stream_bytes)

    objs = []
    objs.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
    objs.append(b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n")
    objs.append(
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >> endobj\n"
    )
    objs.append(b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n")
    objs.append(b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >> endobj\n")
    objs.append(
        f"6 0 obj << /Length {len(compressed)} /Filter /FlateDecode >> stream\n".encode("latin-1")
        + compressed
        + b"\nendstream endobj\n"
    )

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objs:
        offsets.append(len(pdf))
        pdf.extend(obj)

    xref_pos = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode("latin-1"))
    pdf.append(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode("latin-1"))

    pdf.extend(
        f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode("latin-1")
    )
    return bytes(pdf)


# ==============================================================================
# 6. NAVEGAÇÃO ENTRE ETAPAS (CALLBACK SEM ERRO DE ESTADO)
# ==============================================================================
def _mudar_aba_callback(nova_aba: str):
    st.session_state["menu_operacional_radio"] = nova_aba


def render_navegacao_rodape(idx_atual: int):
    st.markdown("<hr style='margin: 1.5rem 0 0.9rem 0; border-color: #CBD5E1;'>", unsafe_allow_html=True)
    col_prev, _, col_next = st.columns([2.2, 7.6, 2.2])
    if idx_atual > 0:
        col_prev.button(
            "← Etapa Anterior",
            key=f"btn_prev_{idx_atual}",
            use_container_width=True,
            on_click=_mudar_aba_callback,
            args=(MENU_ITENS[idx_atual - 1],),
        )
    if idx_atual < len(MENU_ITENS) - 1:
        col_next.button(
            "Próxima Etapa →",
            key=f"btn_next_{idx_atual}",
            use_container_width=True,
            on_click=_mudar_aba_callback,
            args=(MENU_ITENS[idx_atual + 1],),
        )


# ==============================================================================
# 7. BARRA LATERAL (IDENTIDADE FAEG + NAVEGAÇÃO + SALVAR)
# ==============================================================================
with st.sidebar:
    logo_b64 = carregar_logo_base64()
    if logo_b64:
        st.markdown(
            f"""
            <div class="sidebar-brand">
                <img src="data:image/png;base64,{logo_b64}" alt="FAEG Logo">
                <div class="sidebar-brand-text">
                    <span class="sidebar-brand-title">FAEG</span>
                    <span class="sidebar-brand-sub">Soluções Empresariais e Logísticas</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="sidebar-brand">
                <div class="sidebar-monogram">F</div>
                <div class="sidebar-brand-text">
                    <span class="sidebar-brand-title">FAEG</span>
                    <span class="sidebar-brand-sub">Soluções Empresariais e Logísticas</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    opcoes_vg_sidebar = [None] + [v["id"] for v in viagens_list]
    mapa_vg_sidebar = {None: f"✨ Nova Viagem ({st.session_state['form_data'].get('codigo_viagem', 'V1')})"}
    for v in viagens_list:
        mapa_vg_sidebar[v["id"]] = f"{v['codigo']} — {v['rota']}"

    id_atual_fd = st.session_state["form_data"].get("id_viagem")
    idx_sel_vg = opcoes_vg_sidebar.index(id_atual_fd) if id_atual_fd in opcoes_vg_sidebar else 0

    vg_escolhida = st.selectbox(
        "Viagem em Edição",
        options=opcoes_vg_sidebar,
        index=idx_sel_vg,
        format_func=lambda x: mapa_vg_sidebar.get(x, str(x)),
        key="viagem_ativa_selector",
    )

    if vg_escolhida != id_atual_fd:
        if vg_escolhida is None:
            iniciar_nova_viagem()
        else:
            carregar_viagem_para_estado(vg_escolhida)
        st.rerun()

    if st.button("➕ Nova Viagem", use_container_width=True, key="btn_nova_viagem_sidebar"):
        iniciar_nova_viagem()
        st.rerun()

    st.markdown("<div style='margin-top: 0.6rem;'></div>", unsafe_allow_html=True)

    aba_selecionada = st.radio(
        "Etapas da Operação",
        options=MENU_ITENS,
        key="menu_operacional_radio",
        label_visibility="collapsed",
    )

    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
    if st.button("💾 Salvar Viagem", type="primary", use_container_width=True, key="btn_salvar_viagem_sidebar"):
        salvar_viagem_no_banco()
        st.rerun()

# ==============================================================================
# 8. BARRA SUPERIOR EXECUTIVA (TOP CONTEXT BAR)
# ==============================================================================
fd = st.session_state["form_data"]
idx_aba = MENU_ITENS.index(aba_selecionada)

cliente_ativo_obj = next((c for c in clientes_list if c["id"] == fd.get("id_cliente")), None)
motorista_ativo_obj = next((m for m in motoristas_list if m["id"] == fd.get("id_motorista")), None)
veiculo_ativo_obj = next((v for v in veiculos_list if v["id"] == fd.get("id_veiculo")), None)

nome_cliente_ctx = cliente_ativo_obj["razao_social"] if cliente_ativo_obj else "Não selecionado"
orig_ctx = fd.get("rota_origem") or "Origem não definida"
dest_ctx = fd.get("rota_destino") or "Destino não definido"
rota_ctx = f"{orig_ctx} → {dest_ctx}"

st.markdown(
    f"""
    <div class="top-context-bar">
        <div class="ctx-group">
            <span class="ctx-label">Código da Viagem</span>
            <span class="ctx-value"><span class="badge-codigo">{fd.get('codigo_viagem', 'V1')}</span></span>
        </div>
        <div class="ctx-group">
            <span class="ctx-label">Status Operacional</span>
            <span class="ctx-value"><span class="badge-status">{fd.get('status_viagem', 'Planejada')}</span></span>
        </div>
        <div class="ctx-group">
            <span class="ctx-label">Cliente Contratante</span>
            <span class="ctx-value">{nome_cliente_ctx}</span>
        </div>
        <div class="ctx-group">
            <span class="ctx-label">Rota (Origem → Destino)</span>
            <span class="ctx-value">{rota_ctx}</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ==============================================================================
# ETAPA 1: FROTA FAEG (+ IMPORTAÇÃO DE PLANILHA RECOLHÍVEL)
# ==============================================================================
if idx_aba == 0:
    st.markdown(
        """
        <div class="etapa-header">
            <h2>🚚 1. Frota FAEG — Identificação da Viagem, Motorista e Veículo</h2>
            <p>Defina o código único sequencial (V1, V2...), a modalidade da operação e vincule motorista e veículo.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.markdown('<div class="secao-titulo">Identificação Operacional</div>', unsafe_allow_html=True)
        # Grade de 12 unidades: [3, 3, 3, 3]
        c1, c2, c3, c4 = st.columns([3, 3, 3, 3])
        fd["codigo_viagem"] = c1.text_input(
            "Código da Viagem (Editável)",
            value=fd.get("codigo_viagem", "V1"),
            placeholder="Ex.: V1, V2, V15...",
            key="inp_codigo_viagem",
        ).upper()
        fd["status_viagem"] = c2.selectbox(
            "Status Operacional",
            options=OPCOES_STATUS_VIAGEM,
            index=OPCOES_STATUS_VIAGEM.index(fd.get("status_viagem", "Planejada"))
            if fd.get("status_viagem") in OPCOES_STATUS_VIAGEM
            else 0,
            key="inp_status_viagem",
        )
        fd["tipo_viagem"] = c3.selectbox(
            "Tipo de Viagem",
            options=OPCOES_TIPO_VIAGEM,
            index=OPCOES_TIPO_VIAGEM.index(fd.get("tipo_viagem", "Individual"))
            if fd.get("tipo_viagem") in OPCOES_TIPO_VIAGEM
            else 0,
            key="inp_tipo_viagem",
        )
        fd["tipo_frete"] = c4.selectbox(
            "Tipo de Frete",
            options=OPCOES_TIPO_FRETE,
            index=OPCOES_TIPO_FRETE.index(fd.get("tipo_frete", "Dedicado"))
            if fd.get("tipo_frete") in OPCOES_TIPO_FRETE
            else 0,
            key="inp_tipo_frete",
        )

        st.markdown('<div class="secao-titulo">Dados do Motorista</div>', unsafe_allow_html=True)
        # Grade de 12 unidades: [6, 3, 3]
        m1, m2, m3 = st.columns([6, 3, 3])
        opcoes_mot = [None] + [m["id"] for m in motoristas_list]
        mapa_mot = {None: "Selecione o motorista..."}
        for m in motoristas_list:
            mapa_mot[m["id"]] = f"{m['nome']} ({m['vinculo']})"

        idx_mot = opcoes_mot.index(fd.get("id_motorista")) if fd.get("id_motorista") in opcoes_mot else 0
        mot_sel = m1.selectbox(
            "Nome do Motorista",
            options=opcoes_mot,
            index=idx_mot,
            format_func=lambda x: mapa_mot.get(x, ""),
            key="sel_motorista_etapa1",
        )
        fd["id_motorista"] = mot_sel
        mot_info = next((m for m in motoristas_list if m["id"] == mot_sel), None)

        m2.text_input(
            "CNH (Automático)",
            value=mot_info["cnh"] if mot_info else "",
            disabled=True,
            key=f"disp_cnh_{mot_sel}",
        )
        m3.text_input(
            "Categoria (Automático)",
            value=mot_info["categoria"] if mot_info else "",
            disabled=True,
            key=f"disp_cat_{mot_sel}",
        )

        st.markdown('<div class="secao-titulo">Dados do Veículo</div>', unsafe_allow_html=True)
        # Grade de 12 unidades: [6, 3, 3] — divisórias verticais alinhadas com a linha do Motorista
        v1, v2, v3 = st.columns([6, 3, 3])
        opcoes_vei = [None] + [v["id"] for v in veiculos_list]
        mapa_vei = {None: "Selecione o veículo..."}
        for v in veiculos_list:
            mapa_vei[v["id"]] = f"{v['descricao']} — {v['placa']}"

        idx_vei = opcoes_vei.index(fd.get("id_veiculo")) if fd.get("id_veiculo") in opcoes_vei else 0
        vei_sel = v1.selectbox(
            "Veículo / Carro",
            options=opcoes_vei,
            index=idx_vei,
            format_func=lambda x: mapa_vei.get(x, ""),
            key="sel_veiculo_etapa1",
        )
        fd["id_veiculo"] = vei_sel
        vei_info = next((v for v in veiculos_list if v["id"] == vei_sel), None)

        v2.text_input(
            "Placa (Automático)",
            value=vei_info["placa"] if vei_info else "",
            disabled=True,
            key=f"disp_placa_{vei_sel}",
        )
        v3.text_input(
            "Tipo de Veículo (Automático)",
            value=vei_info["tipo"] if vei_info else "",
            disabled=True,
            key=f"disp_tipo_vei_{vei_sel}",
        )

    # Importação de Planilha mantida na primeira tela em expander limpo para preservar o layout
    with st.expander("📥 Importar Planilha de Controle Operacional (.xlsx)", expanded=False):
        st.caption(
            "Carregue a planilha Excel da FAEG para importar viagens históricas em lote, gerar códigos sequenciais (V1, V2...) e conciliar receitas e despesas."
        )
        arquivo_xlsx = st.file_uploader(
            "Selecione o arquivo Excel (.xlsx)",
            type=["xlsx"],
            key="uploader_planilha_faeg",
        )
        if arquivo_xlsx is not None:
            conteudo_bytes = arquivo_xlsx.getvalue()
            try:
                abas = listar_abas_planilha(io.BytesIO(conteudo_bytes))
                col_aba, col_btn_prev = st.columns([6, 6])
                aba_plan = col_aba.selectbox(
                    "Aba da Planilha para Importar",
                    options=abas,
                    key="sel_aba_planilha_import",
                )
                registros_prev = extrair_registros_planilha(io.BytesIO(conteudo_bytes), aba_plan)
                if registros_prev:
                    df_prev = pd.DataFrame(registros_prev)
                    rec_plan = sum(
                        to_float(r.get("valor_negociado") or r.get("valor_total_recebido"))
                        for r in registros_prev
                    )
                    desp_plan = sum(to_float(r.get("total_despesas_planilha")) for r in registros_prev)
                    k1, k2, k3, k4 = st.columns([3, 3, 3, 3])
                    k1.metric("Viagens Detectadas", len(registros_prev))
                    k2.metric("Receita Planilha", fmt_moeda(rec_plan))
                    k3.metric("Despesas Planilha", fmt_moeda(desp_plan))
                    k4.metric("Resultado Planilha", fmt_moeda(rec_plan - desp_plan))

                    cols_exibir = [
                        c
                        for c in [
                            "id_planilha",
                            "data_frete",
                            "motorista",
                            "placa",
                            "cliente_empresa",
                            "rota_origem",
                            "rota_destino",
                            "valor_negociado",
                            "total_despesas_planilha",
                            "resultado_planilha",
                        ]
                        if c in df_prev.columns
                    ]
                    st.dataframe(df_prev[cols_exibir], use_container_width=True, hide_index=True)

                    if st.button(
                        "✅ Confirmar Importação para o Banco Neon",
                        type="primary",
                        key="btn_confirmar_import_planilha",
                    ):
                        db_imp = SessionLocal()
                        try:
                            sig = inspect.signature(importar_registros_para_banco)
                            if "nome_aba" in sig.parameters:
                                resumo_imp = importar_registros_para_banco(
                                    db_imp, registros_prev, nome_aba=aba_plan
                                )
                            else:
                                resumo_imp = importar_registros_para_banco(db_imp, registros_prev)

                            st.success(
                                f"Importação concluída: {resumo_imp.get('importados', 0)} viagens importadas "
                                f"({', '.join(resumo_imp.get('codigos_gerados', []))})."
                            )
                            c_r1, c_r2, c_r3 = st.columns([4, 4, 4])
                            c_r1.metric(
                                "Receita (Planilha vs Sistema)",
                                fmt_moeda(resumo_imp.get("receita_sistema")),
                                delta=fmt_moeda(
                                    to_float(resumo_imp.get("receita_sistema"))
                                    - to_float(resumo_imp.get("receita_planilha"))
                                ),
                            )
                            c_r2.metric(
                                "Despesas (Planilha vs Sistema)",
                                fmt_moeda(resumo_imp.get("despesa_sistema")),
                                delta=fmt_moeda(
                                    to_float(resumo_imp.get("despesa_sistema"))
                                    - to_float(resumo_imp.get("despesa_planilha"))
                                ),
                            )
                            c_r3.metric(
                                "Resultado Líquido Sistema",
                                fmt_moeda(resumo_imp.get("resultado_sistema")),
                            )
                            pendencias = resumo_imp.get("pendencias") or []
                            if pendencias:
                                with st.expander(f"⚠️ Pendências para completar depois ({len(pendencias)})"):
                                    for p in pendencias:
                                        st.write(f"• {p}")
                        except Exception as exc_imp:
                            db_imp.rollback()
                            st.error(f"Erro durante a importação: {exc_imp}")
                        finally:
                            db_imp.close()
                else:
                    st.info("Nenhum registro operacional válido encontrado na aba selecionada.")
            except Exception as exc_read:
                st.error(f"Não foi possível ler a planilha: {exc_read}")

    render_navegacao_rodape(idx_aba)

# ==============================================================================
# ETAPA 2: FRETE, ROTA (ORIGEM / DESTINO), CARGA E DOCUMENTOS FISCAIS
# ==============================================================================
elif idx_aba == 1:
    st.markdown(
        """
        <div class="etapa-header">
            <h2>📦 2. Frete, Rota (Origem e Destino) e Documentos Fiscais</h2>
            <p>Informe os dados do frete, cidades de origem e destino, especificações da carga e documentos obrigatórios.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.markdown('<div class="secao-titulo">Dados Gerais do Frete e Rota</div>', unsafe_allow_html=True)
        # Linha 1 (12 unidades): [2.5, 2.5, 4.5, 2.5]
        f1, f2, f3, f4 = st.columns([2.5, 2.5, 4.5, 2.5])
        fd["id_frete_externo"] = f1.text_input(
            "ID Frete Externo",
            value=fd.get("id_frete_externo", ""),
            placeholder="Ex.: F26-000001",
            key="inp_id_frete_ext",
        )
        fd["data_frete"] = f2.date_input(
            "Data do Frete",
            value=parse_date_safe(fd.get("data_frete")),
            format="DD/MM/YYYY",
            key="inp_data_frete",
        )
        ciclo_bloqueado = fd.get("tipo_viagem") != "Ciclo"
        if ciclo_bloqueado:
            fd["nome_operacao_ciclo"] = ""
        fd["nome_operacao_ciclo"] = f3.text_input(
            "Nº / Nome do Ciclo Operacional",
            value=fd.get("nome_operacao_ciclo", ""),
            placeholder="Disponível quando Tipo de Viagem = Ciclo",
            disabled=ciclo_bloqueado,
            key=f"inp_ciclo_nome_{ciclo_bloqueado}",
        )
        fd["km_rota_planejado"] = f4.number_input(
            "KM Planejado",
            min_value=0.0,
            step=1.0,
            value=to_float(fd.get("km_rota_planejado")),
            key="inp_km_planejado",
        )

        # Linha 2 (12 unidades): [6, 6] — Origem e Destino separados e alinhados
        r1, r2 = st.columns([6, 6])
        fd["rota_origem"] = r1.text_input(
            "Origem (Cidade / UF)",
            value=fd.get("rota_origem", ""),
            placeholder="Ex.: Guarulhos/SP",
            key="inp_rota_origem",
        )
        fd["rota_destino"] = r2.text_input(
            "Destino (Cidade / UF)",
            value=fd.get("rota_destino", ""),
            placeholder="Ex.: Curitiba/PR",
            key="inp_rota_destino",
        )

        st.markdown('<div class="secao-titulo">Especificações da Carga</div>', unsafe_allow_html=True)
        # Linha 3 (12 unidades): [5.5, 2, 2, 2.5]
        cg1, cg2, cg3, cg4 = st.columns([5.5, 2, 2, 2.5])
        fd["tipo_material"] = cg1.text_input(
            "Tipo de Material / Mercadoria",
            value=fd.get("tipo_material", ""),
            placeholder="Ex.: Peças automotivas, Pneus, Paletizado...",
            key="inp_tipo_material",
        )
        fd["qtde_volumes"] = cg2.number_input(
            "QT Volumes",
            min_value=0,
            step=1,
            value=to_int(fd.get("qtde_volumes")),
            key="inp_qtde_volumes",
        )
        fd["volume_m3"] = cg3.number_input(
            "Volume (m³)",
            min_value=0.0,
            step=0.1,
            value=to_float(fd.get("volume_m3")),
            key="inp_volume_m3",
        )
        fd["peso_bruto_kg"] = cg4.number_input(
            "Peso Bruto (KG)",
            min_value=0.0,
            step=10.0,
            value=to_float(fd.get("peso_bruto_kg")),
            key="inp_peso_bruto",
        )

        st.markdown('<div class="secao-titulo">Documentos Fiscais e Transporte</div>', unsafe_allow_html=True)
        # Linha 4 (12 unidades): [3, 3, 3, 3]
        d1, d2, d3, d4 = st.columns([3, 3, 3, 3])
        fd["nfe_carga"] = d1.text_input(
            "NF-e / Nota Fiscal",
            value=fd.get("nfe_carga", ""),
            placeholder="Nº da NF-e",
            key="inp_nfe_carga",
        )
        fd["cte_numero"] = d2.text_input(
            "CT-e",
            value=fd.get("cte_numero", ""),
            placeholder="Nº do CT-e",
            key="inp_cte_numero",
        )
        fd["mdfe_numero"] = d3.text_input(
            "MDF-e",
            value=fd.get("mdfe_numero", ""),
            placeholder="Nº do MDF-e",
            key="inp_mdfe_numero",
        )
        fd["ciot_numero"] = d4.text_input(
            "CIOT",
            value=fd.get("ciot_numero", ""),
            placeholder="Código CIOT",
            key="inp_ciot_numero",
        )

    render_navegacao_rodape(idx_aba)

# ==============================================================================
# ETAPA 3: CLIENTE CONTRATANTE
# ==============================================================================
elif idx_aba == 2:
    st.markdown(
        """
        <div class="etapa-header">
            <h2>🤝 3. Cliente Contratante</h2>
            <p>Selecione o cliente cadastrado para preencher automaticamente os dados comerciais e fiscais.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.markdown('<div class="secao-titulo">Identificação do Cliente</div>', unsafe_allow_html=True)
        # Linha 1 (12 unidades): [6, 3, 3]
        cl1, cl2, cl3 = st.columns([6, 3, 3])
        opcoes_cli = [None] + [c["id"] for c in clientes_list]
        mapa_cli = {None: "Selecione o cliente..."}
        for c in clientes_list:
            mapa_cli[c["id"]] = f"{c['razao_social']} ({c['cnpj_cpf']})"

        idx_cli = opcoes_cli.index(fd.get("id_cliente")) if fd.get("id_cliente") in opcoes_cli else 0
        cli_sel = cl1.selectbox(
            "Empresa Cliente",
            options=opcoes_cli,
            index=idx_cli,
            format_func=lambda x: mapa_cli.get(x, ""),
            key="sel_cliente_etapa3",
        )
        fd["id_cliente"] = cli_sel
        cli_info = next((c for c in clientes_list if c["id"] == cli_sel), None)

        cl2.text_input(
            "CNPJ / CPF (Automático)",
            value=cli_info["cnpj_cpf"] if cli_info else "",
            disabled=True,
            key=f"disp_cli_cnpj_{cli_sel}",
        )
        cl3.text_input(
            "Prazo Pagamento (Automático)",
            value=f"{cli_info['prazo']} dias" if cli_info else "",
            disabled=True,
            key=f"disp_cli_prazo_{cli_sel}",
        )

        # Linha 2 (12 unidades): [5, 3.5, 3.5]
        cl4, cl5, cl6 = st.columns([5, 3.5, 3.5])
        cl4.text_input(
            "Responsável Comercial (Automático)",
            value=cli_info["responsavel"] if cli_info else "",
            disabled=True,
            key=f"disp_cli_resp_{cli_sel}",
        )
        cl5.text_input(
            "Telefone / Contato (Automático)",
            value=cli_info["telefone"] if cli_info else "",
            disabled=True,
            key=f"disp_cli_tel_{cli_sel}",
        )
        cl6.text_input(
            "E-mail Financeiro (Automático)",
            value=cli_info["email"] if cli_info else "",
            disabled=True,
            key=f"disp_cli_email_{cli_sel}",
        )

        # Linha 3 (12 unidades): [2.5, 6.5, 3]
        cl7, cl8, cl9 = st.columns([2.5, 6.5, 3])
        cl7.text_input(
            "CEP (Automático)",
            value=cli_info["cep"] if cli_info else "",
            disabled=True,
            key=f"disp_cli_cep_{cli_sel}",
        )
        cl8.text_input(
            "Endereço Completo (Automático)",
            value=cli_info["endereco"] if cli_info else "",
            disabled=True,
            key=f"disp_cli_end_{cli_sel}",
        )
        cidade_uf_cli = (
            f"{cli_info['cidade']}/{cli_info['uf']}"
            if cli_info and (cli_info["cidade"] or cli_info["uf"])
            else ""
        )
        cl9.text_input(
            "Cidade / UF (Automático)",
            value=cidade_uf_cli,
            disabled=True,
            key=f"disp_cli_cid_{cli_sel}",
        )

    render_navegacao_rodape(idx_aba)

# ==============================================================================
# ETAPA 4: NEGOCIAÇÃO E RECEBIMENTOS
# ==============================================================================
elif idx_aba == 3:
    st.markdown(
        """
        <div class="etapa-header">
            <h2>💰 4. Negociação e Recebimentos</h2>
            <p>Configure a origem do frete, valores negociados e o cronograma de adiantamento e saldo.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.markdown('<div class="secao-titulo">Acordo Comercial</div>', unsafe_allow_html=True)
        # Linha 1 (12 unidades): [5, 3.5, 3.5]
        n1, n2, n3 = st.columns([5, 3.5, 3.5])
        fd["forma_contratacao"] = n1.selectbox(
            "Origem de Frete",
            options=OPCOES_ORIGEM_FRETE,
            index=OPCOES_ORIGEM_FRETE.index(fd.get("forma_contratacao", "Aplicativo de Fretes"))
            if fd.get("forma_contratacao") in OPCOES_ORIGEM_FRETE
            else 0,
            key="sel_origem_frete",
        )
        fd["valor_divulgado"] = n2.number_input(
            "Valor Divulgado (R$)",
            min_value=0.0,
            step=50.0,
            value=to_float(fd.get("valor_divulgado")),
            key="inp_val_divulgado",
        )
        fd["valor_negociado_total"] = n3.number_input(
            "Valor Negociado Total (R$)",
            min_value=0.0,
            step=50.0,
            value=to_float(fd.get("valor_negociado_total")),
            key="inp_val_negociado",
        )

        st.markdown('<div class="secao-titulo">Parcelamento: Adiantamento e Saldo</div>', unsafe_allow_html=True)
        # Linha 2 (12 unidades): [2.5, 3.5, 6]
        ad1, ad2, ad3 = st.columns([2.5, 3.5, 6])
        fd["perc_adiantamento"] = ad1.number_input(
            "Adiantamento (%)",
            min_value=0.0,
            max_value=100.0,
            step=5.0,
            value=to_float(fd.get("perc_adiantamento"), 70.0),
            key="inp_perc_adiant",
        )
        fd["data_prevista_adiantamento"] = ad2.date_input(
            "Data Prevista Adiantamento",
            value=parse_date_safe(fd.get("data_prevista_adiantamento")),
            format="DD/MM/YYYY",
            key="inp_data_adiant",
        )
        fd["valor_adiantamento"] = ad3.number_input(
            "Valor Adiantamento (R$)",
            min_value=0.0,
            step=50.0,
            value=to_float(fd.get("valor_adiantamento")),
            key="inp_val_adiant",
        )

        # Linha 3 (12 unidades): [2.5, 3.5, 6] — alinhamento idêntico à linha do Adiantamento
        sd1, sd2, sd3 = st.columns([2.5, 3.5, 6])
        fd["perc_saldo"] = sd1.number_input(
            "Saldo (%)",
            min_value=0.0,
            max_value=100.0,
            step=5.0,
            value=to_float(fd.get("perc_saldo"), 30.0),
            key="inp_perc_saldo",
        )
        fd["data_prevista_saldo"] = sd2.date_input(
            "Data Prevista Saldo",
            value=parse_date_safe(fd.get("data_prevista_saldo")),
            format="DD/MM/YYYY",
            key="inp_data_saldo",
        )
        fd["valor_saldo"] = sd3.number_input(
            "Valor Saldo (R$)",
            min_value=0.0,
            step=50.0,
            value=to_float(fd.get("valor_saldo")),
            key="inp_val_saldo",
        )

        col_calc, col_tot = st.columns([4, 8])
        if col_calc.button("🧮 Calcular Valores pelos %", key="btn_calc_parcelas"):
            val_neg = to_float(fd.get("valor_negociado_total"))
            p_ad = to_float(fd.get("perc_adiantamento"))
            p_sd = round(100.0 - p_ad, 2)
            fd["perc_saldo"] = p_sd
            fd["valor_adiantamento"] = round(val_neg * (p_ad / 100.0), 2)
            fd["valor_saldo"] = round(val_neg - fd["valor_adiantamento"], 2)
            st.rerun()

        total_rec_prev = to_float(fd.get("valor_adiantamento")) + to_float(fd.get("valor_saldo"))
        col_tot.info(
            f"**Total Programado (Adiantamento + Saldo):** {fmt_moeda(total_rec_prev)} | "
            f"**Valor Negociado:** {fmt_moeda(fd.get('valor_negociado_total'))}"
        )

    render_navegacao_rodape(idx_aba)

# ==============================================================================
# ETAPA 5: COLETA (ORIGEM)
# ==============================================================================
elif idx_aba == 4:
    st.markdown(
        """
        <div class="etapa-header">
            <h2>📍 5. Coleta (Origem)</h2>
            <p>Selecione o ponto de coleta cadastrado e registre a data e os horários planejado e real.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.markdown('<div class="secao-titulo">Local e Endereço de Coleta</div>', unsafe_allow_html=True)
        # Linha 1 (12 unidades): [5.5, 2, 3.3, 1.2]
        co1, co2, co3, co4 = st.columns([5.5, 2, 3.3, 1.2])
        opcoes_loc = [None] + [l["id"] for l in locais_list]
        mapa_loc = {None: "Selecione o local de coleta..."}
        for l in locais_list:
            mapa_loc[l["id"]] = f"{l['nome']} ({l['cidade']}/{l['uf']})"

        idx_col = (
            opcoes_loc.index(fd.get("id_local_coleta")) if fd.get("id_local_coleta") in opcoes_loc else 0
        )
        col_sel = co1.selectbox(
            "Base / Empresa de Coleta",
            options=opcoes_loc,
            index=idx_col,
            format_func=lambda x: mapa_loc.get(x, ""),
            key="sel_local_coleta",
        )
        fd["id_local_coleta"] = col_sel
        loc_col_info = next((l for l in locais_list if l["id"] == col_sel), None)

        co2.text_input(
            "CEP (Automático)",
            value=loc_col_info["cep"] if loc_col_info else "",
            disabled=True,
            key=f"disp_col_cep_{col_sel}",
        )
        co3.text_input(
            "Cidade (Automático)",
            value=loc_col_info["cidade"] if loc_col_info else "",
            disabled=True,
            key=f"disp_col_cid_{col_sel}",
        )
        co4.text_input(
            "UF",
            value=loc_col_info["uf"] if loc_col_info else "",
            disabled=True,
            key=f"disp_col_uf_{col_sel}",
        )

        # Linha 2 (12 unidades): [8.5, 3.5]
        co5, co6 = st.columns([8.5, 3.5])
        co5.text_input(
            "Endereço Completo de Coleta (Automático)",
            value=loc_col_info["endereco"] if loc_col_info else "",
            disabled=True,
            key=f"disp_col_end_{col_sel}",
        )
        co6.text_input(
            "Contato / Restrição (Automático)",
            value=(
                f"{loc_col_info['contato']} {loc_col_info['restricao']}".strip()
                if loc_col_info
                else ""
            ),
            disabled=True,
            key=f"disp_col_rest_{col_sel}",
        )

        st.markdown('<div class="secao-titulo">Agenda e Horários da Coleta</div>', unsafe_allow_html=True)
        # Linha 3 (12 unidades): [5.5, 3.25, 3.25] — divisória após Data alinha com Base/Empresa acima
        hc1, hc2, hc3 = st.columns([5.5, 3.25, 3.25])
        fd["data_coleta"] = hc1.date_input(
            "Data da Coleta",
            value=parse_date_safe(fd.get("data_coleta")),
            format="DD/MM/YYYY",
            key="inp_data_coleta",
        )
        fd["hora_planejada_coleta"] = hc2.time_input(
            "Horário Planejado",
            value=parse_time_safe(fd.get("hora_planejada_coleta"), time(8, 0)),
            key="inp_hora_plan_col",
        )
        fd["hora_real_coleta"] = hc3.time_input(
            "Horário Real Coletado",
            value=parse_time_safe(fd.get("hora_real_coleta"), time(8, 0)),
            key="inp_hora_real_col",
        )

    render_navegacao_rodape(idx_aba)

# ==============================================================================
# ETAPA 6: ENTREGA (DESTINO)
# ==============================================================================
elif idx_aba == 5:
    st.markdown(
        """
        <div class="etapa-header">
            <h2>🏁 6. Entrega (Destino)</h2>
            <p>Selecione o ponto de entrega cadastrado e registre a data e os horários planejado e real.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.markdown('<div class="secao-titulo">Local e Endereço de Entrega</div>', unsafe_allow_html=True)
        # Linha 1 (12 unidades): [5.5, 2, 3.3, 1.2]
        en1, en2, en3, en4 = st.columns([5.5, 2, 3.3, 1.2])
        opcoes_loc_ent = [None] + [l["id"] for l in locais_list]
        mapa_loc_ent = {None: "Selecione o local de entrega..."}
        for l in locais_list:
            mapa_loc_ent[l["id"]] = f"{l['nome']} ({l['cidade']}/{l['uf']})"

        idx_ent = (
            opcoes_loc_ent.index(fd.get("id_local_entrega"))
            if fd.get("id_local_entrega") in opcoes_loc_ent
            else 0
        )
        ent_sel = en1.selectbox(
            "Base / Empresa de Entrega",
            options=opcoes_loc_ent,
            index=idx_ent,
            format_func=lambda x: mapa_loc_ent.get(x, ""),
            key="sel_local_entrega",
        )
        fd["id_local_entrega"] = ent_sel
        loc_ent_info = next((l for l in locais_list if l["id"] == ent_sel), None)

        en2.text_input(
            "CEP (Automático)",
            value=loc_ent_info["cep"] if loc_ent_info else "",
            disabled=True,
            key=f"disp_ent_cep_{ent_sel}",
        )
        en3.text_input(
            "Cidade (Automático)",
            value=loc_ent_info["cidade"] if loc_ent_info else "",
            disabled=True,
            key=f"disp_ent_cid_{ent_sel}",
        )
        en4.text_input(
            "UF",
            value=loc_ent_info["uf"] if loc_ent_info else "",
            disabled=True,
            key=f"disp_ent_uf_{ent_sel}",
        )

        # Linha 2 (12 unidades): [8.5, 3.5]
        en5, en6 = st.columns([8.5, 3.5])
        en5.text_input(
            "Endereço Completo de Entrega (Automático)",
            value=loc_ent_info["endereco"] if loc_ent_info else "",
            disabled=True,
            key=f"disp_ent_end_{ent_sel}",
        )
        en6.text_input(
            "Contato / Restrição (Automático)",
            value=(
                f"{loc_ent_info['contato']} {loc_ent_info['restricao']}".strip()
                if loc_ent_info
                else ""
            ),
            disabled=True,
            key=f"disp_ent_rest_{ent_sel}",
        )

        st.markdown('<div class="secao-titulo">Agenda e Horários da Entrega</div>', unsafe_allow_html=True)
        # Linha 3 (12 unidades): [5.5, 3.25, 3.25]
        he1, he2, he3 = st.columns([5.5, 3.25, 3.25])
        fd["data_entrega"] = he1.date_input(
            "Data da Entrega",
            value=parse_date_safe(fd.get("data_entrega")),
            format="DD/MM/YYYY",
            key="inp_data_entrega",
        )
        fd["hora_planejada_entrega"] = he2.time_input(
            "Horário Planejado",
            value=parse_time_safe(fd.get("hora_planejada_entrega"), time(17, 0)),
            key="inp_hora_plan_ent",
        )
        fd["hora_real_entrega"] = he3.time_input(
            "Horário Real Entregue",
            value=parse_time_safe(fd.get("hora_real_entrega"), time(17, 0)),
            key="inp_hora_real_ent",
        )

    render_navegacao_rodape(idx_aba)

# ==============================================================================
# ETAPA 7: DESPESAS DE VIAGEM (UNIFICADA + EDIÇÃO)
# ==============================================================================
elif idx_aba == 6:
    st.markdown(
        """
        <div class="etapa-header">
            <h2>🧾 7. Despesas de Viagem (Abastecimentos, Pedágios e Custos)</h2>
            <p>Centralize abastecimentos (Diesel/ARLA), pedágios, alimentação e manutenção com cálculo automático.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    edit_idx = st.session_state.get("despesa_edit_idx")
    item_edit = (
        st.session_state["despesas_lista"][edit_idx]
        if edit_idx is not None and 0 <= edit_idx < len(st.session_state["despesas_lista"])
        else None
    )

    with st.container(border=True):
        st.markdown(
            f'<div class="secao-titulo">{"✏️ Editar Despesa Selecionada" if item_edit else "➕ Lançar Nova Despesa"}</div>',
            unsafe_allow_html=True,
        )
        # Linha 1 (12 unidades): [3.5, 4, 2.5, 2]
        dp1, dp2, dp3, dp4 = st.columns([3.5, 4, 2.5, 2])
        tipo_padrao = item_edit["tipo_despesa"] if item_edit else OPCOES_TIPO_DESPESA[0]
        tipo_desp = dp1.selectbox(
            "Categoria da Despesa",
            options=OPCOES_TIPO_DESPESA,
            index=OPCOES_TIPO_DESPESA.index(tipo_padrao) if tipo_padrao in OPCOES_TIPO_DESPESA else 0,
            key=f"inp_desp_tipo_{edit_idx}",
        )

        opcoes_forn = [None] + [f["id"] for f in fornecedores_list]
        mapa_forn = {None: "Avulso / Sem fornecedor vinculado"}
        for f in fornecedores_list:
            mapa_forn[f["id"]] = f"{f['nome']} ({f['categoria']})"
        forn_padrao = item_edit.get("id_fornecedor") if item_edit else None
        forn_sel = dp2.selectbox(
            "Fornecedor / Posto (Opcional)",
            options=opcoes_forn,
            index=opcoes_forn.index(forn_padrao) if forn_padrao in opcoes_forn else 0,
            format_func=lambda x: mapa_forn.get(x, ""),
            key=f"inp_desp_forn_{edit_idx}",
        )

        data_desp = dp3.date_input(
            "Data da Despesa",
            value=parse_date_safe(item_edit["data_despesa"] if item_edit else date.today()),
            format="DD/MM/YYYY",
            key=f"inp_desp_data_{edit_idx}",
        )

        qtd_desp = dp4.number_input(
            "Quantidade / Litros",
            min_value=0.01,
            step=1.0,
            value=to_float(item_edit["quantidade"] if item_edit else 1.0, 1.0),
            key=f"inp_desp_qtd_{edit_idx}",
        )

        # Linha 2 (12 unidades): [6, 3, 3]
        dp5, dp6, dp7 = st.columns([6, 3, 3])
        desc_desp = dp5.text_input(
            "Descrição / Detalhes (Posto, KM, Local)",
            value=item_edit["descricao_detalhe"] if item_edit else "",
            placeholder="Ex.: Posto Graal KM 210 — 120L Diesel S10",
            key=f"inp_desp_desc_{edit_idx}",
        )
        v_unit_desp = dp6.number_input(
            "Valor Unitário (R$)",
            min_value=0.0,
            step=1.0,
            value=to_float(item_edit["valor_unitario"] if item_edit else 0.0),
            key=f"inp_desp_vunit_{edit_idx}",
        )
        v_total_calc = round(qtd_desp * v_unit_desp, 2)
        dp7.text_input(
            "Valor Total Calculado",
            value=fmt_moeda(v_total_calc),
            disabled=True,
            key=f"disp_desp_vtot_{edit_idx}_{qtd_desp}_{v_unit_desp}",
        )

        b_add, b_cancel, _ = st.columns([3, 2.5, 6.5])
        label_btn_desp = "💾 Atualizar Despesa" if item_edit else "➕ Adicionar Despesa"
        if b_add.button(label_btn_desp, type="primary", use_container_width=True, key="btn_salvar_despesa"):
            novo_registro = {
                "id_despesa": item_edit.get("id_despesa") if item_edit else None,
                "id_fornecedor": forn_sel,
                "tipo_despesa": tipo_desp,
                "descricao_detalhe": desc_desp.strip(),
                "quantidade": qtd_desp,
                "valor_unitario": v_unit_desp,
                "valor_total": v_total_calc,
                "data_despesa": data_desp,
            }
            if item_edit is not None:
                st.session_state["despesas_lista"][edit_idx] = novo_registro
                st.session_state["despesa_edit_idx"] = None
                st.toast("Despesa atualizada!", icon="✏️")
            else:
                st.session_state["despesas_lista"].append(novo_registro)
                st.toast("Despesa adicionada à viagem!", icon="➕")
            st.rerun()

        if item_edit is not None:
            if b_cancel.button("Cancelar Edição", use_container_width=True, key="btn_cancelar_edit_desp"):
                st.session_state["despesa_edit_idx"] = None
                st.rerun()

    # Listagem das despesas lançadas
    with st.container(border=True):
        st.markdown('<div class="secao-titulo">Despesas Lançadas nesta Viagem</div>', unsafe_allow_html=True)
        lista_d = st.session_state["despesas_lista"]
        if not lista_d:
            st.info("Nenhuma despesa lançada nesta viagem até o momento.")
        else:
            for i, d in enumerate(lista_d):
                col_t, col_desc, col_val, col_ed, col_del = st.columns([2.8, 4.7, 2.5, 1, 1])
                col_t.markdown(f"**{d['tipo_despesa']}**\n\n`{d['data_despesa']}`")
                col_desc.markdown(
                    f"{d['descricao_detalhe'] or 'Sem descrição'}\n\n"
                    f"Qtd: `{d['quantidade']:.2f}` × `{fmt_moeda(d['valor_unitario'])}`"
                )
                col_val.markdown(f"**{fmt_moeda(d['valor_total'])}**")
                if col_ed.button("✏️", key=f"ed_desp_{i}", help="Editar despesa"):
                    st.session_state["despesa_edit_idx"] = i
                    st.rerun()
                if col_del.button("🗑️", key=f"del_desp_{i}", help="Remover despesa"):
                    st.session_state["despesas_lista"].pop(i)
                    if st.session_state["despesa_edit_idx"] == i:
                        st.session_state["despesa_edit_idx"] = None
                    st.rerun()
                st.markdown("<hr style='margin: 0.35rem 0; border-color: #E2E8F0;'>", unsafe_allow_html=True)

            total_d = sum(to_float(x["valor_total"]) for x in lista_d)
            st.markdown(
                f"<div style='text-align:right; font-size:1.1rem; font-weight:800; color:#F34D25;'>"
                f"TOTAL DE DESPESAS: {fmt_moeda(total_d)}</div>",
                unsafe_allow_html=True,
            )

    render_navegacao_rodape(idx_aba)

# ==============================================================================
# ETAPA 8: FECHAMENTO FINAL E DRE DA VIAGEM
# ==============================================================================
elif idx_aba == 7:
    st.markdown(
        """
        <div class="etapa-header">
            <h2>📊 8. Fechamento Final e DRE da Viagem</h2>
            <p>Confira a quilometragem real rodada, registre observações finais e valide o resultado líquido.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.markdown('<div class="secao-titulo">Auditoria de Odômetro e Observações</div>', unsafe_allow_html=True)
        # Linha 1 (12 unidades): [4, 4, 4]
        o1, o2, o3 = st.columns([4, 4, 4])
        fd["odometro_inicial"] = o1.number_input(
            "Odômetro Inicial (KM)",
            min_value=0,
            step=1,
            value=to_int(fd.get("odometro_inicial")),
            key="inp_odo_ini",
        )
        fd["odometro_final"] = o2.number_input(
            "Odômetro Final (KM)",
            min_value=0,
            step=1,
            value=to_int(fd.get("odometro_final")),
            key="inp_odo_fim",
        )
        km_real_calc = (
            max(0, to_int(fd["odometro_final"]) - to_int(fd["odometro_inicial"]))
            if to_int(fd["odometro_final"]) >= to_int(fd["odometro_inicial"])
            else 0
        )
        o3.text_input(
            "KM Real Rodado (Automático)",
            value=f"{km_real_calc} km",
            disabled=True,
            key=f"disp_km_real_{km_real_calc}",
        )

        fd["observacao_geral"] = st.text_area(
            "Observação Geral da Viagem",
            value=fd.get("observacao_geral", ""),
            placeholder="Anote ocorrências de rota, atrasos, comprovantes ou observações do cliente...",
            height=90,
            key="inp_obs_geral",
        )

    receita_dre = to_float(fd.get("valor_negociado_total"))
    despesas_dre = sum(to_float(d.get("valor_total")) for d in st.session_state["despesas_lista"])
    resultado_dre = receita_dre - despesas_dre
    custo_km_dre = (despesas_dre / km_real_calc) if km_real_calc > 0 else 0.0

    k1, k2, k3, k4 = st.columns([3, 3, 3, 3])
    k1.markdown(
        f'<div class="kpi-card"><div class="kpi-title">Receita Negociada</div><div class="kpi-num">{fmt_moeda(receita_dre)}</div></div>',
        unsafe_allow_html=True,
    )
    k2.markdown(
        f'<div class="kpi-card accent"><div class="kpi-title">Total de Despesas</div><div class="kpi-num" style="color:#F34D25;">{fmt_moeda(despesas_dre)}</div></div>',
        unsafe_allow_html=True,
    )
    cor_res = "#0D263C" if resultado_dre >= 0 else "#F34D25"
    k3.markdown(
        f'<div class="kpi-card info"><div class="kpi-title">Resultado Líquido</div><div class="kpi-num" style="color:{cor_res};">{fmt_moeda(resultado_dre)}</div></div>',
        unsafe_allow_html=True,
    )
    k4.markdown(
        f'<div class="kpi-card"><div class="kpi-title">Custo por KM</div><div class="kpi-num">{fmt_moeda(custo_km_dre)}</div></div>',
        unsafe_allow_html=True,
    )

    render_navegacao_rodape(idx_aba)

# ==============================================================================
# ETAPA 9: RELATÓRIOS, INDICADORES E EXPORTAÇÃO (EXCEL E PDF)
# ==============================================================================
elif idx_aba == 8:
    st.markdown(
        """
        <div class="etapa-header">
            <h2>📈 9. Relatórios Gerenciais e Exportação (Excel / PDF)</h2>
            <p>Visualize a distribuição de custos da viagem ativa e exporte o fechamento completo em Excel ou PDF.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    mot_nome = motorista_ativo_obj["nome"] if motorista_ativo_obj else "Não informado"
    vei_txt = (
        f"{veiculo_ativo_obj['descricao']} ({veiculo_ativo_obj['placa']})"
        if veiculo_ativo_obj
        else "Não informado"
    )

    excel_bytes = gerar_excel_viagem(
        fd, st.session_state["despesas_lista"], nome_cliente_ctx, mot_nome, vei_txt
    )
    pdf_bytes = gerar_pdf_nativo_viagem(
        fd, st.session_state["despesas_lista"], nome_cliente_ctx, mot_nome, vei_txt
    )

    _, col_xl, col_pdf = st.columns([7, 2.5, 2.5])
    col_xl.download_button(
        label="📥 Baixar Excel (.xlsx)",
        data=excel_bytes,
        file_name=f"FAEG_{fd.get('codigo_viagem', 'V1')}_Relatorio.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        key="btn_dl_excel",
    )
    col_pdf.download_button(
        label="📄 Baixar PDF (.pdf)",
        data=pdf_bytes,
        file_name=f"FAEG_{fd.get('codigo_viagem', 'V1')}_Relatorio.pdf",
        mime="application/pdf",
        use_container_width=True,
        key="btn_dl_pdf",
    )

    g1, g2 = st.columns([6.5, 5.5])
    with g1:
        with st.container(border=True):
            st.markdown('<div class="secao-titulo">Distribuição de Despesas por Categoria</div>', unsafe_allow_html=True)
            lista_d = st.session_state["despesas_lista"]
            if lista_d:
                df_g = pd.DataFrame(lista_d)
                agrupado = df_g.groupby("tipo_despesa")["valor_total"].sum()
                st.bar_chart(agrupado, color="#0D263C")
            else:
                st.info("Adicione despesas na Etapa 7 para visualizar o gráfico de distribuição.")

    with g2:
        with st.container(border=True):
            st.markdown('<div class="secao-titulo">Indicadores de Desempenho (KPIs)</div>', unsafe_allow_html=True)
            receita_kpi = to_float(fd.get("valor_negociado_total"))
            desp_kpi = sum(to_float(d.get("valor_total")) for d in st.session_state["despesas_lista"])
            lucro_kpi = receita_kpi - desp_kpi
            margem_kpi = (lucro_kpi / receita_kpi * 100.0) if receita_kpi > 0 else 0.0
            km_kpi = max(0, to_int(fd.get("odometro_final")) - to_int(fd.get("odometro_inicial")))
            custo_km_kpi = (desp_kpi / km_kpi) if km_kpi > 0 else 0.0

            st.metric("Receita Total Negociada", fmt_moeda(receita_kpi))
            st.metric("Lucro Líquido da Operação", fmt_moeda(lucro_kpi), delta=f"{margem_kpi:.1f}% de margem")
            st.metric("Custo Operacional por KM", fmt_moeda(custo_km_kpi))

    render_navegacao_rodape(idx_aba)

# ==============================================================================
# ETAPA 10: CADASTROS GERAIS (MASTER DATA COM EDIÇÃO E EXCLUSÃO)
# ==============================================================================
elif idx_aba == 9:
    st.markdown(
        """
        <div class="etapa-header">
            <h2>🗂️ 10. Cadastros Gerais (Master Data)</h2>
            <p>Gerencie motoristas, veículos, clientes, locais de coleta/entrega e fornecedores no banco Neon.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_m, tab_v, tab_c, tab_l, tab_f = st.tabs(
        ["👤 Motoristas", "🚛 Veículos", "🏢 Clientes", "📍 Locais", "⛽ Fornecedores"]
    )

    # --- 10.1 MOTORISTAS ---
    with tab_m:
        edit_mot_id = st.session_state.get("edit_mot_id")
        mot_ed = next((m for m in motoristas_list if m["id"] == edit_mot_id), None)
        with st.container(border=True):
            st.markdown(
                f'<div class="secao-titulo">{"✏️ Editar Motorista" if mot_ed else "➕ Novo Motorista"}</div>',
                unsafe_allow_html=True,
            )
            a1, a2, a3 = st.columns([6, 3, 3])
            m_nome = a1.text_input("Nome Completo", value=mot_ed["nome"] if mot_ed else "", key=f"cm_nome_{edit_mot_id}")
            m_cpf = a2.text_input("CPF", value=mot_ed["cpf"] if mot_ed else "", key=f"cm_cpf_{edit_mot_id}")
            m_tel = a3.text_input("Telefone", value=mot_ed["telefone"] if mot_ed else "", key=f"cm_tel_{edit_mot_id}")

            a4, a5, a6 = st.columns([4, 4, 4])
            m_cnh = a4.text_input("Número CNH", value=mot_ed["cnh"] if mot_ed else "", key=f"cm_cnh_{edit_mot_id}")
            m_cat = a5.text_input("Categoria CNH", value=mot_ed["categoria"] if mot_ed else "E", key=f"cm_cat_{edit_mot_id}").upper()
            vinculos = ["Próprio", "Agregado", "Terceiro"]
            m_vinc = a6.selectbox(
                "Vínculo",
                options=vinculos,
                index=vinculos.index(mot_ed["vinculo"]) if mot_ed and mot_ed["vinculo"] in vinculos else 0,
                key=f"cm_vinc_{edit_mot_id}",
            )

            bm1, bm2, _ = st.columns([3, 2.5, 6.5])
            if bm1.button("💾 Salvar Motorista", type="primary", use_container_width=True, key="btn_save_mot"):
                if not m_nome.strip() or not m_cpf.strip() or not m_cnh.strip():
                    st.error("Preencha Nome, CPF e CNH.")
                else:
                    db = SessionLocal()
                    try:
                        obj = db.query(Motorista).filter(Motorista.id_motorista == edit_mot_id).first() if edit_mot_id else Motorista()
                        if not edit_mot_id:
                            db.add(obj)
                        obj.nome_completo = m_nome.strip()
                        obj.cpf = m_cpf.strip()
                        obj.telefone_contato = m_tel.strip()
                        obj.cnh_numero = m_cnh.strip()
                        obj.cnh_categoria = m_cat.strip()
                        obj.vinculo = m_vinc
                        db.commit()
                        st.session_state["edit_mot_id"] = None
                        st.toast("Motorista salvo com sucesso!", icon="✅")
                        st.rerun()
                    except Exception as e:
                        db.rollback()
                        st.error(f"Erro ao salvar motorista: {e}")
                    finally:
                        db.close()

            if mot_ed and bm2.button("Cancelar", use_container_width=True, key="btn_canc_mot"):
                st.session_state["edit_mot_id"] = None
                st.rerun()

        with st.container(border=True):
            for m in motoristas_list:
                r1, r2, r3, r4 = st.columns([5, 3, 2, 2])
                r1.markdown(f"**{m['nome']}** ({m['vinculo']})")
                r2.markdown(f"CPF: `{m['cpf']}` | CNH: `{m['cnh']}` ({m['categoria']})")
                if r3.button("✏️", key=f"ed_m_{m['id']}"):
                    st.session_state["edit_mot_id"] = m["id"]
                    st.rerun()
                if r4.button("✕", key=f"del_m_{m['id']}"):
                    db = SessionLocal()
                    try:
                        db.query(Motorista).filter(Motorista.id_motorista == m["id"]).delete()
                        db.commit()
                        st.rerun()
                    except Exception as e:
                        db.rollback()
                        st.error(f"Não foi possível remover (possui viagens vinculadas): {e}")
                    finally:
                        db.close()

    # --- 10.2 VEÍCULOS ---
    with tab_v:
        edit_vei_id = st.session_state.get("edit_vei_id")
        vei_ed = next((v for v in veiculos_list if v["id"] == edit_vei_id), None)
        with st.container(border=True):
            st.markdown(
                f'<div class="secao-titulo">{"✏️ Editar Veículo" if vei_ed else "➕ Novo Veículo"}</div>',
                unsafe_allow_html=True,
            )
            v_c1, v_c2, v_c3 = st.columns([6, 3, 3])
            v_desc = v_c1.text_input("Descrição / Modelo", value=vei_ed["descricao"] if vei_ed else "", key=f"cv_desc_{edit_vei_id}")
            v_placa = v_c2.text_input("Placa", value=vei_ed["placa"] if vei_ed else "", key=f"cv_placa_{edit_vei_id}").upper()
            v_tipo = v_c3.text_input("Tipo (Truck, Toco, Van...)", value=vei_ed["tipo"] if vei_ed else "", key=f"cv_tipo_{edit_vei_id}")

            v_c4, v_c5, v_c6 = st.columns([4, 4, 4])
            v_ren = v_c4.text_input("RENAVAM", value=vei_ed["renavam"] if vei_ed else "", key=f"cv_ren_{edit_vei_id}")
            v_kg = v_c5.number_input("Capacidade (KG)", min_value=0.0, step=100.0, value=to_float(vei_ed["cap_kg"] if vei_ed else 0.0), key=f"cv_kg_{edit_vei_id}")
            v_m3 = v_c6.number_input("Capacidade (m³)", min_value=0.0, step=1.0, value=to_float(vei_ed["cap_m3"] if vei_ed else 0.0), key=f"cv_m3_{edit_vei_id}")

            bv1, bv2, _ = st.columns([3, 2.5, 6.5])
            if bv1.button("💾 Salvar Veículo", type="primary", use_container_width=True, key="btn_save_vei"):
                if not v_desc.strip() or not v_placa.strip():
                    st.error("Preencha Descrição e Placa.")
                else:
                    db = SessionLocal()
                    try:
                        obj = db.query(Veiculo).filter(Veiculo.id_veiculo == edit_vei_id).first() if edit_vei_id else Veiculo()
                        if not edit_vei_id:
                            db.add(obj)
                        obj.descricao_marca = v_desc.strip()
                        obj.placa = v_placa.strip()
                        obj.tipo_veiculo = v_tipo.strip()
                        obj.renavam = v_ren.strip() or None
                        obj.capacidade_carga_kg = Decimal(str(v_kg))
                        obj.capacidade_volume_m3 = Decimal(str(v_m3))
                        db.commit()
                        st.session_state["edit_vei_id"] = None
                        st.toast("Veículo salvo com sucesso!", icon="✅")
                        st.rerun()
                    except Exception as e:
                        db.rollback()
                        st.error(f"Erro ao salvar veículo: {e}")
                    finally:
                        db.close()

            if vei_ed and bv2.button("Cancelar", use_container_width=True, key="btn_canc_vei"):
                st.session_state["edit_vei_id"] = None
                st.rerun()

        with st.container(border=True):
            for v in veiculos_list:
                r1, r2, r3, r4 = st.columns([5, 3, 2, 2])
                r1.markdown(f"**{v['descricao']}** — `{v['placa']}`")
                r2.markdown(f"Tipo: `{v['tipo']}` | Cap: `{v['cap_kg']} kg`")
                if r3.button("✏️", key=f"ed_v_{v['id']}"):
                    st.session_state["edit_vei_id"] = v["id"]
                    st.rerun()
                if r4.button("✕", key=f"del_v_{v['id']}"):
                    db = SessionLocal()
                    try:
                        db.query(Veiculo).filter(Veiculo.id_veiculo == v["id"]).delete()
                        db.commit()
                        st.rerun()
                    except Exception as e:
                        db.rollback()
                        st.error(f"Não foi possível remover: {e}")
                    finally:
                        db.close()

    # --- 10.3 CLIENTES ---
    with tab_c:
        edit_cli_id = st.session_state.get("edit_cli_id")
        cli_ed = next((c for c in clientes_list if c["id"] == edit_cli_id), None)
        with st.container(border=True):
            st.markdown(
                f'<div class="secao-titulo">{"✏️ Editar Cliente" if cli_ed else "➕ Novo Cliente"}</div>',
                unsafe_allow_html=True,
            )
            c_c1, c_c2, c_c3 = st.columns([6, 3.5, 2.5])
            c_raz = c_c1.text_input("Razão Social", value=cli_ed["razao_social"] if cli_ed else "", key=f"cc_raz_{edit_cli_id}")
            c_doc = c_c2.text_input("CNPJ / CPF", value=cli_ed["cnpj_cpf"] if cli_ed else "", key=f"cc_doc_{edit_cli_id}")
            c_prz = c_c3.number_input("Prazo Pgto (Dias)", min_value=0, step=5, value=to_int(cli_ed["prazo"] if cli_ed else 30), key=f"cc_prz_{edit_cli_id}")

            c_c4, c_c5, c_c6 = st.columns([4, 4, 4])
            c_resp = c_c4.text_input("Responsável Comercial", value=cli_ed["responsavel"] if cli_ed else "", key=f"cc_resp_{edit_cli_id}")
            c_tel = c_c5.text_input("Telefone", value=cli_ed["telefone"] if cli_ed else "", key=f"cc_tel_{edit_cli_id}")
            c_mail = c_c6.text_input("E-mail Financeiro", value=cli_ed["email"] if cli_ed else "", key=f"cc_mail_{edit_cli_id}")

            c_c7, c_c8, c_c9, c_c10 = st.columns([2.5, 5.5, 2.8, 1.2])
            c_cep = c_c7.text_input("CEP", value=cli_ed["cep"] if cli_ed else "", key=f"cc_cep_{edit_cli_id}")
            c_end = c_c8.text_input("Endereço Completo", value=cli_ed["endereco"] if cli_ed else "", key=f"cc_end_{edit_cli_id}")
            c_cid = c_c9.text_input("Cidade", value=cli_ed["cidade"] if cli_ed else "", key=f"cc_cid_{edit_cli_id}")
            c_uf = c_c10.text_input("UF", value=cli_ed["uf"] if cli_ed else "", max_chars=2, key=f"cc_uf_{edit_cli_id}").upper()

            bc1, bc2, _ = st.columns([3, 2.5, 6.5])
            if bc1.button("💾 Salvar Cliente", type="primary", use_container_width=True, key="btn_save_cli"):
                if not c_raz.strip() or not c_doc.strip():
                    st.error("Preencha Razão Social e CNPJ/CPF.")
                else:
                    db = SessionLocal()
                    try:
                        obj = db.query(Cliente).filter(Cliente.id_cliente == edit_cli_id).first() if edit_cli_id else Cliente()
                        if not edit_cli_id:
                            db.add(obj)
                        obj.razao_social = c_raz.strip()
                        if hasattr(obj, "nome_fantasia"):
                            obj.nome_fantasia = c_raz.strip()
                        obj.cnpj_cpf = c_doc.strip()
                        obj.responsavel_comercial = c_resp.strip()
                        obj.telefone_comercial = c_tel.strip()
                        obj.email_financeiro = c_mail.strip()
                        obj.prazo_pagamento_dias = c_prz
                        if hasattr(obj, "cep"):
                            obj.cep = c_cep.strip()
                        if hasattr(obj, "endereco_completo"):
                            obj.endereco_completo = c_end.strip()
                        if hasattr(obj, "cidade"):
                            obj.cidade = c_cid.strip()
                        if hasattr(obj, "uf"):
                            obj.uf = c_uf.strip()
                        db.commit()
                        st.session_state["edit_cli_id"] = None
                        st.toast("Cliente salvo com sucesso!", icon="✅")
                        st.rerun()
                    except Exception as e:
                        db.rollback()
                        st.error(f"Erro ao salvar cliente: {e}")
                    finally:
                        db.close()

            if cli_ed and bc2.button("Cancelar", use_container_width=True, key="btn_canc_cli"):
                st.session_state["edit_cli_id"] = None
                st.rerun()

        with st.container(border=True):
            for c in clientes_list:
                r1, r2, r3, r4 = st.columns([5, 3, 2, 2])
                r1.markdown(f"**{c['razao_social']}**")
                r2.markdown(f"Doc: `{c['cnpj_cpf']}` | {c['cidade']}/{c['uf']}")
                if r3.button("✏️", key=f"ed_c_{c['id']}"):
                    st.session_state["edit_cli_id"] = c["id"]
                    st.rerun()
                if r4.button("✕", key=f"del_c_{c['id']}"):
                    db = SessionLocal()
                    try:
                        db.query(Cliente).filter(Cliente.id_cliente == c["id"]).delete()
                        db.commit()
                        st.rerun()
                    except Exception as e:
                        db.rollback()
                        st.error(f"Não foi possível remover: {e}")
                    finally:
                        db.close()

    # --- 10.4 LOCAIS ---
    with tab_l:
        edit_loc_id = st.session_state.get("edit_loc_id")
        loc_ed = next((l for l in locais_list if l["id"] == edit_loc_id), None)
        with st.container(border=True):
            st.markdown(
                f'<div class="secao-titulo">{"✏️ Editar Local" if loc_ed else "➕ Novo Local de Coleta / Entrega"}</div>',
                unsafe_allow_html=True,
            )
            l_c1, l_c2, l_c3 = st.columns([6, 3.5, 2.5])
            l_nome = l_c1.text_input("Nome do Local / CD / Empresa", value=loc_ed["nome"] if loc_ed else "", key=f"cl_nome_{edit_loc_id}")
            l_tipo = l_c2.text_input("Tipo Instalação", value=loc_ed["tipo"] if loc_ed else "Centro de Distribuição", key=f"cl_tipo_{edit_loc_id}")
            l_cep = l_c3.text_input("CEP", value=loc_ed["cep"] if loc_ed else "", key=f"cl_cep_{edit_loc_id}")

            l_c4, l_c5, l_c6 = st.columns([7.5, 3.3, 1.2])
            l_end = l_c4.text_input("Endereço Completo", value=loc_ed["endereco"] if loc_ed else "", key=f"cl_end_{edit_loc_id}")
            l_cid = l_c5.text_input("Cidade", value=loc_ed["cidade"] if loc_ed else "", key=f"cl_cid_{edit_loc_id}")
            l_uf = l_c6.text_input("UF", value=loc_ed["uf"] if loc_ed else "", max_chars=2, key=f"cl_uf_{edit_loc_id}").upper()

            l_c7, l_c8 = st.columns([6, 6])
            l_cont = l_c7.text_input("Contato / Portaria", value=loc_ed["contato"] if loc_ed else "", key=f"cl_cont_{edit_loc_id}")
            l_rest = l_c8.text_input("Restrição de Horário", value=loc_ed["restricao"] if loc_ed else "", key=f"cl_rest_{edit_loc_id}")

            bl1, bl2, _ = st.columns([3, 2.5, 6.5])
            if bl1.button("💾 Salvar Local", type="primary", use_container_width=True, key="btn_save_loc"):
                if not l_nome.strip():
                    st.error("Preencha o Nome do Local.")
                else:
                    db = SessionLocal()
                    try:
                        obj = db.query(Local).filter(Local.id_local == edit_loc_id).first() if edit_loc_id else Local()
                        if not edit_loc_id:
                            db.add(obj)
                        obj.nome_local = l_nome.strip()
                        obj.tipo_instalacao = l_tipo.strip()
                        obj.cep = l_cep.strip()
                        obj.endereco_completo = l_end.strip()
                        obj.cidade = l_cid.strip()
                        obj.uf = l_uf.strip()
                        obj.contato_portaria = l_cont.strip()
                        obj.restricao_horario = l_rest.strip()
                        db.commit()
                        st.session_state["edit_loc_id"] = None
                        st.toast("Local salvo com sucesso!", icon="✅")
                        st.rerun()
                    except Exception as e:
                        db.rollback()
                        st.error(f"Erro ao salvar local: {e}")
                    finally:
                        db.close()

            if loc_ed and bl2.button("Cancelar", use_container_width=True, key="btn_canc_loc"):
                st.session_state["edit_loc_id"] = None
                st.rerun()

        with st.container(border=True):
            for l in locais_list:
                r1, r2, r3, r4 = st.columns([5, 3, 2, 2])
                r1.markdown(f"**{l['nome']}** ({l['cidade']}/{l['uf']})")
                r2.markdown(f"{l['endereco'] or '-'}")
                if r3.button("✏️", key=f"ed_l_{l['id']}"):
                    st.session_state["edit_loc_id"] = l["id"]
                    st.rerun()
                if r4.button("✕", key=f"del_l_{l['id']}"):
                    db = SessionLocal()
                    try:
                        db.query(Local).filter(Local.id_local == l["id"]).delete()
                        db.commit()
                        st.rerun()
                    except Exception as e:
                        db.rollback()
                        st.error(f"Não foi possível remover: {e}")
                    finally:
                        db.close()

    # --- 10.5 FORNECEDORES ---
    with tab_f:
        edit_forn_id = st.session_state.get("edit_forn_id")
        forn_ed = next((f for f in fornecedores_list if f["id"] == edit_forn_id), None)
        with st.container(border=True):
            st.markdown(
                f'<div class="secao-titulo">{"✏️ Editar Fornecedor" if forn_ed else "➕ Novo Fornecedor"}</div>',
                unsafe_allow_html=True,
            )
            f_c1, f_c2, f_c3 = st.columns([5, 4, 3])
            f_nome = f_c1.text_input("Nome Fantasia", value=forn_ed["nome"] if forn_ed else "", key=f"cf_nome_{edit_forn_id}")
            f_cnpj = f_c2.text_input("CNPJ", value=forn_ed["cnpj"] if forn_ed else "", key=f"cf_cnpj_{edit_forn_id}")
            f_cat = f_c3.text_input("Categoria", value=forn_ed["categoria"] if forn_ed else "Posto de Combustível", key=f"cf_cat_{edit_forn_id}")

            f_c4, f_c5 = st.columns([9, 3])
            f_cid = f_c4.text_input("Cidade", value=forn_ed["cidade"] if forn_ed else "", key=f"cf_cid_{edit_forn_id}")
            f_uf = f_c5.text_input("UF", value=forn_ed["uf"] if forn_ed else "", max_chars=2, key=f"cf_uf_{edit_forn_id}").upper()

            bf1, bf2, _ = st.columns([3, 2.5, 6.5])
            if bf1.button("💾 Salvar Fornecedor", type="primary", use_container_width=True, key="btn_save_forn"):
                if not f_nome.strip():
                    st.error("Preencha o Nome Fantasia.")
                else:
                    db = SessionLocal()
                    try:
                        obj = db.query(Fornecedor).filter(Fornecedor.id_fornecedor == edit_forn_id).first() if edit_forn_id else Fornecedor()
                        if not edit_forn_id:
                            db.add(obj)
                        obj.nome_fantasia = f_nome.strip()
                        if hasattr(obj, "razao_social"):
                            obj.razao_social = f_nome.strip()
                        obj.cnpj = f_cnpj.strip() or None
                        obj.categoria_servico = f_cat.strip()
                        obj.cidade = f_cid.strip()
                        obj.uf = f_uf.strip()
                        db.commit()
                        st.session_state["edit_forn_id"] = None
                        st.toast("Fornecedor salvo com sucesso!", icon="✅")
                        st.rerun()
                    except Exception as e:
                        db.rollback()
                        st.error(f"Erro ao salvar fornecedor: {e}")
                    finally:
                        db.close()

            if forn_ed and bf2.button("Cancelar", use_container_width=True, key="btn_canc_forn"):
                st.session_state["edit_forn_id"] = None
                st.rerun()

        with st.container(border=True):
            for f in fornecedores_list:
                r1, r2, r3, r4 = st.columns([5, 3, 2, 2])
                r1.markdown(f"**{f['nome']}** ({f['categoria']})")
                r2.markdown(f"CNPJ: `{f['cnpj'] or '-'}` | {f['cidade']}/{f['uf']}")
                if r3.button("✏️", key=f"ed_f_{f['id']}"):
                    st.session_state["edit_forn_id"] = f["id"]
                    st.rerun()
                if r4.button("✕", key=f"del_f_{f['id']}"):
                    db = SessionLocal()
                    try:
                        db.query(Fornecedor).filter(Fornecedor.id_fornecedor == f["id"]).delete()
                        db.commit()
                        st.rerun()
                    except Exception as e:
                        db.rollback()
                        st.error(f"Não foi possível remover: {e}")
                    finally:
                        db.close()

    render_navegacao_rodape(idx_aba)

# ==============================================================================
# ETAPA 11: CONSULTAS GERAIS DE VIAGENS
# ==============================================================================
elif idx_aba == 10:
    st.markdown(
        """
        <div class="etapa-header">
            <h2>🔍 11. Consultas Gerais e Histórico de Viagens</h2>
            <p>Filtre por código (V1, V2...), cliente, origem, destino ou status e abra qualquer viagem para edição.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        q1, q2, q3, q4 = st.columns([3, 3, 3, 3])
        filtro_cod = q1.text_input("Filtrar por Código", placeholder="Ex.: V1, V2...", key="flt_cod")
        filtro_orig = q2.text_input("Filtrar por Origem", placeholder="Cidade ou UF", key="flt_orig")
        filtro_dest = q3.text_input("Filtrar por Destino", placeholder="Cidade ou UF", key="flt_dest")
        filtro_st = q4.selectbox(
            "Filtrar por Status",
            options=["Todos"] + OPCOES_STATUS_VIAGEM,
            key="flt_st",
        )

        filtradas = []
        for v in viagens_list:
            if filtro_cod and filtro_cod.strip().upper() not in v["codigo"].upper():
                continue
            if filtro_orig and filtro_orig.strip().lower() not in v["origem"].lower():
                continue
            if filtro_dest and filtro_dest.strip().lower() not in v["destino"].lower():
                continue
            if filtro_st != "Todos" and v["status"] != filtro_st:
                continue
            filtradas.append(v)

        if not filtradas:
            st.info("Nenhuma viagem encontrada com os filtros aplicados.")
        else:
            for v in filtradas:
                c_a, c_b, c_c, c_d, c_e = st.columns([1.8, 3.2, 3.5, 2, 1.5])
                c_a.markdown(f"<span class='badge-codigo'>{v['codigo']}</span>", unsafe_allow_html=True)
                c_b.markdown(f"**{v['cliente']}**")
                c_c.markdown(f"**Origem:** {v['origem'] or '-'}  \n**Destino:** {v['destino'] or '-'}")
                c_d.markdown(f"<span class='badge-status'>{v['status']}</span>", unsafe_allow_html=True)
                if c_e.button("Abrir ✏️", key=f"abrir_vg_{v['id']}", use_container_width=True):
                    carregar_viagem_para_estado(v["id"])
                    st.session_state["menu_operacional_radio"] = MENU_ITENS[0]
                    st.rerun()
                st.markdown("<hr style='margin: 0.4rem 0; border-color: #E2E8F0;'>", unsafe_allow_html=True)

    render_navegacao_rodape(idx_aba)