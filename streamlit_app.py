import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

# ================= CONFIG =================
st.set_page_config(
    page_title="Sistema Financeiro Pessoal",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Sistema Financeiro Pessoal — Elite")
st.caption("Controle • Decisão • Futuro")

# ================= DADOS BASE =================
receita_mensal = 4500
gastos = {
    "Faculdade": 500,
    "Cartão": 500,
    "Gasolina": 400,
    "Academia": 150,
    "Alimentação": 600,
    "Assinaturas": 120,
    "Lazer": 300
}

gastos_df = pd.DataFrame(gastos.items(), columns=["Categoria", "Valor"])
total_gastos = gastos_df["Valor"].sum()
saldo = receita_mensal - total_gastos
taxa_poupanca = saldo / receita_mensal * 100

# ================= KPIs =================
c1, c2, c3, c4 = st.columns(4)
c1.metric("💰 Receita", f"R$ {receita_mensal:,.2f}")
c2.metric("💸 Gastos", f"R$ {total_gastos:,.2f}")
c3.metric("📉 Saldo", f"R$ {saldo:,.2f}")
c4.metric("📈 Poupança", f"{taxa_poupanca:.1f}%")

st.divider()

# ================= 1️⃣ REGRA 50-30-20 =================
st.subheader("1️⃣ Regra Financeira (50–30–20)")

necessidades = gastos_df["Valor"].sum() * 0.6
qualidade = gastos_df["Valor"].sum() * 0.25
futuro = saldo

regra_df = pd.DataFrame({
    "Grupo": ["Necessidades", "Qualidade de Vida", "Futuro"],
    "Valor": [necessidades, qualidade, futuro]
})

st.plotly_chart(px.pie(regra_df, names="Grupo", values="Valor"), use_container_width=True)

# ================= 2️⃣ CUSTO DE VIDA REAL =================
st.subheader("2️⃣ Custo de Vida Real")

custo_minimo = gastos_df[gastos_df["Categoria"] != "Lazer"]["Valor"].sum()
meses_sobrevivencia = 30000 / custo_minimo

st.metric("Custo mínimo mensal", f"R$ {custo_minimo:,.2f}")
st.metric("Meses de sobrevivência (reserva)", f"{meses_sobrevivencia:.1f}")

# ================= 3️⃣ LIBERDADE FINANCEIRA =================
st.subheader("3️⃣ Tempo até Liberdade Financeira")

investimento_mensal = saldo
rentabilidade = 0.07
objetivo = custo_minimo * 12 / rentabilidade

anos = np.arange(0, 30)
patrimonio = [investimento_mensal * ((1 + rentabilidade) ** i - 1) / rentabilidade for i in anos]

df_lib = pd.DataFrame({"Ano": anos, "Patrimônio": patrimonio})
st.plotly_chart(px.line(df_lib, x="Ano", y="Patrimônio"), use_container_width=True)

# ================= 4️⃣ SIMULADOR DE DECISÕES =================
st.subheader("4️⃣ Simulador de Decisões")

extra = st.slider("Nova despesa mensal (R$)", 0, 2000, 0)
novo_saldo = saldo - extra
st.metric("Saldo após decisão", f"R$ {novo_saldo:,.2f}")

# ================= 5️⃣ CARTÃO DE CRÉDITO =================
st.subheader("5️⃣ Cartão de Crédito")

limite = 3000
usado = gastos["Cartão"]
percentual = usado / limite * 100

st.metric("Uso do cartão", f"{percentual:.1f}%")
st.progress(min(percentual / 100, 1.0))

# ================= 6️⃣ RENDA ATIVA x ESCALÁVEL =================
st.subheader("6️⃣ Tipos de Renda")

renda_df = pd.DataFrame({
    "Tipo": ["Ativa", "Escalável", "Passiva"],
    "Valor": [4500, 0, 0]
})
st.plotly_chart(px.bar(renda_df, x="Tipo", y="Valor"), use_container_width=True)

# ================= 7️⃣ SEGURANÇA FINANCEIRA =================
st.subheader("7️⃣ Índice de Segurança Financeira")

indice = 0
if meses_sobrevivencia >= 6: indice += 40
if taxa_poupanca >= 20: indice += 30
if percentual <= 30: indice += 30

st.metric("Índice de Segurança (0–100)", indice)

# ================= 8️⃣ LINHA DO TEMPO DA VIDA =================
st.subheader("8️⃣ Linha do Tempo da Vida")

vida_df = pd.DataFrame({
    "Evento": ["Casamento", "Filhos", "Imóvel"],
    "Ano": [2027, 2029, 2032]
})
st.dataframe(vida_df, use_container_width=True)

# ================= 9️⃣ AUDITORIA DE ASSINATURAS =================
st.subheader("9️⃣ Auditoria de Assinaturas")

assinaturas = pd.DataFrame({
    "Serviço": ["Spotify", "Netflix", "Cloud"],
    "Mensal": [34, 55, 31]
})
assinaturas["Anual"] = assinaturas["Mensal"] * 12
st.dataframe(assinaturas, use_container_width=True)

# ================= 🔟 MODO CRISE =================
st.subheader("🔟 Modo Crise")

queda = st.slider("Queda de renda (%)", 0, 60, 30)
nova_renda = receita_mensal * (1 - queda / 100)
novo_saldo_crise = nova_renda - custo_minimo

st.metric("Saldo em crise", f"R$ {novo_saldo_crise:,.2f}")

if novo_saldo_crise < 0:
    st.error("Risco financeiro severo")
else:
    st.success("Você sobrevive ao cenário")

