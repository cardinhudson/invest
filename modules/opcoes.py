"""
Módulo para gerenciar opções (calls e puts) e vendas cobertas
Inclui consulta de opções disponíveis, registro de vendas e controle de dividendos sintéticos
"""

import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import yfinance as yf

# Caminho para armazenamento de dados
PASTA_DADOS = Path("data")
PASTA_DADOS.mkdir(exist_ok=True)
ARQ_VENDAS_OPCOES = PASTA_DADOS / "vendas_opcoes.parquet"


def _ticker_para_yf(ticker: str) -> str | None:
    if ticker is None:
        return None
    t = str(ticker).strip().upper()
    if not t:
        return None
    if "." in t:
        return t
    # convenção B3
    if t[-1:].isdigit():
        return f"{t}.SA"
    return t


def _ticker_curto(ticker: str) -> str | None:
    if ticker is None:
        return None
    t = str(ticker).strip()
    if not t:
        return None
    if " - " in t:
        t = t.split(" - ", 1)[0].strip()
    if "." in t:
        t = t.split(".", 1)[0].strip()
    return t


def _mes_ano(dt) -> str | None:
    try:
        d = pd.to_datetime(dt, errors="coerce")
        if pd.isna(d):
            return None
        return d.strftime("%m/%Y")
    except Exception:
        return None


def consultar_opcoes_disponiveis(ticker: str, tipo: str = "call") -> pd.DataFrame:
    """
    Consulta opções disponíveis para um ticker via yfinance
    
    Args:
        ticker: Código da ação (ex: PETR4.SA)
        tipo: 'call' ou 'put'
    
    Returns:
        DataFrame com colunas: strike, vencimento, preco_atual, distancia_pct
    """
    try:
        ticker_informado = str(ticker).strip() if ticker is not None else ""
        ticker_yf = _ticker_para_yf(ticker_informado)
        if not ticker_yf:
            return pd.DataFrame()

        # Obter dados da ação
        acao = yf.Ticker(ticker_yf)
        hist = acao.history(period="5d")
        if hist is None or hist.empty or "Close" not in hist.columns:
            return pd.DataFrame()
        close = pd.to_numeric(hist["Close"], errors="coerce").dropna()
        if close.empty:
            return pd.DataFrame()
        preco_atual = float(close.iloc[-1])
        
        # Obter datas de vencimento disponíveis
        datas_vencimento = acao.options
        
        if not datas_vencimento:
            return pd.DataFrame()
        
        # Coletar todas as opções
        opcoes_lista = []
        
        for data_venc in datas_vencimento:
            try:
                # Obter cadeia de opções para esta data
                cadeia = acao.option_chain(data_venc)
                
                # Selecionar calls ou puts
                if tipo.lower() == "call":
                    opcoes_df = cadeia.calls
                else:
                    opcoes_df = cadeia.puts
                
                # Extrair informações relevantes
                venc_dt = pd.to_datetime(data_venc, errors="coerce")
                mes_venc = _mes_ano(venc_dt)

                for _, row in opcoes_df.iterrows():
                    strike = row.get("strike", 0)
                    if strike == 0:
                        continue
                    
                    # Calcular distância percentual do strike
                    distancia_pct = ((strike - preco_atual) / preco_atual) * 100
                    
                    opcoes_lista.append({
                        "Ticker": _ticker_curto(ticker_informado) or ticker_informado,
                        "Ticker YF": ticker_yf,
                        "Tipo": tipo.capitalize(),
                        "Strike": strike,
                        "Vencimento": venc_dt,
                        "Mês Vencimento": mes_venc,
                        "Preço Atual Ação": preco_atual,
                        "Distância %": distancia_pct,
                        "Last Price": row.get("lastPrice", 0),
                        "Bid": row.get("bid", 0),
                        "Ask": row.get("ask", 0),
                        "Volume": row.get("volume", 0),
                        "Open Interest": row.get("openInterest", 0),
                        "Implied Volatility": row.get("impliedVolatility", 0),
                    })
            except Exception as e:
                print(f"Erro ao processar vencimento {data_venc}: {e}")
                continue
        
        if not opcoes_lista:
            return pd.DataFrame()
        
        df_opcoes = pd.DataFrame(opcoes_lista)
        
        # Ordenar por vencimento e strike
        df_opcoes = df_opcoes.sort_values(["Vencimento", "Strike"])
        
        return df_opcoes
        
    except Exception as e:
        print(f"Erro ao consultar opções para {ticker}: {e}")
        return pd.DataFrame()


