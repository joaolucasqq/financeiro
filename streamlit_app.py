import streamlit as st
import pandas as pd
from datetime import date, datetime
import gspread
from google.oauth2.service_account import Credentials

# ================= CONFIG =================
st.set_page_config(page_title="Dashboard Financeiro & Metas", layout="wide")

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
    df["tipo"] = df["tipo"].str.lower().str.strip()

    return df.dropna(subset=["data"])

@st.cache_data(ttl=30)
def load_metas():
    df = pd.DataFrame(ws_metas.get_all_records())
    if df.empty:
        return df

    df.columns = df.columns.str.lower().str.strip()
    df["id"] = df["id"].astype(int)
    df["valor_meta"] = pd.to_numeric(df["valor_meta"], errors="coerce").fillna(0.0)
    df["valor_manual"] = pd.to_numeric(df["valor_manual"], errors="coerce").fillna(0.0)
    df["inicio"] = pd.to_datetime(df["inicio"], dayfirst=True).dt.date
    df["fim"] = pd.to_datetime(df["fim"], dayfirst=True).dt.date

    return df

# ================= WRITE =================
def salvar_lancamento(d):
    ws_lanc.append_row([
        d["data"].strftime("%d/%m/%Y"),
        d["tipo"], d["categoria"], d["conta"],
        d["descricao"], d["valor"],
        d["fixo"], d["pagamento"], d["observacao"]
    ], value_input_option="USER_ENTERED")
    load_lancamentos.clear()

def salvar_meta(m):
    ws_metas.append_row([
        m["id"], m["descricao"], m["tipo_metrica"],
        m["unidade"], m["valor_meta"],
        m["inicio"].strftime("%d/%m/%Y"),
        m["fim"].strftime("%d/%m/%Y"),
        0
    ], value_input_option="USER_ENTERED")
    load_metas.clear()

def atualizar_progresso(meta_id, valor):
    cell = ws_metas.find(str(meta_id))
    ws_metas.update_cell(cell.row, 8, valor)
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
    dias_passados = max(1, (hoje - meta["inicio"]).days + 1)
    projecao = (atual / dias_passados) * total_dias if dias_passados > 0 else atual

    return atual, pct, projecao

# ================= APP =================
st.title("📊 Dashboard Financeiro & Metas")

df_lanc = load_lancamentos()
df_metas = load_metas()

tab_dash, tab_lanc, tab_meta = st.tabs(
    ["📊 Dashboard", "➕ Lançamentos", "🎯 Metas"]
)

# ---------- DASHBOARD ----------
with tab_dash:
    st.dataframe(df_lanc.sort_values("data", ascending=False), use_container_width=True)

