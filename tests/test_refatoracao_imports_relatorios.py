"""Teste subprocessado: força SQLite local, evitando uso involuntário do Neon."""
from pathlib import Path
import os
import subprocess
import sys
import textwrap

ROOT = Path(__file__).resolve().parents[1]


def test_importacao_11_etapas_e_exportacoes_sem_neon():
    codigo = textwrap.dedent(
        r'''
        import sys, types, importlib, pathlib
        from database.connection import Base, engine
        from database import models
        Base.metadata.create_all(engine)
        class CacheDummy:
            def __call__(self, *args, **kwargs):
                if args and callable(args[0]):
                    return self.decorar(args[0])
                return self.decorar
            @staticmethod
            def decorar(fn):
                fn.clear = lambda: None
                return fn
        st = types.ModuleType("streamlit")
        st.cache_data = CacheDummy()
        st.cache_resource = CacheDummy()
        st.session_state = {}
        sys.modules["streamlit"] = st
        import faeg_app.core, faeg_app.layout, faeg_app.theme, faeg_app.bootstrap
        from faeg_app import reporting
        for path in sorted(pathlib.Path("faeg_app/pages").glob("etapa_*.py")):
            mod = importlib.import_module("faeg_app.pages." + path.stem)
            assert callable(mod.render)
        assert reporting.obter_caminho_logo() is not None
        excel = reporting.gerar_excel_base_completa([], [], [], [], [], [], [])
        assert excel.startswith(b"PK")
        campos = ("codigo id_frete cliente ciclo motorista veiculo origem destino tipo_viagem "
                  "frete_info status km_real_fmt receita_fmt despesa_fmt resultado_fmt "
                  "custo_km_fmt margem_fmt parcelas_previstas_fmt recebido_real_fmt saldo_receber_fmt")
        pdf = reporting.gerar_pdf_relatorio({k: "teste" for k in campos.split()}, [])
        assert pdf.startswith(b"%PDF-")
        '''
    )
    env = dict(os.environ)
    env["DATABASE_URL"] = "sqlite:///:memory:"
    proc = subprocess.run(
        [sys.executable, "-c", codigo], cwd=ROOT, env=env,
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
