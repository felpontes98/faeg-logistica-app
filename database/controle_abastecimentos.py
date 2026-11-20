"""Cálculos indicativos do histórico de abastecimento, sem acesso ao banco.

O cálculo de km/L pressupõe tanque cheio em dois abastecimentos consecutivos
de Diesel do mesmo veículo. Não equivale ao consumo exato se houver abastecimento
parcial, registro faltante, troca de veículo ou alteração do odômetro.
"""


def calcular_indicadores_abastecimentos(registros):
    """Recebe dicts de abastecimentos e retorna novas linhas em ordem cronológica.

    Um intervalo é calculado apenas entre dois registros CONSECUTIVOS de Diesel
    do mesmo veículo. ARLA não altera essa sequência e não tem consumo km/L.
    Ausência ou regressão de odômetro produz indicador nulo, nunca zero fictício.
    """
    ordenados = sorted(
        registros,
        key=lambda r: (r["data_abastecimento"], r["id_abastecimento"]),
    )
    anterior_diesel = {}
    saida = []

    for registro in ordenados:
        linha = dict(registro)
        linha["km_intervalo"] = None
        linha["km_por_litro"] = None
        linha["custo_por_km"] = None
        linha["observacao"] = ""

        if linha["tipo_combustivel"] == "Diesel":
            id_veiculo = linha["id_veiculo"]
            anterior = anterior_diesel.get(id_veiculo)
            odometro = linha.get("odometro")

            if anterior is not None:
                km_anterior = anterior.get("odometro")
                if odometro is None or km_anterior is None:
                    linha["observacao"] = "Falta leitura do odômetro em um dos abastecimentos consecutivos."
                elif odometro <= km_anterior:
                    linha["observacao"] = "Leituras sem avanço ou regressivas; confira o odômetro."
                else:
                    distancia = odometro - km_anterior
                    litros = float(linha["litros"])
                    valor = float(linha["valor_total"])
                    linha["km_intervalo"] = distancia
                    if litros > 0:
                        linha["km_por_litro"] = round(distancia / litros, 2)
                    linha["custo_por_km"] = round(valor / distancia, 2)

            anterior_diesel[id_veiculo] = linha

        saida.append(linha)

    return saida
