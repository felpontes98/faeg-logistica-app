# Guia de leitura para avaliação acadêmica — Sistema Web FAEG

**Projeto:** FAEG — Sistema Web de Gestão Logística (Startup Challenge UMC 2026)

## 1. Problema e proposta

O controle anterior era realizado em planilhas. O MVP organiza fretes, ciclos, coletas, entregas, valores negociados, recebimentos, custos e quilometragem em uma aplicação web com armazenamento relacional.

## 2. Implementação apresentada

- **Front-end e interação:** Python/Streamlit, com 11 etapas em módulos próprios.
- **Persistência:** SQLAlchemy e PostgreSQL (Neon), com 18 modelos ORM.
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
| Testes e limites | [Plano de testes](plano_testes.md) e [auditoria final](auditoria_final_2026-11-24.md) |
| Justificativas de projeto | [ADRs](decisoes/README.md) |

## 4. Reprodução dos testes de desenvolvimento

Criar um ambiente Python 3.11, instalar `requirements.txt` e `pytest`, e executar:

```powershell
python -m compileall -q app.py faeg_app database views tests
python -m pytest -q tests
```

Os testes usam **SQLite isolado**, sem credenciais de produção. Para abrir o Streamlit, é necessária uma `DATABASE_URL` de banco PostgreSQL de testes, conforme [guia de execução](guia_execucao.md). **Não é seguro fornecer credenciais do Neon de produção no material acadêmico.**

## 5. Limitações assumidas

O MVP não é apresentado como ERP homologado ou demonstrativo contábil definitivo. Permanecem pendentes autenticação/autorização por perfil, migrações versionadas e testes integrados completos no banco PostgreSQL.
