# Planejamento técnico e evolução do MVP

Este documento organiza as próximas melhorias propostas pela equipe de desenvolvimento do Sistema Web FAEG. As prioridades consideram continuidade operacional, proteção de dados e manutenção do código.

| Prioridade | Evolução | Objetivo |
| --- | --- | --- |
| Alta | Autenticação e autorização por perfil | Implementar login e permissões de acesso por usuário |
| Alta | Proteção de dados e rotinas de backup | Definir acessos, recuperação e retenção de informações operacionais |
| Alta | Testes integrados de operações críticas | Abranger ciclos, recebimentos, despesas, cancelamentos e exportações com PostgreSQL isolado |
| Média | Migrações versionadas | Controlar alterações estruturais do banco com histórico e plano de reversão |
| Média | Política de dependências | Definir versões e procedimento de atualização dos pacotes |
| Média | Refatoração incremental do núcleo compartilhado | Dividir gradualmente serviços concentrados em `faeg_app/core.py` |
| Média | Conciliação de consumo de combustível | Diferenciar compra, consumo estimado e consumo aferido com critérios operacionais |
| Evolutiva | Ampliação das análises e indicadores | Comparar ciclos, rotas e custo por quilômetro com base no histórico |

## Diretrizes de implementação

- Preservar histórico e IDs internos de fretes e ciclos.
- Não atribuir custos compartilhados a fretes sem um critério de alocação aprovado.
- Evitar migrações automáticas de despesas antigas ou mudanças financeiras sem conferência dos registros.
- Manter separadas as despesas efetivamente lançadas e as estimativas de consumo.
- Versionar mudanças com testes e documentação correspondente.

O planejamento poderá ser refinado conforme o uso do sistema pela FAEG e as necessidades das próximas versões.
