from pathlib import Path
import os,subprocess,sys

def test_salvamento_integral_ciclo_e_despesa_unica_sqlite():
    raiz=Path(__file__).resolve().parents[1]
    env=dict(os.environ,DATABASE_URL='sqlite:///:memory:')
    run=subprocess.run([sys.executable,'tests/helpers/smoke_salvar_ciclo_fluxo.py'],cwd=raiz,
        env=env,capture_output=True,text=True,timeout=30)
    assert run.returncode==0,run.stdout+'\n'+run.stderr
    assert 'CICLO OK' in run.stdout
