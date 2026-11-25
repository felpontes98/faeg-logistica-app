# Guia de leitura para avaliação acadêmica — Sistema Web FAEG

**Projeto:** FAEG — Sistema Web de Gestão Logística (Startup Challenge UMC 2026)

## 1. Problema e proposta

O controle anterior era realizado em planilhas. O MVP organiza fretes, ciclos, coletas, entregas, valores negociados, recebimentos, custos e quilometragem em uma aplicação web com armazenamento relacional.

## 2. Implementação apresentada

- **Front-end e interação:** Python/Streamlit, com 11 etapas em módulos próprios.
- **Persistência:** SQLAlchemy e PostgreSQL (Neon), com **19 tabelas ORM**, incluindo rascunhos.
- **Regra central:** contratos comerciais são fretes; a operação pode agrupar fretes em ciclos e saídas físicas. Custos compartilhados não recebem rateio automático nem são somados duas vezes.
- **Abastecimentos:** uma compra financeira e um histórico operacional associado; consumo por KM é somente estimativa gerencial.
- **Consultas e relatórios:** dados operacionais, indicadores e exportações Excel/PDF.

## 3. Evidências disponíveis no repositório

| Evidência | Documento |
| --- | --- |
| Escopo e requisitos | [Resumo](resumo_faeg.md) e [requisitos](requisitos.md) |
| Evolução do MVP | [Reuniões](reunioes/) e [protótipo inicial](prototipo/prototipo_inicial.html) |
| Modelagem | [Diagramas UML e ER](diagramas/README.md) |
| Arquitetura e código | [Módulos](arquitetura_aplicacao.md) e [dados](arquitetura_banco.md) |
| Testes e evolução | [Plano de testes](plano_testes.md) e [planejamento técnico](planejamento_tecnico.md) |
| Justificativas de projeto | [ADRs](decisoes/README.md) |

## 4. Reprodução dos testes de desenvolvimento

Criar um ambiente Python 3.11, instalar `requirements.txt` e `pytest`, e executar:

```powershell
python -m compileall -q app.py faeg_app database views tests
python -m pytest -q tests
```

Os testes de persistência utilizam **SQLite isolado**. O procedimento de execução local com PostgreSQL está descrito no [guia de execução](guia_execucao.md). As credenciais e os dados reais da empresa permanecem fora dos materiais acadêmicos.

## 5. Escopo e próximos incrementos

O sistema é um MVP de gestão operacional, com indicadores gerenciais. Autenticação própria por usuário, migrações versionadas e ampliação dos testes integrados integram o [planejamento técnico](planejamento_tecnico.md).
