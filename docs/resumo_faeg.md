# Resumo do projeto — FAEG Logística

**Projeto:** Sistema Web FAEG · **Contexto:** Startup Challenge UMC 2026
**Aplicação:** controle operacional e financeiro da FAEG — Soluções Empresariais e Logísticas.

## Problema

A operação de transportes envolve fretes negociados separadamente, deslocamentos compartilhados, coletas e entregas em diferentes datas, despesas de veículo, abastecimentos e recebimentos. O modelo inicial em planilhas exige conciliação manual desses registros e dificulta a análise consolidada por operação.

## Solução proposta

O Sistema Web FAEG organiza essas informações em um MVP acessível pelo navegador, com banco de dados relacional e relatórios gerenciais. A interface reúne 11 etapas: Frota, Frete e Documentos, Cliente, Negociação e Recebimentos, Coleta, Entrega, Despesas, Fechamento, Relatórios, Consultas e Cadastros.

### Estrutura operacional

- **Frete:** contratação com cliente, carga, documentos e negociação próprios.
- **Ciclo operacional:** agrupamento de fretes e despesas compartilhadas, inclusive retornos e coletas complementares.
- **Saída operacional:** deslocamento realizado pelo veículo, com datas, planejamento e odômetros.
- **Trecho:** segmento de percurso vinculado à saída.
- **Abastecimento:** aquisição registrada em despesa única e histórico operacional; consumo por quilometragem calculado separadamente como estimativa gerencial.

As receitas são vinculadas aos fretes. Os custos compartilhados e os quilômetros efetivamente rodados são consolidados na operação, sem rateio automático entre contratos.

## Tecnologias e organização

| Camada | Implementação |
| --- | --- |
| Interface | Python/Streamlit, com 11 módulos em `faeg_app/pages/` |
| Regras e serviços | `faeg_app/`, `database/` e `views/` |
| Persistência | SQLAlchemy e PostgreSQL/Neon |
| Modelo relacional | 18 tabelas ORM |
| Relatórios | Exportações Excel/PDF e indicadores gerenciais |
| Qualidade | Testes automatizados em `tests/` e integração contínua no GitHub Actions |

## Escopo atual e evolução

O MVP contempla cadastros, controle de fretes e ciclos, pagamentos efetivos, despesas, abastecimentos, saídas operacionais, consultas e relatórios. A importação de planilhas oferece prévia e conferência, sem gravação automática em lote. O fechamento é gerencial e não substitui escrituração contábil.

O planejamento de continuidade inclui autenticação por usuário, permissões, migrações versionadas, conciliação de combustível e ampliação dos testes integrados. Consulte [planejamento técnico](planejamento_tecnico.md).

## Equipe e documentação

- **Felipe Pontes:** desenvolvimento de software.
- **Larissa do Espírito Santo:** desenvolvimento de software.
- **Eduardo Pontes:** representante da FAEG, requisitos operacionais e validação das regras de negócio.

O projeto é documentado em [reuniões](reunioes/), [requisitos](requisitos.md), [regras de negócio](regras_negocio.md), [decisões técnicas](decisoes/README.md), [diagramas](diagramas/README.md) e [protótipo inicial](prototipo/prototipo_inicial.html).
