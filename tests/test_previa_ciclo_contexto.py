"""Regressão: o fechamento do ciclo recebe os clientes do contexto modularizado."""
import os
from pathlib import Path
import subprocess
import sys
import textwrap

ROOT = Path(__file__).resolve().parents[1]


def test_previa_ciclo_consulta_cliente_sem_variavel_global():
    codigo = textwrap.dedent('''
        import sys, types
        class Cache:
            def __call__(self, *args, **kwargs):
                if args and callable(args[0]):
                    return self.decorar(args[0])
                return self.decorar
            def decorar(self, fn):
                fn.clear = lambda: None
                return fn
        st = types.ModuleType('streamlit')
        st.cache_data = Cache()
        st.cache_resource = Cache()
        st.session_state = {'form_data': {
            'tipo_viagem': 'Ciclo', 'ciclo_nome': 'Ciclo-01',
            'cli_id': 7, 'valor_negociado': 150.0,
        }}
        sys.modules['streamlit'] = st
        import faeg_app.core as core
        core.carregar_todas_viagens_consulta = lambda: ([{
            'id_viagem': 8, 'ciclo': 'Ciclo-01', 'id_ciclo': 2,
            'tipo_viagem': 'Ciclo',
            'financeiro_individual': True,
        }], [])
        core.carregar_recebimentos_viagem = lambda _id: []
        core.carregar_todas_despesas_ciclo = lambda: []
        core.consolidar_ciclos = lambda fretes, despesas: fretes
        clientes = [{'id_cliente': 7, 'razao_social': 'Cliente Teste'}]
        resultado = core.montar_previa_financeira_ciclo(8, 0.0, clientes)
        assert resultado['cliente'] == 'Cliente Teste', resultado
        assert resultado['valor_negociado'] == 150.0, resultado
    ''')
    env = dict(os.environ, DATABASE_URL='sqlite:///:memory:')
    proc = subprocess.run([sys.executable, '-c', codigo], cwd=ROOT,
                          env=env, capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stdout + '\n' + proc.stderr
