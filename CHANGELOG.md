# Histórico de alterações — FAEG

Registro resumido de marcos conhecidos. **Não substitui o histórico do Git**, que permanece a fonte detalhada de commits e diferenças.

## 2026-11-24 — Documentação, modelagem e licenciamento

- README reorganizado como ponto de entrada do projeto.
- Inventário do banco atualizado para 18 entidades ORM.
- Diagramas de classes, sequência, dados, componentes, processos, casos de uso, estados e implantação.
- Guia de instalação, plano de testes, glossário, segurança e ADRs.
- Fluxo de CI com verificação de sintaxe e testes existentes, sem conexão ao Neon.
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

## 2026-11-24 — Organização modular do aplicativo (após Ajuste 27)

- Separação das 11 etapas em `faeg_app/pages/` mantendo o conteúdo e as regras existentes.
- Extração de CSS, layout, consultas/callbacks e geradores Excel/PDF.
- Correção do caminho de assets após extração do carregador de logo.
- Inclusão de testes estruturais, de exportação e de simulação de abertura das 11 telas, sem acesso ao Neon.
- Nenhuma alteração em modelos SQLAlchemy, tabelas, dados ou licenciamento.

## 2026-11-24 — Revisão final para apresentação acadêmica

- Revisão das notações Mermaid e adequação dos diagramas de componentes, implantação, atividades e ER aos módulos existentes.
- Atualização dos documentos que ainda descreviam o `app.py` pré-modularização.
- Verificação estática automatizada de links, blocos Mermaid, chaves ORM e navegação documental.
- Relatório de auditoria final com distinção entre evidências testadas e pendências de homologação.
- Sem alteração nas regras de negócio, modelos ORM, banco Neon ou interface operacional.
