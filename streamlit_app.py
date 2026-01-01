import streamlit as st
import pandas as pd
import numpy as np
from datetime import date
import gspread
from google.oauth2.service_account import Credentials

# ================= CONFIG =================
st.set_page_config(
    page_title="Dashboard Financeiro & Metas",
    layout="wide"
)

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

SHEET_ID = "1sFMHJSj7zbpLn73n7QILqmGG3CLL98rXTm9Et9QKFMA"

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
ws_reg = sheet.worksheet("metas_registros")

# ================= LOADERS =================
@st.cache_data(ttl=30)
def load_lancamentos():
    df = pd.DataFrame(ws_lanc.get_all_records())
    if df.empty:
        return df

    df.columns = df.columns.str.lower().str.strip()
    df["data"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce").dt.date
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0.0)
    df["tipo"] = df["tipo"].astype(str).str.lower().str.strip()

    return df.dropna(subset=["data"])

@st.cache_data(ttl=30)
def load_metas():
    df = pd.DataFrame(ws_metas.get_all_records())

    if df.empty:
        return pd.DataFrame(columns=[
            "id","descricao","tipo_metrica","unidade",
            "valor_meta","inicio","fim"
        ])

    df.columns = df.columns.str.lower().str.strip()

    df["id"] = pd.to_numeric(df["id"], errors="coerce").astype(int)
    df["valor_meta"] = pd.to_numeric(df["valor_meta"], errors="coerce").fillna(0.0)
    df["inicio"] = pd.to_datetime(df["inicio"], dayfirst=True, errors="coerce").dt.date
    df["fim"] = pd.to_datetime(df["fim"], dayfirst=True, errors="coerce").dt.date
    df["tipo_metrica"] = df["tipo_metrica"].astype(str).str.lower().str.strip()

    return df.dropna(subset=["id","inicio","fim"])

@st.cache_data(ttl=30)
def load_registros_metas():
    df = pd.DataFrame(ws_reg.get_all_records())

    if df.empty:
        return pd.DataFrame(columns=["meta_id","data","valor"])

    df.columns = df.columns.str.lower().str.strip()
    df["meta_id"] = pd.to_numeric(df["meta_id"], errors="coerce").astype(int)
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0.0)
    df["data"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce").dt.date

    return df.dropna(subset=["meta_id","data"])

# ================= WRITE =================
def salvar_lancamento(d):
    ws_lanc.append_row(
        [
            d["data"].strftime("%d/%m/%Y"),
            d["tipo"],
            d["descricao"],
            float(d["valor"])
        ],
        value_input_option="USER_ENTERED"
    )
    load_lancamentos.clear()

def salvar_meta(m):
    ws_metas.append_row(
        [
            m["id"],
            m["descricao"],
            m["tipo_metrica"],
            m["unidade"],
            float(m["valor_meta"]),
            m["inicio"].strftime("%d/%m/%Y"),
            m["fim"].strftime("%d/%m/%Y")
        ],
        value_input_option="USER_ENTERED"
    )
    load_metas.clear()

def salvar_progresso_meta(meta_id, data, valor):
    ws_reg.append_row(
        [int(meta_id), data.strftime("%d/%m/%Y"), float(valor)],
        value_input_option="USER_ENTERED"
    )
    load_registros_metas.clear()

# ================= METAS =================
def progresso_meta(meta, df_reg):
    base = df_reg[df_reg["meta_id"] == meta["id"]]

    if base.empty:
        return 0.0, pd.DataFrame()

    base = base.sort_values("data")
    base["acumulado"] = base["valor"].cumsum()
    atual = base["acumulado"].iloc[-1]

    return atual, base

# ================= APP =================
st.title("📊 Dashboard Financeiro & Metas")

df_lanc = load_lancamentos()
df_metas = load_metas()
df_reg = load_registros_metas()

tab_dash, tab_lanc, tab_meta = st.tabs(
    ["📊 Dashboard", "➕ Lançamentos", "🎯 Metas"]
)

# -------- DASHBOARD --------
with tab_dash:
    st.subheader("Últimos lançamentos financeiros")
    st.dataframe(
        df_lanc.sort_values("data", ascending=False),
        use_container_width=True
    )

# -------- LANÇAMENTOS --------
with tab_lanc:
    st.subheader("Novo lançamento financeiro")

    with st.form("lanc"):
        d = st.date_input("Data", format="DD/MM/YYYY")
        t = st.selectbox("Tipo", ["receita","despesa"])
        desc = st.text_input("Descrição")
        val = st.number_input("Valor", min_value=0.0)

        if st.form_submit_button("Salvar"):
            salvar_lancamento({
                "data": d,
                "tipo": t,
                "descricao": desc,
                "valor": val
            })
            st.success("Lançamento salvo")
            st.rerun()

# -------- METAS --------
with tab_meta:
    st.subheader("Criar nova meta")

    with st.form("nova_meta"):
        novo_id = 1 if df_metas.empty else df_metas["id"].max() + 1
        desc = st.text_input("Descrição da meta")
        tipo = st.selectbox(
            "Tipo da meta",
            ["financeira","quantidade","percentual","tempo","binaria"]
        )
        unidade = st.text_input("Unidade (R$, dias, %, horas)")
        valor = st.number_input("Valor da meta", min_value=1.0)
        ini = st.date_input("Início", format="DD/MM/YYYY")
        fim = st.date_input("Fim", format="DD/MM/YYYY")

        if st.form_submit_button("Salvar meta"):
            salvar_meta({
                "id": novo_id,
                "descricao": desc,
                "tipo_metrica": tipo,
                "unidade": unidade,
                "valor_meta": valor,
                "inicio": ini,
                "fim": fim
            })
            st.success("Meta criada")
            st.rerun()

    st.divider()
    st.subheader("📈 Progresso das metas")

    for _, m in df_metas.iterrows():
        atual, hist = progresso_meta(m, df_reg)
        pct = min(atual / m["valor_meta"], 1) if m["valor_meta"] > 0 else 0

        st.markdown(f"### 🎯 {m['descricao']}")
        st.caption(f"{atual:.2f} {m['unidade']} / {m['valor_meta']} {m['unidade']}")
        st.progress(pct)

        if not hist.empty:
            st.line_chart(hist.set_index("data")[["acumulado"]])
        else:
            st.info("Nenhum progresso registrado ainda.")

        with st.expander("➕ Lançar progresso"):
            with st.form(f"prog_{m['id']}"):
                d = st.date_input("Data", format="DD/MM/YYYY")
                v = st.number_input("Valor do progresso", min_value=0.0)

                if st.form_submit_button("Salvar progresso"):
                    salvar_progresso_meta(m["id"], d, v)
                    st.success("Progresso registrado")
                    st.rerun()
