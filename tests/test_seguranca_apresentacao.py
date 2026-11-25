"""Verificações de mensagens de falha exibidas pela interface."""

import runpy
import sys
from pathlib import Path
from types import ModuleType


def test_erro_interno_nao_exibe_detalhes_de_conexao(monkeypatch):
    mensagens = []
    fake_streamlit = ModuleType("streamlit")
    fake_streamlit.error = mensagens.append
    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)

    arquivo = Path(__file__).resolve().parents[1] / "faeg_app" / "erros.py"
    informar_falha = runpy.run_path(str(arquivo))["informar_falha"]
    try:
        raise RuntimeError("postgresql://operador:senha-interna@host/privado")
    except RuntimeError:
        informar_falha("registrar uma saída")

    assert len(mensagens) == 1
    assert "Não foi possível registrar uma saída" in mensagens[0]
    assert "senha-interna" not in mensagens[0]
    assert "postgresql://" not in mensagens[0]
