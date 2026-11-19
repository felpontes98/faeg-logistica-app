import base64
import io
import os
import re
import zlib
from datetime import date

import pandas as pd
import streamlit as st
from sqlalchemy.exc import IntegrityError

from database.connection import SessionLocal
from database.importador_planilha import analisar_planilha_faeg, importar_planilha_para_banco
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
# CONFIGURAÇÃO DA PÁGINA E IDENTIDADE VISUAL OFICIAL FAEG (MANUAL 2026)
# ==============================================================================
st.set_page_config(
    page_title="FAEG - Gestão Logística e Operacional",
    page_icon="🟧",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource(show_spinner=False)
def inicializar_banco_uma_vez(schema_v=3):
    """Garante que todas as tabelas e colunas novas existam no Neon sem alterar dados."""
    sincronizar_colunas_banco()
    return True


inicializar_banco_uma_vez(schema_v=3)

# ==============================================================================
# LISTAS PADRONIZADAS DO SISTEMA
# ==============================================================================
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

CATEGORIAS_DESPESA_FORNECEDOR = [
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

OPCOES_SITUACAO_OPERACAO = [
    "Aguardando Adiantamento",
    "Adiantamento Recebido",
    "Em Transporte",
    "Entregue / Aguardando Saldo",
    "Quitada / Concluída",
    "Cancelada",
]

# ==============================================================================
# FUNÇÕES DE PROGRESSÃO E EXTRAÇÃO DO CÓDIGO ÚNICO DA VIAGEM (V1, V2, V3...)
# ==============================================================================
def resolver_codigo_viagem(viagem_obj, ciclo_obj=None):
    """Obtém o código único da viagem (padrão V1, V2, V3...)."""
    cod_col = getattr(viagem_obj, "codigo_viagem", None)
    if cod_col and str(cod_col).strip():
        return str(cod_col).strip().upper()
    if ciclo_obj and ciclo_obj.status_ciclo and str(ciclo_obj.status_ciclo).startswith("COD::"):
        cod = str(ciclo_obj.status_ciclo).replace("COD::", "", 1).strip()
        if cod:
            return cod.upper()
    return f"V{viagem_obj.id_viagem}"


def extrair_numero_sequencial(codigo_str, fallback_id=0):
    """Extrai o número sequencial final de códigos como 'V1', 'V14', etc."""
    if codigo_str:
        match = re.search(r"(\d+)\s*$", str(codigo_str).strip())
        if match:
            return int(match.group(1))
    return int(fallback_id or 0)


def calcular_proximo_codigo_viagem(viagens_lista):
    """Calcula o próximo código único sequencial começando em V1."""
    if not viagens_lista:
        return "V1"
    usados = {str(vg.get("codigo_viagem", "")).strip().upper() for vg in viagens_lista}
    maior_seq = 0
    for vg in viagens_lista:
        seq = extrair_numero_sequencial(vg.get("codigo_viagem"), vg.get("id_viagem", 0))
        if seq > maior_seq:
            maior_seq = seq
    proximo_num = maior_seq + 1
    while f"V{proximo_num}" in usados:
        proximo_num += 1
    return f"V{proximo_num}"


def formatar_rota_exibicao(origem, destino, fallback_resumo=""):
    orig = (origem or "").strip()
    dest = (destino or "").strip()
    if orig and dest:
        return f"{orig} -> {dest}"
    if orig or dest:
        return orig or dest
    return (fallback_resumo or "").strip()


# ==============================================================================
# ESTILIZAÇÃO CSS OFICIAL FAEG (PALETA, TIPOGRAFIA E CORREÇÃO DE LABELS/CAMPOS)
# ==============================================================================
st.markdown(
    """
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
    html, body, [class*="css"], .stApp, button, input, select, textarea {
        font-family: 'Montserrat', sans-serif !important;
    }

    header[data-testid="stHeader"] {
        background: transparent;
        height: 0.4rem;
    }
    #MainMenu, footer {visibility: hidden;}

    /* Remove completamente "Press Enter to submit form" / "Press Enter to apply" */
    div[data-testid="InputInstructions"],
    [data-testid="stForm"] small,
    .stTextInput small,
    .stNumberInput small {
        display: none !important;
    }

    .stApp, [data-testid="stAppViewContainer"] {
        background-color: #E9E9E9 !important;
        color: #0D263C !important;
    }
    .block-container {
        padding: 1.2rem 2.2rem 2.5rem 2.2rem;
        max-width: 100%;
    }

    /* =====================================================================
       SIDEBAR INSTITUCIONAL FAEG (AZUL ESTRUTURAL #0D263C)
       ===================================================================== */
    section[data-testid="stSidebar"] {
        background-color: #0D263C !important;
        border-right: 1px solid #081826;
        min-width: 245px;
        max-width: 560px;
    }
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 0 !important;
    }

    div[data-testid="stSidebarResizeHandle"] {
        background-color: rgba(171, 206, 225, 0.15) !important;
        width: 4px !important;
        transition: background-color 0.15s ease;
    }
    div[data-testid="stSidebarResizeHandle"]:hover {
        background-color: #F34D25 !important;
    }

    .sidebar-brand {
        padding: 1.35rem 1.1rem 1.15rem 1.1rem;
        border-bottom: 1px solid rgba(171, 206, 225, 0.22);
        margin-bottom: 0.9rem;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .sidebar-logo-img {
        width: 100%;
        max-width: 215px;
        max-height: 86px;
        height: auto;
        object-fit: contain;
        display: block;
        filter: drop-shadow(0 2px 6px rgba(0, 0, 0, 0.25));
    }
    .sidebar-monogram-fallback {
        width: 54px;
        height: 54px;
        border-radius: 10px;
        background-color: #F34D25;
        color: #FFFFFF;
        font-weight: 900;
        font-size: 1.9rem;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    /* Cartão Fixo da Viagem Ativa na Sidebar */
    .sidebar-active-trip-card {
        background-color: #143654;
        border: 1px solid rgba(171, 206, 225, 0.38);
        border-left: 4px solid #F34D25;
        border-radius: 0.45rem;
        padding: 0.65rem 0.85rem;
        margin: 0 0.95rem 0.55rem 0.95rem;
    }
    .sidebar-active-trip-tag {
        font-size: 0.62rem;
        font-weight: 800;
        text-transform: uppercase;
        color: #ABCEE1;
        letter-spacing: 0.06em;
    }
    .sidebar-active-trip-code {
        font-size: 0.95rem;
        font-weight: 900;
        color: #FFFFFF;
        margin-top: 0.15rem;
        word-break: break-word;
    }

    /* Menu Lateral (st.radio) */
    section[data-testid="stSidebar"] div[role="radiogroup"] {
        gap: 2px;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label {
        width: 100%;
        padding: 0.56rem 1.25rem;
        margin: 0;
        border-radius: 0;
        cursor: pointer;
        transition: all 0.15s ease;
        border-right: 4px solid transparent;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
        background-color: rgba(171, 206, 225, 0.12);
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"],
    section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
        background-color: rgba(171, 206, 225, 0.22) !important;
        border-right: 4px solid #F34D25 !important;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p {
        color: #FFFFFF !important;
        font-weight: 700 !important;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label p {
        font-size: 0.81rem !important;
        color: #E9E9E9 !important;
        font-weight: 500;
        margin: 0;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {
        display: none !important;
    }

    /* Botão Secundário na Sidebar (+ Iniciar Nova Viagem) */
    section[data-testid="stSidebar"] .stButton > button[kind="secondary"] {
        background-color: rgba(171, 206, 225, 0.14) !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(171, 206, 225, 0.45) !important;
        font-weight: 700 !important;
        font-size: 0.75rem !important;
        border-radius: 0.4rem !important;
    }
    section[data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover {
        background-color: rgba(171, 206, 225, 0.28) !important;
    }

    /* Botão Principal CTA em Laranja Energia (#F34D25) */
    section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
        background-color: #F34D25 !important;
        color: #FFFFFF !important;
        font-weight: 800 !important;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        font-size: 0.82rem !important;
        border: none !important;
        border-radius: 0.45rem !important;
        padding: 0.75rem 1rem !important;
        box-shadow: 0 4px 12px rgba(243, 77, 37, 0.35);
    }
    section[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
        background-color: #D93E18 !important;
    }

    /* =====================================================================
       PADRONIZAÇÃO TOTAL DE TODOS OS INPUTS, SELECTS, DATES E TIMES
       ===================================================================== */
    [data-testid="stAppViewContainer"] div[data-baseweb="input"],
    [data-testid="stAppViewContainer"] div[data-baseweb="input"] > div,
    [data-testid="stAppViewContainer"] div[data-baseweb="base-input"],
    [data-testid="stAppViewContainer"] div[data-baseweb="select"] > div,
    [data-testid="stAppViewContainer"] div[data-testid="stDateInput"] > div > div,
    [data-testid="stAppViewContainer"] div[data-testid="stTimeInput"] > div > div {
        background-color: #FFFFFF !important;
        border: 1.5px solid #CBD5E1 !important;
        border-radius: 0.45rem !important;
        min-height: 42px !important;
        color: #0D263C !important;
        box-shadow: none !important;
    }

    [data-testid="stAppViewContainer"] div[data-baseweb="input"]:hover > div,
    [data-testid="stAppViewContainer"] div[data-baseweb="select"] > div:hover {
        border-color: #94A3B8 !important;
    }
    [data-testid="stAppViewContainer"] div[data-baseweb="input"]:focus-within > div,
    [data-testid="stAppViewContainer"] div[data-baseweb="base-input"]:focus-within,
    [data-testid="stAppViewContainer"] div[data-baseweb="select"] > div:focus-within {
        border-color: #F34D25 !important;
        box-shadow: 0 0 0 2px rgba(243, 77, 37, 0.16) !important;
    }

    [data-testid="stAppViewContainer"] div[data-baseweb="input"] input,
    [data-testid="stAppViewContainer"] div[data-baseweb="select"] > div {
        padding-left: 0.65rem !important;
        padding-right: 0.65rem !important;
    }

    [data-testid="stAppViewContainer"] input,
    [data-testid="stAppViewContainer"] textarea,
    [data-testid="stAppViewContainer"] div[data-baseweb="select"] span,
    [data-testid="stAppViewContainer"] div[data-baseweb="select"] div {
        color: #0D263C !important;
        -webkit-text-fill-color: #0D263C !important;
        font-size: 0.86rem !important;
        font-weight: 500 !important;
    }

    [data-testid="stAppViewContainer"] input::placeholder,
    [data-testid="stAppViewContainer"] textarea::placeholder {
        color: #64748B !important;
        -webkit-text-fill-color: #64748B !important;
        opacity: 1 !important;
        font-size: 0.80rem !important;
        font-weight: 400 !important;
        text-overflow: ellipsis !important;
    }

    [data-testid="stAppViewContainer"] div[data-baseweb="select"] svg,
    [data-testid="stAppViewContainer"] div[data-testid="stDateInput"] svg,
    [data-testid="stAppViewContainer"] div[data-testid="stTimeInput"] svg {
        fill: #0D263C !important;
        color: #0D263C !important;
    }

    [data-testid="stAppViewContainer"] button[data-testid="stNumberInputStepDown"],
    [data-testid="stAppViewContainer"] button[data-testid="stNumberInputStepUp"] {
        background-color: #F8FAFC !important;
        color: #0D263C !important;
        border-left: 1px solid #E2E8F0 !important;
    }
    [data-testid="stAppViewContainer"] button[data-testid="stNumberInputStepDown"]:hover,
    [data-testid="stAppViewContainer"] button[data-testid="stNumberInputStepUp"]:hover {
        background-color: #ABCEE1 !important;
        color: #0D263C !important;
    }

    div[data-baseweb="popover"],
    div[data-baseweb="popover"] > div,
    ul[data-baseweb="menu"],
    div[data-baseweb="calendar"] {
        background-color: #FFFFFF !important;
        color: #0D263C !important;
        border: 1px solid #CBD5E1 !important;
        box-shadow: 0 12px 28px rgba(13, 38, 60, 0.16) !important;
    }
    ul[data-baseweb="menu"] li,
    div[data-baseweb="calendar"] * {
        color: #0D263C !important;
    }
    ul[data-baseweb="menu"] li:hover,
    ul[data-baseweb="menu"] li[aria-selected="true"] {
        background-color: rgba(171, 206, 225, 0.4) !important;
        color: #0D263C !important;
        font-weight: 700 !important;
    }

    [data-testid="stAppViewContainer"] div[data-baseweb="input"]:has(input:disabled),
    [data-testid="stAppViewContainer"] div[data-baseweb="input"]:has(input:disabled) > div,
    [data-testid="stAppViewContainer"] div[data-baseweb="base-input"]:has(input:disabled) {
        background-color: #F1F5F9 !important;
        border: 1.5px dashed #94A3B8 !important;
    }
    [data-testid="stAppViewContainer"] input:disabled {
        background-color: #F1F5F9 !important;
        color: #0D263C !important;
        font-weight: 700 !important;
        -webkit-text-fill-color: #0D263C !important;
        opacity: 1 !important;
    }

    /* Rótulos com quebra de linha controlada (elimina sobreposição entre colunas) */
    div[data-testid="stWidgetLabel"],
    .stTextInput label,
    .stNumberInput label,
    .stSelectbox label,
    .stDateInput label,
    .stTimeInput label,
    .stTextArea label {
        margin-bottom: 0.25rem !important;
        min-height: 1.15rem !important;
    }
    div[data-testid="stWidgetLabel"] p,
    .stTextInput label p,
    .stNumberInput label p,
    .stSelectbox label p,
    .stDateInput label p,
    .stTimeInput label p,
    .stTextArea label p {
        font-size: 0.71rem !important;
        font-weight: 700 !important;
        color: #0D263C !important;
        text-transform: uppercase !important;
        letter-spacing: 0.03em !important;
        white-space: normal !important;
        word-break: break-word !important;
        overflow: visible !important;
        text-overflow: unset !important;
        line-height: 1.25 !important;
    }

    /* Abas internas (st.tabs) no padrão visual FAEG */
    button[data-baseweb="tab"] {
        font-weight: 700 !important;
        font-size: 0.85rem !important;
        color: #475569 !important;
        padding: 0.65rem 1.1rem !important;
        background-color: transparent !important;
    }
    button[data-baseweb="tab"]:hover {
        color: #0D263C !important;
        background-color: rgba(171, 206, 225, 0.16) !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #F34D25 !important;
        font-weight: 800 !important;
    }
    div[data-baseweb="tab-highlight"] {
        background-color: #F34D25 !important;
        height: 3px !important;
    }

    [data-testid="stAppViewContainer"] .stButton > button,
    [data-testid="stAppViewContainer"] .stFormSubmitButton > button,
    [data-testid="stAppViewContainer"] .stDownloadButton > button {
        background-color: #0D263C !important;
        color: #FFFFFF !important;
        font-weight: 700 !important;
        font-size: 0.8rem !important;
        letter-spacing: 0.02em;
        border: 1px solid #0D263C !important;
        border-radius: 0.45rem !important;
        min-height: 40px !important;
        transition: all 0.15s ease;
    }
    [data-testid="stAppViewContainer"] .stButton > button:hover,
    [data-testid="stAppViewContainer"] .stFormSubmitButton > button:hover,
    [data-testid="stAppViewContainer"] .stDownloadButton > button:hover {
        background-color: #F34D25 !important;
        border-color: #F34D25 !important;
        color: #FFFFFF !important;
    }

    /* =====================================================================
       BARRA EXECUTIVA E CARTÃO PRINCIPAL
       ===================================================================== */
    .top-context-bar {
        background-color: #FFFFFF;
        border: 1px solid #D6D6D6;
        border-left: 5px solid #F34D25;
        border-radius: 0.55rem;
        padding: 0.85rem 1.4rem;
        margin-bottom: 1rem;
        display: flex;
        flex-wrap: wrap;
        justify-content: space-between;
        align-items: center;
        gap: 1rem;
        box-shadow: 0 2px 6px rgba(13, 38, 60, 0.04);
    }
    .ctx-item {
        display: flex;
        flex-direction: column;
    }
    .ctx-label {
        font-size: 0.64rem;
        font-weight: 700;
        text-transform: uppercase;
        color: #64748B;
        letter-spacing: 0.05em;
    }
    .ctx-val {
        font-size: 0.9rem;
        font-weight: 800;
        color: #0D263C;
    }
    .ctx-badge {
        background-color: rgba(171, 206, 225, 0.35);
        color: #0D263C;
        border: 1px solid #ABCEE1;
        padding: 0.32rem 0.8rem;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div > .main-card-marker) {
        background-color: #FFFFFF;
        border-radius: 0.65rem;
        border: 1px solid #D6D6D6;
        padding: 1.85rem 2.2rem;
        box-shadow: 0 4px 14px rgba(13, 38, 60, 0.05);
    }

    .tab-header-wrap {
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 2px solid #E9E9E9;
        padding-bottom: 0.75rem;
        margin-bottom: 1.35rem;
    }
    .tab-title {
        font-size: 1.32rem;
        font-weight: 800;
        color: #0D263C;
        letter-spacing: -0.01em;
        display: flex;
        align-items: center;
        gap: 0.6rem;
    }
    .tab-title i {
        color: #F34D25;
        font-size: 1.22rem;
    }
    .tab-step-pill {
        background-color: #F1F5F9;
        color: #475569;
        font-size: 0.72rem;
        font-weight: 700;
        padding: 0.25rem 0.7rem;
        border-radius: 999px;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    .sec-subtitle {
        font-size: 0.75rem;
        font-weight: 800;
        color: #0D263C;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        border-top: 1px solid #E9E9E9;
        padding-top: 1rem;
        margin-top: 1rem;
        margin-bottom: 0.65rem;
        display: flex;
        align-items: center;
        gap: 0.45rem;
    }
    .sec-subtitle::before {
        content: "";
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 2px;
        background-color: #F34D25;
    }

    .edit-banner-pill {
        background-color: rgba(243, 77, 37, 0.1);
        border: 1px solid #F34D25;
        color: #0D263C;
        font-size: 0.75rem;
        font-weight: 700;
        padding: 0.4rem 0.75rem;
        border-radius: 0.4rem;
        margin-bottom: 0.7rem;
        display: flex;
        align-items: center;
        gap: 0.45rem;
    }

    .confirm-box-del {
        background-color: #FEF2F2;
        border: 1px solid #EF4444;
        border-left: 4px solid #DC2626;
        color: #7F1D1D;
        font-size: 0.76rem;
        font-weight: 700;
        padding: 0.45rem 0.7rem;
        border-radius: 0.35rem;
        margin: 0.25rem 0 0.4rem 0;
    }
    .confirm-box-edit {
        background-color: #EFF6FF;
        border: 1px solid #3B82F6;
        border-left: 4px solid #0D263C;
        color: #0D263C;
        font-size: 0.76rem;
        font-weight: 700;
        padding: 0.45rem 0.7rem;
        border-radius: 0.35rem;
        margin: 0.25rem 0 0.4rem 0;
    }

    .cliente-coleta-banner {
        background-color: rgba(171, 206, 225, 0.22);
        border: 1px solid #ABCEE1;
        border-left: 4px solid #0D263C;
        border-radius: 0.45rem;
        padding: 0.65rem 1rem;
        margin-bottom: 1rem;
        font-size: 0.82rem;
        color: #0D263C;
    }

    .faeg-recebimento-banner {
        background-color: rgba(171, 206, 225, 0.25);
        border: 1px solid #ABCEE1;
        border-left: 5px solid #0D263C;
        border-radius: 0.5rem;
        padding: 1.05rem 1.4rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 1.2rem;
    }
    .faeg-recebimento-label {
        color: #0D263C;
        font-weight: 700;
        text-transform: uppercase;
        font-size: 0.82rem;
        letter-spacing: 0.03em;
    }
    .faeg-recebimento-val {
        color: #0D263C;
        font-size: 1.6rem;
        font-weight: 900;
    }

    .kpi-consulta-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 0.9rem;
        margin: 0.9rem 0 1.2rem 0;
    }
    .kpi-consulta-card {
        background: #F8FAFC;
        border: 1px solid #CBD5E1;
        border-top: 4px solid #0D263C;
        border-radius: 0.45rem;
        padding: 0.85rem 1rem;
    }
    .kpi-consulta-card.orange {
        border-top-color: #F34D25;
    }
    .kpi-consulta-lbl {
        font-size: 0.68rem;
        font-weight: 700;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .kpi-consulta-val {
        font-size: 1.2rem;
        font-weight: 900;
        color: #0D263C;
        margin-top: 0.2rem;
    }

    .dre-box {
        background-color: #0D263C;
        border-radius: 0.65rem;
        padding: 1.8rem 2.2rem;
        color: #FFFFFF;
        margin-top: 1.3rem;
        border-top: 5px solid #F34D25;
        box-shadow: 0 8px 20px rgba(13, 38, 60, 0.18);
    }
    .dre-header {
        text-align: center;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.09em;
        color: #ABCEE1;
        border-bottom: 1px solid rgba(171, 206, 225, 0.25);
        padding-bottom: 0.7rem;
        margin-bottom: 1.3rem;
        font-size: 0.85rem;
    }
    .dre-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.9rem;
        font-size: 1rem;
    }
    .dre-total-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-top: 1px solid rgba(171, 206, 225, 0.25);
        padding-top: 1.1rem;
        margin-top: 0.9rem;
    }

    /* Cards da Aba 11 */
    div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div > .card-faeg-azul) {
        background-color: #FFFFFF;
        border: 1px solid #D6D6D6;
        border-top: 4px solid #0D263C;
        border-radius: 0.55rem;
        padding: 1.3rem;
        box-shadow: 0 2px 8px rgba(13, 38, 60, 0.04);
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div > .card-faeg-laranja) {
        background-color: #FFFFFF;
        border: 1px solid #D6D6D6;
        border-top: 4px solid #F34D25;
        border-radius: 0.55rem;
        padding: 1.3rem;
        box-shadow: 0 2px 8px rgba(13, 38, 60, 0.04);
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div > .card-faeg-expansao) {
        background-color: #FFFFFF;
        border: 1px solid #D6D6D6;
        border-top: 4px solid #ABCEE1;
        border-radius: 0.55rem;
        padding: 1.3rem;
        box-shadow: 0 2px 8px rgba(13, 38, 60, 0.04);
    }
</style>
""",
    unsafe_allow_html=True,
)


# ==============================================================================
# FUNÇÕES AUXILIARES, CÁLCULOS AUTOMÁTICOS E PERSISTÊNCIA ENTRE ABAS
# ==============================================================================
def to_float(val, default=0.0):
    return float(val) if val is not None else float(default)


def to_int(val, default=0):
    return int(val) if val is not None else int(default)


def fmt_brl(val):
    v = to_float(val, 0.0)
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_rotulo_cliente(c):
    partes_nome = [c["razao_social"]]
    if (
        c.get("nome_fantasia")
        and c["nome_fantasia"].strip().lower() != c["razao_social"].strip().lower()
    ):
        partes_nome.append(f"({c['nome_fantasia']})")
    titulo = " ".join(partes_nome)

    detalhes_local = []
    if c.get("endereco_completo"):
        detalhes_local.append(c["endereco_completo"])
    if c.get("cidade") or c.get("uf"):
        detalhes_local.append(f"{c.get('cidade') or ''}/{c.get('uf') or ''}".strip("/"))

    sufixo = f" — {', '.join(detalhes_local)}" if detalhes_local else f" — Doc: {c['cnpj_cpf']}"
    return f"{titulo}{sufixo}"


def formatar_rotulo_local(l, cli_map):
    end_parts = []
    if l.get("endereco_completo"):
        end_parts.append(l["endereco_completo"])
    cid_uf = f"{l.get('cidade') or ''}/{l.get('uf') or ''}".strip("/")
    if cid_uf:
        end_parts.append(cid_uf)
    end_txt = f" — {', '.join(end_parts)}" if end_parts else ""

    cli_vinculado = cli_map.get(l.get("id_cliente"))
    cli_txt = ""
    if cli_vinculado:
        nome_c = cli_vinculado.get("nome_fantasia") or cli_vinculado["razao_social"]
        cli_txt = f" [Cliente: {nome_c}]"

    return f"{l['nome_local']}{end_txt}{cli_txt}"


def get_campo(chave, padrao=None):
    if "form_data" not in st.session_state:
        st.session_state["form_data"] = {}
    return st.session_state["form_data"].get(chave, padrao)


def sync_campo(chave_widget, chave_dado):
    if "form_data" not in st.session_state:
        st.session_state["form_data"] = {}
    if chave_widget in st.session_state:
        st.session_state["form_data"][chave_dado] = st.session_state[chave_widget]


def _atualizar_rota_automatica(locais_lista):
    """Preenche automaticamente Origem e/ou Destino se estiverem em branco ao escolher os locais."""
    loc_map = {l["id_local"]: l for l in locais_lista}
    col_id = get_campo("col_id", 0)
    ent_id = get_campo("ent_id", 0)

    if col_id and not (get_campo("rota_origem") or "").strip():
        l_c = loc_map.get(col_id)
        if l_c and (l_c.get("cidade") or l_c.get("uf")):
            orig = f"{l_c.get('cidade') or ''}/{l_c.get('uf') or ''}".strip("/")
            if orig:
                st.session_state["form_data"]["rota_origem"] = orig
                if "w_rota_origem" in st.session_state:
                    del st.session_state["w_rota_origem"]

    if ent_id and not (get_campo("rota_destino") or "").strip():
        l_e = loc_map.get(ent_id)
        if l_e and (l_e.get("cidade") or l_e.get("uf")):
            dest = f"{l_e.get('cidade') or ''}/{l_e.get('uf') or ''}".strip("/")
            if dest:
                st.session_state["form_data"]["rota_destino"] = dest
                if "w_rota_destino" in st.session_state:
                    del st.session_state["w_rota_destino"]


def on_local_select_change(chave_widget, chave_dado, locais_lista):
    """Sincroniza imediatamente o local escolhido e preenche Origem/Destino se ainda estiverem vazios."""
    sync_campo(chave_widget, chave_dado)
    _atualizar_rota_automatica(locais_lista)


def _limpar_widgets_financeiros():
    for wk in ["w_perc_adiant", "w_val_adiant", "w_perc_saldo", "w_val_saldo"]:
        if wk in st.session_state:
            del st.session_state[wk]


def on_valor_negociado_change():
    sync_campo("w_val_negociado", "valor_negociado")
    neg = to_float(get_campo("valor_negociado", 0.0))
    p_adi = to_float(get_campo("perc_adiant", 0.0))
    p_sal = to_float(get_campo("perc_saldo", 0.0))
    if neg > 0:
        if p_adi > 0:
            st.session_state["form_data"]["valor_adiant"] = round(neg * (p_adi / 100.0), 2)
        if p_sal > 0:
            st.session_state["form_data"]["valor_saldo"] = round(neg * (p_sal / 100.0), 2)
        _limpar_widgets_financeiros()


def on_perc_adiant_change():
    sync_campo("w_perc_adiant", "perc_adiant")
    neg = to_float(get_campo("valor_negociado", 0.0))
    p_adi = to_float(get_campo("perc_adiant", 0.0))
    if neg > 0:
        st.session_state["form_data"]["valor_adiant"] = round(neg * (p_adi / 100.0), 2)
        if 0 <= p_adi <= 100:
            p_sal = round(100.0 - p_adi, 2)
            st.session_state["form_data"]["perc_saldo"] = p_sal
            st.session_state["form_data"]["valor_saldo"] = round(neg * (p_sal / 100.0), 2)
        _limpar_widgets_financeiros()


def on_val_adiant_change():
    sync_campo("w_val_adiant", "valor_adiant")
    neg = to_float(get_campo("valor_negociado", 0.0))
    v_adi = to_float(get_campo("valor_adiant", 0.0))
    if neg > 0:
        p_adi = round((v_adi / neg) * 100.0, 2)
        st.session_state["form_data"]["perc_adiant"] = p_adi
        if 0 <= v_adi <= neg:
            v_sal = round(neg - v_adi, 2)
            st.session_state["form_data"]["valor_saldo"] = v_sal
            st.session_state["form_data"]["perc_saldo"] = round((v_sal / neg) * 100.0, 2)
        _limpar_widgets_financeiros()


def on_perc_saldo_change():
    sync_campo("w_perc_saldo", "perc_saldo")
    neg = to_float(get_campo("valor_negociado", 0.0))
    p_sal = to_float(get_campo("perc_saldo", 0.0))
    if neg > 0:
        st.session_state["form_data"]["valor_saldo"] = round(neg * (p_sal / 100.0), 2)
        if 0 <= p_sal <= 100:
            p_adi = round(100.0 - p_sal, 2)
            st.session_state["form_data"]["perc_adiant"] = p_adi
            st.session_state["form_data"]["valor_adiant"] = round(neg * (p_adi / 100.0), 2)
        _limpar_widgets_financeiros()


def on_val_saldo_change():
    sync_campo("w_val_saldo", "valor_saldo")
    neg = to_float(get_campo("valor_negociado", 0.0))
    v_sal = to_float(get_campo("valor_saldo", 0.0))
    if neg > 0:
        p_sal = round((v_sal / neg) * 100.0, 2)
        st.session_state["form_data"]["perc_saldo"] = p_sal
        if 0 <= v_sal <= neg:
            v_adi = round(neg - v_sal, 2)
            st.session_state["form_data"]["valor_adiant"] = v_adi
            st.session_state["form_data"]["perc_adiant"] = round((v_adi / neg) * 100.0, 2)
        _limpar_widgets_financeiros()


def on_cliente_select_change(locais_lista):
    """Ao selecionar o Cliente na Etapa 3, vincula automaticamente seu Local de Coleta correspondente."""
    sync_campo("w_cli_id", "cli_id")
    cli_id_novo = get_campo("cli_id", 0)
    if cli_id_novo:
        local_match = next((l for l in locais_lista if l.get("id_cliente") == cli_id_novo), None)
        if local_match:
            st.session_state["form_data"]["col_id"] = local_match["id_local"]
            if "w_col_id" in st.session_state:
                del st.session_state["w_col_id"]
            _atualizar_rota_automatica(locais_lista)


def on_tipo_viagem_change():
    """Bloqueia e limpa o campo de Ciclo Operacional quando o Tipo de Viagem for Individual."""
    sync_campo("w_tipo_viagem", "tipo_viagem")
    if get_campo("tipo_viagem", "Individual") == "Individual":
        st.session_state["form_data"]["ciclo_nome"] = ""
        if "w_ciclo_nome" in st.session_state:
            del st.session_state["w_ciclo_nome"]


# ==============================================================================
# CACHE DE DADOS PARA NAVEGAÇÃO INSTANTÂNEA, CONSULTAS E EXPORTAÇÃO COMPLETA
# ==============================================================================
@st.cache_data(ttl=300, show_spinner=False)
def carregar_listas_base():
    """Carrega todos os cadastros e viagens em memória."""
    with SessionLocal() as session:
        motoristas = [
            {
                "id_motorista": m.id_motorista,
                "nome_completo": m.nome_completo,
                "cpf": m.cpf,
                "telefone_contato": m.telefone_contato,
                "cnh_numero": m.cnh_numero,
                "cnh_categoria": m.cnh_categoria,
                "cnh_validade": m.cnh_validade,
                "vinculo": m.vinculo,
            }
            for m in session.query(Motorista).order_by(Motorista.nome_completo).all()
        ]
        veiculos = [
            {
                "id_veiculo": v.id_veiculo,
                "descricao_marca": v.descricao_marca,
                "placa": v.placa,
                "tipo_veiculo": v.tipo_veiculo,
                "renavam": v.renavam,
                "ano_fabricacao": v.ano_fabricacao,
                "capacidade_carga_kg": v.capacidade_carga_kg,
                "capacidade_volume_m3": v.capacidade_volume_m3,
            }
            for v in session.query(Veiculo).order_by(Veiculo.descricao_marca).all()
        ]
        clientes = [
            {
                "id_cliente": c.id_cliente,
                "razao_social": c.razao_social,
                "nome_fantasia": c.nome_fantasia,
                "cnpj_cpf": c.cnpj_cpf,
                "inscricao_estadual": c.inscricao_estadual,
                "responsavel_comercial": c.responsavel_comercial,
                "telefone_comercial": c.telefone_comercial,
                "email_financeiro": c.email_financeiro,
                "prazo_pagamento_dias": c.prazo_pagamento_dias,
                "cep": c.cep,
                "endereco_completo": c.endereco_completo,
                "cidade": c.cidade,
                "uf": c.uf,
            }
            for c in session.query(Cliente).order_by(Cliente.razao_social).all()
        ]
        locais = [
            {
                "id_local": l.id_local,
                "id_cliente": l.id_cliente,
                "nome_local": l.nome_local,
                "tipo_instalacao": l.tipo_instalacao,
                "cep": l.cep,
                "endereco_completo": l.endereco_completo,
                "cidade": l.cidade,
                "uf": l.uf,
                "contato_portaria": l.contato_portaria,
                "restricao_horario": l.restricao_horario,
            }
            for l in session.query(Local).order_by(Local.nome_local).all()
        ]
        fornecedores = [
            {
                "id_fornecedor": f.id_fornecedor,
                "razao_social": f.razao_social,
                "nome_fantasia": f.nome_fantasia,
                "cnpj": f.cnpj,
                "categoria_servico": f.categoria_servico,
                "cidade": f.cidade,
                "uf": f.uf,
            }
            for f in session.query(Fornecedor).order_by(Fornecedor.nome_fantasia).all()
        ]
        viagens_raw = session.query(Viagem).order_by(Viagem.id_viagem.desc()).all()
        viagens = []
        for vg in viagens_raw:
            cod = resolver_codigo_viagem(vg, vg.ciclo)
            rota_fmt = formatar_rota_exibicao(
                getattr(vg, "rota_origem", None),
                getattr(vg, "rota_destino", None),
                vg.rota_resumo,
            )
            viagens.append(
                {
                    "id_viagem": vg.id_viagem,
                    "codigo_viagem": cod,
                    "seq_num": extrair_numero_sequencial(cod, vg.id_viagem),
                    "rota_origem": getattr(vg, "rota_origem", "") or "",
                    "rota_destino": getattr(vg, "rota_destino", "") or "",
                    "rota_resumo": rota_fmt,
                }
            )
        viagens.sort(key=lambda x: (x["seq_num"], x["id_viagem"]), reverse=True)
    return motoristas, veiculos, clientes, locais, fornecedores, viagens


@st.cache_data(ttl=300, show_spinner=False)
def carregar_todas_viagens_consulta():
    """Carrega visão consolidada de todas as viagens, ciclos, receitas e despesas para Consultas e BI."""
    with SessionLocal() as session:
        viagens_raw = session.query(Viagem).order_by(Viagem.id_viagem.desc()).all()
        despesas_all = session.query(ViagemDespesa).all()
        desp_por_viagem = {}
        desp_detalhadas = []
        cod_map = {vg.id_viagem: resolver_codigo_viagem(vg, vg.ciclo) for vg in viagens_raw}

        for d in despesas_all:
            vt = to_float(d.valor_total)
            desp_por_viagem[d.id_viagem] = desp_por_viagem.get(d.id_viagem, 0.0) + vt
            desp_detalhadas.append(
                {
                    "Código Viagem": cod_map.get(d.id_viagem, f"V{d.id_viagem}"),
                    "Tipo Despesa": d.tipo_despesa,
                    "Descrição": d.descricao_detalhe or "-",
                    "Fornecedor": d.fornecedor.nome_fantasia if d.fornecedor else "Não informado",
                    "Quantidade": to_float(d.quantidade),
                    "Valor Unitário (R$)": to_float(d.valor_unitario),
                    "Valor Total (R$)": vt,
                }
            )

        lista = []
        for vg in viagens_raw:
            ciclo = vg.ciclo
            fin = ciclo.financeiro if ciclo else None
            cli = ciclo.cliente if ciclo else None
            mot = vg.motorista
            vei = vg.veiculo
            col = vg.local_coleta
            ent = vg.local_entrega

            cod_vg = cod_map.get(vg.id_viagem, f"V{vg.id_viagem}")
            v_div = to_float(fin.valor_divulgado) if fin else 0.0
            v_neg = to_float(fin.valor_negociado_total) if fin else 0.0
            v_adi = to_float(fin.valor_adiantamento) if fin else 0.0
            v_sal = to_float(fin.valor_saldo) if fin else 0.0
            total_rec = v_adi + v_sal
            receita_base = v_neg if v_neg > 0 else total_rec
            tot_desp = desp_por_viagem.get(vg.id_viagem, 0.0)
            res_liq = receita_base - tot_desp
            km_real = to_int(vg.km_real_rodado)
            if km_real == 0 and to_int(vg.odometro_final) > to_int(vg.odometro_inicial):
                km_real = to_int(vg.odometro_final) - to_int(vg.odometro_inicial)
            custo_km = (tot_desp / km_real) if km_real > 0 else 0.0
            margem = ((res_liq / receita_base) * 100.0) if receita_base > 0 else 0.0

            tipo_viagem_atual = getattr(vg, "tipo_viagem", None) or (
                vg.tipo_frete if vg.tipo_frete in ["Individual", "Ciclo"] else "Individual"
            )
            tipo_frete_atual = vg.tipo_frete if vg.tipo_frete not in ["Individual", "Ciclo"] else "Dedicado"
            ciclo_nome_limpo = ciclo.nome_operacao if ciclo else "-"
            if ciclo_nome_limpo.startswith("Individual - "):
                ciclo_nome_limpo = "-"

            origem_str = (getattr(vg, "rota_origem", None) or "").strip()
            destino_str = (getattr(vg, "rota_destino", None) or "").strip()
            if not origem_str and not destino_str and vg.rota_resumo and "->" in vg.rota_resumo:
                partes_r = vg.rota_resumo.split("->", 1)
                origem_str = partes_r[0].strip()
                destino_str = partes_r[1].strip()
            rota_exib = formatar_rota_exibicao(origem_str, destino_str, vg.rota_resumo)

            lista.append(
                {
                    "id_viagem": vg.id_viagem,
                    "codigo_viagem": cod_vg,
                    "seq_num": extrair_numero_sequencial(cod_vg, vg.id_viagem),
                    "id_frete": vg.id_frete_externo or "-",
                    "status": vg.status_viagem or "Aguardando Adiantamento",
                    "tipo_viagem": tipo_viagem_atual,
                    "ciclo": ciclo_nome_limpo,
                    "tipo_frete": tipo_frete_atual,
                    "origem_frete": fin.forma_contratacao if fin else "-",
                    "data_coleta": vg.data_coleta,
                    "data_entrega": vg.data_entrega,
                    "cliente": cli.razao_social if cli else "-",
                    "cliente_fantasia": (cli.nome_fantasia or "") if cli else "",
                    "motorista": mot.nome_completo if mot else "-",
                    "veiculo": f"{vei.descricao_marca} ({vei.placa})" if vei else "-",
                    "rota_origem": origem_str,
                    "rota_destino": destino_str,
                    "rota": rota_exib or "-",
                    "coleta": f"{col.nome_local} ({col.cidade}/{col.uf})" if col else "-",
                    "entrega": f"{ent.nome_local} ({ent.cidade}/{ent.uf})" if ent else "-",
                    "nfe": vg.nfe_carga or "-",
                    "cte": vg.cte_numero or "-",
                    "mdfe": vg.mdfe_numero or "-",
                    "ciot": vg.ciot_numero or "-",
                    "valor_divulgado": v_div,
                    "valor_negociado": v_neg,
                    "valor_adiantamento": v_adi,
                    "valor_saldo": v_sal,
                    "total_recebido": total_rec,
                    "receita_base": receita_base,
                    "total_despesas": tot_desp,
                    "resultado_liquido": res_liq,
                    "km_rodado": km_real,
                    "custo_km": custo_km,
                    "margem_pct": margem,
                }
            )
        lista.sort(key=lambda x: (x["seq_num"], x["id_viagem"]), reverse=True)
    return lista, desp_detalhadas


@st.cache_data(ttl=300, show_spinner=False)
def carregar_despesas_viagem(id_viagem):
    """Carrega despesas de uma viagem específica em cache."""
    if not id_viagem or id_viagem == 0:
        return []
    with SessionLocal() as session:
        return [
            {
                "id_despesa": d.id_despesa,
                "id_fornecedor": d.id_fornecedor,
                "tipo_despesa": d.tipo_despesa,
                "descricao_detalhe": d.descricao_detalhe,
                "quantidade": d.quantidade,
                "valor_unitario": d.valor_unitario,
                "valor_total": d.valor_total,
            }
            for d in session.query(ViagemDespesa)
            .filter_by(id_viagem=id_viagem)
            .order_by(ViagemDespesa.id_despesa)
            .all()
        ]


def gerar_excel_base_completa(todas_viagens, desp_detalhadas, motoristas, veiculos, clientes, locais, fornecedores):
    """Gera arquivo Excel (.xlsx) completo com todas as viagens, despesas e cadastros do sistema."""
    buf = io.BytesIO()

    df_viagens = pd.DataFrame(
        [
            {
                "Código Viagem": v["codigo_viagem"],
                "ID Frete": v["id_frete"],
                "Situação": v["status"],
                "Tipo Viagem": v["tipo_viagem"],
                "Ciclo": v["ciclo"],
                "Tipo Frete": v["tipo_frete"],
                "Origem Frete": v["origem_frete"],
                "Data Coleta": v["data_coleta"].strftime("%d/%m/%Y") if v["data_coleta"] else "-",
                "Data Entrega": v["data_entrega"].strftime("%d/%m/%Y") if v["data_entrega"] else "-",
                "Cliente": v["cliente"],
                "Motorista": v["motorista"],
                "Veículo": v["veiculo"],
                "Origem": v["rota_origem"],
                "Destino": v["rota_destino"],
                "Rota": v["rota"],
                "Coleta": v["coleta"],
                "Entrega": v["entrega"],
                "NF-e": v["nfe"],
                "CT-e": v["cte"],
                "MDF-e": v["mdfe"],
                "CIOT": v["ciot"],
                "Valor Divulgado (R$)": v["valor_divulgado"],
                "Valor Negociado (R$)": v["valor_negociado"],
                "Adiantamento (R$)": v["valor_adiantamento"],
                "Saldo (R$)": v["valor_saldo"],
                "Total Recebido (R$)": v["total_recebido"],
                "Despesas Totais (R$)": v["total_despesas"],
                "Resultado Líquido (R$)": v["resultado_liquido"],
                "Margem (%)": round(v["margem_pct"], 2),
                "KM Rodado": v["km_rodado"],
                "Custo por KM (R$)": round(v["custo_km"], 2),
            }
            for v in todas_viagens
        ]
    )

    df_desp = pd.DataFrame(desp_detalhadas)
    df_mot = pd.DataFrame(motoristas)
    df_vei = pd.DataFrame(veiculos)
    df_cli = pd.DataFrame(clientes)
    df_loc = pd.DataFrame(locais)
    df_forn = pd.DataFrame(fornecedores)

    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_viagens.to_excel(writer, sheet_name="Viagens_e_Ciclos", index=False)
        df_desp.to_excel(writer, sheet_name="Despesas_Viagens", index=False)
        df_mot.to_excel(writer, sheet_name="Cad_Motoristas", index=False)
        df_vei.to_excel(writer, sheet_name="Cad_Veiculos", index=False)
        df_cli.to_excel(writer, sheet_name="Cad_Clientes", index=False)
        df_loc.to_excel(writer, sheet_name="Cad_Locais", index=False)
        df_forn.to_excel(writer, sheet_name="Cad_Fornecedores", index=False)

    return buf.getvalue()


def obter_caminho_logo():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidatos = [
        os.path.join(base_dir, "assets", "logo_faeg.png"),
        os.path.join(base_dir, "logo_faeg.png"),
        os.path.join(base_dir, "assets", "logo_faeg.jpg"),
        os.path.join(base_dir, "assets", "logo_faeg.svg"),
        "assets/logo_faeg.png",
        "logo_faeg.png",
    ]
    for path in candidatos:
        if os.path.exists(path):
            return path
    return None


def carregar_logo_base64():
    """Carrega o logotipo dinamicamente sempre refletindo o arquivo mais recente."""
    path = obter_caminho_logo()
    if path:
        ext = os.path.splitext(path)[1].lower().replace(".", "")
        mime = "svg+xml" if ext == "svg" else ("jpeg" if ext in ["jpg", "jpeg"] else "png")
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/{mime};base64,{b64}"
    return None


# ==============================================================================
# GERADOR DE PDF NATIVO ZERO-DEPENDÊNCIA (PADRÃO VISUAL FAEG)
# ==============================================================================
def _pdf_esc(txt):
    if txt is None:
        return "-"
    s = str(txt).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return s.encode("latin-1", "replace").decode("latin-1")


def _compilar_pdf_pagina_unica(cmds):
    stream_bytes = "\n".join(cmds).encode("latin-1", "replace")
    compressed = zlib.compress(stream_bytes)

    objs = []
    objs.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    objs.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    objs.append(
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>\nendobj\n"
    )
    objs.append(b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>\nendobj\n")
    objs.append(
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>\nendobj\n"
    )
    objs.append(
        f"6 0 obj\n<< /Length {len(compressed)} /Filter /FlateDecode >>\nstream\n".encode("ascii")
        + compressed
        + b"\nendstream\nendobj\n"
    )

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objs:
        offsets.append(out.tell())
        out.write(obj)
    xref_pos = out.tell()
    out.write(f"xref\n0 {len(objs) + 1}\n".encode("ascii"))
    out.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.write(f"{off:010d} 00000 n \n".encode("ascii"))
    out.write(
        f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode("ascii")
    )
    return out.getvalue()


def gerar_pdf_relatorio(dados_resumo, despesas_lista):
    cmds = []

    def rect(x, y_top, w, h, r, g, b):
        y = 842 - y_top - h
        cmds.append(f"{r:.3f} {g:.3f} {b:.3f} rg {x:.1f} {y:.1f} {w:.1f} {h:.1f} re f")

    def text(x, y_top, txt, size=10, bold=False, r=0.051, g=0.149, b=0.235):
        y = 842 - y_top
        font = "/F2" if bold else "/F1"
        cmds.append(
            f"BT {font} {size} Tf {r:.3f} {g:.3f} {b:.3f} rg {x:.1f} {y:.1f} Td ({_pdf_esc(txt)}) Tj ET"
        )

    rect(0, 0, 595, 76, 0.051, 0.149, 0.235)
    rect(0, 76, 595, 5, 0.953, 0.302, 0.145)
    text(40, 34, "FAEG — GESTAO LOGISTICA E OPERACIONAL", size=15, bold=True, r=1, g=1, b=1)
    text(
        40,
        54,
        "Demonstrativo Operacional e Financeiro da Viagem (DRE)",
        size=10,
        bold=False,
        r=0.671,
        g=0.808,
        b=0.882,
    )
    text(440, 54, f"Emissao: {date.today().strftime('%d/%m/%Y')}", size=9, bold=False, r=0.914, g=0.914, b=0.914)

    rect(40, 98, 515, 22, 0.914, 0.914, 0.914)
    text(48, 113, "1. RESUMO DA OPERACAO", size=10, bold=True)

    y = 136
    pares_op = [
        ("Codigo Viagem:", dados_resumo["codigo"], "ID Frete:", dados_resumo["id_frete"]),
        ("Cliente:", dados_resumo["cliente"], "Ciclo:", dados_resumo["ciclo"]),
        ("Motorista:", dados_resumo["motorista"], "Veiculo / Placa:", dados_resumo["veiculo"]),
        ("Origem:", dados_resumo["origem"], "Destino:", dados_resumo["destino"]),
        ("Tipo Viagem:", dados_resumo["tipo_viagem"], "Tipo / Origem Frete:", dados_resumo["frete_info"]),
        ("Situacao:", dados_resumo["status"], "KM Real Rodado:", f"{dados_resumo['km_real']} km"),
    ]
    for l1, v1, l2, v2 in pares_op:
        text(42, y, l1, size=9, bold=True, r=0.35, g=0.40, b=0.48)
        text(128, y, str(v1)[:34], size=9, bold=False)
        text(310, y, l2, size=9, bold=True, r=0.35, g=0.40, b=0.48)
        text(412, y, str(v2)[:30], size=9, bold=False)
        y += 18

    y += 10
    rect(40, y, 515, 22, 0.914, 0.914, 0.914)
    text(48, y + 15, "2. FECHAMENTO FINANCEIRO (DRE) E INDICADORES (KPIs)", size=10, bold=True)
    y += 38

    rect(40, y - 14, 515, 92, 0.051, 0.149, 0.235)
    text(55, y + 4, "Receita Total Considerada:", size=10, bold=False, r=0.671, g=0.808, b=0.882)
    text(390, y + 4, dados_resumo["receita_fmt"], size=11, bold=True, r=1, g=1, b=1)
    y += 22
    text(55, y + 4, "Custos Totais de Viagem:", size=10, bold=False, r=0.671, g=0.808, b=0.882)
    text(390, y + 4, f"- {dados_resumo['despesa_fmt']}", size=11, bold=True, r=0.953, g=0.302, b=0.145)
    y += 26
    text(55, y + 4, "RESULTADO LIQUIDO:", size=11, bold=True, r=1, g=1, b=1)
    text(390, y + 4, dados_resumo["resultado_fmt"], size=13, bold=True, r=1, g=1, b=1)
    y += 34

    text(42, y, f"Custo por KM: {dados_resumo['custo_km_fmt']}", size=10, bold=True)
    text(250, y, f"Margem de Lucro: {dados_resumo['margem_fmt']}", size=10, bold=True)
    text(420, y, f"Recebido: {dados_resumo['recebido_fmt']}", size=9, bold=False)
    y += 24

    rect(40, y, 515, 22, 0.914, 0.914, 0.914)
    text(48, y + 15, "3. DETALHAMENTO DE DESPESAS DA VIAGEM", size=10, bold=True)
    y += 36

    rect(40, y - 12, 515, 18, 0.051, 0.149, 0.235)
    text(46, y, "Categoria", size=8, bold=True, r=1, g=1, b=1)
    text(175, y, "Descricao / Local", size=8, bold=True, r=1, g=1, b=1)
    text(370, y, "Qtd", size=8, bold=True, r=1, g=1, b=1)
    text(420, y, "Unitario", size=8, bold=True, r=1, g=1, b=1)
    text(488, y, "Total", size=8, bold=True, r=1, g=1, b=1)
    y += 18

    if not despesas_lista:
        text(46, y, "Nenhuma despesa lancada nesta viagem.", size=9, bold=False)
    else:
        for idx_d, d in enumerate(despesas_lista[:22]):
            if idx_d % 2 == 1:
                rect(40, y - 11, 515, 16, 0.965, 0.972, 0.985)
            text(46, y, str(d["tipo"])[:22], size=8)
            text(175, y, str(d["desc"])[:34], size=8)
            text(370, y, f"{d['qtd']:.2f}", size=8)
            text(420, y, d["unit_fmt"], size=8)
            text(488, y, d["total_fmt"], size=8, bold=True)
            y += 16
            if y > 790:
                break

    return _compilar_pdf_pagina_unica(cmds)


def gerar_pdf_relatorio_consolidado(resumo_geral, ranking_clientes, despesas_categorias):
    """Gera PDF executivo consolidado do Painel Geral / BI Operacional FAEG."""
    cmds = []

    def rect(x, y_top, w, h, r, g, b):
        y = 842 - y_top - h
        cmds.append(f"{r:.3f} {g:.3f} {b:.3f} rg {x:.1f} {y:.1f} {w:.1f} {h:.1f} re f")

    def text(x, y_top, txt, size=10, bold=False, r=0.051, g=0.149, b=0.235):
        y = 842 - y_top
        font = "/F2" if bold else "/F1"
        cmds.append(
            f"BT {font} {size} Tf {r:.3f} {g:.3f} {b:.3f} rg {x:.1f} {y:.1f} Td ({_pdf_esc(txt)}) Tj ET"
        )

    rect(0, 0, 595, 76, 0.051, 0.149, 0.235)
    rect(0, 76, 595, 5, 0.953, 0.302, 0.145)
    text(40, 34, "FAEG — RELATORIO EXECUTIVO CONSOLIDADO (BI)", size=14, bold=True, r=1, g=1, b=1)
    text(
        40,
        54,
        f"Filtro aplicado: {resumo_geral['filtro_desc']}",
        size=9,
        bold=False,
        r=0.671,
        g=0.808,
        b=0.882,
    )
    text(440, 54, f"Emissao: {date.today().strftime('%d/%m/%Y')}", size=9, bold=False, r=0.914, g=0.914, b=0.914)

    rect(40, 96, 515, 22, 0.914, 0.914, 0.914)
    text(48, 111, "1. INDICADORES GLOBAIS DA OPERACAO", size=10, bold=True)

    y = 136
    rect(40, y - 12, 515, 96, 0.051, 0.149, 0.235)
    text(55, y + 6, f"Total de Viagens: {resumo_geral['qtd_viagens']}", size=10, bold=True, r=0.671, g=0.808, b=0.882)
    text(310, y + 6, f"KM Total Rodado: {resumo_geral['km_total']} km", size=10, bold=True, r=0.671, g=0.808, b=0.882)
    y += 24
    text(55, y + 6, "Receita Consolidada:", size=10, bold=False, r=1, g=1, b=1)
    text(210, y + 6, resumo_geral["receita_fmt"], size=10, bold=True, r=1, g=1, b=1)
    text(340, y + 6, "Despesas Totais:", size=10, bold=False, r=1, g=1, b=1)
    text(445, y + 6, resumo_geral["despesa_fmt"], size=10, bold=True, r=0.953, g=0.302, b=0.145)
    y += 26
    text(55, y + 6, "RESULTADO LIQUIDO CONSOLIDADO:", size=10, bold=True, r=1, g=1, b=1)
    text(275, y + 6, resumo_geral["resultado_fmt"], size=12, bold=True, r=1, g=1, b=1)
    text(430, y + 6, f"Margem: {resumo_geral['margem_fmt']}", size=10, bold=True, r=0.671, g=0.808, b=0.882)

    y += 42
    rect(40, y, 515, 22, 0.914, 0.914, 0.914)
    text(48, y + 15, "2. DESEMPENHO CONSOLIDADO POR CLIENTE", size=10, bold=True)
    y += 34

    rect(40, y - 12, 515, 18, 0.051, 0.149, 0.235)
    text(46, y, "Cliente", size=8, bold=True, r=1, g=1, b=1)
    text(245, y, "Viagens", size=8, bold=True, r=1, g=1, b=1)
    text(300, y, "Receita", size=8, bold=True, r=1, g=1, b=1)
    text(385, y, "Despesas", size=8, bold=True, r=1, g=1, b=1)
    text(470, y, "Resultado", size=8, bold=True, r=1, g=1, b=1)
    y += 18

    if not ranking_clientes:
        text(46, y, "Sem dados para exibir.", size=9)
        y += 18
    else:
        for idx_c, rc in enumerate(ranking_clientes[:10]):
            if idx_c % 2 == 1:
                rect(40, y - 11, 515, 16, 0.965, 0.972, 0.985)
            text(46, y, str(rc["cliente"])[:34], size=8)
            text(255, y, str(rc["viagens"]), size=8)
            text(300, y, rc["receita_fmt"], size=8)
            text(385, y, rc["despesa_fmt"], size=8)
            text(470, y, rc["resultado_fmt"], size=8, bold=True)
            y += 16

    y += 14
    rect(40, y, 515, 22, 0.914, 0.914, 0.914)
    text(48, y + 15, "3. DISTRIBUICAO CONSOLIDADA DE DESPESAS POR CATEGORIA", size=10, bold=True)
    y += 34

    rect(40, y - 12, 515, 18, 0.051, 0.149, 0.235)
    text(46, y, "Categoria de Despesa", size=8, bold=True, r=1, g=1, b=1)
    text(330, y, "Participacao (%)", size=8, bold=True, r=1, g=1, b=1)
    text(455, y, "Total Acumulado", size=8, bold=True, r=1, g=1, b=1)
    y += 18

    if not despesas_categorias:
        text(46, y, "Nenhuma despesa registrada no filtro atual.", size=9)
    else:
        for idx_cat, dc in enumerate(despesas_categorias[:10]):
            if idx_cat % 2 == 1:
                rect(40, y - 11, 515, 16, 0.965, 0.972, 0.985)
            text(46, y, str(dc["categoria"])[:42], size=8)
            text(340, y, dc["pct_fmt"], size=8)
            text(455, y, dc["total_fmt"], size=8, bold=True)
            y += 16
            if y > 795:
                break

    return _compilar_pdf_pagina_unica(cmds)


# ==============================================================================
# NAVEGAÇÃO SEGURA VIA CALLBACK E ESTADO DA VIAGEM
# ==============================================================================
def _mudar_aba_callback(nova_aba):
    st.session_state["menu_operacional_radio"] = nova_aba


def _abrir_viagem_para_edicao(id_v, destino_aba):
    st.session_state["viagem_ativa_id"] = id_v
    st.session_state["loaded_viagem_id"] = None
    st.session_state["menu_operacional_radio"] = destino_aba


def _iniciar_nova_viagem():
    st.session_state["viagem_ativa_id"] = 0
    st.session_state["loaded_viagem_id"] = None
    st.session_state["despesas_temp"] = []
    st.session_state["menu_operacional_radio"] = "1. Frota FAEG"


def render_navegacao_rodape(idx_atual, menu_itens):
    st.markdown("<hr style='margin: 1.6rem 0 1rem 0; border-color: #E9E9E9;'>", unsafe_allow_html=True)
    n1, _, n3 = st.columns([1.2, 3, 1.2])
    if idx_atual > 0:
        n1.button(
            "← Etapa Anterior",
            key=f"prev_step_{idx_atual}",
            use_container_width=True,
            on_click=_mudar_aba_callback,
            args=(menu_itens[idx_atual - 1],),
        )
    if idx_atual < len(menu_itens) - 1:
        n3.button(
            "Próxima Etapa →",
            key=f"next_step_{idx_atual}",
            use_container_width=True,
            on_click=_mudar_aba_callback,
            args=(menu_itens[idx_atual + 1],),
        )


def limpar_widgets_viagem():
    for k in list(st.session_state.keys()):
        if k.startswith("w_"):
            del st.session_state[k]


def carregar_estado_viagem(id_viagem_escolhida, viagens_lista):
    if st.session_state.get("loaded_viagem_id") == id_viagem_escolhida and "form_data" in st.session_state:
        return

    limpar_widgets_viagem()
    if id_viagem_escolhida == 0:
        prox_cod = calcular_proximo_codigo_viagem(viagens_lista)
        st.session_state["form_data"] = {
            "id_viagem_label": prox_cod,
            "mot_id": 0,
            "vei_id": 0,
            "id_frete": "",
            "data_op": date.today(),
            "ciclo_nome": "",
            "tipo_viagem": "Individual",
            "tipo_frete": "Dedicado",
            "rota_origem": "",
            "rota_destino": "",
            "km_rota": 0.0,
            "tipo_material": "",
            "qt_volumes": 0,
            "volume_m3": 0.0,
            "peso_kg": 0.0,
            "nfe": "",
            "cte": "",
            "mdfe": "",
            "ciot": "",
            "cli_id": 0,
            "forma_contrat": OPCOES_ORIGEM_FRETE[0],
            "valor_divulgado": 0.0,
            "valor_negociado": 0.0,
            "perc_adiant": 0.0,
            "data_adiant": None,
            "valor_adiant": 0.0,
            "perc_saldo": 0.0,
            "data_saldo": None,
            "valor_saldo": 0.0,
            "col_id": 0,
            "data_coleta": date.today(),
            "hora_plan_col": None,
            "hora_real_col": None,
            "ent_id": 0,
            "data_entrega": date.today(),
            "hora_plan_ent": None,
            "hora_real_ent": None,
            "odo_ini": 0,
            "odo_fin": 0,
            "status_viagem": "Aguardando Adiantamento",
        }
        st.session_state["despesas_temp"] = []
    else:
        with SessionLocal() as session:
            vg = session.query(Viagem).filter_by(id_viagem=id_viagem_escolhida).first()
            if vg:
                ciclo = vg.ciclo
                fin = ciclo.financeiro if ciclo else None
                ciclo_exib = ciclo.nome_operacao if ciclo else ""
                if ciclo_exib.startswith("Individual - "):
                    ciclo_exib = ""

                tipo_vg_db = getattr(vg, "tipo_viagem", None) or (
                    vg.tipo_frete if vg.tipo_frete in ["Individual", "Ciclo"] else "Individual"
                )
                tipo_fr_db = vg.tipo_frete if vg.tipo_frete not in ["Individual", "Ciclo"] else "Dedicado"
                if tipo_vg_db == "Individual":
                    ciclo_exib = ""

                origem_db = (getattr(vg, "rota_origem", None) or "").strip()
                destino_db = (getattr(vg, "rota_destino", None) or "").strip()
                if not origem_db and not destino_db and vg.rota_resumo and "->" in vg.rota_resumo:
                    partes_r = vg.rota_resumo.split("->", 1)
                    origem_db = partes_r[0].strip()
                    destino_db = partes_r[1].strip()

                st.session_state["form_data"] = {
                    "id_viagem_label": resolver_codigo_viagem(vg, ciclo),
                    "mot_id": vg.id_motorista or 0,
                    "vei_id": vg.id_veiculo or 0,
                    "id_frete": vg.id_frete_externo or "",
                    "data_op": vg.data_criacao.date() if vg.data_criacao else date.today(),
                    "ciclo_nome": ciclo_exib,
                    "tipo_viagem": tipo_vg_db,
                    "tipo_frete": tipo_fr_db,
                    "rota_origem": origem_db,
                    "rota_destino": destino_db,
                    "km_rota": to_float(vg.km_rota_planejado),
                    "tipo_material": vg.tipo_material or "",
                    "qt_volumes": to_int(vg.qtde_volumes),
                    "volume_m3": to_float(vg.volume_m3),
                    "peso_kg": to_float(vg.peso_bruto_kg),
                    "nfe": vg.nfe_carga or "",
                    "cte": vg.cte_numero or "",
                    "mdfe": vg.mdfe_numero or "",
                    "ciot": vg.ciot_numero or "",
                    "cli_id": ciclo.id_cliente if ciclo else 0,
                    "forma_contrat": fin.forma_contratacao if fin else OPCOES_ORIGEM_FRETE[0],
                    "valor_divulgado": to_float(fin.valor_divulgado) if fin else 0.0,
                    "valor_negociado": to_float(fin.valor_negociado_total) if fin else 0.0,
                    "perc_adiant": to_float(fin.perc_adiantamento) if fin else 0.0,
                    "data_adiant": fin.data_prevista_adiantamento if fin else None,
                    "valor_adiant": to_float(fin.valor_adiantamento) if fin else 0.0,
                    "perc_saldo": to_float(fin.perc_saldo) if fin else 0.0,
                    "data_saldo": fin.data_prevista_saldo if fin else None,
                    "valor_saldo": to_float(fin.valor_saldo) if fin else 0.0,
                    "col_id": vg.id_local_coleta or 0,
                    "data_coleta": vg.data_coleta or date.today(),
                    "hora_plan_col": vg.hora_planejada_coleta,
                    "hora_real_col": vg.hora_real_coleta,
                    "ent_id": vg.id_local_entrega or 0,
                    "data_entrega": vg.data_entrega or date.today(),
                    "hora_plan_ent": vg.hora_planejada_entrega,
                    "hora_real_ent": vg.hora_real_entrega,
                    "odo_ini": to_int(vg.odometro_inicial),
                    "odo_fin": to_int(vg.odometro_final),
                    "status_viagem": vg.status_viagem or "Aguardando Adiantamento",
                }
        st.session_state["despesas_temp"] = []

    st.session_state["loaded_viagem_id"] = id_viagem_escolhida


def salvar_viagem_completa(id_viagem_atual, viagens_lista):
    mot_id = get_campo("mot_id", 0)
    vei_id = get_campo("vei_id", 0)
    cli_id = get_campo("cli_id", 0)
    col_id = get_campo("col_id", 0)
    ent_id = get_campo("ent_id", 0)
    tipo_viagem_val = get_campo("tipo_viagem", "Individual")
    tipo_frete_val = get_campo("tipo_frete", "Dedicado")
    ciclo_num_val = (get_campo("ciclo_nome") or "").strip()

    prox_cod = calcular_proximo_codigo_viagem(viagens_lista)
    codigo_digitado = (get_campo("id_viagem_label") or prox_cod).strip().upper()
    if not codigo_digitado:
        codigo_digitado = prox_cod

    for vg_item in viagens_lista:
        if vg_item["id_viagem"] != id_viagem_atual and vg_item["codigo_viagem"].upper() == codigo_digitado:
            st.error(
                f"Já existe uma viagem salva com o código '{codigo_digitado}'. "
                f"Informe um código único (sugestão: {prox_cod})."
            )
            return

    if not all([mot_id, vei_id, cli_id, col_id, ent_id]):
        st.error(
            "Para salvar a viagem, selecione obrigatoriamente: Motorista (1), Veículo (1), "
            "Cliente (3), Local de Coleta (5) e Local de Entrega (6)."
        )
        return

    if tipo_viagem_val == "Ciclo" and not ciclo_num_val:
        st.error("Quando o Tipo de Viagem for 'Ciclo', preencha o 'Nº do Ciclo Operacional' na Etapa 1.")
        return

    odo_ini = to_int(get_campo("odo_ini", 0))
    odo_fin = to_int(get_campo("odo_fin", 0))
    km_real = max(0, odo_fin - odo_ini)
    nome_ciclo = ciclo_num_val if tipo_viagem_val == "Ciclo" else f"Individual - {codigo_digitado}"

    origem_val = (get_campo("rota_origem") or "").strip()
    destino_val = (get_campo("rota_destino") or "").strip()
    rota_resumo_val = formatar_rota_exibicao(origem_val, destino_val)

    try:
        with SessionLocal() as session:
            if id_viagem_atual == 0:
                ciclo = CicloOperacional(
                    id_cliente=cli_id,
                    nome_operacao=nome_ciclo,
                    data_abertura=get_campo("data_op", date.today()),
                    status_ciclo=f"COD::{codigo_digitado}",
                )
                session.add(ciclo)
                session.flush()

                fin = CicloFinanceiro(
                    id_ciclo=ciclo.id_ciclo,
                    forma_contratacao=get_campo("forma_contrat", OPCOES_ORIGEM_FRETE[0]),
                    valor_divulgado=to_float(get_campo("valor_divulgado", 0.0)),
                    valor_negociado_total=to_float(get_campo("valor_negociado", 0.0)),
                    perc_adiantamento=to_float(get_campo("perc_adiant", 0.0)),
                    data_prevista_adiantamento=get_campo("data_adiant"),
                    valor_adiantamento=to_float(get_campo("valor_adiant", 0.0)),
                    perc_saldo=to_float(get_campo("perc_saldo", 0.0)),
                    data_prevista_saldo=get_campo("data_saldo"),
                    valor_saldo=to_float(get_campo("valor_saldo", 0.0)),
                )
                session.add(fin)

                vg = Viagem(
                    id_ciclo=ciclo.id_ciclo,
                    id_motorista=mot_id,
                    id_veiculo=vei_id,
                    id_local_coleta=col_id,
                    id_local_entrega=ent_id,
                    codigo_viagem=codigo_digitado,
                    id_frete_externo=get_campo("id_frete") or None,
                    status_viagem=get_campo("status_viagem", "Aguardando Adiantamento"),
                    tipo_viagem=tipo_viagem_val,
                    tipo_frete=tipo_frete_val,
                    rota_origem=origem_val or None,
                    rota_destino=destino_val or None,
                    rota_resumo=rota_resumo_val or None,
                    km_rota_planejado=to_float(get_campo("km_rota", 0.0)),
                    tipo_material=get_campo("tipo_material") or None,
                    qtde_volumes=to_int(get_campo("qt_volumes", 0)),
                    volume_m3=to_float(get_campo("volume_m3", 0.0)),
                    peso_bruto_kg=to_float(get_campo("peso_kg", 0.0)),
                    nfe_carga=get_campo("nfe") or None,
                    cte_numero=get_campo("cte") or None,
                    mdfe_numero=get_campo("mdfe") or None,
                    ciot_numero=get_campo("ciot") or None,
                    data_coleta=get_campo("data_coleta"),
                    hora_planejada_coleta=get_campo("hora_plan_col"),
                    hora_real_coleta=get_campo("hora_real_col"),
                    data_entrega=get_campo("data_entrega"),
                    hora_planejada_entrega=get_campo("hora_plan_ent"),
                    hora_real_entrega=get_campo("hora_real_ent"),
                    odometro_inicial=odo_ini,
                    odometro_final=odo_fin,
                    km_real_rodado=km_real,
                )
                session.add(vg)
                session.flush()

                for dt in st.session_state.get("despesas_temp", []):
                    session.add(
                        ViagemDespesa(
                            id_viagem=vg.id_viagem,
                            id_fornecedor=dt["id_fornecedor"] if dt["id_fornecedor"] != 0 else None,
                            tipo_despesa=dt["tipo_despesa"],
                            descricao_detalhe=dt["descricao_detalhe"],
                            quantidade=dt["quantidade"],
                            valor_unitario=dt["valor_unitario"],
                            valor_total=dt["valor_total"],
                        )
                    )
                session.commit()
                st.session_state["viagem_ativa_id"] = vg.id_viagem
                st.session_state["loaded_viagem_id"] = None
                st.session_state["despesas_temp"] = []
                carregar_listas_base.clear()
                carregar_despesas_viagem.clear()
                carregar_todas_viagens_consulta.clear()
                st.toast(f"Viagem {codigo_digitado} salva com sucesso no Neon!", icon="✅")
                st.rerun()
            else:
                vg = session.query(Viagem).filter_by(id_viagem=id_viagem_atual).first()
                if vg:
                    vg.codigo_viagem = codigo_digitado
                    vg.id_motorista = mot_id
                    vg.id_veiculo = vei_id
                    vg.id_local_coleta = col_id
                    vg.id_local_entrega = ent_id
                    vg.id_frete_externo = get_campo("id_frete") or None
                    vg.status_viagem = get_campo("status_viagem", "Aguardando Adiantamento")
                    vg.tipo_viagem = tipo_viagem_val
                    vg.tipo_frete = tipo_frete_val
                    vg.rota_origem = origem_val or None
                    vg.rota_destino = destino_val or None
                    vg.rota_resumo = rota_resumo_val or None
                    vg.km_rota_planejado = to_float(get_campo("km_rota", 0.0))
                    vg.tipo_material = get_campo("tipo_material") or None
                    vg.qtde_volumes = to_int(get_campo("qt_volumes", 0))
                    vg.volume_m3 = to_float(get_campo("volume_m3", 0.0))
                    vg.peso_bruto_kg = to_float(get_campo("peso_kg", 0.0))
                    vg.nfe_carga = get_campo("nfe") or None
                    vg.cte_numero = get_campo("cte") or None
                    vg.mdfe_numero = get_campo("mdfe") or None
                    vg.ciot_numero = get_campo("ciot") or None
                    vg.data_coleta = get_campo("data_coleta")
                    vg.hora_planejada_coleta = get_campo("hora_plan_col")
                    vg.hora_real_coleta = get_campo("hora_real_col")
                    vg.data_entrega = get_campo("data_entrega")
                    vg.hora_planejada_entrega = get_campo("hora_plan_ent")
                    vg.hora_real_entrega = get_campo("hora_real_ent")
                    vg.odometro_inicial = odo_ini
                    vg.odometro_final = odo_fin
                    vg.km_real_rodado = km_real

                    if vg.ciclo:
                        vg.ciclo.id_cliente = cli_id
                        vg.ciclo.nome_operacao = nome_ciclo
                        vg.ciclo.status_ciclo = f"COD::{codigo_digitado}"
                        if vg.ciclo.financeiro:
                            fin = vg.ciclo.financeiro
                            fin.forma_contratacao = get_campo("forma_contrat", OPCOES_ORIGEM_FRETE[0])
                            fin.valor_divulgado = to_float(get_campo("valor_divulgado", 0.0))
                            fin.valor_negociado_total = to_float(get_campo("valor_negociado", 0.0))
                            fin.perc_adiantamento = to_float(get_campo("perc_adiant", 0.0))
                            fin.data_prevista_adiantamento = get_campo("data_adiant")
                            fin.valor_adiantamento = to_float(get_campo("valor_adiant", 0.0))
                            fin.perc_saldo = to_float(get_campo("perc_saldo", 0.0))
                            fin.data_prevista_saldo = get_campo("data_saldo")
                            fin.valor_saldo = to_float(get_campo("valor_saldo", 0.0))
                    session.commit()
                    st.session_state["loaded_viagem_id"] = None
                    carregar_listas_base.clear()
                    carregar_despesas_viagem.clear()
                    carregar_todas_viagens_consulta.clear()
                    st.toast(f"Alterações da viagem {codigo_digitado} atualizadas!", icon="✅")
                    st.rerun()
    except IntegrityError:
        st.error(f"Não foi possível salvar: o código '{codigo_digitado}' já está em uso por outra viagem.")


# ==============================================================================
# LEITURA RÁPIDA EM CACHE DAS BASES
# ==============================================================================
motoristas_db, veiculos_db, clientes_db, locais_db, fornecedores_db, viagens_db = carregar_listas_base()

if "viagem_ativa_id" not in st.session_state:
    st.session_state["viagem_ativa_id"] = 0

viagem_sel_id = st.session_state["viagem_ativa_id"]
carregar_estado_viagem(viagem_sel_id, viagens_db)

# ==============================================================================
# SIDEBAR INSTITUCIONAL FAEG (APENAS LOGO COM SLOGAN)
# ==============================================================================
with st.sidebar:
    logo_b64 = carregar_logo_base64()
    if logo_b64:
        icone_marca_html = f'<img src="{logo_b64}" class="sidebar-logo-img" alt="FAEG" />'
    else:
        icone_marca_html = '<div class="sidebar-monogram-fallback">FAEG</div>'

    st.markdown(
        f"""
        <div class="sidebar-brand">
            {icone_marca_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

    prox_cod_sidebar = calcular_proximo_codigo_viagem(viagens_db)
    cod_ativo_sidebar = get_campo("id_viagem_label", prox_cod_sidebar)
    tag_modo_sidebar = "Criando Nova Viagem" if viagem_sel_id == 0 else "Editando Viagem Salva"

    st.markdown(
        f"""
        <div class="sidebar-active-trip-card">
            <div class="sidebar-active-trip-tag">{tag_modo_sidebar}</div>
            <div class="sidebar-active-trip-code">{cod_ativo_sidebar}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if viagem_sel_id != 0:
        st.button(
            "➕ Iniciar Nova Viagem",
            type="secondary",
            use_container_width=True,
            on_click=_iniciar_nova_viagem,
        )

    st.markdown(
        "<hr style='margin: 0.7rem 0 0.6rem 0; border-color: rgba(171, 206, 225, 0.2);'>",
        unsafe_allow_html=True,
    )

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
        "10. Consultas Gerais",
        "11. Cadastros Gerais",
    ]
    aba_ativa = st.radio(
        "Menu Operacional",
        MENU_ITENS,
        key="menu_operacional_radio",
        label_visibility="collapsed",
    )

    st.markdown(
        "<hr style='margin: 0.9rem 0 0.9rem 0; border-color: rgba(171, 206, 225, 0.2);'>",
        unsafe_allow_html=True,
    )

    if st.button("Salvar Viagem", type="primary", use_container_width=True):
        salvar_viagem_completa(viagem_sel_id, viagens_db)

# ==============================================================================
# BARRA SUPERIOR DE CONTEXTO EXECUTIVO
# ==============================================================================
cli_obj_ctx = next((c for c in clientes_db if c["id_cliente"] == get_campo("cli_id", 0)), None)
cli_nome_ctx = (
    f"{cli_obj_ctx['razao_social']}"
    + (f" ({cli_obj_ctx['nome_fantasia']})" if cli_obj_ctx.get("nome_fantasia") else "")
    if cli_obj_ctx
    else "Não selecionado"
)
mot_nome_ctx = next(
    (m["nome_completo"] for m in motoristas_db if m["id_motorista"] == get_campo("mot_id", 0)),
    "Não selecionado",
)
rota_ctx = (
    formatar_rota_exibicao(get_campo("rota_origem", ""), get_campo("rota_destino", ""))
    or "Rota não definida"
)
status_ctx = get_campo("status_viagem", "Aguardando Adiantamento")
id_label_ctx = get_campo("id_viagem_label", prox_cod_sidebar)

st.markdown(
    f"""
    <div class="top-context-bar">
        <div class="ctx-item">
            <span class="ctx-label">Código da Viagem</span>
            <span class="ctx-val">{id_label_ctx}</span>
        </div>
        <div class="ctx-item">
            <span class="ctx-label">Cliente Contratante</span>
            <span class="ctx-val">{cli_nome_ctx}</span>
        </div>
        <div class="ctx-item">
            <span class="ctx-label">Motorista Responsável</span>
            <span class="ctx-val">{mot_nome_ctx}</span>
        </div>
        <div class="ctx-item">
            <span class="ctx-label">Trecho / Rota</span>
            <span class="ctx-val">{rota_ctx}</span>
        </div>
        <div>
            <span class="ctx-badge">{status_ctx}</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ==============================================================================
# ÁREA DE CONTEÚDO PRINCIPAL (CARTÃO BRANCO #FFFFFF)
# ==============================================================================
with st.container(border=True):
    st.markdown('<div class="main-card-marker"></div>', unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # ETAPA 1: FROTA FAEG + UPLOAD/IMPORTAÇÃO DA PLANILHA
    # --------------------------------------------------------------------------
    if aba_ativa == "1. Frota FAEG":
        st.markdown(
            """
            <div class="tab-header-wrap">
                <div class="tab-title"><i class="fa-solid fa-truck"></i> Informações FAEG</div>
                <span class="tab-step-pill">Etapa 1 de 11</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Bloco de Upload e Importação da Planilha FAEG (.xlsx)
        with st.expander("📥 Importar e Conciliar Planilha de Controle de Fretes (.xlsx)", expanded=False):
            st.caption(
                "Envie a planilha operacional da FAEG para importar viagens, receitas e despesas diretamente no banco "
                "com os mesmos valores financeiros da planilha. Cadastros ausentes são criados automaticamente para "
                "edição posterior."
            )
            up_file = st.file_uploader(
                "Selecione o arquivo Excel (.xlsx)",
                type=["xlsx"],
                key="uploader_planilha_faeg",
            )
            if up_file is not None:
                file_bytes = up_file.getvalue()
                analise = analisar_planilha_faeg(file_bytes)
                if analise.get("erro"):
                    st.error(analise["erro"])
                else:
                    resumo_pl = analise["resumo"]
                    kp1, kp2, kp3, kp4 = st.columns(4)
                    kp1.metric("Viagens Detectadas", resumo_pl["total_viagens"])
                    kp2.metric("Receita Total Planilha", fmt_brl(resumo_pl["receita_total"]))
                    kp3.metric("Despesas Totais Planilha", fmt_brl(resumo_pl["despesas_totais"]))
                    kp4.metric("Resultado Líquido Planilha", fmt_brl(resumo_pl["resultado_liquido"]))

                    if analise.get("preview_df") is not None and not analise["preview_df"].empty:
                        st.dataframe(analise["preview_df"], use_container_width=True, hide_index=True)

                    if st.button(
                        "✅ Confirmar Importação e Salvar Registros no Banco",
                        key="btn_confirmar_import_planilha",
                        use_container_width=True,
                    ):
                        with SessionLocal() as session:
                            res_imp = importar_planilha_para_banco(session, analise["registros"])
                        carregar_listas_base.clear()
                        carregar_despesas_viagem.clear()
                        carregar_todas_viagens_consulta.clear()
                        st.session_state["loaded_viagem_id"] = None
                        st.success(
                            f"Importação concluída! {res_imp['importadas']} viagem(ns) gravada(s), "
                            f"{res_imp['atualizadas']} atualizada(s) e {res_imp['pendencias']} cadastro(s) "
                            f"pré-criado(s) para revisão."
                        )
                        if res_imp.get("avisos"):
                            with st.expander("Ver detalhes / pendências de cadastro para editar depois"):
                                for av in res_imp["avisos"]:
                                    st.write(f"- {av}")
                        st.rerun()

        c_id, c_tipo_vg, c_ciclo, c_data = st.columns([1.2, 1.3, 1.8, 1.2])
        with c_id:
            st.text_input(
                "CÓDIGO DA VIAGEM (ÚNICO) *",
                value=get_campo("id_viagem_label", prox_cod_sidebar),
                placeholder=f"Ex: {prox_cod_sidebar}",
                key="w_id_viagem_label",
                on_change=sync_campo,
                args=("w_id_viagem_label", "id_viagem_label"),
            )
        with c_tipo_vg:
            tipos_vg = ["Individual", "Ciclo"]
            tv_atual = get_campo("tipo_viagem", "Individual")
            st.selectbox(
                "TIPO DE VIAGEM",
                tipos_vg,
                index=tipos_vg.index(tv_atual) if tv_atual in tipos_vg else 0,
                key="w_tipo_viagem",
                on_change=on_tipo_viagem_change,
            )
        with c_ciclo:
            eh_ciclo = get_campo("tipo_viagem", "Individual") == "Ciclo"
            st.text_input(
                "Nº DO CICLO OPERACIONAL",
                value=get_campo("ciclo_nome", "") if eh_ciclo else "",
                placeholder="Ex: CICLO-01" if eh_ciclo else "Bloqueado (Viagem Individual)",
                disabled=not eh_ciclo,
                key="w_ciclo_nome",
                on_change=sync_campo,
                args=("w_ciclo_nome", "ciclo_nome"),
            )
        with c_data:
            st.date_input(
                "DATA OPERAÇÃO",
                value=get_campo("data_op", date.today()),
                format="DD/MM/YYYY",
                key="w_data_op",
                on_change=sync_campo,
                args=("w_data_op", "data_op"),
            )

        st.markdown('<div class="sec-subtitle">Dados do Motorista</div>', unsafe_allow_html=True)
        mot_ops = {0: "Selecione um motorista..."}
        for m in motoristas_db:
            mot_ops[m["id_motorista"]] = m["nome_completo"]

        mot_atual = get_campo("mot_id", 0)
        idx_mot = list(mot_ops.keys()).index(mot_atual) if mot_atual in mot_ops else 0

        m1, m2, m3 = st.columns([2.4, 1.3, 0.9])
        with m1:
            mot_sel = st.selectbox(
                "NOME DO MOTORISTA *",
                options=list(mot_ops.keys()),
                index=idx_mot,
                format_func=lambda x: mot_ops[x],
                key="w_mot_id",
                on_change=sync_campo,
                args=("w_mot_id", "mot_id"),
            )
        mot_obj = next((m for m in motoristas_db if m["id_motorista"] == mot_sel), None)
        with m2:
            st.text_input(
                "CNH (AUTOMÁTICO)",
                value=mot_obj["cnh_numero"] if mot_obj else "",
                disabled=True,
                key=f"prev_cnh_{mot_sel}",
            )
        with m3:
            st.text_input(
                "CATEGORIA",
                value=mot_obj["cnh_categoria"] if mot_obj else "",
                disabled=True,
                key=f"prev_cat_{mot_sel}",
            )

        st.markdown('<div class="sec-subtitle">Dados do Veículo</div>', unsafe_allow_html=True)
        vei_ops = {0: "Selecione o veículo..."}
        for v in veiculos_db:
            vei_ops[v["id_veiculo"]] = f"{v['descricao_marca']} ({v['placa']})"

        vei_atual = get_campo("vei_id", 0)
        idx_vei = list(vei_ops.keys()).index(vei_atual) if vei_atual in vei_ops else 0

        v1, v2, v3 = st.columns([2.4, 1.1, 1.1])
        with v1:
            vei_sel = st.selectbox(
                "VEÍCULO / CARRO *",
                options=list(vei_ops.keys()),
                index=idx_vei,
                format_func=lambda x: vei_ops[x],
                key="w_vei_id",
                on_change=sync_campo,
                args=("w_vei_id", "vei_id"),
            )
        vei_obj = next((v for v in veiculos_db if v["id_veiculo"] == vei_sel), None)
        with v2:
            st.text_input(
                "PLACA (AUTOMÁTICO)",
                value=vei_obj["placa"] if vei_obj else "",
                disabled=True,
                key=f"prev_placa_{vei_sel}",
            )
        with v3:
            st.text_input(
                "TIPO (AUTOMÁTICO)",
                value=vei_obj["tipo_veiculo"] if vei_obj else "",
                disabled=True,
                key=f"prev_tipo_{vei_sel}",
            )

        render_navegacao_rodape(0, MENU_ITENS)

    # --------------------------------------------------------------------------
    # ETAPA 2: FRETE, ROTA (ORIGEM / DESTINO), CARGA E DOCUMENTOS
    # --------------------------------------------------------------------------
    elif aba_ativa == "2. Frete e Docs":
        st.markdown(
            """
            <div class="tab-header-wrap">
                <div class="tab-title"><i class="fa-solid fa-file-invoice"></i> Frete, Carga e Documentos</div>
                <span class="tab-step-pill">Etapa 2 de 11</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        f1, f2, f3, f4, f5 = st.columns([1.1, 1.3, 1.6, 1.6, 1.0])
        with f1:
            st.text_input(
                "ID FRETE",
                value=get_campo("id_frete", ""),
                placeholder="Ex: FRT-102",
                key="w_id_frete",
                on_change=sync_campo,
                args=("w_id_frete", "id_frete"),
            )
        with f2:
            tipos_frete_ops = ["Dedicado", "Complemento", "Fracionado", "Retorno", "Transferência"]
            tf_atual = get_campo("tipo_frete", "Dedicado")
            st.selectbox(
                "TIPO DE FRETE",
                tipos_frete_ops,
                index=tipos_frete_ops.index(tf_atual) if tf_atual in tipos_frete_ops else 0,
                key="w_tipo_frete",
                on_change=sync_campo,
                args=("w_tipo_frete", "tipo_frete"),
            )
        with f3:
            st.text_input(
                "ORIGEM (CIDADE / UF)",
                value=get_campo("rota_origem", ""),
                placeholder="Ex: Suzano/SP",
                key="w_rota_origem",
                on_change=sync_campo,
                args=("w_rota_origem", "rota_origem"),
            )
        with f4:
            st.text_input(
                "DESTINO (CIDADE / UF)",
                value=get_campo("rota_destino", ""),
                placeholder="Ex: Rio de Janeiro/RJ",
                key="w_rota_destino",
                on_change=sync_campo,
                args=("w_rota_destino", "rota_destino"),
            )
        with f5:
            st.number_input(
                "KM X ROTA",
                min_value=0.0,
                step=10.0,
                value=to_float(get_campo("km_rota", 0.0)),
                key="w_km_rota",
                on_change=sync_campo,
                args=("w_km_rota", "km_rota"),
            )

        st.markdown('<div class="sec-subtitle">Detalhes da Carga</div>', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns([2.4, 1.0, 1.0, 1.2])
        with c1:
            st.text_input(
                "TIPO DE MATERIAL",
                value=get_campo("tipo_material", ""),
                placeholder="Ex: Bobinas, Paletes, Peças",
                key="w_tipo_material",
                on_change=sync_campo,
                args=("w_tipo_material", "tipo_material"),
            )
        with c2:
            st.number_input(
                "QT VOLUMES",
                min_value=0,
                step=1,
                value=to_int(get_campo("qt_volumes", 0)),
                key="w_qt_volumes",
                on_change=sync_campo,
                args=("w_qt_volumes", "qt_volumes"),
            )
        with c3:
            st.number_input(
                "VOLUME (M³)",
                min_value=0.0,
                step=1.0,
                format="%.2f",
                value=to_float(get_campo("volume_m3", 0.0)),
                key="w_volume_m3",
                on_change=sync_campo,
                args=("w_volume_m3", "volume_m3"),
            )
        with c4:
            st.number_input(
                "PESO BRUTO (KG)",
                min_value=0.0,
                step=100.0,
                format="%.2f",
                value=to_float(get_campo("peso_kg", 0.0)),
                key="w_peso_kg",
                on_change=sync_campo,
                args=("w_peso_kg", "peso_kg"),
            )

        st.markdown('<div class="sec-subtitle">Documentos Fiscais</div>', unsafe_allow_html=True)
        d1, d2, d3, d4 = st.columns(4)
        with d1:
            st.text_input(
                "NF-E / CARGA",
                value=get_campo("nfe", ""),
                placeholder="Número da NF-e",
                key="w_nfe",
                on_change=sync_campo,
                args=("w_nfe", "nfe"),
            )
        with d2:
            st.text_input(
                "CT-E (CONHECIMENTO)",
                value=get_campo("cte", ""),
                placeholder="Número do CT-e",
                key="w_cte",
                on_change=sync_campo,
                args=("w_cte", "cte"),
            )
        with d3:
            st.text_input(
                "MDF-E (MANIFESTO)",
                value=get_campo("mdfe", ""),
                placeholder="Número do MDF-e",
                key="w_mdfe",
                on_change=sync_campo,
                args=("w_mdfe", "mdfe"),
            )
        with d4:
            st.text_input(
                "CIOT",
                value=get_campo("ciot", ""),
                placeholder="Código CIOT",
                key="w_ciot",
                on_change=sync_campo,
                args=("w_ciot", "ciot"),
            )

        render_navegacao_rodape(1, MENU_ITENS)

    # --------------------------------------------------------------------------
    # ETAPA 3: CLIENTE CONTRATANTE
    # --------------------------------------------------------------------------
    elif aba_ativa == "3. Cliente":
        st.markdown(
            """
            <div class="tab-header-wrap">
                <div class="tab-title"><i class="fa-solid fa-building"></i> Cliente Contratante</div>
                <span class="tab-step-pill">Etapa 3 de 11</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        cli_ops = {0: "Selecione um cliente..."}
        for c in clientes_db:
            cli_ops[c["id_cliente"]] = formatar_rotulo_cliente(c)

        cli_atual = get_campo("cli_id", 0)
        idx_cli = list(cli_ops.keys()).index(cli_atual) if cli_atual in cli_ops else 0

        cl1, cl2, cl3 = st.columns([2.6, 1.5, 1.2])
        with cl1:
            cli_sel = st.selectbox(
                "EMPRESA CLIENTE (RAZÃO SOCIAL / FANTASIA / ENDEREÇO) *",
                options=list(cli_ops.keys()),
                index=idx_cli,
                format_func=lambda x: cli_ops[x],
                key="w_cli_id",
                on_change=on_cliente_select_change,
                args=(locais_db,),
            )
        cli_obj = next((c for c in clientes_db if c["id_cliente"] == cli_sel), None)
        with cl2:
            st.text_input(
                "RESPONSÁVEL",
                value=(cli_obj.get("responsavel_comercial") or "") if cli_obj else "",
                disabled=True,
                key=f"prev_cli_resp_{cli_sel}",
            )
        with cl3:
            st.text_input(
                "TELEFONE / CONTATO",
                value=(cli_obj.get("telefone_comercial") or "") if cli_obj else "",
                disabled=True,
                key=f"prev_cli_tel_{cli_sel}",
            )

        if cli_obj:
            end_cli_str = ", ".join(
                filter(
                    None,
                    [
                        cli_obj.get("endereco_completo"),
                        f"CEP {cli_obj['cep']}" if cli_obj.get("cep") else "",
                        f"{cli_obj.get('cidade') or ''}/{cli_obj.get('uf') or ''}".strip("/"),
                    ],
                )
            )
            st.markdown(
                f"""
                <div class="cliente-coleta-banner">
                    <strong>Endereço Cadastrado do Cliente:</strong> {end_cli_str or 'Não informado'}
                    &nbsp;|&nbsp; <strong>E-mail:</strong> {cli_obj.get('email_financeiro') or '-'}
                </div>
                """,
                unsafe_allow_html=True,
            )

        render_navegacao_rodape(2, MENU_ITENS)

    # --------------------------------------------------------------------------
    # ETAPA 4: NEGOCIAÇÃO E RECEBIMENTOS
    # --------------------------------------------------------------------------
    elif aba_ativa == "4. Negociação / Pgto":
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
                value=to_float(get_campo("valor_negociado", 0.0)),
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
                value=to_float(get_campo("perc_adiant", 0.0)),
                key="w_perc_adiant",
                on_change=on_perc_adiant_change,
            )
        with a2:
            st.date_input(
                "DATA ADIANTAMENTO",
                value=get_campo("data_adiant"),
                format="DD/MM/YYYY",
                key="w_data_adiant",
                on_change=sync_campo,
                args=("w_data_adiant", "data_adiant"),
            )
        with a3:
            st.number_input(
                "VALOR ADIANTAMENTO (R$)",
                min_value=0.0,
                step=100.0,
                format="%.2f",
                value=to_float(get_campo("valor_adiant", 0.0)),
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
                value=to_float(get_campo("perc_saldo", 0.0)),
                key="w_perc_saldo",
                on_change=on_perc_saldo_change,
            )
        with s2:
            st.date_input(
                "DATA SALDO",
                value=get_campo("data_saldo"),
                format="DD/MM/YYYY",
                key="w_data_saldo",
                on_change=sync_campo,
                args=("w_data_saldo", "data_saldo"),
            )
        with s3:
            st.number_input(
                "VALOR SALDO (R$)",
                min_value=0.0,
                step=100.0,
                format="%.2f",
                value=to_float(get_campo("valor_saldo", 0.0)),
                key="w_val_saldo",
                on_change=on_val_saldo_change,
            )

        total_rec_now = to_float(get_campo("valor_adiant", 0.0)) + to_float(get_campo("valor_saldo", 0.0))
        st.markdown(
            f"""
            <div class="faeg-recebimento-banner">
                <span class="faeg-recebimento-label">Valor Total Recebido (Adiant. + Saldo):</span>
                <span class="faeg-recebimento-val">{fmt_brl(total_rec_now)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        render_navegacao_rodape(3, MENU_ITENS)

    # --------------------------------------------------------------------------
    # ETAPA 5: LOCAL DE COLETA (ORIGEM)
    # --------------------------------------------------------------------------
    elif aba_ativa == "5. Coleta (Origem)":
        st.markdown(
            """
            <div class="tab-header-wrap">
                <div class="tab-title"><i class="fa-solid fa-location-arrow"></i> Local de Coleta (Origem)</div>
                <span class="tab-step-pill">Etapa 5 de 11</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        cli_map_local = {c["id_cliente"]: c for c in clientes_db}
        loc_ops = {0: "Selecione um local cadastrado..."}
        for l in locais_db:
            loc_ops[l["id_local"]] = formatar_rotulo_local(l, cli_map_local)

        col_atual = get_campo("col_id", 0)
        idx_col = list(loc_ops.keys()).index(col_atual) if col_atual in loc_ops else 0

        col_sel = st.selectbox(
            "BASE / EMPRESA CADASTRADA (COLETA) *",
            options=list(loc_ops.keys()),
            index=idx_col,
            format_func=lambda x: loc_ops[x],
            key="w_col_id",
            on_change=on_local_select_change,
            args=("w_col_id", "col_id", locais_db),
        )
        col_obj = next((l for l in locais_db if l["id_local"] == col_sel), None)

        lc1, lc2, lc3, lc4 = st.columns([0.9, 2.3, 1.3, 0.55])
        lc1.text_input("CEP", value=(col_obj.get("cep") or "") if col_obj else "", disabled=True, key=f"p_col_cep_{col_sel}")
        lc2.text_input(
            "ENDEREÇO COMPLETO",
            value=(col_obj.get("endereco_completo") or "") if col_obj else "",
            disabled=True,
            key=f"p_col_end_{col_sel}",
        )
        lc3.text_input(
            "CIDADE",
            value=(col_obj.get("cidade") or "") if col_obj else "",
            disabled=True,
            key=f"p_col_cid_{col_sel}",
        )
        lc4.text_input("UF", value=(col_obj.get("uf") or "") if col_obj else "", disabled=True, key=f"p_col_uf_{col_sel}")

        if col_obj and (col_obj.get("contato_portaria") or col_obj.get("restricao_horario")):
            st.markdown(
                f"""
                <div class="cliente-coleta-banner">
                    <strong>Portaria / Contato:</strong> {col_obj.get('contato_portaria') or '-'}
                    &nbsp;|&nbsp; <strong>Restrição de Horário:</strong> {col_obj.get('restricao_horario') or 'Não há restrição'}
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown('<div class="sec-subtitle">Horários da Operação de Coleta</div>', unsafe_allow_html=True)
        hc1, hc2, hc3, _ = st.columns([1.15, 1.0, 1.0, 1.3])
        with hc1:
            st.date_input(
                "DATA COLETA",
                value=get_campo("data_coleta", date.today()),
                format="DD/MM/YYYY",
                key="w_data_coleta",
                on_change=sync_campo,
                args=("w_data_coleta", "data_coleta"),
            )
        with hc2:
            st.time_input(
                "HORA PLANEJADA",
                value=get_campo("hora_plan_col"),
                key="w_hora_plan_col",
                on_change=sync_campo,
                args=("w_hora_plan_col", "hora_plan_col"),
            )
        with hc3:
            st.time_input(
                "HORA REAL",
                value=get_campo("hora_real_col"),
                key="w_hora_real_col",
                on_change=sync_campo,
                args=("w_hora_real_col", "hora_real_col"),
            )

        render_navegacao_rodape(4, MENU_ITENS)

    # --------------------------------------------------------------------------
    # ETAPA 6: LOCAL DE ENTREGA (DESTINO)
    # --------------------------------------------------------------------------
    elif aba_ativa == "6. Entrega (Destino)":
        st.markdown(
            """
            <div class="tab-header-wrap">
                <div class="tab-title"><i class="fa-solid fa-flag-checkered"></i> Local de Entrega (Destino)</div>
                <span class="tab-step-pill">Etapa 6 de 11</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        cli_map_local = {c["id_cliente"]: c for c in clientes_db}
        loc_ops = {0: "Selecione um local cadastrado..."}
        for l in locais_db:
            loc_ops[l["id_local"]] = formatar_rotulo_local(l, cli_map_local)

        ent_atual = get_campo("ent_id", 0)
        idx_ent = list(loc_ops.keys()).index(ent_atual) if ent_atual in loc_ops else 0

        ent_sel = st.selectbox(
            "BASE / EMPRESA CADASTRADA (ENTREGA) *",
            options=list(loc_ops.keys()),
            index=idx_ent,
            format_func=lambda x: loc_ops[x],
            key="w_ent_id",
            on_change=on_local_select_change,
            args=("w_ent_id", "ent_id", locais_db),
        )
        ent_obj = next((l for l in locais_db if l["id_local"] == ent_sel), None)

        le1, le2, le3, le4 = st.columns([0.9, 2.3, 1.3, 0.55])
        le1.text_input("CEP", value=(ent_obj.get("cep") or "") if ent_obj else "", disabled=True, key=f"p_ent_cep_{ent_sel}")
        le2.text_input(
            "ENDEREÇO COMPLETO",
            value=(ent_obj.get("endereco_completo") or "") if ent_obj else "",
            disabled=True,
            key=f"p_ent_end_{ent_sel}",
        )
        le3.text_input(
            "CIDADE",
            value=(ent_obj.get("cidade") or "") if ent_obj else "",
            disabled=True,
            key=f"p_ent_cid_{ent_sel}",
        )
        le4.text_input("UF", value=(ent_obj.get("uf") or "") if ent_obj else "", disabled=True, key=f"p_ent_uf_{ent_sel}")

        if ent_obj and (ent_obj.get("contato_portaria") or ent_obj.get("restricao_horario")):
            st.markdown(
                f"""
                <div class="cliente-coleta-banner">
                    <strong>Portaria / Contato:</strong> {ent_obj.get('contato_portaria') or '-'}
                    &nbsp;|&nbsp; <strong>Restrição de Horário:</strong> {ent_obj.get('restricao_horario') or 'Não há restrição'}
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown('<div class="sec-subtitle">Horários da Operação de Entrega</div>', unsafe_allow_html=True)
        he1, he2, he3, _ = st.columns([1.15, 1.0, 1.0, 1.3])
        with he1:
            st.date_input(
                "DATA ENTREGA",
                value=get_campo("data_entrega", date.today()),
                format="DD/MM/YYYY",
                key="w_data_entrega",
                on_change=sync_campo,
                args=("w_data_entrega", "data_entrega"),
            )
        with he2:
            st.time_input(
                "HORA PLANEJADA",
                value=get_campo("hora_plan_ent"),
                key="w_hora_plan_ent",
                on_change=sync_campo,
                args=("w_hora_plan_ent", "hora_plan_ent"),
            )
        with he3:
            st.time_input(
                "HORA REAL",
                value=get_campo("hora_real_ent"),
                key="w_hora_real_ent",
                on_change=sync_campo,
                args=("w_hora_real_ent", "hora_real_ent"),
            )

        render_navegacao_rodape(5, MENU_ITENS)

    # --------------------------------------------------------------------------
    # ETAPA 7: DESPESAS DE VIAGEM (CAMPOS AMPLIADOS SEM CORTES)
    # --------------------------------------------------------------------------
    elif aba_ativa == "7. Despesas de Viagem":
        st.markdown(
            """
            <div class="tab-header-wrap">
                <div class="tab-title"><i class="fa-solid fa-receipt"></i> Despesas de Viagem</div>
                <span class="tab-step-pill">Etapa 7 de 11</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<div class="sec-subtitle">Adicionar Nova Despesa</div>', unsafe_allow_html=True)

        # Linha 1: Campos de seleção e descrição largos para evitar corte de opções/placeholders
        c_d1, c_d2, c_d3 = st.columns([2.1, 2.5, 2.1])
        with c_d1:
            tipo_desp = st.selectbox("TIPO DE DESPESA", CATEGORIAS_DESPESA_FORNECEDOR, key="desp_tipo")
        with c_d2:
            desc_desp = st.text_input(
                "DESCRIÇÃO / LOCAL",
                placeholder="Ex: Abastecimento KM 120 / Pedágio",
                key="desp_desc",
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

        # Linha 2: Quantidade, Valor Unitário, Total Calculado e Botão Adicionar
        c_d4, c_d5, c_d6, c_d7 = st.columns([1.2, 1.3, 2.2, 2.0])
        with c_d4:
            qtd_desp = st.number_input("QTD / L", min_value=0.01, value=1.00, step=1.0, format="%.2f", key="desp_qtd")
        with c_d5:
            unit_desp = st.number_input("UNITÁRIO (R$)", min_value=0.00, value=0.00, step=10.0, format="%.2f", key="desp_unit")
        with c_d6:
            total_previsto_desp = qtd_desp * unit_desp
            st.markdown(
                f'<div style="padding-top:1.55rem; font-weight:800; color:#0D263C; font-size:0.86rem;">'
                f'VALOR TOTAL: <span style="color:#F34D25; font-size:1.2rem;">{fmt_brl(total_previsto_desp)}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )
        with c_d7:
            st.markdown('<div style="padding-top:1.35rem;"></div>', unsafe_allow_html=True)
            btn_add_desp = st.button("Adicionar à Lista", use_container_width=True, key="btn_add_despesa")

        if btn_add_desp:
            if unit_desp <= 0:
                st.warning("Informe um valor unitário maior que R$ 0,00.")
            else:
                v_tot_item = round(qtd_desp * unit_desp, 2)
                if viagem_sel_id == 0:
                    st.session_state.setdefault("despesas_temp", []).append(
                        {
                            "id_fornecedor": forn_sel,
                            "tipo_despesa": tipo_desp,
                            "descricao_detalhe": desc_desp.strip() or tipo_desp,
                            "quantidade": round(qtd_desp, 2),
                            "valor_unitario": round(unit_desp, 2),
                            "valor_total": v_tot_item,
                        }
                    )
                    st.toast("Despesa adicionada à lista temporária!", icon="🧾")
                    st.rerun()
                else:
                    with SessionLocal() as db:
                        db.add(
                            ViagemDespesa(
                                id_viagem=viagem_sel_id,
                                id_fornecedor=forn_sel if forn_sel != 0 else None,
                                tipo_despesa=tipo_desp,
                                descricao_detalhe=desc_desp.strip() or tipo_desp,
                                quantidade=round(qtd_desp, 2),
                                valor_unitario=round(unit_desp, 2),
                                valor_total=v_tot_item,
                            )
                        )
                        db.commit()
                    carregar_despesas_viagem.clear()
                    carregar_todas_viagens_consulta.clear()
                    st.toast("Despesa gravada no banco!", icon="✅")
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
                                db.delete(obj_d)
                                db.commit()
                        carregar_despesas_viagem.clear()
                        carregar_todas_viagens_consulta.clear()
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

        render_navegacao_rodape(6, MENU_ITENS)

    # --------------------------------------------------------------------------
    # ETAPA 8: FECHAMENTO FINAL (ODÔMETRO, SITUAÇÃO E DRE)
    # --------------------------------------------------------------------------
    elif aba_ativa == "8. Fechamento Final":
        st.markdown(
            """
            <div class="tab-header-wrap">
                <div class="tab-title"><i class="fa-solid fa-calculator"></i> Fechamento Final e DRE</div>
                <span class="tab-step-pill">Etapa 8 de 11</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        f1, f2, f3, f4 = st.columns([1.1, 1.1, 1.1, 1.7])
        with f1:
            odo_ini_v = st.number_input(
                "ODÔMETRO INICIAL",
                min_value=0,
                step=10,
                value=to_int(get_campo("odo_ini", 0)),
                key="w_odo_ini",
                on_change=sync_campo,
                args=("w_odo_ini", "odo_ini"),
            )
        with f2:
            odo_fin_v = st.number_input(
                "ODÔMETRO FINAL",
                min_value=0,
                step=10,
                value=to_int(get_campo("odo_fin", 0)),
                key="w_odo_fin",
                on_change=sync_campo,
                args=("w_odo_fin", "odo_fin"),
            )
        km_real_calc = max(0, to_int(odo_fin_v) - to_int(odo_ini_v))
        with f3:
            st.text_input("KM REAL RODADO", value=f"{km_real_calc} km", disabled=True, key=f"prev_km_{km_real_calc}")
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

        v_neg_dre = to_float(get_campo("valor_negociado", 0.0))
        v_rec_dre = to_float(get_campo("valor_adiant", 0.0)) + to_float(get_campo("valor_saldo", 0.0))
        receita_dre = v_neg_dre if v_neg_dre > 0 else v_rec_dre

        if viagem_sel_id == 0:
            custos_dre = sum(to_float(d["valor_total"]) for d in st.session_state.get("despesas_temp", []))
        else:
            custos_dre = sum(to_float(d["valor_total"]) for d in carregar_despesas_viagem(viagem_sel_id))

        resultado_dre = receita_dre - custos_dre
        cor_res = "#4ADE80" if resultado_dre >= 0 else "#F87171"

        st.markdown(
            f"""
            <div class="dre-box">
                <div class="dre-header">Demonstrativo de Resultado da Viagem (DRE — FAEG)</div>
                <div class="dre-row">
                    <span style="color:#ABCEE1;">Receita Total (Frete Negociado / Recebido)</span>
                    <span style="font-weight:800; font-size:1.15rem;">{fmt_brl(receita_dre)}</span>
                </div>
                <div class="dre-row">
                    <span style="color:#ABCEE1;">Custos Totais (Combustível, Pedágios e Outras Despesas)</span>
                    <span style="font-weight:800; font-size:1.15rem; color:#F34D25;">- {fmt_brl(custos_dre)}</span>
                </div>
                <div class="dre-total-row">
                    <span style="font-weight:800; text-transform:uppercase; letter-spacing:0.04em;">Resultado Líquido</span>
                    <span style="font-weight:900; font-size:1.85rem; color:{cor_res};">{fmt_brl(resultado_dre)}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        render_navegacao_rodape(7, MENU_ITENS)

    # --------------------------------------------------------------------------
    # ETAPA 9: RELATÓRIOS E EXPORTAÇÃO (VIAGEM ATIVA + PAINEL GERAL / BI)
    # --------------------------------------------------------------------------
    elif aba_ativa == "9. Relatórios / Exportar":
        st.markdown(
            """
            <div class="tab-header-wrap">
                <div class="tab-title"><i class="fa-solid fa-chart-pie"></i> Relatórios e Exportação</div>
                <span class="tab-step-pill">Etapa 9 de 11</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        todas_vg_exp, desp_det_exp = carregar_todas_viagens_consulta()
        xlsx_bytes_completo = gerar_excel_base_completa(
            todas_vg_exp, desp_det_exp, motoristas_db, veiculos_db, clientes_db, locais_db, fornecedores_db
        )

        tab_rel_viagem, tab_rel_geral = st.tabs(
            [
                "📄 Relatório da Viagem Ativa",
                "📊 Painel Geral (BI Consolidado)",
            ]
        )

        # ----------------------------------------------------------------------
        # SUB-ABA 1: RELATÓRIO DA VIAGEM ATIVA
        # ----------------------------------------------------------------------
        with tab_rel_viagem:
            v_neg_r = to_float(get_campo("valor_negociado", 0.0))
            v_rec_r = to_float(get_campo("valor_adiant", 0.0)) + to_float(get_campo("valor_saldo", 0.0))
            receita_r = v_neg_r if v_neg_r > 0 else v_rec_r

            if viagem_sel_id == 0:
                desps_r = st.session_state.get("despesas_temp", [])
            else:
                desps_r = carregar_despesas_viagem(viagem_sel_id)

            custos_r = sum(to_float(d["valor_total"]) for d in desps_r)
            resultado_r = receita_r - custos_r
            km_r = max(0, to_int(get_campo("odo_fin", 0)) - to_int(get_campo("odo_ini", 0)))
            custo_km_r = (custos_r / km_r) if km_r > 0 else 0.0
            margem_r = ((resultado_r / receita_r) * 100.0) if receita_r > 0 else 0.0

            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("Receita Considerada", fmt_brl(receita_r))
            k2.metric("Custos Totais", fmt_brl(custos_r))
            k3.metric("Resultado Líquido", fmt_brl(resultado_r))
            k4.metric("Custo por KM", fmt_brl(custo_km_r))
            k5.metric("Margem de Lucro", f"{margem_r:.1f}%")

            st.markdown('<div class="sec-subtitle">Exportação da Viagem Atual</div>', unsafe_allow_html=True)
            vei_obj_r = next((v for v in veiculos_db if v["id_veiculo"] == get_campo("vei_id", 0)), None)
            dados_pdf = {
                "codigo": id_label_ctx,
                "id_frete": get_campo("id_frete") or "-",
                "cliente": cli_nome_ctx,
                "ciclo": get_campo("ciclo_nome") or "Individual",
                "motorista": mot_nome_ctx,
                "veiculo": f"{vei_obj_r['descricao_marca']} ({vei_obj_r['placa']})" if vei_obj_r else "-",
                "origem": get_campo("rota_origem") or "-",
                "destino": get_campo("rota_destino") or "-",
                "tipo_viagem": get_campo("tipo_viagem", "Individual"),
                "frete_info": f"{get_campo('tipo_frete', 'Dedicado')} / {get_campo('forma_contrat', '-')}",
                "status": status_ctx,
                "km_real": km_r,
                "receita_fmt": fmt_brl(receita_r),
                "despesa_fmt": fmt_brl(custos_r),
                "resultado_fmt": fmt_brl(resultado_r),
                "custo_km_fmt": fmt_brl(custo_km_r),
                "margem_fmt": f"{margem_r:.1f}%",
                "recebido_fmt": fmt_brl(v_rec_r),
            }
            desps_pdf = [
                {
                    "tipo": d["tipo_despesa"],
                    "desc": d.get("descricao_detalhe") or "-",
                    "qtd": to_float(d["quantidade"]),
                    "unit_fmt": fmt_brl(d["valor_unitario"]),
                    "total_fmt": fmt_brl(d["valor_total"]),
                }
                for d in desps_r
            ]
            pdf_bytes = gerar_pdf_relatorio(dados_pdf, desps_pdf)

            b_pdf, b_xls, _ = st.columns([1.5, 1.7, 2.3])
            with b_pdf:
                st.download_button(
                    "📄 Baixar Relatório PDF (Viagem)",
                    data=pdf_bytes,
                    file_name=f"Relatorio_{id_label_ctx}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="dl_pdf_viagem_ativa",
                )
            with b_xls:
                st.download_button(
                    "📥 Exportar Base Completa (.xlsx)",
                    data=xlsx_bytes_completo,
                    file_name="Base_Completa_FAEG.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="dl_xlsx_viagem_ativa",
                )

            if desps_r:
                st.markdown('<div class="sec-subtitle">Distribuição de Gastos por Categoria</div>', unsafe_allow_html=True)
                df_chart = (
                    pd.DataFrame(desps_r)
                    .groupby("tipo_despesa", as_index=False)["valor_total"]
                    .sum()
                    .rename(columns={"tipo_despesa": "Categoria", "valor_total": "Total (R$)"})
                )
                st.bar_chart(df_chart.set_index("Categoria"), color="#F34D25")
            else:
                st.info("Nenhuma despesa registrada nesta viagem para exibir o gráfico de categorias.")

        # ----------------------------------------------------------------------
        # SUB-ABA 2: PAINEL GERAL (BI CONSOLIDADO DE TODAS AS VIAGENS)
        # ----------------------------------------------------------------------
        with tab_rel_geral:
            if not todas_vg_exp:
                st.info("Nenhuma viagem salva no banco até o momento para consolidar indicadores.")
            else:
                st.markdown('<div class="sec-subtitle">Filtros do Painel Executivo</div>', unsafe_allow_html=True)
                fg1, fg2, fg3 = st.columns([1.4, 1.3, 2.3])
                with fg1:
                    bi_status = st.selectbox(
                        "SITUAÇÃO DA OPERAÇÃO",
                        ["Todas"] + OPCOES_SITUACAO_OPERACAO,
                        key="bi_filtro_status",
                    )
                with fg2:
                    bi_tipo = st.selectbox(
                        "TIPO DE VIAGEM",
                        ["Todos", "Individual", "Ciclo"],
                        key="bi_filtro_tipo",
                    )
                with fg3:
                    clientes_bi_ops = ["Todos"] + sorted(
                        list({v["cliente"] for v in todas_vg_exp if v["cliente"] and v["cliente"] != "-"})
                    )
                    bi_cliente = st.selectbox(
                        "CLIENTE CONTRATANTE",
                        clientes_bi_ops,
                        key="bi_filtro_cliente",
                    )

                vg_bi_filtradas = todas_vg_exp
                if bi_status != "Todas":
                    vg_bi_filtradas = [v for v in vg_bi_filtradas if v["status"] == bi_status]
                if bi_tipo != "Todos":
                    vg_bi_filtradas = [v for v in vg_bi_filtradas if v["tipo_viagem"] == bi_tipo]
                if bi_cliente != "Todos":
                    vg_bi_filtradas = [v for v in vg_bi_filtradas if v["cliente"] == bi_cliente]

                cods_bi_ativos = {v["codigo_viagem"] for v in vg_bi_filtradas}
                desps_bi_filtradas = [
                    d for d in desp_det_exp if d.get("Código Viagem") in cods_bi_ativos
                ]

                rec_global = sum(v["receita_base"] for v in vg_bi_filtradas)
                desp_global = sum(v["total_despesas"] for v in vg_bi_filtradas)
                res_global = rec_global - desp_global
                margem_global = ((res_global / rec_global) * 100.0) if rec_global > 0 else 0.0
                km_global = sum(v["km_rodado"] for v in vg_bi_filtradas)
                custo_km_global = (desp_global / km_global) if km_global > 0 else 0.0

                st.markdown('<div class="sec-subtitle">Indicadores Globais Consolidados</div>', unsafe_allow_html=True)
                bg1, bg2, bg3 = st.columns(3)
                bg1.metric("Viagens Analisadas", len(vg_bi_filtradas))
                bg2.metric("Receita Consolidada", fmt_brl(rec_global))
                bg3.metric("Despesas Consolidadas", fmt_brl(desp_global))

                bg4, bg5, bg6 = st.columns(3)
                bg4.metric("Resultado Líquido Total", fmt_brl(res_global))
                bg5.metric("Margem Média Global", f"{margem_global:.1f}%")
                bg6.metric("KM Rodado / Custo Médio KM", f"{km_global:,} km ({fmt_brl(custo_km_global)})".replace(",", "."))

                # Agrupamento por Cliente
                ranking_cli_lista = []
                if vg_bi_filtradas:
                    df_bi_vg = pd.DataFrame(vg_bi_filtradas)
                    grp_cli = (
                        df_bi_vg.groupby("cliente", as_index=False)
                        .agg(
                            viagens=("id_viagem", "count"),
                            receita=("receita_base", "sum"),
                            despesas=("total_despesas", "sum"),
                            resultado=("resultado_liquido", "sum"),
                        )
                        .sort_values("resultado", ascending=False)
                    )
                    for _, row_c in grp_cli.iterrows():
                        mg_c = ((row_c["resultado"] / row_c["receita"]) * 100.0) if row_c["receita"] > 0 else 0.0
                        ranking_cli_lista.append(
                            {
                                "cliente": row_c["cliente"],
                                "viagens": int(row_c["viagens"]),
                                "receita": float(row_c["receita"]),
                                "despesas": float(row_c["despesas"]),
                                "resultado": float(row_c["resultado"]),
                                "margem": mg_c,
                                "receita_fmt": fmt_brl(row_c["receita"]),
                                "despesa_fmt": fmt_brl(row_c["despesas"]),
                                "resultado_fmt": fmt_brl(row_c["resultado"]),
                                "margem_fmt": f"{mg_c:.1f}%",
                            }
                        )

                # Agrupamento de Despesas por Categoria
                desp_cat_lista = []
                if desps_bi_filtradas:
                    df_bi_desp = pd.DataFrame(desps_bi_filtradas)
                    grp_cat = (
                        df_bi_desp.groupby("Tipo Despesa", as_index=False)["Valor Total (R$)"]
                        .sum()
                        .sort_values("Valor Total (R$)", ascending=False)
                    )
                    tot_cat_soma = float(grp_cat["Valor Total (R$)"].sum())
                    for _, row_d in grp_cat.iterrows():
                        val_cat = float(row_d["Valor Total (R$)"])
                        pct_cat = ((val_cat / tot_cat_soma) * 100.0) if tot_cat_soma > 0 else 0.0
                        desp_cat_lista.append(
                            {
                                "categoria": row_d["Tipo Despesa"],
                                "total": val_cat,
                                "total_fmt": fmt_brl(val_cat),
                                "pct_fmt": f"{pct_cat:.1f}%",
                            }
                        )

                g_col1, g_col2 = st.columns(2)
                with g_col1:
                    st.markdown('<div class="sec-subtitle">Despesas por Categoria (Consolidado)</div>', unsafe_allow_html=True)
                    if desp_cat_lista:
                        df_chart_cat_bi = pd.DataFrame(desp_cat_lista)[["categoria", "total"]].rename(
                            columns={"categoria": "Categoria", "total": "Total (R$)"}
                        )
                        st.bar_chart(df_chart_cat_bi.set_index("Categoria"), color="#F34D25")
                    else:
                        st.info("Sem despesas registradas para o filtro selecionado.")

                with g_col2:
                    st.markdown('<div class="sec-subtitle">Resultado Líquido por Cliente</div>', unsafe_allow_html=True)
                    if ranking_cli_lista:
                        df_chart_cli_bi = pd.DataFrame(ranking_cli_lista)[["cliente", "resultado"]].rename(
                            columns={"cliente": "Cliente", "resultado": "Resultado Líquido (R$)"}
                        )
                        st.bar_chart(df_chart_cli_bi.set_index("Cliente"), color="#0D263C")
                    else:
                        st.info("Sem viagens filtradas para exibir o ranking por cliente.")

                if ranking_cli_lista:
                    st.markdown('<div class="sec-subtitle">Resumo Executivo por Cliente</div>', unsafe_allow_html=True)
                    df_tabela_cli = pd.DataFrame(
                        [
                            {
                                "Cliente": r["cliente"],
                                "Viagens": r["viagens"],
                                "Receita Total": r["receita_fmt"],
                                "Despesas Totais": r["despesa_fmt"],
                                "Resultado Líquido": r["resultado_fmt"],
                                "Margem (%)": r["margem_fmt"],
                            }
                            for r in ranking_cli_lista
                        ]
                    )
                    st.dataframe(df_tabela_cli, use_container_width=True, hide_index=True)

                st.markdown('<div class="sec-subtitle">Exportação Executiva Consolidada</div>', unsafe_allow_html=True)
                resumo_pdf_bi = {
                    "filtro_desc": f"Situacao: {bi_status} | Tipo: {bi_tipo} | Cliente: {bi_cliente}",
                    "qtd_viagens": len(vg_bi_filtradas),
                    "km_total": km_global,
                    "receita_fmt": fmt_brl(rec_global),
                    "despesa_fmt": fmt_brl(desp_global),
                    "resultado_fmt": fmt_brl(res_global),
                    "margem_fmt": f"{margem_global:.1f}%",
                }
                pdf_bi_bytes = gerar_pdf_relatorio_consolidado(
                    resumo_pdf_bi, ranking_cli_lista, desp_cat_lista
                )

                eb1, eb2, _ = st.columns([1.8, 1.7, 2.0])
                with eb1:
                    st.download_button(
                        "📄 Baixar Relatório Executivo PDF",
                        data=pdf_bi_bytes,
                        file_name=f"Relatorio_Consolidado_FAEG_{date.today().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key="dl_pdf_consolidado_bi",
                    )
                with eb2:
                    st.download_button(
                        "📥 Exportar Base Completa (.xlsx)",
                        data=xlsx_bytes_completo,
                        file_name="Base_Completa_FAEG.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key="dl_xlsx_consolidado_bi",
                    )

        render_navegacao_rodape(8, MENU_ITENS)

    # --------------------------------------------------------------------------
    # ETAPA 10: CONSULTAS GERAIS (COM RÓTULOS SEM SOBREPOSIÇÃO)
    # --------------------------------------------------------------------------
    elif aba_ativa == "10. Consultas Gerais":
        st.markdown(
            """
            <div class="tab-header-wrap">
                <div class="tab-title"><i class="fa-solid fa-magnifying-glass-chart"></i> Consultas Gerais e Histórico</div>
                <span class="tab-step-pill">Etapa 10 de 11</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        todas_viagens, desp_detalhadas = carregar_todas_viagens_consulta()

        f1, f2, f3, f4 = st.columns([2.6, 1.3, 1.3, 1.4])
        with f1:
            termo_busca = st.text_input(
                "BUSCA GERAL (CÓDIGO, CLIENTE, MOTORISTA, ROTA, CICLO, NF-E)",
                placeholder="Digite para filtrar instantaneamente...",
                key="consulta_busca",
            )
        with f2:
            filtro_tipo_vg = st.selectbox(
                "TIPO DE VIAGEM",
                ["Todos", "Individual", "Ciclo"],
                key="consulta_tipo",
            )
        with f3:
            filtro_situacao = st.selectbox(
                "SITUAÇÃO",
                ["Todas"] + OPCOES_SITUACAO_OPERACAO,
                key="consulta_situacao",
            )
        with f4:
            filtro_origem = st.selectbox(
                "ORIGEM DE FRETE",
                ["Todas"] + OPCOES_ORIGEM_FRETE,
                key="consulta_origem",
            )

        filtradas = todas_viagens
        if termo_busca.strip():
            tb = termo_busca.strip().lower()
            filtradas = [
                v
                for v in filtradas
                if tb in v["codigo_viagem"].lower()
                or tb in v["cliente"].lower()
                or tb in v["cliente_fantasia"].lower()
                or tb in v["motorista"].lower()
                or tb in v["rota"].lower()
                or tb in v["ciclo"].lower()
                or tb in v["nfe"].lower()
                or tb in v["id_frete"].lower()
            ]
        if filtro_tipo_vg != "Todos":
            filtradas = [v for v in filtradas if v["tipo_viagem"] == filtro_tipo_vg]
        if filtro_situacao != "Todas":
            filtradas = [v for v in filtradas if v["status"] == filtro_situacao]
        if filtro_origem != "Todas":
            filtradas = [v for v in filtradas if v["origem_frete"] == filtro_origem]

        tot_rec_f = sum(v["receita_base"] for v in filtradas)
        tot_desp_f = sum(v["total_despesas"] for v in filtradas)
        tot_res_f = sum(v["resultado_liquido"] for v in filtradas)

        st.markdown(
            f"""
            <div class="kpi-consulta-grid">
                <div class="kpi-consulta-card">
                    <div class="kpi-consulta-lbl">Viagens Filtradas</div>
                    <div class="kpi-consulta-val">{len(filtradas)}</div>
                </div>
                <div class="kpi-consulta-card">
                    <div class="kpi-consulta-lbl">Receita Consolidada</div>
                    <div class="kpi-consulta-val">{fmt_brl(tot_rec_f)}</div>
                </div>
                <div class="kpi-consulta-card orange">
                    <div class="kpi-consulta-lbl">Despesas Consolidadas</div>
                    <div class="kpi-consulta-val">{fmt_brl(tot_desp_f)}</div>
                </div>
                <div class="kpi-consulta-card">
                    <div class="kpi-consulta-lbl">Resultado Líquido</div>
                    <div class="kpi-consulta-val">{fmt_brl(tot_res_f)}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if not filtradas:
            st.info("Nenhuma viagem encontrada para os filtros aplicados.")
        else:
            df_cons = pd.DataFrame(
                [
                    {
                        "Código": v["codigo_viagem"],
                        "Situação": v["status"],
                        "Tipo": v["tipo_viagem"],
                        "Ciclo": v["ciclo"],
                        "Cliente": v["cliente"],
                        "Motorista": v["motorista"],
                        "Origem": v["rota_origem"] or "-",
                        "Destino": v["rota_destino"] or "-",
                        "Receita": fmt_brl(v["receita_base"]),
                        "Despesas": fmt_brl(v["total_despesas"]),
                        "Resultado": fmt_brl(v["resultado_liquido"]),
                    }
                    for v in filtradas
                ]
            )
            st.dataframe(df_cons, use_container_width=True, hide_index=True)

            st.markdown('<div class="sec-subtitle">Abrir Viagem para Visualizar ou Editar</div>', unsafe_allow_html=True)
            ac1, ac2, ac3 = st.columns([2.6, 1.5, 1.5])
            opcoes_abrir = {
                v["id_viagem"]: f"{v['codigo_viagem']} — {v['cliente']} ({v['rota']})" for v in filtradas
            }
            with ac1:
                vg_escolhida_abrir = st.selectbox(
                    "SELECIONE A VIAGEM",
                    options=list(opcoes_abrir.keys()),
                    format_func=lambda x: opcoes_abrir[x],
                    key="sel_abrir_viagem_consulta",
                )
            with ac2:
                st.markdown('<div style="padding-top:1.35rem;"></div>', unsafe_allow_html=True)
                st.button(
                    "✏️ Editar Viagem",
                    key="btn_editar_viagem_consulta",
                    use_container_width=True,
                    on_click=_abrir_viagem_para_edicao,
                    args=(vg_escolhida_abrir, "1. Frota FAEG"),
                )
            with ac3:
                st.markdown('<div style="padding-top:1.35rem;"></div>', unsafe_allow_html=True)
                xlsx_cons = gerar_excel_base_completa(
                    filtradas, desp_detalhadas, motoristas_db, veiculos_db, clientes_db, locais_db, fornecedores_db
                )
                st.download_button(
                    "📥 Exportar Excel (.xlsx)",
                    data=xlsx_cons,
                    file_name="Consulta_Viagens_FAEG.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

        render_navegacao_rodape(9, MENU_ITENS)

    # --------------------------------------------------------------------------
    # ETAPA 11: CADASTROS GERAIS (ORGANIZADO EM 5 ABAS INTERNAS st.tabs)
    # --------------------------------------------------------------------------
    elif aba_ativa == "11. Cadastros Gerais":
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
                        f"<div class='edit-banner-pill'>✏️ Editando Motorista: {mot_edit_obj['nome_completo']}</div>",
                        unsafe_allow_html=True,
                    )

                with st.form("form_cad_mot", clear_on_submit=True):
                    mc1, mc2, mc3 = st.columns([2.6, 1.3, 1.3])
                    m_nome = mc1.text_input(
                        "Nome Completo *",
                        placeholder="Ex: Carlos Eduardo Mendes",
                        value=mot_edit_obj["nome_completo"] if mot_edit_obj else "",
                    )
                    m_cpf = mc2.text_input(
                        "CPF *",
                        placeholder="000.000.000-00",
                        value=mot_edit_obj["cpf"] if mot_edit_obj else "",
                    )
                    m_tel = mc3.text_input(
                        "Telefone / WhatsApp",
                        placeholder="(11) 99999-9999",
                        value=(mot_edit_obj.get("telefone_contato") or "") if mot_edit_obj else "",
                    )

                    mc4, mc5, mc6, mc7 = st.columns([1.4, 0.9, 1.2, 1.7])
                    m_cnh = mc4.text_input(
                        "Número CNH *",
                        placeholder="00000000000",
                        value=mot_edit_obj["cnh_numero"] if mot_edit_obj else "",
                    )
                    cats_cnh = ["C", "D", "E", "AE", "B"]
                    idx_cat_m = (
                        cats_cnh.index(mot_edit_obj["cnh_categoria"])
                        if mot_edit_obj and mot_edit_obj.get("cnh_categoria") in cats_cnh
                        else 2
                    )
                    m_cat = mc5.selectbox("Categoria", cats_cnh, index=idx_cat_m)
                    m_val_cnh = mc6.date_input(
                        "Validade CNH",
                        value=mot_edit_obj.get("cnh_validade") if mot_edit_obj else None,
                        format="DD/MM/YYYY",
                    )
                    vinculos_ops = ["Frota Própria (CLT)", "Agregado", "Terceiro (TAC)", "Outros"]
                    idx_vinc = (
                        vinculos_ops.index(mot_edit_obj["vinculo"])
                        if mot_edit_obj and mot_edit_obj.get("vinculo") in vinculos_ops
                        else 0
                    )
                    m_vinc = mc7.selectbox("Vínculo", vinculos_ops, index=idx_vinc)

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
                                f"**{m['nome_completo']}** <span style='color:#64748B;font-size:0.78rem;'>| CNH: {m['cnh_numero']} ({m['cnh_categoria']}) | {m.get('vinculo') or '-'}</span>",
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
                                    f"<div class='confirm-box-edit'>⚠️ Confirmar edição de <strong>{m['nome_completo']}</strong>?</div>",
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
                                    f"<div class='confirm-box-del'>🚨 Excluir permanentemente <strong>{m['nome_completo']}</strong>?</div>",
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
                        f"<div class='edit-banner-pill'>✏️ Editando Veículo: {vei_edit_obj['descricao_marca']} ({vei_edit_obj['placa']})</div>",
                        unsafe_allow_html=True,
                    )

                with st.form("form_cad_vei", clear_on_submit=True):
                    vc1, vc2, vc3 = st.columns([2.6, 1.2, 1.4])
                    v_desc = vc1.text_input(
                        "Descrição / Marca / Modelo *",
                        placeholder="Ex: Scania R450 Highline",
                        value=vei_edit_obj["descricao_marca"] if vei_edit_obj else "",
                    )
                    v_placa = vc2.text_input(
                        "Placa *",
                        placeholder="ABC1D23",
                        value=vei_edit_obj["placa"] if vei_edit_obj else "",
                    )
                    tipos_v = ["Carreta", "Bitrem", "Rodotrem", "Truck", "Toco", "3/4", "VUC", "Utilitário"]
                    idx_tv = (
                        tipos_v.index(vei_edit_obj["tipo_veiculo"])
                        if vei_edit_obj and vei_edit_obj.get("tipo_veiculo") in tipos_v
                        else 0
                    )
                    v_tipo = vc3.selectbox("Tipo de Veículo", tipos_v, index=idx_tv)

                    vc4, vc5, vc6, vc7 = st.columns([1.6, 1.0, 1.3, 1.3])
                    v_renavam = vc4.text_input(
                        "RENAVAM",
                        placeholder="00000000000",
                        value=(vei_edit_obj.get("renavam") or "") if vei_edit_obj else "",
                    )
                    v_ano = vc5.number_input(
                        "Ano",
                        min_value=1980,
                        max_value=2035,
                        step=1,
                        value=to_int(vei_edit_obj.get("ano_fabricacao"), 2024) if vei_edit_obj else 2024,
                    )
                    v_cap_kg = vc6.number_input(
                        "Capacidade (KG)",
                        min_value=0.0,
                        step=500.0,
                        format="%.2f",
                        value=to_float(vei_edit_obj.get("capacidade_carga_kg"), 0.0) if vei_edit_obj else 0.0,
                    )
                    v_cap_m3 = vc7.number_input(
                        "Volume (m³)",
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
                                f"**{v['descricao_marca']}** <span style='color:#64748B;font-size:0.78rem;'>| Placa: {v['placa']} | {v.get('tipo_veiculo') or '-'}</span>",
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
                                    f"<div class='confirm-box-edit'>⚠️ Confirmar edição de <strong>{v['descricao_marca']} ({v['placa']})</strong>?</div>",
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
                                    f"<div class='confirm-box-del'>🚨 Excluir permanentemente <strong>{v['descricao_marca']} ({v['placa']})</strong>?</div>",
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
                        f"<div class='edit-banner-pill'>✏️ Editando Cliente: {cli_edit_obj['razao_social']}</div>",
                        unsafe_allow_html=True,
                    )

                with st.form("form_cad_cli", clear_on_submit=True):
                    cc1, cc2 = st.columns(2)
                    c_razao = cc1.text_input(
                        "Razão Social *",
                        placeholder="Ex: Indústria Metalúrgica Suzano Ltda",
                        value=cli_edit_obj["razao_social"] if cli_edit_obj else "",
                    )
                    c_fantasia = cc2.text_input(
                        "Nome Fantasia",
                        placeholder="Ex: MetalSuzano",
                        value=(cli_edit_obj.get("nome_fantasia") or "") if cli_edit_obj else "",
                    )

                    cc3, cc4, cc5 = st.columns([1.6, 1.4, 1.0])
                    c_doc = cc3.text_input(
                        "CNPJ / CPF *",
                        placeholder="00.000.000/0001-00",
                        value=cli_edit_obj["cnpj_cpf"] if cli_edit_obj else "",
                    )
                    c_ie = cc4.text_input(
                        "Inscrição Estadual",
                        placeholder="Isento ou número IE",
                        value=(cli_edit_obj.get("inscricao_estadual") or "") if cli_edit_obj else "",
                    )
                    c_prazo = cc5.number_input(
                        "Prazo Pgto (Dias)",
                        min_value=0,
                        step=5,
                        value=to_int(cli_edit_obj.get("prazo_pagamento_dias"), 30) if cli_edit_obj else 30,
                    )

                    cc6, cc7, cc8 = st.columns([1.6, 1.3, 1.8])
                    c_resp = cc6.text_input(
                        "Responsável",
                        placeholder="Ex: Mariana Costa",
                        value=(cli_edit_obj.get("responsavel_comercial") or "") if cli_edit_obj else "",
                    )
                    c_tel = cc7.text_input(
                        "Telefone",
                        placeholder="(11) 4748-9000",
                        value=(cli_edit_obj.get("telefone_comercial") or "") if cli_edit_obj else "",
                    )
                    c_email = cc8.text_input(
                        "E-mail",
                        placeholder="contato@empresa.com.br",
                        value=(cli_edit_obj.get("email_financeiro") or "") if cli_edit_obj else "",
                    )

                    ce1, ce2, ce3, ce4 = st.columns([1.1, 2.7, 1.5, 0.7])
                    c_cep = ce1.text_input(
                        "CEP",
                        placeholder="00000-000",
                        value=(cli_edit_obj.get("cep") or "") if cli_edit_obj else "",
                    )
                    c_end = ce2.text_input(
                        "Endereço Completo",
                        placeholder="Av. Principal, 1000 - Centro",
                        value=(cli_edit_obj.get("endereco_completo") or "") if cli_edit_obj else "",
                    )
                    c_cid = ce3.text_input(
                        "Cidade",
                        placeholder="Ex: Suzano",
                        value=(cli_edit_obj.get("cidade") or "") if cli_edit_obj else "",
                    )
                    c_uf = ce4.text_input(
                        "UF",
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
                                f"**{c['razao_social']}**{ft_txt} <span style='color:#64748B;font-size:0.78rem;'>| Doc: {c['cnpj_cpf']}{cid_txt}</span>",
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
                                    f"<div class='confirm-box-edit'>⚠️ Confirmar edição de <strong>{c['razao_social']}</strong>?</div>",
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
                                    f"<div class='confirm-box-del'>🚨 Excluir permanentemente <strong>{c['razao_social']}</strong>?</div>",
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
                        f"<div class='edit-banner-pill'>✏️ Editando Local: {loc_edit_obj['nome_local']}</div>",
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
                                f"**{l['nome_local']}**{cid_l_txt} <span style='color:#64748B;font-size:0.78rem;'>| {l.get('restricao_horario') or 'Sem restrição'}{cli_tag}</span>",
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
                                    f"<div class='confirm-box-edit'>⚠️ Confirmar edição de <strong>{l['nome_local']}</strong>?</div>",
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
                                    f"<div class='confirm-box-del'>🚨 Excluir permanentemente <strong>{l['nome_local']}</strong>?</div>",
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
                        f"<div class='edit-banner-pill'>✏️ Editando Fornecedor: {forn_edit_obj['nome_fantasia']}</div>",
                        unsafe_allow_html=True,
                    )

                with st.form("form_cad_forn", clear_on_submit=True):
                    fn1, fn2 = st.columns(2)
                    f_razao = fn1.text_input(
                        "Razão Social",
                        placeholder="Ex: Auto Posto Graal Ltda",
                        value=(forn_edit_obj.get("razao_social") or "") if forn_edit_obj else "",
                    )
                    f_fantasia = fn2.text_input(
                        "Nome Fantasia *",
                        placeholder="Ex: Posto Graal Dutra",
                        value=forn_edit_obj["nome_fantasia"] if forn_edit_obj else "",
                    )

                    fc1, fc2 = st.columns(2)
                    f_cnpj = fc1.text_input(
                        "CNPJ",
                        placeholder="00.000.000/0001-00",
                        value=(forn_edit_obj.get("cnpj") or "") if forn_edit_obj else "",
                    )
                    idx_cat_f = (
                        CATEGORIAS_DESPESA_FORNECEDOR.index(forn_edit_obj["categoria_servico"])
                        if forn_edit_obj and forn_edit_obj.get("categoria_servico") in CATEGORIAS_DESPESA_FORNECEDOR
                        else 0
                    )
                    f_cat = fc2.selectbox("Categoria", CATEGORIAS_DESPESA_FORNECEDOR, index=idx_cat_f)

                    fc3, fc4 = st.columns([4, 1.5])
                    f_cid = fc3.text_input(
                        "Cidade",
                        placeholder="Ex: Resende",
                        value=(forn_edit_obj.get("cidade") or "") if forn_edit_obj else "",
                    )
                    f_uf = fc4.text_input(
                        "UF",
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
                                f"**{f['nome_fantasia']}**{rz_f_txt} <span style='color:#64748B;font-size:0.78rem;'>| {f.get('categoria_servico') or '-'}</span>",
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
                                    f"<div class='confirm-box-edit'>⚠️ Confirmar edição de <strong>{f['nome_fantasia']}</strong>?</div>",
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
                                    f"<div class='confirm-box-del'>🚨 Excluir permanentemente <strong>{f['nome_fantasia']}</strong>?</div>",
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