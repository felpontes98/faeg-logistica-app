# Segurança da aplicação

O Sistema Web FAEG armazena dados operacionais, comerciais e cadastrais. O controle de acesso ao ambiente, a proteção das credenciais e a integridade das informações fazem parte da administração da aplicação.

## Controles atuais

| Componente | Implementação |
| --- | --- |
| Conexão com o banco | SQLAlchemy e `DATABASE_URL` configurada no ambiente de execução |
| Segredos | Variáveis de ambiente e configuração privada do Streamlit, fora do versionamento |
| Persistência | PostgreSQL, com validações de integridade e relacionamentos definidos no ORM |
| Histórico financeiro | Registros de recebimentos, cancelamentos e atribuições de despesas, conforme as regras de negócio |
| Autenticação de usuários | Não implementada nesta versão do MVP |

## Ambientes e publicação

**Política de ambientes:** dados operacionais permanecem em implantação de acesso restrito. Demonstrações com acesso público são destinadas a registros fictícios ou anonimizados, em banco independente da base operacional.

As credenciais e os backups são mantidos fora do repositório. Mudanças estruturais no banco são precedidas de cópia de segurança e executadas em ambiente controlado. Exportações com dados comerciais ou pessoais permanecem sob responsabilidade dos usuários autorizados.

## Comunicação de vulnerabilidades

Ocorrências de segurança são comunicadas privadamente aos responsáveis pelo projeto. Relatos contendo credenciais, documentos pessoais ou dados operacionais não são tratados em issues públicas.

## Evolução

Autenticação individual, perfis de acesso e migrações versionadas integram a evolução da plataforma. Os procedimentos de instalação e publicação estão documentados no [guia de execução](docs/guia_execucao.md).
