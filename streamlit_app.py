import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

# ================= CONFIGURAÇÃO =================
st.set_page_config(
    page_title="Sistema Financeiro Pessoal",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Sistema Financeiro Pessoal")
st.caption("Controle • Planejamento • Decisão")

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
taxa_poupanca = (saldo / receita_mensal) * 100 if receita_mensal > 0 else 0

custo_minimo = gastos_df[gastos_df["Categoria"] != "Lazer"]["Valor"].sum()

# ================= ABAS =================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Visão Geral",
    "🎯 Metas & Planejamento",
    "📈 Projeções",
    "🚨 Crise & Riscos",
    "⚙️ Configurações"
])

# ================= 📊 VISÃO GERAL =================
with tab1:
    st.subheader("Resumo Atual")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Receita", f"R$ {receita_mensal:,.2f}")
    c2.metric("💸 Gastos", f"R$ {total_gastos:,.2f}")
    c3.metric("📉 Saldo", f"R$ {saldo:,.2f}")
    c4.metric("📈 Poupança", f"{taxa_poupanca:.1f}%")

    st.divider()

    st.subheader("Gastos por Categoria")
    st.plotly_chart(
        px.bar(gastos_df, x="Categoria", y="Valor", text_auto=True),
        use_container_width=True
    )

    if saldo < 0:
        st.error("🚨 Você está gastando mais do que ganha")
    elif taxa_poupanca < 20:
        st.warning("⚠️ Taxa de poupança abaixo de 20%")
    else:
        st.success("✅ Situação financeira saudável")

# ================= 🎯 METAS & PLANEJAMENTO =================
with tab2:
    st.subheader("Metas Financeiras")

    metas = pd.DataFrame({
        "Meta": ["Reserva de Emergência", "Carro", "Apartamento"],
        "Objetivo": [30000, 50000, 300000],
        "Atual": [30000, 12000, 0]
    })

    for _, row in metas.iterrows():
        progresso = row["Atual"] / row["Objetivo"]
        st.progress(
            progresso,
            text=f"{row['Meta']} — R$ {row['Atual']:,.0f} / R$ {row['Objetivo']:,.0f}"
        )

    st.divider()

    st.subheader("Planejado x Real")

    planejado = {
        "Faculdade": 500,
        "Cartão": 450,
        "Gasolina": 350,
        "Academia": 150,
        "Alimentação": 550,
        "Assinaturas": 100,
        "Lazer": 250
    }

    plan_df = pd.DataFrame({
        "Categoria": planejado.keys(),
        "Planejado": planejado.values(),
        "Real": gastos_df.set_index("Categoria").loc[planejado.keys(), "Valor"].values
    })

    st.plotly_chart(
        px.bar(plan_df, x="Categoria", y=["Planejado", "Real"], barmode="group"),
        use_container_width=True
    )

# ================= 📈 PROJEÇÕES =================
with tab3:
    st.subheader("Liberdade Financeira")

    investimento_mensal = max(saldo, 0)
    rentabilidade = 0.07

    anos = list(range(0, 31))
    patrimonio = [
        investimento_mensal * ((1 + rentabilidade)**i - 1) / rentabilidade if i > 0 else 0
        for i in anos
    ]

    proj_df = pd.DataFrame({
        "Ano": anos,
        "Patrimônio": patrimonio
    })

    st.plotly_chart(
        px.line(proj_df, x="Ano", y="Patrimônio", markers=True),
        use_container_width=True
    )

    objetivo_liberdade = custo_minimo * 12 / rentabilidade
    st.metric("Patrimônio para Liberdade Financeira", f"R$ {objetivo_liberdade:,.0f}")

# ================= 🚨 CRISE & RISCOS =================
with tab4:
    st.subheader("Modo Crise")

    queda = st.slider("Queda de renda (%)", 0, 70, 30)
    nova_renda = receita_mensal * (1 - queda / 100)
    saldo_crise = nova_renda - custo_minimo

    c1, c2 = st.columns(2)
    c1.metric("Nova Renda", f"R$ {nova_renda:,.2f}")
    c2.metric("Saldo em Crise", f"R$ {saldo_crise:,.2f}")

    if saldo_crise < 0:
        st.error("🚨 Você entra no negativo nesse cenário")
    else:
        st.success("✅ Você sobrevive ao cenário")

# ================= ⚙️ CONFIGURAÇÕES =================
with tab5:
    st.subheader("Configurações (base para evoluir)")

    st.info(
        "Esta aba é a base para transformar o dashboard em app completo:\n\n"
        "- Editar renda\n"
        "- Editar metas\n"
        "- Ajustar limites\n"
        "- Conectar banco ou Google Sheets\n"
        "- Criar login\n"
    )

    st.write("Versão: 1.0 — Estrutura Profissional")
