"""Conferência conservadora de possíveis custos repetidos entre frete e ciclo.

O cruzamento é uma pista para revisão humana, não prova de nota duplicada.
Não altera registros existentes nem tenta redistribuir valores.
"""

import re
import unicodedata
from decimal import Decimal

from database.models import Abastecimento, CicloDespesa, Viagem, ViagemDespesa


COMBUSTIVEIS = {"Posto de Combustível", "Abast. ARLA"}


def _texto(valor):
    sem_acento = "".join(
        letra for letra in unicodedata.normalize("NFKD", str(valor or ""))
        if not unicodedata.combining(letra)
    )
    return re.sub(r"\s+", " ", sem_acento.casefold()).strip()


def _numero(valor, casas):
    return Decimal(str(valor or 0)).quantize(Decimal("1").scaleb(-casas))


def _dados(despesa, abastecimento=None, id_veiculo=None):
    """Uniformiza os campos de despesas financeiras salvas e novas."""
    obter = (
        (lambda nome: despesa.get(nome))
        if isinstance(despesa, dict)
        else (lambda nome: getattr(despesa, nome, None))
    )
    return {
        "tipo_despesa": obter("tipo_despesa"),
        "data_despesa": obter("data_despesa"),
        "valor_total": obter("valor_total"),
        "quantidade": obter("quantidade"),
        "valor_unitario": obter("valor_unitario"),
        "descricao_detalhe": obter("descricao_detalhe"),
        "id_fornecedor": obter("id_fornecedor"),
        "id_veiculo": (
            (abastecimento.id_veiculo if abastecimento else None)
            or obter("id_veiculo_abast") or id_veiculo
        ),
        "odometro_abastecimento": (
            (abastecimento.odometro if abastecimento else None)
            or obter("odometro_abastecimento")
        ),
    }


def _semelhantes(a, b):
    if _texto(a["tipo_despesa"]) != _texto(b["tipo_despesa"]):
        return False
    if a["data_despesa"] != b["data_despesa"]:
        return False
    if _numero(a["valor_total"], 2) != _numero(b["valor_total"], 2):
        return False
    if _numero(a["quantidade"], 2) != _numero(b["quantidade"], 2):
        return False
    if _numero(a["valor_unitario"], 4) != _numero(b["valor_unitario"], 4):
        return False
    # Descrições distintas identificam gastos distintos. O rótulo genérico da
    # categoria pode coincidir em várias despesas legítimas no mesmo dia.
    if _texto(a["descricao_detalhe"]) != _texto(b["descricao_detalhe"]):
        return False
    if a["id_fornecedor"] and b["id_fornecedor"] and a["id_fornecedor"] != b["id_fornecedor"]:
        return False
    if a["id_veiculo"] and b["id_veiculo"] and a["id_veiculo"] != b["id_veiculo"]:
        return False
    if (
        a["tipo_despesa"] in COMBUSTIVEIS
        and a["odometro_abastecimento"] and b["odometro_abastecimento"]
        and a["odometro_abastecimento"] != b["odometro_abastecimento"]
    ):
        return False
    return True


def _identificacao_origem(tipo, despesa, viagem=None):
    if tipo == "Frete":
        return {
            "origem": "Frete",
            "id_lancamento": despesa.id_despesa,
            "id_frete": viagem.id_frete_externo or viagem.codigo_viagem,
            "id_ciclo": viagem.id_ciclo,
        }
    return {
        "origem": "Ciclo",
        "id_lancamento": despesa.id_despesa_ciclo,
        "id_frete": None,
        "id_ciclo": despesa.id_ciclo,
    }


