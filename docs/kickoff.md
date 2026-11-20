# Projeto: FAEG - Sistema de Gestão Logística
**Documento:** Kickoff de Projeto
**Data / Versão:** 30/10/2026 - v1.0
**Autores / Responsáveis:** Felipe Pontes, Eduardo Pontes e Larissa do Espírito Santo

> **Documento histórico:** este registro preserva os objetivos e o estágio da reunião inicial. Para a situação atual do código e as correções identificadas, consultar o [Resumo do projeto](resumo_faeg.md) e os [Requisitos](requisitos.md).

---

## 1. Contexto e Objetivo do Projeto
Este documento formaliza o início do desenvolvimento de um MVP (Minimum Viable Product) acadêmico em parceria com a UMC. O objetivo principal é desenvolver um sistema de gestão logística para a empresa FAEG, substituindo o atual controle operacional e financeiro feito integralmente em planilhas. A solução visa otimizar a digitação diária de dados, criar um banco de dados histórico estruturado e facilitar a futura análise de métricas operacionais.

## 2. Cenário Atual e Dores do Cliente

### Operação Logística
A FAEG atua no ramo de transportes rodoviários, atendendo todo o Brasil (com forte atuação em São Paulo e interior).  A empresa utiliza plataformas como a FreteBras para captar fretes, trabalhando frequentemente com cargas de complemento, frete dedicado e carga completa. 

### O Gargalo da Gestão Atual
Todo o registro de viagens (ciclos) é feito de forma manual em uma planilha extensa, exigindo o controle minucioso dos seguintes dados:
* **Frota e Equipe:** Dados do veículo (placa, Renavam) e motorista.
* **Rota:** Origem, destino e quilometragem.
* **Carga:** Tipo e volume do material.
* **Financeiro:** Valor bruto do frete, adiantamentos, despesas variáveis (pedágio e combustível) e cálculo do saldo líquido.

### Principal Dor
O processo de preenchimento manual consome tempo excessivo da operação. Além disso, a visualização em formato de planilha linear dificulta a extração rápida de inteligência de negócios (Business Intelligence), como identificar as rotas mais rentáveis, clientes mais frequentes ou a eficiência por motorista.

## 3. Escopo do MVP
A primeira versão entregável (MVP) focará nas seguintes entregas estruturais:
* **Interface Otimizada:** Substituir o preenchimento linear da planilha por telas divididas por categorias de inserção de dados, facilitando a usabilidade e a rotina de trabalho.
* **Persistência de Dados:** Criar a infraestrutura de banco de dados relacional para armazenar o histórico de registros com segurança e rastreabilidade.
* **Base para Escalabilidade:** Entregar uma ferramenta simples e funcional focada na resolução do gargalo da digitação diária, que servirá como arquitetura base para o desenvolvimento de relatórios automatizados e dashboards no futuro.

## 4. Próximos Passos e Alinhamentos

* **Ação do Cliente (Concluída):** A planilha atual de controle de fretes foi enviada à equipe de desenvolvimento para estudo estrutural e engenharia reversa de fórmulas.
* **Ação da Equipe de Desenvolvimento (Em Andamento):** Análise de dados, mapeamento das regras de negócio e definição da arquitetura do novo sistema.
* **Pauta para a Próxima Reunião:** 
    * Apresentação do protótipo visual de alta fidelidade (layout das telas, sem integração backend) para validação de usabilidade com o cliente.
    * Definição e apresentação do cronograma de testes para a versão funcional do MVP.

---

## 5. Registro de evolução documental — novembro/2026

Após o kickoff, o código-fonte passou a contemplar uma aplicação Streamlit com onze etapas de navegação, nove modelos de banco, formulários operacionais, consultas, exportação de dados e relatórios. A implementação não foi homologada nesta revisão documental.

O diagnóstico estático identificou pendências que precisam ser tratadas antes de considerar concluída a migração da planilha para o sistema: integração de importação, agrupamento de vários fretes em um ciclo, fechamento consolidado, separação entre parcelas previstas e recebimentos, segurança e testes.

Os próximos passos técnicos e os critérios de aceite devem ser acompanhados em [Requisitos](requisitos.md) e [Arquitetura do banco](arquitetura_banco.md), sem alterar retrospectivamente o escopo registrado no kickoff original. A equipe poderá utilizar as Issues do GitHub para acompanhar a execução das correções.