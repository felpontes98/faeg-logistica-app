"""Operações compartilhadas entre as etapas do Sistema Web FAEG.

Reúne consultas, validações, callbacks Streamlit e rotinas de persistência.
"""

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
from database.saidas_operacionais import consultar_todas_saidas, resumo_saidas
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
# FUNÇÕES AUXILIARES, CÁLCULOS AUTOMÁTICOS E PERSISTÊNCIA ENTRE ABAS
# ==============================================================================
def to_float(val, default=0.0):
    return float(val) if val is not None else float(default)


def to_int(val, default=0):
    return int(val) if val is not None else int(default)


def fmt_brl(val):
    v = to_float(val, 0.0)
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def situacao_financeira_por_recebimentos(valor_negociado, total_recebido):
    """Estado visual do pagamento; não altera a situação operacional nem grava no banco."""
    negociado = round(max(0.0, to_float(valor_negociado)), 2)
    recebido = round(max(0.0, to_float(total_recebido)), 2)
    if recebido <= 0:
        return None
    if negociado <= 0:
        return "Recebimento a Conferir"
    if recebido >= negociado:
        return "Pagamento Quitado"
    return "Recebimento Parcial"


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


_WIDGETS_PREVISAO_FINANCEIRA = {
    "w_val_negociado": "valor_negociado",
    "w_perc_adiant": "perc_adiant",
    "w_val_adiant": "valor_adiant",
    "w_perc_saldo": "perc_saldo",
    "w_val_saldo": "valor_saldo",
}


def inicializar_widgets_previsao_financeira():
    """Ao abrir a Etapa 4, recupera os valores da viagem sem sobrescrever edições."""
    for chave_widget, chave_campo in _WIDGETS_PREVISAO_FINANCEIRA.items():
        if chave_widget not in st.session_state:
            st.session_state[chave_widget] = to_float(get_campo(chave_campo, 0.0))


def sincronizar_widgets_previsao_financeira():
    """Atualiza os campos visíveis antes do rerun do Streamlit, inclusive os correlatos."""
    for chave_widget, chave_campo in _WIDGETS_PREVISAO_FINANCEIRA.items():
        st.session_state[chave_widget] = to_float(get_campo(chave_campo, 0.0))


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
        sincronizar_widgets_previsao_financeira()


def on_perc_adiant_change():
    sync_campo("w_perc_adiant", "perc_adiant")
    neg = to_float(get_campo("valor_negociado", 0.0))
    p_adi = to_float(get_campo("perc_adiant", 0.0))
    if neg > 0:
        st.session_state["form_data"]["valor_adiant"] = round(neg * (p_adi / 100.0), 2)
        if 0 <= p_adi <= 100:
            p_sal = round(100.0 - p_adi, 2)
            st.session_state["form_data"]["perc_saldo"] = p_sal
            st.session_state["form_data"]["valor_saldo"] = round(neg - st.session_state["form_data"]["valor_adiant"], 2)
        sincronizar_widgets_previsao_financeira()


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
        sincronizar_widgets_previsao_financeira()


def on_perc_saldo_change():
    sync_campo("w_perc_saldo", "perc_saldo")
    neg = to_float(get_campo("valor_negociado", 0.0))
    p_sal = to_float(get_campo("perc_saldo", 0.0))
    if neg > 0:
        st.session_state["form_data"]["valor_saldo"] = round(neg * (p_sal / 100.0), 2)
        if 0 <= p_sal <= 100:
            p_adi = round(100.0 - p_sal, 2)
            st.session_state["form_data"]["perc_adiant"] = p_adi
            st.session_state["form_data"]["valor_adiant"] = round(neg - st.session_state["form_data"]["valor_saldo"], 2)
        sincronizar_widgets_previsao_financeira()


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
        sincronizar_widgets_previsao_financeira()


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

# ==============================================================================
# NAVEGAÇÃO SEGURA VIA CALLBACK E ESTADO DA VIAGEM
# ==============================================================================
def _mudar_aba_callback(nova_aba):
    st.session_state["menu_operacional_radio"] = nova_aba


def _abrir_viagem_para_edicao(id_v, destino_aba):
    st.session_state["viagem_ativa_id"] = id_v
    st.session_state["loaded_viagem_id"] = None
    st.session_state["rascunho_ativo_id"] = None
    st.session_state["saidas_provisorias"] = []
    st.session_state["menu_operacional_radio"] = destino_aba


def _iniciar_nova_viagem():
    st.session_state["viagem_ativa_id"] = 0
    st.session_state["loaded_viagem_id"] = None
    st.session_state["despesas_temp"] = []
    st.session_state["saidas_provisorias"] = []
    st.session_state["rascunho_ativo_id"] = None
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


def montar_previa_financeira_ciclo(id_viagem_atual, despesas_frete_atual, clientes_db=None):
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

    clientes_db = clientes_db if clientes_db is not None else carregar_listas_base()[2]
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
            "Para concluir o cadastro, selecione obrigatoriamente: Motorista (1), Veículo (1), "
            "Cliente (3), Local de Coleta (5) e Local de Entrega (6). "
            "Se ainda não tiver essas informações, clique em Salvar rascunho."
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
                    if dt.get("destino_temp") == "ciclo":
                        desp_ciclo = CicloDespesa(
                            id_ciclo=ciclo.id_ciclo,
                            id_fornecedor=dt.get("id_fornecedor") or None,
                            tipo_despesa=dt["tipo_despesa"],
                            descricao_detalhe=dt["descricao_detalhe"],
                            quantidade=dt["quantidade"],
                            valor_unitario=dt["valor_unitario"],
                            valor_total=dt["valor_total"],
                            data_despesa=dt.get("data_despesa") or date.today(),
                        )
                        session.add(desp_ciclo)
                        session.flush()
                        if dt["tipo_despesa"] in {"Posto de Combustível", "Abast. ARLA"}:
                            dados_abast_temp = dict(dt)
                            dados_abast_temp["id_veiculo_abast"] = dt.get("id_veiculo_abast") or vg.id_veiculo
                            registrar_abastecimento_do_lancamento(
                                session, dados_abast_temp, "id_despesa_ciclo", desp_ciclo.id_despesa_ciclo,
                            )
                        continue
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
                # Saídas preparadas antes do primeiro salvamento passam a integrar
                # a operação na MESMA transação do frete, sem duplicidade.
                from database.rascunhos import publicar_saidas_rascunho
                from database.models import RascunhoViagem
                publicar_saidas_rascunho(
                    session, ciclo.id_ciclo, st.session_state.get("saidas_provisorias", [])
                )
                rascunho_id = st.session_state.get("rascunho_ativo_id")
                if rascunho_id:
                    salvo = session.get(RascunhoViagem, int(rascunho_id))
                    if salvo is not None:
                        session.delete(salvo)
                session.commit()
                st.session_state["rascunho_ativo_id"] = None
                st.session_state["saidas_provisorias"] = []
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
