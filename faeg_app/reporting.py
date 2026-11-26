"""Geração de relatórios e exportações gerenciais em Excel e PDF."""

import base64
import io
import os
import zlib
from datetime import date

import pandas as pd

from database.connection import SessionLocal
from database.fechamento_ciclos import consolidar_ciclos, reconciliar_resultado_gerencial
from database.saidas_operacionais import consultar_todas_saidas, resumo_saidas

def gerar_excel_base_completa(todas_viagens, desp_detalhadas, motoristas, veiculos, clientes, locais, fornecedores, abastecimentos=None, fechamentos_ciclos=None, recebimentos=None, despesas_ciclo=None, despesas_veiculo=None, atribuicoes_veiculo=None, alertas_despesas=None):
    """Gera arquivo Excel (.xlsx) completo com todas as viagens, despesas e cadastros do sistema."""
    buf = io.BytesIO()
    # Única leitura por exportação; os trechos são eager-loaded para uso após fechar a sessão.
    with SessionLocal() as db:
        registros_saida = consultar_todas_saidas(db)
        por_ciclo_export = {}
        for saida in registros_saida:
            por_ciclo_export.setdefault(saida.id_ciclo, []).append(saida)
        resumos_export = {cid: resumo_saidas(lista) for cid, lista in por_ciclo_export.items()}

    df_viagens = pd.DataFrame(
        [
            {
                "Código Viagem": v["codigo_viagem"],
                "ID Frete": v["id_frete"],
                "Saída de Coleta": v.get("saida_coleta", "-"),
                "ID Interno Saída": v.get("id_saida_coleta"),
                "Situação": v["status"],
                "Tipo Viagem": v["tipo_viagem"],
                "Ciclo": v["ciclo"],
                "Tipo Frete": v["tipo_frete"],
                "Origem Frete": v["origem_frete"],
                "Data Coleta": v["data_coleta"].strftime("%d/%m/%Y") if v["data_coleta"] else "-",
                "Data Entrega": v["data_entrega"].strftime("%d/%m/%Y") if v["data_entrega"] else "-",
                "Cliente": v["cliente"],
                "Motorista": v["motorista"],
                "Veículo": v["veiculo"],
                "Origem": v["rota_origem"],
                "Destino": v["rota_destino"],
                "Rota": v["rota"],
                "Coleta": v["coleta"],
                "Entrega": v["entrega"],
                "NF-e": v["nfe"],
                "CT-e": v["cte"],
                "MDF-e": v["mdfe"],
                "CIOT": v["ciot"],
                "Valor Divulgado (R$)": v["valor_divulgado"],
                "Valor Negociado (R$)": v["valor_negociado"],
                "Receita Considerada (R$)": v["receita_base"],
                "Conferência Financeira": (
                    "Legado ambíguo — conferir" if v["financeiro_legado_ambiguo"]
                    else "Por frete"
                ),
                "Adiantamento (R$)": v["valor_adiantamento"],
                "Saldo (R$)": v["valor_saldo"],
                "Parcelas Previstas (R$)": v["total_previsto"],
                "Recebido de Fato (R$)": v["total_recebido"],
                "Saldo a Receber (R$)": v["saldo_a_receber"],
                "Excedente Recebido (R$)": v["excedente_recebido"],
                "Despesas Totais (R$)": v["total_despesas"],
                "Resultado Operacional Parcial (R$)": v["resultado_liquido"],
                "Margem (%)": (
                    round(v["margem_pct"], 2)
                    if v["receita_base"] > 0 and v["tipo_viagem"] != "Ciclo"
                    and not v["financeiro_legado_ambiguo"] else None
                ),
                "KM Individual / Ciclo": v["km_rota_planejado"],
                "KM Saída / Entre Coletas (ciclo)": v["km_saida_entre_coletas"],
                "KM Retorno Operacional (ciclo)": v["km_retorno_operacional"],
                "KM Deslocamentos Total (ciclo)": v["km_deslocamentos_operacionais"],
                "Odômetro Inicial (operação)": v["odometro_inicial"] or None,
                "Odômetro Final (operação)": v["odometro_final"] or None,
                "KM Rodado": v["km_rodado"],
                "Custo por KM (R$)": round(v["custo_km"], 2) if v["custo_km"] is not None else None,
            }
            for v in todas_viagens
        ]
    )

    df_desp = pd.DataFrame(desp_detalhadas)
    df_mot = pd.DataFrame(motoristas)
    df_vei = pd.DataFrame(veiculos)
    df_cli = pd.DataFrame(clientes)
    df_loc = pd.DataFrame(locais)
    df_forn = pd.DataFrame(fornecedores)
    veiculos_map = {v["id_veiculo"]: v["placa"] for v in veiculos}
    df_abast = pd.DataFrame([
        {
            "Data": a["data_abastecimento"].strftime("%d/%m/%Y"),
            "Placa": veiculos_map.get(a["id_veiculo"], "-"),
            "Veículo ID": a["id_veiculo"],
            "Tipo": a["tipo_combustivel"],
            "Odômetro (km)": a["odometro"],
            "Litros": a["litros"],
            "Preço por Litro (R$)": a["preco_litro"],
            "Valor Total (R$)": a["valor_total"],
            "Despesa Frete ID": a.get("id_despesa_viagem"),
            "Despesa Ciclo ID": a.get("id_despesa_ciclo"),
            "Despesa Veículo ID": a.get("id_despesa_veiculo"),
            "Origem Financeira": a.get("origem_financeira"),
            "Situação": "Cancelado" if a.get("cancelado") else "Ativo",
            "Data Cancelamento": a["data_cancelamento"].strftime("%d/%m/%Y") if a.get("data_cancelamento") else None,
            "Motivo Cancelamento": a.get("motivo_cancelamento"),
            "KM entre Diesel": a["km_intervalo"],
            "KM/L Indicativo": a["km_por_litro"],
            "R$/KM Indicativo": a["custo_por_km"],
            "Observação": a["observacao"],
        }
        for a in (abastecimentos or [])
    ], columns=[
        "Data", "Placa", "Veículo ID", "Tipo", "Odômetro (km)", "Litros",
        "Preço por Litro (R$)", "Valor Total (R$)",
        "Despesa Frete ID", "Despesa Ciclo ID", "Despesa Veículo ID", "Origem Financeira",
        "Situação", "Data Cancelamento", "Motivo Cancelamento", "KM entre Diesel",
        "KM/L Indicativo", "R$/KM Indicativo", "Observação",
    ])
    df_ciclos = pd.DataFrame([
        {
            "ID Interno Ciclo": f["id_ciclo"],
            "Código Ciclo": f["ciclo"],
            "Quantidade Fretes": f["qtd_fretes"],
            "IDs Frete": ", ".join(f["ids_frete"]),
            "Clientes": ", ".join(f["clientes"]),
            "Negociado (R$)": f["valor_negociado_total"],
            "Adiantamentos Previstos (R$)": f["adiantamentos_previstos"],
            "Saldos Previstos (R$)": f["saldos_previstos"],
            "Parcelas Previstas (R$)": f["parcelas_previstas"],
            "Recebido de Fato (R$)": f["total_recebido"],
            "Saldo a Receber (R$)": f["saldo_a_receber"],
            "Excedente Recebido (R$)": f["excedente_recebido"],
            "Despesas dos Fretes (R$)": f["despesas_fretes_total"],
            "Despesas Compartilhadas (R$)": f["despesas_compartilhadas_total"],
            "Despesas Financeiras (R$)": f["despesas_total"],
            "Resultado Operacional Parcial (R$)": f["resultado_operacional_parcial"],
            "KM Fretes Planejados": f["km_planejado_fretes"],
            "KM Saída / Entre Coletas": f["km_saida_entre_coletas"],
            "KM Retorno Operacional": f["km_retorno_operacional"],
            "KM Deslocamentos": f["km_deslocamentos_operacionais"],
            "KM Total Planejado": (
                resumos_export[f["id_ciclo"]]["km_planejado"]
                if f["id_ciclo"] in resumos_export else f["km_total_planejado"]
            ),
            "KM Real Operacional": (
                resumos_export[f["id_ciclo"]]["km_real"]
                if f["id_ciclo"] in resumos_export else None
            ),
            "Fonte de KM": "Saídas operacionais" if f["id_ciclo"] in resumos_export else "Legado por fretes",
            "Fretes com Financeiro Legado Ambíguo": f["qtd_financeiros_legados_ambiguos"],
        }
        for f in (fechamentos_ciclos if fechamentos_ciclos is not None else consolidar_ciclos(todas_viagens))
    ], columns=[
        "ID Interno Ciclo", "Código Ciclo", "Quantidade Fretes", "IDs Frete",
        "Clientes", "Negociado (R$)", "Adiantamentos Previstos (R$)",
        "Saldos Previstos (R$)", "Parcelas Previstas (R$)",
        "Recebido de Fato (R$)", "Saldo a Receber (R$)", "Excedente Recebido (R$)",
        "Despesas dos Fretes (R$)", "Despesas Compartilhadas (R$)",
        "Despesas Financeiras (R$)", "Resultado Operacional Parcial (R$)",
        "KM Fretes Planejados", "KM Saída / Entre Coletas",
        "KM Retorno Operacional", "KM Deslocamentos", "KM Total Planejado",
        "KM Real Operacional", "Fonte de KM", "Fretes com Financeiro Legado Ambíguo",
    ])
    df_recebimentos = pd.DataFrame([
        {
            "Código Viagem": r["codigo_viagem"],
            "ID Frete": r["id_frete"],
            "Data Recebimento": r["data_recebimento"].strftime("%d/%m/%Y"),
            "Tipo Parcela": r["tipo_parcela"],
            "Forma Pagamento": r["forma_pagamento"],
            "Referência": r["referencia"],
            "Observação": r["observacao"],
            "Valor (R$)": r["valor_recebido"],
            "Situação": "Cancelado" if r["cancelado"] else "Confirmado",
            "Data Cancelamento": r["data_cancelamento"].strftime("%d/%m/%Y") if r["data_cancelamento"] else None,
            "Motivo Cancelamento": r["motivo_cancelamento"],
        }
        for r in (recebimentos or [])
    ], columns=[
        "Código Viagem", "ID Frete", "Data Recebimento", "Tipo Parcela",
        "Forma Pagamento", "Referência", "Observação", "Valor (R$)",
        "Situação", "Data Cancelamento", "Motivo Cancelamento",
    ])
    fornecedores_map = {f["id_fornecedor"]: f["nome_fantasia"] for f in fornecedores}
    df_despesas_ciclo = pd.DataFrame([
        {
            "ID Despesa Ciclo": d["id_despesa_ciclo"],
            "ID Interno Ciclo": d["id_ciclo"],
            "Código Ciclo": d["ciclo"],
            "Data": d["data_despesa"].strftime("%d/%m/%Y"),
            "Categoria": d["tipo_despesa"],
            "Descrição": d["descricao_detalhe"],
            "Fornecedor": fornecedores_map.get(d["id_fornecedor"], "Não informado"),
            "Quantidade": d["quantidade"],
            "Valor Unitário (R$)": d["valor_unitario"],
            "Valor Total (R$)": d["valor_total"],
            "Situação": "Cancelada" if d["cancelado"] else "Ativa",
            "Data Cancelamento": d["data_cancelamento"].strftime("%d/%m/%Y") if d["data_cancelamento"] else None,
            "Motivo Cancelamento": d["motivo_cancelamento"],
        }
        for d in (despesas_ciclo or [])
    ], columns=[
        "ID Despesa Ciclo", "ID Interno Ciclo", "Código Ciclo", "Data",
        "Categoria", "Descrição", "Fornecedor", "Quantidade", "Valor Unitário (R$)",
        "Valor Total (R$)", "Situação", "Data Cancelamento", "Motivo Cancelamento",
    ])
    df_despesas_veiculo = pd.DataFrame([
        {
            "ID Despesa Veículo": d["id_despesa_veiculo"],
            "Placa": veiculos_map.get(d["id_veiculo"], "Não informada"),
            "ID Veículo": d["id_veiculo"],
            "Data": d["data_despesa"].strftime("%d/%m/%Y"),
            "Categoria": d["tipo_despesa"],
            "Descrição": d["descricao_detalhe"],
            "Fornecedor": fornecedores_map.get(d["id_fornecedor"], "Não informado"),
            "Quantidade": d["quantidade"],
            "Valor Unitário (R$)": d["valor_unitario"],
            "Valor Total (R$)": d["valor_total"],
            "Situação": (
                "Cancelada" if d["cancelado"] else
                "Atribuída ao frete" if d["id_despesa_viagem_destino"] else
                "Atribuída ao ciclo" if d["id_despesa_ciclo_destino"] else
                "Pendente de atribuição"
            ),
            "ID Despesa Frete Destino": d["id_despesa_viagem_destino"],
            "ID Despesa Ciclo Destino": d["id_despesa_ciclo_destino"],
            "Data Atribuição": d["data_atribuicao"].strftime("%d/%m/%Y") if d["data_atribuicao"] else None,
            "Data Cancelamento": d["data_cancelamento"].strftime("%d/%m/%Y") if d["data_cancelamento"] else None,
            "Motivo Cancelamento": d["motivo_cancelamento"],
        }
        for d in (despesas_veiculo or [])
    ], columns=[
        "ID Despesa Veículo", "Placa", "ID Veículo", "Data", "Categoria", "Descrição",
        "Fornecedor", "Quantidade", "Valor Unitário (R$)", "Valor Total (R$)",
        "Situação", "ID Despesa Frete Destino", "ID Despesa Ciclo Destino",
        "Data Atribuição", "Data Cancelamento", "Motivo Cancelamento",
    ])
    df_atribuicoes = pd.DataFrame([
        {
            "ID Evento": e["id_evento"],
            "ID Despesa Veículo": e["id_despesa_veiculo"],
            "Ação": e["acao"],
            "Tipo Destino": e["tipo_destino"],
            "ID Frete/Ciclo Interno": e["id_destino"],
            "ID Lançamento Destino": e["id_lancamento_destino"],
            "Data/Hora": e["data_evento"].strftime("%d/%m/%Y %H:%M"),
            "Justificativa": e["motivo"],
        }
        for e in (atribuicoes_veiculo or [])
    ], columns=[
        "ID Evento", "ID Despesa Veículo", "Ação", "Tipo Destino",
        "ID Frete/Ciclo Interno", "ID Lançamento Destino", "Data/Hora", "Justificativa",
    ])
    conciliacao = reconciliar_resultado_gerencial(todas_viagens, despesas_ciclo, despesas_veiculo)
    df_conciliacao = pd.DataFrame([
        {
            "Indicador": "Receita negociada considerada dos fretes",
            "Valor (R$)": conciliacao["receita_negociada_considerada"],
            "Tratamento": "Receita (financeiro legado ambíguo excluído)",
        },
        {
            "Indicador": "Despesas financeiras dos fretes",
            "Valor (R$)": conciliacao["despesas_fretes"],
            "Tratamento": "Subtrair uma vez (origem viagens_despesas)",
        },
        {
            "Indicador": "Despesas compartilhadas ativas dos ciclos",
            "Valor (R$)": conciliacao["despesas_compartilhadas"],
            "Tratamento": "Subtrair uma vez (origem ciclos_despesas), sem rateio",
        },
        {
            "Indicador": "Total de despesas contabilizadas",
            "Valor (R$)": conciliacao["despesas_financeiras_totais"],
            "Tratamento": "Fretes + compartilhadas; sem abastecimento duplicado",
        },
        {
            "Indicador": "Resultado operacional parcial gerencial",
            "Valor (R$)": conciliacao["resultado_operacional_parcial"],
            "Tratamento": "Receita considerada - despesas contabilizadas",
        },
        {
            "Indicador": "Despesas de veículo ainda pendentes",
            "Valor (R$)": conciliacao["despesas_veiculo_pendentes"],
            "Tratamento": "NÃO somar ao resultado enquanto não atribuídas",
        },
        {
            "Indicador": "Despesas de veículo já atribuídas (informativo)",
            "Valor (R$)": conciliacao["despesas_veiculo_ja_atribuidas"],
            "Tratamento": "JÁ incluídas no frete/ciclo — NÃO somar novamente",
        },
        {
            "Indicador": "Recebido efetivamente dos fretes",
            "Valor (R$)": conciliacao["total_recebido"],
            "Tratamento": "Fluxo recebido; não é receita negociada adicional",
        },
        {
            "Indicador": "Saldo a receber dos fretes",
            "Valor (R$)": conciliacao["saldo_a_receber"],
            "Tratamento": "Incalculável se houver financeiro legado ambíguo",
        },
        {
            "Indicador": "Conferência: fretes com financeiro legado ambíguo",
            "Valor (R$)": None,
            "Tratamento": (
                f"{conciliacao['qtd_financeiros_legados_ambiguos']} frete(s) — "
                "receita excluída até individualização; resultado parcial"
            ),
        },
        {
            "Indicador": "Conferência: despesas de ciclo sem frete do tipo Ciclo",
            "Valor (R$)": None,
            "Tratamento": (
                f"{conciliacao['qtd_despesas_ciclo_sem_fretes']} despesa(s) — "
                "incluídas no total gerencial, mas ausentes dos fechamentos por ciclo"
            ),
        },
    ], columns=["Indicador", "Valor (R$)", "Tratamento"])
    df_alertas_despesas = pd.DataFrame([
        {
            **a,
            "Data": a["Data"].strftime("%d/%m/%Y") if a.get("Data") else None,
        }
        for a in (alertas_despesas or [])
    ], columns=[
        "ID Ciclo", "Código Ciclo", "ID Frete", "ID Despesa Frete",
        "ID Despesa Ciclo", "Data", "Categoria", "Descrição", "Valor (R$)", "Situação",
    ])

    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_viagens.to_excel(writer, sheet_name="Viagens_e_Ciclos", index=False)
        df_desp.to_excel(writer, sheet_name="Despesas_Viagens", index=False)
        df_mot.to_excel(writer, sheet_name="Cad_Motoristas", index=False)
        df_vei.to_excel(writer, sheet_name="Cad_Veiculos", index=False)
        df_cli.to_excel(writer, sheet_name="Cad_Clientes", index=False)
        df_loc.to_excel(writer, sheet_name="Cad_Locais", index=False)
        df_forn.to_excel(writer, sheet_name="Cad_Fornecedores", index=False)
        df_abast.to_excel(writer, sheet_name="Abastecimentos_Veiculos", index=False)
        df_ciclos.to_excel(writer, sheet_name="Fechamento_Ciclos", index=False)
        df_conciliacao.to_excel(writer, sheet_name="Conferencia_Financeira", index=False)
        df_alertas_despesas.to_excel(writer, sheet_name="Possiveis_Duplicidades", index=False)
        df_recebimentos.to_excel(writer, sheet_name="Recebimentos_Fretes", index=False)
        df_despesas_ciclo.to_excel(writer, sheet_name="Despesas_Ciclo", index=False)
        df_despesas_veiculo.to_excel(writer, sheet_name="Despesas_Veiculo", index=False)
        df_atribuicoes.to_excel(writer, sheet_name="Atribuicoes_Despesas", index=False)
        # Exportação da operação física sem rateio de quilômetros por ID Frete.
        dados_saidas = []
        dados_trechos = []
        por_ciclo = {}
        for saida in registros_saida:
            por_ciclo.setdefault(saida.id_ciclo, []).append(saida)
            dados_saidas.append({
                "ID Saída": saida.id_saida, "ID Ciclo": saida.id_ciclo,
                "Fretes Vinculados": ", ".join(
                    v.id_frete_externo or v.codigo_viagem or f"V{v.id_viagem}"
                    for v in saida.fretes_coletados
                ),
                "ID Veículo": saida.id_veiculo, "ID Motorista": saida.id_motorista,
                "Descrição": saida.descricao, "Início": saida.data_inicio,
                "Fim": saida.data_fim, "KM Manual de Referência": saida.km_planejado_manual,
                "Odômetro Inicial": saida.odometro_inicial, "Odômetro Final": saida.odometro_final,
                "Observações": saida.observacoes,
            })
            for trecho in saida.trechos:
                dados_trechos.append({
                    "ID Trecho": trecho.id_trecho, "ID Saída": trecho.id_saida,
                    "Tipo": trecho.tipo_trecho, "Origem": trecho.origem,
                    "Destino": trecho.destino, "KM Planejado": trecho.km_planejado,
                    "Observações": trecho.observacoes,
                })
        dados_resumo = [{"ID Ciclo": cid, **{
            k: v for k, v in resumo_saidas(saidas).items()
            if k in {"qtd_saidas", "qtd_trechos", "km_planejado", "km_real", "completo"}
        }} for cid, saidas in por_ciclo.items()]
        pd.DataFrame(dados_saidas).to_excel(writer, sheet_name="Saidas_Operacionais", index=False)
        pd.DataFrame(dados_trechos).to_excel(writer, sheet_name="Trechos_Operacionais", index=False)
        pd.DataFrame(dados_resumo).to_excel(writer, sheet_name="KM_Operacional_Ciclos", index=False)

    return buf.getvalue()


