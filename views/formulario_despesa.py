"""Formulário de registro e edição dos lançamentos da Etapa 7."""

from datetime import date
from uuid import uuid4

import streamlit as st

from database.conferencia_duplicidades import COMBUSTIVEIS, procurar_semelhancas_cruzadas
from database.connection import SessionLocal
from database.despesas import (
    atualizar_rascunho, carregar_lancamento, editar_despesa, registrar_despesa, valores_despesa,
)
from database.identificacao_fretes import ciclo_existente_unico
from database.models import Viagem
from faeg_app.core import CATEGORIAS_DESPESA_FORNECEDOR, fmt_brl, get_campo, limpar_caches_atribuicao
from faeg_app.erros import informar_falha


def abrir_edicao(tipo, identificador, viagem_ativa):
    try:
        if tipo == "Rascunho":
            anterior = dict(st.session_state["despesas_temp"][identificador])
            origem = ("Ciclo" if anterior.get("destino_temp") == "ciclo" else "Frete", None)
            financeiro = origem
            fixo = get_campo("vei_id", 0)
            dados = anterior
        else:
            with SessionLocal() as db:
                lancamento = carregar_lancamento(db, tipo, identificador)
                anterior = lancamento.versao()
                origem = lancamento.referencia()
                financeiro = lancamento.destino_financeiro()
                dados = lancamento.dados()
                fixo = None
                if origem[0] == "Veículo":
                    fixo = origem[1]
                elif origem[0] == "Frete":
                    fixo = lancamento.origem.viagem.id_veiculo
        st.session_state["edicao_despesa"] = {
            "tipo": tipo, "id": identificador, "viagem": viagem_ativa, "anterior": anterior,
            "origem": origem, "financeiro": financeiro, "veiculo_fixo": fixo,
            "dados": dados, "chave": uuid4().hex,
        }
    except (ValueError, IndexError):
        st.warning("O lançamento mudou ou está cancelado. Atualize a lista de despesas.")
    except Exception:
        informar_falha("abrir a despesa")


def _novo_destino(ctx, ciclos, veiculos):
    viagem = ctx.viagem_sel_id
    operacao_ciclo = get_campo("tipo_viagem") == "Ciclo"
    opcoes = {"Frete": "Frete atual (ID Frete)"}
    if operacao_ciclo or (viagem and ciclos):
        opcoes["Ciclo"] = "Ciclo inteiro (ID Ciclo)"
    if veiculos:
        opcoes["Veículo"] = "Veículo (sem frete/ciclo definido)"
    contexto = (viagem, operacao_ciclo)
    chave = "desp_destino_lancamento"
    if st.session_state.get("desp_contexto_destino") != contexto:
        st.session_state[chave] = "Ciclo" if operacao_ciclo else "Frete"
        st.session_state["desp_contexto_destino"] = contexto
    tipo = st.selectbox("Destino do custo", list(opcoes), format_func=opcoes.get, key=chave)
    id_ciclo = None
    if viagem:
        with SessionLocal() as db:
            frete = db.get(Viagem, viagem)
            if frete is None:
                raise ValueError("O frete deixou de existir. Abra outra viagem.")
            id_ciclo = frete.id_ciclo
            placa = frete.id_veiculo
            ciclo_salvo = frete.ciclo.nome_operacao if frete.ciclo else ""
            if tipo == "Ciclo" and operacao_ciclo and ciclo_salvo.strip().casefold() != (get_campo("ciclo_nome") or "").strip().casefold():
                raise ValueError("Salve a mudança de ciclo na Etapa 1 antes de lançar a despesa.")
    else:
        placa = get_campo("vei_id", 0)
        if operacao_ciclo and tipo != "Veículo":
            with SessionLocal() as db:
                ciclo = ciclo_existente_unico(db, get_campo("ciclo_nome"))
                id_ciclo = ciclo.id_ciclo if ciclo else None
    if tipo == "Ciclo":
        if operacao_ciclo:
            nome = (get_campo("ciclo_nome") or "").strip()
            if not nome:
                raise ValueError("Informe o nome do ciclo na Etapa 1.")
            st.caption(f"Ciclo da operação · {nome}")
        else:
            id_ciclo = st.selectbox("Ciclo que receberá o custo", list(ciclos),
                                    format_func=ciclos.get, key="desp_ciclo_destino_unico")
        return tipo, id_ciclo, placa if not viagem else None, id_ciclo
    if tipo == "Veículo":
        placa = st.selectbox("Veículo da despesa", list(veiculos),
                             format_func=veiculos.get, key="desp_veiculo_destino_unico")
        return tipo, placa, placa, None
    return tipo, viagem, placa, id_ciclo


