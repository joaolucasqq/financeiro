import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta
import gspread
from google.oauth2.service_account import Credentials

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Financeiro Pessoal", layout="wide")

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

SHEET_ID = "1sFMHJSj7zbpLn73n7QILqmGG3CLL98rXTm9Et9QKFMA"

DEFAULT_CATEGORIES = [
    "Moradia", "Contas", "Mercado", "Transporte", "Saúde", "Lazer",
    "Educação", "Assinaturas", "Pets", "Roupas", "Presentes", "Outros"
]
DEFAULT_ACCOUNTS = ["Conta Principal", "Poupança", "Carteira", "Investimentos"]
DEFAULT_TYPES = ["income", "expense"]

# ---------------- GOOGLE SHEETS ----------------
@st.cache_resource
def connect_gsheets():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPE
    )
    return gspread.authorize(creds)

client = connect_gsheets()
sheet = client.open_by_key(SHEET_ID)

# ⚠️ Ajuste aqui caso suas abas tenham nomes diferentes
ws_tx = sheet.worksheet("transactions")
ws_budget = sheet.worksheet("budgets")
ws_cc = sheet.worksheet("credit_cards")

# ---------------- HELPERS ----------------
def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"

def add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    days_in_month = [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28,
                     31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    day = min(d.day, days_in_month)
    return date(y, m, day)

def cc_cycle_for_date(d: date, closing_day: int):
    closing_this_month = date(d.year, d.month, min(int(closing_day), 28))
    if d <= closing_this_month:
        cycle_end = closing_this_month
        cycle_start = add_months(closing_this_month, -1) + timedelta(days=1)
    else:
        next_close = add_months(closing_this_month, 1)
        cycle_end = next_close
        cycle_start = closing_this_month + timedelta(days=1)
    return cycle_start, cycle_end

# ---------------- LOADERS ----------------
@st.cache_data(ttl=30)
def load_transactions():
    df = pd.DataFrame(ws_tx.get_all_records())
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    df["type"] = df["type"].astype(str).str.lower()
    df = df[df["type"].isin(DEFAULT_TYPES)].copy()
    # garante colunas opcionais
    for col in ["payment_method", "notes", "fixed"]:
        if col not in df.columns:
            df[col] = ""
    return df

@st.cache_data(ttl=30)
def load_budgets():
    df = pd.DataFrame(ws_budget.get_all_records())
    if df.empty:
        return df
    df["budget_amount"] = pd.to_numeric(df["budget_amount"], errors="coerce").fillna(0.0)
    df["month"] = df["month"].astype(str)
    df["category"] = df["category"].astype(str)
    return df

@st.cache_data(ttl=30)
def load_credit_cards():
    df = pd.DataFrame(ws_cc.get_all_records())
    if df.empty:
        return df
    df["closing_day"] = pd.to_numeric(df.get("closing_day", 10), errors="coerce").fillna(10).astype(int)
    df["due_day"] = pd.to_numeric(df.get("due_day", 17), errors="coerce").fillna(17).astype(int)
    df["limit"] = pd.to_numeric(df.get("limit", 0), errors="coerce").fillna(0.0)
    df["name"] = df["name"].astype(str)
    return df

# ---------------- WRITERS ----------------
def append_row(ws, values):
    ws.append_row(values, value_input_option="USER_ENTERED")

def add_transaction(row: dict):
    append_row(ws_tx, [
        str(row["date"]),
        row["type"],
        row["category"],
        row["account"],
        row["description"],
        float(row["amount"]),
        str(row.get("fixed", "")),
        row.get("payment_method", ""),
        row.get("notes", "")
    ])
    load_transactions.clear()  # limpa cache

def upsert_budget(month: str, category: str, budget_amount: float):
    dfb = load_budgets()
    if dfb.empty:
        append_row(ws_budget, [month, category, float(budget_amount)])
        load_budgets.clear()
        return

    # procura linha existente (1-based no Sheets). Header na linha 1.
    records = ws_budget.get_all_records()
    for i, r in enumerate(records, start=2):
        if str(r.get("month")) == month and str(r.get("category")) == category:
            ws_budget.update(f"C{i}", [[float(budget_amount)]])
            load_budgets.clear()
            return

    append_row(ws_budget, [month, category, float(budget_amount)])
    load_budgets.clear()

# ---------------- CALCS ----------------
def compute_kpis(df: pd.DataFrame, start: date, end: date):
    if df.empty:
        return 0.0, 0.0, 0.0, 0.0
    mask = (df["date"] >= start) & (df["date"] <= end)
    dff = df.loc[mask].copy()
    income = dff.loc[dff["type"] == "income", "amount"].sum()
    expense = dff.loc[dff["type"] == "expense", "amount"].sum()
    net = income - expense

    df_sorted = df.sort_values("date").copy()
    df_sorted["signed"] = np.where(df_sorted["type"] == "income", df_sorted["amount"], -df_sorted["amount"])
    df_sorted["balance"] = df_sorted["signed"].cumsum()
    df_end = df_sorted[df_sorted["date"] <= end]
    balance_end = float(df_end["balance"].iloc[-1]) if not df_end.empty else 0.0
    return float(income), float(expense), float(net), float(balance_end)

def compute_budget_status(df: pd.DataFrame, dfb: pd.DataFrame, month: str):
    if df.empty or dfb.empty:
        return pd.DataFrame(columns=["category", "budget_amount", "spent", "remaining", "pct_used"])
    budgets = dfb[dfb["month"] == month].copy()
    if budgets.empty:
        return pd.DataFrame(columns=["category", "budget_amount", "spent", "remaining", "pct_used"])

    dfm = df.copy()
    dfm["month"] = pd.to_datetime(dfm["date"]).dt.to_period("M").astype(str)
    dfm = dfm[(dfm["month"] == month) & (dfm["type"] == "expense")]

    spent = dfm.groupby("category", as_index=False)["amount"].sum().rename(columns={"amount": "spent"})
    out = budgets.merge(spent, on="category", how="left")
    out["spent"] = out["spent"].fillna(0.0)
    out["remaining"] = out["budget_amount"] - out["spent"]
    out["pct_used"] = np.where(out["budget_amount"] > 0, out["spent"] / out["budget_amount"], np.nan)
    return out.sort_values("pct_used", ascending=False)

# ---------------- UI ----------------
st.title("💸 Dashboard Financeiro Pessoal (Google Sheets)")

df = load_transactions()

with st.sidebar:
    st.header("📌 Filtros")

    if df.empty:
        st.warning("Sua aba 'transactions' está vazia. Adicione um lançamento na aba 'Novo lançamento'.")
        min_date = date.today().replace(day=1)
        max_date = date.today()
    else:
        min_date = min(df["date"])
        max_date = max(df["date"])

    start_default = date.today().replace(day=1)
    end_default = date.today()

    start = st.date_input("Início", value=start_default, min_value=min_date, max_value=max_date)
    end = st.date_input("Fim", value=end_default, min_value=min_date, max_value=max_date)

    type_filter = st.multiselect("Tipo", options=["income", "expense"], default=["income", "expense"])

    categories_all = sorted(set(df.get("category", pd.Series([])).dropna().astype(str).tolist() + DEFAULT_CATEGORIES))
    cat_filter = st.multiselect("Categorias", options=categories_all, default=[])

    accounts_all = sorted(set(df.get("account", pd.Series([])).dropna().astype(str).tolist() + DEFAULT_ACCOUNTS))
    acc_filter = st.multiselect("Contas", options=accounts_all, default=[])

# Apply filters
df_view = df.copy()
if not df_view.empty:
    df_view = df_view[(df_view["date"] >= start) & (df_view["date"] <= end)]
    if type_filter:
        df_view = df_view[df_view["type"].isin(type_filter)]
    if cat_filter:
        df_view = df_view[df_view["category"].isin(cat_filter)]
    if acc_filter:
        df_view = df_view[df_view["account"].isin(acc_filter)]

tab_dash, tab_add, tab_budget, tab_cc, tab_data = st.tabs(
    ["📊 Dashboard", "➕ Novo lançamento", "🎯 Orçamentos", "💳 Cartão de crédito", "🗂️ Dados"]
)

with tab_dash:
    col1, col2, col3, col4 = st.columns(4)
    income, expense, net, balance_end = compute_kpis(df, start, end)

    fmt = lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    col1.metric("💰 Saldo (até fim do período)", fmt(balance_end))
    col2.metric("📈 Entradas", fmt(income))
    col3.metric("📉 Saídas", fmt(expense))
    col4.metric("🧾 Resultado", fmt(net))

    st.divider()

    cA, cB = st.columns(2)
    with cA:
        st.subheader("📈 Saldo acumulado (no período)")
        if df.empty:
            st.info("Sem lançamentos.")
        else:
            dff = df.sort_values("date").copy()
            dff["signed"] = np.where(dff["type"] == "income", dff["amount"], -dff["amount"])
            dff["balance"] = dff["signed"].cumsum()
            mask = (dff["date"] >= start) & (dff["date"] <= end)
            dplot = dff.loc[mask, ["date", "balance"]]
            if dplot.empty:
                st.info("Sem dados no período.")
            else:
                st.line_chart(dplot.set_index("date"))

    with cB:
        st.subheader("📊 Entradas x Saídas por mês")
        if df_view.empty:
            st.info("Sem dados no período.")
        else:
            dff = df_view.copy()
            dff["month"] = pd.to_datetime(dff["date"]).dt.to_period("M").astype(str)
            pivot = dff.pivot_table(index="month", columns="type", values="amount", aggfunc="sum", fill_value=0).reset_index()
            pivot = pivot.sort_values("month")
            st.bar_chart(pivot.set_index("month"))

    st.divider()

    cC, cD = st.columns(2)
    with cC:
        st.subheader("🧩 Gastos por categoria (período)")
        if df_view.empty:
            st.info("Sem dados.")
        else:
            dff = df_view[df_view["type"] == "expense"]
            if dff.empty:
                st.info("Sem despesas no período.")
            else:
                cat = dff.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False)
                st.dataframe(cat, use_container_width=True)
                st.bar_chart(cat.set_index("category"))

    with cD:
        st.subheader("📌 Últimos lançamentos (período)")
        st.dataframe(df_view.sort_values("date", ascending=False), use_container_width=True)

