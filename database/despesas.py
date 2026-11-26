"""Registro e correção de despesas e do abastecimento associado."""

from dataclasses import dataclass
from datetime import date, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import NamedTuple

from sqlalchemy import inspect

from database.conferencia_duplicidades import COMBUSTIVEIS, procurar_semelhancas_cruzadas
from database.models import (
    Abastecimento, CicloDespesa, CicloOperacional, DespesaEdicao, Fornecedor,
    Veiculo, VeiculoDespesa, Viagem, ViagemDespesa,
)


class Vinculo(NamedTuple):
    modelo: type
    titular: type
    campo_titular: str
    campo_origem: str


VINCULOS = {
    "Frete": Vinculo(ViagemDespesa, Viagem, "id_viagem", "id_despesa_viagem"),
    "Ciclo": Vinculo(CicloDespesa, CicloOperacional, "id_ciclo", "id_despesa_ciclo"),
    "Veículo": Vinculo(VeiculoDespesa, Veiculo, "id_veiculo", "id_despesa_veiculo"),
}
CAMPOS_FINANCEIROS = (
    "tipo_despesa", "descricao_detalhe", "data_despesa", "id_fornecedor",
    "quantidade", "valor_unitario", "valor_total",
)


def valores_despesa(quantidade, unitario, combustivel, anteriores=None):
    """Arredonda nas precisões de armazenamento antes de calcular o total."""
    qtd = Decimal(str(quantidade)).quantize(Decimal("0.01"), ROUND_HALF_UP)
    preco_informado = Decimal(str(unitario))
    if anteriores and anteriores.get("valor_unitario") is not None:
        preco_anterior = Decimal(str(anteriores["valor_unitario"]))
        if preco_anterior == preco_informado:
            if anteriores.get("quantidade") is not None and qtd == Decimal(str(anteriores["quantidade"])):
                total_anterior = anteriores.get("valor_total")
                if total_anterior is not None and total_anterior > 0:
                    # Um ajuste de descrição ou odômetro conserva o total do comprovante histórico.
                    return float(qtd), float(preco_anterior), float(total_anterior)
    precisao = Decimal("0.0001") if combustivel else Decimal("0.01")
    preco = Decimal(str(unitario)).quantize(precisao, ROUND_HALF_UP)
    total = (qtd * preco).quantize(Decimal("0.01"), ROUND_HALF_UP)
    return float(qtd), float(preco), float(total)


def validar_dados(dados, anteriores=None):
    if not dados["tipo_despesa"] or not isinstance(dados["data_despesa"], date):
        raise ValueError("Informe a categoria e a data da despesa.")
    combustivel = dados["tipo_despesa"] in COMBUSTIVEIS
    qtd, preco, total = valores_despesa(dados["quantidade"], dados["valor_unitario"], combustivel, anteriores)
    if min(qtd, preco, total) <= 0:
        raise ValueError("Informe quantidade e preço que resultem em pelo menos R$ 0,01.")
    if qtd >= 10**10 or preco >= 10**8 or total >= 10**10:
        raise ValueError("Quantidade, preço ou total ultrapassam a capacidade do lançamento.")
    if combustivel and not dados.get("id_veiculo_abast"):
        raise ValueError("Selecione o veículo abastecido.")
    odometro = dados.get("odometro_abastecimento")
    if odometro is not None and not 0 <= odometro <= 2147483647:
        raise ValueError("Confira a leitura do odômetro.")
    return {**dados, "quantidade": qtd, "valor_unitario": preco, "valor_total": total,
            "odometro_abastecimento": (odometro or None) if combustivel else None,
            "id_veiculo_abast": dados.get("id_veiculo_abast") if combustivel else None}


