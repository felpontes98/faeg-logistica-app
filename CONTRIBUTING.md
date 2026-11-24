# Contribuição e revisão de mudanças

Este projeto combina desenvolvimento acadêmico e utilização operacional real. As mudanças devem preservar fretes, ciclos, despesas, recebimentos e histórico do banco.

## Fluxo recomendado

1. Criar issue descrevendo problema, requisito e cenário esperado.
2. Criar branch específica, por exemplo `docs/diagramas` ou `fix/fechamento-ciclo`.
3. Evitar editar diretamente dados reais como forma de testar cálculos; usar PostgreSQL isolado ou SQLite em memória para os testes existentes.
4. Rodar `python -m compileall -q app.py faeg_app database views tests` e `python -m pytest -q tests`.
5. Conferir `git diff --check` e realizar revisão de alterações em `database/models.py` e `sincronizar_colunas_banco()`.
6. Abrir pull request indicando mudanças, riscos, plano de teste e impacto no Neon.

## Padrões mínimos

- Código e documentação em português, com termos técnicos padronizados no [glossário](docs/glossario.md).
- Requisitos identificados por `RF-XX` e decisões documentadas em [ADRs](docs/decisoes/README.md).
- Nenhuma credencial, CPF, CNH, telefone real, dados financeiros reais ou screenshot com dados privados no repositório.
- Desenvolver cenários de verificação para novas funcionalidades, especialmente quando envolvem dados financeiros e operacionais.
- Evitar mudanças automáticas/destrutivas em dados legados sem autorização explícita e plano de recuperação.

## Diagrama e Markdown

Usar blocos Mermaid para diagramas exibidos diretamente no GitHub. Diagramas são **modelos de compreensão**, não uma substituição para inspeção de implementação. Atualizar os diagramas ao mudar relacionamentos ou fluxos relevantes.
