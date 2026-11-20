import base64
from html import escape
import io
import os
import re
import zlib
from datetime import date

import pandas as pd
import streamlit as st
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from database.connection import SessionLocal
from database.atribuicao_despesas import atribuir_despesa_veiculo, estornar_atribuicao_veiculo
from database.conferencia_duplicidades import (
    listar_semelhancas_entre_frete_ciclo,
    procurar_semelhancas_cruzadas,
)
from database.controle_abastecimentos import calcular_indicadores_abastecimentos
from database.fechamento_ciclos import consolidar_ciclos, reconciliar_resultado_gerencial
from database.importador_planilha import preparar_previa_importacao_faeg
from database.models import (
    Abastecimento,
    CicloOperacional,
    CicloDespesa,
    Cliente,
    FreteFinanceiro,
    Fornecedor,
    Local,
    Motorista,
    RecebimentoFrete,
    Veiculo,
    VeiculoDespesa,
    VeiculoDespesaAtribuicao,
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
def inicializar_banco_uma_vez(schema_v=12):
    """Garante que todas as tabelas e colunas novas existam no Neon sem alterar dados."""
    sincronizar_colunas_banco()
    return True


inicializar_banco_uma_vez(schema_v=12)

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


def financeiro_e_cliente_do_frete(viagem):
    """Usa os dados próprios do frete e preserva a leitura dos registros antigos."""
    financeiro_novo = viagem.financeiro_frete
    if financeiro_novo is not None:
        return financeiro_novo, financeiro_novo.cliente
    ciclo = viagem.ciclo
    return (ciclo.financeiro, ciclo.cliente) if ciclo is not None else (None, None)


def localizar_ciclo_operacional(session, identificador):
    """Localiza um ciclo compartilhado por seu identificador, ignorando caixa e espaços."""
    return (
        session.query(CicloOperacional)
        .filter(func.lower(func.trim(CicloOperacional.nome_operacao)) == identificador.strip().lower())
        .order_by(CicloOperacional.id_ciclo.asc())
        .first()
    )


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
        /* Compensa o espaço superior reservado pelo Streamlit sem mover o menu. */
        width: 100%;
        box-sizing: border-box;
        padding: 0.35rem 1.1rem 2.15rem 1.1rem;
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
        object-position: center;
        display: block;
        margin: 0 auto;
        transform: translateY(-22px);
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

    /* Indicadores compactos: o mesmo padrão nas etapas 7, 8, 9 e 10. */
    .faeg-indicators-grid {
        display: grid;
        grid-template-columns: repeat(var(--faeg-cols, 3), minmax(0, 1fr));
        gap: 0.8rem;
        margin: 0.65rem 0 1.1rem;
    }
    .faeg-indicator-card {
        min-width: 0;
        background: #FFFFFF;
        border: 1px solid #D6E1E9;
        border-top: 3px solid #ABCEE1;
        border-radius: 0.55rem;
        padding: 0.85rem 1rem;
        box-shadow: 0 2px 6px rgba(13, 38, 60, 0.035);
    }
    .faeg-indicator-card.is-accent {
        background: #FFF9F6;
        border-top-color: #F34D25;
    }
    .faeg-indicator-label {
        color: #556B7C;
        font-size: 0.67rem;
        font-weight: 800;
        letter-spacing: 0.045em;
        text-transform: uppercase;
        line-height: 1.4;
        margin-bottom: 0.38rem;
    }
    .faeg-indicator-value {
        color: #0D263C;
        font-size: clamp(1.1rem, 1.5vw, 1.45rem);
        font-weight: 800;
        line-height: 1.25;
        overflow-wrap: anywhere;
        font-variant-numeric: tabular-nums;
    }
    .faeg-indicator-value.is-long {
        font-size: clamp(0.94rem, 1.15vw, 1.12rem);
        line-height: 1.35;
    }
    @media (max-width: 1150px) {
        .faeg-indicators-grid[style*="--faeg-cols:4"],
        .faeg-indicators-grid[style*="--faeg-cols:5"] {
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }
    }
    @media (max-width: 780px) {
        .faeg-indicators-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 520px) {
        .faeg-indicators-grid { grid-template-columns: minmax(0, 1fr); }
    }

    /* Painel de KM do fechamento: hierarquia clara, sem seis métricas soltas. */
    .faeg-km-dashboard {
        background: #F8FAFC;
        border: 1px solid #D5E0E8;
        border-radius: 0.8rem;
        padding: 1.35rem;
        margin: 1rem 0 0.6rem;
    }
    .faeg-km-heading {
        display: flex;
        flex-wrap: wrap;
        align-items: flex-start;
        justify-content: space-between;
        gap: 0.7rem;
        margin-bottom: 1.05rem;
    }
    .faeg-km-eyebrow {
        font-size: 0.68rem;
        font-weight: 800;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: #D94B2A;
        margin-bottom: 0.2rem;
    }
    .faeg-km-title {
        color: #0D263C;
        font-size: 1.15rem;
        font-weight: 850;
        line-height: 1.3;
    }
    .faeg-km-tag {
        display: inline-block;
        color: #1C4A64;
        background: #E5F1F7;
        border: 1px solid #C4DFEE;
        border-radius: 999px;
        font-weight: 750;
        font-size: 0.69rem;
        padding: 0.32rem 0.72rem;
    }
    .faeg-km-group-label {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        color: #526579;
        font-size: 0.69rem;
        font-weight: 850;
        letter-spacing: 0.07em;
        text-transform: uppercase;
        margin: 0.65rem 0 0.55rem;
    }
    .faeg-km-group-label::after {
        content: "";
        flex: 1;
        height: 1px;
        background: #D9E3EA;
    }
    .faeg-km-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.8rem;
    }
    .faeg-km-card {
        background: #FFFFFF;
        border: 1px solid #DCE6EE;
        border-top: 3px solid #ABCEE1;
        border-radius: 0.55rem;
        padding: 1rem 1.1rem;
        min-width: 0;
    }
    .faeg-km-card.is-primary {
        background: #EFF6FA;
        border-color: #C7DCE9;
        border-top-color: #F34D25;
        border-top-width: 4px;
    }
    .faeg-km-card.is-unavailable {
        background: #F9FAFB;
    }
    .faeg-km-card-label {
        color: #4A6175;
        font-size: 0.7rem;
        font-weight: 800;
        letter-spacing: 0.045em;
        text-transform: uppercase;
        line-height: 1.4;
    }
    .faeg-km-card-value {
        color: #0D263C;
        font-size: clamp(1.15rem, 1.9vw, 1.65rem);
        font-weight: 850;
        margin-top: 0.4rem;
        line-height: 1.15;
        overflow-wrap: anywhere;
    }
    .faeg-km-card.is-primary .faeg-km-card-value {
        color: #113F5A;
    }
    .faeg-km-card.is-warning .faeg-km-card-value {
        color: #B84424;
    }
    .faeg-km-card-note {
        color: #61758A;
        font-size: 0.72rem;
        line-height: 1.45;
        margin-top: 0.5rem;
    }
    .faeg-km-formula {
        margin-top: 0.95rem;
        padding: 0.75rem 0.9rem;
        border-radius: 0.45rem;
        color: #23445B;
        font-size: 0.81rem;
        font-weight: 650;
        background: #EAF2F7;
        border: 1px solid #D2E3EF;
        line-height: 1.45;
    }
    @media (max-width: 950px) {
        .faeg-km-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .faeg-km-card.is-primary { grid-column: auto; }
    }
    @media (max-width: 600px) {
        .faeg-km-dashboard { padding: 0.9rem; }
        .faeg-km-grid { grid-template-columns: minmax(0, 1fr); }
        .faeg-km-card-value { font-size: 1.4rem; }
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


def fmt_km(val):
    return f"{to_float(val):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " km"


def exibir_indicadores(indicadores, colunas=3):
    """Mostra KPIs no mesmo padrão visual, mantendo os valores calculados pelo app."""
    colunas = max(1, min(int(colunas), 5))
    cartoes = []
    for item in indicadores:
        rotulo, valor = item[:2]
        destaque = len(item) > 2 and item[2] == "destaque"
        valor_texto = str(valor)
        classes = "faeg-indicator-card is-accent" if destaque else "faeg-indicator-card"
        classe_valor = "faeg-indicator-value is-long" if len(valor_texto) > 19 else "faeg-indicator-value"
        cartoes.append(
            f'<div class="{classes}">'
            f'<div class="faeg-indicator-label">{escape(str(rotulo))}</div>'
            f'<div class="{classe_valor}">{escape(valor_texto)}</div>'
            '</div>'
        )
    st.markdown(
        f'<div class="faeg-indicators-grid" style="--faeg-cols:{colunas}">'
        + "".join(cartoes) + '</div>',
        unsafe_allow_html=True,
    )


def formatar_rotulo_cliente(c):
    partes_nome = [c["razao_social"]]
    if (
        c.get("nome_fantasia")
        and c["nome_fantasia"].strip().lower() != c["razao_social"].strip().lower()
    ):
        partes_nome.append(f"({c['nome_fantasia']})")
    return " ".join(partes_nome)


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
        st.session_state["form_data"]["km_deslocamentos"] = 0.0
        st.session_state["form_data"]["km_saida_entre_coletas"] = 0.0
        st.session_state["form_data"]["km_retorno_operacional"] = 0.0
        st.session_state["form_data"]["km_componentes_discriminados"] = True
        st.session_state["km_componentes_editados"] = False
        if "w_ciclo_nome" in st.session_state:
            del st.session_state["w_ciclo_nome"]
        for chave in ("w_km_saida_entre_coletas", "w_km_retorno_operacional"):
            st.session_state.pop(chave, None)


def on_ciclo_nome_change():
    """Recupera componentes de KM compartilhados só com ID inequívoco."""
    sync_campo("w_ciclo_nome", "ciclo_nome")
    nome = (get_campo("ciclo_nome") or "").strip()
    km_deslocamentos = 0.0
    km_saida = 0.0
    km_retorno = 0.0
    discriminados = True
    if nome and get_campo("tipo_viagem") == "Ciclo":
        with SessionLocal() as session:
            ciclo = None
            id_viagem_aberta = st.session_state.get("viagem_ativa_id", 0)
            if id_viagem_aberta:
                viagem_aberta = session.query(Viagem).filter_by(
                    id_viagem=id_viagem_aberta,
                ).first()
                if (
                    viagem_aberta is not None and viagem_aberta.ciclo is not None
                    and viagem_aberta.ciclo.nome_operacao.strip().casefold() == nome.casefold()
                ):
                    ciclo = viagem_aberta.ciclo
            if ciclo is None:
                ciclos_encontrados = (
                    session.query(CicloOperacional)
                    .filter(func.lower(func.trim(CicloOperacional.nome_operacao)) == nome.lower())
                    .order_by(CicloOperacional.id_ciclo).limit(2).all()
                )
                if len(ciclos_encontrados) == 1:
                    ciclo = ciclos_encontrados[0]
                elif len(ciclos_encontrados) > 1:
                    st.warning(
                        f"Há mais de um ID interno para o ciclo '{nome}'. "
                        "O KM compartilhado não foi preenchido automaticamente."
                    )
            if ciclo is not None:
                km_deslocamentos = to_float(ciclo.km_deslocamentos_operacionais)
                discriminados = (
                    ciclo.km_saida_entre_coletas is not None
                    or ciclo.km_retorno_operacional is not None
                )
                km_saida = to_float(ciclo.km_saida_entre_coletas)
                km_retorno = to_float(ciclo.km_retorno_operacional)
    st.session_state["form_data"]["km_deslocamentos"] = km_deslocamentos
    st.session_state["form_data"]["km_saida_entre_coletas"] = km_saida
    st.session_state["form_data"]["km_retorno_operacional"] = km_retorno
    st.session_state["form_data"]["km_componentes_discriminados"] = discriminados
    st.session_state["km_componentes_editados"] = False
    for chave in ("w_km_saida_entre_coletas", "w_km_retorno_operacional"):
        st.session_state.pop(chave, None)


def on_km_componente_change(chave_widget, campo):
    """O valor composto passa a substituir o total legado só após edição."""
    sync_campo(chave_widget, campo)
    st.session_state["km_componentes_editados"] = True
    st.session_state["form_data"]["km_componentes_discriminados"] = True
    st.session_state["form_data"]["km_deslocamentos"] = round(
        to_float(get_campo("km_saida_entre_coletas", 0.0))
        + to_float(get_campo("km_retorno_operacional", 0.0)), 2
    )


def calcular_km_deslocamentos_formulario():
    """Preserva o total antigo até os dois campos novos serem informados."""
    if get_campo("km_componentes_discriminados", True):
        return round(
            to_float(get_campo("km_saida_entre_coletas", 0.0))
            + to_float(get_campo("km_retorno_operacional", 0.0)), 2
        )
    return round(to_float(get_campo("km_deslocamentos", 0.0)), 2)


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
def carregar_todos_recebimentos():
    """Registros confirmados ou cancelados, preservados para auditoria."""
    with SessionLocal() as session:
        return [
            {
                "id_recebimento": r.id_recebimento,
                "id_viagem": r.id_viagem,
                "codigo_viagem": resolver_codigo_viagem(r.viagem, r.viagem.ciclo),
                "id_frete": r.viagem.id_frete_externo or "-",
                "data_recebimento": r.data_recebimento,
                "tipo_parcela": r.tipo_parcela,
                "forma_pagamento": r.forma_pagamento,
                "referencia": r.referencia,
                "observacao": r.observacao,
                "valor_recebido": float(r.valor_recebido),
                "cancelado": bool(r.cancelado),
                "data_cancelamento": r.data_cancelamento,
                "motivo_cancelamento": r.motivo_cancelamento,
            }
            for r in session.query(RecebimentoFrete)
            .order_by(RecebimentoFrete.data_recebimento, RecebimentoFrete.id_recebimento)
            .all()
        ]


@st.cache_data(ttl=300, show_spinner=False)
def carregar_recebimentos_viagem(id_viagem):
    if not id_viagem:
        return []
    return [r for r in carregar_todos_recebimentos() if r["id_viagem"] == id_viagem]


@st.cache_data(ttl=300, show_spinner=False)
def carregar_todas_despesas_ciclo():
    """Despesas compartilhadas por ID do ciclo, nunca repetidas por frete."""
    with SessionLocal() as session:
        return [
            {
                "id_despesa_ciclo": d.id_despesa_ciclo,
                "id_ciclo": d.id_ciclo,
                "ciclo": d.ciclo.nome_operacao,
                "id_fornecedor": d.id_fornecedor,
                "tipo_despesa": d.tipo_despesa,
                "descricao_detalhe": d.descricao_detalhe,
                "quantidade": float(d.quantidade),
                "valor_unitario": float(d.valor_unitario),
                "valor_total": float(d.valor_total),
                "data_despesa": d.data_despesa,
                "cancelado": bool(d.cancelado),
                "data_cancelamento": d.data_cancelamento,
                "motivo_cancelamento": d.motivo_cancelamento,
            }
            for d in session.query(CicloDespesa)
            .order_by(CicloDespesa.data_despesa, CicloDespesa.id_despesa_ciclo)
            .all()
        ]


@st.cache_data(ttl=300, show_spinner=False)
def carregar_todas_despesas_veiculo():
    """Despesas ainda sem destino financeiro, preservadas por veículo."""
    with SessionLocal() as session:
        return [
            {
                "id_despesa_veiculo": d.id_despesa_veiculo,
                "id_veiculo": d.id_veiculo,
                "id_fornecedor": d.id_fornecedor,
                "tipo_despesa": d.tipo_despesa,
                "descricao_detalhe": d.descricao_detalhe,
                "quantidade": float(d.quantidade),
                "valor_unitario": float(d.valor_unitario),
                "valor_total": float(d.valor_total),
                "data_despesa": d.data_despesa,
                "cancelado": bool(d.cancelado),
                "data_cancelamento": d.data_cancelamento,
                "motivo_cancelamento": d.motivo_cancelamento,
                "id_despesa_viagem_destino": d.id_despesa_viagem_destino,
                "id_despesa_ciclo_destino": d.id_despesa_ciclo_destino,
                "data_atribuicao": d.data_atribuicao,
            }
            for d in session.query(VeiculoDespesa)
            .order_by(VeiculoDespesa.data_despesa, VeiculoDespesa.id_despesa_veiculo)
            .all()
        ]


@st.cache_data(ttl=300, show_spinner=False)
def carregar_historico_atribuicoes_veiculo():
    """Trilha de atribuições e estornos independente da situação atual."""
    with SessionLocal() as session:
        return [
            {
                "id_evento": e.id_evento,
                "id_despesa_veiculo": e.id_despesa_veiculo,
                "acao": e.acao,
                "tipo_destino": e.tipo_destino,
                "id_destino": e.id_destino,
                "id_lancamento_destino": e.id_lancamento_destino,
                "data_evento": e.data_evento,
                "motivo": e.motivo,
            }
            for e in session.query(VeiculoDespesaAtribuicao)
            .order_by(VeiculoDespesaAtribuicao.data_evento, VeiculoDespesaAtribuicao.id_evento)
            .all()
        ]


@st.cache_data(ttl=300, show_spinner=False)
def carregar_alertas_despesas_cruzadas():
    """Indícios para conferência humana, nunca exclusão automática de custos."""
    with SessionLocal() as session:
        return listar_semelhancas_entre_frete_ciclo(session)


def limpar_caches_atribuicao():
    """Renova indicadores após movimentar um custo entre destinos."""
    carregar_todas_despesas_veiculo.clear()
    carregar_historico_atribuicoes_veiculo.clear()
    carregar_alertas_despesas_cruzadas.clear()
    carregar_todas_despesas_ciclo.clear()
    carregar_despesas_viagem.clear()
    carregar_todas_viagens_consulta.clear()
    carregar_todos_abastecimentos.clear()
    carregar_abastecimentos_veiculo.clear()


@st.cache_data(ttl=300, show_spinner=False)
def carregar_todas_viagens_consulta():
    """Carrega visão consolidada de todas as viagens, ciclos, receitas e despesas para Consultas e BI."""
    with SessionLocal() as session:
        viagens_raw = session.query(Viagem).order_by(Viagem.id_viagem.desc()).all()
        despesas_all = session.query(ViagemDespesa).all()
        recebidos_por_viagem = {}
        # A consulta consolidada usa uma única sessão para viagens e recebimentos.
        # Não mistura os dados atuais das viagens com outro cache de 5 minutos.
        for id_viagem_receb, valor_recebido, cancelado in session.query(
            RecebimentoFrete.id_viagem,
            RecebimentoFrete.valor_recebido,
            RecebimentoFrete.cancelado,
        ).all():
            if not cancelado:
                recebidos_por_viagem[id_viagem_receb] = (
                    recebidos_por_viagem.get(id_viagem_receb, 0.0) + float(valor_recebido)
                )
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
                    "Data do Abastecimento": d.data_despesa if d.tipo_despesa in {"Posto de Combustível", "Abast. ARLA"} else None,
                    "Odômetro no Abastecimento (km)": d.odometro_abastecimento,
                }
            )

        lista = []
        for vg in viagens_raw:
            ciclo = vg.ciclo
            fin, cli = financeiro_e_cliente_do_frete(vg)
            mot = vg.motorista
            vei = vg.veiculo
            col = vg.local_coleta
            ent = vg.local_entrega

            cod_vg = cod_map.get(vg.id_viagem, f"V{vg.id_viagem}")
            v_div = to_float(fin.valor_divulgado) if fin else 0.0
            v_neg = to_float(fin.valor_negociado_total) if fin else 0.0
            v_adi = to_float(fin.valor_adiantamento) if fin else 0.0
            v_sal = to_float(fin.valor_saldo) if fin else 0.0
            total_previsto = v_adi + v_sal
            total_recebido_real = round(recebidos_por_viagem.get(vg.id_viagem, 0.0), 2)
            financeiro_individual = vg.financeiro_frete is not None
            # Uma linha financeira legada do CICLO não pode ser replicada como
            # receita individual em vários fretes do mesmo grupo.
            legado_ambiguo = (
                not financeiro_individual and ciclo is not None and len(ciclo.viagens) > 1
            )
            # Parcelas previstas NÃO são recebimentos nem receita negociada:
            # não substituem o valor negociado ausente no fechamento.
            receita_base = 0.0 if legado_ambiguo else v_neg
            saldo_a_receber_real = round(max(0.0, v_neg - total_recebido_real), 2) if not legado_ambiguo else None
            excedente_recebido = round(max(0.0, total_recebido_real - v_neg), 2) if not legado_ambiguo else None
            tot_desp = desp_por_viagem.get(vg.id_viagem, 0.0)
            res_liq = receita_base - tot_desp
            od_ini = to_int(vg.odometro_inicial)
            od_fim = to_int(vg.odometro_final)
            km_real = od_fim - od_ini if od_ini > 0 and od_fim >= od_ini else None
            custo_km = (tot_desp / km_real) if km_real else None
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
                    "id_veiculo": vg.id_veiculo,
                    "id_ciclo": vg.id_ciclo,
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
                    "financeiro_individual": financeiro_individual,
                    "financeiro_legado_ambiguo": legado_ambiguo,
                    "valor_adiantamento": v_adi,
                    "valor_saldo": v_sal,
                    "total_previsto": total_previsto,
                    "total_recebido": total_recebido_real,
                    "saldo_a_receber": saldo_a_receber_real,
                    "excedente_recebido": excedente_recebido,
                    "receita_base": receita_base,
                    "total_despesas": tot_desp,
                    "km_rota_planejado": to_float(vg.km_rota_planejado),
                    "km_deslocamentos_operacionais": to_float(ciclo.km_deslocamentos_operacionais) if ciclo else 0.0,
                    "km_saida_entre_coletas": (
                        to_float(ciclo.km_saida_entre_coletas)
                        if ciclo and ciclo.km_saida_entre_coletas is not None else None
                    ),
                    "km_retorno_operacional": (
                        to_float(ciclo.km_retorno_operacional)
                        if ciclo and ciclo.km_retorno_operacional is not None else None
                    ),
                    "resultado_liquido": res_liq,
                    "km_rodado": km_real,
                    "odometro_inicial": od_ini,
                    "odometro_final": od_fim,
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
                "odometro_abastecimento": d.odometro_abastecimento,
                "data_despesa": d.data_despesa,
            }
            for d in session.query(ViagemDespesa)
            .filter_by(id_viagem=id_viagem)
            .order_by(ViagemDespesa.id_despesa)
            .all()
        ]


