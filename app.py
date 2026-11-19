import base64
import io
import os
import re
import zlib
from datetime import date

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
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
            v_tot = to_float(d.valor_total)
            desp_por_viagem[d.id_viagem] = desp_por_viagem.get(d.id_viagem, 0.0) + v_tot
            desp_detalhadas.append(
                {
                    "ID Despesa": d.id_despesa,
                    "Código Viagem": cod_map.get(d.id_viagem, f"V{d.id_viagem}"),
                    "Tipo Despesa": d.tipo_despesa,
                    "Descrição": d.descricao_detalhe or "-",
                    "Fornecedor / Posto": d.fornecedor.nome_fantasia if d.fornecedor else "Não informado",
                    "Quantidade": to_float(d.quantidade),
                    "Valor Unitário (R$)": to_float(d.valor_unitario),
                    "Valor Total (R$)": v_tot,
                }
            )

        resultado = []
        for vg in viagens_raw:
            c = vg.ciclo
            fin = c.financeiro if c else None
            cod = resolver_codigo_viagem(vg, c)

            raw_tv = getattr(vg, "tipo_viagem", None)
            if raw_tv in ["Individual", "Ciclo"]:
                tipo_v = raw_tv
            elif vg.tipo_frete in ["Individual", "Ciclo"]:
                tipo_v = vg.tipo_frete
            elif c and c.nome_operacao and not str(c.nome_operacao).startswith("Individual"):
                tipo_v = "Ciclo"
            else:
                tipo_v = "Individual"

            ciclo_nome = (
                c.nome_operacao
                if (tipo_v == "Ciclo" and c and c.nome_operacao and not str(c.nome_operacao).startswith("Individual"))
                else "-"
            )

            val_div = to_float(fin.valor_divulgado) if fin else 0.0
            val_neg = to_float(fin.valor_negociado_total) if fin else 0.0
            val_adiant = to_float(fin.valor_adiantamento) if fin else 0.0
            val_saldo = to_float(fin.valor_saldo) if fin else 0.0
            total_rec = val_adiant + val_saldo
            receita_efetiva = val_neg if val_neg > 0 else total_rec
            total_desp = desp_por_viagem.get(vg.id_viagem, 0.0)
            lucro_liq = receita_efetiva - total_desp
            km_rod = to_int(vg.km_real_rodado, 0)
            custo_km = (total_desp / km_rod) if km_rod > 0 else 0.0
            margem_pct = ((lucro_liq / receita_efetiva) * 100.0) if receita_efetiva > 0 else 0.0

            cli_nome = "-"
            if c and c.cliente:
                cli_nome = c.cliente.razao_social
                if c.cliente.nome_fantasia:
                    cli_nome += f" ({c.cliente.nome_fantasia})"

            mot_nome = vg.motorista.nome_completo if vg.motorista else "-"
            vei_txt = f"{vg.veiculo.descricao_marca} ({vg.veiculo.placa})" if vg.veiculo else "-"
            col_txt = vg.local_coleta.nome_local if vg.local_coleta else "-"
            ent_txt = vg.local_entrega.nome_local if vg.local_entrega else "-"

            r_orig = getattr(vg, "rota_origem", "") or ""
            r_dest = getattr(vg, "rota_destino", "") or ""
            r_fmt = formatar_rota_exibicao(r_orig, r_dest, vg.rota_resumo) or "-"

            resultado.append(
                {
                    "id_viagem": vg.id_viagem,
                    "codigo_viagem": cod,
                    "seq_num": extrair_numero_sequencial(cod, vg.id_viagem),
                    "id_frete": vg.id_frete_externo or "-",
                    "status": vg.status_viagem or "Aguardando Adiantamento",
                    "tipo_viagem": tipo_v,
                    "ciclo": ciclo_nome,
                    "tipo_frete": vg.tipo_frete or "-",
                    "origem_frete": (fin.forma_contratacao if fin and fin.forma_contratacao else "-"),
                    "data_coleta": vg.data_coleta,
                    "data_entrega": vg.data_entrega,
                    "cliente": cli_nome,
                    "motorista": mot_nome,
                    "veiculo": vei_txt,
                    "rota_origem": r_orig or "-",
                    "rota_destino": r_dest or "-",
                    "rota": r_fmt,
                    "coleta": col_txt,
                    "entrega": ent_txt,
                    "nfe": vg.nfe_carga or "-",
                    "cte": vg.cte_numero or "-",
                    "mdfe": vg.mdfe_numero or "-",
                    "ciot": vg.ciot_numero or "-",
                    "valor_divulgado": val_div,
                    "valor_negociado": val_neg,
                    "valor_adiantamento": val_adiant,
                    "valor_saldo": val_saldo,
                    "total_recebido": total_rec,
                    "receita_efetiva": receita_efetiva,
                    "total_despesas": total_desp,
                    "resultado_liquido": lucro_liq,
                    "margem_pct": margem_pct,
                    "km_rodado": km_rod,
                    "custo_km": custo_km,
                }
            )

        resultado.sort(key=lambda x: (x["seq_num"], x["id_viagem"]), reverse=True)
        return resultado, desp_detalhadas


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
# ESTILOS CSS OFICIAIS FAEG
# ==============================================================================
st.markdown(
    """
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        :root {
            color-scheme: light !important;
        }

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

        /* Botão Secundário na Sidebar (+ Nova Viagem) */
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

        [data-testid="stAppViewContainer"] input,
        [data-testid="stAppViewContainer"] textarea,
        [data-testid="stAppViewContainer"] div[data-baseweb="select"] span,
        [data-testid="stAppViewContainer"] div[data-baseweb="select"] div {
            color: #0D263C !important;
            -webkit-text-fill-color: #0D263C !important;
            font-size: 0.88rem !important;
            font-weight: 500 !important;
        }

        [data-testid="stAppViewContainer"] input::placeholder,
        [data-testid="stAppViewContainer"] textarea::placeholder {
            color: #64748B !important;
            -webkit-text-fill-color: #64748B !important;
            opacity: 1 !important;
            font-size: 0.82rem !important;
            font-weight: 400 !important;
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

        .stTextInput label, .stNumberInput label, .stSelectbox label, .stDateInput label, .stTimeInput label {
            margin-bottom: 0.25rem !important;
        }
        .stTextInput label p, .stNumberInput label p, .stSelectbox label p, .stDateInput label p, .stTimeInput label p {
            font-size: 0.72rem !important;
            font-weight: 700 !important;
            color: #0D263C !important;
            text-transform: uppercase !important;
            letter-spacing: 0.03em;
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
            line-height: 1.25 !important;
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
# GERADOR DE PDF NATIVO ZERO-DEPENDÊNCIA (PADRÃO VISUAL FAEG)
# ==============================================================================
def _pdf_esc(txt):
    if txt is None:
        return "-"
    s = str(txt).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return s.encode("latin-1", "replace").decode("latin-1")


def gerar_pdf_relatorio(dados_resumo, despesas_lista):
    cmds = []

    def rect(x, y_top, w, h, rgb):
        y_pdf = 842 - y_top - h
        r, g, b = [round(c / 255.0, 4) for c in rgb]
        cmds.append(f"{r} {g} {b} rg {x:.1f} {y_pdf:.1f} {w:.1f} {h:.1f} re f")

    def line(x1, y_top1, x2, y_top2, rgb=(203, 213, 225), width=0.8):
        r, g, b = [round(c / 255.0, 4) for c in rgb]
        cmds.append(f"{width} w {r} {g} {b} RG {x1:.1f} {842 - y_top1:.1f} m {x2:.1f} {842 - y_top2:.1f} l S")

    def text(x, y_top, txt, size=9, bold=False, rgb=(13, 38, 60)):
        font = "/F2" if bold else "/F1"
        r, g, b = [round(c / 255.0, 4) for c in rgb]
        cmds.append(f"BT {font} {size} Tf {r} {g} {b} rg 1 0 0 1 {x:.1f} {842 - y_top:.1f} Tm ({_pdf_esc(txt)}) Tj ET")

    rect(0, 0, 595, 78, (13, 38, 60))
    rect(0, 78, 595, 5, (243, 77, 37))

    text(36, 34, "FAEG - SOLUCOES EMPRESARIAIS E LOGISTICAS", size=15, bold=True, rgb=(255, 255, 255))
    text(
        36,
        54,
        f"Relatorio Operacional e Financeiro de Viagem  |  Codigo: {dados_resumo['codigo']}",
        size=9.5,
        bold=False,
        rgb=(171, 206, 225),
    )

    y = 108
    text(36, y, "1. DADOS DA OPERACAO E FROTA", size=10.5, bold=True, rgb=(13, 38, 60))
    line(36, y + 6, 559, y + 6)
    y += 24

    pares_info = [
        ("Cliente:", dados_resumo["cliente"][:36], "Situacao:", dados_resumo["status"][:28]),
        ("Tipo Viagem:", dados_resumo["tipo_viagem"][:36], "Tipo Frete:", dados_resumo["tipo_frete"][:30]),
        ("Origem Frete:", dados_resumo["origem_frete"][:36], "KM Rodado:", f"{dados_resumo['km_rodado']} km"),
        ("Veiculo:", dados_resumo["veiculo"][:36], "Data Coleta:", dados_resumo["data_coleta"]),
        ("Motorista:", dados_resumo["motorista"][:36], "Data Entrega:", dados_resumo["data_entrega"]),
        ("Origem:", dados_resumo["rota_origem"][:36], "Destino:", dados_resumo["rota_destino"][:30]),
        ("Coleta:", dados_resumo["coleta"][:36], "MDF-e / CIOT:", f"{dados_resumo['mdfe']} / {dados_resumo['ciot']}"),
        ("Entrega:", dados_resumo["entrega"][:36], "NF-e / CT-e:", f"{dados_resumo['nfe']} / {dados_resumo['cte']}"),
    ]

    for lbl1, val1, lbl2, val2 in pares_info:
        text(36, y, lbl1, size=8.5, bold=True, rgb=(100, 116, 139))
        text(105, y, val1, size=8.5, bold=False, rgb=(13, 38, 60))
        if lbl2:
            text(315, y, lbl2, size=8.5, bold=True, rgb=(100, 116, 139))
            text(390, y, val2, size=8.5, bold=False, rgb=(13, 38, 60))
        y += 17

    y += 12
    text(36, y, "2. RESUMO FINANCEIRO (DRE) E INDICADORES (KPIs)", size=10.5, bold=True, rgb=(13, 38, 60))
    line(36, y + 6, 559, y + 6)
    y += 16

    cards = [
        ("RECEITA TOTAL", fmt_brl(dados_resumo["receita"]), (13, 38, 60), (255, 255, 255), (171, 206, 225)),
        ("CUSTOS TOTAIS", fmt_brl(dados_resumo["custos"]), (241, 245, 249), (243, 77, 37), (100, 116, 139)),
        ("RESULTADO LIQUIDO", fmt_brl(dados_resumo["resultado"]), (13, 38, 60), (171, 206, 225), (171, 206, 225)),
        (
            "MARGEM / CUSTO KM",
            f"{dados_resumo['margem']:.1f}% | {fmt_brl(dados_resumo['custo_km'])}",
            (241, 245, 249),
            (13, 38, 60),
            (100, 116, 139),
        ),
    ]
    w_card = 124
    gap = 9
    for idx, (t_c, v_c, bg_c, fg_v, fg_t) in enumerate(cards):
        xc = 36 + idx * (w_card + gap)
        rect(xc, y, w_card, 46, bg_c)
        text(xc + 8, y + 16, t_c, size=7, bold=True, rgb=fg_t)
        text(xc + 8, y + 34, v_c, size=10, bold=True, rgb=fg_v)

    y += 68

    text(36, y, "3. DETALHAMENTO DE DESPESAS DA VIAGEM", size=10.5, bold=True, rgb=(13, 38, 60))
    y += 10

    rect(36, y, 523, 20, (13, 38, 60))
    text(44, y + 13, "TIPO", size=8, bold=True, rgb=(255, 255, 255))
    text(155, y + 13, "DESCRICAO / LOCAL", size=8, bold=True, rgb=(255, 255, 255))
    text(365, y + 13, "QTD", size=8, bold=True, rgb=(255, 255, 255))
    text(415, y + 13, "UNITARIO", size=8, bold=True, rgb=(255, 255, 255))
    text(490, y + 13, "TOTAL", size=8, bold=True, rgb=(255, 255, 255))
    y += 20

    if not despesas_lista:
        rect(36, y, 523, 22, (248, 250, 252))
        text(200, y + 14, "Nenhuma despesa lancada para esta viagem.", size=8.5, bold=False, rgb=(100, 116, 139))
        y += 22
    else:
        for i, d in enumerate(despesas_lista[:20]):
            if i % 2 == 1:
                rect(36, y, 523, 18, (248, 250, 252))
            text(44, y + 12, str(d["tipo_despesa"])[:20], size=8, bold=False, rgb=(13, 38, 60))
            text(155, y + 12, str(d["descricao_detalhe"] or "-")[:38], size=8, bold=False, rgb=(13, 38, 60))
            text(365, y + 12, f"{to_float(d['quantidade']):g}", size=8, bold=False, rgb=(13, 38, 60))
            text(415, y + 12, fmt_brl(d["valor_unitario"]), size=8, bold=False, rgb=(13, 38, 60))
            text(490, y + 12, fmt_brl(d["valor_total"]), size=8, bold=True, rgb=(13, 38, 60))
            y += 18

    rect(36, y, 523, 24, (241, 245, 249))
    line(36, y, 559, y, rgb=(13, 38, 60), width=1.2)
    text(340, y + 15, "CUSTO TOTAL DAS DESPESAS:", size=8.5, bold=True, rgb=(13, 38, 60))
    text(485, y + 15, fmt_brl(dados_resumo["custos"]), size=9.5, bold=True, rgb=(243, 77, 37))

    text(
        36,
        812,
        "Documento gerado pelo Sistema Operacional FAEG - Solucoes Empresariais e Logisticas",
        size=7.5,
        bold=False,
        rgb=(148, 163, 184),
    )

    stream_bytes = "\n".join(cmds).encode("latin-1", "replace")
    compressed = zlib.compress(stream_bytes)

    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>\nendobj\n"
        ),
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>\nendobj\n",
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>\nendobj\n",
        (
            f"6 0 obj\n<< /Length {len(compressed)} /Filter /FlateDecode >>\nstream\n".encode("ascii")
            + compressed
            + b"\nendstream\nendobj\n"
        ),
    ]

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for obj in objects:
        offsets.append(out.tell())
        out.write(obj)

    xref_pos = out.tell()
    out.write(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    out.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.write(f"{off:010d} 00000 n \n".encode("ascii"))

    out.write(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("ascii")
    )
    return out.getvalue()


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
    if c.get("nome_fantasia") and c["nome_fantasia"].strip().lower() != c["razao_social"].strip().lower():
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


def on_negociacao_change(origem_alterada):
    """Calcula automaticamente % <-> R$ tanto para Adiantamento quanto para Saldo, e atualiza Total Recebido."""
    if origem_alterada == "val_negociado":
        sync_campo("w_val_negociado", "val_negociado")
    elif origem_alterada == "perc_adiant":
        sync_campo("w_perc_adiant", "perc_adiant")
    elif origem_alterada == "val_adiant":
        sync_campo("w_val_adiant", "val_adiant")
    elif origem_alterada == "perc_saldo":
        sync_campo("w_perc_saldo", "perc_saldo")
    elif origem_alterada == "val_saldo":
        sync_campo("w_val_saldo", "val_saldo")

    fd = st.session_state["form_data"]
    val_neg = max(0.0, to_float(fd.get("val_negociado", 0.0)))

    if origem_alterada == "val_negociado":
        p_ad = min(100.0, max(0.0, to_float(fd.get("perc_adiant", 0.0))))
        p_sd = min(100.0, max(0.0, to_float(fd.get("perc_saldo", 0.0))))
        if p_ad > 0:
            fd["val_adiant"] = round(val_neg * (p_ad / 100.0), 2)
        elif val_neg > 0 and to_float(fd.get("val_adiant", 0.0)) > 0:
            fd["perc_adiant"] = round((to_float(fd["val_adiant"]) / val_neg) * 100.0, 2)

        if p_sd > 0:
            fd["val_saldo"] = round(val_neg * (p_sd / 100.0), 2)
        elif val_neg > 0 and to_float(fd.get("val_saldo", 0.0)) > 0:
            fd["perc_saldo"] = round((to_float(fd["val_saldo"]) / val_neg) * 100.0, 2)

    elif origem_alterada == "perc_adiant":
        p_ad = min(100.0, max(0.0, to_float(fd.get("perc_adiant", 0.0))))
        fd["perc_adiant"] = p_ad
        fd["val_adiant"] = round(val_neg * (p_ad / 100.0), 2)

    elif origem_alterada == "val_adiant":
        v_ad = max(0.0, to_float(fd.get("val_adiant", 0.0)))
        fd["val_adiant"] = v_ad
        fd["perc_adiant"] = round((v_ad / val_neg) * 100.0, 2) if val_neg > 0 else 0.0

    elif origem_alterada == "perc_saldo":
        p_sd = min(100.0, max(0.0, to_float(fd.get("perc_saldo", 0.0))))
        fd["perc_saldo"] = p_sd
        fd["val_saldo"] = round(val_neg * (p_sd / 100.0), 2)

    elif origem_alterada == "val_saldo":
        v_sd = max(0.0, to_float(fd.get("val_saldo", 0.0)))
        fd["val_saldo"] = v_sd
        fd["perc_saldo"] = round((v_sd / val_neg) * 100.0, 2) if val_neg > 0 else 0.0

    _limpar_widgets_financeiros()


def on_tipo_viagem_change():
    sync_campo("w_tipo_viagem", "tipo_viagem")
    if get_campo("tipo_viagem") == "Individual":
        st.session_state["form_data"]["ciclo_nome"] = ""
    if "w_ciclo_nome" in st.session_state:
        del st.session_state["w_ciclo_nome"]


def on_cliente_change(clientes_lista, locais_lista):
    sync_campo("w_cli_id", "cli_id")
    cli_id_novo = get_campo("cli_id", 0)
    if not cli_id_novo:
        return

    cli_obj = next((c for c in clientes_lista if c["id_cliente"] == cli_id_novo), None)
    if not cli_obj:
        return

    local_match = next((l for l in locais_lista if l.get("id_cliente") == cli_id_novo), None)

    if not local_match:
        nomes_busca = {
            (cli_obj.get("razao_social") or "").strip().lower(),
            (cli_obj.get("nome_fantasia") or "").strip().lower(),
        }
        nomes_busca.discard("")
        candidatos = [l for l in locais_lista if (l.get("nome_local") or "").strip().lower() in nomes_busca]
        if len(candidatos) == 1:
            local_match = candidatos[0]
        elif len(candidatos) > 1 and cli_obj.get("cidade"):
            cid_cli = cli_obj["cidade"].strip().lower()
            local_match = next(
                (l for l in candidatos if (l.get("cidade") or "").strip().lower() == cid_cli),
                candidatos[0],
            )

    if local_match:
        st.session_state["form_data"]["col_id"] = local_match["id_local"]
        if "w_col_id" in st.session_state:
            del st.session_state["w_col_id"]
        _atualizar_rota_automatica(locais_lista)


def render_cabecalho_aba(icone, titulo, passo_num, total_passos=11):
    st.markdown(
        f"""
        <div class="tab-header-wrap">
            <div class="tab-title"><i class="{icone}"></i> {titulo}</div>
            <span class="tab-step-pill">Etapa {passo_num} de {total_passos}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


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

    st.session_state["loaded_viagem_id"] = id_viagem_escolhida
    limpar_widgets_viagem()

    if id_viagem_escolhida == 0:
        proximo_codigo = calcular_proximo_codigo_viagem(viagens_lista)
        st.session_state["form_data"] = {
            "id_viagem_label": proximo_codigo,
            "status_viagem": "Aguardando Adiantamento",
            "mot_id": 0,
            "vei_id": 0,
            "id_frete": "",
            "data_frete": date.today(),
            "tipo_viagem": "Individual",
            "ciclo_nome": "",
            "tipo_frete": "Dedicado",
            "rota_origem": "",
            "rota_destino": "",
            "km_rota": 0.0,
            "tipo_mat": "",
            "qt_vol": 0,
            "vol_m3": 0.0,
            "peso_kg": 0.0,
            "nfe": "",
            "cte": "",
            "mdfe": "",
            "ciot": "",
            "cli_id": 0,
            "forma_contr": "Aplicativo de Fretes",
            "val_divulgado": 0.0,
            "val_negociado": 0.0,
            "perc_adiant": 0.0,
            "data_adiant": date.today(),
            "val_adiant": 0.0,
            "perc_saldo": 0.0,
            "data_saldo": date.today(),
            "val_saldo": 0.0,
            "col_id": 0,
            "data_col": date.today(),
            "hr_plan_col": None,
            "hr_real_col": None,
            "ent_id": 0,
            "data_ent": date.today(),
            "hr_plan_ent": None,
            "hr_real_ent": None,
            "km_ini": 0,
            "km_fin": 0,
        }
        return

    with SessionLocal() as db:
        v = db.query(Viagem).filter_by(id_viagem=id_viagem_escolhida).first()
        if not v:
            return
        c = v.ciclo
        fin = c.financeiro if c else None

        raw_tv = getattr(v, "tipo_viagem", None)
        if raw_tv in ["Individual", "Ciclo"]:
            tipo_viagem_norm = raw_tv
        elif v.tipo_frete in ["Individual", "Ciclo"]:
            tipo_viagem_norm = v.tipo_frete
        elif c and c.nome_operacao and not str(c.nome_operacao).startswith("Individual"):
            tipo_viagem_norm = "Ciclo"
        else:
            tipo_viagem_norm = "Individual"

        ciclo_nome_norm = ""
        if tipo_viagem_norm == "Ciclo" and c and c.nome_operacao:
            if not str(c.nome_operacao).startswith("Individual"):
                ciclo_nome_norm = c.nome_operacao

        opcoes_tipo_frete = ["Dedicado", "Complemento", "Cheio", "Fracionado", "Agregado"]
        tipo_frete_norm = v.tipo_frete if v.tipo_frete in opcoes_tipo_frete else "Dedicado"

        r_orig = getattr(v, "rota_origem", None) or ""
        r_dest = getattr(v, "rota_destino", None) or ""
        if not r_orig and not r_dest and v.rota_resumo:
            txt_r = str(v.rota_resumo).strip()
            if "->" in txt_r:
                p = txt_r.split("->", 1)
                r_orig, r_dest = p[0].strip(), p[1].strip()
            else:
                r_orig = txt_r

        st.session_state["form_data"] = {
            "id_viagem_label": resolver_codigo_viagem(v, c),
            "status_viagem": v.status_viagem or "Aguardando Adiantamento",
            "mot_id": v.id_motorista or 0,
            "vei_id": v.id_veiculo or 0,
            "id_frete": v.id_frete_externo or "",
            "data_frete": v.data_coleta or (c.data_abertura if c and c.data_abertura else date.today()),
            "tipo_viagem": tipo_viagem_norm,
            "ciclo_nome": ciclo_nome_norm,
            "tipo_frete": tipo_frete_norm,
            "rota_origem": r_orig,
            "rota_destino": r_dest,
            "km_rota": to_float(v.km_rota_planejado),
            "tipo_mat": v.tipo_material or "",
            "qt_vol": to_int(v.qtde_volumes),
            "vol_m3": to_float(v.volume_m3),
            "peso_kg": to_float(v.peso_bruto_kg),
            "nfe": v.nfe_carga or "",
            "cte": v.cte_numero or "",
            "mdfe": v.mdfe_numero or "",
            "ciot": v.ciot_numero or "",
            "cli_id": c.id_cliente if c else 0,
            "forma_contr": (
                fin.forma_contratacao
                if fin and fin.forma_contratacao in OPCOES_ORIGEM_FRETE
                else "Aplicativo de Fretes"
            ),
            "val_divulgado": to_float(fin.valor_divulgado) if fin else 0.0,
            "val_negociado": to_float(fin.valor_negociado_total) if fin else 0.0,
            "perc_adiant": to_float(fin.perc_adiantamento) if fin else 0.0,
            "data_adiant": (
                fin.data_prevista_adiantamento if fin and fin.data_prevista_adiantamento else date.today()
            ),
            "val_adiant": to_float(fin.valor_adiantamento) if fin else 0.0,
            "perc_saldo": to_float(fin.perc_saldo) if fin else 0.0,
            "data_saldo": fin.data_prevista_saldo if fin and fin.data_prevista_saldo else date.today(),
            "val_saldo": to_float(fin.valor_saldo) if fin else 0.0,
            "col_id": v.id_local_coleta or 0,
            "data_col": v.data_coleta or date.today(),
            "hr_plan_col": v.hora_planejada_coleta,
            "hr_real_col": v.hora_real_coleta,
            "ent_id": v.id_local_entrega or 0,
            "data_ent": v.data_entrega or date.today(),
            "hr_plan_ent": v.hora_planejada_entrega,
            "hr_real_ent": v.hora_real_entrega,
            "km_ini": to_int(v.odometro_inicial),
            "km_fin": to_int(v.odometro_final),
        }


def salvar_viagem_completa(id_viagem_atual, viagens_lista):
    mot_id = get_campo("mot_id", 0)
    vei_id = get_campo("vei_id", 0)
    cli_id = get_campo("cli_id", 0)
    col_id = get_campo("col_id", 0)
    ent_id = get_campo("ent_id", 0)
    tipo_viagem_val = get_campo("tipo_viagem", "Individual")
    tipo_frete_val = get_campo("tipo_frete", "Dedicado")
    ciclo_num_val = (get_campo("ciclo_nome") or "").strip()

    faltando = []
    if not mot_id:
        faltando.append("Motorista (Etapa 1)")
    if not vei_id:
        faltando.append("Veículo (Etapa 1)")
    if tipo_viagem_val == "Ciclo" and not ciclo_num_val:
        faltando.append("Nº do Ciclo Operacional (Etapa 2)")
    if not cli_id:
        faltando.append("Cliente (Etapa 3)")
    if not col_id:
        faltando.append("Local de Coleta (Etapa 5)")
    if not ent_id:
        faltando.append("Local de Entrega (Etapa 6)")

    if faltando:
        st.sidebar.error("Preencha / selecione antes de salvar:\n- " + "\n- ".join(faltando))
        return

    codigo_viagem_editado = (get_campo("id_viagem_label") or "").strip().upper()
    if not codigo_viagem_editado:
        codigo_viagem_editado = calcular_proximo_codigo_viagem(viagens_lista)

    rota_orig_val = (get_campo("rota_origem") or "").strip()
    rota_dest_val = (get_campo("rota_destino") or "").strip()
    rota_resumo_val = formatar_rota_exibicao(rota_orig_val, rota_dest_val)

    km_ini = to_int(get_campo("km_ini", 0))
    km_fin = to_int(get_campo("km_fin", 0))
    km_real = max(0, km_fin - km_ini) if km_fin >= km_ini else 0

    nome_operacao_final = (
        ciclo_num_val if tipo_viagem_val == "Ciclo" else f"Individual - {codigo_viagem_editado}"
    )

    val_neg = to_float(get_campo("val_negociado", 0.0))
    val_ad = to_float(get_campo("val_adiant", 0.0))
    val_sd = to_float(get_campo("val_saldo", 0.0))
    total_rec = val_ad + val_sd

    situacao_atual = get_campo("status_viagem", "Aguardando Adiantamento")
    if situacao_atual == "Aguardando Adiantamento":
        if val_neg > 0 and total_rec >= val_neg - 0.01:
            situacao_final = "Quitada / Concluída"
        elif val_ad > 0:
            situacao_final = "Adiantamento Recebido"
        else:
            situacao_final = situacao_atual
    else:
        situacao_final = situacao_atual

    with SessionLocal() as db:
        # Valida unicidade do Código da Viagem (V1, V2, V3...)
        duplicado = (
            db.query(Viagem)
            .filter(Viagem.codigo_viagem.ilike(codigo_viagem_editado))
            .filter(Viagem.id_viagem != id_viagem_atual)
            .first()
        )
        if duplicado:
            st.sidebar.error(
                f"O Código de Viagem '{codigo_viagem_editado}' já está em uso! Informe outro identificador único."
            )
            return

        if id_viagem_atual == 0:
            novo_ciclo = CicloOperacional(
                id_cliente=cli_id,
                nome_operacao=nome_operacao_final,
                data_abertura=get_campo("data_frete") or date.today(),
                status_ciclo=f"COD::{codigo_viagem_editado}",
            )
            db.add(novo_ciclo)
            db.flush()

            novo_fin = CicloFinanceiro(
                id_ciclo=novo_ciclo.id_ciclo,
                forma_contratacao=get_campo("forma_contr", "Aplicativo de Fretes"),
                valor_divulgado=get_campo("val_divulgado", 0.0),
                valor_negociado_total=val_neg,
                perc_adiantamento=get_campo("perc_adiant", 0.0),
                data_prevista_adiantamento=get_campo("data_adiant"),
                valor_adiantamento=val_ad,
                perc_saldo=get_campo("perc_saldo", 0.0),
                data_prevista_saldo=get_campo("data_saldo"),
                valor_saldo=val_sd,
            )
            db.add(novo_fin)

            nova_v = Viagem(
                codigo_viagem=codigo_viagem_editado,
                id_ciclo=novo_ciclo.id_ciclo,
                id_motorista=mot_id,
                id_veiculo=vei_id,
                id_frete_externo=get_campo("id_frete", ""),
                tipo_viagem=tipo_viagem_val,
                tipo_frete=tipo_frete_val,
                rota_origem=rota_orig_val,
                rota_destino=rota_dest_val,
                rota_resumo=rota_resumo_val,
                km_rota_planejado=get_campo("km_rota", 0.0),
                id_local_coleta=col_id,
                data_coleta=get_campo("data_col"),
                hora_planejada_coleta=get_campo("hr_plan_col"),
                hora_real_coleta=get_campo("hr_real_col"),
                id_local_entrega=ent_id,
                data_entrega=get_campo("data_ent"),
                hora_planejada_entrega=get_campo("hr_plan_ent"),
                hora_real_entrega=get_campo("hr_real_ent"),
                tipo_material=get_campo("tipo_mat", ""),
                qtde_volumes=get_campo("qt_vol", 0),
                peso_bruto_kg=get_campo("peso_kg", 0.0),
                volume_m3=get_campo("vol_m3", 0.0),
                nfe_carga=get_campo("nfe", ""),
                cte_numero=get_campo("cte", ""),
                mdfe_numero=get_campo("mdfe", ""),
                ciot_numero=get_campo("ciot", ""),
                odometro_inicial=km_ini,
                odometro_final=km_fin,
                km_real_rodado=km_real,
                status_viagem=situacao_final,
            )
            db.add(nova_v)
            db.flush()

            for d_temp in st.session_state.get("despesas_temp", []):
                db.add(
                    ViagemDespesa(
                        id_viagem=nova_v.id_viagem,
                        id_fornecedor=d_temp.get("id_fornecedor"),
                        tipo_despesa=d_temp["tipo_despesa"],
                        descricao_detalhe=d_temp["descricao_detalhe"],
                        quantidade=d_temp["quantidade"],
                        valor_unitario=d_temp["valor_unitario"],
                        valor_total=d_temp["valor_total"],
                    )
                )
            db.commit()
            carregar_listas_base.clear()
            carregar_todas_viagens_consulta.clear()
            carregar_despesas_viagem.clear()
            st.session_state["despesas_temp"] = []
            st.session_state["edit_desp_tmp_idx"] = None
            st.session_state["viagem_ativa_id"] = nova_v.id_viagem
            st.session_state["loaded_viagem_id"] = None
            st.toast(f"Viagem {codigo_viagem_editado} salva com sucesso!", icon="🟧")
            st.rerun()
        else:
            v = db.query(Viagem).filter_by(id_viagem=id_viagem_atual).first()
            if not v:
                return
            c = v.ciclo
            c.id_cliente = cli_id
            c.nome_operacao = nome_operacao_final
            c.data_abertura = get_campo("data_frete") or c.data_abertura
            c.status_ciclo = f"COD::{codigo_viagem_editado}"

            fin = c.financeiro
            if not fin:
                fin = CicloFinanceiro(id_ciclo=c.id_ciclo)
                db.add(fin)

            fin.forma_contratacao = get_campo("forma_contr", "Aplicativo de Fretes")
            fin.valor_divulgado = get_campo("val_divulgado", 0.0)
            fin.valor_negociado_total = val_neg
            fin.perc_adiantamento = get_campo("perc_adiant", 0.0)
            fin.data_prevista_adiantamento = get_campo("data_adiant")
            fin.valor_adiantamento = val_ad
            fin.perc_saldo = get_campo("perc_saldo", 0.0)
            fin.data_prevista_saldo = get_campo("data_saldo")
            fin.valor_saldo = val_sd

            v.codigo_viagem = codigo_viagem_editado
            v.id_motorista = mot_id
            v.id_veiculo = vei_id
            v.id_frete_externo = get_campo("id_frete", "")
            v.tipo_viagem = tipo_viagem_val
            v.tipo_frete = tipo_frete_val
            v.rota_origem = rota_orig_val
            v.rota_destino = rota_dest_val
            v.rota_resumo = rota_resumo_val
            v.km_rota_planejado = get_campo("km_rota", 0.0)
            v.id_local_coleta = col_id
            v.data_coleta = get_campo("data_col")
            v.hora_planejada_coleta = get_campo("hr_plan_col")
            v.hora_real_coleta = get_campo("hr_real_col")
            v.id_local_entrega = ent_id
            v.data_entrega = get_campo("data_ent")
            v.hora_planejada_entrega = get_campo("hr_plan_ent")
            v.hora_real_entrega = get_campo("hr_real_ent")
            v.tipo_material = get_campo("tipo_mat", "")
            v.qtde_volumes = get_campo("qt_vol", 0)
            v.peso_bruto_kg = get_campo("peso_kg", 0.0)
            v.volume_m3 = get_campo("vol_m3", 0.0)
            v.nfe_carga = get_campo("nfe", "")
            v.cte_numero = get_campo("cte", "")
            v.mdfe_numero = get_campo("mdfe", "")
            v.ciot_numero = get_campo("ciot", "")
            v.odometro_inicial = km_ini
            v.odometro_final = km_fin
            v.km_real_rodado = km_real
            v.status_viagem = situacao_final

            db.commit()
            carregar_listas_base.clear()
            carregar_todas_viagens_consulta.clear()
            st.session_state["loaded_viagem_id"] = None
            st.toast(f"Viagem {codigo_viagem_editado} atualizada com sucesso!", icon="🟧")
            st.rerun()


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
    # TAB 1: INFORMAÇÕES FAEG + IMPORTAÇÃO DE PLANILHA
    # --------------------------------------------------------------------------
    if aba_ativa == MENU_ITENS[0]:
        render_cabecalho_aba("fa-solid fa-truck", "Informações FAEG", 1)

        c_id, c_st, _ = st.columns([3.5, 4.0, 4.5])
        c_id.text_input(
            "Código Único da Viagem (Editável)",
            value=get_campo("id_viagem_label", prox_cod_sidebar),
            placeholder="Ex: V1, V2, V15...",
            help="Identificador único sequencial (V1, V2, V3...). Pode ser editado manualmente para preencher viagens puladas da planilha.",
            key="w_id_viagem_label",
            on_change=sync_campo,
            args=("w_id_viagem_label", "id_viagem_label"),
        )
        situacao_opcoes = list(OPCOES_SITUACAO_OPERACAO)
        st_atual = get_campo("status_viagem", "Aguardando Adiantamento")
        if st_atual not in situacao_opcoes:
            situacao_opcoes.append(st_atual)
        c_st.selectbox(
            "Situação Financeira / Operação",
            options=situacao_opcoes,
            index=situacao_opcoes.index(st_atual),
            key="w_status_viagem",
            on_change=sync_campo,
            args=("w_status_viagem", "status_viagem"),
        )

        st.markdown('<div class="sec-subtitle">Dados do Motorista</div>', unsafe_allow_html=True)
        mot_opcoes = {0: "Selecione um motorista cadastrado..."}
        mot_map = {m["id_motorista"]: m for m in motoristas_db}
        for m in motoristas_db:
            mot_opcoes[m["id_motorista"]] = m["nome_completo"]

        mot_atual_id = get_campo("mot_id", 0)
        if mot_atual_id not in mot_opcoes:
            mot_atual_id = 0

        cm1, cm2, cm3 = st.columns([6, 3, 3])
        cm1.selectbox(
            "Nome do Motorista",
            options=list(mot_opcoes.keys()),
            index=list(mot_opcoes.keys()).index(mot_atual_id),
            format_func=lambda x: mot_opcoes[x],
            key="w_mot_id",
            on_change=sync_campo,
            args=("w_mot_id", "mot_id"),
        )
        mot_id_ativo = get_campo("mot_id", 0)
        m_atual = mot_map.get(mot_id_ativo)
        cm2.text_input(
            "Nº da CNH",
            value=m_atual["cnh_numero"] if m_atual else "",
            disabled=True,
            key=f"prev_mot_cnh_{mot_id_ativo}",
        )
        cm3.text_input(
            "Categoria CNH",
            value=m_atual["cnh_categoria"] if m_atual else "",
            disabled=True,
            key=f"prev_mot_cat_{mot_id_ativo}",
        )

        if m_atual and m_atual.get("cnh_validade"):
            dias_cnh = (m_atual["cnh_validade"] - date.today()).days
            if dias_cnh < 0:
                st.error(
                    f"🚨 Atenção: A CNH de **{m_atual['nome_completo']}** venceu em **{m_atual['cnh_validade'].strftime('%d/%m/%Y')}**!"
                )
            elif dias_cnh <= 30:
                st.warning(
                    f"⚠️ CNH de **{m_atual['nome_completo']}** vence em **{dias_cnh} dias** ({m_atual['cnh_validade'].strftime('%d/%m/%Y')})."
                )

        st.markdown('<div class="sec-subtitle">Dados do Veículo</div>', unsafe_allow_html=True)
        vei_opcoes = {0: "Selecione o veículo cadastrado..."}
        vei_map = {v["id_veiculo"]: v for v in veiculos_db}
        for v in veiculos_db:
            vei_opcoes[v["id_veiculo"]] = f"{v['descricao_marca']} ({v['placa']})"

        vei_atual_id = get_campo("vei_id", 0)
        if vei_atual_id not in vei_opcoes:
            vei_atual_id = 0

        cv1, cv2, cv3 = st.columns([6, 3, 3])
        cv1.selectbox(
            "Veículo / Carro",
            options=list(vei_opcoes.keys()),
            index=list(vei_opcoes.keys()).index(vei_atual_id),
            format_func=lambda x: vei_opcoes[x],
            key="w_vei_id",
            on_change=sync_campo,
            args=("w_vei_id", "vei_id"),
        )
        vei_id_ativo = get_campo("vei_id", 0)
        v_atual = vei_map.get(vei_id_ativo)
        cv2.text_input(
            "Placa",
            value=(v_atual["placa"] or "").upper() if v_atual else "",
            disabled=True,
            key=f"prev_vei_placa_{vei_id_ativo}",
        )
        cv3.text_input(
            "Tipo de Veículo",
            value=v_atual["tipo_veiculo"] if v_atual else "",
            disabled=True,
            key=f"prev_vei_tipo_{vei_id_ativo}",
        )

        # ----------------------------------------------------------------------
        # IMPORTAÇÃO / CONCILIAÇÃO DA PLANILHA EXCEL FAEG
        # ----------------------------------------------------------------------
        st.markdown(
            '<div class="sec-subtitle">Importar Planilha de Controle Operacional (Excel .xlsx)</div>',
            unsafe_allow_html=True,
        )
        with st.expander("📤 Fazer upload da planilha FAEG para importar / conciliar viagens no banco", expanded=False):
            st.caption(
                "Importa automaticamente todas as viagens, receitas (Adiantamento + Saldo), despesas (Diesel, ARLA, Pedágio, Alimentação, Hospedagem, Manutenção, Outras) "
                "e cadastros da planilha. Campos novos no sistema que não existam na planilha ficam liberados para edição posterior."
            )
            up_c1, up_c2 = st.columns([7.5, 4.5])
            arquivo_xlsx = up_c1.file_uploader(
                "Selecione o arquivo Excel (.xlsx)",
                type=["xlsx"],
                key="uploader_planilha_faeg",
                label_visibility="collapsed",
            )
            modo_dup = up_c2.selectbox(
                "Se o Código da Viagem já existir no banco:",
                options=["atualizar", "ignorar"],
                format_func=lambda m: (
                    "Atualizar e conciliar com a planilha"
                    if m == "atualizar"
                    else "Manter registro atual e ignorar duplicado"
                ),
                key="modo_dup_planilha",
            )

            if arquivo_xlsx is not None:
                bytes_plan = arquivo_xlsx.getvalue()
                try:
                    prev_regs = analisar_planilha_faeg(bytes_plan)
                except Exception as exc:
                    prev_regs = []
                    st.error(f"Erro ao ler a planilha: {exc}")

                if prev_regs:
                    tot_rec_prev = sum(r["receita_consolidada"] for r in prev_regs)
                    tot_desp_prev = sum(r["despesa_consolidada"] for r in prev_regs)
                    tot_res_prev = sum(r["resultado_consolidado"] for r in prev_regs)

                    st.markdown(
                        f"""
                        <div class="kpi-consulta-grid">
                            <div class="kpi-consulta-card">
                                <div class="kpi-consulta-lbl">Viagens Identificadas</div>
                                <div class="kpi-consulta-val">{len(prev_regs)}</div>
                            </div>
                            <div class="kpi-consulta-card">
                                <div class="kpi-consulta-lbl">Receita Total (Planilha)</div>
                                <div class="kpi-consulta-val">{fmt_brl(tot_rec_prev)}</div>
                            </div>
                            <div class="kpi-consulta-card orange">
                                <div class="kpi-consulta-lbl">Despesas Totais (Planilha)</div>
                                <div class="kpi-consulta-val" style="color:#F34D25;">{fmt_brl(tot_desp_prev)}</div>
                            </div>
                            <div class="kpi-consulta-card">
                                <div class="kpi-consulta-lbl">Resultado Líquido (Planilha)</div>
                                <div class="kpi-consulta-val">{fmt_brl(tot_res_prev)}</div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    df_prev_plan = pd.DataFrame(
                        [
                            {
                                "Linha": r["linha"],
                                "ID Planilha": r["raw_id"] or "(Auto V#)",
                                "Motorista": r["motorista"] or "⚠️ Pendente",
                                "Placa": r["placa"] or "⚠️ Pendente",
                                "Cliente": r["empresa"] or "⚠️ Pendente",
                                "Origem": r["rota_origem"] or "-",
                                "Destino": r["rota_destino"] or "-",
                                "Receita": fmt_brl(r["receita_consolidada"]),
                                "Despesas": fmt_brl(r["despesa_consolidada"]),
                                "Resultado": fmt_brl(r["resultado_consolidado"]),
                            }
                            for r in prev_regs
                        ]
                    )
                    st.dataframe(df_prev_plan, use_container_width=True, hide_index=True)

                    if st.button("🚀 Confirmar Importação e Gravar no Banco de Dados", use_container_width=True):
                        with st.spinner("Sincronizando cadastros, viagens, receitas e despesas no Neon..."):
                            rel_imp = importar_planilha_para_banco(bytes_plan, modo_duplicado=modo_dup)
                        carregar_listas_base.clear()
                        carregar_todas_viagens_consulta.clear()
                        carregar_despesas_viagem.clear()
                        st.session_state["loaded_viagem_id"] = None
                        st.session_state["ultimo_relatorio_importacao"] = rel_imp
                        st.rerun()

            if "ultimo_relatorio_importacao" in st.session_state:
                rel_ok = st.session_state["ultimo_relatorio_importacao"]
                st.success(
                    f"✅ Importação concluída! **{rel_ok['importadas']}** viagem(ns) nova(s) inserida(s), "
                    f"**{rel_ok['atualizadas']}** atualizada(s) e **{rel_ok['ignoradas']}** ignorada(s)."
                )
                if rel_ok.get("pendencias"):
                    with st.expander(
                        f"⚠️ Campos complementares para revisar depois ({len(rel_ok['pendencias'])} aviso(s))",
                        expanded=True,
                    ):
                        for p_txt in rel_ok["pendencias"]:
                            st.write(f"- {p_txt}")

        render_navegacao_rodape(0, MENU_ITENS)

    # --------------------------------------------------------------------------
    # TAB 2: FRETE, CARGA E DOCUMENTOS
    # --------------------------------------------------------------------------
    elif aba_ativa == MENU_ITENS[1]:
        render_cabecalho_aba("fa-solid fa-file-invoice", "Frete, Carga e Documentos", 2)

        c1, c2, c3, c4, c5 = st.columns([1.8, 2.2, 2.2, 3.3, 2.5])
        c1.text_input(
            "ID Frete",
            value=get_campo("id_frete", ""),
            placeholder="Ex: F26-000001",
            key="w_id_frete",
            on_change=sync_campo,
            args=("w_id_frete", "id_frete"),
        )
        c2.date_input(
            "Data Operação",
            value=get_campo("data_frete", date.today()),
            format="DD/MM/YYYY",
            key="w_data_frete",
            on_change=sync_campo,
            args=("w_data_frete", "data_frete"),
        )
        tipos_viagem = ["Individual", "Ciclo"]
        tv_val = get_campo("tipo_viagem", "Individual")
        if tv_val not in tipos_viagem:
            tv_val = "Individual"
        tipo_viagem_sel = c3.selectbox(
            "Tipo de Viagem",
            tipos_viagem,
            index=tipos_viagem.index(tv_val),
            key="w_tipo_viagem",
            on_change=on_tipo_viagem_change,
        )
        eh_individual = tipo_viagem_sel == "Individual"
        c4.text_input(
            "Nº do Ciclo Operacional",
            value="" if eh_individual else get_campo("ciclo_nome", ""),
            placeholder="Bloqueado (Viagem Individual)" if eh_individual else "Digite o nº do ciclo (Ex: 2026-01)",
            disabled=eh_individual,
            key="w_ciclo_nome",
            on_change=sync_campo,
            args=("w_ciclo_nome", "ciclo_nome"),
        )
        tipos_frete = ["Dedicado", "Complemento", "Cheio", "Fracionado", "Agregado"]
        tf_val = get_campo("tipo_frete", "Dedicado")
        if tf_val not in tipos_frete:
            tf_val = "Dedicado"
        c5.selectbox(
            "Tipo de Frete",
            tipos_frete,
            index=tipos_frete.index(tf_val),
            key="w_tipo_frete",
            on_change=sync_campo,
            args=("w_tipo_frete", "tipo_frete"),
        )

        # ROTA SEPARADA EM ORIGEM E DESTINO
        c_orig, c_dest, c_km = st.columns([4.75, 4.75, 2.5])
        c_orig.text_input(
            "Origem",
            value=get_campo("rota_origem", ""),
            placeholder="Ex: Suzano/SP",
            key="w_rota_origem",
            on_change=sync_campo,
            args=("w_rota_origem", "rota_origem"),
        )
        c_dest.text_input(
            "Destino",
            value=get_campo("rota_destino", ""),
            placeholder="Ex: Rio de Janeiro/RJ",
            key="w_rota_destino",
            on_change=sync_campo,
            args=("w_rota_destino", "rota_destino"),
        )
        c_km.number_input(
            "KM Planejado",
            value=to_float(get_campo("km_rota", 0.0)),
            min_value=0.0,
            step=10.0,
            key="w_km_rota",
            on_change=sync_campo,
            args=("w_km_rota", "km_rota"),
        )

        st.markdown('<div class="sec-subtitle">Detalhes da Carga</div>', unsafe_allow_html=True)
        c8, c9, c10, c11 = st.columns([5.5, 2.0, 2.0, 2.5])
        c8.text_input(
            "Tipo de Material",
            value=get_campo("tipo_mat", ""),
            placeholder="Ex: Bobinas de Aço / Carga Geral",
            key="w_tipo_mat",
            on_change=sync_campo,
            args=("w_tipo_mat", "tipo_mat"),
        )
        c9.number_input(
            "QT Volumes",
            value=to_int(get_campo("qt_vol", 0)),
            min_value=0,
            step=1,
            key="w_qt_vol",
            on_change=sync_campo,
            args=("w_qt_vol", "qt_vol"),
        )
        vol_informado = c10.number_input(
            "Volume (m³)",
            value=to_float(get_campo("vol_m3", 0.0)),
            min_value=0.0,
            step=0.01,
            key="w_vol_m3",
            on_change=sync_campo,
            args=("w_vol_m3", "vol_m3"),
        )
        peso_informado = c11.number_input(
            "Peso Bruto (KG)",
            value=to_float(get_campo("peso_kg", 0.0)),
            min_value=0.0,
            step=0.01,
            key="w_peso_kg",
            on_change=sync_campo,
            args=("w_peso_kg", "peso_kg"),
        )

        vei_carga = next((v for v in veiculos_db if v["id_veiculo"] == get_campo("vei_id", 0)), None)
        if vei_carga:
            cap_kg = to_float(vei_carga.get("capacidade_carga_kg"), 0.0)
            cap_m3 = to_float(vei_carga.get("capacidade_volume_m3"), 0.0)
            if cap_kg > 0 and peso_informado > cap_kg:
                st.warning(
                    f"⚠️ O peso informado ({peso_informado:g} kg) excede a capacidade cadastrada do veículo "
                    f"**{vei_carga['descricao_marca']}** ({cap_kg:g} kg)."
                )
            if cap_m3 > 0 and vol_informado > cap_m3:
                st.warning(
                    f"⚠️ O volume informado ({vol_informado:g} m³) excede a capacidade cúbica do veículo "
                    f"**{vei_carga['descricao_marca']}** ({cap_m3:g} m³)."
                )

        st.markdown('<div class="sec-subtitle">Documentos Fiscais</div>', unsafe_allow_html=True)
        d1, d2, d3, d4 = st.columns([3, 3, 3, 3])
        d1.text_input(
            "NF-e / Carga",
            value=get_campo("nfe", ""),
            placeholder="Nº da NF-e",
            key="w_nfe",
            on_change=sync_campo,
            args=("w_nfe", "nfe"),
        )
        d2.text_input(
            "CT-e",
            value=get_campo("cte", ""),
            placeholder="Nº do CT-e",
            key="w_cte",
            on_change=sync_campo,
            args=("w_cte", "cte"),
        )
        d3.text_input(
            "MDF-e",
            value=get_campo("mdfe", ""),
            placeholder="Nº do MDF-e",
            key="w_mdfe",
            on_change=sync_campo,
            args=("w_mdfe", "mdfe"),
        )
        d4.text_input(
            "CIOT",
            value=get_campo("ciot", ""),
            placeholder="Código CIOT",
            key="w_ciot",
            on_change=sync_campo,
            args=("w_ciot", "ciot"),
        )

        render_navegacao_rodape(1, MENU_ITENS)

    # --------------------------------------------------------------------------
    # TAB 3: CLIENTE / CONTRATANTE
    # --------------------------------------------------------------------------
    elif aba_ativa == MENU_ITENS[2]:
        render_cabecalho_aba("fa-solid fa-building", "Cliente / Contratante", 3)

        cli_opcoes = {0: "Selecione um cliente cadastrado..."}
        cli_map = {c["id_cliente"]: c for c in clientes_db}
        for c in clientes_db:
            cli_opcoes[c["id_cliente"]] = formatar_rotulo_cliente(c)

        cli_atual_id = get_campo("cli_id", 0)
        if cli_atual_id not in cli_opcoes:
            cli_atual_id = 0

        st.selectbox(
            "Empresa Cliente (Razão Social / Nome Fantasia — Endereço)",
            options=list(cli_opcoes.keys()),
            index=list(cli_opcoes.keys()).index(cli_atual_id),
            format_func=lambda x: cli_opcoes[x],
            key="w_cli_id",
            on_change=on_cliente_change,
            args=(clientes_db, locais_db),
        )
        cli_id_ativo = get_campo("cli_id", 0)
        c_atual = cli_map.get(cli_id_ativo)

        cc1, cc2, cc3 = st.columns([4.5, 4.5, 3.0])
        cc1.text_input(
            "Razão Social",
            value=c_atual["razao_social"] if c_atual else "",
            disabled=True,
            key=f"prev_cli_rz_{cli_id_ativo}",
        )
        cc2.text_input(
            "Nome Fantasia",
            value=(c_atual.get("nome_fantasia") or "") if c_atual else "",
            disabled=True,
            key=f"prev_cli_ft_{cli_id_ativo}",
        )
        cc3.text_input(
            "CNPJ / CPF",
            value=c_atual["cnpj_cpf"] if c_atual else "",
            disabled=True,
            key=f"prev_cli_doc_{cli_id_ativo}",
        )

        cc4, cc5, cc6 = st.columns([4.0, 4.0, 4.0])
        cc4.text_input(
            "Responsável",
            value=(c_atual["responsavel_comercial"] or "") if c_atual else "",
            disabled=True,
            key=f"prev_cli_resp_{cli_id_ativo}",
        )
        cc5.text_input(
            "Telefone / Contato",
            value=(c_atual["telefone_comercial"] or "") if c_atual else "",
            disabled=True,
            key=f"prev_cli_tel_{cli_id_ativo}",
        )
        cc6.text_input(
            "E-mail",
            value=(c_atual["email_financeiro"] or "") if c_atual else "",
            disabled=True,
            key=f"prev_cli_mail_{cli_id_ativo}",
        )

        end_cli_txt = ""
        if c_atual:
            partes_e = [
                p
                for p in [
                    c_atual.get("endereco_completo"),
                    f"{c_atual.get('cidade') or ''}/{c_atual.get('uf') or ''}".strip("/"),
                    f"CEP: {c_atual['cep']}" if c_atual.get("cep") else "",
                ]
                if p
            ]
            end_cli_txt = " — ".join(partes_e)
        st.text_input(
            "Endereço do Cliente",
            value=end_cli_txt,
            disabled=True,
            key=f"prev_cli_end_{cli_id_ativo}",
        )

        if c_atual:
            col_corresp = next((l for l in locais_db if l["id_local"] == get_campo("col_id", 0)), None)
            if col_corresp:
                st.success(
                    f"📍 Local de Coleta vinculado automaticamente: **{col_corresp['nome_local']}** "
                    f"({col_corresp.get('endereco_completo') or '-'}, {col_corresp.get('cidade') or ''}/{col_corresp.get('uf') or ''})"
                )

        render_navegacao_rodape(2, MENU_ITENS)

    # --------------------------------------------------------------------------
    # TAB 4: NEGOCIAÇÃO E RECEBIMENTOS (CÁLCULOS AUTOMÁTICOS BIDIRECIONAIS)
    # --------------------------------------------------------------------------
    elif aba_ativa == MENU_ITENS[3]:
        render_cabecalho_aba("fa-solid fa-handshake", "Negociação e Recebimentos", 4)

        f1, f2, f3 = st.columns([3.5, 3.2, 5.3])
        fc_val = get_campo("forma_contr", "Aplicativo de Fretes")
        f1.selectbox(
            "Origem de Frete",
            OPCOES_ORIGEM_FRETE,
            index=OPCOES_ORIGEM_FRETE.index(fc_val) if fc_val in OPCOES_ORIGEM_FRETE else 0,
            key="w_forma_contr",
            on_change=sync_campo,
            args=("w_forma_contr", "forma_contr"),
        )
        f2.number_input(
            "Valor Divulgado (R$)",
            value=to_float(get_campo("val_divulgado", 0.0)),
            min_value=0.0,
            step=50.0,
            key="w_val_divulgado",
            on_change=sync_campo,
            args=("w_val_divulgado", "val_divulgado"),
        )
        val_neg = f3.number_input(
            "Valor Negociado (R$)",
            value=to_float(get_campo("val_negociado", 0.0)),
            min_value=0.0,
            step=50.0,
            key="w_val_negociado",
            on_change=on_negociacao_change,
            args=("val_negociado",),
        )

        st.markdown('<div class="sec-subtitle">Adiantamento (% ou R$)</div>', unsafe_allow_html=True)
        a1, a2, a3 = st.columns([3, 3.5, 5.5])
        a1.number_input(
            "% Adiantamento",
            value=to_float(get_campo("perc_adiant", 0.0)),
            min_value=0.0,
            max_value=100.0,
            step=1.0,
            key="w_perc_adiant",
            on_change=on_negociacao_change,
            args=("perc_adiant",),
        )
        a2.date_input(
            "Data Adiantamento",
            value=get_campo("data_adiant", date.today()),
            format="DD/MM/YYYY",
            key="w_data_adiant",
            on_change=sync_campo,
            args=("w_data_adiant", "data_adiant"),
        )
        a3.number_input(
            "Valor Adiantamento (R$)",
            value=to_float(get_campo("val_adiant", 0.0)),
            min_value=0.0,
            step=50.0,
            key="w_val_adiant",
            on_change=on_negociacao_change,
            args=("val_adiant",),
        )

        st.markdown('<div class="sec-subtitle">Saldo a Receber (% ou R$)</div>', unsafe_allow_html=True)
        s1, s2, s3 = st.columns([3, 3.5, 5.5])
        s1.number_input(
            "% Saldo",
            value=to_float(get_campo("perc_saldo", 0.0)),
            min_value=0.0,
            max_value=100.0,
            step=1.0,
            key="w_perc_saldo",
            on_change=on_negociacao_change,
            args=("perc_saldo",),
        )
        s2.date_input(
            "Data Saldo",
            value=get_campo("data_saldo", date.today()),
            format="DD/MM/YYYY",
            key="w_data_saldo",
            on_change=sync_campo,
            args=("w_data_saldo", "data_saldo"),
        )
        s3.number_input(
            "Valor Saldo (R$)",
            value=to_float(get_campo("val_saldo", 0.0)),
            min_value=0.0,
            step=50.0,
            key="w_val_saldo",
            on_change=on_negociacao_change,
            args=("val_saldo",),
        )

        total_recebido = to_float(get_campo("val_adiant", 0.0)) + to_float(get_campo("val_saldo", 0.0))
        st.markdown(
            f"""
            <div class="faeg-recebimento-banner">
                <span class="faeg-recebimento-label">Valor Total Recebido (Adiant. + Saldo):</span>
                <span class="faeg-recebimento-val">{fmt_brl(total_recebido)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if val_neg > 0 and abs(val_neg - total_recebido) > 0.01:
            st.caption(
                f"ℹ️ Diferença / Pendente entre Valor Negociado ({fmt_brl(val_neg)}) e Total Recebido ({fmt_brl(total_recebido)}): "
                f"**{fmt_brl(val_neg - total_recebido)}**"
            )

        render_navegacao_rodape(3, MENU_ITENS)

    # --------------------------------------------------------------------------
    # TAB 5: LOCAL DE COLETA (ORIGEM) — ATUALIZAÇÃO INSTANTÂNEA
    # --------------------------------------------------------------------------
    elif aba_ativa == MENU_ITENS[4]:
        render_cabecalho_aba("fa-solid fa-location-arrow", "Local de Coleta (Origem)", 5)

        cli_map_local = {c["id_cliente"]: c for c in clientes_db}
        cli_sel_atual = cli_map_local.get(get_campo("cli_id", 0))
        if cli_sel_atual:
            end_cli_b = ", ".join(
                p
                for p in [
                    cli_sel_atual.get("endereco_completo"),
                    f"{cli_sel_atual.get('cidade') or ''}/{cli_sel_atual.get('uf') or ''}".strip("/"),
                ]
                if p
            )
            st.markdown(
                f"""
                <div class="cliente-coleta-banner">
                    <strong>Cliente / Transportadora Selecionada:</strong> {cli_sel_atual['razao_social']}
                    {f" ({cli_sel_atual['nome_fantasia']})" if cli_sel_atual.get('nome_fantasia') else ""}
                    {f" &nbsp;|&nbsp; <strong>Endereço do Cadastro:</strong> {end_cli_b}" if end_cli_b else ""}
                </div>
                """,
                unsafe_allow_html=True,
            )

        loc_opcoes = {0: "Selecione um local cadastrado..."}
        loc_map = {l["id_local"]: l for l in locais_db}
        for l in locais_db:
            loc_opcoes[l["id_local"]] = formatar_rotulo_local(l, cli_map_local)

        col_atual_id = get_campo("col_id", 0)
        if col_atual_id not in loc_opcoes:
            col_atual_id = 0

        lc0, lc1, lc3, lc4 = st.columns([6.0, 2.0, 2.8, 1.2])
        lc0.selectbox(
            "Base / Empresa Cadastrada (Endereço e Cliente)",
            options=list(loc_opcoes.keys()),
            index=list(loc_opcoes.keys()).index(col_atual_id),
            format_func=lambda x: loc_opcoes[x],
            key="w_col_id",
            on_change=on_local_select_change,
            args=("w_col_id", "col_id", locais_db),
        )
        col_id_ativo = get_campo("col_id", 0)
        l_col = loc_map.get(col_id_ativo)
        lc1.text_input(
            "CEP",
            value=(l_col.get("cep") or "") if l_col else "",
            disabled=True,
            key=f"prev_col_cep_{col_id_ativo}",
        )
        lc3.text_input(
            "Cidade",
            value=(l_col.get("cidade") or "") if l_col else "",
            disabled=True,
            key=f"prev_col_cid_{col_id_ativo}",
        )
        lc4.text_input(
            "UF",
            value=(l_col.get("uf") or "") if l_col else "",
            disabled=True,
            key=f"prev_col_uf_{col_id_ativo}",
        )

        lc_end, lc_cont, lc_rest = st.columns([6.0, 3.0, 3.0])
        lc_end.text_input(
            "Endereço Completo",
            value=(l_col.get("endereco_completo") or "") if l_col else "",
            disabled=True,
            key=f"prev_col_end_{col_id_ativo}",
        )
        lc_cont.text_input(
            "Contato / Portaria",
            value=(l_col.get("contato_portaria") or "") if l_col else "",
            disabled=True,
            key=f"prev_col_cont_{col_id_ativo}",
        )
        lc_rest.text_input(
            "Restrição de Horário",
            value=(l_col.get("restricao_horario") or "") if l_col else "",
            disabled=True,
            key=f"prev_col_rest_{col_id_ativo}",
        )

        st.markdown('<div class="sec-subtitle">Horários da Operação</div>', unsafe_allow_html=True)
        hc1, hc2, hc3 = st.columns([6.0, 3.0, 3.0])
        hc1.date_input(
            "Data Coleta",
            value=get_campo("data_col", date.today()),
            format="DD/MM/YYYY",
            key="w_data_col",
            on_change=sync_campo,
            args=("w_data_col", "data_col"),
        )
        hc2.time_input(
            "Hora Planejada",
            value=get_campo("hr_plan_col", None),
            key="w_hr_plan_col",
            on_change=sync_campo,
            args=("w_hr_plan_col", "hr_plan_col"),
        )
        hc3.time_input(
            "Hora Real",
            value=get_campo("hr_real_col", None),
            key="w_hr_real_col",
            on_change=sync_campo,
            args=("w_hr_real_col", "hr_real_col"),
        )

        render_navegacao_rodape(4, MENU_ITENS)

    # --------------------------------------------------------------------------
    # TAB 6: LOCAL DE ENTREGA (DESTINO) — ATUALIZAÇÃO INSTANTÂNEA
    # --------------------------------------------------------------------------
    elif aba_ativa == MENU_ITENS[5]:
        render_cabecalho_aba("fa-solid fa-map-pin", "Local de Entrega (Destino)", 6)

        cli_map_local = {c["id_cliente"]: c for c in clientes_db}
        loc_opcoes = {0: "Selecione um local cadastrado..."}
        loc_map = {l["id_local"]: l for l in locais_db}
        for l in locais_db:
            loc_opcoes[l["id_local"]] = formatar_rotulo_local(l, cli_map_local)

        ent_atual_id = get_campo("ent_id", 0)
        if ent_atual_id not in loc_opcoes:
            ent_atual_id = 0

        le0, le1, le3, le4 = st.columns([6.0, 2.0, 2.8, 1.2])
        le0.selectbox(
            "Base / Empresa Cadastrada (Endereço e Cliente)",
            options=list(loc_opcoes.keys()),
            index=list(loc_opcoes.keys()).index(ent_atual_id),
            format_func=lambda x: loc_opcoes[x],
            key="w_ent_id",
            on_change=on_local_select_change,
            args=("w_ent_id", "ent_id", locais_db),
        )
        ent_id_ativo = get_campo("ent_id", 0)
        l_ent = loc_map.get(ent_id_ativo)
        le1.text_input(
            "CEP",
            value=(l_ent.get("cep") or "") if l_ent else "",
            disabled=True,
            key=f"prev_ent_cep_{ent_id_ativo}",
        )
        le3.text_input(
            "Cidade",
            value=(l_ent.get("cidade") or "") if l_ent else "",
            disabled=True,
            key=f"prev_ent_cid_{ent_id_ativo}",
        )
        le4.text_input(
            "UF",
            value=(l_ent.get("uf") or "") if l_ent else "",
            disabled=True,
            key=f"prev_ent_uf_{ent_id_ativo}",
        )

        le_end, le_cont, le_rest = st.columns([6.0, 3.0, 3.0])
        le_end.text_input(
            "Endereço Completo",
            value=(l_ent.get("endereco_completo") or "") if l_ent else "",
            disabled=True,
            key=f"prev_ent_end_{ent_id_ativo}",
        )
        le_cont.text_input(
            "Contato / Portaria",
            value=(l_ent.get("contato_portaria") or "") if l_ent else "",
            disabled=True,
            key=f"prev_ent_cont_{ent_id_ativo}",
        )
        le_rest.text_input(
            "Restrição de Horário",
            value=(l_ent.get("restricao_horario") or "") if l_ent else "",
            disabled=True,
            key=f"prev_ent_rest_{ent_id_ativo}",
        )

        st.markdown('<div class="sec-subtitle">Horários da Operação</div>', unsafe_allow_html=True)
        he1, he2, he3 = st.columns([6.0, 3.0, 3.0])
        he1.date_input(
            "Data Entrega",
            value=get_campo("data_ent", date.today()),
            format="DD/MM/YYYY",
            key="w_data_ent",
            on_change=sync_campo,
            args=("w_data_ent", "data_ent"),
        )
        he2.time_input(
            "Hora Planejada",
            value=get_campo("hr_plan_ent", None),
            key="w_hr_plan_ent",
            on_change=sync_campo,
            args=("w_hr_plan_ent", "hr_plan_ent"),
        )
        he3.time_input(
            "Hora Real",
            value=get_campo("hr_real_ent", None),
            key="w_hr_real_ent",
            on_change=sync_campo,
            args=("w_hr_real_ent", "hr_real_ent"),
        )

        render_navegacao_rodape(5, MENU_ITENS)

    # --------------------------------------------------------------------------
    # TAB 7: DESPESAS DE VIAGEM
    # --------------------------------------------------------------------------
    elif aba_ativa == MENU_ITENS[6]:
        render_cabecalho_aba("fa-solid fa-receipt", "Despesas de Viagem", 7)

        lista_desp_cache = carregar_despesas_viagem(viagem_sel_id) if viagem_sel_id != 0 else []
        lista_desp_tmp = st.session_state.get("despesas_temp", [])

        edit_id = st.session_state.get("edit_desp_id", None)
        edit_tmp_idx = st.session_state.get("edit_desp_tmp_idx", None)

        if viagem_sel_id != 0:
            desp_edit_obj = next((d for d in lista_desp_cache if d["id_despesa"] == edit_id), None)
        else:
            desp_edit_obj = (
                lista_desp_tmp[edit_tmp_idx]
                if (edit_tmp_idx is not None and 0 <= edit_tmp_idx < len(lista_desp_tmp))
                else None
            )

        sufixo_desp = f"ed_{edit_id or edit_tmp_idx}" if desp_edit_obj else "new"

        with st.container(border=True):
            st.markdown(
                f"<div style='font-size:0.8rem;font-weight:800;color:#0D263C;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:0.8rem;'>"
                f"{'✏️ Editar Despesa' if desp_edit_obj else 'Adicionar Nova Despesa'}</div>",
                unsafe_allow_html=True,
            )

            tipos_desp = list(CATEGORIAS_DESPESA_FORNECEDOR)
            if desp_edit_obj and desp_edit_obj["tipo_despesa"] not in tipos_desp:
                tipos_desp.append(desp_edit_obj["tipo_despesa"])

            forn_opcoes = {0: "Não informado"}
            for f in fornecedores_db:
                forn_opcoes[f["id_fornecedor"]] = f["nome_fantasia"]

            d1, d2, d3, d4, d5 = st.columns([2.5, 3.9, 2.6, 1.4, 1.6])
            idx_tp = (
                tipos_desp.index(desp_edit_obj["tipo_despesa"])
                if desp_edit_obj and desp_edit_obj["tipo_despesa"] in tipos_desp
                else 0
            )
            tp_sel = d1.selectbox("Tipo de Despesa", tipos_desp, index=idx_tp, key=f"inp_desp_tipo_{sufixo_desp}")
            desc_sel = d2.text_input(
                "Descrição / Local",
                placeholder="Ex: Abastecimento Ida",
                value=desp_edit_obj["descricao_detalhe"] if desp_edit_obj else "",
                key=f"inp_desp_desc_{sufixo_desp}",
            )
            idx_forn = (
                list(forn_opcoes.keys()).index(desp_edit_obj["id_fornecedor"])
                if desp_edit_obj and desp_edit_obj.get("id_fornecedor") in forn_opcoes
                else 0
            )
            forn_sel = d3.selectbox(
                "Fornecedor / Posto",
                options=list(forn_opcoes.keys()),
                index=idx_forn,
                format_func=lambda x: forn_opcoes[x],
                key=f"inp_desp_forn_{sufixo_desp}",
            )
            qtd_sel = d4.number_input(
                "Qtd / L",
                min_value=0.01,
                step=1.0,
                value=to_float(desp_edit_obj["quantidade"], 1.0) if desp_edit_obj else 1.0,
                key=f"inp_desp_qtd_{sufixo_desp}",
            )
            val_sel = d5.number_input(
                "Unitário (R$)",
                min_value=0.0,
                step=5.0,
                value=to_float(desp_edit_obj["valor_unitario"], 0.0) if desp_edit_obj else 0.0,
                key=f"inp_desp_val_{sufixo_desp}",
            )

            total_preview = round(qtd_sel * val_sel, 2)
            bar1, bar2, bar3 = st.columns([3, 1, 1.3])
            bar1.markdown(
                f"<div style='padding-top:0.5rem;font-weight:700;color:#0D263C;text-transform:uppercase;font-size:0.82rem;'>"
                f"Valor Total: <span style='font-size:1.4rem;color:#F34D25;font-weight:900;margin-left:0.5rem;'>{fmt_brl(total_preview)}</span></div>",
                unsafe_allow_html=True,
            )

            if desp_edit_obj:
                if bar2.button("Cancelar", use_container_width=True):
                    st.session_state["edit_desp_id"] = None
                    st.session_state["edit_desp_tmp_idx"] = None
                    st.rerun()

            btn_label = "Atualizar Despesa" if desp_edit_obj else "Adicionar à Lista"
            if bar3.button(btn_label, use_container_width=True):
                if val_sel <= 0 or not desc_sel.strip():
                    st.warning("Preencha descrição e valor.")
                elif viagem_sel_id == 0:
                    item_novo = {
                        "id_fornecedor": forn_sel if forn_sel != 0 else None,
                        "tipo_despesa": tp_sel,
                        "descricao_detalhe": desc_sel.strip(),
                        "quantidade": qtd_sel,
                        "valor_unitario": val_sel,
                        "valor_total": total_preview,
                    }
                    if desp_edit_obj and edit_tmp_idx is not None:
                        lista_desp_tmp[edit_tmp_idx] = item_novo
                        st.session_state["edit_desp_tmp_idx"] = None
                        st.toast("Despesa atualizada!", icon="🧾")
                    else:
                        lista_desp_tmp.append(item_novo)
                        st.toast("Despesa adicionada à fila (será gravada ao clicar em Salvar Viagem).", icon="🧾")
                    st.session_state["despesas_temp"] = lista_desp_tmp
                    st.rerun()
                else:
                    with SessionLocal() as db:
                        if desp_edit_obj:
                            obj_db = db.query(ViagemDespesa).filter_by(id_despesa=desp_edit_obj["id_despesa"]).first()
                            if obj_db:
                                obj_db.tipo_despesa = tp_sel
                                obj_db.descricao_detalhe = desc_sel.strip()
                                obj_db.id_fornecedor = forn_sel if forn_sel != 0 else None
                                obj_db.quantidade = qtd_sel
                                obj_db.valor_unitario = val_sel
                                obj_db.valor_total = total_preview
                            st.session_state["edit_desp_id"] = None
                        else:
                            db.add(
                                ViagemDespesa(
                                    id_viagem=viagem_sel_id,
                                    id_fornecedor=forn_sel if forn_sel != 0 else None,
                                    tipo_despesa=tp_sel,
                                    descricao_detalhe=desc_sel.strip(),
                                    quantidade=qtd_sel,
                                    valor_unitario=val_sel,
                                    valor_total=total_preview,
                                )
                            )
                        db.commit()
                    carregar_despesas_viagem.clear()
                    carregar_todas_viagens_consulta.clear()
                    st.toast("Despesa salva com sucesso!", icon="🧾")
                    st.rerun()

        lista_desp = lista_desp_cache if viagem_sel_id != 0 else lista_desp_tmp
        custo_total_desp = sum(to_float(d["valor_total"]) for d in lista_desp)

        if not lista_desp:
            st.markdown(
                """
                <div style="border:1px solid #D6D6D6;border-radius:0.45rem;overflow:hidden;margin-top:1rem;">
                    <div style="background:#0D263C;color:#FFFFFF;padding:0.85rem 1rem;font-weight:700;font-size:0.78rem;text-transform:uppercase;letter-spacing:0.04em;display:grid;grid-template-columns:1.3fr 2.2fr 0.7fr 1fr 1fr;">
                        <span>Tipo</span><span>Descrição</span><span style="text-align:center;">Qtd</span><span style="text-align:right;">Unitário</span><span style="text-align:right;">Total</span>
                    </div>
                    <div style="padding:1.5rem;text-align:center;color:#64748B;font-style:italic;background:#FFFFFF;">Nenhuma despesa lançada.</div>
                    <div style="background:#F1F5F9;color:#0D263C;padding:0.85rem 1rem;font-weight:800;display:flex;justify-content:flex-end;align-items:center;gap:1.5rem;border-top:2px solid #0D263C;">
                        <span>CUSTO TOTAL:</span><span style="font-size:1.25rem;color:#F34D25;font-weight:900;">R$ 0,00</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div style="background:#0D263C;color:#FFFFFF;padding:0.8rem 1rem;border-radius:0.45rem 0.45rem 0 0;font-weight:700;font-size:0.78rem;text-transform:uppercase;letter-spacing:0.04em;display:grid;grid-template-columns:1.3fr 2.2fr 0.7fr 1fr 1fr 0.9fr;">
                    <span>Tipo</span><span>Descrição</span><span style="text-align:center;">Qtd</span><span style="text-align:right;">Unitário</span><span style="text-align:right;">Total</span><span style="text-align:center;">Ações</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if viagem_sel_id != 0:
                for d in lista_desp:
                    did = d["id_despesa"]
                    r1, r2, r3, r4, r5, r6, r7 = st.columns([1.3, 2.2, 0.7, 1.0, 1.0, 0.45, 0.45])
                    r1.write(d["tipo_despesa"])
                    r2.write(d["descricao_detalhe"] or "-")
                    r3.markdown(
                        f"<div style='text-align:center;'>{to_float(d['quantidade']):g}</div>", unsafe_allow_html=True
                    )
                    r4.markdown(
                        f"<div style='text-align:right;'>{fmt_brl(d['valor_unitario'])}</div>", unsafe_allow_html=True
                    )
                    r5.markdown(
                        f"<div style='text-align:right;font-weight:700;color:#F34D25;'>{fmt_brl(d['valor_total'])}</div>",
                        unsafe_allow_html=True,
                    )
                    if r6.button("✏️", key=f"ed_d_{did}", help="Editar"):
                        st.session_state["confirm_edit_desp"] = did
                        st.session_state["confirm_del_desp"] = None
                        st.rerun()
                    if r7.button("🗑️", key=f"del_d_{did}", help="Remover"):
                        st.session_state["confirm_del_desp"] = did
                        st.session_state["confirm_edit_desp"] = None
                        st.rerun()

                    if st.session_state.get("confirm_edit_desp") == did:
                        st.markdown(
                            f"<div class='confirm-box-edit'>⚠️ Confirmar edição da despesa <strong>{d['tipo_despesa']} — {d['descricao_detalhe']}</strong>?</div>",
                            unsafe_allow_html=True,
                        )
                        ce1, ce2, _ = st.columns([1.2, 1.2, 4])
                        if ce1.button("✅ Sim, Editar", key=f"ok_ed_d_{did}", use_container_width=True):
                            st.session_state["edit_desp_id"] = did
                            st.session_state["confirm_edit_desp"] = None
                            st.rerun()
                        if ce2.button("❌ Cancelar", key=f"no_ed_d_{did}", use_container_width=True):
                            st.session_state["confirm_edit_desp"] = None
                            st.rerun()

                    if st.session_state.get("confirm_del_desp") == did:
                        st.markdown(
                            f"<div class='confirm-box-del'>🚨 Tem certeza que deseja EXCLUIR permanentemente a despesa <strong>{d['tipo_despesa']} — {d['descricao_detalhe']}</strong>?</div>",
                            unsafe_allow_html=True,
                        )
                        cd1, cd2, _ = st.columns([1.2, 1.2, 4])
                        if cd1.button("🗑️ Sim, Excluir", key=f"ok_dl_d_{did}", use_container_width=True):
                            with SessionLocal() as db:
                                obj_del = db.query(ViagemDespesa).filter_by(id_despesa=did).first()
                                if obj_del:
                                    db.delete(obj_del)
                                    db.commit()
                            st.session_state["confirm_del_desp"] = None
                            carregar_despesas_viagem.clear()
                            carregar_todas_viagens_consulta.clear()
                            st.rerun()
                        if cd2.button("❌ Cancelar", key=f"no_dl_d_{did}", use_container_width=True):
                            st.session_state["confirm_del_desp"] = None
                            st.rerun()
            else:
                for idx_tmp, d in enumerate(lista_desp):
                    r1, r2, r3, r4, r5, r6, r7 = st.columns([1.3, 2.2, 0.7, 1.0, 1.0, 0.45, 0.45])
                    r1.write(d["tipo_despesa"])
                    r2.write(d["descricao_detalhe"] or "-")
                    r3.markdown(
                        f"<div style='text-align:center;'>{to_float(d['quantidade']):g}</div>", unsafe_allow_html=True
                    )
                    r4.markdown(
                        f"<div style='text-align:right;'>{fmt_brl(d['valor_unitario'])}</div>", unsafe_allow_html=True
                    )
                    r5.markdown(
                        f"<div style='text-align:right;font-weight:700;color:#F34D25;'>{fmt_brl(d['valor_total'])}</div>",
                        unsafe_allow_html=True,
                    )
                    if r6.button("✏️", key=f"ed_tmp_{idx_tmp}", help="Editar"):
                        st.session_state["confirm_edit_desp_tmp"] = idx_tmp
                        st.session_state["confirm_del_desp_tmp"] = None
                        st.rerun()
                    if r7.button("🗑️", key=f"del_tmp_{idx_tmp}", help="Remover"):
                        st.session_state["confirm_del_desp_tmp"] = idx_tmp
                        st.session_state["confirm_edit_desp_tmp"] = None
                        st.rerun()

                    if st.session_state.get("confirm_edit_desp_tmp") == idx_tmp:
                        st.markdown(
                            f"<div class='confirm-box-edit'>⚠️ Confirmar edição da despesa <strong>{d['tipo_despesa']}</strong>?</div>",
                            unsafe_allow_html=True,
                        )
                        ce1, ce2, _ = st.columns([1.2, 1.2, 4])
                        if ce1.button("✅ Sim, Editar", key=f"ok_ed_tmp_{idx_tmp}", use_container_width=True):
                            st.session_state["edit_desp_tmp_idx"] = idx_tmp
                            st.session_state["confirm_edit_desp_tmp"] = None
                            st.rerun()
                        if ce2.button("❌ Cancelar", key=f"no_ed_tmp_{idx_tmp}", use_container_width=True):
                            st.session_state["confirm_edit_desp_tmp"] = None
                            st.rerun()

                    if st.session_state.get("confirm_del_desp_tmp") == idx_tmp:
                        st.markdown(
                            f"<div class='confirm-box-del'>🚨 Confirmar remoção da despesa <strong>{d['tipo_despesa']}</strong>?</div>",
                            unsafe_allow_html=True,
                        )
                        cd1, cd2, _ = st.columns([1.2, 1.2, 4])
                        if cd1.button("🗑️ Sim, Excluir", key=f"ok_dl_tmp_{idx_tmp}", use_container_width=True):
                            lista_desp.pop(idx_tmp)
                            st.session_state["despesas_temp"] = lista_desp
                            st.session_state["edit_desp_tmp_idx"] = None
                            st.session_state["confirm_del_desp_tmp"] = None
                            st.rerun()
                        if cd2.button("❌ Cancelar", key=f"no_dl_tmp_{idx_tmp}", use_container_width=True):
                            st.session_state["confirm_del_desp_tmp"] = None
                            st.rerun()

            st.markdown(
                f"""
                <div style="background:#F1F5F9;color:#0D263C;padding:0.85rem 1rem;border-radius:0 0 0.45rem 0.45rem;font-weight:800;display:flex;justify-content:flex-end;align-items:center;gap:1.5rem;border-top:2px solid #0D263C;">
                    <span>CUSTO TOTAL:</span><span style="font-size:1.25rem;color:#F34D25;font-weight:900;">{fmt_brl(custo_total_desp)}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        render_navegacao_rodape(6, MENU_ITENS)

    # --------------------------------------------------------------------------
    # TAB 8: FECHAMENTO FINAL
    # --------------------------------------------------------------------------
    elif aba_ativa == MENU_ITENS[7]:
        render_cabecalho_aba("fa-solid fa-flag-checkered", "Fechamento Final", 8)

        k1, k2, k3 = st.columns([4, 4, 4])
        km_ini_v = k1.number_input(
            "Odômetro Inicial (KM)",
            value=to_int(get_campo("km_ini", 0)),
            min_value=0,
            step=10,
            key="w_km_ini",
            on_change=sync_campo,
            args=("w_km_ini", "km_ini"),
        )
        km_fin_v = k2.number_input(
            "Odômetro Final (KM)",
            value=to_int(get_campo("km_fin", 0)),
            min_value=0,
            step=10,
            key="w_km_fin",
            on_change=sync_campo,
            args=("w_km_fin", "km_fin"),
        )
        km_rodado = max(0, km_fin_v - km_ini_v) if km_fin_v >= km_ini_v else 0
        k3.text_input("KM Real Rodado", value=f"{km_rodado} km", disabled=True, key=f"prev_km_rodado_{km_rodado}")

        neg = to_float(get_campo("val_negociado", 0.0))
        recebido = to_float(get_campo("val_adiant", 0.0)) + to_float(get_campo("val_saldo", 0.0))
        receita_base = neg if neg > 0 else recebido

        despesas_v = (
            carregar_despesas_viagem(viagem_sel_id) if viagem_sel_id != 0 else st.session_state.get("despesas_temp", [])
        )
        total_despesas = sum(to_float(d["valor_total"]) for d in despesas_v)

        resultado_liq = receita_base - total_despesas
        cor_res = "#FFFFFF" if resultado_liq >= 0 else "#F34D25"

        st.markdown(
            f"""
            <div class="dre-box">
                <div class="dre-header">Resumo Financeiro (DRE) — FAEG</div>
                <div class="dre-row">
                    <span style="color:#E9E9E9;">Receita Total</span>
                    <span style="font-size:1.25rem;font-weight:700;color:#ABCEE1;">{fmt_brl(receita_base)}</span>
                </div>
                <div class="dre-row" style="margin-bottom:1.4rem;">
                    <span style="color:#E9E9E9;">Custos Totais</span>
                    <span style="font-size:1.25rem;font-weight:700;color:#F34D25;">- {fmt_brl(total_despesas)}</span>
                </div>
                <div class="dre-total-row">
                    <span style="font-size:1.05rem;font-weight:700;text-transform:uppercase;letter-spacing:0.04em;">Resultado Líquido</span>
                    <span style="font-size:2.1rem;font-weight:900;color:{cor_res};">{fmt_brl(resultado_liq)}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        render_navegacao_rodape(7, MENU_ITENS)

    # --------------------------------------------------------------------------
    # TAB 9: RELATÓRIOS / EXPORTAR (VIAGEM INDIVIDUAL + BI CONSOLIDADO + BASE COMPLETA)
    # --------------------------------------------------------------------------
    elif aba_ativa == MENU_ITENS[8]:
        render_cabecalho_aba("fa-solid fa-chart-pie", "Relatórios, Métricas e Exportação Geral", 9)

        todas_viagens_rel, todas_desp_rel = carregar_todas_viagens_consulta()

        exp_c1, exp_c2 = st.columns([6.5, 5.5])
        exp_c1.markdown(
            "<div style='font-size:0.84rem;color:#475569;padding-top:0.35rem;'>"
            "Exporte toda a base do sistema (Viagens, Ciclos, Despesas, Motoristas, Veículos, Clientes, Locais e Fornecedores) em planilha única:"
            "</div>",
            unsafe_allow_html=True,
        )
        excel_completo_bytes = gerar_excel_base_completa(
            todas_viagens_rel,
            todas_desp_rel,
            motoristas_db,
            veiculos_db,
            clientes_db,
            locais_db,
            fornecedores_db,
        )
        exp_c2.download_button(
            label="📥 Exportar Base Completa do Sistema (Excel Multi-Abas)",
            data=excel_completo_bytes,
            file_name=f"FAEG_Base_Completa_{date.today().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

        st.markdown("<hr style='margin:0.8rem 0 1.2rem 0;border-color:#E9E9E9;'>", unsafe_allow_html=True)

        tab_rel_ind, tab_rel_geral = st.tabs(
            [f"📄 Relatório da Viagem Ativa ({id_label_ctx})", f"📊 Painel Geral & Métricas ({len(todas_viagens_rel)} viagens)"]
        )

        # --- SUB-ABA 1: RELATÓRIO DA VIAGEM ATIVA ---
        with tab_rel_ind:
            despesas_rel = (
                carregar_despesas_viagem(viagem_sel_id) if viagem_sel_id != 0 else st.session_state.get("despesas_temp", [])
            )
            total_desp_rel = sum(to_float(d["valor_total"]) for d in despesas_rel)
            agrupado = {}
            for d in despesas_rel:
                agrupado[d["tipo_despesa"]] = agrupado.get(d["tipo_despesa"], 0.0) + to_float(d["valor_total"])

            lista_export_desp = [
                {
                    "Tipo": d["tipo_despesa"],
                    "Desc": d["descricao_detalhe"],
                    "Qtd": to_float(d["quantidade"]),
                    "R$ Unit": to_float(d["valor_unitario"]),
                    "R$ Total": to_float(d["valor_total"]),
                }
                for d in despesas_rel
            ]

            neg_rel = to_float(get_campo("val_negociado", 0.0))
            rec_rel = to_float(get_campo("val_adiant", 0.0)) + to_float(get_campo("val_saldo", 0.0))
            receita_rel = neg_rel if neg_rel > 0 else rec_rel
            resultado_rel = receita_rel - total_desp_rel
            saldo_a_receber_rel = max(0.0, neg_rel - rec_rel) if neg_rel > 0 else 0.0

            km_i = to_int(get_campo("km_ini", 0))
            km_f = to_int(get_campo("km_fin", 0))
            km_real_rel = max(0, km_f - km_i) if km_f >= km_i else 0
            custo_km_rel = (total_desp_rel / km_real_rel) if km_real_rel > 0 else 0.0
            receita_km_rel = (receita_rel / km_real_rel) if km_real_rel > 0 else 0.0
            margem_rel = ((resultado_rel / receita_rel) * 100.0) if receita_rel > 0 else 0.0

            tv_rel = get_campo("tipo_viagem", "Individual")
            ciclo_rel = (get_campo("ciclo_nome") or "").strip()
            tipo_viagem_fmt = f"Ciclo ({ciclo_rel})" if (tv_rel == "Ciclo" and ciclo_rel) else "Individual"
            tipo_frete_fmt = get_campo("tipo_frete", "Dedicado")
            origem_frete_fmt = get_campo("forma_contr", "Aplicativo de Fretes")
            r_orig_rel = (get_campo("rota_origem") or "").strip() or "-"
            r_dest_rel = (get_campo("rota_destino") or "").strip() or "-"

            b1, b2, _ = st.columns([1.5, 1.5, 5])
            buffer_xlsx = io.BytesIO()
            df_exp_desp = pd.DataFrame(lista_export_desp)
            df_exp_dre = pd.DataFrame(
                [
                    {
                        "Viagem": id_label_ctx,
                        "Situação": status_ctx,
                        "Tipo de Viagem": tipo_viagem_fmt,
                        "Tipo de Frete": tipo_frete_fmt,
                        "Origem de Frete": origem_frete_fmt,
                        "Cliente": cli_nome_ctx,
                        "Motorista": mot_nome_ctx,
                        "Origem": r_orig_rel,
                        "Destino": r_dest_rel,
                        "Rota": rota_ctx,
                        "Receita Total": receita_rel,
                        "Total Recebido": rec_rel,
                        "Saldo Pendente": saldo_a_receber_rel,
                        "Custos Totais": total_desp_rel,
                        "Resultado Líquido": resultado_rel,
                        "KM Rodado": km_real_rel,
                        "Receita por KM": round(receita_km_rel, 2),
                        "Custo por KM": round(custo_km_rel, 2),
                        "Margem (%)": round(margem_rel, 1),
                    }
                ]
            )
            with pd.ExcelWriter(buffer_xlsx, engine="openpyxl") as writer:
                df_exp_dre.to_excel(writer, sheet_name="DRE_Viagem", index=False)
                df_exp_desp.to_excel(writer, sheet_name="Despesas", index=False)

            b1.download_button(
                label="📥 Excel da Viagem",
                data=buffer_xlsx.getvalue(),
                file_name=f"{id_label_ctx}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

            vei_obj = next((v for v in veiculos_db if v["id_veiculo"] == get_campo("vei_id", 0)), None)
            col_obj = next((l for l in locais_db if l["id_local"] == get_campo("col_id", 0)), None)
            ent_obj = next((l for l in locais_db if l["id_local"] == get_campo("ent_id", 0)), None)
            dt_col_val = get_campo("data_col")
            dt_ent_val = get_campo("data_ent")

            dados_pdf = {
                "codigo": id_label_ctx,
                "status": status_ctx,
                "tipo_viagem": tipo_viagem_fmt,
                "tipo_frete": tipo_frete_fmt,
                "origem_frete": origem_frete_fmt,
                "cliente": cli_nome_ctx,
                "motorista": mot_nome_ctx,
                "veiculo": f"{vei_obj['descricao_marca']} ({vei_obj['placa']})" if vei_obj else "Não selecionado",
                "rota_origem": r_orig_rel,
                "rota_destino": r_dest_rel,
                "rota": rota_ctx,
                "km_rodado": km_real_rel,
                "coleta": f"{col_obj['nome_local']} ({col_obj['cidade']}/{col_obj['uf']})" if col_obj else "-",
                "data_coleta": dt_col_val.strftime("%d/%m/%Y") if dt_col_val else "-",
                "entrega": f"{ent_obj['nome_local']} ({ent_obj['cidade']}/{ent_obj['uf']})" if ent_obj else "-",
                "data_entrega": dt_ent_val.strftime("%d/%m/%Y") if dt_ent_val else "-",
                "nfe": get_campo("nfe") or "-",
                "cte": get_campo("cte") or "-",
                "mdfe": get_campo("mdfe") or "-",
                "ciot": get_campo("ciot") or "-",
                "receita": receita_rel,
                "custos": total_desp_rel,
                "resultado": resultado_rel,
                "margem": margem_rel,
                "custo_km": custo_km_rel,
            }
            pdf_bytes = gerar_pdf_relatorio(dados_pdf, despesas_rel)
            b2.download_button(
                label="📄 PDF da Viagem",
                data=pdf_bytes,
                file_name=f"{id_label_ctx}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

            st.markdown(
                f"""
                <div class="kpi-consulta-grid">
                    <div class="kpi-consulta-card">
                        <div class="kpi-consulta-lbl">Receita / KM</div>
                        <div class="kpi-consulta-val">{fmt_brl(receita_km_rel)}</div>
                    </div>
                    <div class="kpi-consulta-card orange">
                        <div class="kpi-consulta-lbl">Custo / KM</div>
                        <div class="kpi-consulta-val" style="color:#F34D25;">{fmt_brl(custo_km_rel)}</div>
                    </div>
                    <div class="kpi-consulta-card">
                        <div class="kpi-consulta-lbl">Margem Líquida</div>
                        <div class="kpi-consulta-val">{margem_rel:.1f}%</div>
                    </div>
                    <div class="kpi-consulta-card">
                        <div class="kpi-consulta-lbl">Saldo a Receber</div>
                        <div class="kpi-consulta-val">{fmt_brl(saldo_a_receber_rel)}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            g1, g2 = st.columns(2)
            with g1:
                labels_js = list(agrupado.keys()) if agrupado else ["Sem dados"]
                data_js = list(agrupado.values()) if agrupado else [1]

                chart_html = f"""
                <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700&display=swap" rel="stylesheet">
                <div style="background:#FFFFFF;border:1px solid #D6D6D6;border-top:4px solid #0D263C;border-radius:0.55rem;padding:1.2rem;text-align:center;font-family:'Montserrat',sans-serif;">
                    <h3 style="font-size:0.82rem;font-weight:700;color:#0D263C;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:1rem;">
                        Distribuição de Gastos (Viagem Atual)
                    </h3>
                    <div style="height:260px;position:relative;">
                        <canvas id="graficoDespesas"></canvas>
                    </div>
                </div>
                <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
                <script>
                    new Chart(document.getElementById('graficoDespesas').getContext('2d'), {{
                        type: 'doughnut',
                        data: {{
                            labels: {labels_js},
                            datasets: [{{
                                data: {data_js},
                                backgroundColor: ['#0D263C', '#F34D25', '#ABCEE1', '#3B5B78', '#8C8C8C', '#E9E9E9'],
                                borderColor: '#FFFFFF',
                                borderWidth: 2
                            }}]
                        }},
                        options: {{
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {{
                                legend: {{
                                    labels: {{
                                        font: {{ family: 'Montserrat', weight: '600' }},
                                        color: '#0D263C'
                                    }}
                                }}
                            }}
                        }}
                    }});
                </script>
                """
                components.html(chart_html, height=345)

            with g2:
                cor_margem = "#0D263C" if resultado_rel >= 0 else "#F34D25"
                st.markdown(
                    f"""
                    <div style="background:#FFFFFF;border:1px solid #D6D6D6;border-top:4px solid #F34D25;border-radius:0.55rem;padding:1.5rem;height:320px;display:flex;flex-direction:column;justify-content:center;gap:1.1rem;">
                        <div style="font-size:0.82rem;font-weight:700;color:#0D263C;text-transform:uppercase;letter-spacing:0.06em;text-align:center;border-bottom:1px solid #E9E9E9;padding-bottom:0.55rem;">
                            Resumo Executivo da Viagem
                        </div>
                        <div style="background:rgba(171, 206, 225, 0.25);border:1px solid #ABCEE1;border-left:5px solid #0D263C;border-radius:0.45rem;padding:0.95rem 1.2rem;display:flex;justify-content:space-between;align-items:center;">
                            <span style="color:#0D263C;font-weight:700;font-size:0.8rem;text-transform:uppercase;">Receita Negociada</span>
                            <span style="font-size:1.35rem;font-weight:900;color:#0D263C;">{fmt_brl(receita_rel)}</span>
                        </div>
                        <div style="background:#F1F5F9;border:1px solid #CBD5E1;border-left:5px solid #F34D25;border-radius:0.45rem;padding:0.95rem 1.2rem;display:flex;justify-content:space-between;align-items:center;">
                            <span style="color:#0D263C;font-weight:700;font-size:0.8rem;text-transform:uppercase;">Resultado Líquido</span>
                            <span style="font-size:1.35rem;font-weight:900;color:{cor_margem};">{fmt_brl(resultado_rel)}</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # --- SUB-ABA 2: PAINEL GERAL & MÉTRICAS CONSOLIDADAS ---
        with tab_rel_geral:
            if not todas_viagens_rel:
                st.info("Ainda não há viagens registradas no banco de dados. Salve uma viagem ou importe a planilha para visualizar os indicadores consolidados.")
            else:
                fat_total = sum(v["receita_efetiva"] for v in todas_viagens_rel)
                rec_caixa = sum(v["total_recebido"] for v in todas_viagens_rel)
                custo_total = sum(v["total_despesas"] for v in todas_viagens_rel)
                lucro_total = sum(v["resultado_liquido"] for v in todas_viagens_rel)
                km_total = sum(v["km_rodado"] for v in todas_viagens_rel)
                ticket_medio = fat_total / len(todas_viagens_rel)
                margem_media = ((lucro_total / fat_total) * 100.0) if fat_total > 0 else 0.0
                custo_km_geral = (custo_total / km_total) if km_total > 0 else 0.0

                st.markdown(
                    f"""
                    <div class="kpi-consulta-grid">
                        <div class="kpi-consulta-card">
                            <div class="kpi-consulta-lbl">Faturamento Total ({len(todas_viagens_rel)} op.)</div>
                            <div class="kpi-consulta-val">{fmt_brl(fat_total)}</div>
                        </div>
                        <div class="kpi-consulta-card">
                            <div class="kpi-consulta-lbl">Total Recebido em Caixa</div>
                            <div class="kpi-consulta-val">{fmt_brl(rec_caixa)}</div>
                        </div>
                        <div class="kpi-consulta-card orange">
                            <div class="kpi-consulta-lbl">Custos Totais Operacionais</div>
                            <div class="kpi-consulta-val" style="color:#F34D25;">{fmt_brl(custo_total)}</div>
                        </div>
                        <div class="kpi-consulta-card">
                            <div class="kpi-consulta-lbl">Lucro Líquido Consolidado</div>
                            <div class="kpi-consulta-val">{fmt_brl(lucro_total)}</div>
                        </div>
                    </div>
                    <div class="kpi-consulta-grid">
                        <div class="kpi-consulta-card">
                            <div class="kpi-consulta-lbl">Ticket Médio / Viagem</div>
                            <div class="kpi-consulta-val">{fmt_brl(ticket_medio)}</div>
                        </div>
                        <div class="kpi-consulta-card">
                            <div class="kpi-consulta-lbl">Margem Líquida Média</div>
                            <div class="kpi-consulta-val">{margem_media:.1f}%</div>
                        </div>
                        <div class="kpi-consulta-card">
                            <div class="kpi-consulta-lbl">KM Total Rodado</div>
                            <div class="kpi-consulta-val">{km_total:,} km</div>
                        </div>
                        <div class="kpi-consulta-card orange">
                            <div class="kpi-consulta-lbl">Custo Médio / KM</div>
                            <div class="kpi-consulta-val" style="color:#F34D25;">{fmt_brl(custo_km_geral)}</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                cg1, cg2 = st.columns(2)
                with cg1:
                    top_vg = list(reversed(todas_viagens_rel[:10]))
                    lbl_vg = [v["codigo_viagem"] for v in top_vg]
                    rec_vg = [round(v["receita_efetiva"], 2) for v in top_vg]
                    cus_vg = [round(v["total_despesas"], 2) for v in top_vg]
                    luc_vg = [round(v["resultado_liquido"], 2) for v in top_vg]

                    bar_html = f"""
                    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700&display=swap" rel="stylesheet">
                    <div style="background:#FFFFFF;border:1px solid #D6D6D6;border-top:4px solid #0D263C;border-radius:0.55rem;padding:1.2rem;font-family:'Montserrat',sans-serif;">
                        <h3 style="font-size:0.8rem;font-weight:700;color:#0D263C;text-transform:uppercase;text-align:center;margin-bottom:0.8rem;">
                            Receita × Custos × Lucro (Últimas Viagens)
                        </h3>
                        <div style="height:260px;position:relative;">
                            <canvas id="graficoComparativo"></canvas>
                        </div>
                    </div>
                    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
                    <script>
                        new Chart(document.getElementById('graficoComparativo').getContext('2d'), {{
                            type: 'bar',
                            data: {{
                                labels: {lbl_vg},
                                datasets: [
                                    {{ label: 'Receita', data: {rec_vg}, backgroundColor: '#0D263C' }},
                                    {{ label: 'Custos', data: {cus_vg}, backgroundColor: '#F34D25' }},
                                    {{ label: 'Lucro', data: {luc_vg}, backgroundColor: '#ABCEE1' }}
                                ]
                            }},
                            options: {{
                                responsive: true,
                                maintainAspectRatio: false,
                                plugins: {{ legend: {{ labels: {{ font: {{ family: 'Montserrat', weight: '600' }} }} }} }}
                            }}
                        }});
                    </script>
                    """
                    components.html(bar_html, height=340)

                with cg2:
                    gastos_cat_geral = {}
                    for d in todas_desp_rel:
                        cat = d["Tipo Despesa"]
                        gastos_cat_geral[cat] = gastos_cat_geral.get(cat, 0.0) + to_float(d["Valor Total (R$)"])
                    lbl_cat = list(gastos_cat_geral.keys()) if gastos_cat_geral else ["Sem despesas"]
                    val_cat = [round(x, 2) for x in gastos_cat_geral.values()] if gastos_cat_geral else [1]

                    doughnut_geral_html = f"""
                    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700&display=swap" rel="stylesheet">
                    <div style="background:#FFFFFF;border:1px solid #D6D6D6;border-top:4px solid #F34D25;border-radius:0.55rem;padding:1.2rem;font-family:'Montserrat',sans-serif;">
                        <h3 style="font-size:0.8rem;font-weight:700;color:#0D263C;text-transform:uppercase;text-align:center;margin-bottom:0.8rem;">
                            Gastos Consolidados por Categoria
                        </h3>
                        <div style="height:260px;position:relative;">
                            <canvas id="graficoCatGeral"></canvas>
                        </div>
                    </div>
                    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
                    <script>
                        new Chart(document.getElementById('graficoCatGeral').getContext('2d'), {{
                            type: 'doughnut',
                            data: {{
                                labels: {lbl_cat},
                                datasets: [{{
                                    data: {val_cat},
                                    backgroundColor: ['#0D263C', '#F34D25', '#ABCEE1', '#3B5B78', '#8C8C8C', '#64748B', '#1E3A5F'],
                                    borderColor: '#FFFFFF',
                                    borderWidth: 2
                                }}]
                            }},
                            options: {{
                                responsive: true,
                                maintainAspectRatio: false,
                                plugins: {{ legend: {{ labels: {{ font: {{ family: 'Montserrat', weight: '600' }} }} }} }}
                            }}
                        }});
                    </script>
                    """
                    components.html(doughnut_geral_html, height=340)

                st.markdown('<div class="sec-subtitle">Ranking de Rentabilidade por Cliente</div>', unsafe_allow_html=True)
                resumo_cli = {}
                for v in todas_viagens_rel:
                    cl = v["cliente"]
                    if cl not in resumo_cli:
                        resumo_cli[cl] = {"Viagens": 0, "Receita": 0.0, "Custos": 0.0, "Lucro": 0.0}
                    resumo_cli[cl]["Viagens"] += 1
                    resumo_cli[cl]["Receita"] += v["receita_efetiva"]
                    resumo_cli[cl]["Custos"] += v["total_despesas"]
                    resumo_cli[cl]["Lucro"] += v["resultado_liquido"]

                df_rank_cli = pd.DataFrame(
                    [
                        {
                            "Cliente": k,
                            "Qtde Viagens": d["Viagens"],
                            "Receita Total": fmt_brl(d["Receita"]),
                            "Custos Totais": fmt_brl(d["Custos"]),
                            "Resultado Líquido": fmt_brl(d["Lucro"]),
                            "Margem (%)": f"{((d['Lucro'] / d['Receita']) * 100.0 if d['Receita'] > 0 else 0.0):.1f}%",
                        }
                        for k, d in sorted(resumo_cli.items(), key=lambda item: item[1]["Lucro"], reverse=True)
                    ]
                )
                st.dataframe(df_rank_cli, use_container_width=True, hide_index=True)

        render_navegacao_rodape(8, MENU_ITENS)

    # --------------------------------------------------------------------------
    # TAB 10: CONSULTAS GERAIS (PESQUISA GLOBAL, EDIÇÃO E EXCLUSÃO SEGURA)
    # --------------------------------------------------------------------------
    elif aba_ativa == MENU_ITENS[9]:
        render_cabecalho_aba("fa-solid fa-magnifying-glass", "Consultas Gerais — Viagens, Fretes e Ciclos", 10)

        todas_viagens, _ = carregar_todas_viagens_consulta()

        if not todas_viagens:
            st.info(
                "Ainda não existem viagens registradas no banco de dados. "
                "Assim que você salvar sua primeira viagem ou importar a planilha na Etapa 1, os registros aparecerão aqui."
            )

        f_col1, f_col2, f_col3, f_col4 = st.columns([4.2, 2.2, 2.4, 3.2])
        termo_busca = f_col1.text_input(
            "Pesquisar por Código, Cliente, Motorista, Origem, Destino, Ciclo ou NF-e",
            placeholder="Digite para filtrar instantaneamente...",
            key="consulta_termo_busca",
        )
        filtro_tipo_v = f_col2.selectbox(
            "Tipo de Viagem",
            ["Todos", "Individual", "Ciclo"],
            key="consulta_filtro_tipo",
        )
        filtro_status = f_col3.selectbox(
            "Situação",
            ["Todas"] + OPCOES_SITUACAO_OPERACAO,
            key="consulta_filtro_status",
        )
        filtro_origem_f = f_col4.selectbox(
            "Origem de Frete",
            ["Todas"] + OPCOES_ORIGEM_FRETE,
            key="consulta_filtro_origem",
        )

        filtradas = []
        termo_low = (termo_busca or "").strip().lower()
        for item in todas_viagens:
            if filtro_tipo_v != "Todos" and item["tipo_viagem"] != filtro_tipo_v:
                continue
            if filtro_status != "Todas" and item["status"] != filtro_status:
                continue
            if filtro_origem_f != "Todas" and item["origem_frete"] != filtro_origem_f:
                continue
            if termo_low:
                blob = " ".join(
                    [
                        item["codigo_viagem"],
                        item["id_frete"],
                        item["ciclo"],
                        item["cliente"],
                        item["motorista"],
                        item["veiculo"],
                        item["rota_origem"],
                        item["rota_destino"],
                        item["rota"],
                        item["nfe"],
                        item["cte"],
                    ]
                ).lower()
                if termo_low not in blob:
                    continue
            filtradas.append(item)

        tot_receita_f = sum(x["receita_efetiva"] for x in filtradas)
        tot_desp_f = sum(x["total_despesas"] for x in filtradas)
        tot_lucro_f = sum(x["resultado_liquido"] for x in filtradas)

        st.markdown(
            f"""
            <div class="kpi-consulta-grid">
                <div class="kpi-consulta-card">
                    <div class="kpi-consulta-lbl">Operações Encontradas</div>
                    <div class="kpi-consulta-val">{len(filtradas)}</div>
                </div>
                <div class="kpi-consulta-card">
                    <div class="kpi-consulta-lbl">Receita Consolidada</div>
                    <div class="kpi-consulta-val">{fmt_brl(tot_receita_f)}</div>
                </div>
                <div class="kpi-consulta-card orange">
                    <div class="kpi-consulta-lbl">Despesas Consolidadas</div>
                    <div class="kpi-consulta-val" style="color:#F34D25;">{fmt_brl(tot_desp_f)}</div>
                </div>
                <div class="kpi-consulta-card">
                    <div class="kpi-consulta-lbl">Resultado Líquido</div>
                    <div class="kpi-consulta-val">{fmt_brl(tot_lucro_f)}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if filtradas:
            df_tabela = pd.DataFrame(
                [
                    {
                        "Código": x["codigo_viagem"],
                        "Data": x["data_coleta"].strftime("%d/%m/%Y") if x["data_coleta"] else "-",
                        "Situação": x["status"],
                        "Tipo": x["tipo_viagem"],
                        "Ciclo": x["ciclo"],
                        "Cliente": x["cliente"],
                        "Motorista": x["motorista"],
                        "Origem": x["rota_origem"],
                        "Destino": x["rota_destino"],
                        "Receita": fmt_brl(x["receita_efetiva"]),
                        "Despesas": fmt_brl(x["total_despesas"]),
                        "Líquido": fmt_brl(x["resultado_liquido"]),
                    }
                    for x in filtradas
                ]
            )
            st.dataframe(df_tabela, use_container_width=True, hide_index=True)

            st.markdown(
                '<div class="sec-subtitle">Abrir para Edição, Consultar Relatório ou Excluir Registro</div>',
                unsafe_allow_html=True,
            )

            for x in filtradas:
                vid = x["id_viagem"]
                with st.container(border=True):
                    c_info, c_fin, c_act1, c_act2, c_act3 = st.columns([4.4, 2.8, 1.6, 1.6, 1.6])
                    dt_str = x["data_coleta"].strftime("%d/%m/%Y") if x["data_coleta"] else "-"
                    ciclo_badge = f" | Ciclo: <strong>{x['ciclo']}</strong>" if x["tipo_viagem"] == "Ciclo" else ""
                    c_info.markdown(
                        f"<div style='font-size:0.88rem;font-weight:800;color:#0D263C;'>"
                        f"{x['codigo_viagem']} — {x['rota']}</div>"
                        f"<div style='font-size:0.75rem;color:#475569;'>"
                        f"Cliente: <strong>{x['cliente']}</strong> | Mot.: {x['motorista']} | Data: {dt_str}{ciclo_badge}</div>",
                        unsafe_allow_html=True,
                    )
                    cor_liq = "#0D263C" if x["resultado_liquido"] >= 0 else "#F34D25"
                    c_fin.markdown(
                        f"<div style='font-size:0.74rem;color:#475569;'>"
                        f"Situação: <strong>{x['status']}</strong><br>"
                        f"Receita: <strong>{fmt_brl(x['receita_efetiva'])}</strong> | "
                        f"Líquido: <strong style='color:{cor_liq};'>{fmt_brl(x['resultado_liquido'])}</strong></div>",
                        unsafe_allow_html=True,
                    )
                    c_act1.button(
                        "✏️ Editar",
                        key=f"cons_edit_{vid}",
                        use_container_width=True,
                        on_click=_abrir_viagem_para_edicao,
                        args=(vid, "1. Frota FAEG"),
                    )
                    c_act2.button(
                        "📊 Relatório",
                        key=f"cons_rel_{vid}",
                        use_container_width=True,
                        on_click=_abrir_viagem_para_edicao,
                        args=(vid, "9. Relatórios / Exportar"),
                    )
                    if c_act3.button("🗑️ Excluir", key=f"cons_del_{vid}", use_container_width=True):
                        st.session_state["confirm_del_viagem_consulta"] = vid
                        st.rerun()

                    if st.session_state.get("confirm_del_viagem_consulta") == vid:
                        st.markdown(
                            f"<div class='confirm-box-del'>🚨 ATENÇÃO: Tem certeza que deseja EXCLUIR permanentemente a viagem <strong>{x['codigo_viagem']} ({x['rota']})</strong> e todas as suas despesas vinculadas?</div>",
                            unsafe_allow_html=True,
                        )
                        cd1, cd2, _ = st.columns([1.4, 1.4, 4])
                        if cd1.button("🗑️ Sim, Excluir Viagem", key=f"ok_del_vg_{vid}", use_container_width=True):
                            with SessionLocal() as db:
                                vg_del = db.query(Viagem).filter_by(id_viagem=vid).first()
                                if vg_del:
                                    ciclo_pai = vg_del.ciclo
                                    db.delete(vg_del)
                                    db.flush()
                                    if ciclo_pai and not ciclo_pai.viagens:
                                        db.delete(ciclo_pai)
                                    db.commit()
                            if st.session_state.get("viagem_ativa_id") == vid:
                                st.session_state["viagem_ativa_id"] = 0
                                st.session_state["loaded_viagem_id"] = None
                            st.session_state["confirm_del_viagem_consulta"] = None
                            carregar_listas_base.clear()
                            carregar_todas_viagens_consulta.clear()
                            carregar_despesas_viagem.clear()
                            st.toast(f"Viagem {x['codigo_viagem']} excluída!", icon="🗑️")
                            st.rerun()
                        if cd2.button("❌ Cancelar", key=f"no_del_vg_{vid}", use_container_width=True):
                            st.session_state["confirm_del_viagem_consulta"] = None
                            st.rerun()

        render_navegacao_rodape(9, MENU_ITENS)

    # --------------------------------------------------------------------------
    # TAB 11: CADASTROS GERAIS (EDITAR E EXCLUIR COM CONFIRMAÇÃO DUPLA)
    # --------------------------------------------------------------------------
    elif aba_ativa == MENU_ITENS[10]:
        render_cabecalho_aba("fa-solid fa-folder-plus", "Cadastros Gerais (Base de Dados FAEG)", 11)

        cli_map_cad = {c["id_cliente"]: c for c in clientes_db}
        r1_c1, r1_c2 = st.columns(2)

        # ----------------------------------------------------------------------
        # 1. MOTORISTAS
        # ----------------------------------------------------------------------
        with r1_c1:
            with st.container(border=True):
                st.markdown('<div class="card-faeg-azul"></div>', unsafe_allow_html=True)
                st.markdown(
                    "<div style='font-size:0.85rem;font-weight:800;color:#0D263C;text-transform:uppercase;margin-bottom:0.8rem;'>"
                    "<i class='fa-solid fa-id-card' style='color:#F34D25;margin-right:0.4rem;'></i> Motoristas</div>",
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
                    m_nome = st.text_input(
                        "Nome Completo *",
                        placeholder="Ex: Genario Pedro",
                        value=mot_edit_obj["nome_completo"] if mot_edit_obj else "",
                    )
                    mc1, mc2 = st.columns(2)
                    m_cpf = mc1.text_input(
                        "CPF *",
                        placeholder="000.000.000-00",
                        value=mot_edit_obj["cpf"] if mot_edit_obj else "",
                    )
                    m_tel = mc2.text_input(
                        "Telefone / WhatsApp",
                        placeholder="(11) 99999-9999",
                        value=(mot_edit_obj["telefone_contato"] or "") if mot_edit_obj else "",
                    )
                    mc3, mc4, mc5 = st.columns([2, 1, 1.5])
                    m_cnh = mc3.text_input(
                        "Nº CNH *",
                        placeholder="00000000000",
                        value=mot_edit_obj["cnh_numero"] if mot_edit_obj else "",
                    )
                    cats_cnh = ["C", "D", "E", "AE", "B"]
                    idx_cat = (
                        cats_cnh.index(mot_edit_obj["cnh_categoria"])
                        if mot_edit_obj and mot_edit_obj["cnh_categoria"] in cats_cnh
                        else 2
                    )
                    m_cat = mc4.selectbox("Categoria", cats_cnh, index=idx_cat)
                    val_cnh_init = (
                        mot_edit_obj["cnh_validade"]
                        if (mot_edit_obj and mot_edit_obj.get("cnh_validade"))
                        else date.today()
                    )
                    m_val_cnh = mc5.date_input("Validade CNH", value=val_cnh_init, format="DD/MM/YYYY")

                    vinc_ops = ["Frota Própria (CLT)", "Agregado", "Terceiro / Autônomo"]
                    idx_vinc = (
                        vinc_ops.index(mot_edit_obj["vinculo"])
                        if mot_edit_obj and mot_edit_obj["vinculo"] in vinc_ops
                        else 0
                    )
                    m_vinc = st.selectbox("Vínculo", vinc_ops, index=idx_vinc)

                    btn_txt_mot = "Atualizar Motorista" if mot_edit_obj else "Cadastrar Motorista"
                    if st.form_submit_button(btn_txt_mot, use_container_width=True):
                        if not m_nome or not m_cpf or not m_cnh:
                            st.error("Preencha Nome, CPF e Nº da CNH.")
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
                                st.error("CPF ou CNH já cadastrado no sistema.")

                if mot_edit_obj:
                    if st.button("Cancelar Edição de Motorista", key="cancel_ed_mot", use_container_width=True):
                        st.session_state["edit_mot_id"] = None
                        st.rerun()

                if motoristas_db:
                    with st.expander(f"📋 Gerenciar Motoristas ({len(motoristas_db)})", expanded=False):
                        for m in motoristas_db:
                            mid = m["id_motorista"]
                            lm1, lm2, lm3 = st.columns([5.5, 0.8, 0.8])
                            lm1.markdown(
                                f"**{m['nome_completo']}** <span style='color:#64748B;font-size:0.78rem;'>| CNH: {m['cnh_numero']} ({m['cnh_categoria']})</span>",
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
                                        st.error("Não é possível excluir: motorista já possui viagens registradas.")
                                if b_no.button("❌ Cancelar", key=f"no_dl_m_{mid}", use_container_width=True):
                                    st.session_state["confirm_dl_mot"] = None
                                    st.rerun()

        # ----------------------------------------------------------------------
        # 2. VEÍCULOS
        # ----------------------------------------------------------------------
        with r1_c2:
            with st.container(border=True):
                st.markdown('<div class="card-faeg-laranja"></div>', unsafe_allow_html=True)
                st.markdown(
                    "<div style='font-size:0.85rem;font-weight:800;color:#0D263C;text-transform:uppercase;margin-bottom:0.8rem;'>"
                    "<i class='fa-solid fa-truck-front' style='color:#F34D25;margin-right:0.4rem;'></i> Veículos da Frota</div>",
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
                    v_marca = st.text_input(
                        "Modelo / Descrição *",
                        placeholder="Ex: Peugeot Expert / VW Constellation",
                        value=vei_edit_obj["descricao_marca"] if vei_edit_obj else "",
                    )
                    vc1, vc2, vc3 = st.columns([2, 2, 1.5])
                    v_placa = vc1.text_input(
                        "Placa *",
                        placeholder="ABC1D23",
                        value=vei_edit_obj["placa"] if vei_edit_obj else "",
                    )
                    tipos_v = ["VUC / Utilitário", "3/4", "Toco", "Truck", "Carreta", "Bitrem"]
                    idx_tv = (
                        tipos_v.index(vei_edit_obj["tipo_veiculo"])
                        if vei_edit_obj and vei_edit_obj["tipo_veiculo"] in tipos_v
                        else 0
                    )
                    v_tipo = vc2.selectbox("Tipo Veículo", tipos_v, index=idx_tv)
                    v_ano = vc3.number_input(
                        "Ano",
                        min_value=1990,
                        max_value=2030,
                        value=to_int(vei_edit_obj["ano_fabricacao"], 2024) if vei_edit_obj else 2024,
                    )
                    vc4, vc5, vc6 = st.columns(3)
                    v_renavam = vc4.text_input(
                        "RENAVAM",
                        placeholder="Opcional",
                        value=(vei_edit_obj["renavam"] or "") if vei_edit_obj else "",
                    )
                    v_cap_kg = vc5.number_input(
                        "Cap. Peso (KG)",
                        min_value=0.0,
                        step=100.0,
                        value=to_float(vei_edit_obj["capacidade_carga_kg"], 1500.0) if vei_edit_obj else 1500.0,
                    )
                    v_cap_m3 = vc6.number_input(
                        "Cap. Vol. (m³)",
                        min_value=0.0,
                        step=1.0,
                        value=to_float(vei_edit_obj["capacidade_volume_m3"], 6.0) if vei_edit_obj else 6.0,
                    )

                    btn_txt_vei = "Atualizar Veículo" if vei_edit_obj else "Cadastrar Veículo"
                    if st.form_submit_button(btn_txt_vei, use_container_width=True):
                        if not v_marca or not v_placa:
                            st.error("Preencha Modelo e Placa.")
                        else:
                            try:
                                with SessionLocal() as db:
                                    if vei_edit_obj:
                                        obj_v = db.query(Veiculo).filter_by(id_veiculo=edit_vei_id).first()
                                        if obj_v:
                                            obj_v.descricao_marca = v_marca.strip()
                                            obj_v.placa = v_placa.strip().upper()
                                            obj_v.tipo_veiculo = v_tipo
                                            obj_v.ano_fabricacao = v_ano
                                            obj_v.renavam = v_renavam.strip() if v_renavam.strip() else None
                                            obj_v.capacidade_carga_kg = v_cap_kg
                                            obj_v.capacidade_volume_m3 = v_cap_m3
                                        st.session_state["edit_vei_id"] = None
                                    else:
                                        db.add(
                                            Veiculo(
                                                descricao_marca=v_marca.strip(),
                                                placa=v_placa.strip().upper(),
                                                tipo_veiculo=v_tipo,
                                                ano_fabricacao=v_ano,
                                                renavam=v_renavam.strip() if v_renavam.strip() else None,
                                                capacidade_carga_kg=v_cap_kg,
                                                capacidade_volume_m3=v_cap_m3,
                                            )
                                        )
                                    db.commit()
                                carregar_listas_base.clear()
                                st.toast("Veículo salvo com sucesso!", icon="✅")
                                st.rerun()
                            except IntegrityError:
                                st.error("Placa ou RENAVAM já cadastrado no sistema.")

                if vei_edit_obj:
                    if st.button("Cancelar Edição de Veículo", key="cancel_ed_vei", use_container_width=True):
                        st.session_state["edit_vei_id"] = None
                        st.rerun()

                if veiculos_db:
                    with st.expander(f"📋 Gerenciar Veículos ({len(veiculos_db)})", expanded=False):
                        for v in veiculos_db:
                            vid = v["id_veiculo"]
                            lv1, lv2, lv3 = st.columns([5.5, 0.8, 0.8])
                            lv1.markdown(
                                f"**{v['descricao_marca']}** <span style='color:#64748B;font-size:0.78rem;'>| Placa: {v['placa']} ({v['tipo_veiculo']})</span>",
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
                                        st.error("Não é possível excluir: veículo já está vinculado a viagens.")
                                if b_no.button("❌ Cancelar", key=f"no_dl_v_{vid}", use_container_width=True):
                                    st.session_state["confirm_dl_vei"] = None
                                    st.rerun()

        st.markdown("<div style='height: 0.7rem;'></div>", unsafe_allow_html=True)
        r2_c1, r2_c2 = st.columns(2)

        # ----------------------------------------------------------------------
        # 3. CLIENTES (COM NOME FANTASIA, ENDEREÇO E OPÇÃO DE GERAR LOCAL DE COLETA)
        # ----------------------------------------------------------------------
        with r2_c1:
            with st.container(border=True):
                st.markdown('<div class="card-faeg-laranja"></div>', unsafe_allow_html=True)
                st.markdown(
                    "<div style='font-size:0.85rem;font-weight:800;color:#0D263C;text-transform:uppercase;margin-bottom:0.8rem;'>"
                    "<i class='fa-solid fa-building-user' style='color:#F34D25;margin-right:0.4rem;'></i> Clientes</div>",
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
                    cl_n1, cl_n2 = st.columns(2)
                    c_razao = cl_n1.text_input(
                        "Razão Social *",
                        placeholder="Ex: Dunlop Pneus Ltda",
                        value=cli_edit_obj["razao_social"] if cli_edit_obj else "",
                    )
                    c_fantasia = cl_n2.text_input(
                        "Nome Fantasia / Filial",
                        placeholder="Ex: Dunlop CD Guarulhos",
                        value=(cli_edit_obj.get("nome_fantasia") or "") if cli_edit_obj else "",
                    )
                    clc1, clc2 = st.columns(2)
                    c_cnpj = clc1.text_input(
                        "CNPJ / CPF *",
                        placeholder="00.000.000/0001-00",
                        value=cli_edit_obj["cnpj_cpf"] if cli_edit_obj else "",
                    )
                    c_ie = clc2.text_input(
                        "Inscrição Estadual",
                        placeholder="Opcional",
                        value=(cli_edit_obj["inscricao_estadual"] or "") if cli_edit_obj else "",
                    )
                    clc3, clc4, clc5 = st.columns([2, 2, 1.3])
                    c_resp = clc3.text_input(
                        "Responsável",
                        placeholder="Ex: Robson",
                        value=(cli_edit_obj["responsavel_comercial"] or "") if cli_edit_obj else "",
                    )
                    c_tel = clc4.text_input(
                        "Telefone",
                        placeholder="(11) 3333-4444",
                        value=(cli_edit_obj["telefone_comercial"] or "") if cli_edit_obj else "",
                    )
                    c_prazo = clc5.number_input(
                        "Prazo (Dias)",
                        min_value=0,
                        max_value=180,
                        value=to_int(cli_edit_obj["prazo_pagamento_dias"], 30) if cli_edit_obj else 30,
                    )
                    c_email = st.text_input(
                        "E-mail Financeiro",
                        placeholder="financeiro@empresa.com.br",
                        value=(cli_edit_obj["email_financeiro"] or "") if cli_edit_obj else "",
                    )

                    ce1, ce2, ce3, ce4 = st.columns([1.8, 4.8, 2.4, 1.0])
                    c_cep = ce1.text_input(
                        "CEP",
                        placeholder="00000-000",
                        value=(cli_edit_obj.get("cep") or "") if cli_edit_obj else "",
                    )
                    c_end = ce2.text_input(
                        "Endereço / Logradouro",
                        placeholder="Rua, Número, Bairro",
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

                    criar_local_auto = st.checkbox(
                        "Cadastrar / sincronizar automaticamente este endereço nos Locais de Coleta/Entrega",
                        value=True,
                    )

                    btn_txt_cli = "Atualizar Cliente" if cli_edit_obj else "Cadastrar Cliente"
                    if st.form_submit_button(btn_txt_cli, use_container_width=True):
                        if not c_razao or not c_cnpj:
                            st.error("Preencha Razão Social e CNPJ/CPF.")
                        else:
                            try:
                                with SessionLocal() as db:
                                    if cli_edit_obj:
                                        obj_c = db.query(Cliente).filter_by(id_cliente=edit_cli_id).first()
                                        if obj_c:
                                            obj_c.razao_social = c_razao.strip()
                                            obj_c.nome_fantasia = c_fantasia.strip() if c_fantasia.strip() else None
                                            obj_c.cnpj_cpf = c_cnpj.strip()
                                            obj_c.inscricao_estadual = c_ie.strip()
                                            obj_c.responsavel_comercial = c_resp.strip()
                                            obj_c.telefone_comercial = c_tel.strip()
                                            obj_c.prazo_pagamento_dias = c_prazo
                                            obj_c.email_financeiro = c_email.strip()
                                            obj_c.cep = c_cep.strip()
                                            obj_c.endereco_completo = c_end.strip()
                                            obj_c.cidade = c_cid.strip()
                                            obj_c.uf = c_uf.strip().upper()
                                            cid_ref = obj_c.id_cliente
                                        st.session_state["edit_cli_id"] = None
                                    else:
                                        novo_cli = Cliente(
                                            razao_social=c_razao.strip(),
                                            nome_fantasia=c_fantasia.strip() if c_fantasia.strip() else None,
                                            cnpj_cpf=c_cnpj.strip(),
                                            inscricao_estadual=c_ie.strip(),
                                            responsavel_comercial=c_resp.strip(),
                                            telefone_comercial=c_tel.strip(),
                                            prazo_pagamento_dias=c_prazo,
                                            email_financeiro=c_email.strip(),
                                            cep=c_cep.strip(),
                                            endereco_completo=c_end.strip(),
                                            cidade=c_cid.strip(),
                                            uf=c_uf.strip().upper(),
                                        )
                                        db.add(novo_cli)
                                        db.flush()
                                        cid_ref = novo_cli.id_cliente

                                    if criar_local_auto and (c_end.strip() or c_cid.strip()):
                                        nome_loc_cli = (
                                            f"{c_razao.strip()} ({c_fantasia.strip()})"
                                            if c_fantasia.strip()
                                            else c_razao.strip()
                                        )
                                        loc_vinculado = db.query(Local).filter_by(id_cliente=cid_ref).first()
                                        if loc_vinculado:
                                            loc_vinculado.nome_local = nome_loc_cli
                                            loc_vinculado.cep = c_cep.strip()
                                            loc_vinculado.endereco_completo = c_end.strip()
                                            loc_vinculado.cidade = c_cid.strip()
                                            loc_vinculado.uf = c_uf.strip().upper()
                                            loc_vinculado.contato_portaria = (
                                                f"{c_resp.strip()} {c_tel.strip()}".strip()
                                            )
                                        else:
                                            db.add(
                                                Local(
                                                    id_cliente=cid_ref,
                                                    nome_local=nome_loc_cli,
                                                    tipo_instalacao="CD / Armazém",
                                                    cep=c_cep.strip(),
                                                    endereco_completo=c_end.strip(),
                                                    cidade=c_cid.strip(),
                                                    uf=c_uf.strip().upper(),
                                                    contato_portaria=f"{c_resp.strip()} {c_tel.strip()}".strip(),
                                                    restricao_horario="Não há restrição",
                                                )
                                            )

                                    db.commit()
                                carregar_listas_base.clear()
                                st.toast("Cliente salvo com sucesso!", icon="✅")
                                st.rerun()
                            except IntegrityError:
                                st.error("CNPJ/CPF já cadastrado no sistema.")

                if cli_edit_obj:
                    if st.button("Cancelar Edição de Cliente", key="cancel_ed_cli", use_container_width=True):
                        st.session_state["edit_cli_id"] = None
                        st.rerun()

                if clientes_db:
                    with st.expander(f"📋 Gerenciar Clientes ({len(clientes_db)})", expanded=False):
                        for c in clientes_db:
                            cid = c["id_cliente"]
                            lc1, lc2, lc3 = st.columns([5.5, 0.8, 0.8])
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
        # 4. LOCAIS DE COLETA E ENTREGA
        # ----------------------------------------------------------------------
        with r2_c2:
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
                rest_atual = (loc_edit_obj.get("restricao_horario") or "Não há restrição") if loc_edit_obj else "Não há restrição"
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
                    with st.expander(f"📋 Gerenciar Locais ({len(locais_db)})", expanded=False):
                        for l in locais_db:
                            lid = l["id_local"]
                            ll_1, ll_2, ll_3 = st.columns([5.5, 0.8, 0.8])
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

        st.markdown("<div style='height: 0.7rem;'></div>", unsafe_allow_html=True)
        r3_c1, _ = st.columns(2)

        # ----------------------------------------------------------------------
        # 5. FORNECEDORES E POSTOS
        # ----------------------------------------------------------------------
        with r3_c1:
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
                    with st.expander(f"📋 Gerenciar Fornecedores ({len(fornecedores_db)})", expanded=False):
                        for f in fornecedores_db:
                            fid = f["id_fornecedor"]
                            lf1, lf2, lf3 = st.columns([5.5, 0.8, 0.8])
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

                            