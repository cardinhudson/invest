
import pandas as pd
import yfinance as yf
from forex_python.converter import CurrencyRates
from datetime import datetime, timedelta

# =========================
# Função para conversão de moeda
# =========================
def converter_para_brl(valor, moeda_origem):
    try:
        c = CurrencyRates()
        return c.convert(moeda_origem, "BRL", valor)
    except:
        return valor  # fallback se API não responder

# =========================
# Função para consolidar investimentos
# =========================
def consolidar_investimentos(investimentos):
    df = pd.DataFrame(investimentos)
    if df.empty:
        return df
    df["Valor em BRL"] = df.apply(lambda x: converter_para_brl(x["Valor"], x["Moeda"]), axis=1)
    return df

# =========================
# Função para calcular evolução histórica (últimos 5 anos)
# =========================
def calcular_evolucao_historica(tickers):
    """
    Recebe uma lista de tickers e retorna um DataFrame com evolução histórica dos preços.
    """
    if not tickers:
        return pd.DataFrame()

    end_date = datetime.today()
    start_date = end_date - timedelta(days=5*365)  # últimos 5 anos

    dados = yf.download(tickers, start=start_date, end=end_date)["Adj Close"]
    return dados

# =========================
# Função para calcular dividendos acumulados
# =========================
def calcular_dividendos(ticker):
    """
    Retorna histórico de dividendos para um ticker.
    """
    dados = yf.Ticker(ticker).dividends
    return dados

# =========================
# Função para projeção futura
# =========================
def calcular_projecao(aporte_mensal, taxa_juros_anual, anos):
    """
    Calcula projeção futura com juros compostos.
    """
    taxa_mensal = (taxa_juros_anual / 100) / 12
    meses = anos * 12
    valor_futuro = 0
    for _ in range(meses):
        valor_futuro = (valor_futuro + aporte_mensal) * (1 + taxa_mensal)
    return round(valor_futuro, 2)

