import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, datetime
import gspread
from google.oauth2.service_account import Credentials

# =================================================
# CONFIG
# =================================================
st.set_page_config(page_title="Dashboard Financeiro Pessoal", layout="wide")

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

SHEET_ID = "1sFMHJSj7zbpLn73n7QILqmGG3CLL98rXTm9Et9QKFMA"

COLUNAS_LANC = [
    "data", "tipo", "categoria", "conta",
    "descricao", "valor", "fixo", "pagamento", "observacao"
]

# =================================================
# GOOGLE
# =================================================
@st.cache_resource
def conectar_google():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPE
    )
    return gspread.authorize(creds)

client = conectar_google()
sheet = client.open_by_key(SHEET_ID)

ws_lanc = sheet.worksheet("lancamentos")
ws_meta = sheet.worksheet("metas")
ws_meta_prog = sheet.worksheet("metas_progresso")

# =================================================
# LOADERS
# =================================================
@st.cache_data(ttl=20)
def load_lancamentos():
    records = ws_lanc.get_all_records()
    df = pd.DataFrame(records)

    if df.empty:
        return pd.DataFrame(columns=COLUNAS_LANC)

    df.columns = df.columns.str.strip().str.lower()

    for col in COLUNAS_LANC:
        if col not in df.columns:
            df[col] = None

    # aceita DD/MM/YYYY e YYYY-MM-DD
    df["data"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce").dt.date
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0.0)

    df["tipo"] = df["tipo"].astype(str).str.strip().str.lower()
    df["pagamento"] = df["pagamento"].astype(str).str.strip().str.lower()

    df = df.dropna(subset=["data"])
    df = df[df["tipo"].isin(["receita", "despesa"])]

    return df.copy()

@st.cache_data(ttl=20)
def load_metas():
    records = ws_meta.get_all_records()
    df = pd.DataFrame(records)

    if df.empty:
        return pd.DataFrame(columns=["id", "descricao", "tipo", "valor_meta", "inicio", "fim"])

    df.columns = df.columns.str.strip().str.lower()

    # garante colunas
    for col in ["id", "descricao", "tipo", "valor_meta", "inicio", "fim"]:
        if col not in df.columns:
            df[col] = None

    df["id"] = pd.to_numeric(df["id"], errors="coerce")
    df["descricao"] = df["descricao"].astype(str).fillna("")
    df["tipo"] = df["tipo"].astype(str).str.strip().str.lower()

    df["valor_meta"] = pd.to_numeric(df["valor_meta"], errors="coerce").fillna(0.0)
    df["inicio"] = pd.to_datetime(df["inicio"], dayfirst=True, errors="coerce").dt.date
    df["fim"] = pd.to_datetime(df["fim"], dayfirst=True, errors="coerce").dt.date

    df = df.dropna(subset=["id", "inicio", "fim"])
    df["id"] = df["id"].astype(int)

    return df.copy()

# =================================================
# WRITE
# =================================================
def salvar_lancamento(d):
    ws_lanc.append_row(
        [
            d["data"].strftime("%d/%m/%Y"),  # BR
            d["tipo"],
            d["categoria"],
            d["conta"],
            d["descricao"],
            float(d["valor"]),
            d["fixo"],
            d["pagamento"],
            d["observacao"]
        ],
        value_input_option="USER_ENTERED"
    )
    load_lancamentos.clear()

def proximo_id_meta(df_metas: pd.DataFrame) -> int:
    if df_metas.empty:
        return 1
    return int(df_metas["id"].max()) + 1

def salvar_meta(meta):
    ws_meta.append_row(
        [
            int(meta["id"]),
            meta["descricao"],
            meta["tipo"],
            float(meta["valor_meta"]),
            meta["inicio"].strftime("%d/%m/%Y"),
            meta["fim"].strftime("%d/%m/%Y"),
        ],
        value_input_option="USER_ENTERED"
    )
    load_metas.clear()

# =================================================
# KPIs
# =================================================
def calcular_kpis(df, inicio, fim):
    if df.empty:
        return 0.0, 0.0, 0.0

    base = df[(df["data"] >= inicio) & (df["data"] <= fim)]
    receita = base[base["tipo"] == "receita"]["valor"].sum()
    despesa = base[base["tipo"] == "despesa"]["valor"].sum()
    saldo = receita - despesa
    return receita, despesa, saldo

def calcular_kpis_pagamento(df, inicio, fim):
    if df.empty:
        return 0.0, 0.0, 0.0

    base = df[
        (df["data"] >= inicio) &
        (df["data"] <= fim) &
        (df["tipo"] == "despesa")
    ].copy()

    # cartao: qualquer coisa contendo "crédito"
    cartao = base[base["pagamento"].str.contains("crédito", na=False)]["valor"].sum()
    # à vista: pix e débito
    avista = base[base["pagamento"].isin(["pix", "débito", "debito"])]["valor"].sum()

    total = cartao + avista
    pct_cartao = (cartao / total * 100) if total > 0 else 0.0
    return avista, cartao, pct_cartao

# =================================================
# METAS: PROGRESSO AUTOMÁTICO (ESCREVE NA PLANILHA)
# =================================================
def calcular_valor_atual(meta, df_lanc):
    periodo = (df_lanc["data"] >= meta["inicio"]) & (df_lanc["data"] <= meta["fim"])
    base = df_lanc[periodo]

    if meta["tipo"] == "receita":
        return float(base[base["tipo"] == "receita"]["valor"].sum())

    if meta["tipo"] == "gasto":
        return float(base[base["tipo"] == "despesa"]["valor"].sum())

    if meta["tipo"] == "economia":
        r = float(base[base["tipo"] == "receita"]["valor"].sum())
        d = float(base[base["tipo"] == "despesa"]["valor"].sum())
        return float(r - d)

    return 0.0

def atualizar_metas_progresso(df_lanc, df_metas):
    # sempre mantém cabeçalho
    header = ["id", "descricao", "valor_meta", "valor_atual", "percentual", "status", "atualizado_em"]

    if df_metas.empty:
        ws_meta_prog.clear()
        ws_meta_prog.append_row(header)
        return

    registros = []
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    for _, meta in df_metas.iterrows():
        atual = calcular_valor_atual(meta, df_lanc)
        alvo = float(meta["valor_meta"]) if float(meta["valor_meta"]) > 0 else 0.0

        pct = (atual / alvo) if alvo > 0 else 0.0
        pct = max(0.0, min(pct, 1.0))  # limita 0..100%

        status = "Concluída" if pct >= 1.0 else "Em andamento"

        registros.append([
            int(meta["id"]),
            str(meta["descricao"]),
            float(alvo),
            float(round(atual, 2)),
            float(round(pct * 100, 1)),
            status,
            now_str
        ])

    ws_meta_prog.clear()
    ws_meta_prog.append_row(header)
    if registros:
        ws_meta_prog.append_rows(registros, value_input_option="USER_ENTERED")

# =================================================
# APP
# =================================================
st.title("💸 Dashboard Financeiro Pessoal")

df = load_lancamentos()
df_metas = load_metas()

# Atualiza a aba metas_progresso automaticamente
# (roda sempre que abrir/atualizar o app)
atualizar_metas_progresso(df, df_metas)

# ---------------- SIDEBAR ----------------
with st.sidebar:
   
