"""FAEG — ponto de entrada Streamlit.

Interface em faeg_app/pages; regras de operação preservadas em faeg_app/core;
relatórios em faeg_app/reporting e identidade visual em faeg_app/theme.
"""

import streamlit as st

# Deve ocorrer antes dos demais comandos Streamlit.
st.set_page_config(
    page_title="FAEG - Gestão Logística e Operacional",
    page_icon="🟧",
    layout="wide",
    initial_sidebar_state="expanded",
)

from faeg_app.bootstrap import inicializar_banco_uma_vez
from faeg_app.context import PageContext
from faeg_app.core import carregar_estado_viagem, carregar_listas_base
from faeg_app.layout import render_sidebar, render_top_context
from faeg_app.theme import aplicar_tema
from faeg_app.pages.etapa_01_frota import render as render_etapa_01
from faeg_app.pages.etapa_02_frete_documentos import render as render_etapa_02
from faeg_app.pages.etapa_03_cliente import render as render_etapa_03
from faeg_app.pages.etapa_04_negociacao_recebimentos import render as render_etapa_04
from faeg_app.pages.etapa_05_coleta import render as render_etapa_05
from faeg_app.pages.etapa_06_entrega import render as render_etapa_06
from faeg_app.pages.etapa_07_despesas import render as render_etapa_07
from faeg_app.pages.etapa_08_fechamento import render as render_etapa_08
from faeg_app.pages.etapa_09_relatorios import render as render_etapa_09
from faeg_app.pages.etapa_10_consultas import render as render_etapa_10
from faeg_app.pages.etapa_11_cadastros import render as render_etapa_11

# Inicialização do esquema declarativo, após a configuração do Streamlit.
inicializar_banco_uma_vez(schema_v=17)
aplicar_tema()

# Dados de referência compartilhados pelas 11 etapas da interface.
motoristas_db, veiculos_db, clientes_db, locais_db, fornecedores_db, viagens_db = carregar_listas_base()
if "viagem_ativa_id" not in st.session_state:
    st.session_state["viagem_ativa_id"] = 0
viagem_sel_id = st.session_state["viagem_ativa_id"]
carregar_estado_viagem(viagem_sel_id, viagens_db)

ctx = PageContext(
    motoristas_db=motoristas_db,
    veiculos_db=veiculos_db,
    clientes_db=clientes_db,
    locais_db=locais_db,
    fornecedores_db=fornecedores_db,
    viagens_db=viagens_db,
    viagem_sel_id=viagem_sel_id,
)
aba_ativa, ctx.prox_cod_sidebar, ctx.menu_itens = render_sidebar(ctx)
render_top_context(ctx)

# Roteamento das 11 etapas na ordem do processo operacional.
RENDERERS = {
    '1. Frota FAEG': render_etapa_01,
    '2. Frete e Docs': render_etapa_02,
    '3. Cliente': render_etapa_03,
    '4. Negociação / Pgto': render_etapa_04,
    '5. Coleta (Origem)': render_etapa_05,
    '6. Entrega (Destino)': render_etapa_06,
    '7. Despesas de Viagem': render_etapa_07,
    '8. Fechamento Final': render_etapa_08,
    '9. Relatórios / Exportar': render_etapa_09,
    '10. Consultas Gerais': render_etapa_10,
    '11. Cadastros Gerais': render_etapa_11,
}

with st.container(border=True):
    st.markdown('<div class="main-card-marker"></div>', unsafe_allow_html=True)
    RENDERERS[aba_ativa](ctx)
