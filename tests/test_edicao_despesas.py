"""Correções de custo, destino atribuído e abastecimento em banco isolado."""

import os
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from database.atribuicao_despesas import atribuir_despesa_veiculo, estornar_atribuicao_veiculo
from database.connection import Base
from database.despesas import (
    atualizar_rascunho, carregar_lancamento, consultar_edicoes, editar_despesa, registrar_despesa,
)
from database.models import (
    Abastecimento, CicloDespesa, CicloOperacional, Cliente, DespesaEdicao,
    Local, Motorista, Veiculo, VeiculoDespesa, Viagem, ViagemDespesa,
)


@pytest.fixture
def db():
    motor = create_engine("sqlite://")
    @event.listens_for(motor, "connect")
    def habilitar_fks(conexao, _):
        conexao.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(motor)
    with Session(motor) as session:
        cliente = Cliente(razao_social="Cliente de teste", cnpj_cpf="001")
        veiculo = Veiculo(descricao_marca="Van", placa="TST0001")
        motorista = Motorista(nome_completo="Motorista de teste", cpf="001", cnh_numero="001")
        local = Local(nome_local="Base")
        session.add_all([cliente, veiculo, motorista, local])
        session.flush()
        ciclo = CicloOperacional(id_cliente=cliente.id_cliente, nome_operacao="Coletas")
        session.add(ciclo)
        session.flush()
        session.add(Viagem(id_ciclo=ciclo.id_ciclo, id_motorista=motorista.id_motorista,
                           id_veiculo=veiculo.id_veiculo, id_local_coleta=local.id_local,
                           id_local_entrega=local.id_local, codigo_viagem="V1", tipo_viagem="Ciclo"))
        session.commit()
        yield session
    motor.dispose()


def diesel():
    return dict(tipo_despesa="Posto de Combustível", descricao_detalhe="Posto A",
                quantidade=10, valor_unitario=6.2345, data_despesa=date(2026, 11, 25),
                odometro_abastecimento=1000, id_veiculo_abast=1, id_fornecedor=None)


@pytest.mark.parametrize("tipo", ["Frete", "Ciclo", "Veículo"])
def test_correcao_categoria_odometro_e_concorrencia(db, tipo):
    ident = registrar_despesa(db, tipo, 1, diesel())
    db.commit()
    def versao():
        return carregar_lancamento(db, tipo, ident).versao()
    inicial = versao()
    dados = dict(diesel(), tipo_despesa="Abast. ARLA", quantidade=2, odometro_abastecimento=1010)
    assert editar_despesa(db, tipo, ident, inicial, dados)
    db.commit()
    ab = db.query(Abastecimento).one()
    assert (ab.tipo_combustivel, ab.valor_total, ab.odometro) == ("ARLA", Decimal("12.47"), 1010)
    with pytest.raises(ValueError, match="mudou"):
        editar_despesa(db, tipo, ident, inicial, diesel())
    assert not editar_despesa(db, tipo, ident, versao(), dados)
    editar_despesa(db, tipo, ident, versao(), dict(dados, tipo_despesa="Pedágio"))
    db.commit()
    assert ab.cancelado
    editar_despesa(db, tipo, ident, versao(), diesel())
    db.commit()
    assert not ab.cancelado and db.query(Abastecimento).one().id_abastecimento == ab.id_abastecimento
    assert db.query(DespesaEdicao).count() == 3


@pytest.mark.parametrize("tipo,modelo", [("Frete", ViagemDespesa), ("Ciclo", CicloDespesa)])
def test_editar_pelo_destino_e_estornar(db, tipo, modelo):
    origem = registrar_despesa(db, "Veículo", 1, diesel())
    db.commit()
    destino = atribuir_despesa_veiculo(db, origem, tipo, 1, "Comprovante conferido")
    db.commit()
    versao = carregar_lancamento(db, tipo, destino).versao()
    editar_despesa(db, tipo, destino, versao, dict(diesel(), quantidade=20))
    db.commit()
    assert db.get(modelo, destino).valor_total == db.get(VeiculoDespesa, origem).valor_total == Decimal("124.69")
    assert db.query(Abastecimento).one().litros == 20
    assert {linha["Campo"] for linha in consultar_edicoes(db)} == {"Total", "Quantidade"}
    estornar_atribuicao_veiculo(db, origem, "Custo volta ao veículo")
    db.commit()
    assert db.get(modelo, destino).cancelado
    with pytest.raises(ValueError, match="cancelada"):
        carregar_lancamento(db, tipo, destino)
    assert carregar_lancamento(db, "Veículo", origem).destino_financeiro() == ("Veículo", 1)


def test_duplicidade_exige_nova_conferencia(db):
    ident = registrar_despesa(db, "Ciclo", 1, diesel())
    frete = registrar_despesa(db, "Frete", 1, dict(diesel(), quantidade=12))
    db.commit()
    versao = carregar_lancamento(db, "Frete", frete).versao()
    with pytest.raises(ValueError, match="comprovantes"):
        editar_despesa(db, "Frete", frete, versao, diesel())
    assert db.query(DespesaEdicao).count() == 0
    editar_despesa(db, "Frete", frete, versao, diesel(), [ident])
    db.commit()
    assert db.query(DespesaEdicao).count() == 1


def test_rascunho_preserva_item_e_detecta_conflito():
    itens = []
    atualizar_rascunho(itens, dict(diesel(), destino_temp="ciclo"))
    inicial = itens[0].copy()
    atualizar_rascunho(itens, dict(diesel(), quantidade=12), indice=0, anterior=inicial)
    assert len(itens) == 1 and itens[0]["destino_temp"] == "ciclo" and itens[0]["valor_total"] == 74.81
    with pytest.raises(ValueError, match="mudou"):
        atualizar_rascunho(itens, diesel(), indice=0, anterior=inicial)


def test_edicao_de_descricao_conserva_arredondamento_historico(db):
    dados = diesel()
    ident = registrar_despesa(db, "Frete", 1, dados)
    db.commit()
    db.get(ViagemDespesa, ident).valor_total = Decimal("62.34")
    db.query(Abastecimento).one().valor_total = Decimal("62.34")
    db.commit()
    versao = carregar_lancamento(db, "Frete", ident).versao()
    editar_despesa(db, "Frete", ident, versao, dict(dados, descricao_detalhe="Posto B"))
    db.commit()
    assert db.get(ViagemDespesa, ident).valor_total == Decimal("62.34")
    assert db.query(Abastecimento).one().valor_total == Decimal("62.34")
    assert [linha["Campo"] for linha in consultar_edicoes(db)] == ["Descrição"]
