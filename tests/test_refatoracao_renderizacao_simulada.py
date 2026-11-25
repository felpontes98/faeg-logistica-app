"""Smoke de renderização com dublê de Streamlit e banco SQLite local.

A execução simulada verifica a organização das etapas em ambiente isolado.
"""
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_onze_etapas_renderizam_sem_excecoes_no_ambiente_simulado():
    env = dict(os.environ)
    env["DATABASE_URL"] = "sqlite:///:memory:"
    processo = subprocess.run(
        [sys.executable, "tests/helpers/smoke_streamlit_simulado.py"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    assert processo.returncode == 0, processo.stdout + "\n" + processo.stderr
    assert "SIMULAÇÃO: 11/11" in processo.stdout
