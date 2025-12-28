# app.py
import os
from datetime import datetime, date, timedelta
import pandas as pd
import numpy as np
import streamlit as st

st.set_page_config(page_title="Financeiro Pessoal", layout="wide")

DATA_DIR = "data"
TX_PATH = os.path.join(DATA_DIR, "transactions.csv")
BUDGET_PATH = os.path.join(DATA_DIR, "budgets.csv")
CC_PATH = os.path.join(DATA_DIR, "credit_cards.csv")

REQUIRED_COLS = ["date", "type", "category", "account", "description", "amount"]

DEFAULT_CATEGORIES = [
    "Moradia", "Contas", "Mercado", "Transporte", "Saúde", "Lazer",
    "Educação", "Assinaturas", "Pets", "Roupas", "Presentes", "Outros"
]

DEFAULT_ACCOUNTS = ["Conta Principal", "Poupança", "Carteira", "Investimentos"]
DEFAULT_TYPES = ["income", "expense"]

def ensure_storage():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(TX_PATH):
        df = pd.DataFrame(columns=REQUIRED_COLS + ["fixed", "payment_method", "notes"])
        df.to_csv(TX_PATH, index=False)
    if not os.path.exists(BUDGET_PATH):
        # budgets: month (YYYY-MM), category, budget_amount
        dfb = pd.DataFrame(columns=["month", "category", "budget_amount"])
        dfb.to_csv(BUDGET_PATH, index=False)
    if not os.path.exists(CC_PATH):
        # credit cards config: name, closing_day (1-28), due_day (1-28), limit
        dfc = pd.DataFrame(
            [{"name": "Cartão Principal", "closing_day": 10, "due_day": 17, "limit": 5000}]
        )
        dfc.to_csv(CC_PATH, index=False)

def load_transactions():
    ensure_storage()
    df = pd.read_csv(TX_PATH)
    if df.empty:
        return df
    # parse date
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    df["type"] = df["type"].astype(str).str.lower()
    # normalize
    df = df[df["type"].isin(DEFAULT_TYPES)].copy()
    return df

def save_transactions(df: pd.DataFrame):
    df2 = df.copy()
    df2["date"] = pd.to_datetime(df2["date"]).dt.strftime("%Y-%m-%d")
    df2.to_csv(TX_PATH, index=False)

def load_budgets():
    ensure_storage()
    dfb = pd.read_csv(BUDGET_PATH)
    if dfb.empty:
        return dfb
    dfb["budget_amount"] = pd.to_numeric(dfb["budget_amount"], errors="coerce").fillna(0.0)
    dfb["month"] = dfb["month"].astype(str)
    dfb["category"] = dfb["category"].astype(str)
    return dfb

def save_budgets(dfb: pd.DataFrame):
    dfb.to_csv(BUDGET_PATH, index=False)

def load_credit_cards():
    ensure_storage()
    dfc = pd.read_csv(CC_PATH)
    if dfc.empty:
        dfc = pd.DataFrame(columns=["name", "closing_day", "due_day", "limit"])
    dfc["closing_day"] = pd.to_numeric(dfc["closing_day"], errors="coerce").fillna(10).astype(int)
    dfc["due_day"] = pd.to_numeric(dfc["due_day"], errors="coerce").fillna(17).astype(int)
    dfc["limit"] = pd.to_numeric(dfc["limit"], errors="coerce").fillna(0.0)
    return dfc

def save_credit_cards(dfc: pd.DataFrame):
    dfc.to_csv(CC_PATH, index=False)

def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"

def to_month_start(d: date) -> date:
    return date(d.year, d.month, 1)

def add_months(d: date, months: int) -> date:
    # safe month add
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    day = min(d.day, [31,29 if (y%4==0 and (y%100!=0 or y%400==0)) else 28,31,30,31,30,31,31,30,31,30,31][m-1])
    return date(y, m, day)

def compute_kpis(df: pd.DataFrame, start: date, end: date):
    if df.empty:
        return 0.0, 0.0, 0.0, 0.0
    mask = (df["date"] >= start) & (df["date"] <= end)
    dff = df.loc[mask].copy()
    income = dff.loc[dff["type"] == "income", "amount"].sum()
    expense = dff.loc[dff["type"] == "expense", "amount"].sum()
    net = income - expense
    # saldo acumulado: assume que "income" soma e "expense" subtrai
    df_sorted = df.sort_values("date").copy()
    df_sorted["signed"] = np.where(df_sorted["type"] == "income", df_sorted["amount"], -df_sorted["amount"])
    df_sorted["balance"] = df_sorted["signed"].cumsum()
    # saldo no final do período (último dia <= end)
    df_end = df_sorted[df_sorted["date"] <= end]
    balance_end = float(df_end["balance"].iloc[-1]) if not df_end.empty else 0.0
    return float(income), float(expense), float(net), float(balance_end)

