"""Rascunhos do formulário: armazenamento independente de viagens operacionais.

Rascunhos não criam fretes, receitas, despesas ou quilômetros financeiros.
A conversão para frete só ocorre quando os dados obrigatórios estão completos.
"""
import json
from datetime import date, datetime, time
from database.models import RascunhoViagem

DATAS_FORM = {"data_op", "data_coleta", "data_entrega", "data_adiant", "data_saldo"}
HORAS_FORM = {"hora_plan_col", "hora_real_col", "hora_plan_ent", "hora_real_ent"}


def _convert_datetime(value):
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    raise TypeError(f"Valor não serializável: {type(value).__name__}")


def empacotar_rascunho(form, saidas, despesas):
    return json.dumps({"form": form, "saidas": saidas, "despesas": despesas},
                      default=_convert_datetime, ensure_ascii=False)


def abrir_rascunho(conteudo_json):
    dados = json.loads(conteudo_json)
    form = dict(dados.get("form") or {})
    for campo in DATAS_FORM:
        if isinstance(form.get(campo), str) and form[campo]:
            form[campo] = date.fromisoformat(form[campo])
    for campo in HORAS_FORM:
        if isinstance(form.get(campo), str) and form[campo]:
            form[campo] = time.fromisoformat(form[campo])
    saidas = dados.get("saidas") or []
    for saida in saidas:
        for campo in ("data_inicio", "data_fim"):
            if isinstance(saida.get(campo), str) and saida[campo]:
                saida[campo] = date.fromisoformat(saida[campo])
    despesas = dados.get("despesas") or []
    for despesa in despesas:
        if isinstance(despesa.get("data_despesa"), str) and despesa["data_despesa"]:
            despesa["data_despesa"] = date.fromisoformat(despesa["data_despesa"])
    return form, saidas, despesas


def salvar_rascunho(session, *, id_rascunho, titulo, form, saidas, despesas):
    nome = (titulo or "Rascunho FAEG").strip()[:150]
    registro = session.get(RascunhoViagem, int(id_rascunho)) if id_rascunho else None
    if registro is None:
        registro = RascunhoViagem(titulo=nome)
        session.add(registro)
    registro.titulo = nome
    registro.conteudo_json = empacotar_rascunho(form, saidas, despesas)
    session.flush()
    return registro.id_rascunho


def publicar_saidas_rascunho(session, id_ciclo, saidas):
    """Converte saídas provisórias em saídas reais na transação do frete.

    Só é chamada uma vez na gravação definitiva. Não afeta outras saídas do ciclo.
    """
    from database.saidas_operacionais import salvar_saida
    ids = []
    for item in saidas:
        ids.append(salvar_saida(
            session, id_ciclo=id_ciclo, id_veiculo=item["id_veiculo"],
            id_motorista=item.get("id_motorista") or None, descricao=item["descricao"],
            data_inicio=item.get("data_inicio"), data_fim=item.get("data_fim"),
            odometro_inicial=item.get("odometro_inicial") or None,
            odometro_final=item.get("odometro_final") or None,
            km_planejado_manual=item.get("km_planejado_manual", 0.0),
            km_saida_coletas=item.get("km_saida_coletas", 0.0),
            km_rota_principal=item.get("km_rota_principal", 0.0),
            km_retorno_base=item.get("km_retorno_base", 0.0),
            observacoes=item.get("observacoes", ""),
        ))
    return ids


def resumo_saidas_provisorias(saidas):
    """Usa exatamente a regra de quilômetros do fechamento definitivo."""
    from types import SimpleNamespace
    from database.saidas_operacionais import resumo_saidas
    objetos = [SimpleNamespace(
        id_saida=i + 1,
        id_veiculo=s.get("id_veiculo"),
        km_planejado_manual=s.get("km_planejado_manual", 0),
        odometro_inicial=s.get("odometro_inicial"),
        odometro_final=s.get("odometro_final"),
        trechos=[],
    ) for i, s in enumerate(saidas)]
    return resumo_saidas(objetos) if objetos else None
