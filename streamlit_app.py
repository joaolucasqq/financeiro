import streamlit as st
import pandas as pd
import plotly.express as px

# ================= CONFIG =================
st.set_page_config(
    page_title="Dashboard Financeiro Pessoal",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Dashboard Financeiro Pessoal")
st.caption("Controle, decisão e visão de longo prazo")

# ================= DADOS =================
dados = [
    {"Mes": "Jan", "Tipo": "Receita", "Categoria": "Salário", "Valor": 2000},
    {"Mes": "Jan", "Tipo": "Receita", "Categoria": "Pensão", "Valor": 2000},

    {"Mes": "Jan", "Tipo": "Gasto", "Categoria": "Faculdade", "Valor": 500, "Planejado": 500},
    {"Mes": "Jan", "Tipo": "Gasto", "Categoria": "Cartão", "Valor": 500, "Planejado": 450},
    {"Mes": "Jan", "Tipo": "Gasto", "Categoria": "Gasolina", "Valor": 400, "Planejado": 350},
    {"Mes": "Jan", "Tipo": "Gasto", "Categoria": "Academia", "Valor": 150, "Planejado": 150},
    {"Mes": "Jan", "Tipo": "Gasto", "Categoria": "Outros", "Valor": 300, "Planejado": 250},
]

df = pd.DataFrame(dados)

# ================= KPIs =================
receita = df[df["Tipo"] == "Receita"]["Valor"].sum()
gastos = df[df["Tipo"] == "Gasto"]["Valor"].sum()
saldo = receita - gastos
taxa_poupanca = (saldo / receita) * 100 if receita > 0 else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("💰 Receita", f"R$ {receita:,.2f}")
col2.metric("💸 Gastos", f"R$ {gastos:,.2f}")
col3.metric("📉 Saldo", f"R$ {saldo:,.2f}")
col4.metric("📈 Poupança", f"{taxa_poupanca:.1f}%")

st.divider()

# ================= METAS =================
st.subheader("🎯 Metas Financeiras")

metas = pd.DataFrame({
    "Meta": ["Reserva Emergência", "Carro", "Apartamento"],
    "Total": [30000, 50000, 300000],
    "Atual": [30000, 12000, 0]
})

for _, row in metas.iterrows():
    progresso = row["Atual"] / row["Total"]
    st.progress(progresso, text=f"{row['Meta']} — R$ {row['Atual']:,.0f} / R$ {row['Total']:,.0f}")

st.divider()

# ================= PLANEJADO x REAL =================
st.subheader("📊 Planejado x Real")

gastos_cat = df[df["Tipo"] == "Gasto"].groupby("Categoria").sum().reset_index()

fig_plan = px.bar(
    gastos_cat,
    x="Categoria",
    y=["Planejado", "Valor"],
    barmode="group",
    title="Orçamento x Gasto Real"
)
st.plotly_chart(fig_plan, use_container_width=True)

st.divider()

# ================= HISTÓRICO =================
st.subheader("📈 Evolução Financeira")

historico = pd.DataFrame({
    "Mês": ["Out", "Nov", "Dez", "Jan"],
    "Receita": [3500, 3800, 4000, receita],
    "Gastos": [3000, 3200, 3300, gastos]
})
historico["Saldo"] = historico["Receita"] - historico["Gastos"]

fig_hist = px.line(
    historico,
    x="Mês",
    y=["Receita", "Gastos", "Saldo"],
    markers=True
)
st.plotly_chart(fig_hist, use_container_width=True)

st.divider()

# ================= SCORE FINANCEIRO =================
st.subheader("🏆 Score Financeiro")

score = 0
if taxa_poupanca >= 20: score += 30
if saldo > 0: score += 20
if gastos <= receita * 0.8: score += 20
if metas.loc[0, "Atual"] >= metas.loc[0, "Total"]: score += 30

st.metric("Score Financeiro (0–100)", score)

if score >= 80:
    st.success("Excelente controle financeiro")
elif score >= 60:
    st.warning("Bom, mas pode melhorar")
else:
    st.error("Risco financeiro — ajuste urgente")

st.divider()

# ================= ALERTAS =================
st.subheader("🚨 Alertas Inteligentes")

if gastos > receita:
    st.error("Você gastou mais do que ganhou!")
if taxa_poupanca < 20:
    st.warning("Taxa de poupança abaixo do ideal (20%)")
if gastos_cat["Valor"].max() > gastos_cat["Planejado"].max():
    st.warning("Alguma categoria estourou o orçamento")

st.divider()

# ================= TABELA =================
st.subheader("📋 Lançamentos Financeiros")
st.dataframe(df, use_container_width=True)
