# Histórico de alterações — FAEG

Registro de versões e principais melhorias do Sistema Web FAEG. O histórico detalhado das alterações permanece disponível nos commits do Git.

## 2026-11-24 — Padronização para apresentação acadêmica

- Revisão das notações Mermaid e adequação dos diagramas de componentes, implantação, atividades e ER aos módulos existentes.
- Atualização dos documentos que ainda descreviam o `app.py` pré-modularização.
- Verificação estática automatizada de links, blocos Mermaid, chaves ORM e navegação documental.
- Padronização da linguagem institucional, atualização de links e organização do planejamento técnico.
- Sem alteração nas regras de negócio, modelos ORM, banco Neon ou interface operacional.

## 2026-11-24 — Organização modular do aplicativo (após Ajuste 27)

- Separação das 11 etapas em `faeg_app/pages/` mantendo o conteúdo e as regras existentes.
- Extração de CSS, layout, consultas/callbacks e geradores Excel/PDF.
- Correção do caminho de assets após extração do carregador de logo.
- Ampliação dos testes de estrutura modular, exportações e navegação simulada das 11 etapas.
- Preservação dos modelos SQLAlchemy, das tabelas e das regras de negócio.

## 2026-11-24 — Documentação, modelagem e licenciamento

- README reorganizado como ponto de entrada do projeto.
- Inventário do banco atualizado para 18 entidades ORM.
- Diagramas de classes, sequência, dados, componentes, processos, casos de uso, estados e implantação.
- Guia de instalação, plano de testes, glossário, segurança e ADRs.
- Configuração de integração contínua com verificações de sintaxe e testes automatizados.
- Política para novas contribuições com direitos reservados; licença MIT anterior arquivada e direitos históricos preservados.
- Atualização documental sem alterar os modelos de banco; o código foi modularizado em etapa posterior.

## 2026-11-24 — Ajuste 27 (commit `01a675f`)

- Cadastro de saídas e trechos operacionais com controle próprio de KM e odômetros.
- Adição das tabelas `saidas_operacionais`, `trechos_operacionais` e `parametros_consumo_veiculo`.
- Indicador gerencial de consumo estimado sem novo lançamento financeiro.
- Compatibilidade com registros legados, sem migração automática do Ciclo 001.

## Evolução anterior — 2026

- MVP com onze etapas de cadastro e consulta, controle de fretes e ciclos, negociação e recebimentos.
- Lançamento único de despesas/abastecimentos e segregação de gastos de frete, ciclo e veículo.
- Exportações gerenciais, conferência financeira e auditoria de vínculos/custos.
- Histórico de reuniões e protótipo visual anterior ao Streamlit.

Para requisitos funcionais detalhados, consultar [`docs/requisitos.md`](docs/requisitos.md). A sequência histórica exata dos ajustes anteriores pode ser levantada pelos commits do GitHub.
