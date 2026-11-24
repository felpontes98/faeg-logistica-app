# Segurança e privacidade

## Dados sob responsabilidade da aplicação

O sistema manipula informações operacionais e comerciais, como documentos de transporte, contatos, dados de veículos e motoristas, endereços, clientes e valores financeiros. O acesso e o compartilhamento desses registros devem respeitar as necessidades da operação e a legislação aplicável.

## Controles da versão atual

| Tema | Implementação e diretriz |
| --- | --- |
| Configurações sensíveis | A conexão ao banco utiliza `DATABASE_URL`; os arquivos locais `.env` e `.streamlit/secrets.toml` estão excluídos do versionamento pelo `.gitignore`. |
| Controle de acesso | O MVP ainda não implementa autenticação própria nem permissões individuais por perfil. O acesso deve ser controlado na implantação e pelos responsáveis pelo ambiente. |
| Persistência | O SQLAlchemy realiza operações de leitura e escrita no PostgreSQL. A inicialização sincroniza o esquema, motivo pelo qual mudanças estruturais requerem controle de versão e backup. |
| Histórico operacional | Cancelamentos e atribuições de despesas possuem registros específicos. Uma trilha geral de auditoria por usuário integra a evolução técnica planejada. |
| Exportações | Os relatórios podem conter informações comerciais ou pessoais; devem ser gerados e compartilhados somente em contextos autorizados. |
| Bibliotecas | As dependências são declaradas em `requirements.txt`. A fixação de versões e a política de atualização fazem parte do planejamento técnico. |

## Evolução de segurança

O planejamento contempla autenticação por usuário, autorização por função, revisão de permissões, política de backup e restauração, retenção adequada de dados, registro de ações críticas e proteção de exportações.

As informações de credenciais e os dados de clientes não devem ser publicados em commits, documentos, imagens ou repositórios públicos. Consulte [planejamento técnico](planejamento_tecnico.md) e [guia de execução](guia_execucao.md).
