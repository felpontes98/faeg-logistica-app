"""Verificações estáticas sem dependência de Streamlit ou conexão com Neon."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "faeg_app" / "pages"


def test_existencia_das_onze_etapas():
    arquivos = sorted(PAGES.glob("etapa_*.py"))
    assert len(arquivos) == 11
    assert [p.stem[6:8] for p in arquivos] == [f"{i:02d}" for i in range(1, 12)]
    for path in arquivos:
        arvore = ast.parse(path.read_text(encoding="utf-8"))
        funcs = [n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name == "render"]
        assert len(funcs) == 1
        assert [a.arg for a in funcs[0].args.args] == ["ctx"]


def test_app_com_roteamento_das_onze_etapas():
    texto = (ROOT / "app.py").read_text(encoding="utf-8")
    arvore = ast.parse(texto)
    rotas = [n for n in ast.walk(arvore) if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == "RENDERERS" for t in n.targets)]
    assert len(rotas) == 1
    assert len(rotas[0].value.keys) == 11
    assert "st.set_page_config" in texto
    assert "render_top_context(ctx)" in texto


def test_arquivos_essenciais_do_layout():
    assert (ROOT / "assets/faeg_styles.html").is_file()
    html = (ROOT / "assets/faeg_styles.html").read_text(encoding="utf-8")
    assert "<style>" in html and "</style>" in html
    assert "sidebar-logo-img" in html
    assert (ROOT / "assets/logo_faeg.png").is_file()
    for modulo in ("core", "layout", "reporting", "theme", "bootstrap", "context"):
        assert (ROOT / "faeg_app" / f"{modulo}.py").is_file()