def _campos(padrao, prefixo, versao, fornecedores, veiculos, veiculo_fixo):
    categorias = list(CATEGORIAS_DESPESA_FORNECEDOR)
    categoria_inicial = padrao.get("tipo_despesa") or categorias[0]
    if categoria_inicial not in categorias:
        categorias.append(categoria_inicial)
    c1, c2, c3 = st.columns([2, 2.5, 2])
    tipo = c1.selectbox("Tipo de despesa", categorias, index=categorias.index(categoria_inicial),
                        key=f"{prefixo}_tipo")
    descricao = c2.text_input("Descrição / local", value=padrao.get("descricao_detalhe") or "",
                              max_chars=200, key=f"{prefixo}_desc_{versao}")
    opcoes = {0: "Não informado", **{f["id_fornecedor"]: f["nome_fantasia"] for f in fornecedores}}
    if padrao.get("id_fornecedor"):
        opcoes.setdefault(padrao["id_fornecedor"], f"Fornecedor #{padrao['id_fornecedor']}")
    fornecedor = c3.selectbox("Fornecedor / posto", list(opcoes), format_func=opcoes.get,
                              index=list(opcoes).index(padrao.get("id_fornecedor") or 0), key=f"{prefixo}_forn")
    combustivel = tipo in COMBUSTIVEIS
    colunas = st.columns(3 if combustivel else 2)
    qtd = colunas[0].number_input("Litros" if combustivel else "Quantidade", min_value=0.01, max_value=9999999999.99,
                                  value=max(0.01, float(padrao.get("quantidade") or 1)), format="%.2f",
                                  step=1.0, key=f"{prefixo}_qtd_{versao}")
    preco = colunas[1].number_input("Preço por litro (R$)" if combustivel else "Valor unitário (R$)",
                                    min_value=0.0, max_value=99999999.9999, value=max(0.0, float(padrao.get("valor_unitario") or 0)),
                                    format="%.4f" if combustivel else "%.2f", step=0.01,
                                    key=f"{prefixo}_unit_{versao}")
    odometro = placa = None
    if combustivel:
        odometro = colunas[2].number_input("Odômetro no posto (km)", min_value=0, max_value=2147483647,
                                          value=int(padrao.get("odometro_abastecimento") or 0),
                                          help="Use zero quando a leitura estiver indisponível.",
                                          key=f"{prefixo}_odometro_abastecimento_{versao}") or None
        if veiculo_fixo is not None:
            placa = veiculo_fixo
            st.caption("Veículo do abastecimento · " + veiculos.get(placa, "selecione a placa na Etapa 1"))
        elif veiculos:
            preferido = padrao.get("id_veiculo_abast") or get_campo("vei_id")
            ids = list(veiculos)
            placa = st.selectbox("Veículo abastecido", ids, index=ids.index(preferido) if preferido in ids else 0,
                                 format_func=veiculos.get, key=f"{prefixo}_veiculo_abast_ciclo")
    data = st.date_input("Data do abastecimento" if combustivel else "Data da despesa",
                         value=padrao.get("data_despesa") if padrao else date.today(), format="DD/MM/YYYY",
                         key=f"{prefixo}_data_unica")
    qtd, preco, total = valores_despesa(qtd, preco, combustivel, padrao)
    st.markdown(f"**Total do lançamento · {fmt_brl(total)}**")
    return {"tipo_despesa": tipo, "descricao_detalhe": descricao.strip() or (None if padrao and not padrao.get("descricao_detalhe") else tipo),
            "data_despesa": data, "id_fornecedor": fornecedor or None,
            "quantidade": qtd, "valor_unitario": preco, "valor_total": total,
            "id_veiculo_abast": placa, "odometro_abastecimento": odometro}


