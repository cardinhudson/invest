import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta

__all__ = [
    'buscar_precos_historicos',
    'buscar_cdi',
    'buscar_ibovespa',
    'buscar_dolar'
]

# =========================
# Função para buscar preços históricos de ativos
# =========================
def buscar_precos_historicos(tickers, anos=5):
    """
    Retorna preços ajustados dos últimos X anos para os tickers informados.
    """
    if not tickers:
        return pd.DataFrame()

    end_date = datetime.today()
    start_date = end_date - timedelta(days=anos * 365)

    dados = yf.download(tickers, start=start_date, end=end_date)
    # Verifica se é MultiIndex (vários ativos)
    if isinstance(dados.columns, pd.MultiIndex):
        colunas = dados.columns.get_level_values(0)
        if "Adj Close" in colunas:
            return dados["Adj Close"]
        elif "Close" in colunas:
            return dados["Close"]
        else:
            return dados
    else:
        # DataFrame simples
        if "Adj Close" in dados.columns:
            return dados["Adj Close"]
        elif "Close" in dados.columns:
            return dados["Close"]
        else:
            return dados

# =========================
# Função para buscar CDI (simulação ou API)
# =========================
def buscar_cdi():
    """
    Retorna taxa CDI acumulada dos últimos 12 meses.
    (Aqui usamos valor fixo como placeholder, mas pode integrar com API do Banco Central)
    """
    return 13.65  # taxa anual simulada em %

# =========================
# Função para buscar Ibovespa histórico
# =========================
def buscar_ibovespa(anos=5):
    """
    Retorna histórico do índice Ibovespa via yfinance.
    """
    return buscar_precos_historicos("^BVSP", anos)

# =========================
# Função para buscar dólar histórico
# =========================
def buscar_dolar(anos=5):
    """
    Retorna histórico do dólar via yfinance.
    """
    return buscar_precos_historicos("USDBRL=X", anos)
