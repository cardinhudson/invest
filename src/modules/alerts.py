import yfinance as yf

__all__ = [
    'verificar_preco_alvo',
    'verificar_dividendos',
    'calcular_projecao_avancada'
]

# =========================
# Função para verificar preço alvo
# =========================
def verificar_preco_alvo(ticker, preco_alvo):
    """
    Verifica se o preço atual do ativo atingiu ou ultrapassou o preço alvo.
    Retorna True se atingiu, False caso contrário.
    """
    try:
        dados = yf.Ticker(ticker).history(period="1d")
        preco_atual = dados["Close"].iloc[-1]
        return preco_atual >= preco_alvo
    except:
        return False

# =========================
# Função para verificar pagamento de dividendos
# =========================
def verificar_dividendos(ticker):
    """
    Verifica se houve pagamento de dividendos recentemente.
    Retorna True se houve pagamento nos últimos 30 dias.
    """
    try:
        dados = yf.Ticker(ticker).dividends
        if not dados.empty:
            ultima_data = dados.index[-1]
            from datetime import datetime, timedelta
            if ultima_data >= datetime.today() - timedelta(days=30):
                return True
        return False
    except:
        return False

# =========================
# Função para projeção avançada com aportes mensais
# =========================
def calcular_projecao_avancada(aporte_mensal, taxa_juros_anual, anos):
    """
    Calcula projeção futura com aportes mensais e juros compostos.
    Fórmula: FV = P * ((1 + i)^n - 1) / i
    Onde:
    P = aporte mensal
    i = taxa mensal
    n = número de meses
    """
    taxa_mensal = (taxa_juros_anual / 100) / 12
    meses = anos * 12
    if taxa_mensal == 0:
        return aporte_mensal * meses
    valor_futuro = aporte_mensal * (((1 + taxa_mensal) ** meses - 1) / taxa_mensal)
    return round(valor_futuro, 2)
