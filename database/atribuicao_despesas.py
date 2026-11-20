"""Atribuição/estorno de gastos provisórios do veículo, numa única transação.

O registro de origem e seu abastecimento são preservados. Só o destino
financeiro é considerado no resultado do frete ou ciclo; o histórico registra
o caminho percorrido pelo custo, inclusive após um estorno.
"""

from datetime import date

from database.conferencia_duplicidades import procurar_semelhancas_cruzadas
from database.models import (
    Abastecimento,
    CicloDespesa,
    CicloOperacional,
    VeiculoDespesa,
    VeiculoDespesaAtribuicao,
    Viagem,
    ViagemDespesa,
)


def _origem_ativa(session, id_despesa_veiculo):
    despesa = (
        session.query(VeiculoDespesa)
        .filter_by(id_despesa_veiculo=id_despesa_veiculo)
        .with_for_update()
        .one_or_none()
    )
    if despesa is None or despesa.cancelado:
        raise ValueError("A despesa do veículo não existe ou foi cancelada.")
    return despesa


def _validar_motivo(motivo):
    motivo = (motivo or "").strip()
    if len(motivo) < 6:
        raise ValueError("Informe uma justificativa com pelo menos 6 caracteres.")
    return motivo[:200]


def _dados_financeiros(despesa):
    return {
        "id_fornecedor": despesa.id_fornecedor,
        "tipo_despesa": despesa.tipo_despesa,
        "descricao_detalhe": despesa.descricao_detalhe,
        "quantidade": despesa.quantidade,
        "valor_unitario": despesa.valor_unitario,
        "valor_total": despesa.valor_total,
        "data_despesa": despesa.data_despesa,
    }


def atribuir_despesa_veiculo(
    session, id_despesa_veiculo, tipo_destino, id_destino, motivo,
    confirmar_despesa_distinta=False,
):
    """Move financeiramente um gasto pendente sem duplicar o combustível.

    O chamador controla commit/rollback e invalida os caches depois do commit.
    """
    motivo = _validar_motivo(motivo)
    origem = _origem_ativa(session, id_despesa_veiculo)
    if origem.id_despesa_viagem_destino or origem.id_despesa_ciclo_destino:
        raise ValueError("Esta despesa já foi atribuída. Faça o estorno antes de atribuí-la novamente.")
    if tipo_destino not in {"Frete", "Ciclo"}:
        raise ValueError("Destino inválido: selecione Frete ou Ciclo.")

    dados = _dados_financeiros(origem)
    abastecimento = session.query(Abastecimento).filter_by(
        id_despesa_veiculo=id_despesa_veiculo,
    ).one_or_none()
    dados_conferencia = {
        **dados,
        "id_veiculo_abast": origem.id_veiculo,
        "odometro_abastecimento": abastecimento.odometro if abastecimento else None,
    }
    if tipo_destino == "Frete":
        frete = session.query(Viagem).filter_by(id_viagem=id_destino).one_or_none()
        if frete is None or frete.id_veiculo != origem.id_veiculo:
            raise ValueError("Selecione um frete salvo que utilize o mesmo veículo da despesa.")
        duplicada = session.query(ViagemDespesa).filter_by(
            id_viagem=id_destino,
            tipo_despesa=origem.tipo_despesa,
            descricao_detalhe=origem.descricao_detalhe,
            data_despesa=origem.data_despesa,
            valor_total=origem.valor_total,
        ).first()
        if duplicada:
            raise ValueError("Há uma despesa aparentemente igual neste frete. Confira antes de atribuir.")
        cruzadas = procurar_semelhancas_cruzadas(
            session, "Frete", frete.id_ciclo, dados_conferencia,
        )
        if cruzadas and not confirmar_despesa_distinta:
            raise ValueError(
                "Existe despesa semelhante já contabilizada no ciclo "
                f"(lançamento #{cruzadas[0]['id_lancamento']}). Confira os comprovantes "
                "e confirme explicitamente se é outro custo antes de atribuir."
            )
        lancamento = ViagemDespesa(
            id_viagem=id_destino,
            odometro_abastecimento=abastecimento.odometro if abastecimento else None,
            **dados,
        )
        session.add(lancamento)
        session.flush()
        origem.id_despesa_viagem_destino = lancamento.id_despesa
        id_lancamento = lancamento.id_despesa
    else:
        ciclo = session.query(CicloOperacional).filter_by(id_ciclo=id_destino).one_or_none()
        if ciclo is None or not session.query(Viagem).filter_by(
            id_ciclo=id_destino, id_veiculo=origem.id_veiculo,
        ).first():
            raise ValueError("Selecione um ciclo salvo com ao menos um frete do mesmo veículo.")
        duplicada = session.query(CicloDespesa).filter_by(
            id_ciclo=id_destino,
            tipo_despesa=origem.tipo_despesa,
            descricao_detalhe=origem.descricao_detalhe,
            data_despesa=origem.data_despesa,
            valor_total=origem.valor_total,
            cancelado=False,
        ).first()
        if duplicada:
            raise ValueError("Há uma despesa aparentemente igual neste ciclo. Confira antes de atribuir.")
        cruzadas = procurar_semelhancas_cruzadas(
            session, "Ciclo", id_destino, dados_conferencia,
        )
        if cruzadas and not confirmar_despesa_distinta:
            raise ValueError(
                "Existe despesa semelhante já contabilizada em um frete do ciclo "
                f"(lançamento #{cruzadas[0]['id_lancamento']}). Confira os comprovantes "
                "e confirme explicitamente se é outro custo antes de atribuir."
            )
        lancamento = CicloDespesa(id_ciclo=id_destino, **dados)
        session.add(lancamento)
        session.flush()
        origem.id_despesa_ciclo_destino = lancamento.id_despesa_ciclo
        id_lancamento = lancamento.id_despesa_ciclo

    origem.data_atribuicao = date.today()
    session.add(VeiculoDespesaAtribuicao(
        id_despesa_veiculo=id_despesa_veiculo,
        acao="Atribuição",
        tipo_destino=tipo_destino,
        id_destino=id_destino,
        id_lancamento_destino=id_lancamento,
        motivo=motivo,
    ))
    return id_lancamento


