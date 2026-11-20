"""Auditoria somente de leitura dos fechamentos na planilha operacional FAEG.

Não abre conexões com o PostgreSQL, não altera a planilha e não tenta corrigir
automaticamente o código ou os valores declarados nas linhas de fechamento.
"""

import io
from collections import defaultdict
from decimal import Decimal, InvalidOperation

import openpyxl


def _texto(valor):
    return str(valor).strip() if valor is not None else ""


def _codigo(valor):
    return _texto(valor).upper()


def _valor_monetario(valor):
    if valor is None or _texto(valor) == "":
        return None
    if isinstance(valor, (int, float, Decimal)):
        return Decimal(str(valor))
    bruto = _texto(valor).replace("R$", "").replace(" ", "")
    if "," in bruto and "." in bruto:
        bruto = bruto.replace(".", "").replace(",", ".") if bruto.rfind(",") > bruto.rfind(".") else bruto.replace(",", "")
    elif "," in bruto:
        bruto = bruto.replace(",", ".")
    try:
        return Decimal(bruto)
    except InvalidOperation:
        return None


def _cabecalho_operacional(aba):
    """Retorna o índice da linha de cabeçalho e suas colunas relevantes."""
    nomes = {
        "id frete": "id_frete",
        "ciclo": "ciclo",
        "tipo": "tipo",
        "valor negociado": "valor_negociado",
        "total de despesas": "total_despesas",
    }
    for linha, valores in enumerate(
        aba.iter_rows(min_row=1, max_row=min(20, aba.max_row), values_only=True), 1
    ):
        normalizados = [_texto(v).lower() for v in valores]
        if "motorista" not in normalizados or "id frete" not in normalizados:
            continue
        colunas = {
            nomes[cabecalho]: indice
            for indice, cabecalho in enumerate(normalizados)
            if cabecalho in nomes
        }
        return linha, colunas
    return None, {}


def auditar_fechamentos_faeg(file_bytes, registros):
    """Confronta blocos de fretes com as linhas seguintes de fechamento.

    A associação pela proximidade é *somente uma hipótese de auditoria*;
    códigos diferentes nunca são sobrescritos ou aceitos automaticamente.
    """
    registros_por_aba = defaultdict(dict)
    for registro in registros:
        registros_por_aba[registro["aba"]][registro["linha"]] = registro

    analises = []
    fretes_pendentes = []
    ignoradas = {"PARÂMETROS", "PARAMETROS", "CONFIG", "LISTAS", "APOIO"}
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    try:
        for aba in wb.worksheets:
            if _codigo(aba.title) in ignoradas:
                continue
            cabecalho, colunas = _cabecalho_operacional(aba)
            if cabecalho is None or "id_frete" not in colunas:
                continue

            bloco = []
            for linha, valores in enumerate(
                aba.iter_rows(min_row=cabecalho + 1, values_only=True), cabecalho + 1
            ):
                if linha in registros_por_aba[aba.title]:
                    bloco.append(registros_por_aba[aba.title][linha])
                    continue

                def valor_coluna(nome):
                    indice = colunas.get(nome)
                    return valores[indice] if indice is not None and indice < len(valores) else None

                identificador_frete = _codigo(valor_coluna("id_frete"))
                tipo = _codigo(valor_coluna("tipo"))
                if not (identificador_frete.startswith("FECHAMENTO") or tipo == "FECHAMENTO"):
                    continue

                declarado = _codigo(valor_coluna("ciclo"))
                candidatos = {_codigo(r["ciclo"]) for r in bloco if _codigo(r["ciclo"])}
                inferido = next(iter(candidatos)) if len(candidatos) == 1 else ""
                receita_fretes = sum(
                    (Decimal(str(r["receita_consolidada"])) for r in bloco), Decimal("0")
                )
                valor_fechamento = _valor_monetario(valor_coluna("valor_negociado"))
                delta = valor_fechamento - receita_fretes if valor_fechamento is not None and bloco else None
                ocorrencias = []

                if not bloco:
                    classificacao = "Possível resumo geral"
                    ocorrencias.append("Linha sem fretes pendentes; não somar como nova receita")
                else:
                    classificacao = "Fechamento de fretes"
                    if not inferido:
                        ocorrencias.append("Bloco com ciclos diferentes ou ID de ciclo ausente nos fretes")
                    elif not declarado:
                        ocorrencias.append("ID do ciclo ausente no fechamento")
                    elif declarado != inferido:
                        ocorrencias.append("ID do ciclo diferente dos fretes do bloco")

                    if valor_fechamento is None:
                        ocorrencias.append("Valor negociado do fechamento não informado")
                    elif abs(delta) > Decimal("0.01"):
                        ocorrencias.append("Valor negociado diferente da soma dos fretes")

                analises.append(
                    {
                        "aba": aba.title,
                        "linha": linha,
                        "classificacao": classificacao,
                        "ciclo_declarado": declarado,
                        "ciclo_do_bloco": inferido,
                        "quantidade_fretes": len(bloco),
                        "receita_fretes": float(receita_fretes) if bloco else None,
                        "receita_fechamento": float(valor_fechamento) if valor_fechamento is not None else None,
                        "diferenca": float(delta) if delta is not None else None,
                        "ocorrencias": ocorrencias,
                    }
                )
                bloco = []

            # Fretes lançados após o último fechamento podem estar em andamento.
            for registro in bloco:
                fretes_pendentes.append(
                    {"aba": aba.title, "linha": registro["linha"], "id_frete": registro["id_frete"], "ciclo": registro["ciclo"]}
                )
    finally:
        wb.close()

    fechamentos = [r for r in analises if r["classificacao"] == "Fechamento de fretes"]
    return {
        "linhas": analises,
        "fretes_sem_fechamento": fretes_pendentes,
        "resumo": {
            "linhas_fechamento": len(analises),
            "fechamentos_de_fretes": len(fechamentos),
            "possiveis_resumos": len(analises) - len(fechamentos),
            "ids_ausentes": sum("ID do ciclo ausente no fechamento" in r["ocorrencias"] for r in fechamentos),
            "ids_divergentes": sum("ID do ciclo diferente dos fretes do bloco" in r["ocorrencias"] for r in fechamentos),
            "valores_divergentes": sum("Valor negociado diferente da soma dos fretes" in r["ocorrencias"] for r in fechamentos),
            "fretes_sem_fechamento": len(fretes_pendentes),
        },
    }
