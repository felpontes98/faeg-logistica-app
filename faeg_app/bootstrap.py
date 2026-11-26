"""Inicialização de esquema, chamada após st.set_page_config()."""
import streamlit as st

from database.models import sincronizar_colunas_banco


@st.cache_resource(show_spinner=False)
def inicializar_banco_uma_vez(schema_v=15):
    """Sincroniza tabelas e colunas previstas pelos modelos atuais."""
    sincronizar_colunas_banco()
    return True