@st.cache_data(ttl=300, show_spinner=False)
def carregar_todos_abastecimentos():
    """Histórico de abastecimentos por veículo, independente das viagens."""
    with SessionLocal() as session:
        origem_veiculos = {
            d.id_despesa_veiculo: d for d in session.query(VeiculoDespesa).all()
        }
        registros = [
            {
                "id_abastecimento": a.id_abastecimento,
                "id_veiculo": a.id_veiculo,
                "id_fornecedor": a.id_fornecedor,
                "id_despesa_viagem": a.id_despesa_viagem,
                "id_despesa_ciclo": a.id_despesa_ciclo,
                "id_despesa_veiculo": a.id_despesa_veiculo,
                "origem_financeira": (
                    "Frete" if a.id_despesa_viagem else
                    "Ciclo" if a.id_despesa_ciclo else
                    "Veículo → Frete" if (
                        a.id_despesa_veiculo and origem_veiculos.get(a.id_despesa_veiculo)
                        and origem_veiculos[a.id_despesa_veiculo].id_despesa_viagem_destino
                    ) else
                    "Veículo → Ciclo" if (
                        a.id_despesa_veiculo and origem_veiculos.get(a.id_despesa_veiculo)
                        and origem_veiculos[a.id_despesa_veiculo].id_despesa_ciclo_destino
                    ) else
                    "Veículo (pendente)" if a.id_despesa_veiculo else "Histórico anterior"
                ),
                "data_abastecimento": a.data_abastecimento,
                "tipo_combustivel": a.tipo_combustivel,
                "odometro": a.odometro,
                "litros": float(a.litros),
                "preco_litro": float(a.preco_litro),
                "valor_total": float(a.valor_total),
                "cancelado": bool(a.cancelado),
                "data_cancelamento": a.data_cancelamento,
                "motivo_cancelamento": a.motivo_cancelamento,
            }
            for a in session.query(Abastecimento)
            .order_by(Abastecimento.data_abastecimento, Abastecimento.id_abastecimento)
            .all()
        ]
    return calcular_indicadores_abastecimentos(registros)


@st.cache_data(ttl=300, show_spinner=False)
def carregar_abastecimentos_veiculo(id_veiculo):
    """Permite consultar o histórico mesmo sem nenhum frete cadastrado."""
    return [a for a in carregar_todos_abastecimentos() if a["id_veiculo"] == id_veiculo]


def registrar_abastecimento_do_lancamento(session, dados, campo_origem, id_origem):
    """Projeção operacional do MESMO custo financeiro, sem segundo registro na tela.

    A tabela abastecimentos é só histórico/consumo; NÃO integra o somatório do DRE.
    """
    if dados["tipo_despesa"] not in {"Posto de Combustível", "Abast. ARLA"}:
        return
    if not dados.get("id_veiculo_abast"):
        raise ValueError("Abastecimento requer veículo identificado.")
    session.add(Abastecimento(
        id_veiculo=dados["id_veiculo_abast"],
        id_fornecedor=dados.get("id_fornecedor") or None,
        data_abastecimento=dados["data_despesa"],
        tipo_combustivel="ARLA" if dados["tipo_despesa"] == "Abast. ARLA" else "Diesel",
        odometro=dados.get("odometro_abastecimento"),
        litros=dados["quantidade"],
        preco_litro=dados["valor_unitario"],
        valor_total=dados["valor_total"],
        **{campo_origem: id_origem},
    ))


def gerar_excel_base_completa(todas_viagens, desp_detalhadas, motoristas, veiculos, clientes, locais, fornecedores, abastecimentos=None, fechamentos_ciclos=None, recebimentos=None, despesas_ciclo=None, despesas_veiculo=None, atribuicoes_veiculo=None, alertas_despesas=None):
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
                "Receita Considerada (R$)": v["receita_base"],
                "Conferência Financeira": (
                    "Legado ambíguo — conferir" if v["financeiro_legado_ambiguo"]
                    else "Por frete"
                ),
                "Adiantamento (R$)": v["valor_adiantamento"],
                "Saldo (R$)": v["valor_saldo"],
                "Parcelas Previstas (R$)": v["total_previsto"],
                "Recebido de Fato (R$)": v["total_recebido"],
                "Saldo a Receber (R$)": v["saldo_a_receber"],
                "Excedente Recebido (R$)": v["excedente_recebido"],
                "Despesas Totais (R$)": v["total_despesas"],
                "Resultado Operacional Parcial (R$)": v["resultado_liquido"],
                "Margem (%)": (
                    round(v["margem_pct"], 2)
                    if v["receita_base"] > 0 and not v["financeiro_legado_ambiguo"] else None
                ),
                "KM Individual / Ciclo": v["km_rota_planejado"],
                "KM Saída / Entre Coletas (ciclo)": v["km_saida_entre_coletas"],
                "KM Retorno Operacional (ciclo)": v["km_retorno_operacional"],
                "KM Deslocamentos Total (ciclo)": v["km_deslocamentos_operacionais"],
                "Odômetro Inicial (operação)": v["odometro_inicial"] or None,
                "Odômetro Final (operação)": v["odometro_final"] or None,
                "KM Rodado": v["km_rodado"],
                "Custo por KM (R$)": round(v["custo_km"], 2) if v["custo_km"] is not None else None,
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
    veiculos_map = {v["id_veiculo"]: v["placa"] for v in veiculos}
    df_abast = pd.DataFrame([
        {
            "Data": a["data_abastecimento"].strftime("%d/%m/%Y"),
            "Placa": veiculos_map.get(a["id_veiculo"], "-"),
            "Veículo ID": a["id_veiculo"],
            "Tipo": a["tipo_combustivel"],
            "Odômetro (km)": a["odometro"],
            "Litros": a["litros"],
            "Preço por Litro (R$)": a["preco_litro"],
            "Valor Total (R$)": a["valor_total"],
            "Despesa Frete ID": a.get("id_despesa_viagem"),
            "Despesa Ciclo ID": a.get("id_despesa_ciclo"),
            "Despesa Veículo ID": a.get("id_despesa_veiculo"),
            "Origem Financeira": a.get("origem_financeira"),
            "Situação": "Cancelado" if a.get("cancelado") else "Ativo",
            "Data Cancelamento": a["data_cancelamento"].strftime("%d/%m/%Y") if a.get("data_cancelamento") else None,
            "Motivo Cancelamento": a.get("motivo_cancelamento"),
            "KM entre Diesel": a["km_intervalo"],
            "KM/L Indicativo": a["km_por_litro"],
            "R$/KM Indicativo": a["custo_por_km"],
            "Observação": a["observacao"],
        }
        for a in (abastecimentos or [])
    ], columns=[
        "Data", "Placa", "Veículo ID", "Tipo", "Odômetro (km)", "Litros",
        "Preço por Litro (R$)", "Valor Total (R$)",
        "Despesa Frete ID", "Despesa Ciclo ID", "Despesa Veículo ID", "Origem Financeira",
        "Situação", "Data Cancelamento", "Motivo Cancelamento", "KM entre Diesel",
        "KM/L Indicativo", "R$/KM Indicativo", "Observação",
    ])
    df_ciclos = pd.DataFrame([
        {
            "ID Interno Ciclo": f["id_ciclo"],
            "Código Ciclo": f["ciclo"],
            "Quantidade Fretes": f["qtd_fretes"],
            "IDs Frete": ", ".join(f["ids_frete"]),
            "Clientes": ", ".join(f["clientes"]),
            "Negociado (R$)": f["valor_negociado_total"],
            "Adiantamentos Previstos (R$)": f["adiantamentos_previstos"],
            "Saldos Previstos (R$)": f["saldos_previstos"],
            "Parcelas Previstas (R$)": f["parcelas_previstas"],
            "Recebido de Fato (R$)": f["total_recebido"],
            "Saldo a Receber (R$)": f["saldo_a_receber"],
            "Excedente Recebido (R$)": f["excedente_recebido"],
            "Despesas dos Fretes (R$)": f["despesas_fretes_total"],
            "Despesas Compartilhadas (R$)": f["despesas_compartilhadas_total"],
            "Despesas Financeiras (R$)": f["despesas_total"],
            "Resultado Operacional Parcial (R$)": f["resultado_operacional_parcial"],
            "KM Fretes Planejados": f["km_planejado_fretes"],
            "KM Saída / Entre Coletas": f["km_saida_entre_coletas"],
            "KM Retorno Operacional": f["km_retorno_operacional"],
            "KM Deslocamentos": f["km_deslocamentos_operacionais"],
            "KM Total Planejado": f["km_total_planejado"],
            "Fretes com Financeiro Legado Ambíguo": f["qtd_financeiros_legados_ambiguos"],
        }
        for f in (fechamentos_ciclos if fechamentos_ciclos is not None else consolidar_ciclos(todas_viagens))
    ], columns=[
        "ID Interno Ciclo", "Código Ciclo", "Quantidade Fretes", "IDs Frete",
        "Clientes", "Negociado (R$)", "Adiantamentos Previstos (R$)",
        "Saldos Previstos (R$)", "Parcelas Previstas (R$)",
        "Recebido de Fato (R$)", "Saldo a Receber (R$)", "Excedente Recebido (R$)",
        "Despesas dos Fretes (R$)", "Despesas Compartilhadas (R$)",
        "Despesas Financeiras (R$)", "Resultado Operacional Parcial (R$)",
        "KM Fretes Planejados", "KM Saída / Entre Coletas",
        "KM Retorno Operacional", "KM Deslocamentos", "KM Total Planejado",
        "Fretes com Financeiro Legado Ambíguo",
    ])
    df_recebimentos = pd.DataFrame([
        {
            "Código Viagem": r["codigo_viagem"],
            "ID Frete": r["id_frete"],
            "Data Recebimento": r["data_recebimento"].strftime("%d/%m/%Y"),
            "Tipo Parcela": r["tipo_parcela"],
            "Forma Pagamento": r["forma_pagamento"],
            "Referência": r["referencia"],
            "Observação": r["observacao"],
            "Valor (R$)": r["valor_recebido"],
            "Situação": "Cancelado" if r["cancelado"] else "Confirmado",
            "Data Cancelamento": r["data_cancelamento"].strftime("%d/%m/%Y") if r["data_cancelamento"] else None,
            "Motivo Cancelamento": r["motivo_cancelamento"],
        }
        for r in (recebimentos or [])
    ], columns=[
        "Código Viagem", "ID Frete", "Data Recebimento", "Tipo Parcela",
        "Forma Pagamento", "Referência", "Observação", "Valor (R$)",
        "Situação", "Data Cancelamento", "Motivo Cancelamento",
    ])
    fornecedores_map = {f["id_fornecedor"]: f["nome_fantasia"] for f in fornecedores}
    df_despesas_ciclo = pd.DataFrame([
        {
            "ID Despesa Ciclo": d["id_despesa_ciclo"],
            "ID Interno Ciclo": d["id_ciclo"],
            "Código Ciclo": d["ciclo"],
            "Data": d["data_despesa"].strftime("%d/%m/%Y"),
            "Categoria": d["tipo_despesa"],
            "Descrição": d["descricao_detalhe"],
            "Fornecedor": fornecedores_map.get(d["id_fornecedor"], "Não informado"),
            "Quantidade": d["quantidade"],
            "Valor Unitário (R$)": d["valor_unitario"],
            "Valor Total (R$)": d["valor_total"],
            "Situação": "Cancelada" if d["cancelado"] else "Ativa",
            "Data Cancelamento": d["data_cancelamento"].strftime("%d/%m/%Y") if d["data_cancelamento"] else None,
            "Motivo Cancelamento": d["motivo_cancelamento"],
        }
        for d in (despesas_ciclo or [])
    ], columns=[
        "ID Despesa Ciclo", "ID Interno Ciclo", "Código Ciclo", "Data",
        "Categoria", "Descrição", "Fornecedor", "Quantidade", "Valor Unitário (R$)",
        "Valor Total (R$)", "Situação", "Data Cancelamento", "Motivo Cancelamento",
    ])
    df_despesas_veiculo = pd.DataFrame([
        {
            "ID Despesa Veículo": d["id_despesa_veiculo"],
            "Placa": veiculos_map.get(d["id_veiculo"], "Não informada"),
            "ID Veículo": d["id_veiculo"],
            "Data": d["data_despesa"].strftime("%d/%m/%Y"),
            "Categoria": d["tipo_despesa"],
            "Descrição": d["descricao_detalhe"],
            "Fornecedor": fornecedores_map.get(d["id_fornecedor"], "Não informado"),
            "Quantidade": d["quantidade"],
            "Valor Unitário (R$)": d["valor_unitario"],
            "Valor Total (R$)": d["valor_total"],
            "Situação": (
                "Cancelada" if d["cancelado"] else
                "Atribuída ao frete" if d["id_despesa_viagem_destino"] else
                "Atribuída ao ciclo" if d["id_despesa_ciclo_destino"] else
                "Pendente de atribuição"
            ),
            "ID Despesa Frete Destino": d["id_despesa_viagem_destino"],
            "ID Despesa Ciclo Destino": d["id_despesa_ciclo_destino"],
            "Data Atribuição": d["data_atribuicao"].strftime("%d/%m/%Y") if d["data_atribuicao"] else None,
            "Data Cancelamento": d["data_cancelamento"].strftime("%d/%m/%Y") if d["data_cancelamento"] else None,
            "Motivo Cancelamento": d["motivo_cancelamento"],
        }
        for d in (despesas_veiculo or [])
    ], columns=[
        "ID Despesa Veículo", "Placa", "ID Veículo", "Data", "Categoria", "Descrição",
        "Fornecedor", "Quantidade", "Valor Unitário (R$)", "Valor Total (R$)",
        "Situação", "ID Despesa Frete Destino", "ID Despesa Ciclo Destino",
        "Data Atribuição", "Data Cancelamento", "Motivo Cancelamento",
    ])
    df_atribuicoes = pd.DataFrame([
        {
            "ID Evento": e["id_evento"],
            "ID Despesa Veículo": e["id_despesa_veiculo"],
            "Ação": e["acao"],
            "Tipo Destino": e["tipo_destino"],
            "ID Frete/Ciclo Interno": e["id_destino"],
            "ID Lançamento Destino": e["id_lancamento_destino"],
            "Data/Hora": e["data_evento"].strftime("%d/%m/%Y %H:%M"),
            "Justificativa": e["motivo"],
        }
        for e in (atribuicoes_veiculo or [])
    ], columns=[
        "ID Evento", "ID Despesa Veículo", "Ação", "Tipo Destino",
        "ID Frete/Ciclo Interno", "ID Lançamento Destino", "Data/Hora", "Justificativa",
    ])
    conciliacao = reconciliar_resultado_gerencial(todas_viagens, despesas_ciclo, despesas_veiculo)
    df_conciliacao = pd.DataFrame([
        {
            "Indicador": "Receita negociada considerada dos fretes",
            "Valor (R$)": conciliacao["receita_negociada_considerada"],
            "Tratamento": "Receita (financeiro legado ambíguo excluído)",
        },
        {
            "Indicador": "Despesas financeiras dos fretes",
            "Valor (R$)": conciliacao["despesas_fretes"],
            "Tratamento": "Subtrair uma vez (origem viagens_despesas)",
        },
        {
            "Indicador": "Despesas compartilhadas ativas dos ciclos",
            "Valor (R$)": conciliacao["despesas_compartilhadas"],
            "Tratamento": "Subtrair uma vez (origem ciclos_despesas), sem rateio",
        },
        {
            "Indicador": "Total de despesas contabilizadas",
            "Valor (R$)": conciliacao["despesas_financeiras_totais"],
            "Tratamento": "Fretes + compartilhadas; sem abastecimento duplicado",
        },
        {
            "Indicador": "Resultado operacional parcial gerencial",
            "Valor (R$)": conciliacao["resultado_operacional_parcial"],
            "Tratamento": "Receita considerada - despesas contabilizadas",
        },
        {
            "Indicador": "Despesas de veículo ainda pendentes",
            "Valor (R$)": conciliacao["despesas_veiculo_pendentes"],
            "Tratamento": "NÃO somar ao resultado enquanto não atribuídas",
        },
        {
            "Indicador": "Despesas de veículo já atribuídas (informativo)",
            "Valor (R$)": conciliacao["despesas_veiculo_ja_atribuidas"],
            "Tratamento": "JÁ incluídas no frete/ciclo — NÃO somar novamente",
        },
        {
            "Indicador": "Recebido efetivamente dos fretes",
            "Valor (R$)": conciliacao["total_recebido"],
            "Tratamento": "Fluxo recebido; não é receita negociada adicional",
        },
        {
            "Indicador": "Saldo a receber dos fretes",
            "Valor (R$)": conciliacao["saldo_a_receber"],
            "Tratamento": "Incalculável se houver financeiro legado ambíguo",
        },
        {
            "Indicador": "Conferência: fretes com financeiro legado ambíguo",
            "Valor (R$)": None,
            "Tratamento": (
                f"{conciliacao['qtd_financeiros_legados_ambiguos']} frete(s) — "
                "receita excluída até individualização; resultado parcial"
            ),
        },
        {
            "Indicador": "Conferência: despesas de ciclo sem frete do tipo Ciclo",
            "Valor (R$)": None,
            "Tratamento": (
                f"{conciliacao['qtd_despesas_ciclo_sem_fretes']} despesa(s) — "
                "incluídas no total gerencial, mas ausentes dos fechamentos por ciclo"
            ),
        },
    ], columns=["Indicador", "Valor (R$)", "Tratamento"])
    df_alertas_despesas = pd.DataFrame([
        {
            **a,
            "Data": a["Data"].strftime("%d/%m/%Y") if a.get("Data") else None,
        }
        for a in (alertas_despesas or [])
    ], columns=[
        "ID Ciclo", "Código Ciclo", "ID Frete", "ID Despesa Frete",
        "ID Despesa Ciclo", "Data", "Categoria", "Descrição", "Valor (R$)", "Situação",
    ])

    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_viagens.to_excel(writer, sheet_name="Viagens_e_Ciclos", index=False)
        df_desp.to_excel(writer, sheet_name="Despesas_Viagens", index=False)
        df_mot.to_excel(writer, sheet_name="Cad_Motoristas", index=False)
        df_vei.to_excel(writer, sheet_name="Cad_Veiculos", index=False)
        df_cli.to_excel(writer, sheet_name="Cad_Clientes", index=False)
        df_loc.to_excel(writer, sheet_name="Cad_Locais", index=False)
        df_forn.to_excel(writer, sheet_name="Cad_Fornecedores", index=False)
        df_abast.to_excel(writer, sheet_name="Abastecimentos_Veiculos", index=False)
        df_ciclos.to_excel(writer, sheet_name="Fechamento_Ciclos", index=False)
        df_conciliacao.to_excel(writer, sheet_name="Conferencia_Financeira", index=False)
        df_alertas_despesas.to_excel(writer, sheet_name="Possiveis_Duplicidades", index=False)
        df_recebimentos.to_excel(writer, sheet_name="Recebimentos_Fretes", index=False)
        df_despesas_ciclo.to_excel(writer, sheet_name="Despesas_Ciclo", index=False)
        df_despesas_veiculo.to_excel(writer, sheet_name="Despesas_Veiculo", index=False)
        df_atribuicoes.to_excel(writer, sheet_name="Atribuicoes_Despesas", index=False)

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


