from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Time,
    text,
)
from sqlalchemy.orm import relationship
from database.connection import Base, engine


class Motorista(Base):
    __tablename__ = "motoristas"

    id_motorista = Column(Integer, primary_key=True, autoincrement=True)
    nome_completo = Column(String(120), nullable=False)
    cpf = Column(String(20), unique=True, nullable=False)
    telefone_contato = Column(String(30))
    cnh_numero = Column(String(30), unique=True, nullable=False)
    cnh_categoria = Column(String(10))
    cnh_validade = Column(Date)
    vinculo = Column(String(50))
    status_ativo = Column(Boolean, default=True)

    viagens = relationship("Viagem", back_populates="motorista")


class Veiculo(Base):
    __tablename__ = "veiculos"

    id_veiculo = Column(Integer, primary_key=True, autoincrement=True)
    descricao_marca = Column(String(120), nullable=False)
    placa = Column(String(15), unique=True, nullable=False)
    tipo_veiculo = Column(String(50))
    renavam = Column(String(30), unique=True)
    ano_fabricacao = Column(Integer)
    capacidade_carga_kg = Column(Numeric(12, 2))
    capacidade_volume_m3 = Column(Numeric(12, 2))
    status_ativo = Column(Boolean, default=True)

    viagens = relationship("Viagem", back_populates="veiculo")
    abastecimentos = relationship("Abastecimento", back_populates="veiculo")


class Cliente(Base):
    __tablename__ = "clientes"

    id_cliente = Column(Integer, primary_key=True, autoincrement=True)
    razao_social = Column(String(150), nullable=False)
    nome_fantasia = Column(String(150))
    cnpj_cpf = Column(String(25), unique=True, nullable=False)
    inscricao_estadual = Column(String(30))
    responsavel_comercial = Column(String(100))
    telefone_comercial = Column(String(30))
    email_financeiro = Column(String(120))
    prazo_pagamento_dias = Column(Integer, default=30)
    cep = Column(String(15))
    endereco_completo = Column(String(250))
    cidade = Column(String(100))
    uf = Column(String(5))

    ciclos = relationship("CicloOperacional", back_populates="cliente")
    locais = relationship("Local", back_populates="cliente")


class Local(Base):
    __tablename__ = "locais"

    id_local = Column(Integer, primary_key=True, autoincrement=True)
    id_cliente = Column(Integer, ForeignKey("clientes.id_cliente"), nullable=True)
    nome_local = Column(String(150), nullable=False)
    tipo_instalacao = Column(String(50))
    cep = Column(String(15))
    endereco_completo = Column(String(250))
    cidade = Column(String(100))
    uf = Column(String(5))
    contato_portaria = Column(String(120))
    restricao_horario = Column(String(120))

    cliente = relationship("Cliente", back_populates="locais")


class Fornecedor(Base):
    __tablename__ = "fornecedores"

    id_fornecedor = Column(Integer, primary_key=True, autoincrement=True)
    razao_social = Column(String(150))
    nome_fantasia = Column(String(150), nullable=False)
    cnpj = Column(String(25), unique=True)
    categoria_servico = Column(String(80))
    cidade = Column(String(100))
    uf = Column(String(5))

    despesas = relationship("ViagemDespesa", back_populates="fornecedor")
    abastecimentos = relationship("Abastecimento", back_populates="fornecedor")


class CicloOperacional(Base):
    __tablename__ = "ciclos_operacionais"

    id_ciclo = Column(Integer, primary_key=True, autoincrement=True)
    id_cliente = Column(Integer, ForeignKey("clientes.id_cliente"), nullable=False)
    nome_operacao = Column(String(150), nullable=False)
    data_abertura = Column(Date)
    data_fechamento = Column(Date)
    status_ciclo = Column(String(50), default="Em Andamento")
    # Deslocamentos de saída, entre coletas/entregas e retorno, informados uma
    # única vez para o ciclo. Não confundir com os KM planejados de cada frete.
    km_deslocamentos_operacionais = Column(Numeric(12, 2), default=0.0)

    cliente = relationship("Cliente", back_populates="ciclos")
    financeiro = relationship(
        "CicloFinanceiro",
        back_populates="ciclo",
        uselist=False,
        cascade="all, delete-orphan",
    )
    viagens = relationship(
        "Viagem",
        back_populates="ciclo",
        cascade="all, delete-orphan",
    )
    despesas_compartilhadas = relationship("CicloDespesa", back_populates="ciclo")


