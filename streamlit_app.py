import streamlit as st
import pandas as pd
import numpy as np
from datetime import date
import gspread
from google.oauth2.service_account import Credentials

# =================================================
# CONFIG
# =================================================
st.set_page_config(page_title="Dashboard Financeiro", layout="wide")

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
# GOOGLE SHEETS
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

# =================================================
# LOADERS (ROBUSTOS)
# =================================================
@st.cache_data(ttl=30)
def load_lancamentos():
    records = ws_lanc.get_all_records()
    df = pd.DataFrame(records)

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
    records = ws_meta.get_all_records()
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df.columns = df.columns.str.strip().str.lower()

    df["valor_meta"] = pd.to_numeric(df["valor_meta"], errors="coerce").fillna(0.0)
    df["inicio"] = pd.to_datetime(df["inicio"], dayfirst=True, errors="coerce").dt.date
    df["fim"] = pd.to_datetime(df["fim"], dayfirst=True, errors="coerce").dt.date
    df["tipo"] = df["tipo"].astype(str).str.strip().str.lower()

    return df.copy()

# =================================================
# WRITE
# =================================================
def salvar_lancamento(d):
    ws_lanc.append_row(
        [
            d["data"].strftime("%d/%m/%Y"),  # DATA BR
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

# =================================================
# KPIs
# =================================================
def calcular_kpis(df, inicio, fim):
    base = df[(df["data"] >= inicio) & (df["data"] <= fim)]
    receita = base[base["tipo"] == "receita"]["valor"].sum()
    despesa = base[base["tipo"] == "despesa"]["valor"].sum()
    saldo = receita - despesa
    return receita, despesa, saldo

def calcular_kpis_pagamento(df, inicio, fim):
    base = df[
        (df["data"] >= inicio) &
        (df["data"] <= fim) &
        (df["tipo"] == "despesa")
    ]

    cartao = base[base["pagamento"].str.contains("crédito")]["valor"].sum()
    avista = base[base["pagamento"].isin(["pix", "débito", "debito"])]["valor"].sum()

    total = cartao + avista
    pct_cartao = (cartao / total * 100) if total > 0 else 0.0

    return avista, cartao, pct_cartao

def progresso_meta(meta, df):
    base = df[(df["data"] >= meta["inicio"]) & (df["data"] <= meta["fim"])]

    if meta["tipo"] == "receita":
        return base[base["tipo"] == "receita"]["valor"].sum()

    if meta["tipo"] == "gasto":
        return base[base["tipo"] == "despesa"]["valor"].sum()

    if meta["tipo"] == "economia":
        r = base[base["tipo"] == "receita"]["valor"].sum()
        d = base[base["tipo"] == "despesa"]["valor"].sum()
        return r - d

    return 0.0

# =================================================
# APP
# =================================================
st.title("💸 Dashboard Financeiro Pessoal")

df = load_lancamentos()

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.header("📅 Filtros")

    if df.empty:
        inicio = fim = date.today()
        st.warning("Nenhum lançamento encontrado.")
    else:
        datas = df["data"]
        inicio = st.date_input("Início", datas.min(), min_value=datas.min(), max_value=datas.max(), format="DD/MM/YYYY")
        fim = st.date_input("Fim", datas.max(), min_value=datas.min(), max_value=datas.max(), format="DD/MM/YYYY")

# ---------------- TABS ----------------
tab_dash, tab_add, tab_meta, tab_data = st.tabs(
    ["📊 Dashboard", "➕ Lançamento", "🎯 Metas", "🗂️ Dados"]
)

# ---------------- DASHBOARD ----------------
with tab_dash:
    receita, despesa, saldo = calcular_kpis(df, inicio, fim)

    c1, c2, c3 = st.columns(3)
    c1.metric("📈 Receita", f"R$ {receita:,.2f}")
    c2.metric("📉 Despesa", f"R$ {despesa:,.2f}")
    c3.metric("💰 Resultado", f"R$ {saldo:,.2f}")

    st.divider()

    avista, cartao, pct_cartao = calcular_kpis_pagamento(df, inicio, fim)

    c4, c5, c6 = st.columns(3)
    c4.metric("⚡ À Vista (PIX / Débito)", f"R$ {avista:,.2f}")
    c5.metric("💳 Cartão de Crédito", f"R$ {cartao:,.2f}")
    c6.metric("% no Cartão", f"{pct_cartao:.1f}%")

    if pct_cartao > 40:
        st.warning("⚠️ Mais de 40% dos gastos estão no cartão.")

    st.divider()

    if not df.empty:
        dff = df.sort_values("data")
        dff["mov"] = np.where(dff["tipo"] == "receita", dff["valor"], -dff["valor"])
        dff["saldo"] = dff["mov"].cumsum()
        st.subheader("📈 Saldo acumulado")
        st.line_chart(dff.set_index("data")["saldo"])

# ---------------- LANÇAMENTO ----------------
with tab_add:
    st.subheader("➕ Novo lançamento")

    with st.form("add"):
        data_l = st.date_input("Data", format="DD/MM/YYYY")
        tipo = st.selectbox("Tipo", ["receita", "despesa"])
        categoria = st.text_input("Categoria")
        conta = st.text_input("Conta")
        descricao = st.text_input("Descrição")
        valor = st.number_input("Valor", min_value=0.0, format="%.2f")
        fixo = st.selectbox("Fixo?", ["sim", "não"])
        pagamento = st.selectbox("Pagamento", ["Pix", "Débito", "Crédito"])
        observacao = st.text_input("Observação")

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
                "observacao": observacao
            })
            st.success("Lançamento salvo com sucesso ✅")
            st.rerun()

# ---------------- METAS ----------------
with tab_meta:
    st.subheader("🎯 Metas")

    with st.form("add_meta"):
        desc = st.text_input("Descrição da meta")
        tipo_meta = st.selectbox("Tipo", ["receita", "gasto", "economia"])
        valor_meta = st.number_input("Valor da meta", min_value=0.0, format="%.2f")
        inicio_m = st.date_input("Início", format="DD/MM/YYYY")
        fim_m = st.date_input("Fim", format="DD/MM/YYYY")

        if st.form_submit_button("Salvar meta"):
            ws_meta.append_row(
                [
                    desc,
                    tipo_meta,
                    float(valor_meta),
                    inicio_m.strftime("%d/%m/%Y"),
                    fim_m.strftime("%d/%m/%Y")
                ],
                value_input_option="USER_ENTERED"
            )
            load_metas.clear()
            st.success("Meta salva ✅")
            st.rerun()

    st.divider()

    metas = load_metas()
    if metas.empty:
        st.info("Nenhuma meta cadastrada.")
    else:
        for _, meta in metas.iterrows():
            atual = progresso_meta(meta, df)
            pct = min(atual / meta["valor_meta"], 1)
            st.markdown(f"### {meta['descricao']}")
            st.progress(pct)
            st.caption(f"R$ {atual:,.2f} / R$ {meta['valor_meta']:,.2f}")

# ---------------- DADOS ----------------
with tab_data:
    st.subheader("📋 Lançamentos")
    st.dataframe(df.sort_values("data", ascending=False), use_container_width=True)