with tab_add:
    st.subheader("➕ Adicionar lançamento (salva na planilha)")
    with st.form("add_tx"):
        c1, c2, c3 = st.columns(3)
        with c1:
            d = st.date_input("Data", value=date.today())
            t = st.selectbox("Tipo", options=["expense", "income"])
        with c2:
            cat = st.selectbox("Categoria", options=categories_all)
            acc = st.selectbox("Conta", options=accounts_all)
        with c3:
            amt = st.number_input("Valor (R$)", min_value=0.0, step=10.0, format="%.2f")

        c4, c5, c6 = st.columns(3)
        with c4:
            desc = st.text_input("Descrição", value="")
        with c5:
            fixed = st.checkbox("Despesa fixa?", value=False)
        with c6:
            pay = st.selectbox("Forma de pagamento", options=["Pix", "Débito", "Crédito", "Boleto", "Transferência", "Dinheiro", "Outro"])

        notes = st.text_input("Observações (ex: nome do cartão)", value="")

        submitted = st.form_submit_button("Salvar na planilha")
        if submitted:
            add_transaction({
                "date": d,
                "type": t,
                "category": cat,
                "account": acc,
                "description": desc,
                "amount": float(amt),
                "fixed": "sim" if fixed else "não",
                "payment_method": pay,
                "notes": notes
            })
            st.success("Lançamento salvo na planilha ✅")
            st.rerun()

