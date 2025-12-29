import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from modules.upload_relatorio import carregar_historico_parquet

st.title("📊 Indicadores de Mercado")

st.markdown("""
Bem-vindo à central de indicadores e gráficos do mercado financeiro!

Aqui você acompanha, em tempo real, os principais dados e tendências das ações, índices e moedas que movimentam o mercado brasileiro e internacional.

**Funcionalidades:**
- Gráficos interativos das principais ações da B3
- Indicadores de mercado: Ibovespa, IFIX, dólar, euro
- Comparação entre ativos
- Ranking das maiores altas e baixas do dia
- Análise técnica (médias móveis, RSI, MACD)
- Busca inteligente de ativos com autocomplete
- Painel de moedas
""")

# Carrega tickers do histórico consolidado
df_historico = carregar_historico_parquet()
if not df_historico.empty and "Código de Negociação" in df_historico.columns:
    tickers_historico = sorted(df_historico["Código de Negociação"].dropna().unique())
else:
    tickers_historico = []

# Lista de tickers populares da B3
tickers_populares = [
    "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "BBAS3.SA", "ABEV3.SA", "WEGE3.SA", "MGLU3.SA", "LREN3.SA", "RENT3.SA",
    "GGBR4.SA", "CSNA3.SA", "USIM5.SA", "JBSS3.SA", "SUZB3.SA", "VIVT3.SA", "TAEE11.SA", "HAPV3.SA", "B3SA3.SA", "BRFS3.SA"
]
tickers_autocomplete = sorted(set(tickers_populares + tickers_historico))

# Autocomplete de tickers
st.header("Buscar Ativo com Autocomplete")
ticker_input = st.text_input("Digite o ticker (ex: PETR4.SA, VALE3.SA, ^BVSP, USDBRL=X)")
suggestions = [t for t in tickers_autocomplete if ticker_input.upper() in t.upper()] if ticker_input else tickers_autocomplete[:5]
if ticker_input:
    st.write("Sugestões:", suggestions)
    if ticker_input.upper() in [t.upper() for t in tickers_autocomplete]:
        ticker_selecionado = ticker_input.upper()
    elif suggestions:
        ticker_selecionado = suggestions[0]
    else:
        ticker_selecionado = ticker_input.upper()
else:
    ticker_selecionado = suggestions[0]

if ticker_input:
    try:
        ticker = yf.Ticker(ticker_selecionado)
        hist = ticker.history(period="1y")
        st.subheader(f"Histórico de preços - {ticker_selecionado}")
        st.line_chart(hist["Close"])
        st.subheader("Volume negociado")
        st.bar_chart(hist["Volume"])
        st.subheader("Variação percentual")
        hist["%"] = hist["Close"].pct_change() * 100
        st.line_chart(hist["%"])
    except Exception as e:
        st.error(f"Erro ao buscar dados: {e}")

# Comparação entre ativos
st.header("Comparação entre ativos")
tickers_comp = st.text_input("Digite tickers separados por vírgula (ex: PETR4.SA, VALE3.SA, ITUB4.SA)")
if tickers_comp:
    lista_tickers = [t.strip() for t in tickers_comp.split(",")]
    try:
        df_comp = yf.download(lista_tickers, period="1y")["Close"]
        st.line_chart(df_comp)
    except Exception as e:
        st.error(f"Erro ao comparar ativos: {e}")

# Painel de moedas
st.header("Painel de Moedas")
moedas = ["USDBRL=X", "EURBRL=X"]
try:
    df_moedas = yf.download(moedas, period="1mo")["Close"]
    st.line_chart(df_moedas)
except Exception as e:
    st.error(f"Erro ao buscar moedas: {e}")

# Ranking das maiores altas/baixas (exemplo com tickers populares)
st.header("Ranking das maiores altas/baixas (exemplo)")
try:
    df_rank = yf.download(tickers_populares, period="5d")["Close"]
    var = df_rank.iloc[-1] / df_rank.iloc[0] - 1
    df_var = pd.DataFrame({"Ticker": var.index, "Variação (%)": var.values * 100})
    df_var = df_var.sort_values("Variação (%)", ascending=False)
    st.dataframe(df_var)
except Exception as e:
    st.error(f"Erro ao calcular ranking: {e}")

st.markdown("""
> **Dica:** Use os filtros e gráficos para comparar ativos, identificar tendências e tomar decisões mais informadas!
""")