def estornar_atribuicao_veiculo(session, id_despesa_veiculo, motivo):
    """Devolve o valor ao estado pendente, sem apagar a trilha de eventos.

    O combustível operacional continua ligado à origem e não é criado de novo.
    """
    motivo = _validar_motivo(motivo)
    origem = _origem_ativa(session, id_despesa_veiculo)
    id_desp_viagem = origem.id_despesa_viagem_destino
    id_desp_ciclo = origem.id_despesa_ciclo_destino
    if not id_desp_viagem and not id_desp_ciclo:
        raise ValueError("A despesa já está pendente e não possui atribuição a estornar.")

    if id_desp_viagem:
        destino = session.query(ViagemDespesa).filter_by(id_despesa=id_desp_viagem).one_or_none()
        if destino is None:
            raise ValueError("Despesa do frete não encontrada: confira a integridade antes do estorno.")
        tipo_destino, id_destino, id_lancamento = "Frete", destino.id_viagem, destino.id_despesa
        origem.id_despesa_viagem_destino = None
        session.flush()
        session.delete(destino)
    else:
        destino = session.query(CicloDespesa).filter_by(id_despesa_ciclo=id_desp_ciclo).one_or_none()
        if destino is None or destino.cancelado:
            raise ValueError("Despesa do ciclo indisponível: confira a integridade antes do estorno.")
        tipo_destino, id_destino, id_lancamento = "Ciclo", destino.id_ciclo, destino.id_despesa_ciclo
        destino.cancelado = True
        destino.data_cancelamento = date.today()
        destino.motivo_cancelamento = f"Estorno de atribuição: {motivo}"[:200]
        origem.id_despesa_ciclo_destino = None

    origem.data_atribuicao = None
    session.add(VeiculoDespesaAtribuicao(
        id_despesa_veiculo=id_despesa_veiculo,
        acao="Estorno",
        tipo_destino=tipo_destino,
        id_destino=id_destino,
        id_lancamento_destino=id_lancamento,
        motivo=motivo,
    ))
    return id_lancamento
