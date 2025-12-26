import streamlit as st
import pandas as pd
import plotly.express as px

# ================= CONFIG =================
st.set_page_config(
    page_title="Dashboard Financeiro",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Dashboard Financeiro Pessoal")
st.markdown("Controle simples, visual e estratégico da sua vida financeira")

# ================= DADOS =================
data = [
    {"Tipo": "Receita", "Categoria": "Salário", "Valor": 2000},
    {"Tipo": "Receita", "Categoria": "Pensão", "Valor": 2000},

    {"Tipo": "Gasto", "Categoria": "Faculdade", "Valor": 500},
    {"Tipo": "Gasto", "Categoria": "Cartão", "Valor": 500},
    {"Tipo": "Gasto", "Categoria": "Gasolina", "Valor": 400},
    {"Tipo": "Gasto", "Categoria": "Academia", "Valor": 150},
    {"Tipo": "Gasto", "Categoria": "Outros", "Valor": 300},
]

df = pd.DataFrame(data)

# ================= KPIs =================
total_receita = df[df["Tipo"] == "Receita"]["Valor"].sum()
total_gasto = df[df["Tipo"] == "Gasto"]["Valor"].sum()
saldo = total_receita - total_gasto
taxa_poupanca = (saldo / total_receita) * 100 if total_receita > 0 else 0

col1, col2, col3, col4 = st.columns(4)

col1.metric("💰 Receita Mensal", f"R$ {total_receita:,.2f}")
col2.metric("💸 Gastos Totais", f"R$ {total_gasto:,.2f}")
col3.metric("📉 Saldo do Mês", f"R$ {saldo:,.2f}")
col4.metric("📈 Taxa de Poupança", f"{taxa_poupanca:.1f}%")

st.divider()

# ================= GRÁFICOS =================
colA, colB = st.columns(2)

# Receita x Gasto
fig_pie = px.pie(
    names=["Receitas", "Gastos"],
    values=[total_receita, total_gasto],
    title="Receitas x Gastos"
)
colA.plotly_chart(fig_pie, use_container_width=True)

# Gastos por categoria
gastos_categoria = df[df["Tipo"] == "Gasto"].groupby("Categoria")["Valor"].sum().reset_index()

fig_bar = px.bar(
    gastos_categoria,
    x="Categoria",
    y="Valor",
    title="Gastos por Categoria",
    text_auto=True
)
colB.plotly_chart(fig_bar, use_container_width=True)

# ================= TABELA =================
st.divider()
st.subheader("📋 Detalhamento Financeiro")
st.dataframe(df, use_container_width=True)

# ================= ALERTAS =================
st.divider()
st.subheader("🚨 Alertas Financeiros")

if saldo < 0:
    st.error("Você está gastando mais do que ganha!")
elif taxa_poupanca < 20:
    st.warning("Sua taxa de poupança está abaixo de 20%")
else:
    st.success("Situação financeira saudável 👍")
