# Casos de uso — visão funcional do sistema FAEG

O Mermaid usa aqui uma **aproximação por fluxograma**, e não a notação gráfica UML de casos de uso com elipses e atores padronizados. Isso permite exibição no GitHub sem imagem externa.

```mermaid
flowchart LR
    OP["Operador FAEG"]
    GP["Gestor operacional"]
    DV["Desenvolvedor"]
    subgraph SYS["Sistema Web FAEG - MVP"]
        C1(["Manter cadastros"])
        C2(["Cadastrar e consultar fretes"])
        C3(["Organizar ciclos operacionais"])
        C4(["Negociar e registrar recebimentos"])
        C5(["Registrar coletas e entregas"])
        C6(["Registrar despesas e abastecimentos"])
        C7(["Registrar saídas e trechos"])
        C8(["Consultar fechamento gerencial"])
        C9(["Exportar PDF e Excel"])
    end
    OP --> C1
    OP --> C2
    OP --> C3
    OP --> C4
    OP --> C5
    OP --> C6
    OP --> C7
    GP --> C8
    GP --> C9
    DV -.-> C9
```

A equipe de desenvolvimento mantém os módulos e a suíte de testes. Autenticação própria, emissão fiscal automática e importação persistente de planilhas não integram o escopo atual do MVP.
