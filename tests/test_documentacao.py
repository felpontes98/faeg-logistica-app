"""Validacoes da documentacao mantida pelo projeto FAEG.

Os testes examinam apenas os arquivos do repositorio; pacotes instalados
em ambientes virtuais nao fazem parte da documentacao do projeto.
A sintaxe Mermaid e validada estaticamente, sem simular a renderizacao web.
"""

import ast
import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"(?<!!)\[[^\]\n]+\]\(([^)]+)\)")
MERMAID = re.compile(r"^```mermaid\s*\n(.*?)^```\s*$", re.MULTILINE | re.DOTALL)
VALID_START = {"flowchart", "erDiagram", "classDiagram", "sequenceDiagram", "stateDiagram-v2"}


def _docs():
    """Documentos da raiz e de docs/, nunca a .venv/ ou dependencias."""
    raiz = ROOT.glob("*.md")
    pasta_docs = (ROOT / "docs").rglob("*.md")
    github = (ROOT / ".github").rglob("*.md")
    return sorted({*raiz, *pasta_docs, *github})


def test_links_markdown_locais_existentes():
    errors = []
    for doc in _docs():
        content = doc.read_text(encoding="utf-8")
        for link in LINK.findall(content):
            link = link.strip().strip("<>")
            if link.startswith(("https://", "http://", "mailto:", "#")):
                continue
            path = unquote(link.split("#", 1)[0])
            if path and not (doc.parent / path).exists():
                errors.append(f"{doc.relative_to(ROOT)}: {link}")
    assert not errors, "Referencias Markdown inexistentes:\n" + "\n".join(errors)


def test_mermaid_blocos_identificados_e_formato_conservador():
    count = 0
    for doc in _docs():
        content = doc.read_text(encoding="utf-8")
        assert content.count("```mermaid") == len(MERMAID.findall(content)), doc
        for diagram in MERMAID.findall(content):
            count += 1
            lines = [line.strip() for line in diagram.splitlines() if line.strip()]
            assert lines[0].split()[0] in VALID_START, (doc, lines[0])
            assert "PK,FK" not in diagram, f"Separar chaves com virgula e espaco: {doc}"
            for line in lines:
                assert line.count('"') % 2 == 0, (doc, line)
    assert count >= 10, f"Coleção de diagramas incompleta: {count}"


def test_der_cobre_todas_as_tabelas_orm():
    tree = ast.parse((ROOT / "database/models.py").read_text(encoding="utf-8"))
    tabelas = set()
    for clazz in tree.body:
        if isinstance(clazz, ast.ClassDef):
            for node in clazz.body:
                if isinstance(node, ast.Assign):
                    if any(isinstance(t, ast.Name) and t.id == "__tablename__" for t in node.targets):
                        tabelas.add(ast.literal_eval(node.value).upper())

    er = (ROOT / "docs/diagramas/entidade_relacionamento.md").read_text(encoding="utf-8")
    blocos = [m for m in MERMAID.findall(er) if m.lstrip().startswith("erDiagram")]
    cobertura = set()
    for bloco in blocos:
        cobertura.update(re.findall(r"^\s*([A-Z0-9_]+)\s*\{", bloco, flags=re.MULTILINE))

    assert tabelas, "Nenhuma tabela ORM encontrada em database/models.py"
    assert cobertura == tabelas, (
        f"DER com diferencas: faltantes={tabelas - cobertura}; "
        f"extras={cobertura - tabelas}"
    )


def test_estrutura_modular_e_pontos_de_entrada_documentados():
    assert (ROOT / "app.py").exists()
    assert len(list((ROOT / "faeg_app/pages").glob("etapa_*.py"))) == 11
    for doc in ("README.md", "SECURITY.md", "docs/README.md", "docs/diagramas/README.md"):
        assert (ROOT / doc).exists(), doc


def test_documentacao_descreve_fluxo_atual_e_modelo_de_dados():
    """O índice e os guias acompanham a estrutura vigente do MVP."""
    indice = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    guia = (ROOT / "docs/guia_preenchimento_operacional.md").read_text(encoding="utf-8")
    requisitos = (ROOT / "docs/requisitos.md").read_text(encoding="utf-8")
    assert "19 tabelas ORM" in indice
    assert "Etapa 2" in guia and "Etapa 8" in guia
    assert "RF-51" in requisitos and "rascunhos" in requisitos.lower()
    assert not (ROOT / "docs/auditoria_final_2026-11-24.md").exists()
    assert not (ROOT / "docs/avaliacao_repositorio.md").exists()
