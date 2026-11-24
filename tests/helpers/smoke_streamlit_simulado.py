"""Execução simulada sem Streamlit real para detectar referências ausentes na UI.
Não reproduz o comportamento completo dos widgets nem valida o Neon.
"""
import sys,types,os,importlib,runpy,traceback
sys.path.insert(0, os.getcwd())
os.environ['DATABASE_URL']='sqlite:///:memory:'
from database.connection import Base,engine
from database import models
Base.metadata.create_all(engine)
models.sincronizar_colunas_banco=lambda:Base.metadata.create_all(engine)

labels=['1. Frota FAEG','2. Frete e Docs','3. Cliente','4. Negociação / Pgto','5. Coleta (Origem)','6. Entrega (Destino)','7. Despesas de Viagem','8. Fechamento Final','9. Relatórios / Exportar','10. Consultas Gerais','11. Cadastros Gerais']
class CacheDummy:
 def __call__(self,*a,**kw):
  if a and callable(a[0]):return self.decorate(a[0]);
  return self.decorate
 @staticmethod
 def decorate(fn):
  fn.clear=lambda:None
  return fn
class Ctx:
 def __enter__(self):return self
 def __exit__(self,*a):return None
 def __getattr__(self,key):return getattr(fake,key)
class FakeSt(types.ModuleType):
 def __init__(self):
  super().__init__('streamlit')
  self.session_state={}
  self.cache_data=CacheDummy()
  self.cache_resource=CacheDummy()
  self.sidebar=Ctx()
  self.menu=labels[0]
 def __getattr__(self,key):
  if key in {'container','form','expander','spinner','empty','popover','chat_message'}:return lambda *a,**kw:Ctx()
  if key=='tabs':return lambda labs,**kw:[Ctx() for _ in labs]
  if key=='columns':return lambda cs,**kw:[Ctx() for _ in range(cs if isinstance(cs,int) else len(cs))]
  if key=='radio':return lambda label,options,*a,**kw:self.menu if 'Menu Operacional' in label else (options[0] if options else '')
  if key in {'selectbox','multiselect','segmented_control'}:
   def selector(label,options,*a,**kw):
    if key=='multiselect':return kw.get('default',[])
    if options is None:return None
    opts=list(options)
    return opts[kw.get('index',0)] if opts else None
   return selector
  if key in {'number_input','slider'}:return lambda *a,**kw:kw.get('value',kw.get('min_value',0))
  if key=='date_input':return lambda *a,**kw:kw.get('value',__import__('datetime').date.today())
  if key in {'text_input','text_area'}:return lambda *a,**kw:kw.get('value','')
  if key=='checkbox':return lambda *a,**kw:kw.get('value',False)
  if key in {'button','form_submit_button','download_button','toggle'}:return lambda *a,**kw:False
  if key=='file_uploader':return lambda *a,**kw:None
  if key=='data_editor':return lambda data,*a,**kw:data
  if key=='select_slider':return lambda *a,**kw:kw.get('value','')
  return lambda *a,**kw:None
fake=FakeSt();sys.modules['streamlit']=fake
falhas = 0
for name in labels:
 fake.menu=name;fake.session_state.clear();fake.session_state['menu_operacional_radio']=name
 print('\nTesting:',name,flush=True)
 try:
  runpy.run_path('app.py',run_name='__main__')
 except BaseException as e:
  falhas += 1
  print('FAIL:',type(e).__name__,str(e)[:300]);traceback.print_exc(limit=8)
 else: print('OK')

if falhas:
    raise SystemExit(f"{falhas} etapas falharam na simulação.")
print("SIMULAÇÃO: 11/11 ETAPAS EXECUTADAS COM SQLITE ISOLADO")