class CicloFinanceiro(Base):
    __tablename__ = "ciclos_financeiro"

    id_ciclo = Column(Integer, ForeignKey("ciclos_operacionais.id_ciclo"), primary_key=True)
    forma_contratacao = Column(String(80))
    valor_divulgado = Column(Numeric(12, 2), default=0.0)
    valor_negociado_total = Column(Numeric(12, 2), default=0.0)
    perc_adiantamento = Column(Numeric(6, 2), default=0.0)
    data_prevista_adiantamento = Column(Date)
    valor_adiantamento = Column(Numeric(12, 2), default=0.0)
    perc_saldo = Column(Numeric(6, 2), default=0.0)
    data_prevista_saldo = Column(Date)
    valor_saldo = Column(Numeric(12, 2), default=0.0)

    ciclo = relationship("CicloOperacional", back_populates="financeiro")


class Viagem(Base):
    __tablename__ = "viagens"

    id_viagem = Column(Integer, primary_key=True, autoincrement=True)
    codigo_viagem = Column(String(30), unique=True, index=True)
    id_ciclo = Column(Integer, ForeignKey("ciclos_operacionais.id_ciclo"), nullable=False)
    id_motorista = Column(Integer, ForeignKey("motoristas.id_motorista"), nullable=False)
    id_veiculo = Column(Integer, ForeignKey("veiculos.id_veiculo"), nullable=False)
    id_frete_externo = Column(String(60))
    data_criacao = Column(DateTime, default=datetime.utcnow)
    status_viagem = Column(String(50), default="Aguardando Adiantamento")
    tipo_viagem = Column(String(30), default="Individual")
    tipo_frete = Column(String(50), default="Dedicado")
    rota_origem = Column(String(120))
    rota_destino = Column(String(120))
    rota_resumo = Column(String(250))
    km_rota_planejado = Column(Numeric(12, 2), default=0.0)
    tipo_material = Column(String(150))
    qtde_volumes = Column(Integer, default=0)
    peso_bruto_kg = Column(Numeric(12, 2), default=0.0)
    volume_m3 = Column(Numeric(12, 2), default=0.0)
    nfe_carga = Column(String(120))
    cte_numero = Column(String(60))
    mdfe_numero = Column(String(60))
    ciot_numero = Column(String(60))
    id_local_coleta = Column(Integer, ForeignKey("locais.id_local"), nullable=False)
    data_coleta = Column(Date)
    hora_planejada_coleta = Column(Time)
    hora_real_coleta = Column(Time)
    id_local_entrega = Column(Integer, ForeignKey("locais.id_local"), nullable=False)
    data_entrega = Column(Date)
    hora_planejada_entrega = Column(Time)
    hora_real_entrega = Column(Time)
    odometro_inicial = Column(Integer, default=0)
    odometro_final = Column(Integer, default=0)
    km_real_rodado = Column(Integer, default=0)

    ciclo = relationship("CicloOperacional", back_populates="viagens")
    motorista = relationship("Motorista", back_populates="viagens")
    veiculo = relationship("Veiculo", back_populates="viagens")
    local_coleta = relationship("Local", foreign_keys=[id_local_coleta])
    local_entrega = relationship("Local", foreign_keys=[id_local_entrega])
    despesas = relationship(
        "ViagemDespesa",
        back_populates="viagem",
        cascade="all, delete-orphan",
    )
    financeiro_frete = relationship(
        "FreteFinanceiro",
        back_populates="viagem",
        uselist=False,
        cascade="all, delete-orphan",
    )
    recebimentos = relationship("RecebimentoFrete", back_populates="viagem")


class FreteFinanceiro(Base):
    """Condições comerciais de UM frete, mesmo quando vários fretes compartilham o ciclo.

    A tabela ciclos_financeiro permanece disponível para leitura de registros antigos.
    Não se reescrevem registros históricos automaticamente.
    """

    __tablename__ = "fretes_financeiro"

    id_viagem = Column(Integer, ForeignKey("viagens.id_viagem"), primary_key=True)
    id_cliente = Column(Integer, ForeignKey("clientes.id_cliente"), nullable=False)
    forma_contratacao = Column(String(80))
    valor_divulgado = Column(Numeric(12, 2), default=0.0)
    valor_negociado_total = Column(Numeric(12, 2), default=0.0)
    perc_adiantamento = Column(Numeric(6, 2), default=0.0)
    data_prevista_adiantamento = Column(Date)
    valor_adiantamento = Column(Numeric(12, 2), default=0.0)
    perc_saldo = Column(Numeric(6, 2), default=0.0)
    data_prevista_saldo = Column(Date)
    valor_saldo = Column(Numeric(12, 2), default=0.0)

    viagem = relationship("Viagem", back_populates="financeiro_frete")
    cliente = relationship("Cliente")


