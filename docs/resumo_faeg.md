# Especificação Técnica e Regras de Negócio — FAEG Logística

## 1. Visão Geral e Infraestrutura em Nuvem
* **Escopo:** MVP desenvolvido por Felipe Pontes e Larissa do Espírito Santo para o **Startup Challenge UMC 2026 (Trilha T2)**, substituindo planilhas manuais da transportadora FAEG por um sistema web integrado.
* **Stack Tecnológica:** Python + **Streamlit** (`app.py`), **SQLAlchemy** + `psycopg[binary]`, **Pandas** + `openpyxl`, banco **PostgreSQL Serverless no Neon.tech** (`neondb`, com *pooled connection*) e deploy contínuo no **Streamlit Community Cloud** via GitHub (`felpontes98/faeg-logistica-app`, branch `main`).
* **Estrutura do Repositório:**
  * `app.py`: interface principal de 11 etapas, regras de cálculo, geração de PDF e exportação Excel.
  * `database/connection.py`: conexão SQLAlchemy lendo `DATABASE_URL` do `.env` (ou *Secrets* na nuvem) com `pool_pre_ping=True` e `pool_recycle=300`.
  * `database/models.py`: mapeamento ORM das **9 tabelas** e função `sincronizar_colunas_banco()` (migração segura via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`).
  * `database/importador_planilha.py`: leitura, mapeamento e conciliação financeira da planilha operacional `.xlsx` da FAEG.
  * `assets/logo_faeg.png` e `.streamlit/config.toml`: logotipo oficial e configurações de tema.
  * `.gitignore`: protege `.env`, `.streamlit/secrets.toml`, `.venv/`, `.vscode/` e `__pycache__/`.

## 2. Arquitetura do Banco de Dados (9 Tabelas no Neon)

| Camada | Tabelas | Relacionamentos e Colunas-Chave |
| :--- | :--- | :--- |
| **Cadastros Base (Master Data)** | `motoristas`, `veiculos`, `clientes`, `locais`, `fornecedores` | `clientes` separa `razao_social` e `nome_fantasia`; `locais` vincula `id_cliente`; `fornecedores` guarda `razao_social` e `categoria_servico`. |
| **Agrupadores Comerciais** | `ciclos_operacionais`, `ciclos_financeiro` | `clientes` (1:N) `ciclos_operacionais` (1:1) `ciclos_financeiro` (valores negociados, adiantamento e saldo). |
| **Operação e Custos** | `viagens`, `viagens_despesas` | `ciclos_operacionais` (1:N) `viagens` (1:N) `viagens_despesas`; inclui `codigo_viagem` (`V1`, `V2`...), `tipo_viagem`, `tipo_frete`, `rota_origem` e `rota_destino` separados. |

## 3. Identidade Visual Oficial (Manual da Marca FAEG 2026)
* **Paleta Cromática Obrigatória:**
  * **Azul Estrutural (`#0D263C` — 45%):** barra lateral (*sidebar*), títulos de etapa, cabeçalhos de tabela e cartão DRE.
  * **Branco (`#FFFFFF` — 25%):** cartões de conteúdo e fundo de todos os campos editáveis (`:root { color-scheme: light !important; }` para impedir campos pretos/escuros).
  * **Cinza Névoa (`#E9E9E9` / `#F1F5F9` — 15%):** fundo geral da página e campos calculados automaticamente (`disabled`).
  * **Azul Expansão (`#ABCEE1` — 10%):** destaques suaves, seleção em listas e banners de recebimento.
  * **Laranja Energia (`#F34D25` — 5%):** botão principal **Salvar Viagem**, borda do item ativo no menu, abas selecionadas, alertas e totais de despesa.
* **Tipografia e Layout:** fonte **Montserrat** + ícones FontAwesome; *sidebar* com composição harmônica de `assets/logo_faeg.png` à esquerda + **FAEG — Soluções Empresariais e Logísticas** à direita; cartão fixo de **Operação / Viagem Ativa** na *sidebar*; *Top Context Bar* executiva; grades de 12 unidades sem truncamento de rótulos.

## 4. Regras de Negócio e Fluxo das 11 Etapas (`app.py`)
1. **1. Frota FAEG:** seleção de motorista e veículo com preenchimento automático; geração automática e editável do **Código Único Sequencial (`V1`, `V2`, `V3`...)** com validação de unicidade; painel recolhível para **Importação da Planilha FAEG (`.xlsx`)**.
2. **2. Frete e Docs:** distinção entre **Tipo de Viagem** (`Individual`, `Dedicado`, `Complemento`, `Retorno`, `Transferência`) e **Tipo de Frete**; bloqueio do campo de ciclo quando `Individual`; rota dividida em **Origem** e **Destino** individuais; carga e docs fiscais (`NF-e`, `CT-e`, `MDF-e`, `CIOT`).
3. **3. Cliente:** seleção do contratante com preenchimento automático de dados comerciais e vínculo automático com o local de coleta correspondente.
4. **4. Negociação / Pgto:** cálculo **bidirecional e independente** (`% Adiantamento` <-> `Valor Adiantamento R$` e `% Saldo` <-> `Valor Saldo R$`), soma automática de **Valor Total Recebido** e **Situação do Pagamento / Operação** sugerida.
5. **5. Coleta (Origem)** e **6. Entrega (Destino):** seleção de locais cadastrados com preenchimento automático de endereço, datas no padrão brasileiro (`DD/MM/AAAA`) e horários planejados/reais.
6. **7. Despesas de Viagem:** lançamento vinculado a fornecedores com categorias unificadas (`Posto de Combustível`, `Abast. ARLA`, `Oficina Mecânica`, `Borracharia`, `Hospedagem`, `Concessionária Pedágio`, `Auxiliar`, `Alimentação`, `Lava-jato`, `Outros`).
7. **8. Fechamento Final:** cálculo automático de `KM Real Rodado` pelo hodômetro e painel **DRE — FAEG** (`Receita Total - Custos Totais = Resultado Líquido`).
8. **9. Relatórios / Exportar:** unificada em 2 sub-abas (`st.tabs`): **Relatório da Viagem Ativa** (KPIs, gráfico, PDF individual e Excel) e **Painel Geral (BI Consolidado)** (filtros, métricas globais, gráficos comparativos, desempenho por cliente, PDF executivo consolidado e exportação da base completa em Excel multi-abas).
9. **10. Consultas Gerais:** filtros por busca textual, tipo de viagem, situação e origem de frete, permitindo abrir e editar qualquer viagem já salva.
10. **11. Cadastros Gerais:** organizada em **5 abas internas (`st.tabs`)** (`Motoristas`, `Veículos`, `Clientes`, `Locais / Bases`, `Fornecedores / Postos`) com confirmação de exclusão em 2 etapas.
