"""Dados somente de apresentação carregados no início de cada rerun Streamlit."""
from dataclasses import dataclass, field


@dataclass
class PageContext:
    motoristas_db: list
    veiculos_db: list
    clientes_db: list
    locais_db: list
    fornecedores_db: list
    viagens_db: list
    viagem_sel_id: int
    prox_cod_sidebar: str = ""
    menu_itens: list[str] = field(default_factory=list)
    cli_nome_ctx: str = ""
    id_label_ctx: str = ""
    mot_nome_ctx: str = ""
    status_ctx: str = ""