class RecebimentoFrete(Base):
    """Pagamento de fato recebido, distinto de adiantamento/saldo previstos.

    Cancelamentos mantêm o registro para conferência; não apagam recebimentos.
    """

    __tablename__ = "recebimentos_frete"

    id_recebimento = Column(Integer, primary_key=True, autoincrement=True)
    id_viagem = Column(Integer, ForeignKey("viagens.id_viagem"), nullable=False, index=True)
    data_recebimento = Column(Date, nullable=False)
    tipo_parcela = Column(String(30), nullable=False)
    forma_pagamento = Column(String(40))
    referencia = Column(String(120))
    observacao = Column(String(200))
    valor_recebido = Column(Numeric(12, 2), nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow)
    cancelado = Column(Boolean, nullable=False, default=False)
    data_cancelamento = Column(Date, nullable=True)
    motivo_cancelamento = Column(String(200), nullable=True)

    viagem = relationship("Viagem", back_populates="recebimentos")


class ViagemDespesa(Base):
    __tablename__ = "viagens_despesas"

    id_despesa = Column(Integer, primary_key=True, autoincrement=True)
    id_viagem = Column(Integer, ForeignKey("viagens.id_viagem"), nullable=False)
    id_fornecedor = Column(Integer, ForeignKey("fornecedores.id_fornecedor"), nullable=True)
    tipo_despesa = Column(String(80), nullable=False)
    descricao_detalhe = Column(String(200))
    quantidade = Column(Numeric(12, 2), default=1.0)
    valor_unitario = Column(Numeric(12, 2), nullable=False)
    valor_total = Column(Numeric(12, 2), nullable=False)
    data_despesa = Column(Date)
    # Leitura feita no posto (Diesel/ARLA), independente dos odômetros da viagem.
    # NULL significa que a leitura não foi informada; não substituir por zero.
    odometro_abastecimento = Column(Integer, nullable=True)

    viagem = relationship("Viagem", back_populates="despesas")
    fornecedor = relationship("Fornecedor", back_populates="despesas")


class CicloDespesa(Base):
    """Despesa comum a todo um ciclo, sem rateio e sem repetição por frete."""

    __tablename__ = "ciclos_despesas"

    id_despesa_ciclo = Column(Integer, primary_key=True, autoincrement=True)
    id_ciclo = Column(Integer, ForeignKey("ciclos_operacionais.id_ciclo"), nullable=False, index=True)
    id_fornecedor = Column(Integer, ForeignKey("fornecedores.id_fornecedor"), nullable=True)
    tipo_despesa = Column(String(80), nullable=False)
    descricao_detalhe = Column(String(200))
    quantidade = Column(Numeric(12, 2), nullable=False, default=1.0)
    valor_unitario = Column(Numeric(12, 2), nullable=False)
    valor_total = Column(Numeric(12, 2), nullable=False)
    data_despesa = Column(Date, nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow)
    cancelado = Column(Boolean, nullable=False, default=False)
    data_cancelamento = Column(Date)
    motivo_cancelamento = Column(String(200))

    ciclo = relationship("CicloOperacional", back_populates="despesas_compartilhadas")
    fornecedor = relationship("Fornecedor")


class Abastecimento(Base):
    """Histórico de Diesel/ARLA por veículo, independente de frete ou ciclo.

    Não contabilizar automaticamente no DRE: despesas financeiras da viagem
    ficam em viagens_despesas e eventual rateio ainda precisa ser definido.
    """

    __tablename__ = "abastecimentos"

    id_abastecimento = Column(Integer, primary_key=True, autoincrement=True)
    id_veiculo = Column(Integer, ForeignKey("veiculos.id_veiculo"), nullable=False, index=True)
    id_fornecedor = Column(Integer, ForeignKey("fornecedores.id_fornecedor"), nullable=True)
    data_abastecimento = Column(Date, nullable=False)
    tipo_combustivel = Column(String(20), nullable=False)
    odometro = Column(Integer, nullable=True)
    litros = Column(Numeric(12, 2), nullable=False)
    preco_litro = Column(Numeric(12, 4), nullable=False)
    valor_total = Column(Numeric(12, 2), nullable=False)

    veiculo = relationship("Veiculo", back_populates="abastecimentos")
    fornecedor = relationship("Fornecedor", back_populates="abastecimentos")


