# Resumo do Projeto — FAEG Logística

## Objetivo

Desenvolver um sistema web para substituir progressivamente o preenchimento operacional em Excel, mantendo a rastreabilidade de fretes individuais e ciclos, facilitando os cadastros, as consultas, os controles de gastos e os relatórios.

O projeto nasceu da operação real da **FAEG — Soluções Empresariais e Logísticas**, com processos e planilha-base apresentados por Eduardo Pontes. O desenvolvimento é conduzido por Felipe Pontes e Larissa do Espírito Santo no contexto do Startup Challenge UMC 2026.

## Estado da versão preparada (pendente de homologação no banco)

Foi realizada uma leitura estática do código e da planilha de referência. O aplicativo possui onze etapas na navegação:

| Etapa | Função presente na interface |
| --- | --- |
| 1 | Frota FAEG e área de importação Excel |
| 2 | Frete, rota, carga e documentos |
| 3 | Cliente contratante |
| 4 | Negociação e pagamento |
| 5 | Coleta |
| 6 | Entrega |
| 7 | Despesas de viagem |
| 8 | Fechamento final |
| 9 | Relatórios, indicadores e exportação |
| 10 | Consultas gerais |
| 11 | Cadastros gerais |

Os formulários, cadastros, consultas e relatórios estão presentes no código. A proposta atual acrescenta `fretes_financeiro`, totalizando **dez tabelas no ORM**. **A presença de uma tela ou de um modelo não equivale a homologação:** este código ainda precisa ser testado com uma cópia do PostgreSQL.

## Decisões operacionais da FAEG

1. **Frete e ciclo possuem identificadores diferentes.** O código do frete identifica cada serviço; o código do ciclo agrupa vários serviços.
2. **O ciclo tem um único fechamento operacional.** Receitas dos fretes são somadas; despesas comuns e quilometragem são registradas sem duplicação.
3. **A quilometragem do Maps é estimada.** A leitura de odômetro da saída/chegada e a do abastecimento são informações reais distintas e podem não estar disponíveis.
4. **Negociação e recebimento não são a mesma coisa.** Percentual e valor das parcelas podem ser calculados automaticamente, mas só valores confirmados representam dinheiro recebido.
5. **Resultado operacional não é automaticamente lucro líquido.** A nomenclatura deve refletir os gastos efetivamente considerados.

Exemplos e critérios de aceite estão documentados em [Regras de negócio](regras_negocio.md) e [Requisitos](requisitos.md).

## Atenções identificadas

| Tema | Situação |
| --- | --- |
| Importação Excel | Prévia sem gravação validada com 34 fretes, 13 ciclos e 13 fechamentos. Gravação continua **bloqueada**, pois exige conciliação de despesas e do fechamento |
| Agrupamento | Novo cadastro reutiliza ciclo existente pelo número; mantém negociação e cliente independentes em `fretes_financeiro`. **Ciclos históricos repetidos não foram migrados** |
| Fechamento | Linhas de `FECHAMENTO` são identificadas na prévia, mas não conciliadas com despesas e receitas consolidadas |
| Recebimentos | Adiantamento mais saldo passam a ser apresentados como **total previsto**, sem confundir com pagamento confirmado; falta criar registro de recebimentos efetivos |
| KM e abastecimento | Há campos de odômetro por viagem, mas não registro independente de abastecimentos |
| Segurança | Não foi identificada autenticação ou autorização de usuários no código revisado |
| Testes | Não havia suíte automatizada de testes no pacote recebido |

**Atenção antes do deploy:** o app cria tabelas ausentes na inicialização. Portanto, a nova tabela será criada assim que o app modificado abrir uma conexão com o banco configurado. É obrigatório validar a versão em um banco de testes e ter backup antes de conectar ao banco oficial. Para as próximas tarefas, a equipe pode usar as Issues do GitHub, com base nos [Requisitos](requisitos.md) e na [Arquitetura do banco](arquitetura_banco.md).

## Tecnologia e identidade visual

- Python, Streamlit, Pandas, SQLAlchemy, `psycopg` e PostgreSQL.
- Código atual concentrado em `app.py`, com persistência em `database/`.
- Tema com azul estrutural `#0D263C`, laranja `#F34D25`, branco e cinza, além do logotipo em `assets/logo_faeg.png`.
- Marca institucional: **FAEG — Soluções Empresariais e Logísticas**.

## Próxima versão

A próxima etapa é validar o novo vínculo frete–ciclo no PostgreSQL de testes, reconciliar e reagrupar os ciclos históricos duplicados, se existirem, e só então reimplementar a gravação Excel. Fechamentos, recebimentos efetivos e quilometragem vêm em seguida, com proteção dos dados existentes.

Para apresentação geral e instalação, consulte o [README](../README.md). Para a arquitetura técnica, consulte [Arquitetura do banco](arquitetura_banco.md).