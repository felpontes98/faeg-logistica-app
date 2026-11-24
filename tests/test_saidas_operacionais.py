"""Executar: DATABASE_URL=sqlite:///:memory: python -m pytest -q tests/test_saidas_operacionais.py
Não se conecta ao Neon. Testa modelos novos e regras de quilometragem.
"""
import os
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

from datetime import date
from decimal import Decimal

import pytest
from database.connection import Base, SessionLocal, engine
from database.models import Cliente, CicloOperacional, Veiculo, SaidaOperacional, TrechoOperacional, ViagemDespesa
from database.saidas_operacionais import (
    salvar_saida, salvar_trecho, consultar_saidas,
    resumo_saidas, estimar_consumo, validar_saida,
)


@pytest.fixture
def db():
    Base.metadata.create_all(engine)
    session = SessionLocal()
    try:
        cli = Cliente(razao_social="CLIENTE TESTE", cnpj_cpf="00.000.000/0001-00")
        veh = Veiculo(descricao_marca="FAEG VAN", placa="TESTE000")
        session.add_all([cli, veh]); session.flush()
        ciclo = CicloOperacional(nome_operacao="C-TESTE", id_cliente=cli.id_cliente)
        session.add(ciclo);session.commit()
        yield session, ciclo.id_ciclo, veh.id_veiculo
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def test_varias_saidas_na_mesma_operacao_sem_somar_duas_vezes(db):
    session, cid, vid = db
    s1 = salvar_saida(session, id_ciclo=cid, id_veiculo=vid, descricao="Coletas preparatórias",
                     km_planejado_manual=150, odometro_inicial=5000, odometro_final=5160)
    s2 = salvar_saida(session, id_ciclo=cid, id_veiculo=vid, descricao="Entrega e retorno",
                     km_planejado_manual=500, odometro_inicial=5160, odometro_final=5700)
    session.commit()
    saidas = consultar_saidas(session,cid)
    rz = resumo_saidas(saidas)
    assert rz["qtd_saidas"] == 2
    assert rz["km_planejado"] == 650.0
    assert rz["km_real"] == 700.0
    assert rz["completo"] is True


def test_trechos_substituem_plano_manual_sem_dupla_soma(db):
    session,cid,vid=db
    sid=salvar_saida(session,id_ciclo=cid,id_veiculo=vid,descricao="Coletas",km_planejado_manual=777,
                   odometro_inicial=100,odometro_final=200)
    salvar_trecho(session,id_saida=sid,tipo_trecho="Coleta",origem="Suzano",destino="Atibaia",km_planejado=60)
    salvar_trecho(session,id_saida=sid,tipo_trecho="Retorno",origem="Atibaia",destino="Suzano",km_planejado=70)
    session.commit()
    rz=resumo_saidas(consultar_saidas(session,cid))
    assert rz['km_planejado']==130
    assert rz['km_real']==100
    assert any('prevalece' in x for x in rz['avisos'])


def test_odometros_ausentes_ou_sobrepostos_nao_viram_zero(db):
    session,cid,vid=db
    salvar_saida(session,id_ciclo=cid,id_veiculo=vid,descricao="A",km_planejado_manual=50,
               odometro_inicial=1000,odometro_final=1060)
    salvar_saida(session,id_ciclo=cid,id_veiculo=vid,descricao="B",km_planejado_manual=50,
               odometro_inicial=1050,odometro_final=1100)
    session.commit()
    rz=resumo_saidas(consultar_saidas(session,cid))
    assert rz['km_real'] is None and rz['completo'] is False
    assert any('sobrepostos' in x for x in rz['avisos'])
    session.query(SaidaOperacional).filter_by(descricao='B').one().odometro_final=None
    session.commit()
    rz=resumo_saidas(consultar_saidas(session,cid))
    assert rz['km_real'] is None


def test_estimar_diesel_nao_e_lancamento_financeiro(db):
    session,cid,vid=db
    assert estimar_consumo(600,12,6)=={'litros_estimados':50.,'custo_estimado':300.}
    assert estimar_consumo(None,12,6) is None
    assert estimar_consumo(600,0,6) is None
    # Apuração não faz inserts em ViagemDespesa.
    assert session.query(ViagemDespesa).count() == 0


def test_validacao_datas_odometros_e_estrangeiros(db):
    session,cid,vid=db
    with pytest.raises(ValueError, match='anterior'):
        salvar_saida(session,id_ciclo=cid,id_veiculo=vid,descricao='A',
                    data_inicio=date(2026,11,21),data_fim=date(2026,11,20))
    with pytest.raises(ValueError, match='menor'):
        salvar_saida(session,id_ciclo=cid,id_veiculo=vid,descricao='A',
                    odometro_inicial=500,odometro_final=480)
    with pytest.raises(ValueError, match='não encontrado'):
        salvar_saida(session,id_ciclo=99999,id_veiculo=vid,descricao='A')


def test_legacy_cycle_fields_remain_unchanged(db):
    session,cid,vid=db
    ciclo=session.get(CicloOperacional,cid)
    ciclo.km_deslocamentos_operacionais=120
    ciclo.km_saida_entre_coletas=60
    ciclo.km_retorno_operacional=60
    session.commit()
    salvar_saida(session,id_ciclo=cid,id_veiculo=vid,descricao='Trecho diferente',km_planejado_manual=200)
    session.commit()
    session.refresh(ciclo)
    assert float(ciclo.km_deslocamentos_operacionais)==120
    assert float(ciclo.km_saida_entre_coletas)==60
    assert float(ciclo.km_retorno_operacional)==60
