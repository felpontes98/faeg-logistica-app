# Avaliação técnica do repositório — 24/11/2026

**Base auditada:** arquivo ZIP `faeg-logistica-app-main (1).zip` fornecido para revisão. **Método:** leitura estática dos fontes e documentação, conferência de estrutura, contagem dos modelos ORM e execução dos testes existentes em SQLite. Não foram acessados logs privados do GitHub, segredos, banco Neon nem o ambiente de produção nesta auditoria documental.

## Inventário confirmado

| Item | Observação |
| --- | --- |
| Linguagem e interface | Python + Streamlit (`app.py`, 7.253 linhas na cópia recebida) |
| Banco de dados | PostgreSQL/Neon via SQLAlchemy; `database/models.py` com 18 entidades |
| Domínio | Fretes, ciclos, saídas, trechos, despesas, abastecimentos, recebimentos |
| Estrutura de navegação | 11 etapas no `app.py` |
| Testes existentes | 6 testes Pytest de saídas operacionais, usando SQLite em memória |
| Documentação recebida | README, requisitos, regras, arquitetura, resumo, 3 reuniões e protótipo HTML |
| Licença na cópia auditada | MIT; novo aviso para contribuições posteriores, com histórico MIT preservado em `licenses/` |

## Pontos corrigidos neste pacote documental

1. README reduzido e estruturado para apresentação, instalação, arquitetura e documentação.
2. Contagem e inventário das tabelas atualizados de 15 para **18**; DER complementado com saídas/trechos/consumo.
3. Critérios de quilometragem atualizados para distinguir **modo legado** e prioridade do KM de saídas da versão atual.
4. Adicionados UML de classes e sequência, mais diagramas de componentes, DER, atividades, implantação, estados e casos de uso.
5. Adicionados glossário, guia de execução, plano de testes, segurança, ADRs, CONTRIBUTING, SECURITY, CHANGELOG e `.editorconfig`.
6. Adicionada CI básica para sintaxe e testes existentes, **sem credenciais de banco**.

## Recomendações de engenharia (não implementadas neste pacote)

| Prioridade | Assunto | Justificativa / próximo passo |
| --- | --- | --- |
| **P0** | Autenticação e autorização | Não identificado controle próprio de usuário/perfil no código; proteger dados pessoais, financeiros e operações de escrita. |
| **P0** | Backups e restauração | Verificar branch/backup do Neon e ensaiar restauração antes de mudanças no esquema ou nos dados. |
| **P1** | Migrações versionadas | `sincronizar_colunas_banco()` combina criação de tabelas e DDL na inicialização; avaliar Alembic em fluxo separado. |
| **P1** | Testes PostgreSQL de integração | SQLite não detecta diferenças de DDL, transações, tipos e constraints da produção. |
| **P1** | Cobertura financeira | Adicionar cenários automatizados de receitas, recebimentos, gastos compartilhados, atribuições/estornos e relatórios. |
| **P1** | Refatoração incremental | `app.py` concentra interface e regras; dividir por páginas/serviços somente com testes de regressão. |
| **P2** | Dependências reprodutíveis | `requirements.txt` sem versões fixas; definir estratégia de atualização e lock quando o ambiente estiver estabilizado. |
| **P2** | Auditoria abrangente | Histórico de cancelamentos/atribuições existe, mas alterações gerais e acesso não são totalmente auditados. |
| **P2** | Homologação documentada | Executar matriz de aceite com dados fictícios, evidências e assinatura dos responsáveis. |

## Limites desta entrega

**Não foram alterados:** `app.py`, `database/`, `views/`, `tests/`, `requirements.txt`, identidade visual ou qualquer registro no Neon. Foram atualizados a documentação, a política de licença para novas contribuições e a CI. A licença MIT original foi mantida integralmente no histórico `licenses/`. A CI terá execução inicial após ser enviada ao GitHub.

A [matriz de rastreabilidade](rastreabilidade.md) relaciona requisitos e módulos; o [plano de testes](plano_testes.md) descreve as evidências ainda necessárias.

## Atualização posterior — modularização conservadora (24/11/2026)

O inventário acima é um registro histórico da revisão anterior, quando o `app.py` tinha mais de 7 mil linhas. Na nova entrega, o ponto de entrada possui **74 linhas** e as 11 etapas foram movidas para `faeg_app/pages/`. As funções compartilhadas foram isoladas em `faeg_app/core.py`, relatórios em `faeg_app/reporting.py`, aparência em `faeg_app/theme.py`, contexto visual em `faeg_app/layout.py`. A restrição sobre alterações automáticas de esquema e a ausência de testes integrados PostgreSQL **permanecem**. Consulte [arquitetura da aplicação](arquitetura_aplicacao.md).
