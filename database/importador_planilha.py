import io
import re
from collections import defaultdict
from datetime import date, datetime, time

import openpyxl
import pandas as pd

from database.conciliacao_planilha import auditar_fechamentos_faeg
from database.connection import SessionLocal
from database.models import (
    CicloFinanceiro,
    CicloOperacional,
    Cliente,
    Local,
    Motorista,
    Veiculo,
    Viagem,
    ViagemDespesa,
)


def _limpar_texto(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip()
    if s.lower() in {"nan", "none", "nat", "#ref!", "#div/0!", "#valor!", "#value!", "#name?"}:
        return ""
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s


def _parse_float(val, default=0.0):
    valor_padrao = None if default is None else float(default)
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return valor_padrao
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s or s.lower() in {"nan", "none", "-"} or s.startswith("#"):
        return valor_padrao
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
    except (ValueError, TypeError):
        return valor_padrao


def _parse_int(val, default=0):
    return int(round(_parse_float(val, default)))


def _parse_date(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    s = str(val).strip()
    if not s or s.lower() in {"nan", "none", "nat", "-"}:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%y"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    try:
        dt = pd.to_datetime(s, dayfirst=True, errors="coerce")
        if pd.notna(dt):
            return dt.date()
    except Exception:
        pass
    return None


def _parse_time(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, time):
        return val.replace(microsecond=0)
    if isinstance(val, datetime):
        return val.time().replace(microsecond=0)
    s = str(val).strip()
    if not s or s.lower() in {"nan", "none", "nat", "-"}:
        return None
    if " " in s:
        s = s.split(" ")[-1]
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(s[:8], fmt).time()
        except ValueError:
            continue
    return None


def _normalizar_placa(placa_txt):
    return re.sub(r"[^A-Z0-9]", "", _limpar_texto(placa_txt).upper())


def _separar_origem_destino(rota_txt):
    txt = _limpar_texto(rota_txt)
    if not txt:
        return "", ""
    if "->" in txt:
        p = txt.split("->", 1)
        return p[0].strip(), p[1].strip()
    m = re.search(r"\s+[xX]\s+", txt)
    if m:
        return txt[: m.start()].strip(), txt[m.end() :].strip()
    if "/" in txt and " - " in txt:
        p = txt.split(" - ", 1)
        return p[0].strip(), p[1].strip()
    return txt, ""


def _normalizar_codigo_v(raw_id, usados_set, seq_fallback):
    txt = _limpar_texto(raw_id).upper()
    if txt:
        m = re.fullmatch(r"V?\s*0*(\d+)", txt)
        if m:
            cod = f"V{int(m.group(1))}"
        else:
            cod = txt
    else:
        while f"V{seq_fallback}" in usados_set:
            seq_fallback += 1
        cod = f"V{seq_fallback}"
    return cod


def _mapear_status(status_planilha, val_negociado, val_adiant, total_recebido):
    st_raw = _limpar_texto(status_planilha)
    st_low = st_raw.lower()
    if any(k in st_low for k in ["conclu", "quitad", "pago", "finaliz", "fechad"]):
        return "Quitada / Concluída"
    if "cancel" in st_low:
        return "Cancelada"
    if any(k in st_low for k in ["entregue", "aguardando saldo", "pendente saldo"]):
        return "Entregue / Aguardando Saldo"
    if any(k in st_low for k in ["transporte", "trânsito", "transito", "andamento", "rota"]):
        return "Em Transporte"
    if any(k in st_low for k in ["adiantamento recebido", "sinal"]):
        return "Adiantamento Recebido"

    if val_negociado > 0 and total_recebido >= val_negociado - 0.01:
        return "Quitada / Concluída"
    if val_adiant > 0:
        return "Adiantamento Recebido"
    return "Aguardando Adiantamento"


def _mapear_tipo_frete(tipo_txt):
    t = _limpar_texto(tipo_txt)
    if not t:
        return "Dedicado"
    t_low = t.lower()
    for op in ["Dedicado", "Complemento", "Cheio", "Fracionado", "Agregado"]:
        if op.lower() in t_low:
            return op
    return "Dedicado"


def _mapear_origem_frete(forma_txt):
    f = _limpar_texto(forma_txt)
    if not f:
        return "Aplicativo de Fretes"
    f_low = f.lower()
    mapa = {
        "aplicativo": "Aplicativo de Fretes",
        "fretebras": "Aplicativo de Fretes",
        "rede": "Redes Sociais",
        "whatsapp": "Redes Sociais",
        "fixo": "Cliente Fixo",
        "recorrente": "Cliente Recorrente",
        "eventual": "Cliente Eventual",
        "indica": "Indicação",
        "prospec": "Prospecção",
        "transportadora": "Transportadora Parceira",
        "parceira": "Transportadora Parceira",
    }
    for chave, destino in mapa.items():
        if chave in f_low:
            return destino
    return "Outros"


def _encontrar_linha_cabecalho(ws):
    """Localiza a linha onde ficam os cabeçalhos ('ID', 'Carro', 'Placa', 'Motorista', 'Rota')."""
    for r_idx in range(1, min(20, ws.max_row + 1)):
        vals = [_limpar_texto(ws.cell(r_idx, c).value).lower() for c in range(1, min(30, ws.max_column + 1))]
        if "motorista" in vals and ("placa" in vals or "rota" in vals or "carro" in vals):
            return r_idx
    return 8


def _obter_ou_criar_motorista(db, nome_mot, pendencias):
    nome_clean = _limpar_texto(nome_mot)
    if not nome_clean:
        nome_clean = "Motorista Não Informado (Planilha)"
        pendencias.append("Motorista ausente na linha (criado registro provisório)")

    mot = db.query(Motorista).filter(Motorista.nome_completo.ilike(nome_clean)).first()
    if mot:
        return mot, False

    ts = int(datetime.utcnow().timestamp() * 1000) % 100000000
    mot = Motorista(
        nome_completo=nome_clean,
        cpf=f"PEND-CPF-{ts}-{db.query(Motorista).count() + 1}",
        telefone_contato="",
        cnh_numero=f"PEND-CNH-{ts}-{db.query(Motorista).count() + 1}",
        cnh_categoria="E",
        vinculo="Frota Própria (CLT)",
    )
    db.add(mot)
    db.flush()
    pendencias.append(f"Motorista '{nome_clean}' cadastrado sem CPF/CNH (completar na Aba 11)")
    return mot, True


def _obter_ou_criar_veiculo(db, carro_txt, placa_txt, pendencias):
    placa_norm = _normalizar_placa(placa_txt)
    carro_clean = _limpar_texto(carro_txt)

    if placa_norm:
        vei = db.query(Veiculo).filter(Veiculo.placa.ilike(placa_norm)).first()
        if vei:
            return vei, False

    if carro_clean and not placa_norm:
        vei = db.query(Veiculo).filter(Veiculo.descricao_marca.ilike(carro_clean)).first()
        if vei:
            return vei, False

    if not placa_norm:
        placa_norm = f"PEND{db.query(Veiculo).count() + 1:03d}"
        pendencias.append(f"Veículo '{carro_clean or 'Sem nome'}' cadastrado sem placa (completar na Aba 11)")

    if not carro_clean:
        carro_clean = f"Veículo {placa_norm}"

    vei = Veiculo(
        descricao_marca=carro_clean,
        placa=placa_norm,
        tipo_veiculo="Truck",
    )
    db.add(vei)
    db.flush()
    return vei, True


def _obter_ou_criar_cliente(db, empresa_txt, resp_txt, cont_txt, pendencias):
    emp_clean = _limpar_texto(empresa_txt)
    if not emp_clean:
        emp_clean = "Cliente Não Informado (Planilha)"
        pendencias.append("Cliente ausente na linha (vinculado a 'Cliente Não Informado')")

    cli = (
        db.query(Cliente)
        .filter((Cliente.razao_social.ilike(emp_clean)) | (Cliente.nome_fantasia.ilike(emp_clean)))
        .first()
    )
    if cli:
        if resp_txt and not cli.responsavel_comercial:
            cli.responsavel_comercial = _limpar_texto(resp_txt)
        if cont_txt and not cli.telefone_comercial:
            cli.telefone_comercial = _limpar_texto(cont_txt)
        return cli, False

    ts = int(datetime.utcnow().timestamp() * 1000) % 100000000
    cli = Cliente(
        razao_social=emp_clean,
        nome_fantasia=emp_clean,
        cnpj_cpf=f"PEND-DOC-{ts}-{db.query(Cliente).count() + 1}",
        responsavel_comercial=_limpar_texto(resp_txt),
        telefone_comercial=_limpar_texto(cont_txt),
        prazo_pagamento_dias=30,
    )
    db.add(cli)
    db.flush()
    pendencias.append(f"Cliente '{emp_clean}' cadastrado sem CNPJ (completar na Aba 11)")
    return cli, True


def _obter_ou_criar_local(db, nome_local_txt, end_txt, cep_txt, bairro_txt, cid_txt, uf_txt, cont_txt, cliente_id, papel_fallback, cidade_fallback):
    nome_l = _limpar_texto(nome_local_txt)
    end_l = _limpar_texto(end_txt)
    bairro_l = _limpar_texto(bairro_txt)
    cid_l = _limpar_texto(cid_txt)
    uf_l = _limpar_texto(uf_txt).upper()[:2]
    cep_l = _limpar_texto(cep_txt)
    cont_l = _limpar_texto(cont_txt)

    if not cid_l and cidade_fallback:
        if "/" in cidade_fallback:
            p_c = cidade_fallback.split("/", 1)
            cid_l = p_c[0].strip()
            if not uf_l:
                uf_l = p_c[1].strip().upper()[:2]
        else:
            cid_l = cidade_fallback.strip()

    end_completo = ", ".join(p for p in [end_l, bairro_l] if p)

    if not nome_l:
        if cid_l:
            nome_l = f"Base {papel_fallback} - {cid_l}/{uf_l}".strip("/")
        elif end_completo:
            nome_l = end_completo[:120]
        else:
            nome_l = f"Local {papel_fallback} (Completar Cadastro)"

    q = db.query(Local).filter(Local.nome_local.ilike(nome_l))
    if cid_l:
        q = q.filter(Local.cidade.ilike(cid_l))
    loc = q.first()
    if loc:
        if end_completo and not loc.endereco_completo:
            loc.endereco_completo = end_completo
        if cep_l and not loc.cep:
            loc.cep = cep_l
        if cont_l and not loc.contato_portaria:
            loc.contato_portaria = cont_l
        if cliente_id and not loc.id_cliente:
            loc.id_cliente = cliente_id
        return loc, False

    loc = Local(
        id_cliente=cliente_id,
        nome_local=nome_l[:150],
        tipo_instalacao="Cliente Final" if papel_fallback == "Entrega" else "CD / Armazém",
        cep=cep_l[:15],
        endereco_completo=end_completo[:250],
        cidade=cid_l[:100],
        uf=uf_l,
        contato_portaria=cont_l[:120],
        restricao_horario="Não há restrição",
    )
    db.add(loc)
    db.flush()
    return loc, True


def analisar_planilha_faeg(file_bytes):
    """
    Lê a planilha Excel da FAEG (data_only=True para obter os valores calculados das fórmulas)
    e retorna um resumo estruturado das linhas válidas encontradas antes de gravar no banco.
    """
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    abas_ignoradas = {"PARÂMETROS", "PARAMETROS", "CONFIG", "LISTAS", "APOIO"}
    abas_operacionais = [s for s in wb.sheetnames if s.strip().upper() not in abas_ignoradas]
    if not abas_operacionais:
        abas_operacionais = [wb.sheetnames[0]]

    registros = []
    for aba in abas_operacionais:
        ws = wb[aba]
        header_row = _encontrar_linha_cabecalho(ws)

        # Mapeia índices de colunas considerando cabeçalhos repetidos (Coleta vs Entrega e Abastecimento 1 vs 2)
        col_map = {}
        contagem_nomes = {}
        for c in range(1, ws.max_column + 1):
            h = _limpar_texto(ws.cell(header_row, c).value)
            if not h:
                # Trata caso da coluna 39 (Endereço de Coleta que às vezes vem como '6482' ou vazio antes do CEP de Coleta)
                if c == 40 and "endereco_coleta" not in col_map:
                    col_map["endereco_coleta"] = c
                continue
            h_low = h.lower()
            contagem_nomes[h_low] = contagem_nomes.get(h_low, 0) + 1
            ocorrencia = contagem_nomes[h_low]

            if h_low == "id":
                col_map["id"] = c
            elif h_low == "carro":
                col_map["carro"] = c
            elif h_low == "placa":
                col_map["placa"] = c
            elif h_low == "motorista":
                col_map["motorista"] = c
            elif h_low == "id frete":
                col_map["id_frete"] = c
            elif h_low == "ciclo":
                col_map["ciclo"] = c
            elif h_low == "tipo":
                col_map["tipo"] = c
            elif h_low == "rota":
                col_map["rota"] = c
            elif "km" in h_low and "rota" in h_low:
                col_map["km_rota"] = c
            elif h_low == "data":
                col_map["data"] = c
            elif "tipo de material" in h_low:
                col_map["tipo_material"] = c
            elif "volumes" in h_low:
                col_map["qtde_volumes"] = c
            elif "volume" in h_low and "m" in h_low:
                col_map["volume_m3"] = c
            elif "peso" in h_low:
                col_map["peso_kg"] = c
            elif "nf-e" in h_low or "nfe" in h_low:
                col_map["nfe"] = c
            elif "ct-e" in h_low or "cte" in h_low:
                col_map["cte"] = c
            elif "mdf-e" in h_low or "mdfe" in h_low:
                col_map["mdfe"] = c
            elif "ciot" in h_low:
                col_map["ciot"] = c
            elif h_low == "empresa":
                col_map["empresa"] = c
            elif h_low == "responsável" or h_low == "responsavel":
                col_map["responsavel_cli"] = c
            elif h_low == "contato":
                col_map["contato_cli"] = c
            elif "forma de contratação" in h_low or "forma de contratacao" in h_low:
                col_map["forma_contratacao"] = c
            elif "valor divulgado" in h_low:
                col_map["valor_divulgado"] = c
            elif "valor negociado" in h_low:
                col_map["valor_negociado"] = c
            elif "adiantamento %" in h_low:
                col_map["perc_adiantamento"] = c
            elif "saldo %" in h_low:
                col_map["perc_saldo"] = c
            elif "data adiantamento" in h_low:
                col_map["data_adiantamento"] = c
            elif "valor adiantamento" in h_low:
                col_map["valor_adiantamento"] = c
            elif "data saldo" in h_low:
                col_map["data_saldo"] = c
            elif "valor saldo" in h_low:
                col_map["valor_saldo"] = c
            elif "valor total recebido" in h_low:
                col_map["valor_total_recebido"] = c
            elif h_low in {"endereço", "endereco"}:
                if "endereco_coleta" not in col_map:
                    col_map["endereco_coleta"] = c
                else:
                    col_map["endereco_entrega"] = c
            elif h_low == "cep":
                if ocorrencia == 1:
                    col_map["cep_coleta"] = c
                else:
                    col_map["cep_entrega"] = c
            elif h_low == "bairro":
                if ocorrencia == 1:
                    col_map["bairro_coleta"] = c
                else:
                    col_map["bairro_entrega"] = c
            elif h_low == "cidade":
                if ocorrencia == 1:
                    col_map["cidade_coleta"] = c
                else:
                    col_map["cidade_entrega"] = c
            elif h_low == "uf":
                if ocorrencia == 1:
                    col_map["uf_coleta"] = c
                else:
                    col_map["uf_entrega"] = c
            elif "local para coleta" in h_low:
                col_map["local_coleta"] = c
            elif "responsável despacho" in h_low or "responsavel despacho" in h_low:
                col_map["resp_coleta"] = c
            elif "contato do responsável" in h_low or "contato do responsavel" in h_low:
                if "cont_coleta" not in col_map:
                    col_map["cont_coleta"] = c
                else:
                    col_map["cont_entrega"] = c
            elif "data da coleta" in h_low:
                col_map["data_coleta"] = c
            elif "planejado da coleta" in h_low:
                col_map["hr_plan_coleta"] = c
            elif "real coletado" in h_low:
                col_map["hr_real_coleta"] = c
            elif "local para entrega" in h_low:
                col_map["local_entrega"] = c
            elif "responsável recebimento" in h_low or "responsavel recebimento" in h_low:
                col_map["resp_entrega"] = c
            elif "data da entrega" in h_low:
                col_map["data_entrega"] = c
            elif "planejado da entrega" in h_low:
                col_map["hr_plan_entrega"] = c
            elif "real da entrega" in h_low:
                col_map["hr_real_entrega"] = c
            elif "litros de diesel" in h_low:
                col_map["litros_diesel_1" if ocorrencia == 1 else "litros_diesel_2"] = c
            elif "r$/l diesel" in h_low:
                col_map["preco_diesel_1" if ocorrencia == 1 else "preco_diesel_2"] = c
            elif "litros de arla" in h_low:
                col_map["litros_arla_1" if ocorrencia == 1 else "litros_arla_2"] = c
            elif "r$/l arla" in h_low:
                col_map["preco_arla_1" if ocorrencia == 1 else "preco_arla_2"] = c
            elif "valor diesel" in h_low:
                col_map["valor_diesel_1" if ocorrencia == 1 else "valor_diesel_2"] = c
            elif "valor arla" in h_low:
                col_map["valor_arla_1" if ocorrencia == 1 else "valor_arla_2"] = c
            elif "combustível total" in h_low or "combustivel total" in h_low:
                col_map["combustivel_total"] = c
            elif "pedágio" in h_low or "pedagio" in h_low:
                col_map["pedagio"] = c
            elif "alimentação" in h_low or "alimentacao" in h_low:
                col_map["alimentacao"] = c
            elif "hospedagem" in h_low:
                col_map["hospedagem"] = c
            elif "manutenção" in h_low or "manutencao" in h_low:
                col_map["manutencao"] = c
            elif "outras despesas" in h_low:
                col_map["outras_despesas"] = c
            elif "total de despesas" in h_low:
                col_map["total_despesas"] = c
            elif "km inicial" in h_low:
                col_map["km_inicial"] = c
            elif "km final" in h_low:
                col_map["km_final"] = c
            elif "km real rodado" in h_low:
                col_map["km_real_rodado"] = c
            elif h_low == "status":
                col_map["status"] = c
            elif "valor total geral" in h_low:
                col_map["valor_total_geral"] = c
            elif "resultado da viagem" in h_low:
                col_map["resultado_viagem"] = c

        # Fallback posicional para Coluna 40 (Endereço de Coleta cujo cabeçalho às vezes é numérico)
        if "endereco_coleta" not in col_map and "cep_coleta" in col_map and col_map["cep_coleta"] > 2:
            col_map["endereco_coleta"] = col_map["cep_coleta"] - 1

        def get_c(r, key):
            idx_c = col_map.get(key)
            return ws.cell(r, idx_c).value if idx_c else None

        for r in range(header_row + 1, ws.max_row + 1):
            raw_id = _limpar_texto(get_c(r, "id"))
            raw_id_frete = _limpar_texto(get_c(r, "id_frete"))
            raw_tipo = _limpar_texto(get_c(r, "tipo"))
            raw_mot = _limpar_texto(get_c(r, "motorista"))
            raw_placa = _limpar_texto(get_c(r, "placa"))
            raw_rota = _limpar_texto(get_c(r, "rota"))
            raw_emp = _limpar_texto(get_c(r, "empresa"))
            val_neg = _parse_float(get_c(r, "valor_negociado"), 0.0)
            val_tot_rec = _parse_float(get_c(r, "valor_total_recebido"), 0.0)

            # Na planilha FAEG, "FECHAMENTO" fica na coluna "ID Frete" (não em "ID").
            # Fechamentos e totais não são novos fretes e não entram na soma das receitas.
            if (
                raw_id.upper().startswith(("FECHAMENTO", "TOTAL", "RESUMO"))
                or raw_id_frete.upper().startswith(("FECHAMENTO", "TOTAL", "RESUMO"))
                or raw_tipo.lower() == "fechamento"
            ):
                continue
            if not any([raw_id, raw_id_frete, raw_mot, raw_placa, raw_rota, raw_emp]):
                continue

            origem, destino = _separar_origem_destino(raw_rota)

            # Despesas detalhadas exatamente como calculadas na planilha
            despesas_itemizadas = []

            # Abastecimento 01 (Diesel + ARLA)
            l_d1 = _parse_float(get_c(r, "litros_diesel_1"), 0.0)
            p_d1 = _parse_float(get_c(r, "preco_diesel_1"), 0.0)
            v_d1 = _parse_float(get_c(r, "valor_diesel_1"), 0.0)
            if v_d1 <= 0 and l_d1 > 0 and p_d1 > 0:
                v_d1 = round(l_d1 * p_d1, 2)
            if v_d1 > 0:
                despesas_itemizadas.append(
                    {
                        "tipo": "Posto de Combustível",
                        "desc": "Abastecimento Diesel 01 (Planilha)",
                        "qtd": l_d1 if l_d1 > 0 else 1.0,
                        "unit": p_d1 if (l_d1 > 0 and p_d1 > 0) else v_d1,
                        "total": round(v_d1, 2),
                    }
                )

            l_a1 = _parse_float(get_c(r, "litros_arla_1"), 0.0)
            p_a1 = _parse_float(get_c(r, "preco_arla_1"), 0.0)
            v_a1 = _parse_float(get_c(r, "valor_arla_1"), 0.0)
            if v_a1 <= 0 and l_a1 > 0 and p_a1 > 0:
                v_a1 = round(l_a1 * p_a1, 2)
            if v_a1 > 0:
                despesas_itemizadas.append(
                    {
                        "tipo": "Abast. ARLA",
                        "desc": "Abastecimento ARLA 01 (Planilha)",
                        "qtd": l_a1 if l_a1 > 0 else 1.0,
                        "unit": p_a1 if (l_a1 > 0 and p_a1 > 0) else v_a1,
                        "total": round(v_a1, 2),
                    }
                )

            # Abastecimento 02 (Diesel + ARLA)
            l_d2 = _parse_float(get_c(r, "litros_diesel_2"), 0.0)
            p_d2 = _parse_float(get_c(r, "preco_diesel_2"), 0.0)
            v_d2 = _parse_float(get_c(r, "valor_diesel_2"), 0.0)
            if v_d2 <= 0 and l_d2 > 0 and p_d2 > 0:
                v_d2 = round(l_d2 * p_d2, 2)
            if v_d2 > 0:
                despesas_itemizadas.append(
                    {
                        "tipo": "Posto de Combustível",
                        "desc": "Abastecimento Diesel 02 (Planilha)",
                        "qtd": l_d2 if l_d2 > 0 else 1.0,
                        "unit": p_d2 if (l_d2 > 0 and p_d2 > 0) else v_d2,
                        "total": round(v_d2, 2),
                    }
                )

            l_a2 = _parse_float(get_c(r, "litros_arla_2"), 0.0)
            p_a2 = _parse_float(get_c(r, "preco_arla_2"), 0.0)
            v_a2 = _parse_float(get_c(r, "valor_arla_2"), 0.0)
            if v_a2 <= 0 and l_a2 > 0 and p_a2 > 0:
                v_a2 = round(l_a2 * p_a2, 2)
            if v_a2 > 0:
                despesas_itemizadas.append(
                    {
                        "tipo": "Abast. ARLA",
                        "desc": "Abastecimento ARLA 02 (Planilha)",
                        "qtd": l_a2 if l_a2 > 0 else 1.0,
                        "unit": p_a2 if (l_a2 > 0 and p_a2 > 0) else v_a2,
                        "total": round(v_a2, 2),
                    }
                )

            # Caso a planilha tenha apenas Combustível Total preenchido sem os subcampos
            comb_plan = _parse_float(get_c(r, "combustivel_total"), 0.0)
            soma_comb_itens = sum(d["total"] for d in despesas_itemizadas)
            if comb_plan > 0 and abs(comb_plan - soma_comb_itens) > 0.05:
                if soma_comb_itens == 0:
                    despesas_itemizadas.append(
                        {
                            "tipo": "Posto de Combustível",
                            "desc": "Combustível Total (Planilha)",
                            "qtd": 1.0,
                            "unit": round(comb_plan, 2),
                            "total": round(comb_plan, 2),
                        }
                    )
                else:
                    diff_comb = round(comb_plan - soma_comb_itens, 2)
                    if diff_comb > 0:
                        despesas_itemizadas.append(
                            {
                                "tipo": "Posto de Combustível",
                                "desc": "Complemento Combustível (Planilha)",
                                "qtd": 1.0,
                                "unit": diff_comb,
                                "total": diff_comb,
                            }
                        )

            # Outras categorias diretas
            outras_cats = [
                ("pedagio", "Concessionária Pedágio", "Pedágio (Planilha)"),
                ("alimentacao", "Alimentação", "Alimentação (Planilha)"),
                ("hospedagem", "Hospedagem", "Hospedagem (Planilha)"),
                ("manutencao", "Oficina Mecânica", "Manutenção Emergencial (Planilha)"),
                ("outras_despesas", "Outros", "Outras Despesas (Planilha)"),
            ]
            for col_k, tipo_d, desc_d in outras_cats:
                v_cat = _parse_float(get_c(r, col_k), 0.0)
                if v_cat > 0:
                    despesas_itemizadas.append(
                        {
                            "tipo": tipo_d,
                            "desc": desc_d,
                            "qtd": 1.0,
                            "unit": round(v_cat, 2),
                            "total": round(v_cat, 2),
                        }
                    )

            # Garante fidelidade exata ao "Total de despesas" da planilha caso haja diferença de centavos
            total_desp_plan = _parse_float(get_c(r, "total_despesas"), 0.0)
            soma_atual_desp = round(sum(d["total"] for d in despesas_itemizadas), 2)
            if total_desp_plan > 0 and abs(total_desp_plan - soma_atual_desp) > 0.01:
                ajuste = round(total_desp_plan - soma_atual_desp, 2)
                if ajuste > 0:
                    despesas_itemizadas.append(
                        {
                            "tipo": "Outros",
                            "desc": "Ajuste Conciliação Planilha",
                            "qtd": 1.0,
                            "unit": ajuste,
                            "total": ajuste,
                        }
                    )

            val_div = _parse_float(get_c(r, "valor_divulgado"), 0.0)
            val_ad = _parse_float(get_c(r, "valor_adiantamento"), 0.0)
            val_sd = _parse_float(get_c(r, "valor_saldo"), 0.0)
            perc_ad = _parse_float(get_c(r, "perc_adiantamento"), 0.0)
            perc_sd = _parse_float(get_c(r, "perc_saldo"), 0.0)

            # Ajusta percentuais caso venham como fração decimal (ex: 0.4 -> 40%)
            if 0 < perc_ad <= 1.0 and val_neg > 0 and abs((val_neg * perc_ad) - val_ad) < 1.0:
                perc_ad = round(perc_ad * 100.0, 2)
            if 0 < perc_sd <= 1.0 and val_neg > 0 and abs((val_neg * perc_sd) - val_sd) < 1.0:
                perc_sd = round(perc_sd * 100.0, 2)

            if val_neg == 0 and val_tot_rec > 0:
                val_neg = val_tot_rec
            if val_ad == 0 and val_sd == 0 and val_tot_rec > 0:
                val_sd = val_tot_rec
                perc_sd = 100.0

            receita_plan = val_neg if val_neg > 0 else (val_ad + val_sd)
            desp_final = round(sum(d["total"] for d in despesas_itemizadas), 2)
            res_plan_cel = _parse_float(get_c(r, "resultado_viagem"), None)
            resultado_calc = round(receita_plan - desp_final, 2)

            registros.append(
                {
                    "aba": aba,
                    "linha": r,
                    "raw_id": raw_id,
                    "carro": _limpar_texto(get_c(r, "carro")),
                    "placa": raw_placa,
                    "motorista": raw_mot,
                    "id_frete": _limpar_texto(get_c(r, "id_frete")),
                    "ciclo": _limpar_texto(get_c(r, "ciclo")),
                    "tipo": _limpar_texto(get_c(r, "tipo")),
                    "rota_origem": origem,
                    "rota_destino": destino,
                    "km_rota": _parse_float(get_c(r, "km_rota"), 0.0),
                    "data_frete": _parse_date(get_c(r, "data")),
                    "tipo_material": _limpar_texto(get_c(r, "tipo_material")),
                    "qtde_volumes": _parse_int(get_c(r, "qtde_volumes"), 0),
                    "volume_m3": _parse_float(get_c(r, "volume_m3"), 0.0),
                    "peso_kg": _parse_float(get_c(r, "peso_kg"), 0.0),
                    "nfe": _limpar_texto(get_c(r, "nfe")),
                    "cte": _limpar_texto(get_c(r, "cte")),
                    "mdfe": _limpar_texto(get_c(r, "mdfe")),
                    "ciot": _limpar_texto(get_c(r, "ciot")),
                    "empresa": raw_emp,
                    "responsavel_cli": _limpar_texto(get_c(r, "responsavel_cli")),
                    "contato_cli": _limpar_texto(get_c(r, "contato_cli")),
                    "forma_contratacao": _limpar_texto(get_c(r, "forma_contratacao")),
                    "valor_divulgado": val_div,
                    "valor_negociado": val_neg,
                    "perc_adiantamento": perc_ad,
                    "data_adiantamento": _parse_date(get_c(r, "data_adiantamento")),
                    "valor_adiantamento": val_ad,
                    "perc_saldo": perc_sd,
                    "data_saldo": _parse_date(get_c(r, "data_saldo")),
                    "valor_saldo": val_sd,
                    "total_recebido": val_tot_rec if val_tot_rec > 0 else round(val_ad + val_sd, 2),
                    "endereco_coleta": _limpar_texto(get_c(r, "endereco_coleta")),
                    "cep_coleta": _limpar_texto(get_c(r, "cep_coleta")),
                    "bairro_coleta": _limpar_texto(get_c(r, "bairro_coleta")),
                    "cidade_coleta": _limpar_texto(get_c(r, "cidade_coleta")),
                    "uf_coleta": _limpar_texto(get_c(r, "uf_coleta")),
                    "local_coleta": _limpar_texto(get_c(r, "local_coleta")),
                    "resp_coleta": _limpar_texto(get_c(r, "resp_coleta")),
                    "cont_coleta": _limpar_texto(get_c(r, "cont_coleta")),
                    "data_coleta": _parse_date(get_c(r, "data_coleta")),
                    "hr_plan_coleta": _parse_time(get_c(r, "hr_plan_coleta")),
                    "hr_real_coleta": _parse_time(get_c(r, "hr_real_coleta")),
                    "endereco_entrega": _limpar_texto(get_c(r, "endereco_entrega")),
                    "cep_entrega": _limpar_texto(get_c(r, "cep_entrega")),
                    "bairro_entrega": _limpar_texto(get_c(r, "bairro_entrega")),
                    "cidade_entrega": _limpar_texto(get_c(r, "cidade_entrega")),
                    "uf_entrega": _limpar_texto(get_c(r, "uf_entrega")),
                    "local_entrega": _limpar_texto(get_c(r, "local_entrega")),
                    "resp_entrega": _limpar_texto(get_c(r, "resp_entrega")),
                    "cont_entrega": _limpar_texto(get_c(r, "cont_entrega")),
                    "data_entrega": _parse_date(get_c(r, "data_entrega")),
                    "hr_plan_entrega": _parse_time(get_c(r, "hr_plan_entrega")),
                    "hr_real_entrega": _parse_time(get_c(r, "hr_real_entrega")),
                    "km_inicial": _parse_int(get_c(r, "km_inicial"), 0),
                    "km_final": _parse_int(get_c(r, "km_final"), 0),
                    "km_real_rodado": _parse_int(get_c(r, "km_real_rodado"), 0),
                    "status_planilha": _limpar_texto(get_c(r, "status")),
                    "despesas": despesas_itemizadas,
                    "receita_consolidada": receita_plan,
                    "despesa_consolidada": desp_final,
                    "resultado_consolidado": res_plan_cel if res_plan_cel is not None else resultado_calc,
                }
            )

    return registros


def preparar_previa_importacao_faeg(file_bytes):
    """Confere fretes, fechamentos e divergências sem alterar a planilha ou o banco."""
    try:
        registros = analisar_planilha_faeg(file_bytes)

        if not registros:
            return {"erro": "Nenhuma linha válida de frete foi encontrada no arquivo Excel."}

        auditoria = auditar_fechamentos_faeg(file_bytes, registros)
        resumo_fechamentos = auditoria["resumo"]

        fretes_por_ciclo = defaultdict(list)
        for registro in registros:
            if registro["ciclo"]:
                fretes_por_ciclo[registro["ciclo"].strip().upper()].append(registro)
        ciclos = set(fretes_por_ciclo)
        ciclos_com_varios_fretes = sum(len(fretes) > 1 for fretes in fretes_por_ciclo.values())
        ciclos_com_varios_clientes = sum(
            len({r["empresa"].strip().casefold() for r in fretes if r["empresa"].strip()}) > 1
            for fretes in fretes_por_ciclo.values()
        )
        total_receita = round(sum(r["receita_consolidada"] for r in registros), 2)
        total_despesas = round(sum(r["despesa_consolidada"] for r in registros), 2)
        previa = pd.DataFrame(
            [
                {
                    "ID Frete": r["id_frete"],
                    "ID Ciclo": r["ciclo"] or "-",
                    "Tipo": r["tipo"] or "-",
                    "Rota": f"{r['rota_origem']} → {r['rota_destino']}",
                    "Receita do frete (R$)": r["receita_consolidada"],
                    "Despesas do frete (R$)": r["despesa_consolidada"],
                }
                for r in registros
            ]
        )

        previa_fechamentos = pd.DataFrame(
            [
                {
                    "Aba": item["aba"],
                    "Linha": item["linha"],
                    "Classificação": item["classificacao"],
                    "Ciclo na linha": item["ciclo_declarado"] or "Não informado",
                    "Ciclo dos fretes": item["ciclo_do_bloco"] or "-",
                    "Qtd. fretes": item["quantidade_fretes"],
                    "Receita dos fretes (R$)": item["receita_fretes"],
                    "Valor do fechamento (R$)": item["receita_fechamento"],
                    "Diferença (R$)": item["diferenca"],
                    "Conferência": "; ".join(item["ocorrencias"]) or "Conferido",
                }
                for item in auditoria["linhas"]
            ]
        )

        avisos = [
            "A prévia é somente de leitura. Valores negociados não comprovam pagamento efetivo.",
            "O vínculo entre cada fechamento e os fretes anteriores é uma sugestão de conferência, não uma correção automática.",
            "A gravação da planilha no PostgreSQL continua bloqueada até a conciliação e os testes de migração.",
        ]
        if resumo_fechamentos["ids_ausentes"] or resumo_fechamentos["ids_divergentes"]:
            avisos.append("Existem fechamentos com identificador de ciclo ausente ou diferente dos fretes correspondentes. Confira a tabela abaixo.")
        if resumo_fechamentos["possiveis_resumos"]:
            avisos.append("Há linha(s) sem fretes pendentes, possivelmente total geral. Esses valores não entram na receita dos fretes.")
        if resumo_fechamentos["fretes_sem_fechamento"]:
            avisos.append("Existem fretes sem uma linha posterior de fechamento. Eles podem representar ciclos em andamento.")

        return {
            "erro": None,
            "resumo": {
                "total_fretes": len(registros),
                "total_ciclos": len(ciclos),
                "total_fechamentos": resumo_fechamentos["linhas_fechamento"],
                "fechamentos_de_fretes": resumo_fechamentos["fechamentos_de_fretes"],
                "possiveis_resumos_gerais": resumo_fechamentos["possiveis_resumos"],
                "ids_fechamento_ausentes": resumo_fechamentos["ids_ausentes"],
                "ids_fechamento_divergentes": resumo_fechamentos["ids_divergentes"],
                "valores_fechamento_divergentes": resumo_fechamentos["valores_divergentes"],
                "fretes_sem_fechamento": resumo_fechamentos["fretes_sem_fechamento"],
                "ciclos_multifrete": ciclos_com_varios_fretes,
                "ciclos_multicliente": ciclos_com_varios_clientes,
                "receita_fretes": total_receita,
                "despesas_fretes": total_despesas,
            },
            "preview_df": previa,
            "preview_fechamentos_df": previa_fechamentos,
            "fretes_sem_fechamento": auditoria["fretes_sem_fechamento"],
            "avisos": avisos,
            "importacao_bloqueada": True,
        }
    except Exception:
        return {
            "erro": "Não foi possível ler a planilha. Confirme o formato .xlsx e os cabeçalhos esperados da FAEG."
        }


def importar_planilha_para_banco(file_bytes, modo_duplicado="atualizar"):
    """
    Grava todos os registros extraídos da planilha no PostgreSQL (Neon),
    criando automaticamente cadastros ausentes e conciliando receitas e despesas.
    """
    # Segurança: este importador antigo ainda cria um ciclo para CADA frete e
    # substitui despesas existentes. Não pode ser chamado até a conciliação ser
    # implementada e validada em um banco de testes.
    raise RuntimeError(
        "Importação no banco bloqueada: use apenas a prévia até a rotina de "
        "conciliação de fretes, ciclos e despesas ser homologada."
    )

    registros = analisar_planilha_faeg(file_bytes)
    if not registros:
        return {
            "importadas": 0,
            "atualizadas": 0,
            "ignoradas": 0,
            "pendencias": ["Nenhuma linha válida de viagem foi encontrada na planilha."],
            "resumo_viagens": [],
        }

    importadas = 0
    atualizadas = 0
    ignoradas = 0
    pendencias = []
    resumo_viagens = []

    with SessionLocal() as db:
        existentes_cod = {
            str(v.codigo_viagem).strip().upper()
            for v in db.query(Viagem).all()
            if v.codigo_viagem
        }
        seq_auto = 1

        for reg in registros:
            cod_v = _normalizar_codigo_v(reg["raw_id"], existentes_cod, seq_auto)
            existentes_cod.add(cod_v)
            seq_auto += 1

            viagem_existente = db.query(Viagem).filter(Viagem.codigo_viagem.ilike(cod_v)).first()
            if viagem_existente and modo_duplicado == "ignorar":
                ignoradas += 1
                continue

            mot_obj, _ = _obter_ou_criar_motorista(db, reg["motorista"], pendencias)
            vei_obj, _ = _obter_ou_criar_veiculo(db, reg["carro"], reg["placa"], pendencias)
            cli_obj, _ = _obter_ou_criar_cliente(
                db, reg["empresa"], reg["responsavel_cli"], reg["contato_cli"], pendencias
            )

            col_obj, _ = _obter_ou_criar_local(
                db,
                reg["local_coleta"],
                reg["endereco_coleta"],
                reg["cep_coleta"],
                reg["bairro_coleta"],
                reg["cidade_coleta"],
                reg["uf_coleta"],
                reg["cont_coleta"] or reg["resp_coleta"],
                cli_obj.id_cliente,
                "Coleta",
                reg["rota_origem"],
            )
            ent_obj, _ = _obter_ou_criar_local(
                db,
                reg["local_entrega"],
                reg["endereco_entrega"],
                reg["cep_entrega"],
                reg["bairro_entrega"],
                reg["cidade_entrega"],
                reg["uf_entrega"],
                reg["cont_entrega"] or reg["resp_entrega"],
                None,
                "Entrega",
                reg["rota_destino"],
            )

            tipo_raw = reg["tipo"].lower()
            ciclo_raw = reg["ciclo"]
            if "ciclo" in tipo_raw or (ciclo_raw and not re.fullmatch(r"V\d+", ciclo_raw.upper())):
                tipo_viagem_final = "Ciclo"
                nome_op_final = ciclo_raw if ciclo_raw else f"Ciclo - {cod_v}"
            else:
                tipo_viagem_final = "Individual"
                nome_op_final = f"Individual - {cod_v}"

            tipo_frete_final = _mapear_tipo_frete(reg["tipo"])
            origem_frete_final = _mapear_origem_frete(reg["forma_contratacao"])
            status_final = _mapear_status(
                reg["status_planilha"],
                reg["valor_negociado"],
                reg["valor_adiantamento"],
                reg["total_recebido"],
            )

            rota_resumo_final = (
                f"{reg['rota_origem']} -> {reg['rota_destino']}"
                if (reg["rota_origem"] and reg["rota_destino"])
                else (reg["rota_origem"] or reg["rota_destino"])
            )

            km_ini = reg["km_inicial"]
            km_fin = reg["km_final"]
            km_real = reg["km_real_rodado"] if reg["km_real_rodado"] > 0 else max(0, km_fin - km_ini)

            dt_base = reg["data_coleta"] or reg["data_frete"] or date.today()

            if viagem_existente:
                c_obj = viagem_existente.ciclo
                c_obj.id_cliente = cli_obj.id_cliente
                c_obj.nome_operacao = nome_op_final
                c_obj.data_abertura = dt_base
                c_obj.status_ciclo = f"COD::{cod_v}"

                fin_obj = c_obj.financeiro
                if not fin_obj:
                    fin_obj = CicloFinanceiro(id_ciclo=c_obj.id_ciclo)
                    db.add(fin_obj)

                fin_obj.forma_contratacao = origem_frete_final
                fin_obj.valor_divulgado = reg["valor_divulgado"]
                fin_obj.valor_negociado_total = reg["valor_negociado"]
                fin_obj.perc_adiantamento = reg["perc_adiantamento"]
                fin_obj.data_prevista_adiantamento = reg["data_adiantamento"] or dt_base
                fin_obj.valor_adiantamento = reg["valor_adiantamento"]
                fin_obj.perc_saldo = reg["perc_saldo"]
                fin_obj.data_prevista_saldo = reg["data_saldo"] or reg["data_entrega"] or dt_base
                fin_obj.valor_saldo = reg["valor_saldo"]

                viagem_existente.codigo_viagem = cod_v
                viagem_existente.id_motorista = mot_obj.id_motorista
                viagem_existente.id_veiculo = vei_obj.id_veiculo
                viagem_existente.id_frete_externo = reg["id_frete"]
                viagem_existente.status_viagem = status_final
                viagem_existente.tipo_viagem = tipo_viagem_final
                viagem_existente.tipo_frete = tipo_frete_final
                viagem_existente.rota_origem = reg["rota_origem"]
                viagem_existente.rota_destino = reg["rota_destino"]
                viagem_existente.rota_resumo = rota_resumo_final
                viagem_existente.km_rota_planejado = reg["km_rota"]
                viagem_existente.tipo_material = reg["tipo_material"]
                viagem_existente.qtde_volumes = reg["qtde_volumes"]
                viagem_existente.peso_bruto_kg = reg["peso_kg"]
                viagem_existente.volume_m3 = reg["volume_m3"]
                viagem_existente.nfe_carga = reg["nfe"]
                viagem_existente.cte_numero = reg["cte"]
                viagem_existente.mdfe_numero = reg["mdfe"]
                viagem_existente.ciot_numero = reg["ciot"]
                viagem_existente.id_local_coleta = col_obj.id_local
                viagem_existente.data_coleta = dt_base
                viagem_existente.hora_planejada_coleta = reg["hr_plan_coleta"]
                viagem_existente.hora_real_coleta = reg["hr_real_coleta"]
                viagem_existente.id_local_entrega = ent_obj.id_local
                viagem_existente.data_entrega = reg["data_entrega"] or dt_base
                viagem_existente.hora_planejada_entrega = reg["hr_plan_entrega"]
                viagem_existente.hora_real_entrega = reg["hr_real_entrega"]
                viagem_existente.odometro_inicial = km_ini
                viagem_existente.odometro_final = km_fin
                viagem_existente.km_real_rodado = km_real

                db.query(ViagemDespesa).filter_by(id_viagem=viagem_existente.id_viagem).delete()
                for d_item in reg["despesas"]:
                    db.add(
                        ViagemDespesa(
                            id_viagem=viagem_existente.id_viagem,
                            id_fornecedor=None,
                            tipo_despesa=d_item["tipo"],
                            descricao_detalhe=d_item["desc"],
                            quantidade=d_item["qtd"],
                            valor_unitario=d_item["unit"],
                            valor_total=d_item["total"],
                            data_despesa=dt_base,
                        )
                    )
                atualizadas += 1
            else:
                novo_ciclo = CicloOperacional(
                    id_cliente=cli_obj.id_cliente,
                    nome_operacao=nome_op_final,
                    data_abertura=dt_base,
                    status_ciclo=f"COD::{cod_v}",
                )
                db.add(novo_ciclo)
                db.flush()

                novo_fin = CicloFinanceiro(
                    id_ciclo=novo_ciclo.id_ciclo,
                    forma_contratacao=origem_frete_final,
                    valor_divulgado=reg["valor_divulgado"],
                    valor_negociado_total=reg["valor_negociado"],
                    perc_adiantamento=reg["perc_adiantamento"],
                    data_prevista_adiantamento=reg["data_adiantamento"] or dt_base,
                    valor_adiantamento=reg["valor_adiantamento"],
                    perc_saldo=reg["perc_saldo"],
                    data_prevista_saldo=reg["data_saldo"] or reg["data_entrega"] or dt_base,
                    valor_saldo=reg["valor_saldo"],
                )
                db.add(novo_fin)

                nova_v = Viagem(
                    codigo_viagem=cod_v,
                    id_ciclo=novo_ciclo.id_ciclo,
                    id_motorista=mot_obj.id_motorista,
                    id_veiculo=vei_obj.id_veiculo,
                    id_frete_externo=reg["id_frete"],
                    status_viagem=status_final,
                    tipo_viagem=tipo_viagem_final,
                    tipo_frete=tipo_frete_final,
                    rota_origem=reg["rota_origem"],
                    rota_destino=reg["rota_destino"],
                    rota_resumo=rota_resumo_final,
                    km_rota_planejado=reg["km_rota"],
                    tipo_material=reg["tipo_material"],
                    qtde_volumes=reg["qtde_volumes"],
                    peso_bruto_kg=reg["peso_kg"],
                    volume_m3=reg["volume_m3"],
                    nfe_carga=reg["nfe"],
                    cte_numero=reg["cte"],
                    mdfe_numero=reg["mdfe"],
                    ciot_numero=reg["ciot"],
                    id_local_coleta=col_obj.id_local,
                    data_coleta=dt_base,
                    hora_planejada_coleta=reg["hr_plan_coleta"],
                    hora_real_coleta=reg["hr_real_coleta"],
                    id_local_entrega=ent_obj.id_local,
                    data_entrega=reg["data_entrega"] or dt_base,
                    hora_planejada_entrega=reg["hr_plan_entrega"],
                    hora_real_entrega=reg["hr_real_entrega"],
                    odometro_inicial=km_ini,
                    odometro_final=km_fin,
                    km_real_rodado=km_real,
                )
                db.add(nova_v)
                db.flush()

                for d_item in reg["despesas"]:
                    db.add(
                        ViagemDespesa(
                            id_viagem=nova_v.id_viagem,
                            id_fornecedor=None,
                            tipo_despesa=d_item["tipo"],
                            descricao_detalhe=d_item["desc"],
                            quantidade=d_item["qtd"],
                            valor_unitario=d_item["unit"],
                            valor_total=d_item["total"],
                            data_despesa=dt_base,
                        )
                    )
                importadas += 1

            resumo_viagens.append(
                {
                    "Código": cod_v,
                    "Rota": rota_resumo_final or "-",
                    "Cliente": cli_obj.razao_social,
                    "Receita (R$)": reg["receita_consolidada"],
                    "Despesas (R$)": reg["despesa_consolidada"],
                    "Resultado (R$)": reg["resultado_consolidado"],
                }
            )

        db.commit()

    pendencias_unicas = list(dict.fromkeys(pendencias))
    return {
        "importadas": importadas,
        "atualizadas": atualizadas,
        "ignoradas": ignoradas,
        "pendencias": pendencias_unicas,
        "resumo_viagens": resumo_viagens,
    }