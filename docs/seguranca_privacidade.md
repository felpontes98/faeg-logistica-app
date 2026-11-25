# Segurança, privacidade e publicação

O Sistema Web FAEG processa dados de clientes, motoristas, fornecedores, veículos, documentos de transporte e operações financeiras. As permissões de acesso e a exposição de dados devem ser adequadas ao ambiente de execução.

## Controles do MVP

| Área | Diretriz |
| --- | --- |
| Credenciais | A conexão utiliza `DATABASE_URL` fornecida pelo ambiente. Arquivos `.env` e `.streamlit/secrets.toml` não são versionados. |
| Banco | Operações SQLAlchemy e relacionamentos ORM; a inicialização pode criar tabelas ou alterar colunas. Aplicar em ambiente controlado, com backup. |
| Histórico | Cancelamentos, recebimentos e atribuições de despesas mantêm registros de movimentação conforme suas regras. |
| Exportação | Relatórios podem conter informações comerciais ou pessoais e devem ser compartilhados somente por pessoas autorizadas. |
| Autenticação | O MVP ainda não implementa autenticação própria nem autorização individual por perfil. |

## Implantação pública temporária

**Um endereço Streamlit público não constitui controle de acesso.** Sem autenticação própria, qualquer visitante que abra a aplicação poderá acessar as funcionalidades disponibilizadas pela interface, inclusive consultas, exportações e ações de escrita. O uso de credenciais protegidas no servidor **não impede** que a interface pública opere sobre os dados aos quais a conexão tem acesso.

Para apresentações e demonstrações públicas:

1. Utilizar **PostgreSQL/Neon isolado da base operacional**, com dados fictícios ou efetivamente anonimizados. Uma branch clonada de produção herda os dados e **não deve ser considerada anonimizada por padrão**.
2. Configurar a `DATABASE_URL` da implantação pública exclusivamente para a base de demonstração; não reutilizar a conexão operacional.
3. Não incluir dados reais identificáveis, notas fiscais, contatos, documentos pessoais ou comprovantes nos registros e nas exportações do ambiente público.
4. Conferir se o acesso permite somente dados e funções apropriados à demonstração; descartar ou recriar a base de demonstração quando necessário.
5. Após o período público, **restringir a implantação** e conferir a conexão ao banco correspondente. Implementar autenticação individual antes de disponibilizar registros operacionais reais a mais usuários.

A visibilidade do repositório GitHub e a visibilidade do aplicativo Streamlit são configurações independentes. Tornar um repositório privado não protege, por si só, um aplicativo que continua público.

## Proteção do repositório e dos ambientes

- Não enviar para Git credenciais, arquivos `.env`, `secrets.toml`, backups de banco, exportações com dados reais ou comprovantes.
- Utilizar contas e permissões de banco adequadas ao ambiente; não compartilhar credenciais do Neon por mensagens ou capturas de tela.
- Fazer backup restaurável antes de alterações estruturais. A rotina de sincronização automática do esquema não substitui controle de migrações.
- Evitar mostrar mensagens completas de erro de conexão diretamente na interface pública; consultar os logs privados da aplicação.
- Manter bibliotecas e dependências atualizadas mediante testes e revisão do ambiente de publicação.

## Evolução

Autenticação de usuário, autorização por perfil, registros de acesso, migrações versionadas e rotinas formalizadas de backup/restauração integram o planejamento do produto. Consulte [planejamento técnico](planejamento_tecnico.md) e [execução e implantação](guia_execucao.md).