def chart_balance(df: pd.DataFrame, start: date, end: date):
    if df.empty:
        st.info("Sem lançamentos para plotar.")
        return
    dff = df.sort_values("date").copy()
    dff["signed"] = np.where(dff["type"] == "income", dff["amount"], -dff["amount"])
    dff["balance"] = dff["signed"].cumsum()
    mask = (dff["date"] >= start) & (dff["date"] <= end)
    dplot = dff.loc[mask, ["date", "balance"]].copy()
    if dplot.empty:
        st.info("Sem dados no período para saldo acumulado.")
        return
    st.line_chart(dplot.set_index("date"))

def chart_monthly(df: pd.DataFrame, start: date, end: date):
    if df.empty:
        st.info("Sem lançamentos para plotar.")
        return
    mask = (df["date"] >= start) & (df["date"] <= end)
    dff = df.loc[mask].copy()
    if dff.empty:
        st.info("Sem dados no período.")
        return
    dff["month"] = pd.to_datetime(dff["date"]).dt.to_period("M").astype(str)
    pivot = dff.pivot_table(index="month", columns="type", values="amount", aggfunc="sum", fill_value=0).reset_index()
    pivot = pivot.sort_values("month")
    st.bar_chart(pivot.set_index("month"))

def chart_categories(df: pd.DataFrame, start: date, end: date, only_expenses=True):
    if df.empty:
        st.info("Sem lançamentos para plotar.")
        return
    mask = (df["date"] >= start) & (df["date"] <= end)
    dff = df.loc[mask].copy()
    if only_expenses:
        dff = dff[dff["type"] == "expense"]
    if dff.empty:
        st.info("Sem dados para categorias.")
        return
    cat = dff.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False)
    st.write(cat)
    # Streamlit não tem pizza nativo, mas dá pra mostrar como tabela e usar bar_chart
    st.bar_chart(cat.set_index("category"))

def compute_budget_status(df: pd.DataFrame, dfb: pd.DataFrame, month: str):
    if df.empty or dfb.empty:
        return pd.DataFrame(columns=["category", "budget_amount", "spent", "remaining", "pct_used"])
    budgets = dfb[dfb["month"] == month].copy()
    if budgets.empty:
        return pd.DataFrame(columns=["category", "budget_amount", "spent", "remaining", "pct_used"])
    # gastos do mês
    dfm = df.copy()
    dfm["month"] = pd.to_datetime(dfm["date"]).dt.to_period("M").astype(str)
    dfm = dfm[(dfm["month"] == month) & (dfm["type"] == "expense")]
    spent = dfm.groupby("category", as_index=False)["amount"].sum().rename(columns={"amount": "spent"})
    out = budgets.merge(spent, on="category", how="left")
    out["spent"] = out["spent"].fillna(0.0)
    out["remaining"] = out["budget_amount"] - out["spent"]
    out["pct_used"] = np.where(out["budget_amount"] > 0, out["spent"] / out["budget_amount"], np.nan)
    out = out.sort_values("pct_used", ascending=False)
    return out

def cc_cycle_for_date(d: date, closing_day: int):
    # ciclo do cartão: de (closing+1 do mês anterior) até closing do mês atual (aproximação simples)
    # Ex: fechamento dia 10. Ciclo: 11 do mês anterior -> 10 do mês atual.
    closing_this_month = date(d.year, d.month, min(closing_day, 28))
    if d <= closing_this_month:
        cycle_end = closing_this_month
        cycle_start = add_months(closing_this_month, -1) + timedelta(days=1)
    else:
        next_close = add_months(closing_this_month, 1)
        cycle_end = next_close
        cycle_start = closing_this_month + timedelta(days=1)
    return cycle_start, cycle_end

# ---------------- UI ----------------
ensure_storage()

st.title("💸 Dashboard Financeiro Pessoal (Streamlit)")