def carregar_vendas_opcoes() -> pd.DataFrame:
    """
    Carrega o histórico de vendas de opções do arquivo parquet
    
    Returns:
        DataFrame com vendas registradas
    """
    if ARQ_VENDAS_OPCOES.exists():
        try:
            df = pd.read_parquet(ARQ_VENDAS_OPCOES)
            
            # Garantir tipos corretos
            if not df.empty:
                # Converter data para datetime se necessário
                if "Data Operação" in df.columns:
                    df["Data Operação"] = pd.to_datetime(df["Data Operação"])
                if "Vencimento" in df.columns:
                    df["Vencimento"] = pd.to_datetime(df["Vencimento"])
                
                # Garantir colunas numéricas
                for col in ["Strike", "Prêmio Recebido", "Preço Venda", "Quantidade"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")

                # Migração leve de colunas novas
                if "Deletada Em" not in df.columns:
                    df["Deletada Em"] = pd.NaT
                else:
                    df["Deletada Em"] = pd.to_datetime(df["Deletada Em"], errors="coerce")

                if "Ticker Base" not in df.columns:
                    df["Ticker Base"] = df.get("Ticker").apply(_ticker_curto)
                if "Ticker YF" not in df.columns:
                    df["Ticker YF"] = df.get("Ticker").apply(_ticker_para_yf)
            
            return df
        except Exception as e:
            print(f"Erro ao carregar vendas de opções: {e}")
            return pd.DataFrame()
    else:
        # Criar DataFrame vazio com estrutura
        return pd.DataFrame(columns=[
            "ID",
            "Usuário",
            "Ticker",
            "Ticker Base",
            "Ticker YF",
            "Tipo",  # Call ou Put
            "Strike",
            "Vencimento",
            "Quantidade",
            "Preço Venda",
            "Prêmio Recebido",
            "Data Operação",
            "Status",  # Ativa, Exercida, Expirada
            "Deletada Em",
            "Observações"
        ])


def registrar_venda_opcao(
    usuario: str,
    ticker: str,
    tipo: str,
    strike: float,
    vencimento: str,
    quantidade: int,
    preco_venda: float,
    premio_recebido: float,
    data_operacao: str = None,
    observacoes: str = ""
) -> bool:
    """
    Registra uma nova venda de opção
    
    Args:
        usuario: Nome do usuário
        ticker: Código da ação
        tipo: 'Call' ou 'Put'
        strike: Preço de exercício
        vencimento: Data de vencimento (YYYY-MM-DD)
        quantidade: Número de contratos vendidos
        preco_venda: Preço de venda por contrato
        premio_recebido: Valor total do prêmio recebido
        data_operacao: Data da operação (default: hoje)
        observacoes: Notas adicionais
    
    Returns:
        True se registrado com sucesso
    """
    try:
        # Carregar vendas existentes
        df_vendas = carregar_vendas_opcoes()
        
        # Data da operação
        if data_operacao is None:
            data_operacao = datetime.now().strftime("%Y-%m-%d")
        
        # Gerar ID único
        if df_vendas.empty:
            novo_id = 1
        else:
            novo_id = int(df_vendas["ID"].max()) + 1 if "ID" in df_vendas.columns else 1
        
        # Criar nova entrada
        ticker_base = _ticker_curto(ticker) or str(ticker).strip()
        ticker_yf = _ticker_para_yf(ticker_base)

        nova_venda = pd.DataFrame([{
            "ID": novo_id,
            "Usuário": usuario,
            "Ticker": ticker_base,
            "Ticker Base": ticker_base,
            "Ticker YF": ticker_yf,
            "Tipo": tipo,
            "Strike": float(strike),
            "Vencimento": pd.to_datetime(vencimento),
            "Quantidade": int(quantidade),
            "Preço Venda": float(preco_venda),
            "Prêmio Recebido": float(premio_recebido),
            "Data Operação": pd.to_datetime(data_operacao),
            "Status": "Ativa",
            "Deletada Em": pd.NaT,
            "Observações": observacoes
        }])
        
        # Adicionar ao DataFrame
        if df_vendas.empty:
            df_vendas = nova_venda
        else:
            df_vendas = pd.concat([df_vendas, nova_venda], ignore_index=True)
        
        # Salvar
        df_vendas.to_parquet(ARQ_VENDAS_OPCOES, index=False)
        
        return True
        
    except Exception as e:
        print(f"Erro ao registrar venda de opção: {e}")
        return False


def atualizar_status_opcao(id_opcao: int, novo_status: str) -> bool:
    """
    Atualiza o status de uma opção (Ativa, Exercida, Expirada)
    
    Args:
        id_opcao: ID da opção
        novo_status: Novo status ('Ativa', 'Exercida', 'Expirada')
    
    Returns:
        True se atualizado com sucesso
    """
    try:
        df_vendas = carregar_vendas_opcoes()
        
        if df_vendas.empty or id_opcao not in df_vendas["ID"].values:
            return False
        
        # Atualizar status
        df_vendas.loc[df_vendas["ID"] == id_opcao, "Status"] = novo_status
        if novo_status == "Deletada":
            if "Deletada Em" not in df_vendas.columns:
                df_vendas["Deletada Em"] = pd.NaT
            df_vendas.loc[df_vendas["ID"] == id_opcao, "Deletada Em"] = pd.Timestamp.now()
        
        # Salvar
        df_vendas.to_parquet(ARQ_VENDAS_OPCOES, index=False)
        
        return True
        
    except Exception as e:
        print(f"Erro ao atualizar status: {e}")
        return False


def opcoes_para_dividendos_sinteticos(df_vendas: pd.DataFrame = None) -> pd.DataFrame:
    """
    Converte vendas de opções em formato de dividendos sintéticos
    para integração com o sistema de dividendos existente
    
    Args:
        df_vendas: DataFrame de vendas (se None, carrega do arquivo)
    
    Returns:
        DataFrame no formato de dividendos com colunas:
        Usuário, Ativo, Data, Tipo, Valor, Observações
    """
    if df_vendas is None:
        df_vendas = carregar_vendas_opcoes()
    
    if df_vendas.empty:
        return pd.DataFrame(columns=[
            "Usuário",
            "Ativo",
            "Data",
            "Tipo",
            "Valor Bruto",
            "Impostos",
            "Valor Líquido",
            "Observações",
        ])

    # Excluir registros deletados (soft delete)
    if "Status" in df_vendas.columns:
        df_vendas = df_vendas[df_vendas["Status"] != "Deletada"].copy()
    if df_vendas.empty:
        return pd.DataFrame(columns=[
            "Usuário",
            "Ativo",
            "Data",
            "Tipo",
            "Valor Bruto",
            "Impostos",
            "Valor Líquido",
            "Observações",
        ])
    
    # Converter para formato de dividendos
    df_divs_sinteticos = []
    
    for _, venda in df_vendas.iterrows():
        ativo_base = _ticker_curto(venda.get("Ticker Base") or venda.get("Ticker"))
        if not ativo_base:
            ativo_base = venda.get("Ticker")

        premio = float(pd.to_numeric(venda.get("Prêmio Recebido"), errors="coerce") or 0)
        if premio <= 0:
            continue

        df_divs_sinteticos.append({
            "Usuário": venda["Usuário"],
            "Ativo": ativo_base,
            "Data": venda["Data Operação"],
            "Tipo": f"Dividendo Sintético ({venda['Tipo']})",
            "Valor Bruto": premio,
            "Impostos": 0.0,
            "Valor Líquido": premio,
            "Observações": f"Opção {venda['Tipo']} - Strike R$ {float(pd.to_numeric(venda.get('Strike'), errors='coerce') or 0):.2f} - Venc: {pd.to_datetime(venda.get('Vencimento'), errors='coerce').strftime('%d/%m/%Y') if pd.notna(pd.to_datetime(venda.get('Vencimento'), errors='coerce')) else venda.get('Vencimento')}"
        })
    
    return pd.DataFrame(df_divs_sinteticos)


def filtrar_opcoes(
    df_opcoes: pd.DataFrame,
    distancia_min: float = None,
    distancia_max: float = None,
    vencimentos: list = None,
    meses_vencimento: list = None
) -> pd.DataFrame:
    """
    Filtra opções por critérios
    
    Args:
        df_opcoes: DataFrame de opções
        distancia_min: Distância mínima do strike (%)
        distancia_max: Distância máxima do strike (%)
        vencimentos: Lista de datas de vencimento permitidas
    
    Returns:
        DataFrame filtrado
    """
    if df_opcoes.empty:
        return df_opcoes
    
    df_filtrado = df_opcoes.copy()
    
    # Filtrar por distância
    if distancia_min is not None:
        df_filtrado = df_filtrado[df_filtrado["Distância %"] >= distancia_min]
    
    if distancia_max is not None:
        df_filtrado = df_filtrado[df_filtrado["Distância %"] <= distancia_max]
    
    # Filtrar por vencimentos
    if vencimentos:
        df_filtrado = df_filtrado[df_filtrado["Vencimento"].isin(vencimentos)]

    # Filtrar por mês/ano de vencimento
    if meses_vencimento and "Mês Vencimento" in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado["Mês Vencimento"].isin(meses_vencimento)]
    
    return df_filtrado