def procurar_semelhancas_cruzadas(session, destino, id_ciclo, dados):
    """Encontra possíveis duplicidades entre destinos financeiros diferentes.

    `destino` é o local planejado para o novo custo: Frete ou Ciclo. Somente
    despesas do MESMO ciclo são comparadas, preservando a separação de IDs.
    """
    if id_ciclo is None or destino not in {"Frete", "Ciclo"}:
        return []
    novo = _dados(dados)
    if destino == "Frete":
        candidatos = [
            (d, None)
            for d in session.query(CicloDespesa).filter_by(
                id_ciclo=id_ciclo,
                cancelado=False,
                tipo_despesa=novo["tipo_despesa"],
                data_despesa=novo["data_despesa"],
                valor_total=novo["valor_total"],
            ).all()
        ]
        tipo_origem = "Ciclo"
    else:
        candidatos = session.query(ViagemDespesa, Viagem).join(
            Viagem, ViagemDespesa.id_viagem == Viagem.id_viagem,
        ).filter(
            Viagem.id_ciclo == id_ciclo,
            ViagemDespesa.cancelado.is_(False),
            ViagemDespesa.tipo_despesa == novo["tipo_despesa"],
            ViagemDespesa.data_despesa == novo["data_despesa"],
            ViagemDespesa.valor_total == novo["valor_total"],
        ).all()
        tipo_origem = "Frete"

    semelhantes = []
    for despesa, viagem in candidatos:
        ab = (
            session.query(Abastecimento).filter_by(
                **({
                    "id_despesa_ciclo": despesa.id_despesa_ciclo
                } if tipo_origem == "Ciclo" else {
                    "id_despesa_viagem": despesa.id_despesa
                })
            ).first()
            if novo["tipo_despesa"] in COMBUSTIVEIS else None
        )
        salvo = _dados(despesa, ab, viagem.id_veiculo if viagem else None)
        if _semelhantes(novo, salvo):
            semelhantes.append(_identificacao_origem(tipo_origem, despesa, viagem))
    return semelhantes


def listar_semelhancas_entre_frete_ciclo(session):
    """Auditoria somente leitura dos custos semelhantes já cadastrados."""
    fretes = session.query(ViagemDespesa, Viagem).join(
        Viagem, ViagemDespesa.id_viagem == Viagem.id_viagem,
    ).filter(ViagemDespesa.cancelado.is_(False)).all()
    ciclos = session.query(CicloDespesa).filter_by(cancelado=False).all()
    abastecimentos = session.query(Abastecimento).all()
    ab_fretes = {a.id_despesa_viagem: a for a in abastecimentos if a.id_despesa_viagem}
    ab_ciclos = {a.id_despesa_ciclo: a for a in abastecimentos if a.id_despesa_ciclo}

    ciclos_por_chave = {}
    for despesa in ciclos:
        chave = (
            despesa.id_ciclo, _texto(despesa.tipo_despesa),
            despesa.data_despesa, _numero(despesa.valor_total, 2),
        )
        ciclos_por_chave.setdefault(chave, []).append(despesa)

    alertas = []
    for d_frete, viagem in fretes:
        chave = (
            viagem.id_ciclo, _texto(d_frete.tipo_despesa),
            d_frete.data_despesa, _numero(d_frete.valor_total, 2),
        )
        dados_frete = _dados(d_frete, ab_fretes.get(d_frete.id_despesa), viagem.id_veiculo)
        for d_ciclo in ciclos_por_chave.get(chave, []):
            dados_ciclo = _dados(d_ciclo, ab_ciclos.get(d_ciclo.id_despesa_ciclo))
            if _semelhantes(dados_frete, dados_ciclo):
                alertas.append({
                    "ID Ciclo": viagem.id_ciclo,
                    "Código Ciclo": viagem.ciclo.nome_operacao if viagem.ciclo else "-",
                    "ID Frete": viagem.id_frete_externo or viagem.codigo_viagem,
                    "ID Despesa Frete": d_frete.id_despesa,
                    "ID Despesa Ciclo": d_ciclo.id_despesa_ciclo,
                    "Data": d_frete.data_despesa,
                    "Categoria": d_frete.tipo_despesa,
                    "Descrição": d_frete.descricao_detalhe or "-",
                    "Valor (R$)": float(d_frete.valor_total),
                    "Situação": "Possível repetição — conferir comprovantes",
                })
    return alertas
