"""Inicialização de esquema, chamada após st.set_page_config()."""
import streamlit as st

from database.models import sincronizar_colunas_banco


@st.cache_resource(show_spinner=False)
def inicializar_banco_uma_vez(schema_v=13):
    """Mantém a sincronização de esquema existente (não é uma nova migração)."""
    sincronizar_colunas_banco()
    return True
