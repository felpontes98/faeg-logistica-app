"""Apresentação segura de falhas operacionais na interface Streamlit."""

import logging

import streamlit as st

_LOG = logging.getLogger(__name__)


def informar_falha(acao: str) -> None:
    """Registra detalhes no log privado e apresenta aviso neutro ao usuário."""
    _LOG.exception("Falha ao %s", acao)
    st.error(f"Não foi possível {acao}. Confira os dados ou contate o responsável pelo sistema.")
