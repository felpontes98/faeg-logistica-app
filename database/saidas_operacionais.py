"""Saídas/trechos físicos de uma operação FAEG.

Não há rateio por frete. As funções de consulta não escrevem no banco.
Os odômetros de abastecimento pertencem ao veículo e nunca substituem os de saída.
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import selectinload

from database.models import (
    CicloOperacional,
    ParametroConsumoVeiculo,
    SaidaOperacional,
    TrechoOperacional,
    Veiculo,
)


def _num(v):
    return Decimal(str(v or 0))


def _duas(v):
    return float(_num(v).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def validar_saida(dados):
    """Rejeita combinações impossíveis sem obrigar o fechamento no cadastro."""
    if not (dados.get("descricao") or "").strip():
        raise ValueError("Informe a descrição da saída.")
    if dados.get("data_inicio") and dados.get("data_fim") and dados["data_fim"] < dados["data_inicio"]:
        raise ValueError("O encerramento não pode ser anterior ao início da saída.")
    a, b = dados.get("odometro_inicial"), dados.get("odometro_final")
    if a is not None and (a < 0 or (b is not None and b < 0)):
        raise ValueError("O odômetro não pode ser negativo.")
    if a is not None and b is not None and b < a:
        raise ValueError("O odômetro final não pode ser menor que o inicial.")
    if _num(dados.get("km_planejado_manual")) < 0:
        raise ValueError("O KM planejado não pode ser negativo.")


def salvar_saida(session, *, id_ciclo, id_veiculo, id_motorista=None, id_saida=None,
                 descricao, data_inicio=None, data_fim=None,
                 odometro_inicial=None, odometro_final=None,
                 km_planejado_manual=None, observacoes=None):
    dados = locals().copy()
    validar_saida(dados)
    ciclo = session.get(CicloOperacional, int(id_ciclo))
    if ciclo is None:
        raise ValueError("Ciclo não encontrado.")
    if session.get(Veiculo, int(id_veiculo)) is None:
        raise ValueError("Veículo não encontrado.")
    if id_saida is None:
        saida = SaidaOperacional(id_ciclo=id_ciclo)
        session.add(saida)
    else:
        saida = session.get(SaidaOperacional, int(id_saida))
        if saida is None or saida.id_ciclo != id_ciclo:
            raise ValueError("Saída não pertence à operação selecionada.")
    for campo in ("id_veiculo", "id_motorista", "descricao", "data_inicio", "data_fim",
                  "odometro_inicial", "odometro_final", "km_planejado_manual", "observacoes"):
        setattr(saida, campo, dados[campo])
    session.flush()
    return saida.id_saida


def salvar_trecho(session, *, id_saida, tipo_trecho, origem, destino, km_planejado,
                  observacoes=None, id_trecho=None):
    saida = session.get(SaidaOperacional, int(id_saida))
    if saida is None:
        raise ValueError("A saída não existe.")
    if not origem.strip() or not destino.strip():
        raise ValueError("Informe origem e destino do trecho.")
    if _num(km_planejado) < 0:
        raise ValueError("KM do trecho não pode ser negativo.")
    if id_trecho is None:
        trecho = TrechoOperacional(id_saida=id_saida)
        session.add(trecho)
    else:
        trecho = session.get(TrechoOperacional, int(id_trecho))
        if trecho is None or trecho.id_saida != id_saida:
            raise ValueError("Trecho não pertence à saída selecionada.")
    trecho.tipo_trecho = tipo_trecho
    trecho.origem = origem.strip()
    trecho.destino = destino.strip()
    trecho.km_planejado = _num(km_planejado)
    trecho.observacoes = (observacoes or "").strip() or None
    session.flush()
    return trecho.id_trecho


def resumo_saidas(saidas):
    """Soma trajetos apenas uma vez; dados incompletos não viram KM real zero.

    Se existirem trechos numa saída, os trechos prevalecem sobre seu KM manual
    (o número manual continua preservado para auditoria). Sobreposição de
    intervalos de odômetro do mesmo veículo impede o total consolidado.
    """
    if not saidas:
        return {"qtd_saidas": 0, "qtd_trechos": 0, "km_planejado": None,
                "km_real": None, "km_real_parcial": 0., "completo": False,
                "avisos": [], "por_veiculo": {}}
    avisos = []
    km_plan = Decimal("0")
    km_real_conhecido = Decimal("0")
    intervalos = []
    por_veiculo = {}
    completos = 0
    qtd_trechos = 0
    for s in saidas:
        trechos = list(getattr(s, "trechos", []) or [])
        qtd_trechos += len(trechos)
        if trechos:
            plano = sum((_num(t.km_planejado) for t in trechos), Decimal("0"))
            if s.km_planejado_manual is not None and abs(plano - _num(s.km_planejado_manual)) > Decimal("0.01"):
                avisos.append(f"Saída {s.id_saida}: a soma dos trechos prevalece sobre o KM manual da saída.")
        elif s.km_planejado_manual is not None:
            plano = _num(s.km_planejado_manual)
        else:
            plano = Decimal("0")
            avisos.append(f"Saída {s.id_saida}: falta KM planejado.")
        km_plan += plano
        a, b = s.odometro_inicial, s.odometro_final
        if a is not None and b is not None and b >= a:
            km = Decimal(int(b) - int(a))
            km_real_conhecido += km
            completos += 1
            intervalos.append((s.id_veiculo, int(a), int(b), s.id_saida))
            por_veiculo[s.id_veiculo] = por_veiculo.get(s.id_veiculo, Decimal("0")) + km
        else:
            avisos.append(f"Saída {s.id_saida}: odômetros incompletos/inconsistentes.")
    houve_sobreposicao = False
    for i, (vei, ini, fim, id1) in enumerate(intervalos):
        for vei2, ini2, fim2, id2 in intervalos[i+1:]:
            if vei == vei2 and max(ini, ini2) < min(fim, fim2):
                houve_sobreposicao = True
                avisos.append(f"Saídas {id1} e {id2}: odômetros sobrepostos para o mesmo veículo.")
    completo = (completos == len(saidas)) and not houve_sobreposicao
    return {
        "qtd_saidas": len(saidas), "qtd_trechos": qtd_trechos,
        "km_planejado": _duas(km_plan),
        "km_real": _duas(km_real_conhecido) if completo else None,
        "km_real_parcial": _duas(km_real_conhecido),
        "completo": completo,
        "avisos": avisos,
        "por_veiculo": {idv: _duas(km) for idv, km in por_veiculo.items()} if completo else {},
    }


def consultar_saidas(session, id_ciclo):
    return (session.query(SaidaOperacional)
            .options(selectinload(SaidaOperacional.trechos))
            .filter_by(id_ciclo=id_ciclo)
            .order_by(SaidaOperacional.data_inicio, SaidaOperacional.id_saida).all())


def consultar_todas_saidas(session):
    return (session.query(SaidaOperacional)
            .options(selectinload(SaidaOperacional.trechos))
            .order_by(SaidaOperacional.id_ciclo, SaidaOperacional.data_inicio, SaidaOperacional.id_saida).all())


def estimar_consumo(km, km_por_litro, preco_por_litro):
    """Estimativa gerencial, NUNCA lançamento adicional de despesa."""
    if km is None or _num(km) < 0 or _num(km_por_litro) <= 0 or _num(preco_por_litro) <= 0:
        return None
    litros = _num(km) / _num(km_por_litro)
    return {"litros_estimados": _duas(litros),
            "custo_estimado": _duas(litros * _num(preco_por_litro))}


def estimativas_por_veiculo(session, resumo):
    """Retorna estimativas somente quando TODAS as saídas têm odômetros válidos."""
    if not resumo["completo"]:
        return [], ["Consumo indisponível: complete os odômetros de todas as saídas."]
    valores, avisos = [], []
    for id_veiculo, km in resumo["por_veiculo"].items():
        p = session.get(ParametroConsumoVeiculo, id_veiculo)
        if p is None:
            avisos.append(f"Veículo {id_veiculo}: configure consumo médio e preço de referência.")
            continue
        estimativa = estimar_consumo(km, p.km_por_litro, p.preco_litro_referencia)
        if estimativa is None:
            avisos.append(f"Veículo {id_veiculo}: parâmetros de consumo inválidos.")
            continue
        valores.append({"id_veiculo": id_veiculo, "km": km, **estimativa})
    return valores, avisos
