"""
Módulo para gerenciar cotações de moedas (USD/BRL) por mês.
Armazena e recupera cotações históricas para conversão.
"""

import os
import pandas as pd
from datetime import datetime
from typing import Optional
import yfinance as yf

COTACOES_PATH = "data/cotacoes_usd_brl.parquet"


def garantir_cotacoes_base() -> pd.DataFrame:
    """Garante que existe um arquivo base de cotações, criando se necessário."""
    if os.path.exists(COTACOES_PATH):
        try:
            return pd.read_parquet(COTACOES_PATH)
        except Exception:
            pass
    
    # Criar arquivo base vazio
    df = pd.DataFrame(columns=["Mês/Ano", "Cotação"])
    os.makedirs(os.path.dirname(COTACOES_PATH), exist_ok=True)
    df.to_parquet(COTACOES_PATH, index=False)
    return df


def obter_cotacao_mes_yfinance(mes_ano: str) -> Optional[float]:
    """
    Obtém cotação de fechamento do mês via yfinance.
    
    Args:
        mes_ano: Formato "MM/AAAA" (ex: "11/2024")
    
    Returns:
        Cotação de fechamento do mês ou None se não encontrar
    """
    try:
        # Converter MM/AAAA para datetime
        mes, ano = mes_ano.split("/")
        # Último dia do mês
        if int(mes) == 12:
            data_fim = f"{int(ano)+1}-01-01"
        else:
            data_fim = f"{ano}-{int(mes)+1:02d}-01"
        
        data_inicio = f"{ano}-{mes}-01"
        
        # Buscar histórico USD/BRL
        ticker = yf.Ticker("BRL=X")
        hist = ticker.history(start=data_inicio, end=data_fim)
        
        if not hist.empty:
            # Última cotação do período
            return float(hist["Close"].iloc[-1])
    except Exception as e:
        print(f"Erro ao obter cotação via yfinance para {mes_ano}: {e}")
    
    return None


def obter_cotacao_mes(mes_ano: str, forcar_atualizacao: bool = False) -> float:
    """
    Obtém cotação USD/BRL para um mês específico.
    
    Prioridade:
    1. Banco de dados local (se não forçar atualização)
    2. yfinance (busca online)
    3. Fallback fixo (5.80)
    
    Args:
        mes_ano: Formato "MM/AAAA" (ex: "11/2024")
        forcar_atualizacao: Se True, busca online mesmo que exista no banco
    
    Returns:
        Cotação USD/BRL do mês
    """
    df_cotacoes = garantir_cotacoes_base()
    
    # Buscar no banco local
    if not forcar_atualizacao and not df_cotacoes.empty:
        registro = df_cotacoes[df_cotacoes["Mês/Ano"] == mes_ano]
        if not registro.empty:
            return float(registro.iloc[0]["Cotação"])
    
    # Buscar online via yfinance
    cotacao = obter_cotacao_mes_yfinance(mes_ano)
    
    if cotacao:
        # Salvar no banco
        salvar_cotacao_mes(mes_ano, cotacao)
        return cotacao
    
    # Fallback
    print(f"[Aviso] Usando cotação fallback para {mes_ano}: 5.80")
    return 5.80


def salvar_cotacao_mes(mes_ano: str, cotacao: float) -> None:
    """
    Salva/atualiza cotação de um mês no banco local.
    
    Args:
        mes_ano: Formato "MM/AAAA"
        cotacao: Valor da cotação USD/BRL
    """
    df_cotacoes = garantir_cotacoes_base()
    
    # Remover registro existente se houver
    df_cotacoes = df_cotacoes[df_cotacoes["Mês/Ano"] != mes_ano]
    
    # Adicionar novo registro
    novo_registro = pd.DataFrame([{"Mês/Ano": mes_ano, "Cotação": cotacao}])
    df_cotacoes = pd.concat([df_cotacoes, novo_registro], ignore_index=True)
    
    # Salvar
    df_cotacoes.to_parquet(COTACOES_PATH, index=False)


def converter_usd_para_brl(valor_usd: float, mes_ano: str) -> float:
    """
    Converte valor de USD para BRL usando cotação do mês.
    
    Args:
        valor_usd: Valor em dólares
        mes_ano: Mês/ano da cotação (formato "MM/AAAA")
    
    Returns:
        Valor convertido em reais
    """
    cotacao = obter_cotacao_mes(mes_ano)
    return valor_usd * cotacao


def obter_cotacao_atual_usd_brl() -> float:
    """
    Obtém cotação atual (tempo real) de USD/BRL.
    
    Returns:
        Cotação atual ou fallback 5.80
    """
    try:
        ticker = yf.Ticker("BRL=X")
        hist = ticker.history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    
    return 5.80


def obter_historico_cotacao_usd_brl(periodo: str = "10y", intervalo: str = "1d") -> pd.DataFrame:
    """
    Obtém histórico de cotações USD/BRL.
    
    Args:
        periodo: Período do histórico. Opções: '1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max'
        intervalo: Intervalo dos dados. Opções: '1d' (diário), '1wk' (semanal), '1mo' (mensal)
    
    Returns:
        DataFrame com colunas: Date (index), Open, High, Low, Close, Volume
    """
    try:
        ticker = yf.Ticker("BRL=X")
        hist = ticker.history(period=periodo, interval=intervalo)
        
        if not hist.empty:
            # Reset index para ter Date como coluna
            hist = hist.reset_index()
            # Renomear coluna de data
            if 'Date' not in hist.columns and 'Datetime' in hist.columns:
                hist = hist.rename(columns={'Datetime': 'Date'})
            return hist
        else:
            return pd.DataFrame()
    except Exception as e:
        print(f"Erro ao obter histórico de cotação: {e}")
        return pd.DataFrame()


