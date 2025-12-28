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
@st.cache_data(ttl=30)
def load_lancamentos():
    df = pd.DataFrame(ws_lanc.get_all_records())

    if df.empty:
        return pd.DataFrame(columns=COLUNAS_LANC)

    df.columns = df.columns.str.strip().str.lower()

    for col in COLUNAS_LANC:
        if col not in df.columns:
            df[col] = None

    df["data"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce").dt.date
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0.0)

    df["tipo"] = df["tipo"].astype(str).str.strip().str.lower()
    df["pagamento"] = df["pagamento"].astype(str).str.strip().str.lower()

    df = df.dropna(subset=["data"])
    df = df[df["tipo"].isin(["receita", "despesa"])]

    return df.copy()

@st.cache_data(ttl=30)
def load_metas():
    df = pd.DataFrame(ws_meta.get_all_records())

    if df.empty:
        return pd.DataFrame(columns=["id", "descricao", "tipo", "valor_meta", "inicio", "fim"])

    df.columns = df.columns.str.strip().str.lower()

    df["id"] = pd.to_numeric(df["id"], errors="coerce").astype(int)
    df["tipo"] = df["tipo"].astype(str).str.strip().str.lower()
    df["valor_meta"] = pd.to_numeric(df["valor_meta"], errors="coerce").fillna(0.0)

    df["inicio"] = pd.to_datetime(df["inicio"], dayfirst=True, errors="coerce").dt.date
    df["fim"] = pd.to_datetime(df["fim"], dayfirst=True, errors="coerce").dt.date

    return df.copy()

