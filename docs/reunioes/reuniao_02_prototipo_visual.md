# Projeto: FAEG - Sistema de Gestão Logística
**Documento:** Apresentação do Protótipo Visual
**Data / Versão:** 06/11/2026 - v1.0
**Participantes:** Felipe Pontes e Eduardo Pontes

---

## 1. Contexto e Objetivo da Reunião

Em continuidade ao kickoff de 30/10/2026, esta etapa documental registra a apresentação visual de um protótipo do sistema FAEG LOG, concebido para transformar o controle operacional e financeiro realizado em planilhas em um fluxo de preenchimento organizado por telas.

## 2. Estrutura apresentada

### Organização da Interface

* **Navegação por etapas:** O protótipo exibe um menu lateral que separa as informações em nove áreas: Frota FAEG, Frete e Documentos, Cliente, Negociação/Pagamento, Coleta, Entrega, Despesas de Viagem, Fechamento Final e Relatórios/Exportação.
* **Preenchimento orientado:** As telas distribuem os campos em grupos relacionados à operação, reduzindo a necessidade de percorrer uma planilha extensa.
* **Registro da viagem:** O protótipo incluiu o comando visual de salvamento; a persistência foi prevista para a implementação funcional.

### Telas Percorridas na Demonstração

* **Informações FAEG:** Estrutura inicial para identificação da viagem e dados de frota.
* **Frete, Carga e Documentos:** Campos destinados às informações do frete, da carga e da documentação vinculada.
* **Local de Coleta (Origem):** Formulário voltado à localização e aos dados operacionais da coleta.
* **Fechamento Final:** Apresentação de indicadores e de um resumo financeiro da viagem.
* **Dashboard e Exportação:** Área visual para apresentação de indicadores e acesso à exportação de informações.

## 3. Pontos de validação

* **Estrutura de navegação:** Verificar se a ordem das etapas acompanha o processo real de cadastro e fechamento de uma viagem.
* **Clareza dos formulários:** Confirmar se nomes de campos, agrupamentos e informações solicitadas são compreensíveis durante o uso cotidiano.
* **Regras operacionais e financeiras:** Validar, em testes posteriores, como os dados inseridos alimentam cálculos, indicadores e relatórios.
* **Gravação de informações:** Confirmar, na versão funcional, que o comando de salvamento mantém os registros corretamente no banco de dados.

## 4. Próximos Passos e Alinhamentos Propostos

* **Evolução do protótipo:** Consolidar a estrutura visual das etapas e ajustar eventuais campos ou agrupamentos identificados durante a avaliação.
* **Integração funcional:** Relacionar os formulários às regras de negócio e ao armazenamento estruturado dos registros.
* **Nova demonstração:** Apresentar uma versão mais completa do sistema, incluindo consultas, cadastros e o fluxo operacional e financeiro.
* **Preparação de testes:** Definir cenários para conferir o preenchimento, a recuperação dos dados e a consistência dos resultados.

## 5. Registro do Protótipo Visual

Para demonstrar a proposta inicial do Sistema FAEG, foi
desenvolvido um protótipo utilizando HTML, CSS e JavaScript.

O protótipo apresenta a organização das nove etapas previstas,
permitindo visualizar o fluxo operacional, os formulários,
o fechamento financeiro e a área de relatórios.

Essa primeira versão teve como finalidade apresentar a estrutura
visual e orientar o desenvolvimento da aplicação definitiva.

Posteriormente, o projeto evoluiu para uma aplicação web
desenvolvida em Python e Streamlit, com integração ao banco
de dados PostgreSQL.

**Arquivo de referência:**
[Protótipo Visual Inicial](../prototipo/prototipo_inicial.html)

---