def render_formulario_despesa(ctx, ciclos, veiculos):
    edicao = st.session_state.get("edicao_despesa")
    if edicao and edicao["viagem"] != ctx.viagem_sel_id:
        st.session_state.pop("edicao_despesa")
        edicao = None
    if edicao:
        tipo, titular = edicao["origem"]
        financeiro, destino = edicao["financeiro"]
        temporario = edicao["tipo"] == "Rascunho"
        id_ciclo = destino if financeiro == "Ciclo" else None
        if temporario:
            with SessionLocal() as db:
                ciclo = ciclo_existente_unico(db, get_campo("ciclo_nome"))
                id_ciclo = ciclo.id_ciclo if ciclo else None
        elif financeiro == "Frete":
            with SessionLocal() as db:
                id_ciclo = db.query(Viagem.id_ciclo).filter_by(id_viagem=destino).scalar()
        veiculo_fixo = get_campo("vei_id", 0) if temporario else edicao["veiculo_fixo"]
        padrao = edicao["dados"]
        prefixo = f"edicao_{edicao['chave']}"
        titulo = "Editar despesa do rascunho" if temporario else f"Editar despesa · {edicao['tipo']} #{edicao['id']}"
        st.subheader(titulo)
        if edicao["financeiro"] != edicao["origem"]:
            st.caption(f"Despesa do veículo {veiculos.get(titular, titular)} atribuída a {financeiro.lower()} #{destino}.")
    else:
        st.subheader("Registrar despesa")
        tipo, titular, veiculo_fixo, id_ciclo = _novo_destino(ctx, ciclos, veiculos)
        temporario = not ctx.viagem_sel_id and tipo != "Veículo"
        financeiro, padrao, prefixo = tipo, {}, "desp"
        if tipo == "Veículo":
            st.caption("O custo permanece pendente até a atribuição a um frete ou ciclo.")
        elif tipo == "Ciclo":
            st.caption("O custo entra uma vez no resultado do ciclo.")
    versao = st.session_state.get("versao_campos_despesa", 0)
    dados = _campos(padrao, prefixo, versao, ctx.fornecedores_db, veiculos, veiculo_fixo)
    coincidencias = []
    confirmados = []
    if id_ciclo and financeiro != "Veículo" and dados["valor_total"] > 0:
        with SessionLocal() as db:
            coincidencias = procurar_semelhancas_cruzadas(db, financeiro, id_ciclo, dados)
        if coincidencias:
            ids = [d["id_lancamento"] for d in coincidencias]
            referencias = ", ".join(f"{d['origem']} #{d['id_lancamento']}" for d in coincidencias)
            st.warning(f"Lançamento semelhante em {referencias}. Confira os comprovantes.")
            chave = (prefixo, versao, financeiro, id_ciclo, tuple(dados.values()), tuple(ids))
            if st.checkbox("Conferi os comprovantes e os gastos são distintos.", key=f"comprovante_{chave}"):
                confirmados = ids
    salvar = st.button("Salvar alterações" if edicao else "Registrar despesa",
                       key="salvar_edicao_despesa" if edicao else "btn_add_despesa", type="primary")
    if edicao and st.button("Voltar sem salvar", key="fechar_edicao_despesa"):
        st.session_state.pop("edicao_despesa")
        st.rerun()
    if not salvar:
        return
    try:
        if temporario:
            if coincidencias and not confirmados:
                raise ValueError("Confirme a conferência dos comprovantes antes de salvar.")
            dados.update(destino_temp=tipo.lower(), coincidencias_confirmadas=confirmados)
            atualizar_rascunho(st.session_state.setdefault("despesas_temp", []), dados,
                               indice=edicao["id"] if edicao else None,
                               anterior=edicao["anterior"] if edicao else None)
        else:
            with SessionLocal.begin() as db:
                if edicao:
                    editar_despesa(db, edicao["tipo"], edicao["id"], edicao["anterior"], dados, confirmados)
                else:
                    registrar_despesa(db, tipo, titular, dados, confirmados)
            limpar_caches_atribuicao()
    except ValueError as exc:
        st.warning(str(exc))
        return
    except Exception:
        informar_falha("salvar a despesa")
        return
    st.session_state.pop("edicao_despesa", None)
    st.session_state["versao_campos_despesa"] = versao + 1
    mensagem = "Despesa atualizada." if edicao else "Despesa registrada."
    if temporario:
        mensagem += " Salve o rascunho ou o frete para guardar o preenchimento."
    st.toast(mensagem, icon="✅")
    st.rerun()
