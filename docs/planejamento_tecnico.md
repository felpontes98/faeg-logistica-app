# Evolução técnica

A evolução do Sistema Web FAEG está organizada por área funcional e impacto na operação.

| Área | Objetivo |
| --- | --- |
| Acesso | Autenticação individual e autorização por perfil |
| Dados | Rotinas de backup, recuperação e retenção |
| Persistência | Migrações de esquema versionadas |
| Qualidade | Testes integrados em PostgreSQL e verificações de interface |
| Arquitetura | Separação incremental de serviços atualmente concentrados em `core.py` |
| Operação | Conciliação do consumo estimado com medições efetivas de combustível |
| Indicadores | Evolução dos relatórios de rotas, custos e desempenho por ciclo |

As mudanças mantêm a separação entre negociação comercial, execução física e apuração financeira. O histórico de fretes, ciclos, despesas e recebimentos permanece associado aos respectivos identificadores.