with tab_budget:
    st.subheader("🎯 Orçamentos por categoria (mês) — salva na planilha")
    dfb = load_budgets()

    month = st.selectbox(
        "Mês (YYYY-MM)",
        options=sorted(set(dfb["month"].tolist() + [month_key(date.today())])) if not dfb.empty else [month_key(date.today())]
    )

    st.caption("Define orçamento por categoria no mês. O app calcula gasto e restante.")

    c1, c2 = st.columns(2)
    with c1:
        cat_b = st.selectbox("Categoria", options=categories_all, key="budget_cat")
    with c2:
        bud = st.number_input("Orçamento (R$)", min_value=0.0, step=50.0, format="%.2f", key="budget_val")

    if st.button("💾 Salvar / Atualizar orçamento"):
        upsert_budget(month, cat_b, float(bud))
        st.success("Orçamento salvo/atualizado ✅")
        st.rerun()

    st.divider()
    status = compute_budget_status(load_transactions(), load_budgets(), month)
    if status.empty:
        st.info("Sem orçamentos definidos para este mês.")
    else:
        over = status[status["remaining"] < 0]
        if not over.empty:
            st.error("⚠️ Categorias estouradas:")
            st.dataframe(over[["category", "budget_amount", "spent", "remaining", "pct_used"]], use_container_width=True)
        st.subheader("📌 Status do orçamento")
        st.dataframe(status[["category", "budget_amount", "spent", "remaining", "pct_used"]], use_container_width=True)

with tab_cc:
    st.subheader("💳 Cartão de crédito (faturas por fechamento)")
    dfc = load_credit_cards()

    st.caption("Aba 'credit_cards' deve ter colunas: name, closing_day, due_day, limit")

    if dfc.empty:
        st.info("Cadastre pelo menos 1 cartão na aba 'credit_cards'.")
    else:
        card = st.selectbox("Selecionar cartão", options=dfc["name"].tolist())
        row = dfc[dfc["name"] == card].iloc[0]
        closing_day = int(row["closing_day"])
        limit = float(row["limit"])

        tx = load_transactions()
        txc = tx[(tx["type"] == "expense") & (tx["payment_method"].astype(str) == "Crédito")].copy()
        txc = txc[txc["notes"].astype(str).str.strip().str.lower() == str(card).strip().lower()]

        cycle_start, cycle_end = cc_cycle_for_date(date.today(), closing_day)
        fatura = txc[(txc["date"] >= cycle_start) & (txc["date"] <= cycle_end)]
        total = fatura["amount"].sum()

        c1, c2, c3 = st.columns(3)
        c1.metric("📅 Ciclo atual", f"{cycle_start.strftime('%d/%m/%Y')} → {cycle_end.strftime('%d/%m/%Y')}")
        c2.metric("🧾 Fatura estimada", f"R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        used_pct = (total / limit) if limit > 0 else 0
        c3.metric("📌 Uso do limite", f"{used_pct*100:.1f}%")

        st.divider()
        st.subheader("Itens da fatura (ciclo atual)")
        st.dataframe(fatura.sort_values("date", ascending=False), use_container_width=True)

with tab_data:
    st.subheader("🗂️ Base completa (transactions)")
    st.dataframe(load_transactions().sort_values("date", ascending=False), use_container_width=True)

    st.caption("Se der erro de aba não encontrada, renomeie as abas para: transactions, budgets, credit_cards.")