def _atualizar_abastecimento(session, registro, dados, campo_origem, id_origem):
    if dados["tipo_despesa"] not in COMBUSTIVEIS:
        if registro is not None and not registro.cancelado:
            registro.cancelado = True
            registro.data_cancelamento = date.today()
            registro.motivo_cancelamento = "Categoria da despesa alterada."
        return
    if not dados.get("id_veiculo_abast"):
        raise ValueError("Selecione o veículo abastecido.")
    if registro is None:
        registro = Abastecimento(**{campo_origem: id_origem})
        session.add(registro)
    registro.id_veiculo = dados["id_veiculo_abast"]
    registro.id_fornecedor = dados.get("id_fornecedor")
    registro.data_abastecimento = dados["data_despesa"]
    registro.tipo_combustivel = "ARLA" if dados["tipo_despesa"] == "Abast. ARLA" else "Diesel"
    registro.odometro = dados.get("odometro_abastecimento")
    registro.litros = dados["quantidade"]
    registro.preco_litro = dados["valor_unitario"]
    registro.valor_total = dados["valor_total"]
    registro.cancelado = False
    registro.data_cancelamento = None
    registro.motivo_cancelamento = None


def registrar_abastecimento_do_lancamento(session, dados, campo_origem, id_origem):
    _atualizar_abastecimento(session, None, dados, campo_origem, id_origem)


@dataclass
class Lancamento:
    tipo: str
    origem: object
    abastecimento: Abastecimento | None
    tipo_atribuido: str | None = None
    atribuido: object | None = None

    @property
    def id_origem(self):
        return inspect(self.origem).identity[0]

    def referencia(self):
        return self.tipo, getattr(self.origem, VINCULOS[self.tipo].campo_titular)

    def destino_financeiro(self):
        if self.atribuido is None:
            return self.referencia()
        return self.tipo_atribuido, getattr(self.atribuido, VINCULOS[self.tipo_atribuido].campo_titular)

    def dados(self):
        ab = self.abastecimento
        combustivel = self.origem.tipo_despesa in COMBUSTIVEIS
        veiculo = odometro = None
        if combustivel:
            if ab is not None and not ab.cancelado:
                veiculo, odometro = ab.id_veiculo, ab.odometro
            elif self.tipo == "Frete":
                veiculo, odometro = self.origem.viagem.id_veiculo, self.origem.odometro_abastecimento
            elif self.tipo == "Veículo":
                veiculo = self.origem.id_veiculo
        dados = {campo: getattr(self.origem, campo) for campo in CAMPOS_FINANCEIROS}
        return {**dados, "id_veiculo_abast": veiculo, "odometro_abastecimento": odometro}

    def vinculos_historico(self):
        chaves = {VINCULOS[self.tipo].campo_origem: self.id_origem}
        if self.atribuido is not None:
            chaves[VINCULOS[self.tipo_atribuido].campo_origem] = inspect(self.atribuido).identity[0]
        return chaves

    def versao(self):
        # O destino atribuído e o titular também podem mudar entre a abertura e a gravação.
        return (self.vinculos_historico(), self.referencia(), self.destino_financeiro(), self.dados())


def carregar_lancamento(session, tipo, id_despesa, *, bloquear=False):
    """Localiza a origem e seu destino. Nas gravações bloqueamos primeiro a origem."""
    if tipo not in VINCULOS:
        raise ValueError("Tipo de lançamento inválido.")
    origem = None
    if tipo != "Veículo":
        campo = VINCULOS[tipo].campo_origem + "_destino"
        consulta = session.query(VeiculoDespesa).filter_by(**{campo: id_despesa})
        if bloquear:
            consulta = consulta.with_for_update()
        origem = consulta.one_or_none()
    if origem is None:
        origem = session.get(VINCULOS[tipo].modelo, id_despesa, with_for_update=bloquear)
    else:
        tipo = "Veículo"
    if origem is None or origem.cancelado:
        raise ValueError("A despesa foi cancelada ou deixou de existir. Reabra a lista de despesas.")
    vinculo = VINCULOS[tipo]
    id_origem = inspect(origem).identity[0]
    abastecimento = session.query(Abastecimento).filter_by(**{vinculo.campo_origem: id_origem}).one_or_none()
    lancamento = Lancamento(tipo, origem, abastecimento)
    if tipo == "Veículo":
        for tipo_destino in ("Frete", "Ciclo"):
            destino = VINCULOS[tipo_destino]
            id_destino = getattr(origem, destino.campo_origem + "_destino")
            if id_destino is not None:
                registro = session.get(destino.modelo, id_destino, with_for_update=bloquear)
                if registro is None or registro.cancelado:
                    raise ValueError("Confira o vínculo da despesa antes de editar.")
                lancamento.tipo_atribuido = tipo_destino
                lancamento.atribuido = registro
    return lancamento


