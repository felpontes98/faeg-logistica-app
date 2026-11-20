"""Diagnóstico somente de leitura dos ciclos já cadastrados no PostgreSQL.

Execute: python -m database.diagnostico_ciclos

Não executa create_all(), INSERT, UPDATE, DELETE ou migração. No PostgreSQL,
abre a transação explicitamente no modo READ ONLY.
"""

import json
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import inspect, text

from database.connection import engine


def _normalizar_identificador(valor):
    return str(valor or "").strip().upper()


def analisar_ciclos_armazenados(registros):
    """Consolida um retrato da base sem alterar seus registros."""
    grupos = defaultdict(list)
    codigos_frete = defaultdict(list)
    total_viagens = 0

    for registro in registros:
        total_viagens += 1
        dados = dict(registro)
        codigo_ciclo = _normalizar_identificador(dados.get("nome_operacao"))
        codigo_frete = _normalizar_identificador(dados.get("id_frete_externo"))
        if codigo_frete:
            codigos_frete[codigo_frete].append(dados["id_viagem"])
        if not codigo_ciclo or codigo_ciclo.startswith("INDIVIDUAL -"):
            continue
        grupos[codigo_ciclo].append(dados)

    grupos_reportados = []
    for codigo_ciclo, fretes in sorted(grupos.items()):
        ids_ciclos = sorted({int(r["id_ciclo"]) for r in fretes})
        ids_clientes = {
            int(r["id_cliente_frete"] or r["id_cliente_ciclo"])
            for r in fretes
            if r.get("id_cliente_frete") or r.get("id_cliente_ciclo")
        }
        com_financeiro_legado = [r for r in fretes if r.get("id_cliente_frete") is None]
        legado_compartilhado = any(
            sum(outro["id_ciclo"] == r["id_ciclo"] for outro in fretes) > 1
            for r in com_financeiro_legado
        )
        problemas = []
        if len(ids_ciclos) > 1:
            problemas.append("Ciclo com vários IDs internos: possível duplicação histórica")
        if len(ids_clientes) > 1:
            problemas.append("Fretes do mesmo ciclo possuem clientes diferentes (pode ser legítimo)")
        if legado_compartilhado:
            problemas.append("Financeiro legado em ciclo compartilhado: totais exigem conferência")

        # Valores por frete têm precedência. Cifras legadas compartilhadas não
        # devem ser apresentadas como totais confiáveis de um ciclo.
        total_negociado = None
        if not legado_compartilhado:
            valores = [
                r.get("valor_frete") if r.get("id_cliente_frete") is not None else r.get("valor_legado")
                for r in fretes
            ]
            if any(valor is None for valor in valores):
                problemas.append("Há fretes sem valor negociado registrado")
            else:
                total_negociado = str(sum((Decimal(str(valor)) for valor in valores), Decimal("0")))

        grupos_reportados.append(
            {
                "codigo_ciclo": codigo_ciclo,
                "ids_ciclos": ids_ciclos,
                "quantidade_fretes": len(fretes),
                "quantidade_clientes": len(ids_clientes),
                "fretes_com_financeiro_legado": len(com_financeiro_legado),
                "total_negociado_estavel": total_negociado,
                "avisos": problemas,
            }
        )

    duplicados = [g for g in grupos_reportados if len(g["ids_ciclos"]) > 1]
    return {
        "total_viagens": total_viagens,
        "total_codigos_ciclo": len(grupos_reportados),
        "codigos_ciclo_duplicados": len(duplicados),
        "ciclos_com_multiplos_fretes": sum(g["quantidade_fretes"] > 1 for g in grupos_reportados),
        "ids_frete_repetidos": {
            codigo: ids for codigo, ids in sorted(codigos_frete.items()) if len(ids) > 1
        },
        "ciclos_a_conferir": [g for g in grupos_reportados if g["avisos"]],
        "nenhum_dado_foi_alterado": True,
    }


def diagnosticar_banco():
    """Recupera um retrato SQL em uma transação obrigatoriamente sem escrita."""
    if engine.dialect.name not in {"postgresql", "sqlite"}:
        raise RuntimeError("Diagnóstico permitido somente em PostgreSQL ou SQLite de testes.")

    with engine.connect() as conexao:
        if engine.dialect.name == "postgresql":
            conexao.execute(text("SET TRANSACTION READ ONLY"))
        else:
            conexao.execute(text("PRAGMA query_only=ON"))

        tabelas = {"viagens", "ciclos_operacionais", "ciclos_financeiro"}
        existentes = {t for t in tabelas | {"fretes_financeiro"} if inspect(conexao).has_table(t)}
        faltantes = tabelas - existentes
        if faltantes:
            raise RuntimeError(f"Banco sem tabelas necessárias para diagnóstico: {', '.join(sorted(faltantes))}")

        if "fretes_financeiro" in existentes:
            colunas_frete = "ff.id_cliente AS id_cliente_frete, ff.valor_negociado_total AS valor_frete"
            join_frete = "LEFT JOIN fretes_financeiro ff ON ff.id_viagem = v.id_viagem"
        else:
            colunas_frete = "NULL AS id_cliente_frete, NULL AS valor_frete"
            join_frete = ""

        consulta = f"""
            SELECT v.id_viagem, v.id_frete_externo, v.id_ciclo,
                   c.nome_operacao, c.id_cliente AS id_cliente_ciclo,
                   cf.valor_negociado_total AS valor_legado,
                   {colunas_frete}
            FROM viagens v
            JOIN ciclos_operacionais c ON c.id_ciclo = v.id_ciclo
            LEFT JOIN ciclos_financeiro cf ON cf.id_ciclo = c.id_ciclo
            {join_frete}
            ORDER BY v.id_viagem
        """
        # A interpolação acima escolhe apenas dois fragmentos de SQL fixos,
        # definidos no próprio código a partir da existência da tabela.
        registros = conexao.execute(text(consulta)).mappings().all()
        resultado = analisar_ciclos_armazenados(registros)
        resultado["tabela_financeiro_individual_existe"] = "fretes_financeiro" in existentes
        return resultado


if __name__ == "__main__":
    print(json.dumps(diagnosticar_banco(), ensure_ascii=False, indent=2))