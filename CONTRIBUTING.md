# Diretrizes de desenvolvimento

O desenvolvimento utiliza Git para versionamento, issues para registro de demandas e testes automatizados para apoiar a manutenção das funcionalidades.

## Processo de alteração

1. Registrar a demanda e os critérios de aceite.
2. Criar uma branch com o escopo da alteração (`feature/`, `fix/` ou `docs/`).
3. Desenvolver a mudança com testes adequados aos componentes afetados.
4. Executar os testes e conferir o diff antes da integração.
5. Integrar as alterações à branch principal após revisão.

```powershell
python -m compileall -q app.py faeg_app database views tests
python -m pytest -q tests
git diff --check
```

## Convenções

- Código Python com funções e módulos organizados por responsabilidade.
- Nomes expressivos e comentários reservados para regras de negócio, decisões técnicas e condições não evidentes.
- Documentação em português, com termos padronizados pelo [glossário](docs/glossario.md).
- Requisitos identificados por `RF-XX`, regras de domínio centralizadas em [regras de negócio](docs/regras_negocio.md) e decisões arquiteturais registradas como ADRs.
- Mudanças no banco acompanhadas de avaliação de compatibilidade, ensaio em PostgreSQL isolado e plano de recuperação.
- Credenciais e dados pessoais ou financeiros reais fora do repositório, dos testes e das evidências públicas.

## Revisão

A descrição da alteração registra seu objetivo, os módulos afetados, os testes executados e eventuais impactos em persistência ou relatórios.
