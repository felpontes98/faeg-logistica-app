import os
import re
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    func,
    text,
)
from sqlalchemy.orm import relationship
from database.connection import Base, SessionLocal, engine


# ==============================================================================
# 1. TABELAS DE DOMÍNIO (CADASTROS GERAIS / MASTER DATA)
# ==============================================================================


class Motorista(Base):
    __tablename__ = "motoristas"

    id_motorista = Column(Integer, primary_key=True, index=True)
    nome_completo = Column(String(100), nullable=False)
    cpf = Column(String(25), unique=True, nullable=False)
    telefone_contato = Column(String(30))
    cnh_numero = Column(String(30), unique=True, nullable=False)
    cnh_categoria = Column(String(10))
    cnh_validade = Column(Date)
    vinculo = Column(String(40))
    status_ativo = Column(Boolean, default=True)

    viagens = relationship("Viagem", back_populates="motorista")


class Veiculo(Base):
    __tablename__ = "veiculos"

    id_veiculo = Column(Integer, primary_key=True, index=True)
    descricao_marca = Column(String(100), nullable=False)
    placa = Column(String(15), unique=True, nullable=False)
    tipo_veiculo = Column(String(40))
    renavam = Column(String(30), unique=True)
    ano_fabricacao = Column(Integer)
    capacidade_carga_kg = Column(Numeric(10, 2))
    capacidade_volume_m3 = Column(Numeric(10, 2))
    status_ativo = Column(Boolean, default=True)

    viagens = relationship("Viagem", back_populates="veiculo")


class Cliente(Base):
    __tablename__ = "clientes"

    id_cliente = Column(Integer, primary_key=True, index=True)
    razao_social = Column(String(150), nullable=False)
    nome_fantasia = Column(String(150))
    cnpj_cpf = Column(String(25), unique=True, nullable=False)
    inscricao_estadual = Column(String(30))
    responsavel_comercial = Column(String(100))
    telefone_comercial = Column(String(30))
    email_financeiro = Column(String(100))
    prazo_pagamento_dias = Column(Integer, default=30)
    cep = Column(String(15))
    endereco_completo = Column(String(200))
    cidade = Column(String(100))
    uf = Column(String(5))

    ciclos = relationship("CicloOperacional", back_populates="cliente")
    locais = relationship("Local", back_populates="cliente")


class Local(Base):
    __tablename__ = "locais"

    id_local = Column(Integer, primary_key=True, index=True)
    id_cliente = Column(Integer, ForeignKey("clientes.id_cliente"), nullable=True)
    nome_local = Column(String(150), nullable=False)
    tipo_instalacao = Column(String(50))
    cep = Column(String(15))
    endereco_completo = Column(String(250))
    cidade = Column(String(100))
    uf = Column(String(5))
    contato_portaria = Column(String(100))
    restricao_horario = Column(String(120))

    cliente = relationship("Cliente", back_populates="locais")


class Fornecedor(Base):
    __tablename__ = "fornecedores"

    id_fornecedor = Column(Integer, primary_key=True, index=True)
    razao_social = Column(String(150))
    nome_fantasia = Column(String(100), nullable=False)
    cnpj = Column(String(25), unique=True)
    categoria_servico = Column(String(50))
    cidade = Column(String(100))
    uf = Column(String(5))

    despesas = relationship("ViagemDespesa", back_populates="fornecedor")


# ==============================================================================
# 2. TABELAS AGRUPADORAS (O CICLO COMERCIAL E O FINANCEIRO)
# ==============================================================================


class CicloOperacional(Base):
    __tablename__ = "ciclos_operacionais"

    id_ciclo = Column(Integer, primary_key=True, index=True)
    id_cliente = Column(Integer, ForeignKey("clientes.id_cliente"), nullable=False)
    nome_operacao = Column(String(150))
    data_abertura = Column(Date)
    data_fechamento = Column(Date)
    status_ciclo = Column(String(30), default="Em Andamento")

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


class CicloFinanceiro(Base):
    __tablename__ = "ciclos_financeiro"

    id_ciclo = Column(
        Integer,
        ForeignKey("ciclos_operacionais.id_ciclo", ondelete="CASCADE"),
        primary_key=True,
    )
    forma_contratacao = Column(String(50))
    valor_divulgado = Column(Numeric(12, 2))
    valor_negociado_total = Column(Numeric(12, 2))
    perc_adiantamento = Column(Numeric(6, 2))
    data_prevista_adiantamento = Column(Date)
    valor_adiantamento = Column(Numeric(12, 2))
    perc_saldo = Column(Numeric(6, 2))
    data_prevista_saldo = Column(Date)
    valor_saldo = Column(Numeric(12, 2))
    forma_pagamento = Column(String(50))
    banco_conta = Column(String(100))
    obs_saldo = Column(String(300))

    ciclo = relationship("CicloOperacional", back_populates="financeiro")


# ==============================================================================
# 3. TABELA TRANSACIONAL CENTRAL (A VIAGEM)
# ==============================================================================


