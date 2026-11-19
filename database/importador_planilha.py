from datetime import date, datetime, time
from decimal import Decimal
import re
import pandas as pd

from database.models import (
    CicloFinanceiro,
    CicloOperacional,
    Cliente,
    Local,
    Motorista,
    Veiculo,
    Viagem,
    ViagemDespesa,
    gerar_proximo_codigo_viagem,
    separar_rota,
)


# ==============================================================================
# CONVERSORES SEGUROS (NÚMEROS, PERCENTUAIS, DATAS E HORÁRIOS)
# ==============================================================================


def _limpar_texto(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip()
    if s.lower() in {"nan", "none", "nat", "null", "-"}:
        return ""
    return s


def _parse_float(val, default: float = 0.0) -> float:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    if isinstance(val, (int, float, Decimal)):
        f = float(val)
        return default if pd.isna(f) else f
    s = str(val).strip()
    if not s or s.lower() in {"nan", "none", "-", "r$", "r$ -"}:
        return default
    s = re.sub(r"[R$\s%]", "", s)
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return default


def _parse_int(val, default: int = 0) -> int:
    return int(round(_parse_float(val, float(default))))


def _parse_percent(val, default: float = 0.0) -> float:
    raw_str = str(val) if val is not None else ""
    num = _parse_float(val, default)
    if "%" not in raw_str and 0 < num <= 1.0:
        return round(num * 100.0, 2)
    return round(num, 2)


def _parse_date(val) -> date | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, pd.Timestamp):
        return None if pd.isna(val) else val.date()
    s = _limpar_texto(val)
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s[:19], fmt).date()
        except ValueError:
            continue
    dt = pd.to_datetime(s, dayfirst=True, errors="coerce")
    return None if pd.isna(dt) else dt.date()


def _parse_time(val) -> time | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, time):
        return val.replace(microsecond=0)
    if isinstance(val, datetime):
        return val.time().replace(microsecond=0)
    if isinstance(val, pd.Timestamp):
        return None if pd.isna(val) else val.time().replace(microsecond=0)
    s = _limpar_texto(val)
    if not s:
        return None
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(s[:8], fmt).time()
        except ValueError:
            continue
    return None