# =================================================
# WRITE
# =================================================
def salvar_lancamento(d):
    ws_lanc.append_row(
        [
            d["data"].strftime("%d/%m/%Y"),
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

def proximo_id_meta(df):
    return 1 if df.empty else int(df["id"].max()) + 1

def salvar_meta(meta):
    ws_meta.append_row(
        [
            meta["id"],
            meta["descricao"],
            meta["tipo"],
            meta["valor_meta"],
            meta["inicio"].strftime("%d/%m/%Y"),
            meta["fim"].strftime("%d/%m/%Y")
        ],
        value_input_option="USER_ENTERED"
    )
    load_metas.clear()

# =================================================
# KPIs
# =================================================
def calcular_kpis(df, inicio, fim):
    base = df[(df["data"] >= inicio) & (df["data"] <= fim)]
    receita = base[base["tipo"] == "receita"]["valor"].sum()
    despesa = base[base["tipo"] == "despesa"]["valor"].sum()
    return receita, despesa, receita - despesa

def calcular_kpis_pagamento(df, inicio, fim):
    base = df[
        (df["data"] >= inicio) &
        (df["data"] <= fim) &
        (df["tipo"] == "despesa")
    ]

    cartao = base[base["pagamento"].str.contains("crédito", na=False)]["valor"].sum()
    avista = base[base["pagamento"].isin(["pix", "debito", "débito"])]["valor"].sum()

    total = cartao + avista
    pct = (cartao / total * 100) if total > 0 else 0.0

    return avista, cartao, pct

# =================================================
# METAS PROGRESSO
# =================================================
def calcular_valor_meta(meta, df):
    base = df[(df["data"] >= meta["inicio"]) & (df["data"] <= meta["fim"])]

    if meta["tipo"] == "receita":
        return base[base["tipo"] == "receita"]["valor"].sum()

    if meta["tipo"] == "gasto":
        return base[base["tipo"] == "despesa"]["valor"].sum()

    if meta["tipo"] == "economia":
        return (
            base[base["tipo"] == "receita"]["valor"].sum() -
            base[base["tipo"] == "despesa"]["valor"].sum()
        )

    return 0.0

def atualizar_metas_progresso(df, metas):
    ws_meta_prog.clear()
    ws_meta_prog.append_row(
        ["id", "descricao", "valor_meta", "valor_atual", "percentual", "status", "atualizado_em"]
    )

    for _, meta in metas.iterrows():
        atual = calcular_valor_meta(meta, df)
        pct = min(atual / meta["valor_meta"], 1) if meta["valor_meta"] > 0 else 0
        status = "Concluída" if pct >= 1 else "Em andamento"

        ws_meta_prog.append_row(
            [
                meta["id"],
                meta["descricao"],
                meta["valor_meta"],
                round(atual, 2),
                round(pct * 100, 1),
                status,
                datetime.now().strftime("%d/%m/%Y %H:%M")
            ],
            value_input_option="USER_ENTERED"
        )

# =================================================
# APP
# =================================================
st.title("💸 Dashboard Financeiro Pessoal")

df = load_lancamentos()
metas = load_metas()
atualizar_metas_progresso(df, metas)

# ---------------- SIDEBAR ----------------
with st.sidebar:
    if df.empty:
        inicio = fim = date.today()
        st.warning("Sem lançamentos.")
    else:
        inicio = st.date_input("Início", df["data"].min(), format="DD/MM/YYYY")
        fim = st.date_input("Fim", df["data"].max(), format="DD/MM/YYYY")

# ---------------- TABS ----------------
tab_dash, tab_lanc, tab_meta, tab_data = st.tabs(
    ["📊 Dashboard", "➕ Novo lançamento", "🎯 Metas", "🗂️ Dados"]
)

# ---------------- DASHBOARD ----------------
with tab_dash:
    receita, despesa, saldo = calcular_kpis(df, inicio, fim)
    a, c, p = calcular_kpis_pagamento(df, inicio, fim)

    c1, c2, c3 = st.columns(3)
    c1.metric("Receita", f"R$ {receita:,.2f}")
    c2.metric("Despesa", f"R$ {despesa:,.2f}")
    c3.metric("Resultado", f"R$ {saldo:,.2f}")

    st.divider()

    c4, c5, c6 = st.columns(3)
    c4.metric("À vista (PIX/Débito)", f"R$ {a:,.2f}")
    c5.metric("Cartão", f"R$ {c:,.2f}")
    c6.metric("% Cartão", f"{p:.1f}%")

# ---------------- LANÇAMENTO ----------------
with tab_lanc:
    with st.form("lanc"):
        data_l = st.date_input("Data", format="DD/MM/YYYY")
        tipo = st.selectbox("Tipo", ["receita", "despesa"])
        categoria = st.text_input("Categoria")
        conta = st.text_input("Conta")
        descricao = st.text_input("Descrição")
        valor = st.number_input("Valor", min_value=0.0)
        fixo = st.selectbox("Fixo?", ["sim", "não"])
        pagamento = st.selectbox("Pagamento", ["Pix", "Débito", "Crédito"])
        obs = st.text_input("Observação")

        if st.form_submit_button("Salvar"):
            salvar_lancamento({
                "data": data_l,
                "tipo": tipo,
                "categoria": categoria,
                "conta": conta,
                "descricao": descricao,
                "valor": valor,
                "fixo": fixo,
                "pagamento": pagamento,
                "observacao": obs
            })
            st.success("Lançamento salvo!")
            st.rerun()

# ---------------- METAS ----------------
with tab_meta:
    st.subheader("➕ Criar meta")

    with st.form("meta"):
        novo_id = proximo_id_meta(metas)
        desc = st.text_input("Descrição")
        tipo_m = st.selectbox("Tipo", ["receita", "gasto", "economia"])
        valor_m = st.number_input("Valor da meta", min_value=0.0)
        ini = st.date_input("Início", format="DD/MM/YYYY")
        fim_m = st.date_input("Fim", format="DD/MM/YYYY")

        if st.form_submit_button("Salvar meta"):
            salvar_meta({
                "id": novo_id,
                "descricao": desc,
                "tipo": tipo_m,
                "valor_meta": valor_m,
                "inicio": ini,
                "fim": fim_m
            })
            st.success("Meta criada!")
            st.rerun()

    st.divider()

    st.subheader("📊 Progresso das metas")
    prog = pd.DataFrame(ws_meta_prog.get_all_records())

    if prog.empty:
        st.info("Nenhuma meta.")
    else:
        for _, r in prog.iterrows():
            st.markdown(f"**{r['descricao']}**")
            st.progress(r["percentual"] / 100)
            st.caption(f"R$ {r['valor_atual']} / R$ {r['valor_meta']} — {r['status']}")

# ---------------- DADOS ----------------
with tab_data:
    st.dataframe(df.sort_values("data", ascending=False), use_container_width=True)
