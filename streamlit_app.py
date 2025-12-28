import streamlit as st
import pandas as pd
import numpy as np
from datetime import date
import gspread
from google.oauth2.service_account import Credentials

# =================================================
# CONFIG
# =================================================
st.set_page_config(page_title="Financeiro Pessoal", layout="wide")

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
# LOADERS (100% SEGUROS)
# =================================================
@st.cache_data(ttl=30)
def load_lancamentos():
    records = ws_lanc.get_all_records()

    # SEMPRE cria DataFrame com colunas
    df = pd.DataFrame(records)
    df.columns = df.columns.str.strip().str.lower()

    for col in COLUNAS_LANC:
        if col not in df.columns:
            df[col] = None

    if df.empty:
        return df

    # conversões seguras
    df["data"] = pd.to_datetime(df["data"], errors="coerce").dt.date
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0.0)
    df["tipo"] = df["tipo"].astype(str).str.lower()

    # remove linhas inválidas
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
    df["inicio"] = pd.to_datetime(df["inicio"], errors="coerce").dt.date
    df["fim"] = pd.to_datetime(df["fim"], errors="coerce").dt.date
    df["tipo"] = df["tipo"].astype(str).str.lower()

    return df.copy()

# =================================================
# WRITER
# =================================================
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
    ], value_input_option="USER_ENTERED")

    load_lancamentos.clear()

# =================================================
# CÁLCULOS
# =================================================
def calcular_kpis(df, inicio, fim):
    if df.empty:
        return 0.0, 0.0, 0.0

    base = df[(df["data"] >= inicio) & (df["data"] <= fim)]
    receita = base.loc[base["tipo"] == "receita", "valor"].sum()
    despesa = base.loc[base["tipo"] == "despesa", "valor"].sum()
    saldo = receita - despesa
    return receita, despesa, saldo

def progresso_meta(meta, df):
    if df.empty:
        return 0.0

    periodo = (df["data"] >= meta["inicio"]) & (df["data"] <= meta["fim"])
    base = df[periodo]

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
        st.info("Nenhum lançamento válido ainda.")
    else:
        datas = df["data"].dropna()
        inicio = st.date_input("Início", datas.min())
        fim = st.date_input("Fim", datas.max())

# ---------------- TABS ----------------
tab_dash, tab_add, tab_meta, tab_data = st.tabs(
    ["📊 Dashboard", "➕ Novo lançamento", "🎯 Metas", "🗂️ Dados"]
)

# ---------------- DASHBOARD ----------------
with tab_dash:
    receita, despesa, saldo = calcular_kpis(df, inicio, fim)

    c1, c2, c3 = st.columns(3)
    c1.metric("📈 Receita", f"R$ {receita:,.2f}")
    c2.metric("📉 Despesa", f"R$ {despesa:,.2f}")
    c3.metric("💰 Resultado", f"R$ {saldo:,.2f}")

    st.divider()

    if not df.empty:
        dff = df.sort_values("data")
        dff["mov"] = np.where(dff["tipo"] == "receita", dff["valor"], -dff["valor"])
        dff["saldo"] = dff["mov"].cumsum()
        st.line_chart(dff.set_index("data")["saldo"])

# ---------------- NOVO LANÇAMENTO ----------------
with tab_add:
    st.subheader("➕ Novo lançamento")

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
            st.success("Lançamento salvo na planilha ✅")
            st.rerun()

# ---------------- METAS ----------------
with tab_meta:
    st.subheader("🎯 Metas")

    df_metas = load_metas()
    if df_metas.empty:
        st.info("Nenhuma meta cadastrada.")
    else:
        for _, meta in df_metas.iterrows():
            atual = progresso_meta(meta, df)
            pct = min(atual / meta["valor_meta"], 1)
            st.markdown(f"### {meta['descricao']}")
            st.progress(pct)
            st.caption(f"R$ {atual:,.2f} / R$ {meta['valor_meta']:,.2f}")

# ---------------- DADOS ----------------
with tab_data:
    st.subheader("📋 Lançamentos")
    st.dataframe(df.sort_values("data", ascending=False), use_container_width=True)