def _compilar_pdf_paginas(paginas_cmds):
    """Monta um PDF A4 com todas as páginas, sem descartar linhas de tabelas."""
    if not paginas_cmds:
        raise ValueError("O relatório PDF precisa ter ao menos uma página.")

    total_paginas = len(paginas_cmds)
    ids_paginas = " ".join(f"{5 + 2 * i} 0 R" for i in range(total_paginas))
    objs = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        f"2 0 obj\n<< /Type /Pages /Kids [{ids_paginas}] /Count {total_paginas} >>\nendobj\n".encode("ascii"),
        b"3 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>\nendobj\n",
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>\nendobj\n",
    ]

    for i, cmds in enumerate(paginas_cmds):
        id_pagina = 5 + 2 * i
        id_conteudo = id_pagina + 1
        comandos = list(cmds)
        comandos.append(
            f"BT /F1 8 Tf 0.40 0.46 0.52 rg 480 27 Td (Pagina {i + 1} de {total_paginas}) Tj ET"
        )
        compressed = zlib.compress("\n".join(comandos).encode("latin-1", "replace"))
        objs.append(
            f"{id_pagina} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {id_conteudo} 0 R >>\nendobj\n".encode("ascii")
        )
        objs.append(
            f"{id_conteudo} 0 obj\n<< /Length {len(compressed)} /Filter /FlateDecode >>\nstream\n".encode("ascii")
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


def _compilar_pdf_pagina_unica(cmds):
    """Compatibilidade com relatórios que tenham apenas uma página."""
    return _compilar_pdf_paginas([cmds])


def gerar_pdf_relatorio(dados_resumo, despesas_lista):
    cmds = []
    paginas = []

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
    text(40, 34, "FAEG - GESTAO LOGISTICA E OPERACIONAL", size=15, bold=True, r=1, g=1, b=1)
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
        ("Situacao:", dados_resumo["status"], "KM Real Rodado:", dados_resumo["km_real_fmt"]),
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
    text(55, y + 4, "RESULTADO OPERACIONAL PARCIAL:", size=10, bold=True, r=1, g=1, b=1)
    text(390, y + 4, dados_resumo["resultado_fmt"], size=13, bold=True, r=1, g=1, b=1)
    y += 46  # Reserva espaço entre o painel escuro e os indicadores complementares.

    text(42, y, f"Custo por KM: {dados_resumo['custo_km_fmt']}", size=10, bold=True)
    text(250, y, f"Margem Operacional: {dados_resumo['margem_fmt']}", size=10, bold=True)
    text(420, y, f"Parcelas previstas: {dados_resumo['parcelas_previstas_fmt']}", size=8, bold=False)
    y += 24
    text(42, y, f"Recebido de fato: {dados_resumo['recebido_real_fmt']}", size=10, bold=True)
    text(310, y, f"Saldo a receber: {dados_resumo['saldo_receber_fmt']}", size=10, bold=True)
    y += 22

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
        for idx_d, d in enumerate(despesas_lista):
            if y > 785:
                paginas.append(cmds)
                cmds = []
                rect(0, 0, 595, 76, 0.051, 0.149, 0.235)
                rect(0, 76, 595, 5, 0.953, 0.302, 0.145)
                text(40, 35, "FAEG - DESPESAS DA VIAGEM (CONTINUACAO)", size=14, bold=True, r=1, g=1, b=1)
                text(40, 55, f"Viagem: {dados_resumo['codigo']}  |  Frete: {dados_resumo['id_frete']}", size=10,
                     r=0.671, g=0.808, b=0.882)
                rect(40, 105, 515, 22, 0.914, 0.914, 0.914)
                text(48, 120, "3. DETALHAMENTO DE DESPESAS DA VIAGEM (CONTINUACAO)", size=10, bold=True)
                y = 152
                rect(40, y - 12, 515, 18, 0.051, 0.149, 0.235)
                text(46, y, "Categoria", size=8, bold=True, r=1, g=1, b=1)
                text(175, y, "Descricao / Local", size=8, bold=True, r=1, g=1, b=1)
                text(370, y, "Qtd", size=8, bold=True, r=1, g=1, b=1)
                text(420, y, "Unitario", size=8, bold=True, r=1, g=1, b=1)
                text(488, y, "Total", size=8, bold=True, r=1, g=1, b=1)
                y += 18
            if idx_d % 2 == 1:
                rect(40, y - 11, 515, 16, 0.965, 0.972, 0.985)
            text(46, y, str(d["tipo"])[:22], size=8)
            text(175, y, str(d["desc"])[:34], size=8)
            text(370, y, f"{d['qtd']:.2f}", size=8)
            text(420, y, d["unit_fmt"], size=8)
            text(488, y, d["total_fmt"], size=8, bold=True)
            y += 16

    paginas.append(cmds)
    return _compilar_pdf_paginas(paginas)


def gerar_pdf_relatorio_consolidado(resumo_geral, ranking_clientes, despesas_categorias):
    """Gera PDF executivo consolidado do Painel Geral / BI Operacional FAEG."""
    cmds = []
    paginas = []

    def rect(x, y_top, w, h, r, g, b):
        y = 842 - y_top - h
        cmds.append(f"{r:.3f} {g:.3f} {b:.3f} rg {x:.1f} {y:.1f} {w:.1f} {h:.1f} re f")

    def text(x, y_top, txt, size=10, bold=False, r=0.051, g=0.149, b=0.235):
        y = 842 - y_top
        font = "/F2" if bold else "/F1"
        cmds.append(
            f"BT {font} {size} Tf {r:.3f} {g:.3f} {b:.3f} rg {x:.1f} {y:.1f} Td ({_pdf_esc(txt)}) Tj ET"
        )

    def pagina_continuacao(titulo):
        nonlocal cmds
        paginas.append(cmds)
        cmds = []
        rect(0, 0, 595, 76, 0.051, 0.149, 0.235)
        rect(0, 76, 595, 5, 0.953, 0.302, 0.145)
        text(40, 34, "FAEG - RELATORIO EXECUTIVO CONSOLIDADO (BI)", size=14, bold=True, r=1, g=1, b=1)
        text(40, 54, f"Filtro aplicado: {resumo_geral['filtro_desc']}", size=9,
             r=0.671, g=0.808, b=0.882)
        rect(40, 103, 515, 22, 0.914, 0.914, 0.914)
        text(48, 118, titulo, size=10, bold=True)
        return 150

    def cabecalho_ranking(y_linha):
        rect(40, y_linha - 12, 515, 18, 0.051, 0.149, 0.235)
        text(46, y_linha, "Cliente", size=8, bold=True, r=1, g=1, b=1)
        text(245, y_linha, "Viagens", size=8, bold=True, r=1, g=1, b=1)
        text(300, y_linha, "Receita", size=8, bold=True, r=1, g=1, b=1)
        text(385, y_linha, "Despesas", size=8, bold=True, r=1, g=1, b=1)
        text(470, y_linha, "Resultado", size=8, bold=True, r=1, g=1, b=1)
        return y_linha + 18

    def cabecalho_categorias(y_linha):
        rect(40, y_linha - 12, 515, 18, 0.051, 0.149, 0.235)
        text(46, y_linha, "Categoria de Despesa", size=8, bold=True, r=1, g=1, b=1)
        text(330, y_linha, "Participacao (%)", size=8, bold=True, r=1, g=1, b=1)
        text(455, y_linha, "Total Acumulado", size=8, bold=True, r=1, g=1, b=1)
        return y_linha + 18

    rect(0, 0, 595, 76, 0.051, 0.149, 0.235)
    rect(0, 76, 595, 5, 0.953, 0.302, 0.145)
    text(40, 34, "FAEG - RELATORIO EXECUTIVO CONSOLIDADO (BI)", size=14, bold=True, r=1, g=1, b=1)
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
    text(310, y + 6, f"KM Registrado: {resumo_geral['km_total_fmt']}", size=10, bold=True, r=0.671, g=0.808, b=0.882)
    y += 24
    text(55, y + 6, "Receita Consolidada:", size=10, bold=False, r=1, g=1, b=1)
    text(210, y + 6, resumo_geral["receita_fmt"], size=10, bold=True, r=1, g=1, b=1)
    text(340, y + 6, "Despesas Fretes:", size=10, bold=False, r=1, g=1, b=1)
    text(445, y + 6, resumo_geral["despesa_fmt"], size=10, bold=True, r=0.953, g=0.302, b=0.145)
    y += 26
    text(55, y + 6, "RESULTADO OPERACIONAL PARCIAL:", size=10, bold=True, r=1, g=1, b=1)
    text(275, y + 6, resumo_geral["resultado_fmt"], size=12, bold=True, r=1, g=1, b=1)
    text(430, y + 6, f"Margem: {resumo_geral['margem_fmt']}", size=10, bold=True, r=0.671, g=0.808, b=0.882)
    text(55, y + 27, f"Recebido de fato: {resumo_geral['recebido_fmt']}", size=9, bold=True, r=1, g=1, b=1)
    text(300, y + 27, f"Saldo em aberto: {resumo_geral['saldo_fmt']}", size=9, bold=True, r=1, g=1, b=1)

    y += 42
    rect(40, y, 515, 22, 0.914, 0.914, 0.914)
    text(48, y + 15, "2. DESEMPENHO POR CLIENTE (SEM RATEIO)", size=10, bold=True)
    y += 34

    y = cabecalho_ranking(y)

    if not ranking_clientes:
        text(46, y, "Sem dados para exibir.", size=9)
        y += 18
    else:
        for idx_c, rc in enumerate(ranking_clientes):
            if y > 785:
                y = cabecalho_ranking(pagina_continuacao("2. DESEMPENHO POR CLIENTE (CONTINUACAO)"))
            if idx_c % 2 == 1:
                rect(40, y - 11, 515, 16, 0.965, 0.972, 0.985)
            text(46, y, str(rc["cliente"])[:34], size=8)
            text(255, y, str(rc["viagens"]), size=8)
            text(300, y, rc["receita_fmt"], size=8)
            text(385, y, rc["despesa_fmt"], size=8)
            text(470, y, rc["resultado_fmt"], size=8, bold=True)
            y += 16

    y += 14
    if y + 68 > 785:
        y = pagina_continuacao("3. DESPESAS POR FRETE / CATEGORIA (SEM RATEIO)")
    else:
        rect(40, y, 515, 22, 0.914, 0.914, 0.914)
        text(48, y + 15, "3. DESPESAS POR FRETE / CATEGORIA (SEM RATEIO)", size=10, bold=True)
        y += 34
    y = cabecalho_categorias(y)

    if not despesas_categorias:
        text(46, y, "Nenhuma despesa registrada no filtro atual.", size=9)
    else:
        for idx_cat, dc in enumerate(despesas_categorias):
            if y > 785:
                y = cabecalho_categorias(pagina_continuacao("3. DESPESAS POR CATEGORIA (CONTINUACAO)"))
            if idx_cat % 2 == 1:
                rect(40, y - 11, 515, 16, 0.965, 0.972, 0.985)
            text(46, y, str(dc["categoria"])[:42], size=8)
            text(340, y, dc["pct_fmt"], size=8)
            text(455, y, dc["total_fmt"], size=8, bold=True)
            y += 16

    paginas.append(cmds)
    return _compilar_pdf_paginas(paginas)


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
    st.session_state["km_componentes_editados"] = False
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
            "km_deslocamentos": 0.0,
            "km_saida_entre_coletas": 0.0,
            "km_retorno_operacional": 0.0,
            "km_componentes_discriminados": True,
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
                fin, cli = financeiro_e_cliente_do_frete(vg)
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
                    "km_deslocamentos": to_float(ciclo.km_deslocamentos_operacionais) if ciclo else 0.0,
                    "km_saida_entre_coletas": to_float(ciclo.km_saida_entre_coletas) if ciclo else 0.0,
                    "km_retorno_operacional": to_float(ciclo.km_retorno_operacional) if ciclo else 0.0,
                    "km_componentes_discriminados": (
                        ciclo.km_saida_entre_coletas is not None
                        or ciclo.km_retorno_operacional is not None
                    ) if ciclo else True,
                    "tipo_material": vg.tipo_material or "",
                    "qt_volumes": to_int(vg.qtde_volumes),
                    "volume_m3": to_float(vg.volume_m3),
                    "peso_kg": to_float(vg.peso_bruto_kg),
                    "nfe": vg.nfe_carga or "",
                    "cte": vg.cte_numero or "",
                    "mdfe": vg.mdfe_numero or "",
                    "ciot": vg.ciot_numero or "",
                    "cli_id": cli.id_cliente if cli else 0,
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


def preencher_financeiro_do_frete(financeiro, id_cliente):
    """Atualiza apenas as condições comerciais do frete selecionado."""
    financeiro.id_cliente = id_cliente
    financeiro.forma_contratacao = get_campo("forma_contrat", OPCOES_ORIGEM_FRETE[0])
    financeiro.valor_divulgado = to_float(get_campo("valor_divulgado", 0.0))
    financeiro.valor_negociado_total = to_float(get_campo("valor_negociado", 0.0))
    financeiro.perc_adiantamento = to_float(get_campo("perc_adiant", 0.0))
    financeiro.data_prevista_adiantamento = get_campo("data_adiant")
    financeiro.valor_adiantamento = to_float(get_campo("valor_adiant", 0.0))
    financeiro.perc_saldo = to_float(get_campo("perc_saldo", 0.0))
    financeiro.data_prevista_saldo = get_campo("data_saldo")
    financeiro.valor_saldo = to_float(get_campo("valor_saldo", 0.0))


def obter_ciclo_para_salvamento(session, tipo_viagem, nome_ciclo, id_cliente, data_operacao, viagem=None):
    """Agrupa fretes por ciclo, mas não altera silenciosamente outros fretes do grupo."""
    atual = viagem.ciclo if viagem is not None else None
    if atual and atual.nome_operacao.strip().casefold() == nome_ciclo.casefold():
        return atual

    encontrado = localizar_ciclo_operacional(session, nome_ciclo) if tipo_viagem == "Ciclo" else None
    if encontrado is not None:
        return encontrado

    # Se o ciclo antigo só tem este frete, renomeá-lo não afeta outros registros.
    if atual is not None and len(atual.viagens) == 1:
        atual.nome_operacao = nome_ciclo
        atual.id_cliente = id_cliente  # Cliente de referência; o cliente real fica no frete.
        return atual

    novo = CicloOperacional(
        id_cliente=id_cliente,
        nome_operacao=nome_ciclo,
        data_abertura=data_operacao,
        status_ciclo="Em Andamento",
    )
    session.add(novo)
    session.flush()
    return novo


def calcular_km_planejado_operacao(id_viagem_atual):
    """Soma KM dos fretes do mesmo ID INTERNO do ciclo, sem duplicar o atual.

    Nomes repetidos em ciclos históricos não autorizam juntar seus fretes.
    Enquanto o frete é editado, o ciclo salvo atual tem prioridade se o nome
    exibido ainda for o mesmo; para novos vínculos usa o primeiro ID localizado.
    """
    km_atual = to_float(get_campo("km_rota", 0.0))
    if get_campo("tipo_viagem", "Individual") != "Ciclo":
        return round(km_atual, 2)
    identificador = (get_campo("ciclo_nome") or "").strip()
    if not identificador:
        return round(km_atual, 2)

    with SessionLocal() as session:
        ciclo_atual = None
        if id_viagem_atual:
            viagem_atual = session.query(Viagem).filter_by(id_viagem=id_viagem_atual).first()
            if (
                viagem_atual is not None and viagem_atual.ciclo is not None
                and viagem_atual.ciclo.nome_operacao.strip().casefold() == identificador.casefold()
            ):
                ciclo_atual = viagem_atual.ciclo
        if ciclo_atual is None:
            ciclos_compativeis = (
                session.query(CicloOperacional)
                .filter(
                    func.lower(func.trim(CicloOperacional.nome_operacao)) == identificador.lower()
                )
                .order_by(CicloOperacional.id_ciclo).limit(2).all()
            )
            if len(ciclos_compativeis) > 1:
                st.warning(
                    f"Existem ciclos diferentes com o nome '{identificador}'. "
                    "O KM dos demais fretes não foi somado por aproximação de nome. "
                    "Confira o ID do ciclo antes de salvar."
                )
                return round(km_atual, 2)
            ciclo_atual = ciclos_compativeis[0] if ciclos_compativeis else None
        if ciclo_atual is None:
            return round(km_atual, 2)
        fretes_salvos = session.query(Viagem).filter_by(id_ciclo=ciclo_atual.id_ciclo).all()
        soma_outros = sum(
            to_float(v.km_rota_planejado)
            for v in fretes_salvos
            if v.id_viagem != id_viagem_atual
        )
    return round(km_atual + soma_outros, 2)


def calcular_km_total_real_operacao(id_viagem_atual, odo_inicial, odo_final):
    """Consolida trechos reais por ID de ciclo, sem somar odômetros sobrepostos.

    A dupla de odômetros no topo da Tela 8 refere-se ao frete atual. Para
    compará-la com o planejamento consolidado de um ciclo, todos os outros
    fretes precisam ter leituras válidas e intervalos não sobrepostos no
    mesmo veículo. Leituras ausentes/ambíguas não geram totais fictícios.
    """
    inicio = to_int(odo_inicial)
    fim = to_int(odo_final)
    if inicio <= 0 or fim < inicio or fim <= 0:
        return None
    if get_campo("tipo_viagem", "Individual") != "Ciclo":
        return fim - inicio

    nome = (get_campo("ciclo_nome") or "").strip()
    if not nome:
        return None
    with SessionLocal() as session:
        ciclo = None
        if id_viagem_atual:
            atual = session.query(Viagem).filter_by(id_viagem=id_viagem_atual).first()
            if (
                atual is not None and atual.ciclo is not None
                and atual.ciclo.nome_operacao.strip().casefold() == nome.casefold()
            ):
                ciclo = atual.ciclo
        if ciclo is None:
            candidatos = (
                session.query(CicloOperacional)
                .filter(func.lower(func.trim(CicloOperacional.nome_operacao)) == nome.lower())
                .order_by(CicloOperacional.id_ciclo).limit(2).all()
            )
            if len(candidatos) > 1:
                st.warning("KM Total Real indisponível: há mais de um ID interno para este nome de ciclo.")
                return None
            ciclo = candidatos[0] if candidatos else None
        outros = (
            session.query(Viagem).filter_by(id_ciclo=ciclo.id_ciclo).all()
            if ciclo is not None else []
        )

        intervalos = [(get_campo("vei_id", 0), inicio, fim)]
        for frete in outros:
            if frete.id_viagem == id_viagem_atual:
                continue
            ini_outro = to_int(frete.odometro_inicial)
            fim_outro = to_int(frete.odometro_final)
            if ini_outro <= 0 or fim_outro <= 0 or fim_outro < ini_outro:
                st.info(
                    "O KM Total Real do ciclo ainda não pode ser calculado: "
                    "existem fretes do mesmo ciclo sem odômetros válidos."
                )
                return None
            intervalos.append((frete.id_veiculo, ini_outro, fim_outro))

    for i, (veiculo_a, inicio_a, fim_a) in enumerate(intervalos):
        for veiculo_b, inicio_b, fim_b in intervalos[i + 1:]:
            if veiculo_a == veiculo_b and max(inicio_a, inicio_b) < min(fim_a, fim_b):
                st.warning(
                    "Os odômetros de fretes do ciclo apresentam intervalos sobrepostos "
                    "no mesmo veículo. Confira as leituras antes de consolidar o KM Total Real."
                )
                return None
    return sum(fim - inicio for _, inicio, fim in intervalos)


def montar_previa_financeira_ciclo(id_viagem_atual, despesas_frete_atual):
    """Considera fretes salvos e substitui o atual pelo formulário não salvo."""
    identificador = (get_campo("ciclo_nome") or "").strip()
    if get_campo("tipo_viagem", "Individual") != "Ciclo" or not identificador:
        return None

    todos, _ = carregar_todas_viagens_consulta()
    ativo_salvo = next((v for v in todos if v["id_viagem"] == id_viagem_atual), None)
    if ativo_salvo and ativo_salvo["ciclo"].strip().casefold() == identificador.casefold():
        id_ciclo = ativo_salvo["id_ciclo"]
    else:
        with SessionLocal() as session:
            existentes = (
                session.query(CicloOperacional.id_ciclo)
                .filter(
                    func.lower(func.trim(CicloOperacional.nome_operacao)) == identificador.lower()
                )
                .limit(2).all()
            )
            if len(existentes) > 1:
                st.warning(
                    "A prévia financeira deste nome de ciclo está indisponível "
                    "porque existem IDs internos duplicados. Confira a base antes "
                    "de associar um novo frete."
                )
                return None
            id_ciclo = existentes[0][0] if existentes else None

    outros = [
        v for v in todos
        if v["tipo_viagem"] == "Ciclo"
        and v["id_ciclo"] == id_ciclo
        and v["id_viagem"] != id_viagem_atual
    ] if id_ciclo is not None else []

    cli_obj = next((c for c in clientes_db if c["id_cliente"] == get_campo("cli_id", 0)), None)
    frete_atual = {
        "id_viagem": id_viagem_atual,
        "id_ciclo": id_ciclo,
        "codigo_viagem": get_campo("id_viagem_label") or "Em edição",
        "id_frete": get_campo("id_frete") or "-",
        "tipo_viagem": "Ciclo",
        "ciclo": identificador,
        "cliente": cli_obj["razao_social"] if cli_obj else "Não informado",
        "valor_negociado": to_float(get_campo("valor_negociado", 0.0)),
        "valor_adiantamento": to_float(get_campo("valor_adiant", 0.0)),
        "valor_saldo": to_float(get_campo("valor_saldo", 0.0)),
        "total_despesas": despesas_frete_atual,
        "total_recebido": round(sum(
            r["valor_recebido"] for r in carregar_recebimentos_viagem(id_viagem_atual)
            if not r["cancelado"]
        ), 2),
        "km_rota_planejado": to_float(get_campo("km_rota", 0.0)),
        "km_deslocamentos_operacionais": calcular_km_deslocamentos_formulario(),
        "km_saida_entre_coletas": (
            to_float(get_campo("km_saida_entre_coletas", 0.0))
            if get_campo("km_componentes_discriminados", True) else None
        ),
        "km_retorno_operacional": (
            to_float(get_campo("km_retorno_operacional", 0.0))
            if get_campo("km_componentes_discriminados", True) else None
        ),
        # Uma viagem antiga que só lê ciclos_financeiro permanece ambígua até
        # ser salva com seus próprios valores em fretes_financeiro.
        "financeiro_individual": ativo_salvo["financeiro_individual"] if ativo_salvo else True,
    }
    consolidados = consolidar_ciclos(outros + [frete_atual], carregar_todas_despesas_ciclo())
    return consolidados[0] if consolidados else None


def salvar_km_deslocamentos_ciclo(ciclo):
    """Salva a composição uma vez por ciclo, preservando totais legados."""
    if (
        get_campo("tipo_viagem", "Individual") == "Individual"
        or st.session_state.get("km_componentes_editados", False)
        or not ciclo.viagens
    ):
        ciclo.km_deslocamentos_operacionais = calcular_km_deslocamentos_formulario()
        if get_campo("km_componentes_discriminados", True):
            ciclo.km_saida_entre_coletas = to_float(get_campo("km_saida_entre_coletas", 0.0))
            ciclo.km_retorno_operacional = to_float(get_campo("km_retorno_operacional", 0.0))


def salvar_viagem_completa(id_viagem_atual, viagens_lista):
    mot_id = get_campo("mot_id", 0)
    vei_id = get_campo("vei_id", 0)
    cli_id = get_campo("cli_id", 0)
    col_id = get_campo("col_id", 0)
    ent_id = get_campo("ent_id", 0)
    tipo_viagem_val = get_campo("tipo_viagem", "Individual")
    tipo_frete_val = get_campo("tipo_frete", "Dedicado")
    ciclo_num_val = (get_campo("ciclo_nome") or "").strip()
    id_frete_digitado = (get_campo("id_frete") or "").strip()

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

    if id_viagem_atual == 0 and any(
        d.get("tipo_despesa") in {"Posto de Combustível", "Abast. ARLA"}
        and d.get("id_veiculo_abast")
        and d["id_veiculo_abast"] != vei_id
        for d in st.session_state.get("despesas_temp", [])
    ):
        st.error(
            "Há abastecimento temporário associado a outro veículo. "
            "Confira/remova esse lançamento na Etapa 7 antes de salvar o frete "
            "com a nova placa; o histórico de consumo não será deslocado automaticamente."
        )
        return

    data_coleta = get_campo("data_coleta")
    data_entrega = get_campo("data_entrega")
    if data_coleta is not None and data_entrega is not None and data_entrega < data_coleta:
        st.error(
            "A data de entrega não pode ser anterior à data de coleta. "
            "Confira as datas nas Etapas 5 e 6 antes de salvar a viagem."
        )
        return

    odo_ini = to_int(get_campo("odo_ini", 0))
    odo_fin = to_int(get_campo("odo_fin", 0))
    if odo_ini > 0 and odo_fin > 0 and odo_fin < odo_ini:
        st.error("O odômetro final não pode ser menor que o inicial. Corrija antes de salvar.")
        return
    # Zero significa leitura ainda não informada na estrutura antiga do banco.
    km_real = (odo_fin - odo_ini) if odo_ini > 0 and odo_fin > 0 else 0
    nome_ciclo = ciclo_num_val if tipo_viagem_val == "Ciclo" else f"Individual - {codigo_digitado}"

    origem_val = (get_campo("rota_origem") or "").strip()
    destino_val = (get_campo("rota_destino") or "").strip()
    rota_resumo_val = formatar_rota_exibicao(origem_val, destino_val)

    try:
        with SessionLocal() as session:
            if tipo_viagem_val == "Ciclo":
                ciclo_atual_de_edicao = (
                    session.query(Viagem).filter_by(id_viagem=id_viagem_atual).first()
                    if id_viagem_atual else None
                )
                mesmo_ciclo_salvo = (
                    ciclo_atual_de_edicao is not None
                    and ciclo_atual_de_edicao.ciclo is not None
                    and ciclo_atual_de_edicao.ciclo.nome_operacao.strip().casefold()
                    == ciclo_num_val.casefold()
                )
                if not mesmo_ciclo_salvo:
                    ciclos_com_mesmo_nome = (
                        session.query(CicloOperacional.id_ciclo)
                        .filter(func.lower(func.trim(CicloOperacional.nome_operacao)) == ciclo_num_val.lower())
                        .limit(3).all()
                    )
                    if len(ciclos_com_mesmo_nome) > 1:
                        ids = ", ".join(str(linha[0]) for linha in ciclos_com_mesmo_nome)
                        st.error(
                            f"O ciclo '{ciclo_num_val}' já possui mais de um ID interno "
                            f"({ids}). Não é seguro vincular automaticamente um novo frete. "
                            "Confira os ciclos históricos antes de escolher o destino."
                        )
                        return
            # O ID Frete identifica um serviço, mesmo quando vários fretes
            # integram o mesmo ciclo. Preservar históricos, mas não permitir
            # que um novo salvamento replique um ID já utilizado.
            if id_frete_digitado:
                outro_frete = session.query(Viagem).filter(
                    func.upper(func.trim(Viagem.id_frete_externo)) == id_frete_digitado.upper(),
                    Viagem.id_viagem != id_viagem_atual,
                ).first()
                if outro_frete:
                    st.error(
                        f"O ID Frete '{id_frete_digitado}' já pertence à viagem "
                        f"{outro_frete.codigo_viagem or outro_frete.id_viagem}. "
                        "Cada frete precisa de identificador próprio, mesmo dentro de um ciclo."
                    )
                    return
            if id_viagem_atual == 0:
                ciclo = obter_ciclo_para_salvamento(
                    session,
                    tipo_viagem_val,
                    nome_ciclo,
                    cli_id,
                    get_campo("data_op", date.today()),
                )
                salvar_km_deslocamentos_ciclo(ciclo)

                vg = Viagem(
                    id_ciclo=ciclo.id_ciclo,
                    id_motorista=mot_id,
                    id_veiculo=vei_id,
                    id_local_coleta=col_id,
                    id_local_entrega=ent_id,
                    codigo_viagem=codigo_digitado,
                    id_frete_externo=id_frete_digitado or None,
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

                financeiro_frete = FreteFinanceiro(id_viagem=vg.id_viagem, id_cliente=cli_id)
                preencher_financeiro_do_frete(financeiro_frete, cli_id)
                session.add(financeiro_frete)

                for dt in st.session_state.get("despesas_temp", []):
                    desp_salva = ViagemDespesa(
                            id_viagem=vg.id_viagem,
                            id_fornecedor=dt.get("id_fornecedor") or None,
                            tipo_despesa=dt["tipo_despesa"],
                            descricao_detalhe=dt["descricao_detalhe"],
                            quantidade=dt["quantidade"],
                            valor_unitario=dt["valor_unitario"],
                            valor_total=dt["valor_total"],
                            odometro_abastecimento=dt.get("odometro_abastecimento"),
                            data_despesa=dt.get("data_despesa"),
                    )
                    session.add(desp_salva)
                    session.flush()
                    if dt["tipo_despesa"] in {"Posto de Combustível", "Abast. ARLA"}:
                        dados_abast_temp = dict(dt)
                        dados_abast_temp["id_veiculo_abast"] = dt.get("id_veiculo_abast") or vg.id_veiculo
                        registrar_abastecimento_do_lancamento(
                            session, dados_abast_temp, "id_despesa_viagem", desp_salva.id_despesa,
                        )
                session.commit()
                st.session_state["viagem_ativa_id"] = vg.id_viagem
                st.session_state["loaded_viagem_id"] = None
                st.session_state["despesas_temp"] = []
                carregar_listas_base.clear()
                carregar_despesas_viagem.clear()
                carregar_todas_viagens_consulta.clear()
                carregar_todas_despesas_ciclo.clear()
                carregar_alertas_despesas_cruzadas.clear()
                carregar_todos_abastecimentos.clear()
                carregar_abastecimentos_veiculo.clear()
                carregar_todos_recebimentos.clear()
                carregar_recebimentos_viagem.clear()
                st.toast(f"Viagem {codigo_digitado} salva com sucesso no Neon!", icon="✅")
                st.rerun()
            else:
                vg = session.query(Viagem).filter_by(id_viagem=id_viagem_atual).first()
                if vg:
                    # O último frete de um ciclo não pode ser removido/renomeado
                    # enquanto houver despesas compartilhadas ativas naquele ID.
                    # A transferência automática dessas despesas seria indevida.
                    saindo_do_ciclo = (
                        vg.ciclo is not None
                        and (
                            vg.ciclo.nome_operacao.strip().casefold() != nome_ciclo.casefold()
                            or vg.tipo_viagem != tipo_viagem_val
                        )
                    )
                    if saindo_do_ciclo and len(vg.ciclo.viagens) == 1:
                        despesa_compartilhada_ativa = session.query(CicloDespesa).filter_by(
                            id_ciclo=vg.id_ciclo, cancelado=False,
                        ).first()
                        if despesa_compartilhada_ativa:
                            st.error(
                                "Este é o último frete de um ciclo com despesas compartilhadas "
                                "ativas. Confira/corrija essas despesas na Etapa 7 antes de "
                                "alterar o ID do ciclo ou transformar o frete em Individual."
                            )
                            return
                    # Uma despesa provisória já atribuída ao frete pertence ao
                    # veículo original. Trocar o veículo sem estornar a atribuição
                    # tornaria o vínculo financeiro inconsistente.
                    if vg.id_veiculo != vei_id:
                        atribuicao_incompativel = (
                            session.query(VeiculoDespesa)
                            .join(
                                ViagemDespesa,
                                VeiculoDespesa.id_despesa_viagem_destino == ViagemDespesa.id_despesa,
                            )
                            .filter(
                                ViagemDespesa.id_viagem == vg.id_viagem,
                                VeiculoDespesa.id_veiculo != vei_id,
                            )
                            .first()
                        )
                        if atribuicao_incompativel:
                            st.error(
                                "Este frete possui despesa provisória atribuída ao veículo anterior. "
                                "Estorne a atribuição na Etapa 7 antes de alterar o veículo do frete."
                            )
                            return
                        abastecimento_incompativel = (
                            session.query(Abastecimento)
                            .join(
                                ViagemDespesa,
                                Abastecimento.id_despesa_viagem == ViagemDespesa.id_despesa,
                            )
                            .filter(
                                ViagemDespesa.id_viagem == vg.id_viagem,
                                Abastecimento.cancelado.is_(False),
                                Abastecimento.id_veiculo != vei_id,
                            )
                            .first()
                        )
                        if abastecimento_incompativel:
                            st.error(
                                "Este frete já possui abastecimento registrado para o veículo "
                                "anterior. Confira/corrija esse lançamento na Etapa 7 antes de "
                                "alterar o veículo; o histórico de consumo não será transferido."
                            )
                            return
                    ciclo_destino = obter_ciclo_para_salvamento(
                        session,
                        tipo_viagem_val,
                        nome_ciclo,
                        cli_id,
                        get_campo("data_op", date.today()),
                        viagem=vg,
                    )
                    salvar_km_deslocamentos_ciclo(ciclo_destino)
                    vg.id_ciclo = ciclo_destino.id_ciclo
                    vg.codigo_viagem = codigo_digitado
                    vg.id_motorista = mot_id
                    vg.id_veiculo = vei_id
                    vg.id_local_coleta = col_id
                    vg.id_local_entrega = ent_id
                    vg.id_frete_externo = id_frete_digitado or None
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

                    financeiro_frete = vg.financeiro_frete
                    if financeiro_frete is None:
                        # Primeiro salvamento de um frete legado: copia a visão para
                        # a tabela individual, preservando o histórico do ciclo.
                        financeiro_frete = FreteFinanceiro(id_viagem=vg.id_viagem, id_cliente=cli_id)
                        session.add(financeiro_frete)
                    preencher_financeiro_do_frete(financeiro_frete, cli_id)
                    session.commit()
                    st.session_state["loaded_viagem_id"] = None
                    carregar_listas_base.clear()
                    carregar_despesas_viagem.clear()
                    carregar_todas_viagens_consulta.clear()
                    carregar_todas_despesas_ciclo.clear()
                    carregar_alertas_despesas_cruzadas.clear()
                    # Código e ID do frete aparecem também nas exportações de recebimentos.
                    carregar_todos_recebimentos.clear()
                    carregar_recebimentos_viagem.clear()
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

        # Prévia de leitura sem gravação. A importação depende da correção dos ciclos.
        with st.expander("📥 Conferir Planilha de Controle de Fretes (.xlsx)", expanded=False):
            st.caption(
                "Selecione a planilha FAEG para conferir fretes, ciclos e linhas de fechamento. "
                "Esta análise não altera o banco de dados."
            )
            up_file = st.file_uploader(
                "Selecione o arquivo Excel (.xlsx)",
                type=["xlsx"],
                key="uploader_planilha_faeg",
            )
            if up_file is not None:
                file_bytes = up_file.getvalue()
                analise = preparar_previa_importacao_faeg(file_bytes)
                if analise.get("erro"):
                    st.error(analise["erro"])
                else:
                    resumo_pl = analise["resumo"]
                    kp1, kp2, kp3, kp4 = st.columns(4)
                    kp1.metric("Fretes Identificados", resumo_pl["total_fretes"])
                    kp2.metric("Ciclos Distintos", resumo_pl["total_ciclos"])
                    kp3.metric("Linhas de Fechamento", resumo_pl["total_fechamentos"])
                    kp4.metric("Receita dos Fretes", fmt_brl(resumo_pl["receita_fretes"]))

                    st.info(
                        f"Ciclos com mais de um frete: {resumo_pl['ciclos_multifrete']}. "
                        f"Ciclos com clientes diferentes: {resumo_pl['ciclos_multicliente']}. "
                        "O cliente e os valores são próprios de cada frete."
                    )
                    st.caption(
                        "Despesas identificadas nas linhas dos fretes: "
                        f"{fmt_brl(resumo_pl['despesas_fretes'])}. "
                        "Os totais não incluem a conciliação de despesas dos fechamentos."
                    )

                    if analise.get("preview_df") is not None and not analise["preview_df"].empty:
                        st.dataframe(analise["preview_df"], use_container_width=True, hide_index=True)

                    with st.expander("🔎 Conferência dos fechamentos e possíveis divergências", expanded=True):
                        st.caption(
                            f"Fechamentos associados a fretes: {resumo_pl['fechamentos_de_fretes']} | "
                            f"Possíveis totais gerais: {resumo_pl['possiveis_resumos_gerais']} | "
                            f"IDs de ciclo ausentes: {resumo_pl['ids_fechamento_ausentes']} | "
                            f"IDs divergentes: {resumo_pl['ids_fechamento_divergentes']} | "
                            f"Valores divergentes: {resumo_pl['valores_fechamento_divergentes']}"
                        )
                        fechamento_df = analise.get("preview_fechamentos_df")
                        if fechamento_df is not None and not fechamento_df.empty:
                            st.dataframe(fechamento_df, use_container_width=True, hide_index=True)
                        if resumo_pl["fretes_sem_fechamento"]:
                            st.info(
                                f"Fretes sem linha posterior de fechamento: "
                                f"{resumo_pl['fretes_sem_fechamento']}. "
                                "Podem ser operações ainda em andamento."
                            )

                    for aviso in analise.get("avisos", []):
                        st.warning(aviso)

                    st.button(
                        "Confirmar Importação no Banco (temporariamente indisponível)",
                        key="btn_confirmar_import_planilha",
                        use_container_width=True,
                        disabled=True,
                        help="A rotina de gravação aguarda a correção dos vínculos de fretes e ciclos.",
                    )

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
                on_change=on_ciclo_nome_change,
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

        f1, f2, f3, f4 = st.columns([1.1, 1.3, 1.6, 1.6])
        with f1:
            st.text_input(
                "ID FRETE",
                value=get_campo("id_frete", ""),
                placeholder="Ex: FRT-102",
                help="Identificador próprio e único do serviço, independente do ID Ciclo. Não reutilize o mesmo ID em outro frete.",
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
        st.markdown('<div class="sec-subtitle">KM X ROTA PLANEJADO</div>', unsafe_allow_html=True)
        st.caption(
            "Preencha os trechos manualmente. Em um ciclo, os deslocamentos de saída/entre "
            "coletas e de retorno são compartilhados e entram uma única vez na Etapa 8. "
            "Não inclua nesses campos o trecho já lançado no KM Individual / Ciclo."
        )
        km1, km2, km3 = st.columns(3)
        with km1:
            st.number_input(
                "KM DE SAÍDA E DESLOCAMENTO ENTRE COLETAS",
                min_value=0.0,
                step=10.0,
                format="%.2f",
                value=to_float(get_campo("km_saida_entre_coletas", 0.0)),
                key="w_km_saida_entre_coletas",
                on_change=on_km_componente_change,
                args=("w_km_saida_entre_coletas", "km_saida_entre_coletas"),
                help="KM adicionais até a primeira coleta e entre coletas, excluindo os trechos já previstos em cada frete.",
            )
        with km2:
            st.number_input(
                "KM INDIVIDUAL / CICLO",
                min_value=0.0,
                step=10.0,
                format="%.2f",
                help=(
                    "Campo manual: informe o KM previsto deste ID Frete. "
                    "Se a viagem fizer parte de um ciclo, a Etapa 8 somará o KM "
                    "dos fretes do mesmo ID interno do ciclo, sem repetir este trecho."
                ),
                value=to_float(get_campo("km_rota", 0.0)),
                key="w_km_rota",
                on_change=sync_campo,
                args=("w_km_rota", "km_rota"),
            )
        with km3:
            st.number_input(
                "KM OPERACIONAL DE RETORNO",
                min_value=0.0,
                step=10.0,
                format="%.2f",
                value=to_float(get_campo("km_retorno_operacional", 0.0)),
                key="w_km_retorno_operacional",
                on_change=on_km_componente_change,
                args=("w_km_retorno_operacional", "km_retorno_operacional"),
                help="KM adicional de retorno após a última entrega, excluindo trechos já associados a fretes.",
            )
        if not get_campo("km_componentes_discriminados", True) and to_float(get_campo("km_deslocamentos", 0.0)) > 0:
            st.info(
                "Este ciclo tem KM de deslocamentos registrado na versão anterior, sem separar "
                "saída e retorno. O total antigo será preservado até você preencher os dois "
                "campos novos; confira a distribuição antes de salvar."
            )

        st.markdown('<div class="sec-subtitle">Odômetros da Operação</div>', unsafe_allow_html=True)
        st.caption(
            "Registre as leituras reais de início e fim da operação. Na Etapa 8, os valores "
            "serão exibidos para calcular o KM real. O odômetro de cada abastecimento "
            "continua no lançamento único da Etapa 7."
        )
        od1, od2 = st.columns(2)
        with od1:
            st.number_input(
                "KM ODÔMETRO INICIAL",
                min_value=0,
                step=10,
                value=to_int(get_campo("odo_ini", 0)),
                key="w_odo_ini",
                on_change=sync_campo,
                args=("w_odo_ini", "odo_ini"),
            )
        with od2:
            st.number_input(
                "KM ODÔMETRO FINAL",
                min_value=0,
                step=10,
                value=to_int(get_campo("odo_fin", 0)),
                key="w_odo_fin",
                on_change=sync_campo,
                args=("w_odo_fin", "odo_fin"),
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

        cli_sel = st.selectbox(
            "EMPRESA CLIENTE (RAZÃO SOCIAL / NOME FANTASIA) *",
            options=list(cli_ops.keys()),
            index=idx_cli,
            format_func=lambda x: cli_ops[x],
            key="w_cli_id",
            on_change=on_cliente_select_change,
            args=(locais_db,),
        )
        cli_obj = next((c for c in clientes_db if c["id_cliente"] == cli_sel), None)

        # Mesmo desenho das Etapas 5 e 6: cada dado cadastral em seu campo.
        ce1, ce2, ce3, ce4 = st.columns([0.9, 2.3, 1.3, 0.55])
        ce1.text_input("CEP", value=(cli_obj.get("cep") or "") if cli_obj else "", disabled=True, key=f"p_cli_cep_{cli_sel}")
        ce2.text_input(
            "ENDEREÇO COMPLETO",
            value=(cli_obj.get("endereco_completo") or "") if cli_obj else "",
            disabled=True,
            key=f"p_cli_end_{cli_sel}",
        )
        ce3.text_input(
            "CIDADE",
            value=(cli_obj.get("cidade") or "") if cli_obj else "",
            disabled=True,
            key=f"p_cli_cid_{cli_sel}",
        )
        ce4.text_input("UF", value=(cli_obj.get("uf") or "") if cli_obj else "", disabled=True, key=f"p_cli_uf_{cli_sel}")

        cc1, cc2, cc3 = st.columns([1.2, 1.0, 1.6])
        cc1.text_input(
            "RESPONSÁVEL",
            value=(cli_obj.get("responsavel_comercial") or "") if cli_obj else "",
            disabled=True,
            key=f"prev_cli_resp_{cli_sel}",
        )
        cc2.text_input(
            "TELEFONE / CONTATO",
            value=(cli_obj.get("telefone_comercial") or "") if cli_obj else "",
            disabled=True,
            key=f"prev_cli_tel_{cli_sel}",
        )
        cc3.text_input(
            "E-MAIL FINANCEIRO",
            value=(cli_obj.get("email_financeiro") or "") if cli_obj else "",
            disabled=True,
            key=f"prev_cli_email_{cli_sel}",
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

        st.info(
            "Um único lançamento para qualquer despesa, inclusive Diesel/ARLA. "
            "Selecione abaixo se pertence ao frete, ao ciclo inteiro ou provisoriamente "
            "ao veículo. O histórico de consumo é preenchido pelo mesmo registro de combustível, "
            "sem cadastrar o gasto novamente."
        )

        st.markdown('<div class="sec-subtitle">Adicionar Nova Despesa</div>', unsafe_allow_html=True)

        with SessionLocal() as db:
            ciclos_destino = {
                c.id_ciclo: c.nome_operacao
                for c in db.query(CicloOperacional)
                .order_by(CicloOperacional.nome_operacao, CicloOperacional.id_ciclo).all()
                if not c.nome_operacao.startswith("Individual - ")
            }
        veiculos_destino = {
            v["id_veiculo"]: f"{v['descricao_marca']} ({v['placa']})"
            for v in veiculos_db
        }
        opcoes_destino = ["Frete atual (ID Frete)"]
        if ciclos_destino:
            opcoes_destino.append("Ciclo inteiro (ID Ciclo)")
        if veiculos_destino:
            opcoes_destino.append("Veículo (sem frete/ciclo definido)")
        st.markdown("**Vínculo financeiro**")
        destino_desp = st.selectbox(
            "VINCULAR ESTA DESPESA A *", opcoes_destino,
            key="desp_destino_lancamento",
            help="O frete atual é o padrão. Uma despesa compartilhada não é copiada para cada frete.",
        )
        ciclo_desp_id = None
        veiculo_desp_id = None
        if destino_desp.startswith("Ciclo inteiro"):
            ciclo_desp_id = st.selectbox(
                "ID CICLO QUE RECEBERÁ ESTE CUSTO *", options=list(ciclos_destino),
                format_func=lambda x: f"{ciclos_destino[x]} (ID interno {x})",
                key="desp_ciclo_destino_unico",
            )
        elif destino_desp.startswith("Veículo"):
            veiculo_desp_id = st.selectbox(
                "VEÍCULO / PLACA *", options=list(veiculos_destino),
                format_func=lambda x: veiculos_destino[x], key="desp_veiculo_destino_unico",
            )

        # Um só formulário: vínculo, dados financeiros e complemento operacional.
        st.markdown("**Dados da despesa**")
        # Os campos de digitação são reiniciados somente após lançar com sucesso.
        # Categoria, fornecedor, vínculo e data permanecem para lançamentos em sequência.
        versao_campos_despesa = st.session_state.get("versao_campos_despesa", 0)
        c_d1, c_d2, c_d3 = st.columns([2.1, 2.5, 2.1])
        with c_d1:
            tipo_desp = st.selectbox("TIPO DE DESPESA", CATEGORIAS_DESPESA_FORNECEDOR, key="desp_tipo")
        with c_d2:
            desc_desp = st.text_input(
                "DESCRIÇÃO / LOCAL",
                placeholder="Ex: Abastecimento KM 120 / Pedágio",
                key=f"desp_desc_{versao_campos_despesa}",
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

        eh_combustivel = tipo_desp in {"Posto de Combustível", "Abast. ARLA"}
        if eh_combustivel:
            st.caption("Abastecimento: litros, preço e odômetro no mesmo lançamento financeiro.")
        # Sem campos vazios em despesas que não são combustível.
        colunas_valores = st.columns([1.3, 1.4, 1.6] if eh_combustivel else [1, 1])
        c_d4, c_d5 = colunas_valores[:2]
        with c_d4:
            qtd_desp = st.number_input("LITROS *" if eh_combustivel else "QUANTIDADE *", min_value=0.01, value=1.00, step=1.0, format="%.2f", key=f"desp_qtd_{versao_campos_despesa}")
        with c_d5:
            unit_desp = st.number_input("PREÇO / LITRO (R$) *" if eh_combustivel else "UNITÁRIO (R$) *", min_value=0.00, value=0.00, step=0.1 if eh_combustivel else 10.0, format="%.4f" if eh_combustivel else "%.2f", key=f"desp_unit_{versao_campos_despesa}")
        if eh_combustivel:
            c_d6 = colunas_valores[2]
            with c_d6:
                odometro_digitado = st.number_input(
                    "ODÔMETRO NO ABASTECIMENTO (KM)", min_value=0, value=0,
                    step=1, key=f"desp_odometro_abastecimento_{versao_campos_despesa}",
                    help="Digite diretamente a leitura do painel. Deixe 0 para não informado.",
                )
        else:
            odometro_digitado = 0
        odometro_abast = int(odometro_digitado) if odometro_digitado > 0 else None

        veiculo_abast_id = veiculo_desp_id
        if eh_combustivel and destino_desp.startswith("Frete"):
            veiculo_abast_id = get_campo("vei_id", 0)
            st.caption(
                "Abastecimento do veículo do frete atual: "
                + veiculos_destino.get(veiculo_abast_id, "veículo ainda não selecionado na Etapa 1")
            )
        elif eh_combustivel and destino_desp.startswith("Ciclo"):
            veiculo_abast_id = st.selectbox(
                "VEÍCULO QUE FOI ABASTECIDO *", options=list(veiculos_destino),
                format_func=lambda x: veiculos_destino[x], key="desp_veiculo_abast_ciclo",
            ) if veiculos_destino else None

        data_despesa_unica = st.date_input(
            "DATA DO ABASTECIMENTO *" if eh_combustivel else "DATA DA DESPESA *",
            value=date.today(), format="DD/MM/YYYY", key="desp_data_unica",
        )
        total_previsto_desp = round(qtd_desp * unit_desp, 2)
        st.markdown(f"**VALOR TOTAL DESTE LANÇAMENTO: {fmt_brl(total_previsto_desp)}**")
        if destino_desp.startswith("Veículo"):
            st.caption("Este gasto permanecerá pendente por veículo e NÃO comporá o resultado de fretes/ciclos até uma vinculação explícita futura.")
        elif destino_desp.startswith("Ciclo"):
            st.caption("Este custo será contabilizado uma única vez no resultado do ciclo, sem rateio por frete.")

        # Um indício de repetição entre frete e ciclo exige conferência explícita,
        # sem apagar, atribuir ou bloquear definitivamente gastos legítimos.
        possiveis_duplicidades = []
        confirmar_despesa_distinta = True
        if total_previsto_desp > 0 and not destino_desp.startswith("Veículo"):
            dados_conferencia = {
                "tipo_despesa": tipo_desp,
                "descricao_detalhe": desc_desp.strip() or tipo_desp,
                "id_fornecedor": forn_sel or None,
                "data_despesa": data_despesa_unica,
                "quantidade": round(qtd_desp, 2),
                "valor_unitario": round(unit_desp, 4 if eh_combustivel else 2),
                "valor_total": total_previsto_desp,
                "odometro_abastecimento": odometro_abast,
                "id_veiculo_abast": veiculo_abast_id,
            }
            with SessionLocal() as db:
                if destino_desp.startswith("Ciclo"):
                    id_ciclo_conferencia = ciclo_desp_id
                    tipo_conferencia = "Ciclo"
                else:
                    tipo_conferencia = "Frete"
                    if viagem_sel_id:
                        id_ciclo_conferencia = db.query(Viagem.id_ciclo).filter_by(
                            id_viagem=viagem_sel_id,
                        ).scalar()
                    elif get_campo("tipo_viagem", "Individual") == "Ciclo":
                        ciclo_conferencia = localizar_ciclo_operacional(
                            db, get_campo("ciclo_nome", "") or "",
                        )
                        id_ciclo_conferencia = (
                            ciclo_conferencia.id_ciclo if ciclo_conferencia else None
                        )
                    else:
                        id_ciclo_conferencia = None
                possiveis_duplicidades = procurar_semelhancas_cruzadas(
                    db, tipo_conferencia, id_ciclo_conferencia, dados_conferencia,
                )
            if possiveis_duplicidades:
                referencias = ", ".join(
                    f"{item['origem']} (despesa #{item['id_lancamento']})"
                    for item in possiveis_duplicidades[:4]
                )
                st.warning(
                    "Existe lançamento semelhante em outro destino financeiro deste ciclo: "
                    f"{referencias}. Confira nota/comprovante, veículo e a natureza do custo. "
                    "Pode ser despesa distinta; o sistema não faz alteração automática."
                )
                chave_confirmacao = zlib.crc32(
                    repr((dados_conferencia, tipo_conferencia, id_ciclo_conferencia,
                          tuple((d["origem"], d["id_lancamento"]) for d in possiveis_duplicidades))).encode()
                )
                confirmar_despesa_distinta = st.checkbox(
                    "Conferi o comprovante: este é um gasto distinto, não um segundo lançamento do mesmo custo.",
                    key=f"desp_similar_confirmar_{chave_confirmacao}_{st.session_state.get('desp_similar_versao', 0)}",
                )
        btn_add_desp = st.button("Registrar Despesa", use_container_width=True, key="btn_add_despesa")

        if btn_add_desp:
            if possiveis_duplicidades and not confirmar_despesa_distinta:
                st.warning("Confirme primeiro a conferência do comprovante para evitar contagem duplicada.")
            elif unit_desp <= 0:
                st.warning("Informe um valor unitário maior que R$ 0,00.")
            elif eh_combustivel and not veiculo_abast_id:
                st.warning("Selecione primeiro o veículo correto para registrar o abastecimento.")
            else:
                v_tot_item = round(qtd_desp * unit_desp, 2)
                dados_desp = {
                    "id_fornecedor": forn_sel or None,
                    "tipo_despesa": tipo_desp,
                    "descricao_detalhe": desc_desp.strip() or tipo_desp,
                    "quantidade": round(qtd_desp, 2),
                    "valor_unitario": round(unit_desp, 4 if eh_combustivel else 2),
                    "valor_total": v_tot_item,
                    "odometro_abastecimento": odometro_abast,
                    "data_despesa": data_despesa_unica,
                    "id_veiculo_abast": veiculo_abast_id if eh_combustivel else None,
                }
                if destino_desp.startswith("Frete") and viagem_sel_id == 0:
                    pendentes = st.session_state.setdefault("despesas_temp", [])
                    chaves_duplicidade_temp = (
                        "tipo_despesa", "data_despesa", "quantidade", "valor_total",
                        "odometro_abastecimento", "id_veiculo_abast",
                    ) if eh_combustivel else (
                        "tipo_despesa", "data_despesa", "quantidade", "valor_total",
                        "descricao_detalhe", "id_fornecedor",
                    )
                    ja_existe = any(
                        all(d.get(k) == dados_desp[k] for k in (
                            chaves_duplicidade_temp
                        )) for d in pendentes
                    )
                    if ja_existe:
                        st.warning("Esta despesa já está na lista temporária do frete.")
                        st.stop()
                    pendentes.append(dados_desp)
                    st.session_state["versao_campos_despesa"] = versao_campos_despesa + 1
                    st.session_state["desp_similar_versao"] = st.session_state.get("desp_similar_versao", 0) + 1
                    st.toast("Despesa adicionada à lista temporária!", icon="🧾")
                    st.rerun()
                else:
                    with SessionLocal() as db:
                        if destino_desp.startswith("Frete"):
                            consulta_existente = db.query(ViagemDespesa).filter_by(
                                id_viagem=viagem_sel_id,
                                tipo_despesa=tipo_desp,
                                data_despesa=data_despesa_unica,
                                quantidade=dados_desp["quantidade"],
                                valor_total=v_tot_item,
                            )
                            if eh_combustivel:
                                consulta_existente = consulta_existente.filter_by(
                                    odometro_abastecimento=odometro_abast,
                                )
                            else:
                                consulta_existente = consulta_existente.filter_by(
                                    descricao_detalhe=dados_desp["descricao_detalhe"],
                                    id_fornecedor=dados_desp["id_fornecedor"],
                                )
                            existente = consulta_existente.first()
                            if existente:
                                st.warning(
                                    "Esta despesa já consta neste frete. Se forem gastos "
                                    "distintos, diferencie a descrição/comprovante antes de registrar."
                                )
                                st.stop()
                            desp_obj = ViagemDespesa(
                                id_viagem=viagem_sel_id,
                                id_fornecedor=forn_sel if forn_sel != 0 else None,
                                tipo_despesa=tipo_desp,
                                descricao_detalhe=desc_desp.strip() or tipo_desp,
                                quantidade=round(qtd_desp, 2),
                                valor_unitario=dados_desp["valor_unitario"],
                                valor_total=v_tot_item,
                                odometro_abastecimento=odometro_abast,
                                data_despesa=data_despesa_unica,
                            )
                            db.add(desp_obj)
                            db.flush()
                            origem_campo, origem_id = "id_despesa_viagem", desp_obj.id_despesa
                        elif destino_desp.startswith("Ciclo"):
                            existente = db.query(CicloDespesa).filter_by(
                                id_ciclo=ciclo_desp_id,
                                tipo_despesa=tipo_desp,
                                descricao_detalhe=dados_desp["descricao_detalhe"],
                                data_despesa=data_despesa_unica,
                                valor_total=v_tot_item,
                                cancelado=False,
                            ).first()
                            if existente:
                                st.warning("Esta despesa já consta no ciclo. Confira antes de registrá-la novamente.")
                                st.stop()
                            desp_obj = CicloDespesa(id_ciclo=ciclo_desp_id, **{
                                k: dados_desp[k] for k in (
                                    "id_fornecedor", "tipo_despesa", "descricao_detalhe",
                                    "quantidade", "valor_unitario", "valor_total", "data_despesa",
                                )
                            })
                            db.add(desp_obj)
                            db.flush()
                            origem_campo, origem_id = "id_despesa_ciclo", desp_obj.id_despesa_ciclo
                        else:
                            existente = db.query(VeiculoDespesa).filter_by(
                                id_veiculo=veiculo_desp_id,
                                tipo_despesa=tipo_desp,
                                descricao_detalhe=dados_desp["descricao_detalhe"],
                                data_despesa=data_despesa_unica,
                                valor_total=v_tot_item,
                                cancelado=False,
                            ).first()
                            if existente:
                                st.warning("Esta despesa já está pendente para este veículo.")
                                st.stop()
                            desp_obj = VeiculoDespesa(id_veiculo=veiculo_desp_id, **{
                                k: dados_desp[k] for k in (
                                    "id_fornecedor", "tipo_despesa", "descricao_detalhe",
                                    "quantidade", "valor_unitario", "valor_total", "data_despesa",
                                )
                            })
                            db.add(desp_obj)
                            db.flush()
                            origem_campo, origem_id = "id_despesa_veiculo", desp_obj.id_despesa_veiculo
                        registrar_abastecimento_do_lancamento(db, dados_desp, origem_campo, origem_id)
                        db.commit()
                    st.session_state["versao_campos_despesa"] = versao_campos_despesa + 1
                    carregar_despesas_viagem.clear()
                    carregar_todas_viagens_consulta.clear()
                    carregar_todas_despesas_ciclo.clear()
                    carregar_todas_despesas_veiculo.clear()
                    carregar_alertas_despesas_cruzadas.clear()
                    carregar_todos_abastecimentos.clear()
                    carregar_abastecimentos_veiculo.clear()
                    st.session_state["desp_similar_versao"] = st.session_state.get("desp_similar_versao", 0) + 1
                    st.toast("Despesa registrada uma única vez no destino escolhido!", icon="✅")
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
                    "odometro_abastecimento": d.get("odometro_abastecimento"),
                    "data_despesa": d.get("data_despesa"),
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
                    "odometro_abastecimento": d.get("odometro_abastecimento"),
                    "data_despesa": d.get("data_despesa"),
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
                if item.get("data_despesa"):
                    data_tipo_rotulo = "Data do abastecimento" if item["tipo_despesa"] in {"Posto de Combustível", "Abast. ARLA"} else "Data da despesa"
                    col_t2.caption(f"{data_tipo_rotulo}: {item['data_despesa'].strftime('%d/%m/%Y')}")
                if item.get("odometro_abastecimento") is not None:
                    col_t2.caption(f"Odômetro no abastecimento: {item['odometro_abastecimento']} km")
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
                                origem_provisoria = db.query(VeiculoDespesa).filter_by(
                                    id_despesa_viagem_destino=obj_d.id_despesa
                                ).first()
                                if origem_provisoria:
                                    st.warning(
                                        "Esta despesa veio de um veículo. Para corrigir, use "
                                        "'Estornar atribuição' no histórico de despesas do veículo, "
                                        "preservando a rastreabilidade."
                                    )
                                else:
                                    # Abastecimento derivado sai junto com o custo
                                    # removido; não deixar medição órfã no histórico.
                                    db.query(Abastecimento).filter_by(
                                        id_despesa_viagem=obj_d.id_despesa
                                    ).delete(synchronize_session=False)
                                    db.delete(obj_d)
                                    db.commit()
                                    limpar_caches_atribuicao()
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

        with st.expander("🧾 Histórico das despesas compartilhadas dos ciclos (consulta/cancelamento)", expanded=False):
            st.caption(
                "Para NOVOS lançamentos, use apenas 'Adicionar Nova Despesa' acima, "
                "selecionando 'Ciclo inteiro'. Esta área permite conferir e cancelar lançamentos."
            )
            if not ciclos_destino:
                st.info("Ainda não há ciclos salvos. Salve primeiro um frete do tipo Ciclo para registrar uma despesa compartilhada.")
            else:
                ciclo_historico_id = st.selectbox(
                    "SELECIONE O CICLO PARA CONFERÊNCIA", options=list(ciclos_destino),
                    format_func=lambda x: f"{ciclos_destino[x]} (ID interno {x})",
                    key="desp_ciclo_historico_id",
                )
                historico_desp_ciclo = [
                    d for d in carregar_todas_despesas_ciclo() if d["id_ciclo"] == ciclo_historico_id
                ]
                if historico_desp_ciclo:
                    st.dataframe(
                        pd.DataFrame([
                            {
                                "Data": d["data_despesa"].strftime("%d/%m/%Y"),
                                "Tipo": d["tipo_despesa"],
                                "Descrição": d["descricao_detalhe"] or "-",
                                "Valor (R$)": d["valor_total"],
                                "Situação": "Cancelada" if d["cancelado"] else "Ativa",
                            }
                            for d in reversed(historico_desp_ciclo)
                        ]),
                        hide_index=True,
                        use_container_width=True,
                    )
                    ativas_ciclo = [d for d in historico_desp_ciclo if not d["cancelado"]]
                    exibir_indicadores(
                        [("DESPESAS COMPARTILHADAS ATIVAS DESTE CICLO", fmt_brl(sum(d["valor_total"] for d in ativas_ciclo)))],
                        colunas=3,
                    )
                    if ativas_ciclo:
                        with st.expander("Corrigir lançamento compartilhado (mantendo histórico)"):
                            opcoes_cancelar_dc = {d["id_despesa_ciclo"]: d for d in ativas_ciclo}
                            dc_cancel_id = st.selectbox(
                                "DESPESA A CANCELAR", options=list(opcoes_cancelar_dc),
                                format_func=lambda x: f"#{x} — {fmt_brl(opcoes_cancelar_dc[x]['valor_total'])}",
                                key="desp_ciclo_cancel_id",
                            )
                            dc_cancel_motivo = st.text_input(
                                "MOTIVO DO CANCELAMENTO *", max_chars=200,
                                key="desp_ciclo_cancel_motivo",
                            )
                            if st.button("Confirmar Cancelamento da Despesa", key="desp_ciclo_cancel_btn"):
                                if len(dc_cancel_motivo.strip()) < 6:
                                    st.warning("Informe um motivo com pelo menos 6 caracteres.")
                                else:
                                    with SessionLocal() as session:
                                        objeto = session.query(CicloDespesa).filter_by(
                                            id_despesa_ciclo=dc_cancel_id, id_ciclo=ciclo_historico_id, cancelado=False,
                                        ).first()
                                        if objeto:
                                            origem_provisoria = session.query(VeiculoDespesa).filter_by(
                                                id_despesa_ciclo_destino=dc_cancel_id
                                            ).first()
                                            if origem_provisoria:
                                                st.warning(
                                                    "Esta despesa foi atribuída a partir de um veículo. "
                                                    "Use 'Estornar atribuição' no histórico do veículo "
                                                    "para devolver o valor ao estado pendente."
                                                )
                                            else:
                                                objeto.cancelado = True
                                                objeto.data_cancelamento = date.today()
                                                objeto.motivo_cancelamento = dc_cancel_motivo.strip()
                                                for ab in session.query(Abastecimento).filter_by(id_despesa_ciclo=dc_cancel_id).all():
                                                    ab.cancelado = True
                                                    ab.data_cancelamento = date.today()
                                                    ab.motivo_cancelamento = dc_cancel_motivo.strip()
                                                session.commit()
                                                limpar_caches_atribuicao()
                                                st.toast("Despesa cancelada, mantendo histórico!", icon="🧾")
                                                st.rerun()
                else:
                    st.info("Nenhuma despesa compartilhada neste ciclo.")

        with st.expander("🚐 Despesas do veículo — conferir, atribuir ou estornar", expanded=False):
            st.caption(
                "Registre novas despesas SOMENTE no formulário acima. Aqui é possível "
                "vincular uma despesa provisória a frete/ciclo salvo ou estornar a atribuição. "
                "O histórico original e o abastecimento do veículo são preservados."
            )
            pendentes_veiculo = carregar_todas_despesas_veiculo()
            pendentes_ativos = {
                d["id_despesa_veiculo"]: d for d in pendentes_veiculo
                if not d["cancelado"] and not d["id_despesa_viagem_destino"] and not d["id_despesa_ciclo_destino"]
            }
            despesas_atribuidas = {
                d["id_despesa_veiculo"]: d for d in pendentes_veiculo
                if not d["cancelado"] and (d["id_despesa_viagem_destino"] or d["id_despesa_ciclo_destino"])
            }
            exibir_indicadores(
                [(
                    "TOTAL DE DESPESAS AINDA NÃO ATRIBUÍDAS",
                    fmt_brl(sum(d["valor_total"] for d in pendentes_ativos.values())),
                    "destaque",
                )],
                colunas=3,
            )
            if pendentes_veiculo:
                st.dataframe(
                    pd.DataFrame([
                        {
                            "ID": d["id_despesa_veiculo"],
                            "Data": d["data_despesa"].strftime("%d/%m/%Y"),
                            "Veículo": veiculos_destino.get(d["id_veiculo"], f"#{d['id_veiculo']}"),
                            "Categoria": d["tipo_despesa"],
                            "Descrição": d["descricao_detalhe"],
                            "Valor (R$)": d["valor_total"],
                            "Situação": (
                                "Cancelada" if d["cancelado"] else
                                "Atribuída a frete" if d["id_despesa_viagem_destino"] else
                                "Atribuída a ciclo" if d["id_despesa_ciclo_destino"] else
                                "Pendente"
                            ),
                            "Data Atribuição": d["data_atribuicao"].strftime("%d/%m/%Y") if d["data_atribuicao"] else None,
                        }
                        for d in reversed(pendentes_veiculo)
                    ]), hide_index=True, use_container_width=True,
                )
                if pendentes_ativos:
                    with st.expander("🔗 Atribuir despesa pendente a um frete ou ciclo", expanded=False):
                        atribuir_id = st.selectbox(
                            "DESPESA DE ORIGEM *", options=list(pendentes_ativos),
                            format_func=lambda x: (
                                f"#{x} — {veiculos_destino.get(pendentes_ativos[x]['id_veiculo'], '-')} "
                                f"— {fmt_brl(pendentes_ativos[x]['valor_total'])}"
                            ), key="atribuir_desp_veiculo_id",
                        )
                        atribuir_origem = pendentes_ativos[atribuir_id]
                        atribuir_tipo = st.selectbox(
                            "DESTINO FINANCEIRO *", ["Frete", "Ciclo"], key="atribuir_desp_tipo",
                        )
                        viagens_disponiveis, _ = carregar_todas_viagens_consulta()
                        viagens_compativeis = [
                            v for v in viagens_disponiveis if v["id_veiculo"] == atribuir_origem["id_veiculo"]
                        ]
                        if atribuir_tipo == "Frete":
                            opcoes_atribuir = {
                                v["id_viagem"]: f"{v['id_frete']} / {v['codigo_viagem']} — {v['cliente']}"
                                for v in viagens_compativeis
                            }
                        else:
                            opcoes_atribuir = {
                                v["id_ciclo"]: f"{ciclos_destino[v['id_ciclo']]} (ID {v['id_ciclo']})"
                                for v in viagens_compativeis
                                if v["tipo_viagem"] == "Ciclo" and v["id_ciclo"] in ciclos_destino
                            }
                        if not opcoes_atribuir:
                            st.info(
                                "Não há destino compatível com este veículo. Salve antes um "
                                "frete/ciclo que utilize a mesma placa. Nenhum custo será transferido."
                            )
                        else:
                            atribuir_destino_id = st.selectbox(
                                "ID DE DESTINO *", options=list(opcoes_atribuir),
                                format_func=lambda x: opcoes_atribuir[x],
                                key=f"atribuir_desp_destino_{atribuir_tipo}",
                            )
                            atribuir_motivo = st.text_input(
                                "JUSTIFICATIVA DA ATRIBUIÇÃO *", max_chars=200,
                                key="atribuir_desp_motivo",
                                help="Descreva por que este custo pertence ao destino escolhido.",
                            )
                            st.caption(
                                "Ao confirmar, o valor passará do estado pendente ao resultado do "
                                f"{atribuir_tipo.lower()} selecionado. O histórico do abastecimento "
                                "não será recriado nem somado duas vezes."
                            )
                            ciclo_da_atribuicao = (
                                next(
                                    (v["id_ciclo"] for v in viagens_compativeis
                                     if v["id_viagem"] == atribuir_destino_id),
                                    None,
                                ) if atribuir_tipo == "Frete" else atribuir_destino_id
                            )
                            with SessionLocal() as db:
                                ab_origem = db.query(Abastecimento).filter_by(
                                    id_despesa_veiculo=atribuir_id,
                                ).one_or_none()
                                dados_atribuicao = {
                                    **atribuir_origem,
                                    "id_veiculo_abast": atribuir_origem["id_veiculo"],
                                    "odometro_abastecimento": ab_origem.odometro if ab_origem else None,
                                }
                                coincidencias_atribuicao = procurar_semelhancas_cruzadas(
                                    db, atribuir_tipo, ciclo_da_atribuicao, dados_atribuicao,
                                )
                            confirmar_atribuicao_distinta = False
                            if coincidencias_atribuicao:
                                st.warning(
                                    "Há custo semelhante no outro destino financeiro deste ciclo "
                                    f"(despesa #{coincidencias_atribuicao[0]['id_lancamento']}). "
                                    "Confira o comprovante antes de transferir. Se for o mesmo gasto, "
                                    "corrija o lançamento anterior em vez de duplicá-lo."
                                )
                                confirmar_atribuicao_distinta = st.checkbox(
                                    "Conferi: são gastos distintos e a justificativa informa a diferença.",
                                    key=(
                                        f"atribuir_similar_confirmar_{atribuir_id}_"
                                        f"{atribuir_tipo}_{atribuir_destino_id}"
                                    ),
                                )
                            if st.button("Confirmar Atribuição", key="atribuir_desp_confirmar"):
                                try:
                                    with SessionLocal() as db:
                                        atribuir_despesa_veiculo(
                                            db, atribuir_id, atribuir_tipo,
                                            atribuir_destino_id, atribuir_motivo,
                                            confirmar_despesa_distinta=confirmar_atribuicao_distinta,
                                        )
                                        db.commit()
                                except ValueError as exc:
                                    st.warning(str(exc))
                                except Exception:
                                    st.error("Não foi possível atribuir a despesa. Nenhuma transferência foi confirmada.")
                                else:
                                    limpar_caches_atribuicao()
                                    st.toast("Despesa atribuída ao destino, com histórico preservado!", icon="✅")
                                    st.rerun()

                    with st.expander("Cancelar despesa provisória incorreta"):
                        desp_veic_cancel_id = st.selectbox(
                            "DESPESA PENDENTE", options=list(pendentes_ativos),
                            format_func=lambda x: f"#{x} — {fmt_brl(pendentes_ativos[x]['valor_total'])}",
                            key="desp_veic_cancel_id",
                        )
                        motivo_veic_cancel = st.text_input(
                            "MOTIVO DO CANCELAMENTO *", key="desp_veic_cancel_motivo", max_chars=200,
                        )
                        if st.button("Confirmar Cancelamento da Despesa Pendente", key="desp_veic_cancel_btn"):
                            if len(motivo_veic_cancel.strip()) < 6:
                                st.warning("Informe um motivo com pelo menos 6 caracteres.")
                            else:
                                with SessionLocal() as db:
                                    pendente_obj = db.query(VeiculoDespesa).filter_by(
                                        id_despesa_veiculo=desp_veic_cancel_id, cancelado=False,
                                        id_despesa_viagem_destino=None, id_despesa_ciclo_destino=None,
                                    ).with_for_update().first()
                                    if pendente_obj:
                                        pendente_obj.cancelado = True
                                        pendente_obj.data_cancelamento = date.today()
                                        pendente_obj.motivo_cancelamento = motivo_veic_cancel.strip()
                                        for ab in db.query(Abastecimento).filter_by(id_despesa_veiculo=desp_veic_cancel_id).all():
                                            ab.cancelado = True
                                            ab.data_cancelamento = date.today()
                                            ab.motivo_cancelamento = motivo_veic_cancel.strip()
                                        db.commit()
                                        limpar_caches_atribuicao()
                                        st.toast("Despesa provisória cancelada, mantendo histórico.", icon="🧾")
                                        st.rerun()

                if despesas_atribuidas:
                    with st.expander("↩️ Estornar atribuição e devolver a pendente", expanded=False):
                        estornar_id = st.selectbox(
                            "DESPESA ATRIBUÍDA *", options=list(despesas_atribuidas),
                            format_func=lambda x: (
                                f"#{x} — {fmt_brl(despesas_atribuidas[x]['valor_total'])} "
                                f"— {'Frete' if despesas_atribuidas[x]['id_despesa_viagem_destino'] else 'Ciclo'}"
                            ), key="estornar_desp_veiculo_id",
                        )
                        estornar_motivo = st.text_input(
                            "JUSTIFICATIVA DO ESTORNO *", max_chars=200,
                            key="estornar_desp_motivo",
                        )
                        st.caption(
                            "O custo deixará o resultado do destino e voltará a ficar pendente "
                            "no veículo. O histórico operacional de abastecimento não será "
                            "duplicado. A movimentação será registrada para auditoria."
                        )
                        if st.button("Confirmar Estorno da Atribuição", key="estornar_desp_confirmar"):
                            try:
                                with SessionLocal() as db:
                                    estornar_atribuicao_veiculo(db, estornar_id, estornar_motivo)
                                    db.commit()
                            except ValueError as exc:
                                st.warning(str(exc))
                            except Exception:
                                st.error("Não foi possível estornar a atribuição. Nenhuma mudança foi confirmada.")
                            else:
                                limpar_caches_atribuicao()
                                st.toast("Atribuição estornada; despesa voltou a pendente!", icon="✅")
                                st.rerun()

                historico_movimentacoes = carregar_historico_atribuicoes_veiculo()
                if historico_movimentacoes:
                    st.markdown("**Histórico de atribuições e estornos**")
                    st.dataframe(pd.DataFrame([
                        {
                            "Data e Hora": e["data_evento"].strftime("%d/%m/%Y %H:%M"),
                            "ID Despesa Veículo": e["id_despesa_veiculo"],
                            "Ação": e["acao"],
                            "Destino": e["tipo_destino"],
                            "ID Frete/Ciclo Interno": e["id_destino"],
                            "ID Lançamento no Destino": e["id_lancamento_destino"],
                            "Justificativa": e["motivo"],
                        }
                        for e in reversed(historico_movimentacoes)
                    ]), hide_index=True, use_container_width=True)
            else:
                st.info("Nenhuma despesa provisória vinculada a veículos.")

        with st.expander("⛽ Histórico de abastecimentos e consumo (somente consulta)", expanded=False):
            st.caption(
                "Não é necessário lançar combustível aqui. Cada abastecimento aparece quando "
                "a despesa de Diesel ou ARLA é registrada acima, com veículo e odômetro. "
                "A tabela operacional não acrescenta valor ao DRE."
            )
            if not veiculos_destino:
                st.info("Cadastre um veículo na Etapa 11 para obter o histórico.")
            else:
                consulta_veic_id = st.selectbox(
                    "VEÍCULO PARA CONSULTA", options=list(veiculos_destino),
                    format_func=lambda x: veiculos_destino[x], key="desp_historico_veiculo",
                )
                abast_historico = carregar_abastecimentos_veiculo(consulta_veic_id)
                if not abast_historico:
                    st.info("Nenhum abastecimento registrado para este veículo.")
                else:
                    st.dataframe(pd.DataFrame([
                        {
                            "Data": a["data_abastecimento"].strftime("%d/%m/%Y"),
                            "Combustível": a["tipo_combustivel"],
                            "Odômetro (km)": a["odometro"],
                            "Litros": a["litros"],
                            "Valor (R$)": a["valor_total"],
                            "KM entre Diesel": a["km_intervalo"],
                            "KM/L (indicativo)": a["km_por_litro"],
                            "R$/KM (indicativo)": a["custo_por_km"],
                            "Origem": a["origem_financeira"],
                            "Situação": "Cancelado" if a["cancelado"] else "Ativo",
                            "Observação": a["observacao"],
                        }
                        for a in reversed(abast_historico)
                    ]), hide_index=True, use_container_width=True)
                    st.caption(
                        "KM/L e R$/KM são apenas indicadores entre dois registros consecutivos "
                        "de Diesel do mesmo veículo. Abastecimentos parciais, registros faltantes "
                        "ou odômetros inconsistentes não permitem afirmar consumo real; "
                        "ARLA não entra no KM/L."
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

        st.markdown('<div class="sec-subtitle">Leituras e situação da operação</div>', unsafe_allow_html=True)
        f1, f2, f3, f4 = st.columns([1.1, 1.1, 1.1, 1.7])
        odo_ini_v = to_int(get_campo("odo_ini", 0))
        odo_fin_v = to_int(get_campo("odo_fin", 0))
        with f1:
            odo_ini_v = st.number_input(
                "ODÔMETRO INICIAL",
                min_value=0,
                step=10,
                value=odo_ini_v,
                key="w_odo_ini",
                on_change=sync_campo,
                args=("w_odo_ini", "odo_ini"),
            )
        with f2:
            odo_fin_v = st.number_input(
                "ODÔMETRO FINAL",
                min_value=0,
                step=10,
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
            "Soma dos intervalos válidos dos fretes do ciclo."
            if get_campo("tipo_viagem", "Individual") == "Ciclo"
            else "Diferença entre os dois odômetros da operação."
        )
        etiqueta_operacao = (
            "Ciclo operacional" if get_campo("tipo_viagem", "Individual") == "Ciclo"
            else "Frete individual"
        )
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
                        <div class="faeg-km-card-label">KM planejado dos fretes</div>
                        <div class="faeg-km-card-value">{fmt_km(km_planejado_op)}</div>
                        <div class="faeg-km-card-note">Trechos informados na Etapa 2.</div>
                    </article>
                    <article class="faeg-km-card">
                        <div class="faeg-km-card-label">KM deslocamentos operacionais</div>
                        <div class="faeg-km-card-value">{fmt_km(km_deslocamentos_op)}</div>
                        <div class="faeg-km-card-note">Saída / entre coletas + retorno.</div>
                    </article>
                    <article class="faeg-km-card is-primary">
                        <div class="faeg-km-card-label">KM total planejado</div>
                        <div class="faeg-km-card-value">{fmt_km(km_total_previsto_op)}</div>
                        <div class="faeg-km-card-note">Fretes + deslocamentos, sem repetição.</div>
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

        if to_float(get_campo("km_rota", 0.0)) <= 0:
            st.warning(
                "O campo KM INDIVIDUAL / CICLO do frete atual ainda está zerado "
                "na Etapa 2. Confira se o trecho foi realmente planejado antes "
                "de considerar o KM Total Planejado como completo."
            )

        with st.expander("Ver detalhes dos cálculos de KM", expanded=False):
            st.markdown(
                "**KM planejado:** no frete individual, usa o KM manual da Etapa 2; "
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
                "O KM real consolidado e seu desvio ficam indisponíveis até haver "
                "odômetros válidos para os fretes envolvidos, sem intervalos sobrepostos."
            )

        v_neg_dre = to_float(get_campo("valor_negociado", 0.0))
        v_rec_dre = to_float(get_campo("valor_adiant", 0.0)) + to_float(get_campo("valor_saldo", 0.0))
        receita_dre = v_neg_dre

        if viagem_sel_id == 0:
            custos_dre = sum(to_float(d["valor_total"]) for d in st.session_state.get("despesas_temp", []))
        else:
            custos_dre = sum(to_float(d["valor_total"]) for d in carregar_despesas_viagem(viagem_sel_id))

        resultado_dre = receita_dre - custos_dre
        cor_res = "#4ADE80" if resultado_dre >= 0 else "#F87171"

        st.markdown(
            f"""
            <div class="dre-box">
                <div class="dre-header">Resultado Operacional Parcial da Viagem (DRE — FAEG)</div>
                <div class="dre-row">
                    <span style="color:#ABCEE1;">Receita Prevista (Frete Negociado)</span>
                    <span style="font-weight:800; font-size:1.15rem;">{fmt_brl(receita_dre)}</span>
                </div>
                <div class="dre-row">
                    <span style="color:#ABCEE1;">Custos Totais (Combustível, Pedágios e Outras Despesas)</span>
                    <span style="font-weight:800; font-size:1.15rem; color:#F34D25;">- {fmt_brl(custos_dre)}</span>
                </div>
                <div class="dre-total-row">
                    <span style="font-weight:800; text-transform:uppercase; letter-spacing:0.04em;">Resultado Operacional Parcial</span>
                    <span style="font-weight:900; font-size:1.85rem; color:{cor_res};">{fmt_brl(resultado_dre)}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption("Custos do histórico de abastecimentos por veículo não são somados aqui; apenas despesas financeiras vinculadas a esta viagem entram no resultado.")

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
        todos_abast_exp = carregar_todos_abastecimentos()
        xlsx_bytes_completo = gerar_excel_base_completa(
            todas_vg_exp, desp_det_exp, motoristas_db, veiculos_db, clientes_db, locais_db, fornecedores_db,
            abastecimentos=todos_abast_exp,
            fechamentos_ciclos=consolidar_ciclos(todas_vg_exp, carregar_todas_despesas_ciclo()),
            recebimentos=carregar_todos_recebimentos(),
            despesas_ciclo=carregar_todas_despesas_ciclo(),
            despesas_veiculo=carregar_todas_despesas_veiculo(),
            atribuicoes_veiculo=carregar_historico_atribuicoes_veiculo(),
            alertas_despesas=carregar_alertas_despesas_cruzadas(),
        )

        tab_rel_viagem, tab_rel_geral, tab_rel_ciclos, tab_rel_conferencia = st.tabs(
            [
                "📄 Relatório da Viagem Ativa",
                "📊 Painel Geral (BI Consolidado)",
                "📚 Fechamento por Ciclo",
                "🧾 Conferência Financeira Geral",
            ]
        )

        # ----------------------------------------------------------------------
        # SUB-ABA 1: RELATÓRIO DA VIAGEM ATIVA
        # ----------------------------------------------------------------------
        with tab_rel_viagem:
            v_neg_r = to_float(get_campo("valor_negociado", 0.0))
            v_rec_r = to_float(get_campo("valor_adiant", 0.0)) + to_float(get_campo("valor_saldo", 0.0))
            receita_r = v_neg_r
            receb_real_r = round(sum(
                r["valor_recebido"] for r in carregar_recebimentos_viagem(viagem_sel_id)
                if not r["cancelado"]
            ), 2)
            saldo_real_r = max(0.0, receita_r - receb_real_r)

            if viagem_sel_id == 0:
                desps_r = st.session_state.get("despesas_temp", [])
            else:
                desps_r = carregar_despesas_viagem(viagem_sel_id)

            custos_r = sum(to_float(d["valor_total"]) for d in desps_r)
            resultado_r = receita_r - custos_r
            od_inicio_rel = to_int(get_campo("odo_ini", 0))
            od_final_rel = to_int(get_campo("odo_fin", 0))
            km_r = (
                od_final_rel - od_inicio_rel
                if od_inicio_rel > 0 and od_final_rel >= od_inicio_rel
                else None
            )
            custo_km_r = (custos_r / km_r) if km_r else None
            margem_r = ((resultado_r / receita_r) * 100.0) if receita_r > 0 else None

            exibir_indicadores(
                [
                    ("Receita Negociada", fmt_brl(receita_r)),
                    ("Custos Totais", fmt_brl(custos_r)),
                    ("Resultado Operacional Parcial", fmt_brl(resultado_r), "destaque"),
                    ("Custo por KM", fmt_brl(custo_km_r) if custo_km_r is not None else "Não informado"),
                    ("Margem Operacional", f"{margem_r:.1f}%" if margem_r is not None else "Não calculável"),
                ],
                colunas=5,
            )
            exibir_indicadores(
                [
                    ("Recebido de Fato", fmt_brl(receb_real_r)),
                    ("Saldo a Receber", fmt_brl(saldo_real_r), "destaque"),
                    ("Parcelas Previstas", fmt_brl(v_rec_r)),
                ],
                colunas=3,
            )

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
                "km_real_fmt": f"{km_r} km" if km_r is not None else "Não informado",
                "receita_fmt": fmt_brl(receita_r),
                "despesa_fmt": fmt_brl(custos_r),
                "resultado_fmt": fmt_brl(resultado_r),
                "custo_km_fmt": fmt_brl(custo_km_r) if custo_km_r is not None else "Não informado",
                "margem_fmt": f"{margem_r:.1f}%" if margem_r is not None else "Não calculável",
                "parcelas_previstas_fmt": fmt_brl(v_rec_r),
                "recebido_real_fmt": fmt_brl(receb_real_r),
                "saldo_receber_fmt": fmt_brl(saldo_real_r),
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

            b_pdf, b_xls = st.columns(2)
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
                recebimentos_global = round(sum(v["total_recebido"] for v in vg_bi_filtradas), 2)
                saldo_global_confiavel = all(v["saldo_a_receber"] is not None for v in vg_bi_filtradas)
                saldo_global = round(sum(v["saldo_a_receber"] or 0 for v in vg_bi_filtradas), 2)
                margem_global = (
                    (res_global / rec_global) * 100.0
                    if rec_global > 0 and not any(v["financeiro_legado_ambiguo"] for v in vg_bi_filtradas)
                    else None
                )
                km_global = sum(v["km_rodado"] or 0 for v in vg_bi_filtradas)
                quantos_com_odometro = sum(v["km_rodado"] is not None for v in vg_bi_filtradas)
                km_completo = quantos_com_odometro == len(vg_bi_filtradas) and bool(vg_bi_filtradas)
                custo_km_global = (desp_global / km_global) if km_global > 0 and km_completo else None
                km_global_fmt = (
                    f"{km_global:,} km".replace(",", ".") + (" (parcial)" if not km_completo else "")
                    if quantos_com_odometro else "Não informado"
                )

                st.markdown('<div class="sec-subtitle">Indicadores Globais Consolidados</div>', unsafe_allow_html=True)
                exibir_indicadores(
                    [
                        ("Viagens Analisadas", len(vg_bi_filtradas)),
                        ("Receita Consolidada", fmt_brl(rec_global)),
                        ("Despesas dos Fretes", fmt_brl(desp_global)),
                    ],
                    colunas=3,
                )
                exibir_indicadores(
                    [
                        ("Resultado Operacional Parcial", fmt_brl(res_global), "destaque"),
                        ("Margem Operacional", f"{margem_global:.1f}%" if margem_global is not None else "Não calculável"),
                        ("KM Registrado / Custo Médio KM", f"{km_global_fmt} / {fmt_brl(custo_km_global) if custo_km_global is not None else 'Não informado'}"),
                    ],
                    colunas=3,
                )
                exibir_indicadores(
                    [
                        ("Recebimentos Confirmados", fmt_brl(recebimentos_global)),
                        ("Saldo em Aberto", fmt_brl(saldo_global) if saldo_global_confiavel else "Conferir financeiro legado", "destaque"),
                    ],
                    colunas=2,
                )
                st.caption(
                    "Este BI é filtrado por frete/cliente e não inclui despesas compartilhadas do ciclo, "
                    "pois não há rateio aprovado. Consulte 'Fechamento por Ciclo' para o resultado "
                    "que inclui esses gastos uma única vez. Não some os dois painéis."
                )
                if not km_completo:
                    st.caption("KM total parcial: existem fretes sem as duas leituras de odômetro. Custo médio por KM global fica indisponível.")
                if any(v["financeiro_legado_ambiguo"] for v in vg_bi_filtradas):
                    st.warning("Alguns fretes antigos compartilham o financeiro do ciclo. Esses valores foram excluídos dos totais por frete até a conferência, evitando receita duplicada.")

                # Agrupamento por Cliente
                ranking_cli_lista = []
                if vg_bi_filtradas:
                    df_bi_vg = pd.DataFrame(vg_bi_filtradas)
                    grp_cli = (
                        df_bi_vg.groupby("cliente", as_index=False)
                        .agg(
                            viagens=("id_viagem", "count"),
                            receita=("receita_base", "sum"),
                            recebido=("total_recebido", "sum"),
                            despesas=("total_despesas", "sum"),
                            resultado=("resultado_liquido", "sum"),
                        )
                        .sort_values("resultado", ascending=False)
                    )
                    for _, row_c in grp_cli.iterrows():
                        cliente_legado_ambiguo = any(
                            v["financeiro_legado_ambiguo"] and v["cliente"] == row_c["cliente"]
                            for v in vg_bi_filtradas
                        )
                        mg_c = (
                            (row_c["resultado"] / row_c["receita"]) * 100.0
                            if row_c["receita"] > 0 and not cliente_legado_ambiguo else None
                        )
                        ranking_cli_lista.append(
                            {
                                "cliente": row_c["cliente"],
                                "viagens": int(row_c["viagens"]),
                                "receita": float(row_c["receita"]),
                                "recebido": float(row_c["recebido"]),
                                "despesas": float(row_c["despesas"]),
                                "resultado": float(row_c["resultado"]),
                                "margem": mg_c,
                                "receita_fmt": fmt_brl(row_c["receita"]),
                                "recebido_fmt": fmt_brl(row_c["recebido"]),
                                "despesa_fmt": fmt_brl(row_c["despesas"]),
                                "resultado_fmt": fmt_brl(row_c["resultado"]),
                                "margem_fmt": f"{mg_c:.1f}%" if mg_c is not None else "Não calculável",
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
                    st.markdown('<div class="sec-subtitle">Resultado Operacional Parcial por Cliente</div>', unsafe_allow_html=True)
                    if ranking_cli_lista:
                        df_chart_cli_bi = pd.DataFrame(ranking_cli_lista)[["cliente", "resultado"]].rename(
                            columns={"cliente": "Cliente", "resultado": "Resultado Operacional Parcial (R$)"}
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
                                "Recebido de Fato": r["recebido_fmt"],
                                "Despesas dos Fretes": r["despesa_fmt"],
                                "Resultado Operacional Parcial": r["resultado_fmt"],
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
                    "km_total_fmt": km_global_fmt,
                    "receita_fmt": fmt_brl(rec_global),
                    "despesa_fmt": fmt_brl(desp_global),
                    "resultado_fmt": fmt_brl(res_global),
                    "recebido_fmt": fmt_brl(recebimentos_global),
                    "saldo_fmt": fmt_brl(saldo_global) if saldo_global_confiavel else "Conferir legado",
                    "margem_fmt": f"{margem_global:.1f}%" if margem_global is not None else "Não calculável",
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

        # ----------------------------------------------------------------------
        # SUB-ABA 3: CONSOLIDAÇÃO POR ID INTERNO DO CICLO
        # ----------------------------------------------------------------------
        with tab_rel_ciclos:
            fechamentos_salvos = consolidar_ciclos(todas_vg_exp, carregar_todas_despesas_ciclo())
            st.caption(
                "Cada despesa por ID Frete é somada uma vez e cada despesa compartilhada "
                "por ID Ciclo entra uma vez, sem rateio. O BI por frete não inclui os gastos "
                "compartilhados; não some os resultados dos dois painéis."
            )
            if not fechamentos_salvos:
                st.info("Ainda não existem fretes do tipo Ciclo salvos para consolidar.")
            else:
                exibir_indicadores(
                    [
                        ("CICLOS COM FRETES", len(fechamentos_salvos)),
                        ("FRETES AGRUPADOS", sum(f["qtd_fretes"] for f in fechamentos_salvos)),
                        ("DESPESAS ATRIBUÍDAS AOS CICLOS", fmt_brl(sum(f["despesas_total"] for f in fechamentos_salvos)), "destaque"),
                    ],
                    colunas=3,
                )
                st.dataframe(
                    pd.DataFrame([
                        {
                            "Ciclo": f["ciclo"],
                            "Fretes": f["qtd_fretes"],
                            "Receita Negociada": fmt_brl(f["valor_negociado_total"]),
                            "Parcelas Previstas": fmt_brl(f["parcelas_previstas"]),
                            "Recebido de Fato": fmt_brl(f["total_recebido"]),
                            "Saldo em Aberto": fmt_brl(f["saldo_a_receber"]) if f["saldo_a_receber"] is not None else "Conferir legado",
                            "Despesas Fretes": fmt_brl(f["despesas_fretes_total"]),
                            "Despesas Compartilhadas": fmt_brl(f["despesas_compartilhadas_total"]),
                            "Despesas Totais": fmt_brl(f["despesas_total"]),
                            "Resultado Parcial": fmt_brl(f["resultado_operacional_parcial"]),
                            "KM Total Planejado": fmt_km(f["km_total_planejado"]),
                            "Conferência Financeira": "Pendente" if f["qtd_financeiros_legados_ambiguos"] else "Por frete",
                        }
                        for f in fechamentos_salvos
                    ]),
                    hide_index=True,
                    use_container_width=True,
                )
                opcoes_ciclos = {f["id_ciclo"]: f for f in fechamentos_salvos}
                ciclo_abrir_id = st.selectbox(
                    "VER DETALHAMENTO DO CICLO",
                    options=list(opcoes_ciclos),
                    format_func=lambda x: f"{opcoes_ciclos[x]['ciclo']} — {opcoes_ciclos[x]['qtd_fretes']} frete(s)",
                    key="rel_ciclo_detalhe",
                )
                ciclo_aberto = opcoes_ciclos[ciclo_abrir_id]
                st.caption(
                    f"Ciclo {ciclo_aberto['ciclo']}: despesas dos fretes "
                    f"{fmt_brl(ciclo_aberto['despesas_fretes_total'])} + despesas compartilhadas "
                    f"{fmt_brl(ciclo_aberto['despesas_compartilhadas_total'])} "
                    f"= {fmt_brl(ciclo_aberto['despesas_total'])}."
                )
                st.dataframe(
                    pd.DataFrame([
                        {
                            "ID Frete": f["id_frete"],
                            "Código Viagem": f["codigo_viagem"],
                            "Cliente": f["cliente"],
                            "Negociado Considerado (R$)": to_float(f["negociado_considerado"]),
                            "Recebido de Fato (R$)": to_float(f["total_recebido"]),
                            "Despesas (R$)": to_float(f["total_despesas"]),
                            "Situação Financeira": "Legado para conferir" if f["financeiro_legado_ambiguo"] else "Individualizado",
                        }
                        for f in ciclo_aberto["fretes"]
                    ]),
                    hide_index=True,
                    use_container_width=True,
                )
                if ciclo_aberto["qtd_financeiros_legados_ambiguos"]:
                    st.warning(
                        "Atenção: este ciclo contém registros financeiros antigos sem separação "
                        "por frete. Esses valores não foram repetidos na receita consolidada; "
                        "a conferência e a individualização ainda são necessárias."
                    )
                st.caption("O Excel da Etapa 9 inclui Fechamento_Ciclos (com os dois componentes de despesa) e Despesas_Ciclo (lançamentos ativos e cancelados).")

        # ----------------------------------------------------------------------
        # SUB-ABA 4: CONFERÊNCIA FINANCEIRA DA BASE INTEIRA (SEM FILTROS DO BI)
        # ----------------------------------------------------------------------
        with tab_rel_conferencia:
            geral = reconciliar_resultado_gerencial(
                todas_vg_exp, carregar_todas_despesas_ciclo(), carregar_todas_despesas_veiculo(),
            )
            st.info(
                "Conferência de TODA a base salva, independente dos filtros do Painel Geral. "
                "O resultado inclui custos diretos dos fretes e compartilhados dos ciclos "
                "uma única vez. Não soma novamente abastecimentos ou despesas de veículo atribuídas."
            )
            exibir_indicadores(
                [
                    ("RECEITA NEGOCIADA CONSIDERADA", fmt_brl(geral["receita_negociada_considerada"])),
                    ("DESPESAS DOS FRETES", fmt_brl(geral["despesas_fretes"])),
                    ("DESPESAS COMPARTILHADAS", fmt_brl(geral["despesas_compartilhadas"])),
                    ("DESPESAS TOTAIS CONTABILIZADAS", fmt_brl(geral["despesas_financeiras_totais"])),
                ],
                colunas=4,
            )
            exibir_indicadores(
                [
                    ("RESULTADO OPERACIONAL PARCIAL", fmt_brl(geral["resultado_operacional_parcial"]), "destaque"),
                    ("MARGEM OPERACIONAL", f"{geral['margem_operacional_pct']:.1f}%" if geral["margem_operacional_pct"] is not None else "Não calculável"),
                    ("RECEBIDO DE FATO", fmt_brl(geral["total_recebido"])),
                    ("SALDO A RECEBER", fmt_brl(geral["saldo_a_receber"]) if geral["saldo_a_receber"] is not None else "Conferir financeiro legado"),
                ],
                colunas=4,
            )
            st.markdown("**Despesas vinculadas ao veículo — controle separado**")
            exibir_indicadores(
                [
                    ("PENDENTES — FORA DO RESULTADO", fmt_brl(geral["despesas_veiculo_pendentes"]), "destaque"),
                    ("JÁ ATRIBUÍDAS — NÃO SOMAR DE NOVO", fmt_brl(geral["despesas_veiculo_ja_atribuidas"])),
                ],
                colunas=2,
            )
            st.caption(
                "Os gastos pendentes ainda não pertencem a frete/ciclo. Os já atribuídos "
                "estão incluídos nas despesas financeiras de seus destinos, não são uma terceira despesa."
            )
            if geral["qtd_financeiros_legados_ambiguos"]:
                st.warning(
                    f"{geral['qtd_financeiros_legados_ambiguos']} frete(s) com financeiro legado "
                    "ambíguo: a receita desses registros não foi considerada; portanto o "
                    "resultado gerencial é incompleto até a individualização."
                )
            if geral["qtd_despesas_ciclo_sem_fretes"]:
                st.warning(
                    f"{geral['qtd_despesas_ciclo_sem_fretes']} despesa(s) compartilhada(s) ativa(s) "
                    "pertencem a ciclos sem fretes do tipo Ciclo. Estão incluídas na conferência "
                    "geral, mas exigem verificação do vínculo antes do fechamento."
                )
            st.caption(
                "Recebido de fato é fluxo de caixa, não outra receita a somar ao negociado. "
                "A planilha completa reproduz esta ponte na aba Conferencia_Financeira. "
                "A conferência separa fontes financeiras; lançamentos manuais iguais em "
                "destinos diferentes ainda exigem verificação humana."
            )
            st.markdown("**Possíveis duplicidades entre despesas do frete e do ciclo**")
            alertas_cruzados = carregar_alertas_despesas_cruzadas()
            if alertas_cruzados:
                st.warning(
                    f"{len(alertas_cruzados)} coincidência(s) de data, categoria, valor "
                    "e demais campos entre despesas de frete e do respectivo ciclo. "
                    "Confira comprovantes antes de corrigir: duas despesas podem ser legítimas."
                )
                st.dataframe(
                    pd.DataFrame([
                        {
                            **a,
                            "Data": a["Data"].strftime("%d/%m/%Y") if a["Data"] else None,
                        }
                        for a in alertas_cruzados
                    ]),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.caption(
                    "Nenhuma coincidência encontrada pelo critério atual. Isso não comprova "
                    "ausência de outros lançamentos repetidos; confira os comprovantes."
                )
            st.caption(
                "Esta lista é somente leitura. O Excel disponibiliza os indícios "
                "na aba Possiveis_Duplicidades; nenhum registro é excluído automaticamente."
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
        tot_recebido_f = sum(v["total_recebido"] for v in filtradas)
        saldos_consulta_validos = all(v["saldo_a_receber"] is not None for v in filtradas)
        tot_saldo_f = sum(v["saldo_a_receber"] or 0 for v in filtradas)

        exibir_indicadores(
            [
                ("Viagens Filtradas", len(filtradas)),
                ("Receita Consolidada", fmt_brl(tot_rec_f)),
                ("Despesas dos Fretes", fmt_brl(tot_desp_f)),
                ("Resultado Operacional Parcial", fmt_brl(tot_res_f), "destaque"),
            ],
            colunas=4,
        )
        exibir_indicadores(
            [
                ("Recebido de Fato (Fretes Filtrados)", fmt_brl(tot_recebido_f)),
                ("Saldo a Receber", fmt_brl(tot_saldo_f) if saldos_consulta_validos else "Conferir financeiro legado", "destaque"),
            ],
            colunas=2,
        )
        st.caption(
            "Os indicadores filtrados por frete não incluem despesas compartilhadas do ciclo. "
            "Para a visão operacional com esses custos, consulte o Fechamento por Ciclo na Etapa 9."
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
                        "Recebido de Fato": fmt_brl(v["total_recebido"]),
                        "Saldo a Receber": fmt_brl(v["saldo_a_receber"]) if v["saldo_a_receber"] is not None else "Conferir legado",
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
                    todas_viagens, desp_detalhadas, motoristas_db, veiculos_db, clientes_db, locais_db, fornecedores_db,
                    abastecimentos=carregar_todos_abastecimentos(),
                    fechamentos_ciclos=consolidar_ciclos(todas_viagens, carregar_todas_despesas_ciclo()),
                    recebimentos=carregar_todos_recebimentos(),
                    despesas_ciclo=carregar_todas_despesas_ciclo(),
                    despesas_veiculo=carregar_todas_despesas_veiculo(),
                    atribuicoes_veiculo=carregar_historico_atribuicoes_veiculo(),
                    alertas_despesas=carregar_alertas_despesas_cruzadas(),
                )
                st.download_button(
                    "📥 Exportar Base Completa (.xlsx)",
                    data=xlsx_cons,
                    file_name="Base_Completa_FAEG.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            st.caption(
                "Os filtros acima alteram apenas a consulta na tela. "
                "A exportação é da base completa, com fretes, despesas e fechamentos "
                "do mesmo conjunto de registros, inclusive a aba Conferencia_Financeira."
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