with st.sidebar:
    st.header("⚙️ Configurações & Importação")

    df = load_transactions()

    uploaded = st.file_uploader("Importar CSV de lançamentos", type=["csv"])
    if uploaded is not None:
        df_up = pd.read_csv(uploaded)
        missing = [c for c in REQUIRED_COLS if c not in df_up.columns]
        if missing:
            st.error(f"CSV sem colunas obrigatórias: {missing}")
        else:
            # normaliza
            df_up = df_up.copy()
            df_up["date"] = pd.to_datetime(df_up["date"], errors="coerce").dt.date
            df_up["amount"] = pd.to_numeric(df_up["amount"], errors="coerce").fillna(0.0)
            df_up["type"] = df_up["type"].astype(str).str.lower()
            for col in ["fixed", "payment_method", "notes"]:
                if col not in df_up.columns:
                    df_up[col] = ""
            df = pd.concat([df, df_up], ignore_index=True).dropna(subset=["date"])
            save_transactions(df)
            st.success("Importado e salvo em data/transactions.csv")

    if st.button("🔄 Usar dados de exemplo"):
        today = date.today()
        sample = pd.DataFrame([
            {"date": today.replace(day=1), "type": "income", "category": "Salário", "account": "Conta Principal",
             "description": "Salário", "amount": 4500, "fixed": True, "payment_method": "Transferência", "notes": ""},
            {"date": today.replace(day=2), "type": "expense", "category": "Moradia", "account": "Conta Principal",
             "description": "Aluguel", "amount": 1400, "fixed": True, "payment_method": "Pix", "notes": ""},
            {"date": today.replace(day=5), "type": "expense", "category": "Mercado", "account": "Conta Principal",
             "description": "Compras do mês", "amount": 650, "fixed": False, "payment_method": "Débito", "notes": ""},
            {"date": today.replace(day=8), "type": "expense", "category": "Transporte", "account": "Conta Principal",
             "description": "Combustível", "amount": 220, "fixed": False, "payment_method": "Crédito", "notes": "Cartão Principal"},
            {"date": today.replace(day=12), "type": "expense", "category": "Lazer", "account": "Conta Principal",
             "description": "Restaurante", "amount": 180, "fixed": False, "payment_method": "Crédito", "notes": "Cartão Principal"},
        ])
        # adaptar colunas
        sample["fixed"] = sample["fixed"].astype(bool)
        df = pd.concat([df, sample], ignore_index=True)
        save_transactions(df)
        st.success("Dados de exemplo adicionados!")

    st.divider()

    st.subheader("📌 Filtros")
    if df.empty:
        min_date = date.today().replace(day=1)
        max_date = date.today()
    else:
        min_date = min(df["date"])
        max_date = max(df["date"])

    # default: mês atual
    start_default = date.today().replace(day=1)
    end_default = date.today()

    start = st.date_input("Início", value=start_default, min_value=min_date, max_value=max_date)
    end = st.date_input("Fim", value=end_default, min_value=min_date, max_value=max_date)

    type_filter = st.multiselect("Tipo", options=["income", "expense"], default=["income", "expense"])

    categories = sorted(set(df["category"].dropna().astype(str).tolist() + DEFAULT_CATEGORIES))
    cat_filter = st.multiselect("Categorias", options=categories, default=[])

    accounts = sorted(set(df["account"].dropna().astype(str).tolist() + DEFAULT_ACCOUNTS))
    acc_filter = st.multiselect("Contas", options=accounts, default=[])

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

# Tabs
tab_dash, tab_add, tab_budget, tab_cc, tab_data = st.tabs(
    ["📊 Dashboard", "➕ Novo lançamento", "🎯 Orçamentos", "💳 Cartão de crédito", "🗂️ Dados"]
)

