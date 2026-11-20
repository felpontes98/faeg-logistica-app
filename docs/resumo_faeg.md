# Resumo do Projeto — FAEG Logística

## Objetivo

Desenvolver um sistema web para substituir progressivamente o preenchimento operacional em Excel, mantendo a rastreabilidade de fretes individuais e ciclos, facilitando os cadastros, as consultas, os controles de gastos e os relatórios.

O projeto nasceu da operação real da **FAEG — Soluções Empresariais e Logísticas**, com processos e planilha-base apresentados por Eduardo Pontes. O desenvolvimento é conduzido por Felipe Pontes e Larissa do Espírito Santo no contexto do Startup Challenge UMC 2026.

## Estado da versão analisada

Foi realizada uma leitura estática do código e da planilha de referência. O aplicativo possui onze etapas na navegação:

| Etapa | Função presente na interface |
| --- | --- |
| 1 | Frota FAEG e área de importação Excel |
| 2 | Frete, rota, carga e documentos |
| 3 | Cliente contratante |
| 4 | Negociação e pagamento |
| 5 | Coleta |
| 6 | Entrega |
| 7 | Despesas de viagem |
| 8 | Fechamento final |
| 9 | Relatórios, indicadores e exportação |
| 10 | Consultas gerais |
| 11 | Cadastros gerais |

Os formulários, cadastros, consultas e relatórios estão presentes no código. O banco é modelado por SQLAlchemy em nove tabelas PostgreSQL. **A presença de uma tela não equivale a homologação funcional:** alguns fluxos precisam de correção e de testes com banco de dados.

## Decisões operacionais da FAEG

1. **Frete e ciclo possuem identificadores diferentes.** O código do frete identifica cada serviço; o código do ciclo agrupa vários serviços.
2. **O ciclo tem um único fechamento operacional.** Receitas dos fretes são somadas; despesas comuns e quilometragem são registradas sem duplicação.
3. **A quilometragem do Maps é estimada.** A leitura de odômetro da saída/chegada e a do abastecimento são informações reais distintas e podem não estar disponíveis.
4. **Negociação e recebimento não são a mesma coisa.** Percentual e valor das parcelas podem ser calculados automaticamente, mas só valores confirmados representam dinheiro recebido.
5. **Resultado operacional não é automaticamente lucro líquido.** A nomenclatura deve refletir os gastos efetivamente considerados.

Exemplos e critérios de aceite estão documentados em [Regras de negócio](regras_negocio.md) e [Requisitos](requisitos.md).

## Atenções identificadas

| Tema | Situação |
| --- | --- |
| Importação Excel | A interface espera estrutura de resposta e parâmetros diferentes dos fornecidos pelo importador |
| Agrupamento | O salvamento e o importador criam um novo registro de ciclo por frete |
| Fechamento | Linhas de `FECHAMENTO` do Excel são ignoradas na importação atual |
| Recebimentos | Total programado de adiantamento e saldo é rotulado como “Valor Total Recebido” |
| KM e abastecimento | Há campos de odômetro por viagem, mas não registro independente de abastecimentos |
| Segurança | Não foi identificada autenticação ou autorização de usuários no código revisado |
| Testes | Não havia suíte automatizada de testes no pacote recebido |

**Nenhum desses pontos foi alterado no código nesta revisão documental.** Para transformar essas pendências em atividades, a equipe pode usar as Issues do GitHub, com base nos [Requisitos](requisitos.md) e na [Arquitetura do banco](arquitetura_banco.md).

## Tecnologia e identidade visual

- Python, Streamlit, Pandas, SQLAlchemy, `psycopg` e PostgreSQL.
- Código atual concentrado em `app.py`, com persistência em `database/`.
- Tema com azul estrutural `#0D263C`, laranja `#F34D25`, branco e cinza, além do logotipo em `assets/logo_faeg.png`.
- Marca institucional: **FAEG — Soluções Empresariais e Logísticas**.

## Próxima versão

A prioridade deve ser corrigir a importação e garantir segurança, depois adequar fretes/ciclos, fechamento, recebimentos e quilometragem. A modularização do aplicativo e a evolução do painel de indicadores vêm em seguida, preservando os dados existentes.

Para apresentação geral e instalação, consulte o [README](../README.md). Para a arquitetura técnica, consulte [Arquitetura do banco](arquitetura_banco.md).