class Viagem(Base):
    __tablename__ = "viagens"

    id_viagem = Column(Integer, primary_key=True, index=True)
    codigo_viagem = Column(String(30), unique=True, index=True)
    id_ciclo = Column(
        Integer,
        ForeignKey("ciclos_operacionais.id_ciclo", ondelete="CASCADE"),
        nullable=False,
    )
    id_motorista = Column(Integer, ForeignKey("motoristas.id_motorista"), nullable=False)
    id_veiculo = Column(Integer, ForeignKey("veiculos.id_veiculo"), nullable=False)
    id_frete_externo = Column(String(50))
    data_frete = Column(Date)
    data_criacao = Column(DateTime, server_default=func.now())
    status_viagem = Column(String(30), default="Planejada")

    # Operação e Rota separada
    tipo_viagem = Column(String(50), default="Individual")
    tipo_frete = Column(String(50))
    rota_origem = Column(String(100))
    rota_destino = Column(String(100))
    rota_resumo = Column(String(210))
    km_rota_planejado = Column(Numeric(10, 2))

    # Logística de Coleta e Entrega
    id_local_coleta = Column(Integer, ForeignKey("locais.id_local"), nullable=False)
    data_coleta = Column(Date)
    hora_planejada_coleta = Column(Time)
    hora_real_coleta = Column(Time)
    obs_coleta = Column(String(300))

    id_local_entrega = Column(Integer, ForeignKey("locais.id_local"), nullable=False)
    data_entrega = Column(Date)
    hora_planejada_entrega = Column(Time)
    hora_real_entrega = Column(Time)
    documento_entrega = Column(String(100))
    obs_entrega = Column(String(300))

    # Dados da Carga e Documentos Fiscais
    tipo_material = Column(String(150))
    qtde_volumes = Column(Integer)
    peso_bruto_kg = Column(Numeric(10, 2))
    volume_m3 = Column(Numeric(10, 2))
    nfe_carga = Column(String(100))
    cte_numero = Column(String(50))
    mdfe_numero = Column(String(50))
    ciot_numero = Column(String(50))

    # Odômetro e Fechamento
    odometro_inicial = Column(Integer)
    odometro_final = Column(Integer)
    km_real_rodado = Column(Integer)
    observacao_geral = Column(String(500))

    # Relacionamentos
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


# ==============================================================================
# 4. TABELA DE DESPESAS (CUSTOS RASTREADOS NA VIAGEM)
# ==============================================================================


class ViagemDespesa(Base):
    __tablename__ = "viagens_despesas"

    id_despesa = Column(Integer, primary_key=True, index=True)
    id_viagem = Column(
        Integer,
        ForeignKey("viagens.id_viagem", ondelete="CASCADE"),
        nullable=False,
    )
    id_fornecedor = Column(Integer, ForeignKey("fornecedores.id_fornecedor"))
    tipo_despesa = Column(String(50), nullable=False)
    descricao_detalhe = Column(String(150))
    quantidade = Column(Numeric(10, 2), default=1.00)
    valor_unitario = Column(Numeric(12, 2), nullable=False)
    valor_total = Column(Numeric(12, 2), nullable=False)
    data_despesa = Column(Date, server_default=func.current_date())

    viagem = relationship("Viagem", back_populates="despesas")
    fornecedor = relationship("Fornecedor", back_populates="despesas")


# ==============================================================================
# UTILITÁRIOS DE ROTA E SEQUÊNCIA DE CÓDIGO DE VIAGEM
# ==============================================================================


def separar_rota(texto_rota: str) -> tuple[str, str]:
    """Separa textos como 'Curitiba/PR x Guarulhos/SP' ou 'SP -> RJ' em (origem, destino)."""
    if not texto_rota:
        return "", ""
    texto = str(texto_rota).strip()
    for sep in ["->", "→", " x ", " X ", " - ", " / "]:
        if sep in texto:
            partes = texto.split(sep, 1)
            return partes[0].strip(), partes[1].strip()
    return texto, ""


def gerar_proximo_codigo_viagem(db) -> str:
    """Retorna o próximo identificador sequencial (V1, V2, V3...) baseado nos códigos existentes."""
    codigos = [c[0] for c in db.query(Viagem.codigo_viagem).all() if c[0]]
    maior = 0
    for cod in codigos:
        match = re.match(r"^V(\d+)$", str(cod).strip().upper())
        if match:
            num = int(match.group(1))
            if num > maior:
                maior = num
    return f"V{maior + 1}"


# ==============================================================================
# MIGRAÇÃO SEGURA E IDEMPOTENTE DAS NOVAS COLUNAS NO NEON (POSTGRESQL)
# ==============================================================================


