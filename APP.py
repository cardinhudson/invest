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

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "Resumo", "Gráficos", "Histórico", "Comparações", "Cadastro", "Inserção Manual", "Upload CSV", "Alertas e Projeções"
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

# Aba Resumo
with tab1:
    st.header("Resumo Consolidado")
    st.header("Filtros dos Investimentos")
    # Filtro de usuário: apenas usuários cadastrados
    usuarios = ["Todos"] + sorted(df_usuarios["Nome"].unique()) if not df_usuarios.empty else ["Todos"]
    usuario_selecionado = st.selectbox("Filtrar por usuário", usuarios)

    # Filtro de período (mês/ano) como selectbox
    periodos_disponiveis = ["Todos"]
    if not df.empty and "Mês/Ano" in df.columns:
        periodos_disponiveis += sorted(df["Mês/Ano"].dropna().unique(), key=lambda x: (int(x.split("/")[1]), int(x.split("/")[0])))
    periodo_selecionado = st.selectbox("Filtrar por período (Mês/Ano)", periodos_disponiveis)

    categorias = ["Todas"]
    acoes = ["Todas"]
    if not df.empty:
        if "Tipo" in df.columns:
            categorias += sorted(df["Tipo"].dropna().unique())
        if "Código de Negociação" in df.columns:
            acoes += sorted(df["Código de Negociação"].dropna().unique())
    categoria_selecionada = st.selectbox("Filtrar por categoria", categorias)
    acao_selecionada = st.selectbox("Filtrar por ação", acoes)

    # Sempre inicialize DataFrame filtrado
    df_filtrado = df.copy() if not df.empty else pd.DataFrame()
    if not df_filtrado.empty:
        if usuario_selecionado != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Usuário"] == usuario_selecionado]
        if periodo_selecionado != "Todos" and "Mês/Ano" in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado["Mês/Ano"] == periodo_selecionado]
        if categoria_selecionada != "Todas" and "Tipo" in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado["Tipo"] == categoria_selecionada]
        if acao_selecionada != "Todas" and "Código de Negociação" in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado["Código de Negociação"] == acao_selecionada]

    # Exibir total dos investimentos
    if not df_filtrado.empty and "Valor Atualizado" in df_filtrado.columns:
        st.metric("Total dos Investimentos", f"R$ {df_filtrado['Valor Atualizado'].sum():,.2f}")

    # Exibir DataFrame filtrado
    st.dataframe(df_filtrado)

    # Busca de tickers com autocompletar
    import yfinance as yf
    st.header("Buscar Ticker do Mercado")
    ticker_input = st.text_input("Digite o ticker para buscar (ex: PETR4.SA)")
    if ticker_input:
        try:
            ticker = yf.Ticker(ticker_input)
            hist = ticker.history(period="5y")
            st.write(hist)
            st.line_chart(hist["Close"])
        except Exception as e:
            st.error(f"Erro ao buscar ticker: {e}")

    # Gráfico de evolução por período
    st.header("Evolução do Patrimônio")
    periodos = ["Mensal", "Bimestral", "Trimestral", "Semestral", "Anual"]
    periodo = st.selectbox("Período", periodos)
    if not df_filtrado.empty and "Mês/Ano" in df_filtrado.columns and "Valor Atualizado" in df_filtrado.columns:
        df_filtrado["Data"] = pd.to_datetime(df_filtrado["Mês/Ano"], format="%m/%Y")
        if periodo == "Mensal":
            df_group = df_filtrado.groupby([df_filtrado["Data"].dt.to_period("M")])["Valor Atualizado"].sum()
        elif periodo == "Bimestral":
            df_group = df_filtrado.groupby([df_filtrado["Data"].dt.to_period("2M")])["Valor Atualizado"].sum()
        elif periodo == "Trimestral":
            df_group = df_filtrado.groupby([df_filtrado["Data"].dt.to_period("Q")])["Valor Atualizado"].sum()
        elif periodo == "Semestral":
            df_group = df_filtrado.groupby([df_filtrado["Data"].dt.to_period("6M")])["Valor Atualizado"].sum()
        elif periodo == "Anual":
            df_group = df_filtrado.groupby([df_filtrado["Data"].dt.year])["Valor Atualizado"].sum()
        st.line_chart(df_group)
    elif not df_filtrado.empty:
        st.info("Dados insuficientes para gráfico de evolução.")
    else:
        st.info("Nenhum dado consolidado encontrado. Faça upload de relatórios na página apropriada.")

# Aba Gráficos
with tab2:
    st.header("Gráficos Interativos")
    if df.empty:
        st.info("Nenhum dado consolidado para gráficos.")
    else:
        if "Categoria" in df.columns and "Valor" in df.columns:
            fig_cat = px.pie(df, names="Categoria", values="Valor", title="Distribuição por Categoria")
            st.plotly_chart(fig_cat)
        if "Moeda" in df.columns and "Valor" in df.columns:
            fig_moeda = px.pie(df, names="Moeda", values="Valor", title="Distribuição por Moeda")
            st.plotly_chart(fig_moeda)
        # Gráfico de linha de evolução
        if "Mês/Ano" in df.columns:
            df_graf = df.copy()
            df_graf["Data"] = pd.to_datetime(df_graf["Mês/Ano"], format="%m/%Y")
            if "Valor Atualizado" in df_graf.columns:
                valor_col = "Valor Atualizado"
            elif "Valor" in df_graf.columns:
                valor_col = "Valor"
            else:
                valor_col = df_graf.select_dtypes(include=["number"]).columns[0] if not df_graf.select_dtypes(include=["number"]).empty else None
            if valor_col:
                df_group = df_graf.groupby([df_graf["Data"].dt.to_period("M")])[valor_col].sum()
                st.subheader("Evolução do patrimônio (linha)")
                st.line_chart(df_group)

# Aba Histórico
with tab3:
    st.header("Histórico de Investimentos")
    if df.empty:
        st.info("Nenhum dado consolidado para histórico.")
    else:
        st.dataframe(df)

# Aba Comparações
with tab4:
    st.header("Comparação com Benchmarks")
    st.write("Ibovespa vs Dólar vs CDI")
    try:
        import numpy as np
        ibov = pd.DataFrame()
        dolar = pd.DataFrame()
        # Exemplo fictício, substitua por busca real se desejar
        ibov["Ibovespa"] = np.random.normal(100000, 5000, 12)
        dolar["Dólar"] = np.random.normal(5, 0.2, 12)
        st.line_chart(ibov)
        st.line_chart(dolar)
        st.write("Taxa CDI anual simulada: 10.5%")
    except Exception as e:
        st.error(f"Erro ao buscar benchmarks: {e}")

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