def exportar_vendas_para_excel(df_vendas: pd.DataFrame = None, caminho: str = None) -> str:
    """
    Exporta vendas de opções para Excel
    
    Args:
        df_vendas: DataFrame de vendas (se None, carrega do arquivo)
        caminho: Caminho do arquivo (se None, usa padrão)
    
    Returns:
        Caminho do arquivo gerado
    """
    if df_vendas is None:
        df_vendas = carregar_vendas_opcoes()
    
    if caminho is None:
        caminho = PASTA_DADOS / f"vendas_opcoes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    try:
        df_vendas.to_excel(caminho, index=False)
        return str(caminho)
    except Exception as e:
        print(f"Erro ao exportar para Excel: {e}")
        return None


def calcular_estatisticas_opcoes(df_vendas: pd.DataFrame = None) -> dict:
    """
    Calcula estatísticas sobre as vendas de opções
    
    Args:
        df_vendas: DataFrame de vendas (se None, carrega do arquivo)
    
    Returns:
        Dicionário com estatísticas
    """
    if df_vendas is None:
        df_vendas = carregar_vendas_opcoes()
    
    if df_vendas.empty:
        return {
            "total_vendas": 0,
            "premio_total": 0,
            "premio_medio": 0,
            "opcoes_ativas": 0,
            "opcoes_exercidas": 0,
            "opcoes_expiradas": 0,
        }

    # Por padrão, ignorar deletadas
    if "Status" in df_vendas.columns:
        df_base = df_vendas[df_vendas["Status"] != "Deletada"].copy()
    else:
        df_base = df_vendas.copy()
    
    return {
        "total_vendas": len(df_base),
        "premio_total": pd.to_numeric(df_base.get("Prêmio Recebido"), errors="coerce").fillna(0).sum(),
        "premio_medio": pd.to_numeric(df_base.get("Prêmio Recebido"), errors="coerce").fillna(0).mean() if len(df_base) else 0,
        "opcoes_ativas": len(df_base[df_base.get("Status") == "Ativa"]) if "Status" in df_base.columns else 0,
        "opcoes_exercidas": len(df_base[df_base.get("Status") == "Exercida"]) if "Status" in df_base.columns else 0,
        "opcoes_expiradas": len(df_base[df_base.get("Status") == "Expirada"]) if "Status" in df_base.columns else 0,
    }