def sincronizar_colunas_banco():
    """Adiciona novas colunas e preenche valores legados sem afetar registros existentes."""
    comandos = [
        # Clientes, Locais e Fornecedores
        "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS nome_fantasia VARCHAR(150);",
        "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS cep VARCHAR(15);",
        "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS endereco_completo VARCHAR(200);",
        "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS cidade VARCHAR(100);",
        "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS uf VARCHAR(5);",
        "ALTER TABLE clientes ALTER COLUMN cnpj_cpf TYPE VARCHAR(25);",
        "ALTER TABLE clientes ALTER COLUMN telefone_comercial TYPE VARCHAR(30);",
        "ALTER TABLE motoristas ALTER COLUMN cpf TYPE VARCHAR(25);",
        "ALTER TABLE motoristas ALTER COLUMN cnh_numero TYPE VARCHAR(30);",
        "ALTER TABLE motoristas ALTER COLUMN telefone_contato TYPE VARCHAR(30);",
        "ALTER TABLE veiculos ALTER COLUMN placa TYPE VARCHAR(15);",
        "ALTER TABLE veiculos ALTER COLUMN renavam TYPE VARCHAR(30);",
        "ALTER TABLE locais ADD COLUMN IF NOT EXISTS id_cliente INTEGER REFERENCES clientes(id_cliente);",
        "ALTER TABLE locais ALTER COLUMN nome_local TYPE VARCHAR(150);",
        "ALTER TABLE locais ALTER COLUMN endereco_completo TYPE VARCHAR(250);",
        "ALTER TABLE locais ALTER COLUMN restricao_horario TYPE VARCHAR(120);",
        "ALTER TABLE fornecedores ADD COLUMN IF NOT EXISTS razao_social VARCHAR(150);",
        # Ciclos Financeiro
        "ALTER TABLE ciclos_financeiro ADD COLUMN IF NOT EXISTS forma_pagamento VARCHAR(50);",
        "ALTER TABLE ciclos_financeiro ADD COLUMN IF NOT EXISTS banco_conta VARCHAR(100);",
        "ALTER TABLE ciclos_financeiro ADD COLUMN IF NOT EXISTS obs_saldo VARCHAR(300);",
        # Viagens: Código único, data_frete, tipo_viagem, rota_origem, rota_destino e observações
        "ALTER TABLE viagens ADD COLUMN IF NOT EXISTS codigo_viagem VARCHAR(30);",
        "ALTER TABLE viagens ADD COLUMN IF NOT EXISTS data_frete DATE;",
        "ALTER TABLE viagens ADD COLUMN IF NOT EXISTS tipo_viagem VARCHAR(50) DEFAULT 'Individual';",
        "ALTER TABLE viagens ADD COLUMN IF NOT EXISTS rota_origem VARCHAR(100);",
        "ALTER TABLE viagens ADD COLUMN IF NOT EXISTS rota_destino VARCHAR(100);",
        "ALTER TABLE viagens ALTER COLUMN rota_resumo TYPE VARCHAR(210);",
        "ALTER TABLE viagens ALTER COLUMN tipo_material TYPE VARCHAR(150);",
        "ALTER TABLE viagens ADD COLUMN IF NOT EXISTS obs_coleta VARCHAR(300);",
        "ALTER TABLE viagens ADD COLUMN IF NOT EXISTS documento_entrega VARCHAR(100);",
        "ALTER TABLE viagens ADD COLUMN IF NOT EXISTS obs_entrega VARCHAR(300);",
        "ALTER TABLE viagens ADD COLUMN IF NOT EXISTS observacao_geral VARCHAR(500);",
    ]
    with engine.begin() as conn:
        for sql in comandos:
            conn.execute(text(sql))

    # Backfill seguro de codigo_viagem (V1, V2...) e rota_origem / rota_destino em registros antigos
    db = SessionLocal()
    try:
        viagens_sem_codigo = (
            db.query(Viagem)
            .filter((Viagem.codigo_viagem.is_(None)) | (Viagem.codigo_viagem == ""))
            .order_by(Viagem.id_viagem.asc())
            .all()
        )
        codigos_existentes = {
            str(c[0]).strip().upper()
            for c in db.query(Viagem.codigo_viagem).all()
            if c[0]
        }
        seq = 1
        for v in viagens_sem_codigo:
            while f"V{seq}" in codigos_existentes:
                seq += 1
            v.codigo_viagem = f"V{seq}"
            codigos_existentes.add(f"V{seq}")
            seq += 1

        viagens_rota_antiga = (
            db.query(Viagem)
            .filter(
                (Viagem.rota_origem.is_(None)) | (Viagem.rota_origem == ""),
                Viagem.rota_resumo.isnot(None),
                Viagem.rota_resumo != "",
            )
            .all()
        )
        for v in viagens_rota_antiga:
            orig, dest = separar_rota(v.rota_resumo)
            v.rota_origem = orig
            v.rota_destino = dest

        db.commit()
    finally:
        db.close()

    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_viagens_codigo_viagem "
                "ON viagens (codigo_viagem) WHERE codigo_viagem IS NOT NULL;"
            )
        )


if __name__ == "__main__":
    sincronizar_colunas_banco()
    db = SessionLocal()
    try:
        print("Schema e mapeamento ORM validados com sucesso!")
        print(
            f"Motoristas: {db.query(Motorista).count()} | "
            f"Clientes: {db.query(Cliente).count()} | "
            f"Viagens: {db.query(Viagem).count()}"
        )
    finally:
        db.close()