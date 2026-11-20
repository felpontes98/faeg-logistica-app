"""Fechamento gerencial por ciclo a partir de fretes, sem alterar o banco.

As despesas diretas pertencem ao ID Frete; as compartilhadas, ao ID Ciclo.
Cada valor é somado uma vez, sem rateio e sem incluir abastecimentos de veículo.
"""


def consolidar_ciclos(fretes, despesas_ciclo=None):
    """Retorna uma linha por ID interno de ciclo, sem somar linhas de fechamento.

    Cada frete deve ter: id_ciclo, id_viagem, codigo_viagem, id_frete,
    valor_negociado, valor_adiantamento, valor_saldo, total_despesas,
    km_rota_planejado, km_deslocamentos_operacionais, financeiro_individual.
    O identificador interno impede juntar ciclos legados homônimos por engano.
    """
    grupos = {}
    despesas_ciclo = despesas_ciclo or []
    for frete in fretes:
        if frete.get("tipo_viagem") != "Ciclo":
            continue
        id_ciclo = frete.get("id_ciclo")
        if id_ciclo is None:
            # Usado exclusivamente para a prévia de um ciclo ainda não salvo.
            id_ciclo = f"novo:{str(frete.get('ciclo', '')).strip().casefold()}"
        grupos.setdefault(id_ciclo, []).append(frete)

    fechamentos = []
    for id_ciclo, itens in grupos.items():
        # Se a prévia substitui um frete salvo, usa sua versão mais recente.
        fretes_unicos = {}
        for item in itens:
            fretes_unicos[item.get("id_viagem") or f"novo:{len(fretes_unicos)}"] = item
        itens = list(fretes_unicos.values())

        itens_detalhados = []
        for item in itens:
            ambiguo = len(itens) > 1 and item.get("financeiro_individual") is False
            detalhe = dict(item)
            detalhe["financeiro_legado_ambiguo"] = ambiguo
            detalhe["negociado_considerado"] = 0.0 if ambiguo else float(item.get("valor_negociado") or 0)
            itens_detalhados.append(detalhe)
        ambiguos = [item for item in itens_detalhados if item["financeiro_legado_ambiguo"]]
        receitas = [item for item in itens_detalhados if not item["financeiro_legado_ambiguo"]]
        receita = round(sum(float(i.get("valor_negociado") or 0) for i in receitas), 2)
        adiantamentos = round(sum(float(i.get("valor_adiantamento") or 0) for i in receitas), 2)
        saldos = round(sum(float(i.get("valor_saldo") or 0) for i in receitas), 2)
        despesas_dos_fretes = round(sum(float(i.get("total_despesas") or 0) for i in itens), 2)
        despesas_comuns = round(sum(
            float(d.get("valor_total") or 0) for d in despesas_ciclo
            if d.get("id_ciclo") == id_ciclo and not d.get("cancelado", False)
        ), 2)
        despesas = round(despesas_dos_fretes + despesas_comuns, 2)
        recebido = round(sum(float(i.get("total_recebido") or 0) for i in itens), 2)
        # Não compensar automaticamente o excedente de um frete com o saldo
        # de outro. Cada contrato mantém seu valor em aberto e o excedente
        # fica disponível para conferência separada.
        saldo_receber = round(sum(
            max(0.0, float(i.get("valor_negociado") or 0) - float(i.get("total_recebido") or 0))
            for i in receitas
        ), 2) if not ambiguos else None
        excedente_recebido = round(sum(
            max(0.0, float(i.get("total_recebido") or 0) - float(i.get("valor_negociado") or 0))
            for i in receitas
        ), 2) if not ambiguos else None
        km_fretes = round(sum(float(i.get("km_rota_planejado") or 0) for i in itens), 2)
        # Na prévia, o frete em edição é anexado por último: seu valor manual
        # dos deslocamentos do ciclo deve prevalecer sobre o cache já salvo.
        deslocamentos = round(float(itens[-1].get("km_deslocamentos_operacionais") or 0), 2)
        resultado = round(receita - despesas, 2)
        margem = round(resultado / receita * 100, 2) if receita > 0 else None

        fechamentos.append({
            "id_ciclo": id_ciclo,
            "ciclo": itens[0].get("ciclo") or "-",
            "qtd_fretes": len(itens),
            "ids_frete": [i.get("id_frete") or "-" for i in itens],
            "codigos_viagem": [i.get("codigo_viagem") or "-" for i in itens],
            "clientes": sorted({i.get("cliente") or "-" for i in itens}),
            "valor_negociado_total": receita,
            "adiantamentos_previstos": adiantamentos,
            "saldos_previstos": saldos,
            "parcelas_previstas": round(adiantamentos + saldos, 2),
            "total_recebido": recebido,
            "saldo_a_receber": saldo_receber,
            "excedente_recebido": excedente_recebido,
            "despesas_total": despesas,
            "despesas_fretes_total": despesas_dos_fretes,
            "despesas_compartilhadas_total": despesas_comuns,
            "resultado_operacional_parcial": resultado,
            "margem_operacional_pct": margem,
            "km_planejado_fretes": km_fretes,
            "km_deslocamentos_operacionais": deslocamentos,
            "km_total_planejado": round(km_fretes + deslocamentos, 2),
            "qtd_financeiros_legados_ambiguos": len(ambiguos),
            "fretes": itens_detalhados,
        })

    return sorted(fechamentos, key=lambda f: (str(f["ciclo"]).casefold(), str(f["id_ciclo"])))
