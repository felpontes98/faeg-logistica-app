"""Identificadores e vínculos de coleta em banco SQLite isolado."""
import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from database.connection import Base, SessionLocal, engine
from database.identificacao_fretes import (
    codigo_frete, previsualizar_frete, reservar_identificadores,
    validar_vinculo_saida, ciclo_existente_unico,
)
from database.models import CicloOperacional, Cliente, Motorista, Veiculo, Viagem
from database.saidas_operacionais import salvar_saida, consultar_saidas, resumo_saidas


@pytest.fixture
def cadastro():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        c = Cliente(razao_social="Cliente Teste", cnpj_cpf="11144477735")
        v = Veiculo(descricao_marca="Van Teste", placa="TESTEA1")
        v2 = Veiculo(descricao_marca="Outro veículo", placa="TESTEB2")
        m = Motorista(nome_completo="Motorista Teste", cpf="11144477735", cnh_numero="CNHTESTE")
        db.add_all((c, v, v2, m))
        db.flush()
        ciclo = CicloOperacional(id_cliente=c.id_cliente, nome_operacao="Ciclo-02")
        outro = CicloOperacional(id_cliente=c.id_cliente, nome_operacao="Ciclo-03")
        db.add_all((ciclo, outro))
        db.commit()
        ids = c.id_cliente, v.id_veiculo, v2.id_veiculo, m.id_motorista, ciclo.id_ciclo, outro.id_ciclo
    yield ids
    Base.metadata.drop_all(engine)


def _frete(session, dados, *, codigo, fv, cid, vid, sid=None):
    cli, _, _, mot, _, _ = dados
    frete = Viagem(
        codigo_viagem=codigo, id_frete_externo=fv, id_ciclo=cid,
        id_motorista=mot, id_veiculo=vid,
        id_local_coleta=1, id_local_entrega=1,
        id_saida_coleta=sid,
    )
    session.add(frete)
    session.flush()
    return frete


def test_formato_continuo_e_previa_sem_ano():
    assert codigo_frete(11) == "FV000000011"
    assert codigo_frete(107) == "FV000000107"
    assert previsualizar_frete("V11") == "FV000000011"
    assert previsualizar_frete("V-11") == ""


def test_varios_fretes_uma_saida_sem_duplicar_km(cadastro):
    cli, vid, v2, mot, cid, outro = cadastro
    with SessionLocal() as db:
        s1 = salvar_saida(db, id_ciclo=cid, id_veiculo=vid, descricao="Três coletas", km_planejado_manual=90)
        s2 = salvar_saida(db, id_ciclo=cid, id_veiculo=vid, descricao="Duas coletas", km_planejado_manual=70)
        ids_fretes = []
        for n, saida in [(11, s1), (12, s1), (13, s1), (14, s2), (15, s2)]:
            frete = _frete(db, cadastro, codigo=f"V{n}", fv=codigo_frete(n), cid=cid, vid=vid, sid=saida)
            ids_fretes.append(frete.id_viagem)
        db.commit()
        db.expire_all()
        assert len(db.get(Viagem, ids_fretes[0]).saida_coleta.fretes_coletados) == 3
        assert len(db.get(Viagem, ids_fretes[-1]).saida_coleta.fretes_coletados) == 2
        assert resumo_saidas(consultar_saidas(db, cid))["km_planejado"] == 160
        assert db.query(Viagem).count() == 5
        assert db.query(CicloOperacional).count() == 2


def test_edicao_do_vinculo_nao_cria_frete_ou_saida(cadastro):
    cli, vid, v2, mot, cid, outro = cadastro
    with SessionLocal() as db:
        s1 = salvar_saida(db, id_ciclo=cid, id_veiculo=vid, descricao="Primeira", km_planejado_manual=20)
        s2 = salvar_saida(db, id_ciclo=cid, id_veiculo=vid, descricao="Segunda", km_planejado_manual=30)
        f = _frete(db, cadastro, codigo="V11", fv="FV000000011", cid=cid, vid=vid, sid=s1)
        f.id_saida_coleta = validar_vinculo_saida(db, f"s:{s2}", cid, vid)
        db.commit()
        assert db.get(Viagem, f.id_viagem).id_saida_coleta == s2
        assert db.query(Viagem).count() == 1
        assert resumo_saidas(consultar_saidas(db, cid))["km_planejado"] == 50


def test_vinculo_recusa_outro_ciclo_e_outro_veiculo(cadastro):
    cli, vid, v2, mot, cid, outro = cadastro
    with SessionLocal() as db:
        s1 = salvar_saida(db, id_ciclo=cid, id_veiculo=vid, descricao="Coleta")
        with pytest.raises(ValueError, match="não pertence"):
            validar_vinculo_saida(db, f"s:{s1}", outro, vid)
        with pytest.raises(ValueError, match="diferente"):
            validar_vinculo_saida(db, f"s:{s1}", cid, v2)
        with pytest.raises(ValueError, match="não é válida"):
            validar_vinculo_saida(db, "s:abc", cid, vid)


def test_ciclo_homonimo_nao_selecionado_automaticamente(cadastro):
    cli, vid, v2, mot, cid, outro = cadastro
    with SessionLocal() as db:
        assert ciclo_existente_unico(db, " ciclo-02 ").id_ciclo == cid
        db.add(CicloOperacional(id_cliente=cli, nome_operacao="CICLO-02"))
        db.flush()
        with pytest.raises(ValueError, match="históricos"):
            ciclo_existente_unico(db, "Ciclo-02")


def test_codigo_automatico_preserva_legacy_e_evita_colisoes(cadastro):
    cli, vid, v2, mot, cid, outro = cadastro
    with SessionLocal() as db:
        _frete(db, cadastro, codigo="V10", fv="FV260000010", cid=cid, vid=vid)
        _frete(db, cadastro, codigo="V11", fv="FV000000012", cid=cid, vid=vid)
        db.flush()
        # FV12 ocupado por registro legado, então o par pula para V13/FV13.
        assert reservar_identificadores(db) == ("V13", "FV000000013")
        novo = _frete(db, cadastro, codigo="V13", fv="FV000000013", cid=outro, vid=vid)
        db.commit()
        assert db.query(Viagem).filter(Viagem.id_frete_externo == "FV260000010").count() == 1
        assert db.get(Viagem, novo.id_viagem).id_ciclo == outro


def test_saida_provisoria_valida_sem_criar_destino_novo(cadastro):
    cli, vid, v2, mot, cid, outro = cadastro
    provisorias = [{"id": "unico-abc", "id_veiculo": vid, "descricao": "Coletas"}]
    with SessionLocal() as db:
        assert validar_vinculo_saida(db, "p:unico-abc", cid, vid, provisoria=provisorias) == 0
        with pytest.raises(ValueError, match="diferente"):
            validar_vinculo_saida(db, "p:unico-abc", cid, v2, provisoria=provisorias)


def test_alterar_veiculo_de_saida_com_fretes_vinculados_exige_correcao(cadastro):
    cli, vid, v2, mot, cid, outro = cadastro
    with SessionLocal() as db:
        sid = salvar_saida(db, id_ciclo=cid, id_veiculo=vid, descricao="Coleta")
        _frete(db, cadastro, codigo="V11", fv="FV000000011", cid=cid, vid=vid, sid=sid)
        db.flush()
        with pytest.raises(ValueError, match="Revise esses vínculos"):
            salvar_saida(db, id_ciclo=cid, id_veiculo=v2, id_saida=sid, descricao="Coleta")
