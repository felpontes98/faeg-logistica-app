"""Aplica o tema institucional da FAEG sem alterar o CSS original."""
from pathlib import Path

import streamlit as st


def aplicar_tema():
    caminho = Path(__file__).resolve().parent.parent / "assets" / "faeg_styles.html"
    st.markdown(caminho.read_text(encoding="utf-8"), unsafe_allow_html=True)