with tab_dash:
    col1, col2, col3, col4 = st.columns(4)
    income, expense, net, balance_end = compute_kpis(df, start, end)

    col1.metric("💰 Saldo (até fim do período)", f"R$ {balance_end:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    col2.metric("📈 Entradas", f"R$ {income:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    col3.metric("📉 Saídas", f"R$ {expense:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    col4.metric("🧾 Resultado", f"R$ {net:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    st.divider()

    cA, cB = st.columns(2)
    with cA:
        st.subheader("📈 Saldo acumulado (no período)")
        chart_balance(df, start, end)

    with cB:
        st.subheader("📊 Entradas x Saídas por mês")
        chart_monthly(df, start, end)

    st.divider()

    cC, cD = st.columns(2)
    with cC:
        st.subheader("🧩 Gastos por categoria (período)")
        chart_categories(df, start, end, only_expenses=True)

    with cD:
        st.subheader("📌 Últimos lançamentos (período)")
        st.dataframe(df_view.sort_values("date", ascending=False), use_container_width=True)

with tab_add:
    st.subheader("➕ Adicionar lançamento")
    with st.form("add_tx"):
        c1, c2, c3 = st.columns(3)
        with c1:
            d = st.date_input("Data", value=date.today())
            t = st.selectbox("Tipo", options=["expense", "income"])
        with c2:
            cat = st.selectbox("Categoria", options=sorted(set(categories)))
            acc = st.selectbox("Conta", options=sorted(set(accounts)))
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

        submitted = st.form_submit_button("Salvar")
        if submitted:
            new_row = {
                "date": d,
                "type": t,
                "category": cat,
                "account": acc,
                "description": desc,
                "amount": float(amt),
                "fixed": bool(fixed),
                "payment_method": pay,
                "notes": notes
            }
            df2 = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_transactions(df2)
            st.success("Lançamento salvo!")
            st.rerun()

with tab_budget:
    st.subheader("🎯 Orçamentos por categoria (mês)")
    dfb = load_budgets()

    month = st.selectbox(
        "Mês (YYYY-MM)",
        options=sorted(set(dfb["month"].tolist() + [month_key(date.today())])),
        index=0 if month_key(date.today()) not in set(dfb["month"].tolist()) else sorted(set(dfb["month"].tolist() + [month_key(date.today())])).index(month_key(date.today()))
    )

    st.caption("Defina quanto você quer gastar por categoria nesse mês. O app calcula quanto já foi gasto e quanto falta.")

    c1, c2 = st.columns(2)
    with c1:
        cat_b = st.selectbox("Categoria", options=sorted(set(categories)))
    with c2:
        bud = st.number_input("Orçamento (R$)", min_value=0.0, step=50.0, format="%.2f")

    if st.button("💾 Salvar orçamento"):
        row = {"month": month, "category": cat_b, "budget_amount": float(bud)}
        if dfb.empty:
            dfb2 = pd.DataFrame([row])
        else:
            dfb2 = dfb.copy()
            # upsert
            mask = (dfb2["month"] == month) & (dfb2["category"] == cat_b)
            dfb2 = dfb2[~mask]
            dfb2 = pd.concat([dfb2, pd.DataFrame([row])], ignore_index=True)
        save_budgets(dfb2)
        st.success("Orçamento salvo!")
        st.rerun()

    st.divider()

    status = compute_budget_status(load_transactions(), load_budgets(), month)
    if status.empty:
        st.info("Sem orçamentos definidos para este mês.")
    else:
        # alertas
        over = status[status["remaining"] < 0]
        if not over.empty:
            st.error("⚠️ Categorias estouradas:")
            st.dataframe(over[["category", "budget_amount", "spent", "remaining", "pct_used"]], use_container_width=True)
        st.subheader("📌 Status do orçamento")
        st.dataframe(status[["category", "budget_amount", "spent", "remaining", "pct_used"]], use_container_width=True)

with tab_cc:
    st.subheader("💳 Cartão de crédito (faturas por fechamento)")
    dfc = load_credit_cards()

    st.caption("Configure seus cartões e o app estima a fatura usando lançamentos com 'Forma de pagamento = Crédito' e 'Observações = nome do cartão'.")

    with st.expander("⚙️ Configurar cartões", expanded=False):
        st.dataframe(dfc, use_container_width=True)
        st.write("Edite o CSV em `data/credit_cards.csv` ou use o formulário abaixo.")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            cc_name = st.text_input("Nome do cartão", value="Cartão Principal")
        with c2:
            closing = st.number_input("Dia de fechamento (1-28)", min_value=1, max_value=28, value=10)
        with c3:
            due = st.number_input("Dia de vencimento (1-28)", min_value=1, max_value=28, value=17)
        with c4:
            limit = st.number_input("Limite (R$)", min_value=0.0, step=100.0, value=5000.0, format="%.2f")

        if st.button("💾 Salvar cartão"):
            row = {"name": cc_name, "closing_day": int(closing), "due_day": int(due), "limit": float(limit)}
            dfc2 = dfc.copy()
            dfc2 = dfc2[dfc2["name"] != cc_name]
            dfc2 = pd.concat([dfc2, pd.DataFrame([row])], ignore_index=True)
            save_credit_cards(dfc2)
            st.success("Cartão salvo!")
            st.rerun()

    if dfc.empty:
        st.info("Cadastre pelo menos 1 cartão.")
    else:
        card = st.selectbox("Selecionar cartão", options=dfc["name"].tolist())
        row = dfc[dfc["name"] == card].iloc[0]
        closing_day = int(row["closing_day"])
        limit = float(row["limit"])

        # pega gastos no crédito com notes == card
        tx = load_transactions()
        txc = tx[(tx["type"] == "expense") & (tx.get("payment_method", "") == "Crédito")].copy()
        if "notes" not in txc.columns:
            txc["notes"] = ""
        txc = txc[txc["notes"].astype(str).str.strip().str.lower() == str(card).strip().lower()]

        # fatura atual (ciclo baseado em hoje)
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
    st.subheader("🗂️ Base completa")
    st.dataframe(load_transactions().sort_values("date", ascending=False), use_container_width=True)

    st.caption("Arquivos locais usados pelo app:")
    st.code(f"{TX_PATH}\n{BUDGET_PATH}\n{CC_PATH}")

    st.download_button(
        "⬇️ Baixar transactions.csv",
        data=pd.read_csv(TX_PATH).to_csv(index=False).encode("utf-8"),
        file_name="transactions.csv",
        mime="text/csv"
    )