def _validar_titular(session, tipo, id_titular, dados):
    titular = session.get(VINCULOS[tipo].titular, id_titular)
    if titular is None:
        raise ValueError("O destino da despesa deixou de existir.")
    if dados.get("id_fornecedor") and session.get(Fornecedor, dados["id_fornecedor"]) is None:
        raise ValueError("Selecione um fornecedor cadastrado.")
    placa = dados.get("id_veiculo_abast")
    if placa and session.get(Veiculo, placa) is None:
        raise ValueError("Selecione um veículo cadastrado.")
    if placa and tipo in {"Frete", "Veículo"} and titular.id_veiculo != placa:
        raise ValueError("O veículo abastecido deve corresponder ao veículo do lançamento.")
    return titular


def _verificar_repeticao(session, tipo, id_titular, dados, atual=None):
    vinculo = VINCULOS[tipo]
    filtros = {vinculo.campo_titular: id_titular, "cancelado": False,
               "tipo_despesa": dados["tipo_despesa"], "data_despesa": dados["data_despesa"],
               "valor_total": dados["valor_total"]}
    if tipo == "Frete":
        filtros["quantidade"] = dados["quantidade"]
        if dados["tipo_despesa"] in COMBUSTIVEIS:
            filtros["odometro_abastecimento"] = dados.get("odometro_abastecimento")
        else:
            filtros.update(id_fornecedor=dados.get("id_fornecedor"), descricao_detalhe=dados["descricao_detalhe"])
    else:
        filtros["descricao_detalhe"] = dados["descricao_detalhe"]
    consulta = session.query(vinculo.modelo).filter_by(**filtros)
    if atual is not None:
        chave = inspect(vinculo.modelo).primary_key[0]
        consulta = consulta.filter(chave != inspect(atual).identity[0])
    if consulta.first() is not None:
        raise ValueError("Já existe uma despesa com estes dados no destino. Confira o comprovante.")


def coincidencias(session, tipo, id_titular, dados):
    if tipo == "Veículo" or not id_titular:
        return []
    id_ciclo = id_titular
    if tipo == "Frete":
        id_ciclo = session.query(Viagem.id_ciclo).filter_by(id_viagem=id_titular).scalar()
    return procurar_semelhancas_cruzadas(session, tipo, id_ciclo, dados)


def _conferir_comprovantes(session, tipo, titular, dados, confirmados):
    encontrados = coincidencias(session, tipo, titular, dados)
    if any(d["id_lancamento"] not in confirmados for d in encontrados):
        raise ValueError("Confira a despesa semelhante no ciclo e confirme se os comprovantes são distintos.")


def _preencher(registro, dados):
    for campo in CAMPOS_FINANCEIROS:
        setattr(registro, campo, dados[campo])
    if isinstance(registro, ViagemDespesa):
        registro.odometro_abastecimento = dados.get("odometro_abastecimento")


def registrar_despesa(session, tipo, id_titular, dados, confirmados=()):
    dados = validar_dados(dados)
    _validar_titular(session, tipo, id_titular, dados)
    _verificar_repeticao(session, tipo, id_titular, dados)
    _conferir_comprovantes(session, tipo, id_titular, dados, confirmados)
    vinculo = VINCULOS[tipo]
    registro = vinculo.modelo(**{vinculo.campo_titular: id_titular})
    _preencher(registro, dados)
    session.add(registro)
    session.flush()
    id_despesa = inspect(registro).identity[0]
    registrar_abastecimento_do_lancamento(session, dados, vinculo.campo_origem, id_despesa)
    return id_despesa


def _dados_historico(dados):
    precisao = {"quantidade": 2, "valor_unitario": 4, "valor_total": 2}
    resultado = {}
    for campo in (*CAMPOS_FINANCEIROS, "id_veiculo_abast", "odometro_abastecimento"):
        valor = dados.get(campo)
        if campo in precisao and valor is not None:
            valor = f"{valor:.{precisao[campo]}f}"
        elif isinstance(valor, date):
            valor = valor.isoformat()
        resultado[campo] = valor
    return resultado


