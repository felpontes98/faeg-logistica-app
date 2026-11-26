"""Identificação automática dos fretes e vínculo com a saída de coleta.

V e FV usam uma mesma sequência numérica. O FV não contém ano.
O bloqueio transacional no PostgreSQL impede duas reservas simultâneas.
Identificadores históricos não são reescritos.
"""
import re

from sqlalchemy import func, text

from database.models import CicloOperacional, SaidaOperacional, Viagem


CODIGO_INTERNO = re.compile(r"^V([1-9][0-9]*)$", re.IGNORECASE)


def codigo_frete(numero):
    """Formata um código comercial sem referência ao ano."""
    return f"FV{int(numero):09d}"


def previsualizar_frete(codigo_viagem):
    """Apresenta a sugestão antes da gravação; reserva definitiva ocorre no banco."""
    correspondencia = CODIGO_INTERNO.fullmatch((codigo_viagem or "").strip())
    return codigo_frete(int(correspondencia.group(1))) if correspondencia else ""


def reservar_identificadores(session):
    """Reserva V e FV na transação de criação, sem modificar registros legados."""
    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(19412203)"))
    usados_v = set()
    usados_fv = set()
    maior = 0
    for id_viagem, codigo_viagem, id_frete in session.query(
        Viagem.id_viagem, Viagem.codigo_viagem, Viagem.id_frete_externo
    ).all():
        maior = max(maior, int(id_viagem))
        codigo = str(codigo_viagem or "").strip().upper()
        usados_v.add(codigo)
        usados_fv.add(str(id_frete or "").strip().upper())
        sequencia = CODIGO_INTERNO.fullmatch(codigo)
        if sequencia:
            maior = max(maior, int(sequencia.group(1)))
    numero = maior + 1
    while f"V{numero}" in usados_v or codigo_frete(numero) in usados_fv:
        numero += 1
    return f"V{numero}", codigo_frete(numero)


def ciclo_existente_unico(session, nome):
    """Recusa nomes de ciclo duplicados, sem misturar identificadores legados."""
    nome = str(nome or "").strip()
    if not nome:
        return None
    ciclos = (session.query(CicloOperacional)
              .filter(func.lower(func.trim(CicloOperacional.nome_operacao)) == nome.lower())
              .limit(2).all())
    if len(ciclos) > 1:
        raise ValueError("Há ciclos históricos com esse nome. Confira o ID interno antes de vincular um frete.")
    return ciclos[0] if ciclos else None


def validar_vinculo_saida(session, referencia, id_ciclo, id_veiculo, *, provisoria=None):
    """Confirma vínculo ao ciclo e veículo antes de gravar o frete."""
    referencia = str(referencia or "").strip()
    if not referencia:
        return None
    if referencia.startswith("s:"):
        try:
            id_saida = int(referencia[2:])
        except ValueError as exc:
            raise ValueError("A saída selecionada não é válida.") from exc
        saida = session.get(SaidaOperacional, id_saida)
        if not saida or saida.id_ciclo != id_ciclo:
            raise ValueError("A saída selecionada não pertence ao ciclo deste frete.")
        if saida.id_veiculo != id_veiculo:
            raise ValueError("O veículo do frete é diferente do veículo da saída selecionada.")
        return saida.id_saida
    if referencia.startswith("p:") and provisoria is not None:
        # A lista de saídas provisórias mantém o identificador usado na tela.
        for i, dados in enumerate(provisoria):
            if str(dados.get("id")) == referencia[2:]:
                if int(dados["id_veiculo"]) != int(id_veiculo):
                    raise ValueError("O veículo do frete é diferente do veículo da saída provisória.")
                return i
    raise ValueError("Selecione novamente uma saída válida para este frete.")