def obter_caminho_logo():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidatos = [
        os.path.join(base_dir, "assets", "logo_faeg.png"),
        os.path.join(base_dir, "logo_faeg.png"),
        os.path.join(base_dir, "assets", "logo_faeg.jpg"),
        os.path.join(base_dir, "assets", "logo_faeg.svg"),
        "assets/logo_faeg.png",
        "logo_faeg.png",
    ]
    for path in candidatos:
        if os.path.exists(path):
            return path
    return None


def carregar_logo_base64():
    """Carrega o logotipo dinamicamente sempre refletindo o arquivo mais recente."""
    path = obter_caminho_logo()
    if path:
        ext = os.path.splitext(path)[1].lower().replace(".", "")
        mime = "svg+xml" if ext == "svg" else ("jpeg" if ext in ["jpg", "jpeg"] else "png")
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/{mime};base64,{b64}"
    return None


# ==============================================================================
# GERADOR DE PDF NATIVO ZERO-DEPENDÊNCIA (PADRÃO VISUAL FAEG)
# ==============================================================================
def _pdf_esc(txt):
    if txt is None:
        return "-"
    s = str(txt).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return s.encode("latin-1", "replace").decode("latin-1")


def _compilar_pdf_paginas(paginas_cmds):
    """Monta um PDF A4 com todas as páginas, sem descartar linhas de tabelas."""
    if not paginas_cmds:
        raise ValueError("O relatório PDF precisa ter ao menos uma página.")

    total_paginas = len(paginas_cmds)
    ids_paginas = " ".join(f"{5 + 2 * i} 0 R" for i in range(total_paginas))
    objs = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        f"2 0 obj\n<< /Type /Pages /Kids [{ids_paginas}] /Count {total_paginas} >>\nendobj\n".encode("ascii"),
        b"3 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>\nendobj\n",
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>\nendobj\n",
    ]

    for i, cmds in enumerate(paginas_cmds):
        id_pagina = 5 + 2 * i
        id_conteudo = id_pagina + 1
        comandos = list(cmds)
        comandos.append(
            f"BT /F1 8 Tf 0.40 0.46 0.52 rg 480 27 Td (Pagina {i + 1} de {total_paginas}) Tj ET"
        )
        compressed = zlib.compress("\n".join(comandos).encode("latin-1", "replace"))
        objs.append(
            f"{id_pagina} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {id_conteudo} 0 R >>\nendobj\n".encode("ascii")
        )
        objs.append(
            f"{id_conteudo} 0 obj\n<< /Length {len(compressed)} /Filter /FlateDecode >>\nstream\n".encode("ascii")
            + compressed
            + b"\nendstream\nendobj\n"
        )

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objs:
        offsets.append(out.tell())
        out.write(obj)
    xref_pos = out.tell()
    out.write(f"xref\n0 {len(objs) + 1}\n".encode("ascii"))
    out.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.write(f"{off:010d} 00000 n \n".encode("ascii"))
    out.write(
        f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode("ascii")
    )
    return out.getvalue()