# ---------- LANÇAMENTOS ----------
# ---------- LANÇAMENTOS ----------
with tab_lanc:
    st.subheader("➕ Lançamentos")

    sub_fin, sub_meta = st.tabs(
        ["💸 Lançamentos Financeiros", "🎯 Lançamentos de Metas"]
    )

    # ===== SUB ABA 1 — LANÇAMENTOS FINANCEIROS =====
    with sub_fin:
        st.subheader("💸 Novo lançamento financeiro")

        with st.form("form_lanc_fin"):
            data = st.date_input("Data", format="DD/MM/YYYY")
            tipo = st.selectbox("Tipo", ["receita", "despesa"])
            categoria = st.text_input("Categoria")
            conta = st.text_input("Conta")
            descricao = st.text_input("Descrição")
            valor = st.number_input("Valor", min_value=0.0)
            fixo = st.selectbox("Fixo?", ["sim", "não"])
            pagamento = st.selectbox("Pagamento", ["pix", "débito", "crédito"])
            observacao = st.text_input("Observação")

            if st.form_submit_button("Salvar lançamento"):
                salvar_lancamento({
                    "data": data,
                    "tipo": tipo,
                    "categoria": categoria,
                    "conta": conta,
                    "descricao": descricao,
                    "valor": valor,
                    "fixo": fixo,
                    "pagamento": pagamento,
                    "observacao": observacao
                })
                st.success("Lançamento financeiro salvo ✅")
                st.rerun()

    # ===== SUB ABA 2 — LANÇAMENTOS DE METAS =====
    with sub_meta:
        st.subheader("🎯 Criar nova meta")

        with st.form("form_lanc_meta"):
            novo_id = 1 if df_metas.empty else df_metas["id"].max() + 1

            descricao = st.text_input("Descrição da meta")
            tipo = st.selectbox(
                "Tipo da meta",
                ["financeira", "quantidade", "percentual", "tempo", "binaria"]
            )
            unidade = st.text_input("Unidade (R$, dias, %, horas)")
            valor = st.number_input("Valor da meta", min_value=1.0)
            inicio = st.date_input("Início", format="DD/MM/YYYY")
            fim = st.date_input("Fim", format="DD/MM/YYYY")

            if st.form_submit_button("Salvar meta"):
                if not descricao.strip() or fim < inicio:
                    st.error("Preencha os dados corretamente.")
                else:
                    salvar_meta({
                        "id": novo_id,
                        "descricao": descricao,
                        "tipo_metrica": tipo,
                        "unidade": unidade,
                        "valor_meta": valor,
                        "inicio": inicio,
                        "fim": fim
                    })
                    st.success("Meta criada com sucesso 🎯")
                    st.rerun()


# ---------- METAS (VISUALIZAÇÃO COMPLETA) ----------
with tab_meta:
    st.subheader("📈 Progresso das metas")

    if df_metas.empty:
        st.info("Nenhuma meta cadastrada.")
    else:
        # carrega registros de progresso
        df_reg = load_registros_metas(ws_reg)

        for _, m in df_metas.iterrows():
            # progresso financeiro ou manual
            if m["tipo_metrica"] == "financeira":
                atual, pct, proj = calcular_progresso(m, df_lanc)
                hist = pd.DataFrame()
            else:
                atual, hist = progresso_meta(m, df_reg)
                pct = min(atual / m["valor_meta"], 1) if m["valor_meta"] > 0 else 0
                proj = None

            st.divider()
            st.subheader(f"🎯 {m['descricao']}")
            st.caption(
                f"Meta: {m['valor_meta']} {m['unidade']} • "
                f"Período: {m['inicio'].strftime('%d/%m/%Y')} → {m['fim'].strftime('%d/%m/%Y')}"
            )

            # KPIs
            c1, c2, c3 = st.columns(3)
            c1.metric("Atual", f"{atual:.2f} {m['unidade']}")
            c2.metric("Progresso", f"{pct*100:.1f}%")
            if proj is not None:
                c3.metric("Projeção", f"{proj:.2f} {m['unidade']}")
            else:
                c3.metric("Restante", f"{m['valor_meta'] - atual:.2f} {m['unidade']}")

            st.progress(pct)

            # -------- HISTÓRICO / GRÁFICO --------
            if not hist.empty:
                st.caption("📊 Evolução do progresso")
                st.line_chart(
                    hist.set_index("data")[["acumulado"]],
                    use_container_width=True
                )
            elif m["tipo_metrica"] != "financeira":
                st.info("Nenhum progresso registrado ainda.")

            # -------- LANÇAR PROGRESSO --------
            if m["tipo_metrica"] != "financeira":
                with st.expander("➕ Lançar progresso"):
                    with st.form(f"prog_{m['id']}"):
                        d = st.date_input(
                            "Data do progresso",
                            value=date.today(),
                            format="DD/MM/YYYY"
                        )
                        v = st.number_input(
                            f"Valor do progresso ({m['unidade']})",
                            min_value=0.0
                        )

                        if st.form_submit_button("Salvar progresso"):
                            salvar_progresso_meta(m["id"], d, v)
                            st.success("Progresso registrado ✅")
                            st.rerun()
