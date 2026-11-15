import os
import sys

# Garante que a pasta raiz do projeto seja encontrada ao rodar este arquivo diretamente
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
)
from sqlalchemy.orm import relationship
from database.connection import Base, SessionLocal


# ==============================================================================
# 1. TABELAS DE DOMÍNIO (CADASTROS GERAIS / MASTER DATA)
# ==============================================================================

class Motorista(Base):
    __tablename__ = "motoristas"

    id_motorista = Column(Integer, primary_key=True, index=True)
    nome_completo = Column(String(100), nullable=False)
    cpf = Column(String(14), unique=True, nullable=False)
    telefone_contato = Column(String(20))
    cnh_numero = Column(String(20), unique=True, nullable=False)
    cnh_categoria = Column(String(5))
    cnh_validade = Column(Date)
    vinculo = Column(String(30))
    status_ativo = Column(Boolean, default=True)

    # Relacionamento: Um motorista realiza várias viagens
    viagens = relationship("Viagem", back_populates="motorista")


class Veiculo(Base):
    __tablename__ = "veiculos"

    id_veiculo = Column(Integer, primary_key=True, index=True)
    descricao_marca = Column(String(100), nullable=False)
    placa = Column(String(10), unique=True, nullable=False)
    tipo_veiculo = Column(String(30))
    renavam = Column(String(20), unique=True)
    ano_fabricacao = Column(Integer)
    capacidade_carga_kg = Column(Numeric(10, 2))
    capacidade_volume_m3 = Column(Numeric(10, 2))
    status_ativo = Column(Boolean, default=True)

    # Relacionamento: Um veículo participa de várias viagens
    viagens = relationship("Viagem", back_populates="veiculo")


class Cliente(Base):
    __tablename__ = "clientes"

    id_cliente = Column(Integer, primary_key=True, index=True)
    razao_social = Column(String(150), nullable=False)
    cnpj_cpf = Column(String(20), unique=True, nullable=False)
    inscricao_estadual = Column(String(30))
    responsavel_comercial = Column(String(100))
    telefone_comercial = Column(String(20))
    email_financeiro = Column(String(100))
    prazo_pagamento_dias = Column(Integer, default=30)

    # Relacionamento: Um cliente contrata vários ciclos operacionais
    ciclos = relationship("CicloOperacional", back_populates="cliente")


class Local(Base):
    __tablename__ = "locais"

    id_local = Column(Integer, primary_key=True, index=True)
    nome_local = Column(String(100), nullable=False)
    tipo_instalacao = Column(String(50))
    cep = Column(String(10))
    endereco_completo = Column(String(200))
    cidade = Column(String(100))
    uf = Column(String(2))
    contato_portaria = Column(String(100))
    restricao_horario = Column(String(50))


class Fornecedor(Base):
    __tablename__ = "fornecedores"

    id_fornecedor = Column(Integer, primary_key=True, index=True)
    nome_fantasia = Column(String(100), nullable=False)
    cnpj = Column(String(20), unique=True)
    categoria_servico = Column(String(50))
    cidade = Column(String(100))
    uf = Column(String(2))

    # Relacionamento: Um fornecedor recebe várias despesas lançadas
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

    # Relacionamentos
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
    valor_divulgado = Column(Numeric(10, 2))
    valor_negociado_total = Column(Numeric(10, 2))
    perc_adiantamento = Column(Numeric(5, 2))
    data_prevista_adiantamento = Column(Date)
    valor_adiantamento = Column(Numeric(10, 2))
    perc_saldo = Column(Numeric(5, 2))
    data_prevista_saldo = Column(Date)
    valor_saldo = Column(Numeric(10, 2))

    # Relacionamento 1:1 com o Ciclo Operacional
    ciclo = relationship("CicloOperacional", back_populates="financeiro")


# ==============================================================================
# 3. TABELA TRANSACIONAL CENTRAL (A VIAGEM)
# ==============================================================================

class Viagem(Base):
    __tablename__ = "viagens"

    id_viagem = Column(Integer, primary_key=True, index=True)
    id_ciclo = Column(
        Integer,
        ForeignKey("ciclos_operacionais.id_ciclo", ondelete="CASCADE"),
        nullable=False,
    )
    id_motorista = Column(Integer, ForeignKey("motoristas.id_motorista"), nullable=False)
    id_veiculo = Column(Integer, ForeignKey("veiculos.id_veiculo"), nullable=False)
    id_frete_externo = Column(String(50))
    data_criacao = Column(DateTime, server_default=func.now())
    status_viagem = Column(String(30), default="Planejada")

    # Operação
    tipo_frete = Column(String(50))
    rota_resumo = Column(String(100))
    km_rota_planejado = Column(Numeric(10, 2))

    # Logística de Coleta e Entrega
    id_local_coleta = Column(Integer, ForeignKey("locais.id_local"), nullable=False)
    data_coleta = Column(Date)
    hora_planejada_coleta = Column(Time)
    hora_real_coleta = Column(Time)
    id_local_entrega = Column(Integer, ForeignKey("locais.id_local"), nullable=False)
    data_entrega = Column(Date)
    hora_planejada_entrega = Column(Time)
    hora_real_entrega = Column(Time)

    # Dados da Carga
    tipo_material = Column(String(100))
    qtde_volumes = Column(Integer)
    peso_bruto_kg = Column(Numeric(10, 2))
    volume_m3 = Column(Numeric(10, 2))
    nfe_carga = Column(String(100))
    cte_numero = Column(String(50))
    mdfe_numero = Column(String(50))
    ciot_numero = Column(String(50))

    # Odômetro
    odometro_inicial = Column(Integer)
    odometro_final = Column(Integer)
    km_real_rodado = Column(Integer)

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
    valor_unitario = Column(Numeric(10, 2), nullable=False)
    valor_total = Column(Numeric(10, 2), nullable=False)
    data_despesa = Column(Date, server_default=func.current_date())

    # Relacionamentos
    viagem = relationship("Viagem", back_populates="despesas")
    fornecedor = relationship("Fornecedor", back_populates="despesas")


# ==============================================================================
# TESTE RÁPIDO DO MAPEAMENTO ORM
# ==============================================================================
if __name__ == "__main__":
    db = SessionLocal()
    try:
        total_motoristas = db.query(Motorista).count()
        total_ciclos = db.query(CicloOperacional).count()
        total_viagens = db.query(Viagem).count()
        print("Mapeamento ORM validado com sucesso!")
        print(f"Registros atuais -> Motoristas: {total_motoristas} | Ciclos: {total_ciclos} | Viagens: {total_viagens}")
    except Exception as e:
        print("Erro ao consultar modelos:", e)
    finally:
        db.close()