def _normalizar_placa(placa: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", placa.upper())


# ==============================================================================
# LEITURA E MAPEAMENTO DAS COLUNAS DA PLANILHA FAEG (95 COLUNAS)
# ==============================================================================


def listar_abas_planilha(arquivo_bytes, nome_arquivo: str) -> list[str]:
    if nome_arquivo.lower().endswith(".csv"):
        return ["CSV"]
    xls = pd.ExcelFile(arquivo_bytes)
    return list(xls.sheet_names)


def _detectar_linha_cabecalho(df_raw: pd.DataFrame) -> int:
    max_scan = min(25, len(df_raw))
    for idx in range(max_scan):
        valores = [_limpar_texto(v).lower() for v in df_raw.iloc[idx].values]
        if "placa" in valores and "motorista" in valores:
            return idx
        if "origem" in valores and "destino" in valores:
            return idx
    return 0


def _mapear_linha_padrao_faeg(row_vals: list) -> dict:
    """Mapeia os 10 blocos exatos da planilha FAEG – Controle Operacional de Viagens."""

    def col(i):
        return row_vals[i] if i < len(row_vals) else None

    rota_bruta = _limpar_texto(col(9))
    origem, destino = separar_rota(rota_bruta)

    # Coleta (Cols 39..50)
    coleta_end = _limpar_texto(col(39))
    coleta_cep = _limpar_texto(col(40))
    coleta_bairro = _limpar_texto(col(41))
    coleta_cidade = _limpar_texto(col(42))
    coleta_uf = _limpar_texto(col(43)).upper()[:2]
    coleta_local = _limpar_texto(col(44))

    # Entrega (Cols 52..64)
    entrega_end = _limpar_texto(col(52))
    entrega_cep = _limpar_texto(col(53))
    entrega_bairro = _limpar_texto(col(54))
    entrega_cidade = _limpar_texto(col(55))
    entrega_uf = _limpar_texto(col(56)).upper()[:2]
    entrega_local = _limpar_texto(col(57))

    # Fallback de Origem e Destino pelos dados de Coleta e Entrega caso Rota esteja vazia
    if not origem and coleta_cidade:
        origem = f"{coleta_cidade}/{coleta_uf}" if coleta_uf else coleta_cidade
    if not destino and entrega_cidade:
        destino = f"{entrega_cidade}/{entrega_uf}" if entrega_uf else entrega_cidade

    # Valores Financeiros
    val_divulgado = _parse_float(col(26))
    val_negociado = _parse_float(col(27))
    perc_adiant = _parse_percent(col(28))
    perc_saldo = _parse_percent(col(29))
    val_adiant_rec = _parse_float(col(34))
    val_saldo_rec = _parse_float(col(36))
    val_total_rec = _parse_float(col(37))
    val_total_geral = _parse_float(col(92))

    if val_negociado == 0.0:
        if val_total_geral > 0:
            val_negociado = val_total_geral
        elif val_total_rec > 0:
            val_negociado = val_total_rec
        elif (val_adiant_rec + val_saldo_rec) > 0:
            val_negociado = round(val_adiant_rec + val_saldo_rec, 2)

    # Abastecimento 01 (Cols 66..72)
    ab1_km = _limpar_texto(col(66))
    ab1_l_diesel = _parse_float(col(67))
    ab1_p_diesel = _parse_float(col(68))
    ab1_l_arla = _parse_float(col(69))
    ab1_p_arla = _parse_float(col(70))
    ab1_v_diesel = _parse_float(col(71))
    ab1_v_arla = _parse_float(col(72))
    if ab1_v_diesel == 0.0 and ab1_l_diesel > 0 and ab1_p_diesel > 0:
        ab1_v_diesel = round(ab1_l_diesel * ab1_p_diesel, 2)
    if ab1_v_arla == 0.0 and ab1_l_arla > 0 and ab1_p_arla > 0:
        ab1_v_arla = round(ab1_l_arla * ab1_p_arla, 2)

    # Abastecimento 02 (Cols 73..79)
    ab2_km = _limpar_texto(col(73))
    ab2_l_diesel = _parse_float(col(74))
    ab2_p_diesel = _parse_float(col(75))
    ab2_l_arla = _parse_float(col(76))
    ab2_p_arla = _parse_float(col(77))
    ab2_v_diesel = _parse_float(col(78))
    ab2_v_arla = _parse_float(col(79))
    if ab2_v_diesel == 0.0 and ab2_l_diesel > 0 and ab2_p_diesel > 0:
        ab2_v_diesel = round(ab2_l_diesel * ab2_p_diesel, 2)
    if ab2_v_arla == 0.0 and ab2_l_arla > 0 and ab2_p_arla > 0:
        ab2_v_arla = round(ab2_l_arla * ab2_p_arla, 2)

    # Outras Despesas e Fechamento (Cols 80..94)
    combustivel_total = _parse_float(col(80))
    pedagio = _parse_float(col(81))
    alimentacao = _parse_float(col(82))
    hospedagem = _parse_float(col(83))
    manutencao = _parse_float(col(84))
    outras_despesas = _parse_float(col(85))
    total_despesas_planilha = _parse_float(col(86))

    km_ini = _parse_int(col(88))
    km_fin = _parse_int(col(89))
    km_real = _parse_int(col(90))
    if km_real == 0 and km_fin > km_ini > 0:
        km_real = km_fin - km_ini

    status_raw = _limpar_texto(col(91)) or "Concluída"
    resultado_planilha = _parse_float(col(93))
    obs_geral = _limpar_texto(col(94))

    return {
        "id_planilha": _limpar_texto(col(1)),
        "carro": _limpar_texto(col(2)),
        "placa": _normalizar_placa(_limpar_texto(col(3))),
        "motorista": _limpar_texto(col(4)),
        "id_frete": _limpar_texto(col(6)),
        "ciclo_planilha": _limpar_texto(col(7)),
        "tipo_raw": _limpar_texto(col(8)),
        "rota_bruta": rota_bruta,
        "origem": origem,
        "destino": destino,
        "km_rota": _parse_float(col(10)),
        "data_frete": _parse_date(col(11)),
        "tipo_material": _limpar_texto(col(12)),
        "qtde_volumes": _parse_int(col(13)),
        "volume_m3": _parse_float(col(14)),
        "peso_kg": _parse_float(col(15)),
        "nfe": _limpar_texto(col(16)),
        "cte": _limpar_texto(col(17)),
        "mdfe": _limpar_texto(col(18)),
        "ciot": _limpar_texto(col(19)),
        "cliente_empresa": _limpar_texto(col(21)),
        "cliente_responsavel": _limpar_texto(col(22)),
        "cliente_contato": _limpar_texto(col(23)),
        "forma_contratacao": _limpar_texto(col(25)),
        "valor_divulgado": val_divulgado,
        "valor_negociado": val_negociado,
        "perc_adiantamento": perc_adiant,
        "perc_saldo": perc_saldo,
        "obs_saldo": _limpar_texto(col(30)),
        "forma_pagamento": _limpar_texto(col(31)),
        "banco_conta": _limpar_texto(col(32)),
        "data_adiantamento": _parse_date(col(33)),
        "valor_adiantamento": val_adiant_rec,
        "data_saldo": _parse_date(col(35)),
        "valor_saldo": val_saldo_rec,
        "valor_total_recebido_planilha": val_total_rec,
        "coleta_endereco": f"{coleta_end} - {coleta_bairro}".strip(" -"),
        "coleta_cep": coleta_cep,
        "coleta_cidade": coleta_cidade,
        "coleta_uf": coleta_uf,
        "coleta_local": coleta_local,
        "coleta_responsavel": _limpar_texto(col(45)),
        "coleta_contato": _limpar_texto(col(46)),
        "data_coleta": _parse_date(col(47)),
        "hora_plan_coleta": _parse_time(col(48)),
        "hora_real_coleta": _parse_time(col(49)),
        "obs_coleta": _limpar_texto(col(50)),
        "entrega_endereco": f"{entrega_end} - {entrega_bairro}".strip(" -"),
        "entrega_cep": entrega_cep,
        "entrega_cidade": entrega_cidade,
        "entrega_uf": entrega_uf,
        "entrega_local": entrega_local,
        "entrega_responsavel": _limpar_texto(col(58)),
        "entrega_contato": _limpar_texto(col(59)),
        "documento_entrega": _limpar_texto(col(60)),
        "data_entrega": _parse_date(col(61)),
        "hora_plan_entrega": _parse_time(col(62)),
        "hora_real_entrega": _parse_time(col(63)),
        "obs_entrega": _limpar_texto(col(64)),
        "ab1_km": ab1_km,
        "ab1_l_diesel": ab1_l_diesel,
        "ab1_p_diesel": ab1_p_diesel,
        "ab1_v_diesel": ab1_v_diesel,
        "ab1_l_arla": ab1_l_arla,
        "ab1_p_arla": ab1_p_arla,
        "ab1_v_arla": ab1_v_arla,
        "ab2_km": ab2_km,
        "ab2_l_diesel": ab2_l_diesel,
        "ab2_p_diesel": ab2_p_diesel,
        "ab2_v_diesel": ab2_v_diesel,
        "ab2_l_arla": ab2_l_arla,
        "ab2_p_arla": ab2_p_arla,
        "ab2_v_arla": ab2_v_arla,
        "combustivel_total": combustivel_total,
        "pedagio": pedagio,
        "alimentacao": alimentacao,
        "hospedagem": hospedagem,
        "manutencao": manutencao,
        "outras_despesas": outras_despesas,
        "total_despesas_planilha": total_despesas_planilha,
        "km_ini": km_ini,
        "km_fin": km_fin,
        "km_real": km_real,
        "status": status_raw,
        "valor_total_geral_planilha": val_total_geral,
        "resultado_planilha": resultado_planilha,
        "obs_geral": obs_geral,
    }


def _mapear_linha_generica(row_series: pd.Series) -> dict:
    """Fallback para planilhas exportadas do próprio sistema ou CSVs simplificados."""
    norm = {str(k).strip().lower(): v for k, v in row_series.items()}

    def get_any(*chaves):
        for ch in chaves:
            if ch in norm and _limpar_texto(norm[ch]):
                return norm[ch]
        return None

    origem = _limpar_texto(get_any("origem", "rota origem", "rota_origem"))
    destino = _limpar_texto(get_any("destino", "rota destino", "rota_destino"))
    rota_bruta = _limpar_texto(get_any("rota", "rota resumo", "rota_resumo"))
    if (not origem or not destino) and rota_bruta:
        o, d = separar_rota(rota_bruta)
        origem = origem or o
        destino = destino or d

    val_negociado = _parse_float(get_any("valor negociado", "receita negociada (r$)", "receita"))
    val_adiant = _parse_float(get_any("valor adiantamento", "adiantamento (r$)"))
    val_saldo = _parse_float(get_any("valor saldo", "saldo (r$)"))
    total_desp = _parse_float(get_any("total de despesas", "despesas (r$)", "despesas"))

    return {
        "id_planilha": _limpar_texto(get_any("id", "código", "codigo_viagem")),
        "carro": _limpar_texto(get_any("carro", "veículo", "veiculo")),
        "placa": _normalizar_placa(_limpar_texto(get_any("placa"))),
        "motorista": _limpar_texto(get_any("motorista")),
        "id_frete": _limpar_texto(get_any("id frete", "id_frete_externo")),
        "ciclo_planilha": _limpar_texto(get_any("ciclo", "id ciclo")),
        "tipo_raw": _limpar_texto(get_any("tipo frete", "tipo", "tipo viagem")),
        "rota_bruta": rota_bruta or f"{origem} -> {destino}".strip(" ->"),
        "origem": origem,
        "destino": destino,
        "km_rota": _parse_float(get_any("km x rota", "km planejado")),
        "data_frete": _parse_date(get_any("data", "data frete")),
        "tipo_material": _limpar_texto(get_any("tipo de material", "material")),
        "qtde_volumes": _parse_int(get_any("qt de volumes", "volumes")),
        "volume_m3": _parse_float(get_any("volume - m³", "volume m3")),
        "peso_kg": _parse_float(get_any("peso - kg", "peso kg")),
        "nfe": _limpar_texto(get_any("nf-e / carga", "nf-e", "nfe")),
        "cte": _limpar_texto(get_any("ct-e", "cte")),
        "mdfe": _limpar_texto(get_any("mdf-e", "mdfe")),
        "ciot": _limpar_texto(get_any("ciot")),
        "cliente_empresa": _limpar_texto(get_any("empresa", "cliente")),
        "cliente_responsavel": _limpar_texto(get_any("responsável", "responsavel")),
        "cliente_contato": _limpar_texto(get_any("contato")),
        "forma_contratacao": _limpar_texto(get_any("forma de contratação")),
        "valor_divulgado": _parse_float(get_any("valor divulgado")),
        "valor_negociado": val_negociado,
        "perc_adiantamento": _parse_percent(get_any("adiantamento %")),
        "perc_saldo": _parse_percent(get_any("saldo %")),
        "obs_saldo": _limpar_texto(get_any("observação referente ao saldo")),
        "forma_pagamento": _limpar_texto(get_any("forma de pagamento")),
        "banco_conta": _limpar_texto(get_any("banco/conta")),
        "data_adiantamento": _parse_date(get_any("data adiantamento a receber")),
        "valor_adiantamento": val_adiant,
        "data_saldo": _parse_date(get_any("data saldo a receber")),
        "valor_saldo": val_saldo,
        "valor_total_recebido_planilha": round(val_adiant + val_saldo, 2),
        "coleta_endereco": _limpar_texto(get_any("endereço coleta")),
        "coleta_cep": _limpar_texto(get_any("cep coleta")),
        "coleta_cidade": _limpar_texto(get_any("cidade coleta")),
        "coleta_uf": _limpar_texto(get_any("uf coleta")).upper()[:2],
        "coleta_local": _limpar_texto(get_any("empresa ou local para coleta", "local coleta")),
        "coleta_responsavel": "",
        "coleta_contato": "",
        "data_coleta": _parse_date(get_any("data da coleta")),
        "hora_plan_coleta": None,
        "hora_real_coleta": None,
        "obs_coleta": "",
        "entrega_endereco": _limpar_texto(get_any("endereço entrega")),
        "entrega_cep": _limpar_texto(get_any("cep entrega")),
        "entrega_cidade": _limpar_texto(get_any("cidade entrega")),
        "entrega_uf": _limpar_texto(get_any("uf entrega")).upper()[:2],
        "entrega_local": _limpar_texto(get_any("empresa ou local para entrega", "local entrega")),
        "entrega_responsavel": "",
        "entrega_contato": "",
        "documento_entrega": "",
        "data_entrega": _parse_date(get_any("data da entrega")),
        "hora_plan_entrega": None,
        "hora_real_entrega": None,
        "obs_entrega": "",
        "ab1_km": "",
        "ab1_l_diesel": 0.0,
        "ab1_p_diesel": 0.0,
        "ab1_v_diesel": 0.0,
        "ab1_l_arla": 0.0,
        "ab1_p_arla": 0.0,
        "ab1_v_arla": 0.0,
        "ab2_km": "",
        "ab2_l_diesel": 0.0,
        "ab2_p_diesel": 0.0,
        "ab2_v_diesel": 0.0,
        "ab2_l_arla": 0.0,
        "ab2_p_arla": 0.0,
        "ab2_v_arla": 0.0,
        "combustivel_total": 0.0,
        "pedagio": 0.0,
        "alimentacao": 0.0,
        "hospedagem": 0.0,
        "manutencao": 0.0,
        "outras_despesas": total_desp,
        "total_despesas_planilha": total_desp,
        "km_ini": _parse_int(get_any("km inicial")),
        "km_fin": _parse_int(get_any("km final")),
        "km_real": _parse_int(get_any("km real rodado", "km real")),
        "status": _limpar_texto(get_any("status")) or "Concluída",
        "valor_total_geral_planilha": val_negociado,
        "resultado_planilha": round(val_negociado - total_desp, 2),
        "obs_geral": _limpar_texto(get_any("observação geral da viagem", "observação")),
    }


def extrair_registros_planilha(arquivo_bytes, nome_arquivo: str, abas_selecionadas: list[str]) -> list[dict]:
    """Lê a(s) aba(s) selecionada(s) e extrai apenas linhas válidas de viagens."""
    registros = []
    eh_csv = nome_arquivo.lower().endswith(".csv")

    for aba in abas_selecionadas:
        if eh_csv:
            df_raw = pd.read_csv(arquivo_bytes, header=None, sep=None, engine="python")
        else:
            df_raw = pd.read_excel(arquivo_bytes, sheet_name=aba, header=None)

        if df_raw.empty:
            continue

        header_idx = _detectar_linha_cabecalho(df_raw)
        headers = [_limpar_texto(v) for v in df_raw.iloc[header_idx].values]
        headers_lower = [h.lower() for h in headers]

        eh_template_faeg = (
            len(headers_lower) >= 20
            and "placa" in headers_lower[:10]
            and "motorista" in headers_lower[:10]
            and "id frete" in headers_lower[:12]
        )

        for r_idx in range(header_idx + 1, len(df_raw)):
            row_vals = list(df_raw.iloc[r_idx].values)
            if eh_template_faeg:
                reg = _mapear_linha_padrao_faeg(row_vals)
            else:
                serie = pd.Series(row_vals[: len(headers)], index=headers)
                reg = _mapear_linha_generica(serie)

            id_txt = reg["id_planilha"].upper()
            if id_txt in {"FECHAMENTO", "TOTAL", "SUBTOTAL", "RESUMO", "ID"}:
                continue

            tem_conteudo = any(
                [
                    reg["placa"],
                    reg["motorista"],
                    reg["id_frete"],
                    reg["origem"],
                    reg["destino"],
                    reg["cliente_empresa"],
                    reg["valor_negociado"] > 0,
                    reg["total_despesas_planilha"] > 0,
                ]
            )
            if not tem_conteudo:
                continue

            reg["aba_origem"] = aba
            registros.append(reg)

    return registros


# ==============================================================================
# PERSISTÊNCIA NO BANCO E CONCILIAÇÃO FINANCEIRA
# ==============================================================================


def _obter_ou_criar_motorista(db, nome: str, pendencias: list[str]) -> Motorista:
    nome_limpo = nome or "Motorista Pendente (Planilha)"
    existente = (
        db.query(Motorista)
        .filter(Motorista.nome_completo.ilike(nome_limpo))
        .first()
    )
    if existente:
        return existente

    seq = db.query(Motorista).count() + 1
    while db.query(Motorista).filter(Motorista.cpf == f"IMP-MOT-{seq:04d}").first():
        seq += 1

    novo = Motorista(
        nome_completo=nome_limpo,
        cpf=f"IMP-MOT-{seq:04d}",
        cnh_numero=f"PEND-CNH-{seq:04d}",
        vinculo="Importado Planilha",
        status_ativo=True,
    )
    db.add(novo)
    db.flush()
    pendencias.append(
        f"Motorista '{nome_limpo}' criado com CPF/CNH provisórios (editar em Cadastros Gerais)."
    )
    return novo


def _obter_ou_criar_veiculo(db, placa: str, carro: str, pendencias: list[str]) -> Veiculo:
    placa_limpa = _normalizar_placa(placa) or f"IMP{db.query(Veiculo).count() + 1:04d}"
    existente = db.query(Veiculo).filter(Veiculo.placa.ilike(placa_limpa)).first()
    if existente:
        if carro and (not existente.descricao_marca or existente.descricao_marca.startswith("Veículo ")):
            existente.descricao_marca = carro
        return existente

    novo = Veiculo(
        descricao_marca=carro or f"Veículo {placa_limpa}",
        placa=placa_limpa,
        tipo_veiculo="Não Informado",
        status_ativo=True,
    )
    db.add(novo)
    db.flush()
    if placa_limpa.startswith("IMP"):
        pendencias.append(
            f"Veículo '{novo.descricao_marca}' criado sem placa (editar em Cadastros Gerais)."
        )
    return novo


def _obter_ou_criar_cliente(db, empresa: str, resp: str, contato: str, pendencias: list[str]) -> Cliente:
    nome_emp = empresa or "Cliente Não Informado (Planilha)"
    existente = (
        db.query(Cliente)
        .filter(
            (Cliente.razao_social.ilike(nome_emp))
            | (Cliente.nome_fantasia.ilike(nome_emp))
        )
        .first()
    )
    if existente:
        return existente

    seq = db.query(Cliente).count() + 1
    while db.query(Cliente).filter(Cliente.cnpj_cpf == f"IMP-CLI-{seq:04d}").first():
        seq += 1

    novo = Cliente(
        razao_social=nome_emp,
        nome_fantasia=nome_emp,
        cnpj_cpf=f"IMP-CLI-{seq:04d}",
        responsavel_comercial=resp,
        telefone_comercial=contato,
    )
    db.add(novo)
    db.flush()
    pendencias.append(
        f"Cliente '{nome_emp}' criado com CNPJ/CPF provisório (editar em Cadastros Gerais)."
    )
    return novo


def _obter_ou_criar_local(
    db,
    nome_local: str,
    endereco: str,
    cep: str,
    cidade: str,
    uf: str,
    contato: str,
    tipo_padrao: str,
) -> Local:
    nome_final = nome_local or (
        f"{tipo_padrao} - {cidade}/{uf}".strip("/") if cidade else f"{tipo_padrao} (Planilha)"
    )
    existente = (
        db.query(Local)
        .filter(Local.nome_local.ilike(nome_final), Local.cidade.ilike(cidade or ""))
        .first()
    )
    if existente:
        return existente

    novo = Local(
        nome_local=nome_final[:150],
        tipo_instalacao=tipo_padrao,
        cep=cep[:15],
        endereco_completo=endereco[:250],
        cidade=cidade[:100],
        uf=uf[:5],
        contato_portaria=contato[:100],
    )
    db.add(novo)
    db.flush()
    return novo


def _gerar_despesas_viagem(db, viagem_id: int, reg: dict):
    """Cria os lançamentos de despesas mantendo soma exata com a planilha."""
    itens = []

    # 1. Abastecimento 01 (Diesel e ARLA)
    km1_txt = f" | KM {reg['ab1_km']}" if reg["ab1_km"] else ""
    if reg["ab1_v_diesel"] > 0:
        qtd = reg["ab1_l_diesel"] if reg["ab1_l_diesel"] > 0 else 1.0
        unit = reg["ab1_p_diesel"] if reg["ab1_p_diesel"] > 0 else reg["ab1_v_diesel"]
        desc = f"Diesel - Abast. 01 (Planilha{km1_txt})"
        itens.append(("Posto de Combustível", desc, qtd, unit, reg["ab1_v_diesel"]))

    if reg["ab1_v_arla"] > 0:
        qtd = reg["ab1_l_arla"] if reg["ab1_l_arla"] > 0 else 1.0
        unit = reg["ab1_p_arla"] if reg["ab1_p_arla"] > 0 else reg["ab1_v_arla"]
        desc = f"ARLA - Abast. 01 (Planilha{km1_txt})"
        itens.append(("Abast. ARLA", desc, qtd, unit, reg["ab1_v_arla"]))

    # 2. Abastecimento 02 (Diesel e ARLA)
    km2_txt = f" | KM {reg['ab2_km']}" if reg["ab2_km"] else ""
    if reg["ab2_v_diesel"] > 0:
        qtd = reg["ab2_l_diesel"] if reg["ab2_l_diesel"] > 0 else 1.0
        unit = reg["ab2_p_diesel"] if reg["ab2_p_diesel"] > 0 else reg["ab2_v_diesel"]
        desc = f"Diesel - Abast. 02 (Planilha{km2_txt})"
        itens.append(("Posto de Combustível", desc, qtd, unit, reg["ab2_v_diesel"]))

    if reg["ab2_v_arla"] > 0:
        qtd = reg["ab2_l_arla"] if reg["ab2_l_arla"] > 0 else 1.0
        unit = reg["ab2_p_arla"] if reg["ab2_p_arla"] > 0 else reg["ab2_v_arla"]
        desc = f"ARLA - Abast. 02 (Planilha{km2_txt})"
        itens.append(("Abast. ARLA", desc, qtd, unit, reg["ab2_v_arla"]))

    # Garante que se 'Combustível total' tiver diferença sobre Abast 01+02, ela também seja lançada
    soma_comb_abast = round(
        reg["ab1_v_diesel"] + reg["ab1_v_arla"] + reg["ab2_v_diesel"] + reg["ab2_v_arla"], 2
    )
    diff_comb = round(reg["combustivel_total"] - soma_comb_abast, 2)
    if diff_comb > 0.01:
        itens.append(
            ("Posto de Combustível", "Combustível Complementar (Planilha)", 1.0, diff_comb, diff_comb)
        )

    # 3. Demais despesas operacionais da planilha
    if reg["pedagio"] > 0:
        itens.append(("Concessionária Pedágio", "Pedágio (Planilha)", 1.0, reg["pedagio"], reg["pedagio"]))
    if reg["alimentacao"] > 0:
        itens.append(("Alimentação", "Alimentação (Planilha)", 1.0, reg["alimentacao"], reg["alimentacao"]))
    if reg["hospedagem"] > 0:
        itens.append(("Hospedagem", "Hospedagem (Planilha)", 1.0, reg["hospedagem"], reg["hospedagem"]))
    if reg["manutencao"] > 0:
        itens.append(("Oficina Mecânica", "Manutenção Emergencial (Planilha)", 1.0, reg["manutencao"], reg["manutencao"]))
    if reg["outras_despesas"] > 0:
        itens.append(("Outros", "Outras Despesas (Planilha)", 1.0, reg["outras_despesas"], reg["outras_despesas"]))

    # 4. Ajuste de diferença caso 'Total de despesas' na planilha possua valor manual extra
    soma_lancada = round(sum(x[4] for x in itens), 2)
    diff_total = round(reg["total_despesas_planilha"] - soma_lancada, 2)
    if diff_total > 0.01:
        itens.append(
            ("Outros", "Ajuste Diferença Total Despesas (Planilha)", 1.0, diff_total, diff_total)
        )

    data_ref = reg["data_frete"] or reg["data_coleta"] or date.today()
    for tipo, desc, qtd, unit, total in itens:
        db.add(
            ViagemDespesa(
                id_viagem=viagem_id,
                tipo_despesa=tipo,
                descricao_detalhe=desc[:150],
                quantidade=round(qtd, 2),
                valor_unitario=round(unit, 2),
                valor_total=round(total, 2),
                data_despesa=data_ref,
            )
        )


def importar_registros_para_banco(
    db,
    registros: list[dict],
    ignorar_duplicados: bool = True,
) -> dict:
    """Importa os registros extraídos para o PostgreSQL e retorna relatório de conciliação."""
    importados = 0
    ignorados = 0
    pendencias = []
    codigos_gerados = []

    receita_planilha_total = 0.0
    despesa_planilha_total = 0.0
    resultado_planilha_total = 0.0

    receita_sistema_total = 0.0
    despesa_sistema_total = 0.0

    contagem_ciclos = {}
    for r in registros:
        c = r["ciclo_planilha"]
        if c:
            contagem_ciclos[c] = contagem_ciclos.get(c, 0) + 1

    ciclos_criados_por_codigo = {}

    for reg in registros:
        viagem_existente = None
        if reg["id_frete"]:
            viagem_existente = (
                db.query(Viagem)
                .filter(Viagem.id_frete_externo == reg["id_frete"])
                .first()
            )
        if not viagem_existente and reg["data_frete"] and reg["placa"]:
            viagem_existente = (
                db.query(Viagem)
                .join(Veiculo, Viagem.id_veiculo == Veiculo.id_veiculo)
                .filter(
                    Viagem.data_frete == reg["data_frete"],
                    Veiculo.placa == reg["placa"],
                    Viagem.rota_origem == reg["origem"],
                    Viagem.rota_destino == reg["destino"],
                )
                .first()
            )

        if viagem_existente and ignorar_duplicados:
            ignorados += 1
            continue

        motorista = _obter_ou_criar_motorista(db, reg["motorista"], pendencias)
        veiculo = _obter_ou_criar_veiculo(db, reg["placa"], reg["carro"], pendencias)
        cliente = _obter_ou_criar_cliente(
            db,
            reg["cliente_empresa"],
            reg["cliente_responsavel"],
            reg["cliente_contato"],
            pendencias,
        )
        local_coleta = _obter_ou_criar_local(
            db,
            reg["coleta_local"],
            reg["coleta_endereco"],
            reg["coleta_cep"],
            reg["coleta_cidade"],
            reg["coleta_uf"],
            reg["coleta_contato"],
            "Coleta",
        )
        local_entrega = _obter_ou_criar_local(
            db,
            reg["entrega_local"],
            reg["entrega_endereco"],
            reg["entrega_cep"],
            reg["entrega_cidade"],
            reg["entrega_uf"],
            reg["entrega_contato"],
            "Entrega",
        )

        opcoes_frete = {"Dedicado", "Complemento", "Cheio", "Fracionado", "Agregado"}
        tipo_raw_cap = reg["tipo_raw"].capitalize() if reg["tipo_raw"] else ""
        eh_multi_viagem = bool(
            reg["ciclo_planilha"] and contagem_ciclos.get(reg["ciclo_planilha"], 0) > 1
        )
        tipo_viagem = "Ciclo" if (eh_multi_viagem or tipo_raw_cap == "Ciclo") else "Individual"
        tipo_frete = tipo_raw_cap if tipo_raw_cap in opcoes_frete else "Dedicado"

        ciclo_key = reg["ciclo_planilha"] if eh_multi_viagem else None
        if ciclo_key and ciclo_key in ciclos_criados_por_codigo:
            ciclo = ciclos_criados_por_codigo[ciclo_key]
            fin = ciclo.financeiro
            if fin:
                fin.valor_negociado_total = float(fin.valor_negociado_total or 0) + reg["valor_negociado"]
                fin.valor_divulgado = float(fin.valor_divulgado or 0) + reg["valor_divulgado"]
                fin.valor_adiantamento = float(fin.valor_adiantamento or 0) + reg["valor_adiantamento"]
                fin.valor_saldo = float(fin.valor_saldo or 0) + reg["valor_saldo"]
        else:
            nome_op = (
                f"Ciclo {reg['ciclo_planilha']} - {reg['origem']} -> {reg['destino']}"
                if reg["ciclo_planilha"]
                else f"Operação {reg['origem']} -> {reg['destino']}"
            )
            ciclo = CicloOperacional(
                id_cliente=cliente.id_cliente,
                nome_operacao=nome_op[:150],
                data_abertura=reg["data_frete"] or reg["data_coleta"] or date.today(),
                data_fechamento=reg["data_entrega"],
                status_ciclo=reg["status"] or "Concluída",
            )
            db.add(ciclo)
            db.flush()

            fin = CicloFinanceiro(
                id_ciclo=ciclo.id_ciclo,
                forma_contratacao=reg["forma_contratacao"] or "Viagem Fechada",
                valor_divulgado=round(reg["valor_divulgado"], 2),
                valor_negociado_total=round(reg["valor_negociado"], 2),
                perc_adiantamento=round(reg["perc_adiantamento"], 2),
                data_prevista_adiantamento=reg["data_adiantamento"],
                valor_adiantamento=round(reg["valor_adiantamento"], 2),
                perc_saldo=round(reg["perc_saldo"], 2),
                data_prevista_saldo=reg["data_saldo"],
                valor_saldo=round(reg["valor_saldo"], 2),
                forma_pagamento=reg["forma_pagamento"][:50],
                banco_conta=reg["banco_conta"][:100],
                obs_saldo=reg["obs_saldo"][:300],
            )
            db.add(fin)
            if ciclo_key:
                ciclos_criados_por_codigo[ciclo_key] = ciclo

        codigo_v = gerar_proximo_codigo_viagem(db)
        rota_resumo = (
            f"{reg['origem']} -> {reg['destino']}"
            if (reg["origem"] or reg["destino"])
            else reg["rota_bruta"]
        )

        nova_viagem = Viagem(
            codigo_viagem=codigo_v,
            id_ciclo=ciclo.id_ciclo,
            id_motorista=motorista.id_motorista,
            id_veiculo=veiculo.id_veiculo,
            id_frete_externo=reg["id_frete"][:50],
            data_frete=reg["data_frete"] or reg["data_coleta"],
            status_viagem=reg["status"][:30] or "Concluída",
            tipo_viagem=tipo_viagem,
            tipo_frete=tipo_frete,
            rota_origem=reg["origem"][:100],
            rota_destino=reg["destino"][:100],
            rota_resumo=rota_resumo[:210],
            km_rota_planejado=round(reg["km_rota"], 2),
            id_local_coleta=local_coleta.id_local,
            data_coleta=reg["data_coleta"],
            hora_planejada_coleta=reg["hora_plan_coleta"],
            hora_real_coleta=reg["hora_real_coleta"],
            obs_coleta=reg["obs_coleta"][:300],
            id_local_entrega=local_entrega.id_local,
            data_entrega=reg["data_entrega"],
            hora_planejada_entrega=reg["hora_plan_entrega"],
            hora_real_entrega=reg["hora_real_entrega"],
            documento_entrega=reg["documento_entrega"][:100],
            obs_entrega=reg["obs_entrega"][:300],
            tipo_material=reg["tipo_material"][:150],
            qtde_volumes=reg["qtde_volumes"],
            peso_bruto_kg=round(reg["peso_kg"], 2),
            volume_m3=round(reg["volume_m3"], 2),
            nfe_carga=reg["nfe"][:100],
            cte_numero=reg["cte"][:50],
            mdfe_numero=reg["mdfe"][:50],
            ciot_numero=reg["ciot"][:50],
            odometro_inicial=reg["km_ini"],
            odometro_final=reg["km_fin"],
            km_real_rodado=reg["km_real"],
            observacao_geral=reg["obs_geral"][:500],
        )
        db.add(nova_viagem)
        db.flush()

        _gerar_despesas_viagem(db, nova_viagem.id_viagem, reg)
        db.flush()

        desp_viagem_sis = sum(
            float(d.valor_total or 0)
            for d in db.query(ViagemDespesa)
            .filter(ViagemDespesa.id_viagem == nova_viagem.id_viagem)
            .all()
        )
        desp_plan = (
            reg["total_despesas_planilha"]
            if reg["total_despesas_planilha"] > 0
            else desp_viagem_sis
        )
        res_plan = (
            reg["resultado_planilha"]
            if reg["resultado_planilha"] != 0
            else round(reg["valor_negociado"] - desp_plan, 2)
        )

        receita_planilha_total += reg["valor_negociado"]
        despesa_planilha_total += desp_plan
        resultado_planilha_total += res_plan

        receita_sistema_total += reg["valor_negociado"]
        despesa_sistema_total += desp_viagem_sis

        if not reg["origem"] or not reg["destino"]:
            pendencias.append(
                f"Viagem {codigo_v}: Origem ou Destino incompleto (editar na aba '2. Frete e Docs')."
            )

        codigos_gerados.append(codigo_v)
        importados += 1

    db.commit()

    pendencias_unicas = list(dict.fromkeys(pendencias))

    return {
        "importados": importados,
        "ignorados": ignorados,
        "codigos_gerados": codigos_gerados,
        "receita_planilha": round(receita_planilha_total, 2),
        "despesa_planilha": round(despesa_planilha_total, 2),
        "resultado_planilha": round(resultado_planilha_total, 2),
        "receita_sistema": round(receita_sistema_total, 2),
        "despesa_sistema": round(despesa_sistema_total, 2),
        "resultado_sistema": round(receita_sistema_total - despesa_sistema_total, 2),
        "pendencias": pendencias_unicas,
    }