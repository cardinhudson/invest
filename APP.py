import sys



import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from modules.upload_relatorio import carregar_historico_parquet
from modules.usuarios import carregar_usuarios, salvar_usuarios

st.set_page_config(page_title="Invest - Controle de Investimentos", layout="wide")
st.title("💰 Invest - Controle de Investimentos")

# Carregar histórico consolidado
try:
    df = carregar_historico_parquet()
except Exception:
    df = pd.DataFrame()


# Carregar usuários persistentes
df_usuarios = carregar_usuarios()


# Tabs para visualização por categoria e consolidado
tab_consolidado, tab_acoes, tab_rf, tab_prov, tab5, tab6, tab7, tab8 = st.tabs([
    "Consolidado", "Ações", "Renda Fixa", "Proventos", "Cadastro", "Inserção Manual", "Upload CSV", "Alertas e Projeções"
])

# Aba Cadastro de Usuários
with tab5:
    st.header("Cadastro de Usuários")
    nome = st.text_input("Nome do usuário")
    cpf = st.text_input("CPF")
    if st.button("Adicionar Usuário"):
        if nome and cpf:
            novo_usuario = pd.DataFrame([{"Nome": nome, "CPF": cpf}])
            df_usuarios = pd.concat([df_usuarios, novo_usuario], ignore_index=True).drop_duplicates()
            salvar_usuarios(df_usuarios)
            st.success(f"{nome} adicionado!")
        else:
            st.error("Preencha todos os campos.")
    st.table(df_usuarios)

import os
def carregar_df_parquet(path):
    if os.path.exists(path):
        return pd.read_parquet(path)
    else:
        return pd.DataFrame()
from modules.upload_relatorio import ACOES_PATH, RENDA_FIXA_PATH, PROVENTOS_PATH

# Aba Consolidado (tudo junto)
with tab_consolidado:
    st.header("Visão Consolidada de Investimentos")
    df_acoes = carregar_df_parquet(ACOES_PATH)
    df_rf = carregar_df_parquet(RENDA_FIXA_PATH)
    df_prov = carregar_df_parquet(PROVENTOS_PATH)
    # Consolidado só de ativos (ações + renda fixa)
    df_consolidado = pd.concat([df_acoes, df_rf], ignore_index=True, sort=False)
    st.dataframe(df_consolidado)
    # Total do patrimônio (ações + renda fixa)
    total_ativos = 0.0
    if not df_consolidado.empty and "Valor Atualizado" in df_consolidado.columns:
        total_ativos = df_consolidado["Valor Atualizado"].sum()
    st.metric("Total em Ativos (Ações + Renda Fixa)", f"R$ {total_ativos:,.2f}")
    # Proventos: mostrar total recebido, mas não somar ao patrimônio
    total_proventos = 0.0
    if not df_prov.empty and "Valor Líquido" in df_prov.columns:
        total_proventos = df_prov["Valor Líquido"].sum()
    st.metric("Total Recebido em Proventos", f"R$ {total_proventos:,.2f}")

# Aba Ações
with tab_acoes:
    st.header("Ações")
    df_acoes = carregar_df_parquet(ACOES_PATH)
    st.dataframe(df_acoes)

# Aba Renda Fixa
with tab_rf:
    st.header("Renda Fixa")
    df_rf = carregar_df_parquet(RENDA_FIXA_PATH)
    st.dataframe(df_rf)

# Aba Proventos
with tab_prov:
    st.header("Proventos")
    df_prov = carregar_df_parquet(PROVENTOS_PATH)
    st.dataframe(df_prov)
    st.header("Evolução dos Proventos Recebidos")
    periodos = ["Mensal", "Bimestral", "Trimestral", "Semestral", "Anual"]
    periodo = st.selectbox("Período", periodos, key="periodo_prov")
    if not df_prov.empty and "Mês/Ano" in df_prov.columns and "Valor Líquido" in df_prov.columns:
        df_prov["Data"] = pd.to_datetime(df_prov["Mês/Ano"], format="%m/%Y")
        if periodo == "Mensal":
            df_group = df_prov.groupby([df_prov["Data"].dt.to_period("M")])["Valor Líquido"].sum()
        elif periodo == "Bimestral":
            df_group = df_prov.groupby([df_prov["Data"].dt.to_period("2M")])["Valor Líquido"].sum()
        elif periodo == "Trimestral":
            df_group = df_prov.groupby([df_prov["Data"].dt.to_period("Q")])["Valor Líquido"].sum()
        elif periodo == "Semestral":
            df_group = df_prov.groupby([df_prov["Data"].dt.to_period("6M")])["Valor Líquido"].sum()
        elif periodo == "Anual":
            df_group = df_prov.groupby([df_prov["Data"].dt.year])["Valor Líquido"].sum()
        df_group.index = df_group.index.astype(str)
        st.subheader("Gráfico de Barras - Valor Recebido")
        st.bar_chart(df_group)
        st.subheader("Gráfico de Linha - Valor Recebido")
        st.line_chart(df_group)
        # Gráfico de percentual mês a mês
        st.subheader("Gráfico de Linha - Percentual de Crescimento (%)")
        df_pct = df_group.pct_change().fillna(0) * 100
        st.line_chart(df_pct)
    elif not df_prov.empty:
        st.info("Dados insuficientes para gráfico de evolução.")
    else:
        st.info("Nenhum dado consolidado encontrado. Faça upload de relatórios na página apropriada.")

## As abas de Gráficos, Histórico e Comparações podem ser reimplementadas aqui se desejado, usando os novos DataFrames separados ou o consolidado.


# Aba Inserção Manual
with tab6:
    st.header("Inserção Manual de Investimentos")
    st.info("Funcionalidade em desenvolvimento.")

# Aba Upload CSV
with tab7:
    st.header("Upload de Investimentos via CSV")
    st.info("Funcionalidade em desenvolvimento.")

# Aba Alertas e Projeções
with tab8:
    st.header("Alertas e Projeções")
    st.info("Funcionalidade em desenvolvimento.")

    if st.button("Calcular Projeção"):
        futuro = calcular_projecao_avancada(aporte_mensal, taxa_juros, anos)
        st.success(f"Projeção futura: R$ {futuro:,.2f}")