def sincronizar_colunas_banco():
    """Cria tabelas ausentes e aplica migrações seguras (ADD COLUMN IF NOT EXISTS) no PostgreSQL."""
    Base.metadata.create_all(bind=engine)

    comandos_migracao = [
        "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS nome_fantasia VARCHAR(150);",
        "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS cep VARCHAR(15);",
        "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS endereco_completo VARCHAR(250);",
        "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS cidade VARCHAR(100);",
        "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS uf VARCHAR(5);",
        "ALTER TABLE locais ADD COLUMN IF NOT EXISTS id_cliente INTEGER REFERENCES clientes(id_cliente);",
        "ALTER TABLE fornecedores ADD COLUMN IF NOT EXISTS razao_social VARCHAR(150);",
        "ALTER TABLE viagens ADD COLUMN IF NOT EXISTS codigo_viagem VARCHAR(30);",
        "ALTER TABLE viagens ADD COLUMN IF NOT EXISTS tipo_viagem VARCHAR(30) DEFAULT 'Individual';",
        "ALTER TABLE viagens ADD COLUMN IF NOT EXISTS rota_origem VARCHAR(120);",
        "ALTER TABLE viagens ADD COLUMN IF NOT EXISTS rota_destino VARCHAR(120);",
        "ALTER TABLE ciclos_operacionais ADD COLUMN IF NOT EXISTS km_deslocamentos_operacionais NUMERIC(12, 2) DEFAULT 0;",
        "ALTER TABLE viagens_despesas ADD COLUMN IF NOT EXISTS data_despesa DATE;",
        "ALTER TABLE viagens_despesas ADD COLUMN IF NOT EXISTS odometro_abastecimento INTEGER;",
        "ALTER TABLE viagens ALTER COLUMN rota_resumo TYPE VARCHAR(250);",
        "ALTER TABLE viagens ALTER COLUMN nfe_carga TYPE VARCHAR(120);",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_viagens_codigo_viagem ON viagens (codigo_viagem);",
    ]

    with engine.begin() as conn:
        for sql in comandos_migracao:
            conn.execute(text(sql))

        # Preenche codigo_viagem (V1, V2...) em viagens antigas que ainda não possuem código
        rows_sem_cod = conn.execute(
            text("SELECT id_viagem FROM viagens WHERE codigo_viagem IS NULL OR TRIM(codigo_viagem) = '' ORDER BY id_viagem ASC")
        ).fetchall()

        if rows_sem_cod:
            existentes = conn.execute(
                text("SELECT codigo_viagem FROM viagens WHERE codigo_viagem IS NOT NULL AND TRIM(codigo_viagem) <> ''")
            ).fetchall()
            usados = {str(r[0]).strip().upper() for r in existentes}
            seq = 1
            for (id_v,) in rows_sem_cod:
                while f"V{seq}" in usados:
                    seq += 1
                cod_novo = f"V{seq}"
                usados.add(cod_novo)
                conn.execute(
                    text("UPDATE viagens SET codigo_viagem = :cod WHERE id_viagem = :id_v"),
                    {"cod": cod_novo, "id_v": id_v},
                )
                seq += 1

        # Migra rota_resumo antiga ("Origem -> Destino" ou "Origem x Destino") para rota_origem e rota_destino
        rows_rota = conn.execute(
            text(
                """
                SELECT id_viagem, rota_resumo
                FROM viagens
                WHERE (rota_origem IS NULL OR TRIM(rota_origem) = '')
                  AND (rota_destino IS NULL OR TRIM(rota_destino) = '')
                  AND rota_resumo IS NOT NULL
                  AND TRIM(rota_resumo) <> ''
                """
            )
        ).fetchall()

        for id_v, r_res in rows_rota:
            txt = str(r_res).strip()
            if "->" in txt:
                partes = txt.split("->", 1)
                orig, dest = partes[0].strip(), partes[1].strip()
            elif " x " in txt.lower():
                idx_x = txt.lower().find(" x ")
                orig, dest = txt[:idx_x].strip(), txt[idx_x + 3 :].strip()
            else:
                orig, dest = txt, ""
            conn.execute(
                text("UPDATE viagens SET rota_origem = :o, rota_destino = :d WHERE id_viagem = :id_v"),
                {"o": orig, "d": dest, "id_v": id_v},
            )


if __name__ == "__main__":
    sincronizar_colunas_banco()
    print("Schema FAEG sincronizado com sucesso!")
