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

# Para deixar a página mais fluida: não chama yfinance ao digitar/selecionar.
# Só busca dados quando o usuário clicar em "Carregar dados".

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
with st.form("form_indicadores_mercado"):
    ticker_input = st.text_input("Digite o ticker (ex: PETR4.SA, VALE3.SA, ^BVSP, USDBRL=X)")
    tickers_comp = st.text_input("Comparação: tickers separados por vírgula (ex: PETR4.SA, VALE3.SA, ITUB4.SA)")
    submitted = st.form_submit_button("▶️ Carregar dados", type="primary")

if ticker_input:
    suggestions = [t for t in tickers_autocomplete if ticker_input.upper() in t.upper()]
    suggestions = suggestions[:10]
    if suggestions:
        st.write("Sugestões:", suggestions)

if submitted:
    st.session_state["im_params"] = {
        "ticker_input": ticker_input or "",
        "tickers_comp": tickers_comp or "",
    }
    st.session_state.pop("im_data", None)

params = st.session_state.get("im_params")
if not isinstance(params, dict) or not (params.get("ticker_input") or params.get("tickers_comp")):
    st.info("Preencha um ticker e/ou comparação e clique em **Carregar dados**.")
    st.stop()

sig = (params.get("ticker_input") or "", params.get("tickers_comp") or "")
if (not isinstance(st.session_state.get("im_data"), dict)) or (st.session_state.get("im_sig") != sig):
    with st.spinner("Buscando dados no yfinance..."):
        data: dict = {}

        # Ativo principal
        ticker_in = (params.get("ticker_input") or "").strip()
        if ticker_in:
            # define ticker selecionado pela melhor sugestão
            suggestions = [t for t in tickers_autocomplete if ticker_in.upper() in t.upper()]
            ticker_sel = None
            if ticker_in.upper() in [t.upper() for t in tickers_autocomplete]:
                ticker_sel = ticker_in.upper()
            elif suggestions:
                ticker_sel = suggestions[0]
            else:
                ticker_sel = ticker_in.upper()

            try:
                tk = yf.Ticker(ticker_sel)
                hist = tk.history(period="1y")
                data["ticker_sel"] = ticker_sel
                data["hist"] = hist
            except Exception as e:
                data["ticker_sel"] = ticker_sel
                data["hist_error"] = str(e)

        # Comparação entre ativos
        comp_txt = (params.get("tickers_comp") or "").strip()
        if comp_txt:
            lista_tickers = [t.strip() for t in comp_txt.split(",") if t.strip()]
            try:
                df_comp = yf.download(lista_tickers, period="1y")["Close"]
                data["df_comp"] = df_comp
            except Exception as e:
                data["df_comp_error"] = str(e)

        # Painel de moedas
        try:
            moedas = ["USDBRL=X", "EURBRL=X"]
            df_moedas = yf.download(moedas, period="1mo")["Close"]
            data["df_moedas"] = df_moedas
        except Exception as e:
            data["df_moedas_error"] = str(e)

        # Ranking
        try:
            df_rank = yf.download(tickers_populares, period="5d")["Close"]
            var = df_rank.iloc[-1] / df_rank.iloc[0] - 1
            df_var = pd.DataFrame({"Ticker": var.index, "Variação (%)": var.values * 100})
            df_var = df_var.sort_values("Variação (%)", ascending=False)
            data["df_rank"] = df_var
        except Exception as e:
            data["df_rank_error"] = str(e)

    st.session_state["im_sig"] = sig
    st.session_state["im_data"] = data

data = st.session_state.get("im_data") or {}

if data.get("hist_error"):
    st.error(f"Erro ao buscar dados do ativo: {data.get('hist_error')}")
elif isinstance(data.get("hist"), pd.DataFrame):
    hist = data["hist"].copy()
    ticker_sel = data.get("ticker_sel") or "(ticker)"
    st.subheader(f"Histórico de preços - {ticker_sel}")
    if "Close" in hist.columns:
        st.line_chart(hist["Close"])
    if "Volume" in hist.columns:
        st.subheader("Volume negociado")
        st.bar_chart(hist["Volume"])
    if "Close" in hist.columns:
        st.subheader("Variação percentual")
        hist["%"] = hist["Close"].pct_change() * 100
        st.line_chart(hist["%"])

st.header("Comparação entre ativos")
if data.get("df_comp_error"):
    st.error(f"Erro ao comparar ativos: {data.get('df_comp_error')}")
elif isinstance(data.get("df_comp"), (pd.Series, pd.DataFrame)):
    st.line_chart(data["df_comp"])

st.header("Painel de Moedas")
if data.get("df_moedas_error"):
    st.error(f"Erro ao buscar moedas: {data.get('df_moedas_error')}")
elif isinstance(data.get("df_moedas"), (pd.Series, pd.DataFrame)):
    st.line_chart(data["df_moedas"])

st.header("Ranking das maiores altas/baixas (exemplo)")
if data.get("df_rank_error"):
    st.error(f"Erro ao calcular ranking: {data.get('df_rank_error')}")
elif isinstance(data.get("df_rank"), pd.DataFrame):
    st.dataframe(data["df_rank"], use_container_width=True)

st.markdown("""
> **Dica:** Use os filtros e gráficos para comparar ativos, identificar tendências e tomar decisões mais informadas!
""")
