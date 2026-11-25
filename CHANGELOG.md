# Histórico de alterações — FAEG

Este documento reúne os principais marcos do Sistema Web FAEG. As alterações detalhadas e as respectivas autorias são registradas no histórico de commits do Git.

## 2026-11-25 — Ajuste 29: fluxo de preenchimento unificado

- Manutenção das 11 etapas, com as saídas operacionais, KM planejados e odômetros concentrados na **Etapa 2**.
- Registro de KM de saída/coletas, rota principal e retorno à base por saída, com cálculo automático dos totais.
- **Etapa 7:** lançamento único das despesas, inclusive Diesel/ARLA com odômetro do abastecimento e vínculo ao frete, ciclo ou veículo.
- **Etapa 8:** conferência e fechamento, sem repetir o cadastro das saídas ou dos odômetros.
- Parâmetros de consumo de referência concentrados nos cadastros dos veículos (Etapa 11).
- Salvamento e retomada de rascunhos, com persistência independente dos fretes definitivos.
- Ampliação dos testes para rascunhos, saídas, integridade financeira e documentação.
- Atualização da modelagem para **19 tabelas ORM**, incluindo `rascunhos_viagens`.

## 2026-11-24 — Organização modular e documentação acadêmica

- Divisão das 11 etapas em `faeg_app/pages/`, com `app.py` como ponto de entrada.
- Separação de layout, tema, relatórios e componentes operacionais reutilizáveis.
- Inclusão dos diagramas Mermaid (classes, sequência, ER, componentes, atividades, estados, casos de uso e implantação).
- Organização dos requisitos, regras de negócio, guias, reuniões, testes, decisões arquiteturais e integração contínua.
- Registro da política de direitos reservados para novas contribuições, preservando as condições MIT das versões anteriores.

## 2026-11-24 — Ajuste 27: saídas e trechos operacionais

- Introdução de saídas e trechos vinculados às operações, com KM planejado e odômetros.
- Inclusão de `saidas_operacionais`, `trechos_operacionais` e `parametros_consumo_veiculo`.
- Consumo estimado de combustível como indicador separado do lançamento financeiro.
- Compatibilidade de leitura com dados de fretes anteriores à reorganização.

## Evolução inicial — 2026

- Evolução da planilha de viagens para MVP web em Streamlit e PostgreSQL/Neon.
- Cadastro de fretes e ciclos, clientes, veículos, motoristas, coletas e entregas.
- Negociações e recebimentos por frete; despesas separadas por frete, ciclo e veículo.
- Consultas, indicadores gerenciais, exportações Excel/PDF e registro histórico de reuniões.

Consulte [requisitos](docs/requisitos.md), [regras de negócio](docs/regras_negocio.md) e [decisões arquiteturais](docs/decisoes/README.md) para o detalhamento técnico.
