"""Testes sem acesso ao Neon: rascunho, saídas e custos separados por operação."""
import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from datetime import date

import pytest
from database.connection import Base, engine, SessionLocal
from database.models import Cliente, CicloOperacional, Veiculo, SaidaOperacional, RascunhoViagem, ViagemDespesa
from database.rascunhos import (empacotar_rascunho, abrir_rascunho,
                               salvar_rascunho, publicar_saidas_rascunho,
                               resumo_saidas_provisorias)
from database.saidas_operacionais import consultar_saidas, resumo_saidas


@pytest.fixture
def dados():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        cli = Cliente(razao_social="CONTRATANTE TESTE", cnpj_cpf="11122233344")
        van = Veiculo(descricao_marca="Expert", placa="TESTE29")
        db.add_all([cli, van]); db.flush()
        ciclo = CicloOperacional(id_cliente=cli.id_cliente, nome_operacao="CICLO 001")
        db.add(ciclo); db.commit()
        yield ciclo.id_ciclo, van.id_veiculo
    Base.metadata.drop_all(engine)


def _saidas(vid):
    return [
        dict(id_veiculo=vid, descricao="Coletas preparatórias", data_inicio=date(2026,11,21),
             data_fim=date(2026,11,21), odometro_inicial=50000, odometro_final=50180,
             km_saida_coletas=30., km_rota_principal=120., km_retorno_base=25.,
             km_planejado_manual=175., observacoes=""),
        dict(id_veiculo=vid, descricao="Entrega e retorno", data_inicio=date(2026,11,22),
             data_fim=date(2026,11,22), odometro_inicial=50180, odometro_final=51000,
             km_saida_coletas=20., km_rota_principal=750., km_retorno_base=40.,
             km_planejado_manual=810., observacoes=""),
    ]


def test_armazenar_recuperar_rascunho_incompleto_com_datas(dados):
    cid,vid = dados
    formulario = {"tipo_viagem": "Ciclo", "ciclo_nome": "CICLO 001",
                  "id_viagem_label": "V10", "data_op": date(2026,11,21),
                  "data_entrega": date(2026,11,25), "valor_negociado": 500.0}
    with SessionLocal() as db:
        rid = salvar_rascunho(db, id_rascunho=None, titulo="V10", form=formulario,
                              saidas=_saidas(vid), despesas=[])
        db.commit()
        salvo = db.get(RascunhoViagem, rid)
        dados_form, saidas, despesas = abrir_rascunho(salvo.conteudo_json)
        assert dados_form["data_op"] == date(2026,11,21)
        assert saidas[0]["data_inicio"] == date(2026,11,21)
        assert dados_form["valor_negociado"] == 500.0
        assert despesas == []
        assert db.query(ViagemDespesa).count() == 0


def test_duas_saidas_com_ciclo_comercial_um_km_fisico(dados):
    cid,vid = dados
    provis = _saidas(vid)
    pr = resumo_saidas_provisorias(provis)
    assert pr["km_planejado"] == 985.
    assert pr["km_real"] == 1000.
    with SessionLocal() as db:
        publicar_saidas_rascunho(db,cid,provis)
        db.commit()
        orig = db.query(SaidaOperacional).filter_by(id_ciclo=cid).all()
        assert len(orig)==2
        total = resumo_saidas(consultar_saidas(db,cid))
        assert total["km_planejado"] == 985.
        assert total["km_real"] == 1000.
        assert float(orig[0].km_saida_coletas) == 30.
        assert float(orig[0].km_retorno_base) == 25.
        assert db.query(ViagemDespesa).count() == 0


def test_rascunho_sem_odometro_final_eh_pendente(dados):
    cid,vid=dados
    saida=_saidas(vid)[:1]
    saida[0]["odometro_final"]=None
    resumo=resumo_saidas_provisorias(saida)
    assert resumo["km_planejado"]==175.
    assert resumo["km_real"] is None
    assert resumo["completo"] is False


def test_nao_permite_odometro_invertido(dados):
    from database.saidas_operacionais import validar_saida
    with pytest.raises(ValueError, match="menor"):
        validar_saida(dict(descricao="Retorno", odometro_inicial=900, odometro_final=500, km_planejado_manual=10))
