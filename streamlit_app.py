import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta
import gspread
from google.oauth2.service_account import Credentials

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
st.set_page_config(page_title="Dashboard Financeiro Pessoal", layout="wide")

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

SHEET_ID = "1sFMHJSj7zbpLn73n7QILqmGG3CLL98rXTm9Et9QKFMA"

# --------------------------------------------------
# GOOGLE SHEETS
# --------------------------------------------------
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
ws_cart = sheet.worksheet("cartoes")
ws_orc = sheet.worksheet("orcamentos")
ws_metas = sheet.worksheet("metas")

# --------------------------------------------------
# LOADERS
# --------------------------------------------------
@st.cache_data(ttl=30)
def load_lancamentos():
    df = pd.DataFrame(ws_lanc.get_all_records())
    if df.empty:
        return df

    df["data"] = pd.to_datetime(df["data"], errors="coerce").dt.date
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0.0)
    df["tipo"] = df["tipo"].astype(str).str.lower()
    df = df[df["tipo"].isin(["receita", "despesa"])]

    for col in ["fixo", "pagamento", "observacao"]:
        if col not in df.columns:
            df[col] = ""

    return df


@st.cache_data(ttl=30)
def load_orcamentos():
    df = pd.DataFrame(ws_orc.get_all_records())
    if df.empty:
        return df
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0.0)
    return df


@st.cache_data(ttl=30)
def load_cartoes():
    df = pd.DataFrame(ws_cart.get_all_records())
    if df.empty:
        return df
    df["limite"] = pd.to_numeric(df["limite"], errors="coerce").fillna(0.0)
    return df


@st.cache_data(ttl=30)
def load_metas():
    df = pd.DataFrame(ws_metas.get_all_records())
    if df.empty:
        return df

    df["valor_meta"] = pd.to_numeric(df["valor_meta"], errors="coerce").fillna(0.0)
    df["inicio"] = pd.to_datetime(df["inicio"], errors="coerce").dt.date
    df["fim"] = pd.to_datetime(df["fim"], errors="coerce").dt.date
    return df

# --------------------------------------------------
# WRITERS
# --------------------------------------------------
def salvar_lancamento(d):
    ws_lanc.append_row([
        str(d["data"]),
        d["tipo"],
        d["categoria"],
        d["conta"],
        d["descricao"],
        float(d["valor"]),
        d["fixo"],
        d["pagamento"],
        d["observacao"]
    ])
    load_lancamentos.clear()

# --------------------------------------------------
# CALCULOS
# --------------------------------------------------
def calcular_kpis(df, inicio, fim):
    f = df[(df["data"] >= inicio) & (df["data"] <= fim)]
    receita = f[f["tipo"] == "receita"]["valor"].sum()
    despesa = f[f["tipo"] == "despesa"]["valor"].sum()
    saldo = receita - despesa
    return receita, despesa, saldo


def calcular_progresso_meta(meta, df):
    periodo = (df["data"] >= meta["inicio"]) & (df["data"] <= meta["fim"])
    base = df[periodo]

    if meta["tipo"] == "receita":
        atual = base[base["tipo"] == "receita"]["valor"].sum()

    elif meta["tipo"] == "gasto":
        base = base[base["tipo"] == "despesa"]
        if meta.get("categoria"):
            base = base[base["categoria"] == meta["categoria"]]
        atual = base["valor"].sum()

    elif meta["tipo"] == "economia":
        r = base[base["tipo"] == "receita"]["valor"].sum()
        d = base[base["tipo"] == "despesa"]["valor"].sum()
        atual = r - d

    else:
        atual = 0

    return max(atual, 0)

# --------------------------------------------------
# APP
# --------------------------------------------------
st.title("💸 Dashboard Financeiro Pessoal")

df = load_lancamentos()

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.header("📅 Filtros")

    if df.empty:
        st.warning("Nenhum lançamento ainda.")
        inicio = fim = date.today()
    else:
        inicio = st.date_input("Início", min(df["data"]))
        fim = st.date_input("Fim", max(df["data"]))

# ---------------- DASHBOARD ----------------
tab_dash, tab_add, tab_metas, tab_data = st.tabs(
    ["📊 Dashboard", "➕ Novo lançamento", "🎯 Metas", "🗂️ Dados"]
)

with tab_dash:
    receita, despesa, saldo = calcular_kpis(df, inicio, fim)

    c1, c2, c3 = st.columns(3)
    c1.metric("📈 Receita", f"R$ {receita:,.2f}")
    c2.metric("📉 Despesa", f"R$ {despesa:,.2f}")
    c3.metric("💰 Resultado", f"R$ {saldo:,.2f}")

    st.divider()

    st.subheader("📈 Saldo acumulado")
    dff = df.sort_values("data")
    dff["mov"] = np.where(dff["tipo"] == "receita", dff["valor"], -dff["valor"])
    dff["saldo"] = dff["mov"].cumsum()
    st.line_chart(dff.set_index("data")["saldo"])

    st.subheader("📊 Gastos por categoria")
    gastos = (
        df[df["tipo"] == "despesa"]
        .groupby("categoria")["valor"]
        .sum()
    )
    st.bar_chart(gastos)

with tab_add:
    st.subheader("➕ Novo lançamento (salva na planilha)")
    with st.form("add"):
        data_l = st.date_input("Data", value=date.today())
        tipo = st.selectbox("Tipo", ["receita", "despesa"])
        categoria = st.text_input("Categoria")
        conta = st.text_input("Conta")
        descricao = st.text_input("Descrição")
        valor = st.number_input("Valor", min_value=0.0, format="%.2f")
        fixo = st.selectbox("Fixo?", ["sim", "não"])
        pagamento = st.text_input("Pagamento")
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
            st.success("Lançamento salvo ✅")
            st.rerun()

with tab_metas:
    st.subheader("🎯 Progresso das metas")
    df_metas = load_metas()

    if df_metas.empty:
        st.info("Nenhuma meta cadastrada.")
    else:
        for _, meta in df_metas.iterrows():
            atual = calcular_progresso_meta(meta, df)
            progresso = min(atual / meta["valor_meta"], 1)

            st.markdown(f"### {meta['descricao']}")
            st.progress(progresso)
            st.caption(f"R$ {atual:,.2f} / R$ {meta['valor_meta']:,.2f}")

with tab_data:
    st.subheader("📋 Lançamentos (base completa)")
    st.dataframe(df.sort_values("data", ascending=False), use_container_width=True)
