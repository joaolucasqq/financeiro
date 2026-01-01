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
            "valor_meta","inicio","fim","valor_manual"
        ])

    df.columns = df.columns.str.lower().str.strip()

    for col in [
        "id","descricao","tipo_metrica","unidade",
        "valor_meta","inicio","fim","valor_manual"
    ]:
        if col not in df.columns:
            df[col] = None

    df["id"] = pd.to_numeric(df["id"], errors="coerce").fillna(0).astype(int)
    df["valor_meta"] = pd.to_numeric(df["valor_meta"], errors="coerce").fillna(0.0)
    df["valor_manual"] = pd.to_numeric(df["valor_manual"], errors="coerce").fillna(0.0)
    df["inicio"] = pd.to_datetime(df["inicio"], dayfirst=True, errors="coerce").dt.date
    df["fim"] = pd.to_datetime(df["fim"], dayfirst=True, errors="coerce").dt.date
    df["tipo_metrica"] = df["tipo_metrica"].astype(str).str.lower().str.strip()

    return df.dropna(subset=["id","inicio","fim"])

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
            m["fim"].strftime("%d/%m/%Y"),
            0
        ],
        value_input_option="USER_ENTERED"
    )
    load_metas.clear()

def atualizar_valor_manual(meta_id, valor):
    cell = ws_metas.find(str(meta_id))
    ws_metas.update_cell(cell.row, 8, float(valor))
    load_metas.clear()

# ================= METAS =================
def calcular_progresso(meta, df_lanc):
    hoje = date.today()

    if meta["tipo_metrica"] == "financeira":
        base = df_lanc[
            (df_lanc["data"] >= meta["inicio"]) &
            (df_lanc["data"] <= meta["fim"]) &
            (df_lanc["tipo"] == "receita")
        ]
        atual = base["valor"].sum()
    else:
        atual = meta["valor_manual"]

    pct = min(atual / meta["valor_meta"], 1) if meta["valor_meta"] > 0 else 0

    total_dias = (meta["fim"] - meta["inicio"]).days + 1
    dias_passados = max(1, min((hoje - meta["inicio"]).days + 1, total_dias))
    projecao = (atual / dias_passados) * total_dias if dias_passados > 0 else atual

    return atual, pct, projecao

def gerar_evolucao_meta(meta, df_lanc):
    datas = pd.date_range(meta["inicio"], meta["fim"], freq="D")
    df = pd.DataFrame({"data": datas})

    if meta["tipo_metrica"] == "financeira":
        base = df_lanc[
            (df_lanc["data"] >= meta["inicio"]) &
            (df_lanc["data"] <= meta["fim"]) &
            (df_lanc["tipo"] == "receita")
        ].copy()

        base["data"] = pd.to_datetime(base["data"])
        base = base.groupby("data")["valor"].sum().reset_index()

        df = df.merge(base, on="data", how="left").fillna(0)
        df["acumulado"] = df["valor"].cumsum()
    else:
        total = len(df)
        crescimento = meta["valor_manual"] / total if total > 0 else 0
        df["acumulado"] = np.arange(1, total + 1) * crescimento

    df["meta"] = meta["valor_meta"]
    return df

def grafico_meta(meta, df_lanc):
    df = gerar_evolucao_meta(meta, df_lanc)
    pct = min(df["acumulado"].iloc[-1] / meta["valor_meta"], 1) if meta["valor_meta"] > 0 else 0

    st.progress(pct)

    st.markdown("**Evolução no tempo**")
    st.line_chart(df.set_index("data")[["acumulado"]])

    st.markdown("**Projeção vs Meta**")
    proj = df.set_index("data")[["acumulado"]].copy()
    proj["Meta"] = meta["valor_meta"]
    st.line_chart(proj)

# ================= APP =================
st.title("📊 Dashboard Financeiro & Metas")

df_lanc = load_lancamentos()
df_metas = load_metas()

tab_dash, tab_lanc, tab_meta = st.tabs(
    ["📊 Dashboard", "➕ Lançamentos", "🎯 Metas"]
)

# -------- DASHBOARD --------
with tab_dash:
    st.subheader("Últimos lançamentos")
    st.dataframe(df_lanc.sort_values("data", ascending=False), use_container_width=True)

# -------- LANÇAMENTOS --------
with tab_lanc:
    with st.form("lanc"):
        d = st.date_input("Data", format="DD/MM/YYYY")
        t = st.selectbox("Tipo", ["receita", "despesa"])
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
    st.subheader("📈 Acompanhamento das metas")

    for _, m in df_metas.iterrows():
        atual, pct, proj = calcular_progresso(m, df_lanc)

        st.markdown(f"### 🎯 {m['descricao']}")
        st.caption(
            f"Atual: {atual:.2f} {m['unidade']} | "
            f"Meta: {m['valor_meta']} {m['unidade']} | "
            f"Projeção: {proj:.2f}"
        )

        grafico_meta(m, df_lanc)

        if m["tipo_metrica"] != "financeira":
            novo_valor = st.number_input(
                f"Atualizar progresso ({m['unidade']})",
                value=float(m["valor_manual"]),
                key=f"meta_{m['id']}"
            )
            if st.button("Salvar progresso", key=f"save_{m['id']}"):
                atualizar_valor_manual(m["id"], novo_valor)
                st.rerun()