def _compilar_pdf_pagina_unica(cmds):
    """Compatibilidade com relatórios que tenham apenas uma página."""
    return _compilar_pdf_paginas([cmds])


def gerar_pdf_relatorio(dados_resumo, despesas_lista):
    cmds = []
    paginas = []

    def rect(x, y_top, w, h, r, g, b):
        y = 842 - y_top - h
        cmds.append(f"{r:.3f} {g:.3f} {b:.3f} rg {x:.1f} {y:.1f} {w:.1f} {h:.1f} re f")

    def text(x, y_top, txt, size=10, bold=False, r=0.051, g=0.149, b=0.235):
        y = 842 - y_top
        font = "/F2" if bold else "/F1"
        cmds.append(
            f"BT {font} {size} Tf {r:.3f} {g:.3f} {b:.3f} rg {x:.1f} {y:.1f} Td ({_pdf_esc(txt)}) Tj ET"
        )

    rect(0, 0, 595, 76, 0.051, 0.149, 0.235)
    rect(0, 76, 595, 5, 0.953, 0.302, 0.145)
    text(40, 34, "FAEG - GESTAO LOGISTICA E OPERACIONAL", size=15, bold=True, r=1, g=1, b=1)
    text(
        40,
        54,
        "Demonstrativo Operacional e Financeiro da Viagem (DRE)",
        size=10,
        bold=False,
        r=0.671,
        g=0.808,
        b=0.882,
    )
    text(440, 54, f"Emissao: {date.today().strftime('%d/%m/%Y')}", size=9, bold=False, r=0.914, g=0.914, b=0.914)

    rect(40, 98, 515, 22, 0.914, 0.914, 0.914)
    text(48, 113, "1. RESUMO DA OPERACAO", size=10, bold=True)

    y = 136
    pares_op = [
        ("Codigo Viagem:", dados_resumo["codigo"], "ID Frete:", dados_resumo["id_frete"]),
        ("Cliente:", dados_resumo["cliente"], "Ciclo:", dados_resumo["ciclo"]),
        ("Motorista:", dados_resumo["motorista"], "Veiculo / Placa:", dados_resumo["veiculo"]),
        ("Origem:", dados_resumo["origem"], "Destino:", dados_resumo["destino"]),
        ("Tipo Viagem:", dados_resumo["tipo_viagem"], "Tipo / Origem Frete:", dados_resumo["frete_info"]),
        ("Situacao:", dados_resumo["status"], "KM Real Rodado:", dados_resumo["km_real_fmt"]),
    ]
    for l1, v1, l2, v2 in pares_op:
        text(42, y, l1, size=9, bold=True, r=0.35, g=0.40, b=0.48)
        text(128, y, str(v1)[:34], size=9, bold=False)
        text(310, y, l2, size=9, bold=True, r=0.35, g=0.40, b=0.48)
        text(412, y, str(v2)[:30], size=9, bold=False)
        y += 18

    y += 10
    rect(40, y, 515, 22, 0.914, 0.914, 0.914)
    text(48, y + 15, "2. FECHAMENTO FINANCEIRO (DRE) E INDICADORES (KPIs)", size=10, bold=True)
    y += 38

    rect(40, y - 14, 515, 92, 0.051, 0.149, 0.235)
    text(55, y + 4, "Receita Total Considerada:", size=10, bold=False, r=0.671, g=0.808, b=0.882)
    text(390, y + 4, dados_resumo["receita_fmt"], size=11, bold=True, r=1, g=1, b=1)
    y += 22
    text(55, y + 4, "Custos Totais de Viagem:", size=10, bold=False, r=0.671, g=0.808, b=0.882)
    text(390, y + 4, f"- {dados_resumo['despesa_fmt']}", size=11, bold=True, r=0.953, g=0.302, b=0.145)
    y += 26
    text(55, y + 4, "RESULTADO OPERACIONAL PARCIAL:", size=10, bold=True, r=1, g=1, b=1)
    text(390, y + 4, dados_resumo["resultado_fmt"], size=13, bold=True, r=1, g=1, b=1)
    y += 46  # Reserva espaço entre o painel escuro e os indicadores complementares.

    text(42, y, f"Custo por KM: {dados_resumo['custo_km_fmt']}", size=10, bold=True)
    text(250, y, f"Margem Operacional: {dados_resumo['margem_fmt']}", size=10, bold=True)
    text(420, y, f"Parcelas previstas: {dados_resumo['parcelas_previstas_fmt']}", size=8, bold=False)
    y += 24
    text(42, y, f"Recebido de fato: {dados_resumo['recebido_real_fmt']}", size=10, bold=True)
    text(310, y, f"Saldo a receber: {dados_resumo['saldo_receber_fmt']}", size=10, bold=True)
    y += 22

    rect(40, y, 515, 22, 0.914, 0.914, 0.914)
    text(48, y + 15, "3. DETALHAMENTO DE DESPESAS DA VIAGEM", size=10, bold=True)
    y += 36

    rect(40, y - 12, 515, 18, 0.051, 0.149, 0.235)
    text(46, y, "Categoria", size=8, bold=True, r=1, g=1, b=1)
    text(175, y, "Descricao / Local", size=8, bold=True, r=1, g=1, b=1)
    text(370, y, "Qtd", size=8, bold=True, r=1, g=1, b=1)
    text(420, y, "Unitario", size=8, bold=True, r=1, g=1, b=1)
    text(488, y, "Total", size=8, bold=True, r=1, g=1, b=1)
    y += 18

    if not despesas_lista:
        text(46, y, "Nenhuma despesa lancada nesta viagem.", size=9, bold=False)
    else:
        for idx_d, d in enumerate(despesas_lista):
            if y > 785:
                paginas.append(cmds)
                cmds = []
                rect(0, 0, 595, 76, 0.051, 0.149, 0.235)
                rect(0, 76, 595, 5, 0.953, 0.302, 0.145)
                text(40, 35, "FAEG - DESPESAS DA VIAGEM (CONTINUACAO)", size=14, bold=True, r=1, g=1, b=1)
                text(40, 55, f"Viagem: {dados_resumo['codigo']}  |  Frete: {dados_resumo['id_frete']}", size=10,
                     r=0.671, g=0.808, b=0.882)
                rect(40, 105, 515, 22, 0.914, 0.914, 0.914)
                text(48, 120, "3. DETALHAMENTO DE DESPESAS DA VIAGEM (CONTINUACAO)", size=10, bold=True)
                y = 152
                rect(40, y - 12, 515, 18, 0.051, 0.149, 0.235)
                text(46, y, "Categoria", size=8, bold=True, r=1, g=1, b=1)
                text(175, y, "Descricao / Local", size=8, bold=True, r=1, g=1, b=1)
                text(370, y, "Qtd", size=8, bold=True, r=1, g=1, b=1)
                text(420, y, "Unitario", size=8, bold=True, r=1, g=1, b=1)
                text(488, y, "Total", size=8, bold=True, r=1, g=1, b=1)
                y += 18
            if idx_d % 2 == 1:
                rect(40, y - 11, 515, 16, 0.965, 0.972, 0.985)
            text(46, y, str(d["tipo"])[:22], size=8)
            text(175, y, str(d["desc"])[:34], size=8)
            text(370, y, f"{d['qtd']:.2f}", size=8)
            text(420, y, d["unit_fmt"], size=8)
            text(488, y, d["total_fmt"], size=8, bold=True)
            y += 16

    paginas.append(cmds)
    return _compilar_pdf_paginas(paginas)