def obter_historico_indice(indice: str, periodo: str = "10y", intervalo: str = "1d") -> pd.DataFrame:
    """
    Obtém histórico de um índice específico.
    
    Args:
        indice: Nome do índice. Opções: 'USD/BRL', 'EUR/BRL', 'IBOV', 'SELIC'
        periodo: Período do histórico
        intervalo: Intervalo dos dados
    
    Returns:
        DataFrame com colunas: Date, Close
    """
    try:
        # Mapeamento de índices para tickers do yfinance
        ticker_map = {
            "USD/BRL": "BRL=X",
            "EUR/BRL": "EURBRL=X",
            "IBOV": "^BVSP",
            "SELIC": "IMA-B"  # Usar IMA-B como proxy melhor para renda fixa brasileira
        }
        
        ticker_symbol = ticker_map.get(indice)
        if not ticker_symbol:
            return pd.DataFrame()
        
        # Para SELIC, usar IHFA11 (ETF que rastreia IMA) ou criar índice sintético
        if indice == "SELIC":
            # Tentar múltiplas opções de ETFs de renda fixa
            etfs_renda_fixa = ["IMAB11.SA", "IHFA11.SA", "BRCR11.SA"]
            
            for etf in etfs_renda_fixa:
                try:
                    ticker = yf.Ticker(etf)
                    hist = ticker.history(period=periodo, interval=intervalo)
                    
                    if not hist.empty and len(hist) > 100:  # Garantir dados suficientes
                        hist = hist.reset_index()
                        if 'Date' not in hist.columns and 'Datetime' in hist.columns:
                            hist = hist.rename(columns={'Datetime': 'Date'})
                        
                        # Normalizar para mostrar rendimento acumulado crescente
                        # Usar valor inicial como base e calcular crescimento
                        valor_inicial = hist['Close'].iloc[0]
                        hist['Close_Original'] = hist['Close'].copy()
                        
                        # Se o ETF tiver queda (não deveria em renda fixa), ajustar
                        # Criar índice acumulado baseado em retornos diários
                        hist['Retorno'] = hist['Close'].pct_change().fillna(0)
                        hist['Indice_Acumulado'] = (1 + hist['Retorno']).cumprod() * valor_inicial
                        hist['Close'] = hist['Indice_Acumulado']
                        
                        return hist[['Date', 'Close']]
                except Exception as e:
                    continue
            
            # Se nenhum ETF funcionar, retornar vazio
            print(f"Aviso: Não foi possível obter dados de SELIC. Nenhum ETF disponível.")
            return pd.DataFrame()
        
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period=periodo, interval=intervalo)
        
        if not hist.empty:
            hist = hist.reset_index()
            if 'Date' not in hist.columns and 'Datetime' in hist.columns:
                hist = hist.rename(columns={'Datetime': 'Date'})
            return hist[['Date', 'Close']]
        else:
            return pd.DataFrame()
    except Exception as e:
        print(f"Erro ao obter histórico de {indice}: {e}")
        return pd.DataFrame()



def obter_historico_acao(ticker: str, periodo: str = "10y", intervalo: str = "1d") -> pd.DataFrame:
    """
    Obtém histórico de preços de uma ação.
    
    Args:
        ticker: Símbolo da ação (ex: 'AAPL', 'GOOGL')
        periodo: Período do histórico
        intervalo: Intervalo dos dados
    
    Returns:
        DataFrame com colunas: Date, Close
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=periodo, interval=intervalo)
        
        if not hist.empty:
            hist = hist.reset_index()
            if 'Date' not in hist.columns and 'Datetime' in hist.columns:
                hist = hist.rename(columns={'Datetime': 'Date'})
            return hist[['Date', 'Close']]
        else:
            return pd.DataFrame()
    except Exception as e:
        print(f"Erro ao obter histórico de {ticker}: {e}")
        return pd.DataFrame()


def converter_brl_para_usd(valor_brl: float, mes_ano: str) -> float:
    """
    Converte valor de BRL para USD usando cotação do mês.
    
    Args:
        valor_brl: Valor em reais
        mes_ano: Mês/ano da cotação (formato "MM/AAAA")
    
    Returns:
        Valor convertido em dólares
    """
    cotacao = obter_cotacao_mes(mes_ano)
    return valor_brl / cotacao if cotacao > 0 else valor_brl


def formatar_valor_moeda(valor: float, moeda: str = "BRL") -> str:
    """
    Formata valor conforme a moeda selecionada.
    
    Args:
        valor: Valor numérico
        moeda: 'BRL' ou 'USD'
    
    Returns:
        String formatada com símbolo de moeda
    """
    if moeda == "BRL":
        return f"R$ {valor:,.2f}"
    elif moeda == "USD":
        return f"$ {valor:,.2f}"
    else:
        return f"{valor:,.2f}"
