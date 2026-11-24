# Segurança, privacidade e riscos técnicos

**Classificação:** diagnóstico documental do código compartilhado em 24/11/2026; **não foi realizado teste de invasão, auditoria LGPD ou análise de configuração da conta em nuvem**.

## Dados potencialmente sensíveis

O modelo inclui CPF, CNH, telefone, identificação de veículos, dados de empresas, documentos de transporte, endereços e valores financeiros. Considerar dados pessoais e confidenciais; permitir acesso somente a usuários autorizados.

## Observações verificadas no repositório

| Aspecto | Situação verificada / ação recomendada |
| --- | --- |
| Segredos | `.env` e `.streamlit/secrets.toml` constam do `.gitignore`; `DATABASE_URL` é obtida do ambiente. Não publicar valores reais. |
| Controle de acesso | Não foi identificado no `app.py` controle próprio de autenticação, permissões por perfil ou autorização de operações. Prioridade antes de ampliar acesso. |
| Banco de dados | A aplicação realiza operações de leitura/escrita e executa sincronização de esquema na inicialização. Planejar papel de banco de menor privilégio e migrações versionadas. |
| Trilha de auditoria | Existem cancelamentos e eventos de atribuição de despesas; **não** representam auditoria geral de toda edição e acesso. |
| Exportação | Relatórios e exportações podem reunir informações de terceiros: restringir compartilhamento e armazenamento. |
| Dependências | `requirements.txt` utiliza dependências sem versões fixadas; faltam reprodutibilidade e rotina de atualização controlada. |
| Testes | A CI de documentação executa testes isolados de saídas; não testa autorização, backups, integridade ampla nem produção. |

## Ações priorizadas

**Alta prioridade:** autenticação, autorização por função, isolamento de dados, política de backup/restauração testada, revisão das credenciais e permissões Neon/Streamlit.

**Média prioridade:** migrações versionadas, trilha de auditoria para edições críticas, análise de tratamento de dados pessoais (base legal, finalidade, retenção), validações de importação e proteção das exportações.

**Evolução:** política de dependências com versões/lock, pipeline de testes integrados PostgreSQL e revisão periódica de acessos.

Não adicionar telas com usuário/senha no código sem desenhar autenticação e gerenciamento de sessão adequados. A existência de controles de hospedagem (quando houver) **não deve ser confundida** com autorização por usuário dentro do aplicativo.