def gerar_pdf_relatorio_consolidado(resumo_geral, ranking_clientes, despesas_categorias):
    """Gera PDF executivo consolidado do Painel Geral / BI Operacional FAEG."""
    cmds = []
    paginas = []

    def rect(x, y_top, w, h, r, g, b):
        y = 842 - y_top - h
        cmds.append(f"{r:.3f} {g:.3f} {b:.3f} rg {x:.1f} {y:.1f} {w:.1f} {h:.1f} re f")

    def text(x, y_top, txt, size=10, bold=False, r=0.051, g=0.149, b=0.235):
        y = 842 - y_top
        font = "/F2" if bold else "/F1"
        cmds.append(
            f"BT {font} {size} Tf {r:.3f} {g:.3f} {b:.3f} rg {x:.1f} {y:.1f} Td ({_pdf_esc(txt)}) Tj ET"
        )

    def pagina_continuacao(titulo):
        nonlocal cmds
        paginas.append(cmds)
        cmds = []
        rect(0, 0, 595, 76, 0.051, 0.149, 0.235)
        rect(0, 76, 595, 5, 0.953, 0.302, 0.145)
        text(40, 34, "FAEG - RELATORIO EXECUTIVO CONSOLIDADO (BI)", size=14, bold=True, r=1, g=1, b=1)
        text(40, 54, f"Filtro aplicado: {resumo_geral['filtro_desc']}", size=9,
             r=0.671, g=0.808, b=0.882)
        rect(40, 103, 515, 22, 0.914, 0.914, 0.914)
        text(48, 118, titulo, size=10, bold=True)
        return 150

    def cabecalho_ranking(y_linha):
        rect(40, y_linha - 12, 515, 18, 0.051, 0.149, 0.235)
        text(46, y_linha, "Cliente", size=8, bold=True, r=1, g=1, b=1)
        text(245, y_linha, "Viagens", size=8, bold=True, r=1, g=1, b=1)
        text(300, y_linha, "Receita", size=8, bold=True, r=1, g=1, b=1)
        text(385, y_linha, "Despesas", size=8, bold=True, r=1, g=1, b=1)
        text(470, y_linha, "Resultado", size=8, bold=True, r=1, g=1, b=1)
        return y_linha + 18

    def cabecalho_categorias(y_linha):
        rect(40, y_linha - 12, 515, 18, 0.051, 0.149, 0.235)
        text(46, y_linha, "Categoria de Despesa", size=8, bold=True, r=1, g=1, b=1)
        text(330, y_linha, "Participacao (%)", size=8, bold=True, r=1, g=1, b=1)
        text(455, y_linha, "Total Acumulado", size=8, bold=True, r=1, g=1, b=1)
        return y_linha + 18

    rect(0, 0, 595, 76, 0.051, 0.149, 0.235)
    rect(0, 76, 595, 5, 0.953, 0.302, 0.145)
    text(40, 34, "FAEG - RELATORIO EXECUTIVO CONSOLIDADO (BI)", size=14, bold=True, r=1, g=1, b=1)
    text(
        40,
        54,
        f"Filtro aplicado: {resumo_geral['filtro_desc']}",
        size=9,
        bold=False,
        r=0.671,
        g=0.808,
        b=0.882,
    )
    text(440, 54, f"Emissao: {date.today().strftime('%d/%m/%Y')}", size=9, bold=False, r=0.914, g=0.914, b=0.914)

    rect(40, 96, 515, 22, 0.914, 0.914, 0.914)
    text(48, 111, "1. INDICADORES GLOBAIS DA OPERACAO", size=10, bold=True)

    y = 136
    rect(40, y - 12, 515, 96, 0.051, 0.149, 0.235)
    text(55, y + 6, f"Total de Viagens: {resumo_geral['qtd_viagens']}", size=10, bold=True, r=0.671, g=0.808, b=0.882)
    text(310, y + 6, f"KM Registrado: {resumo_geral['km_total_fmt']}", size=10, bold=True, r=0.671, g=0.808, b=0.882)
    y += 24
    text(55, y + 6, "Receita Consolidada:", size=10, bold=False, r=1, g=1, b=1)
    text(210, y + 6, resumo_geral["receita_fmt"], size=10, bold=True, r=1, g=1, b=1)
    text(340, y + 6, "Despesas Fretes:", size=10, bold=False, r=1, g=1, b=1)
    text(445, y + 6, resumo_geral["despesa_fmt"], size=10, bold=True, r=0.953, g=0.302, b=0.145)
    y += 26
    text(55, y + 6, "RESULTADO OPERACIONAL PARCIAL:", size=10, bold=True, r=1, g=1, b=1)
    text(275, y + 6, resumo_geral["resultado_fmt"], size=12, bold=True, r=1, g=1, b=1)
    text(430, y + 6, f"Margem: {resumo_geral['margem_fmt']}", size=10, bold=True, r=0.671, g=0.808, b=0.882)
    text(55, y + 27, f"Recebido de fato: {resumo_geral['recebido_fmt']}", size=9, bold=True, r=1, g=1, b=1)
    text(300, y + 27, f"Saldo em aberto: {resumo_geral['saldo_fmt']}", size=9, bold=True, r=1, g=1, b=1)

    y += 42
    rect(40, y, 515, 22, 0.914, 0.914, 0.914)
    text(48, y + 15, "2. DESEMPENHO POR CLIENTE (SEM RATEIO)", size=10, bold=True)
    y += 34

    y = cabecalho_ranking(y)

    if not ranking_clientes:
        text(46, y, "Sem dados para exibir.", size=9)
        y += 18
    else:
        for idx_c, rc in enumerate(ranking_clientes):
            if y > 785:
                y = cabecalho_ranking(pagina_continuacao("2. DESEMPENHO POR CLIENTE (CONTINUACAO)"))
            if idx_c % 2 == 1:
                rect(40, y - 11, 515, 16, 0.965, 0.972, 0.985)
            text(46, y, str(rc["cliente"])[:34], size=8)
            text(255, y, str(rc["viagens"]), size=8)
            text(300, y, rc["receita_fmt"], size=8)
            text(385, y, rc["despesa_fmt"], size=8)
            text(470, y, rc["resultado_fmt"], size=8, bold=True)
            y += 16

    y += 14
    if y + 68 > 785:
        y = pagina_continuacao("3. DESPESAS POR FRETE / CATEGORIA (SEM RATEIO)")
    else:
        rect(40, y, 515, 22, 0.914, 0.914, 0.914)
        text(48, y + 15, "3. DESPESAS POR FRETE / CATEGORIA (SEM RATEIO)", size=10, bold=True)
        y += 34
    y = cabecalho_categorias(y)

    if not despesas_categorias:
        text(46, y, "Nenhuma despesa registrada no filtro atual.", size=9)
    else:
        for idx_cat, dc in enumerate(despesas_categorias):
            if y > 785:
                y = cabecalho_categorias(pagina_continuacao("3. DESPESAS POR CATEGORIA (CONTINUACAO)"))
            if idx_cat % 2 == 1:
                rect(40, y - 11, 515, 16, 0.965, 0.972, 0.985)
            text(46, y, str(dc["categoria"])[:42], size=8)
            text(340, y, dc["pct_fmt"], size=8)
            text(455, y, dc["total_fmt"], size=8, bold=True)
            y += 16

    paginas.append(cmds)
    return _compilar_pdf_paginas(paginas)