COLUNAS_EDICAO = ("Edição", "Data e hora (UTC)", "Despesa do frete", "Despesa do ciclo",
                  "Despesa do veículo", "Campo", "Anterior", "Atualizado")


def consultar_edicoes(session, limite=None):
    consulta = session.query(DespesaEdicao).order_by(DespesaEdicao.id_edicao.desc())
    if limite is not None:
        consulta = consulta.limit(limite)
    linhas = []
    rotulos = dict(zip((*CAMPOS_FINANCEIROS, "id_veiculo_abast", "odometro_abastecimento"),
                       ("Categoria", "Descrição", "Data", "Fornecedor (ID)", "Quantidade", "Preço unitário",
                        "Total", "Veículo abastecido (ID)", "Odômetro")))
    for edicao in consulta:
        data = edicao.data_edicao
        if data.tzinfo:
            data = data.astimezone(timezone.utc)
        for campo, antes in edicao.anterior.items():
            depois = edicao.atualizado[campo]
            if antes != depois:
                valores = (edicao.id_edicao, data.strftime("%d/%m/%Y %H:%M:%S"), edicao.id_despesa_viagem,
                           edicao.id_despesa_ciclo, edicao.id_despesa_veiculo, rotulos[campo], antes, depois)
                linhas.append(dict(zip(COLUNAS_EDICAO, valores)))
    return linhas


def editar_despesa(session, tipo, id_despesa, versao_aberta, dados, confirmados=()):
    lancamento = carregar_lancamento(session, tipo, id_despesa, bloquear=True)
    if lancamento.versao() != versao_aberta:
        raise ValueError("O lançamento mudou desde a abertura. Feche a edição e abra os dados atualizados.")
    anterior = lancamento.dados()
    dados = validar_dados(dados, anterior)
    origem, id_titular = lancamento.referencia()
    _validar_titular(session, origem, id_titular, dados)
    # Comparamos valores monetários à precisão do banco, inclusive no reenvio da tela.
    if _dados_historico(anterior) == _dados_historico(dados):
        return False
    _verificar_repeticao(session, origem, id_titular, dados, lancamento.origem)
    financeiro, id_financeiro = lancamento.destino_financeiro()
    if lancamento.atribuido is not None:
        _validar_titular(session, financeiro, id_financeiro, dados)
        _verificar_repeticao(session, financeiro, id_financeiro, dados, lancamento.atribuido)
    _conferir_comprovantes(session, financeiro, id_financeiro, dados, confirmados)
    if lancamento.atribuido is not None:
        _preencher(lancamento.atribuido, dados)
    _preencher(lancamento.origem, dados)
    _atualizar_abastecimento(session, lancamento.abastecimento, dados, VINCULOS[origem].campo_origem, lancamento.id_origem)
    session.add(DespesaEdicao(**lancamento.vinculos_historico(),
                              anterior=_dados_historico(anterior), atualizado=_dados_historico(dados)))
    return True


def atualizar_rascunho(despesas, dados, *, indice=None, anterior=None):
    """Mantém o índice e o vínculo do item até a publicação do frete."""
    dados = validar_dados(dados)
    if indice is not None and (not 0 <= indice < len(despesas) or despesas[indice] != anterior):
        raise ValueError("A lista do rascunho mudou. Abra novamente a despesa.")
    campos = ["tipo_despesa", "data_despesa", "quantidade", "valor_total"]
    if dados["tipo_despesa"] in COMBUSTIVEIS:
        campos.extend(("odometro_abastecimento", "id_veiculo_abast"))
    else:
        campos.extend(("descricao_detalhe", "id_fornecedor"))
    if any(i != indice and all(item.get(k) == dados.get(k) for k in campos)
           for i, item in enumerate(despesas)):
        raise ValueError("Esta despesa já está no rascunho.")
    if indice is None:
        despesas.append(dados)
    else:
        despesas[indice] = {**anterior, **dados}
