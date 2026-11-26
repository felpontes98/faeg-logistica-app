"""Teste completo do salvamento do ciclo em SQLite; nunca conecta ao Neon."""
import os,sys,types
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from datetime import date
os.environ["DATABASE_URL"]="sqlite:///:memory:"
class CacheDummy:
    def __call__(self,*args,**kwargs):
        return self.decorate(args[0]) if args and callable(args[0]) else self.decorate
    @staticmethod
    def decorate(fn):
        fn.clear=lambda:None
        return fn
st=types.ModuleType('streamlit')
st.session_state={}
st.cache_data=CacheDummy()
st.cache_resource=CacheDummy()
st.errors=[]
st.error=lambda msg:st.errors.append(msg)
st.warning=lambda *args,**kw:None
st.toast=lambda *args,**kw:None
st.rerun=lambda:None
sys.modules['streamlit']=st
from database.connection import Base,SessionLocal,engine
from database.models import (Motorista,Veiculo,Cliente,Local,CicloDespesa,Viagem,
                             SaidaOperacional,ViagemDespesa,Abastecimento,RascunhoViagem)
Base.metadata.create_all(engine)
with SessionLocal() as db:
    m=Motorista(nome_completo='Motorista Teste',cpf='99887766',cnh_numero='7654321')
    v=Veiculo(descricao_marca='Peugeot Expert',placa='TEST001')
    c=Cliente(razao_social='FAEG CLIENTE',cnpj_cpf='1234567890001')
    l1=Local(nome_local='Local A'); l2=Local(nome_local='Local B')
    db.add_all([m,v,c,l1,l2]);db.commit()
    mid=m.id_motorista;vid=v.id_veiculo;cid=c.id_cliente;oid=l1.id_local;did=l2.id_local
from faeg_app.core import salvar_viagem_completa
st.session_state['form_data']={'id_viagem_label':'V1','saida_coleta_ref':'p:teste-primeira','tipo_viagem':'Ciclo',
     'ciclo_nome':'Ciclo 001','mot_id':mid,'vei_id':vid,'cli_id':cid,
     'col_id':oid,'ent_id':did,'valor_negociado':500.0,'data_op':date(2026,11,24),
     'data_coleta':date(2026,11,24),'data_entrega':date(2026,11,25)}
st.session_state['saidas_provisorias']=[{
    'id':'teste-primeira', 'id_veiculo':vid,'id_motorista':mid,'descricao':'Coletas preparatórias',
    'data_inicio':date(2026,11,24),'data_fim':date(2026,11,24),
    'km_saida_coletas':30.,'km_rota_principal':80.,'km_retorno_base':20.,
    'km_planejado_manual':130.,'odometro_inicial':40000,'odometro_final':40130,
}]
st.session_state['despesas_temp']=[{
    'destino_temp':'ciclo','id_fornecedor':None,'tipo_despesa':'Posto de Combustível',
    'descricao_detalhe':'Diesel teste','quantidade':20.,'valor_unitario':6.5,
    'valor_total':130.,'odometro_abastecimento':40100,
    'id_veiculo_abast':vid,'data_despesa':date(2026,11,24),
}]
# simular rascunho gravado antes de fechar o cadastro
from database.rascunhos import salvar_rascunho
with SessionLocal() as db:
    rid=salvar_rascunho(db,id_rascunho=None,titulo='V1',
                        form=st.session_state['form_data'],
                        saidas=st.session_state['saidas_provisorias'],
                        despesas=st.session_state['despesas_temp'])
    db.commit()
st.session_state['rascunho_ativo_id']=rid
salvar_viagem_completa(0,[])
assert not st.errors,st.errors
with SessionLocal() as db:
    assert db.query(Viagem).count()==1
    assert db.query(SaidaOperacional).count()==1
    assert db.query(CicloDespesa).count()==1
    assert db.query(ViagemDespesa).count()==0
    assert db.query(Abastecimento).count()==1
    assert db.query(RascunhoViagem).count()==0
    assert db.query(CicloDespesa).first().valor_total==130
    primeiro=db.query(Viagem).first()
    assert primeiro.codigo_viagem=='V1'
    assert primeiro.id_frete_externo=='FV000000001'
    assert primeiro.id_saida_coleta==db.query(SaidaOperacional).first().id_saida
    id_saida=primeiro.id_saida_coleta
    id_ciclo=primeiro.id_ciclo
# Segundo frete da mesma saída: nenhuma nova saída ou despesa compartilhada.
st.session_state['form_data']={'id_viagem_label':'V1','id_frete':'FV000000001',
     'saida_coleta_ref':f's:{id_saida}', 'tipo_viagem':'Ciclo',
     'ciclo_nome':'Ciclo 001','mot_id':mid,'vei_id':vid,'cli_id':cid,
     'col_id':oid,'ent_id':did,'tipo_material':'Carga complementar',
     'valor_negociado':200.0,'data_op':date(2026,11,24),
     'data_coleta':date(2026,11,24),'data_entrega':date(2026,11,25)}
st.session_state['despesas_temp']=[]
st.session_state['saidas_provisorias']=[]
salvar_viagem_completa(0,[])
assert not st.errors,st.errors
with SessionLocal() as db:
    fretes=db.query(Viagem).order_by(Viagem.id_viagem).all()
    assert len(fretes)==2
    assert [(v.codigo_viagem,v.id_frete_externo) for v in fretes]==[
        ('V1','FV000000001'),('V2','FV000000002')]
    assert all(v.id_saida_coleta==id_saida and v.id_ciclo==id_ciclo for v in fretes)
    assert fretes[1].tipo_material=='Carga complementar'
    assert db.query(SaidaOperacional).count()==1
    assert db.query(CicloDespesa).count()==1
    assert db.query(Abastecimento).count()==1
print('CICLO OK: dois fretes, uma saida, despesa compartilhada unica e identificacao automatica')
