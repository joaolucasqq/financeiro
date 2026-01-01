import streamlit as st
import pandas as pd
from datetime import date, datetime
import gspread
from google.oauth2.service_account import Credentials

# ================= CONFIG =================
st.set_page_config(page_title="Dashboard Financeiro", layout="wide")

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

SHEET_ID = "1sFMHJSj7zbpLn73n7QILqmGG3CLL98rXTm9Et9QKFMA"

COL_LANC = [
    "data", "tipo", "categoria", "conta",
    "descricao", "valor", "fixo", "pagamento", "observacao"
]

# ================= GOOGLE =================
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
ws_metas = sheet.worksheet("metas")
ws_prog = sheet.worksheet("metas_progresso")

# ================= LOADERS =================
@st.cache_data(ttl=30)
def load_lancamentos():
    df = pd.DataFrame(ws_lanc.get_all_records())
    if df.empty:
        return pd.DataFrame(columns=COL_LANC)

    df.columns = df.columns.str.lower().str.strip()
    df["data"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce").dt.date
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0.0)
    df["tipo"] = df["tipo"].str.lower().str.strip()
    df["pagamento"] = df["pagamento"].str.lower().str.strip()

    df = df.dropna(subset=["data"])
    df = df[df["tipo"].isin(["receita", "despesa"])]

    return df.copy()

@st.cache_data(ttl=30)
def load_metas():
    df = pd.DataFrame(ws_metas.get_all_records())
    if df.empty:
        return pd.DataFrame(columns=["id","descricao","tipo","valor_meta","inicio","fim"])

    df.columns = df.columns.str.lower().str.strip()
    df["id"] = df["id"].astype(int)
    df["tipo"] = df["tipo"].str.lower().str.strip()
    df["valor_meta"] = pd.to_numeric(df["valor_meta"], errors="coerce").fillna(0.0)
    df["inicio"] = pd.to_datetime(df["inicio"], dayfirst=True).dt.date
    df["fim"] = pd.to_datetime(df["fim"], dayfirst=True).dt.date

    return df.copy()

# ================= WRITE =================
def salvar_lancamento(d):
    ws_lanc.append_rows([[
        d["data"].strftime("%d/%m/%Y"),
        d["tipo"], d["categoria"], d["conta"],
        d["descricao"], float(d["valor"]),
        d["fixo"], d["pagamento"], d["observacao"]
    ]], value_input_option="USER_ENTERED")
    load_lancamentos.clear()

def salvar_meta(m):
    ws_metas.append_rows([[
        str(m["id"]),
        m["descricao"],
        m["tipo"],
        str(m["valor_meta"]),
        m["inicio"].strftime("%d/%m/%Y"),
        m["fim"].strftime("%d/%m/%Y")
    ]], value_input_option="USER_ENTERED")
    load_metas.clear()

# ================= KPIs =================
def calcular_meta(meta, df):
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

def atualizar_metas_progresso(df, metas):
    ws_prog.clear()
    ws_prog.append_rows([[
        "id","descricao","valor_meta",
        "valor_atual","percentual",
        "status","atualizado_em"
    ]], value_input_option="RAW")

    linhas = []
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")

    for _, m in metas.iterrows():
        atual = float(calcular_meta(m, df))
        alvo = float(m["valor_meta"]) if m["valor_meta"] > 0 else 0.0
        pct = min(atual / alvo, 1) if alvo > 0 else 0

        linhas.append([
            str(m["id"]),
            m["descricao"],
            f"{alvo:.2f}",
            f"{atual:.2f}",
            f"{pct*100:.1f}",
            "Concluída" if pct >= 1 else "Em andamento",
            agora
        ])

    if linhas:
        ws_prog.append_rows(linhas, value_input_option="RAW")

# ================= APP =================
st.title("💸 Dashboard Financeiro")

df = load_lancamentos()
metas = load_metas()

if not metas.empty:
    atualizar_metas_progresso(df, metas)

tab_dash, tab_lanc, tab_meta = st.tabs(
    ["📊 Dashboard", "➕ Lançamento", "🎯 Metas"]
)

# -------- DASH --------
with tab_dash:
    st.dataframe(df)

# -------- LANÇAMENTO --------
with tab_lanc:
    with st.form("lanc"):
        d = st.date_input("Data", format="DD/MM/YYYY")
        t = st.selectbox("Tipo", ["receita","despesa"])
        desc = st.text_input("Descrição")
        val = st.number_input("Valor", min_value=0.0)
        if st.form_submit_button("Salvar"):
            salvar_lancamento({
                "data": d, "tipo": t,
                "categoria": "", "conta": "",
                "descricao": desc, "valor": val,
                "fixo": "", "pagamento": "pix",
                "observacao": ""
            })
            st.rerun()

# -------- METAS --------
with tab_meta:
    with st.form("meta"):
        desc = st.text_input("Descrição")
        tipo = st.selectbox("Tipo", ["receita","gasto","economia"])
        valor = st.number_input("Valor da meta", min_value=1.0)
        ini = st.date_input("Início", format="DD/MM/YYYY")
        fim = st.date_input("Fim", format="DD/MM/YYYY")

        if st.form_submit_button("Salvar meta"):
            salvar_meta({
                "id": 1 if metas.empty else metas["id"].max()+1,
                "descricao": desc,
                "tipo": tipo,
                "valor_meta": valor,
                "inicio": ini,
                "fim": fim
            })
            st.rerun()
