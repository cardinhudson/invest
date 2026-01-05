"""
Módulo para visualização de dados extraídos dos PDFs da Avenue.
Fornece funções para exibir as abas:
- Ações Avenue
- Proventos Avenue (Dividendos)
- Dividendo Consolidado
"""

import os
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io

from modules.upload_pdf_avenue import (
    extrair_acoes_pdf,
    extrair_dividendos_pdf,
    processar_pasta_pdfs,
    ACOES_PDF_PATH,
    DIVIDENDOS_PDF_PATH
)
from modules.upload_relatorio import ACOES_PATH, PROVENTOS_PATH
from modules.cotacoes import (
    obter_cotacao_mes, 
    converter_usd_para_brl, 
    converter_brl_para_usd, 
    formatar_valor_moeda,
    obter_historico_cotacao_usd_brl,
    obter_cotacao_atual_usd_brl,
    obter_historico_indice,
    obter_historico_acao
)

from modules.ticker_info import CACHE_PATH as TICKER_INFO_PATH


@st.cache_data(show_spinner=False)
def _read_ticker_info_cached(path: str, mtime: float) -> pd.DataFrame:
    return pd.read_parquet(path)


@st.cache_data(show_spinner=False)
def _read_parquet_cached(path: str, mtime: float) -> pd.DataFrame:
    return pd.read_parquet(path)


def extrair_ticker_curto(valor):
    """Extrai ticker curto de rótulos longos como 'AAPL - Apple'."""
    if pd.isna(valor):
        return None
    texto = str(valor).strip()
    if not texto:
        return None
    if " - " in texto:
        return texto.split(" - ", 1)[0].strip()
    return texto.split()[0].strip()


def carregar_acoes_avenue() -> pd.DataFrame:
    """
    Carrega dados de ações extraídas dos PDFs Avenue.
    Procura por parquets salvos ou retorna DataFrame vazio.
    """
    if os.path.exists(ACOES_PDF_PATH):
        try:
            mtime = os.path.getmtime(ACOES_PDF_PATH)
            return _read_parquet_cached(ACOES_PDF_PATH, mtime)
        except Exception as e:
            st.warning(f"Erro ao carregar ações Avenue: {e}")
            return pd.DataFrame()
    
    return pd.DataFrame()


def carregar_dividendos_avenue() -> pd.DataFrame:
    """
    Carrega dados de dividendos extraídos dos PDFs Avenue.
    """
    if os.path.exists(DIVIDENDOS_PDF_PATH):
        try:
            mtime = os.path.getmtime(DIVIDENDOS_PDF_PATH)
            return _read_parquet_cached(DIVIDENDOS_PDF_PATH, mtime)
        except Exception as e:
            st.warning(f"Erro ao carregar dividendos Avenue: {e}")
            return pd.DataFrame()
    
    return pd.DataFrame()


def padronizar_acoes_avenue(df: pd.DataFrame) -> pd.DataFrame:
    """
    Padroniza as colunas de ações extraídas conforme especificação do PDF.
    
    Estrutura padronizada:
    - Ativo: Nome do produto
    - Ticker: Código de negociação
    - Quantidade: Quantidade disponível
    - Preço: Preço de fechamento
    - Valor de Mercado: Valor total da posição
    """
    if df.empty:
        return df
    
    df_padrao = df.copy()
    
    # Mapear colunas para padrão especificado
    colunas_mapeadas = {
        "Produto": "Ativo",
        "Ticker": "Ticker",
        "Quantidade Disponível": "Quantidade",
        "Preço de Fechamento": "Preço",
        "Valor": "Valor de Mercado"
    }
    
    # Renomear colunas que existem
    df_padrao = df_padrao.rename(columns={k: v for k, v in colunas_mapeadas.items() if k in df_padrao.columns})
    
    # Adicionar colunas de metadados se existirem
    colunas_mantidas = [col for col in ["Ativo", "Ticker", "Quantidade", "Preço", "Valor de Mercado", "Mês/Ano", "Usuário"] 
                        if col in df_padrao.columns]
    
    return df_padrao[colunas_mantidas] if colunas_mantidas else df_padrao


def padronizar_dividendos_avenue(df: pd.DataFrame) -> pd.DataFrame:
    """
    Padroniza os dividendos extraídos dos PDFs Avenue.
    
    Suporta 2 formatos:
    1. Novo (v3): Data Comex, Ticker, Valor Bruto, Imposto, Valor Líquido, Usuário
    2. Antigo: Data de Pagamento, Tipo de Provento, Valor Líquido, Usuário
    
    Padroniza para:
    - Data, Ativo, Valor Bruto, Impostos, Valor Líquido, Fonte
    """
    if df.empty:
        return df
    
    df_padrao = df.copy()
    
    # ===== DETECÇÃO DE FORMATO =====
    # Novo formato (v3) detectado pela presença de "Data Comex" e "Ticker"
    eh_novo_formato = "Data Comex" in df_padrao.columns and "Ticker" in df_padrao.columns
    
    # ===== NOVO FORMATO (v3) =====
    if eh_novo_formato:
        # Renomear colunas do novo formato
        colunas_renomear = {
            "Data Comex": "Data",
            "Ticker": "Ativo",
            "Imposto": "Impostos",  # Singularizar
        }
        df_padrao = df_padrao.rename(columns={k: v for k, v in colunas_renomear.items() if k in df_padrao.columns})
        
        # Converter data se necessário
        if "Data" in df_padrao.columns and df_padrao["Data"].dtype == "object":
            df_padrao["Data"] = pd.to_datetime(df_padrao["Data"], format="%d/%m/%Y", errors="coerce")
        
        # Garantir que Impostos seja positivo (será multiplicado por -1 para exibição)
        if "Impostos" in df_padrao.columns:
            df_padrao["Impostos"] = pd.to_numeric(df_padrao["Impostos"], errors="coerce")
            df_padrao["Impostos"] = df_padrao["Impostos"].abs()  # Garantir positivo
        
        # Valores já estão corretos: Valor Bruto, Impostos, Valor Líquido
        if "Valor Bruto" in df_padrao.columns:
            df_padrao["Valor Bruto"] = pd.to_numeric(df_padrao["Valor Bruto"], errors="coerce")
        
        if "Valor Líquido" in df_padrao.columns:
            df_padrao["Valor Líquido"] = pd.to_numeric(df_padrao["Valor Líquido"], errors="coerce")
        
        # Fonte/Usuário
        if "Usuário" not in df_padrao.columns:
            df_padrao["Usuário"] = "Avenue"
        
        df_padrao["Fonte"] = df_padrao.get("Usuário", "Avenue")
    
    # ===== FORMATO ANTIGO =====
    else:
        # Renomear colunas principais
        if "Data de Pagamento" in df_padrao.columns:
            df_padrao["Data"] = pd.to_datetime(df_padrao["Data de Pagamento"], format="%d/%m/%Y", errors="coerce")
        
        # Ativo (usa ticker/produto extraído)
        if "Produto" in df_padrao.columns:
            df_padrao["Ativo"] = df_padrao["Produto"]
        elif "Ticker" in df_padrao.columns:
            df_padrao["Ativo"] = df_padrao["Ticker"]
        else:
            df_padrao["Ativo"] = "N/A"
        
        # Valores
        if "Valor Líquido" in df_padrao.columns:
            df_padrao["Valor Líquido"] = pd.to_numeric(df_padrao["Valor Líquido"], errors="coerce")
        
        # Separar créditos de retenções
        df_padrao["eh_retencao"] = df_padrao.get("Tipo de Provento", "").astype(str).str.contains("Retenção", case=False, na=False)
        
        df_padrao["Valor Bruto"] = 0.0
        df_padrao["Impostos"] = 0.0
        
        # Agrupar por Ativo, Data e Usuário para consolidar créditos com retenções
        for (ativo, data, usuario), grupo in df_padrao.groupby(["Ativo", "Data", "Usuário"], dropna=False):
            grupo_indices = grupo.index
            
            # Somar créditos (não-retenção) = Valor Bruto
            creditos = grupo[~grupo["eh_retencao"]]["Valor Líquido"].sum()
            
            # Somar retenções = Impostos (como valor negativo)
            retencoes = grupo[grupo["eh_retencao"]]["Valor Líquido"].sum()
            
            # Atualizar valores
            df_padrao.loc[grupo_indices, "Valor Bruto"] = creditos
            df_padrao.loc[grupo_indices, "Impostos"] = abs(retencoes) if retencoes > 0 else 0.0
        
        # Calcular Valor Líquido = Valor Bruto - Impostos
        df_padrao["Valor Líquido"] = df_padrao["Valor Bruto"] - df_padrao["Impostos"]
        
        # Remover linhas duplicadas
        df_padrao = df_padrao.drop_duplicates(subset=["Ativo", "Data", "Usuário"], keep="first")
        
        # Fonte
        if "Usuário" in df_padrao.columns:
            df_padrao["Fonte"] = df_padrao["Usuário"]
        else:
            df_padrao["Fonte"] = "Avenue"
    
    # Selecionar apenas colunas finais
    colunas_finais = ["Data", "Ativo", "Valor Bruto", "Impostos", "Valor Líquido", "Fonte", "Usuário", "Mês/Ano"]

    return df_padrao[[col for col in colunas_finais if col in df_padrao.columns]]


def carregar_proventos_gerais() -> pd.DataFrame:
    """
    Carrega dados de proventos gerais (não Avenue).
    """
    from modules.upload_relatorio import PROVENTOS_PATH, padronizar_dividendos
    import os
    import pandas as pd
    if os.path.exists(PROVENTOS_PATH):
        try:
            df = pd.read_parquet(PROVENTOS_PATH)
            df_padrao = padronizar_dividendos(df)
            # Garantir que Data é Timestamp
            if "Data" in df_padrao.columns:
                df_padrao["Data"] = pd.to_datetime(df_padrao["Data"], errors="coerce")
            return df_padrao
        except Exception as e:
            return pd.DataFrame()
    return pd.DataFrame()


def exibir_grafico_historico_cotacao(key_prefix=""): 
    """
    Exibe gráfico interativo do histórico de cotações com opções de comparação.
    Permite selecionar índices (USD/BRL, EUR/BRL, IBOV, SELIC) e comparar com ações Avenue.
    key_prefix: string única para evitar conflito de chave no Streamlit.
    """
    st.markdown("---")
    st.subheader("📊 Histórico de Cotação e Comparação de Índices")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        indice_principal = st.selectbox(
            "Índice Principal",
            ["USD/BRL", "EUR/BRL", "IBOV", "SELIC"],
            key=f"{key_prefix}_indice_principal"
        )
    
    with col2:
        tipo_grafico = st.selectbox(
            "Tipo de Gráfico",
            ["Diário", "Semanal", "Mensal"],
            key=f"{key_prefix}_tipo_grafico_cotacao"
        )
    
    with col3:
        periodo_opcoes = {
            "1 Ano": "1y",
            "2 Anos": "2y",
            "5 Anos": "5y",
            "10 Anos": "10y",
            "Máximo": "max"
        }
        periodo_sel = st.selectbox(
            "Período",
            list(periodo_opcoes.keys()),
            index=3,  # 10 Anos por padrão
            key=f"{key_prefix}_periodo_grafico_cotacao"
        )
    
    with col4:
        mostrar_media = st.checkbox(
            "Mostrar Média Móvel (30)",
            value=False,
            key=f"{key_prefix}_media_movel_cotacao"
        )
    
    # Opções de comparação
    st.markdown("##### Comparar com:")
    
    # Aviso sobre SELIC
    if "SELIC" in ([indice_principal] + comparar_indices if 'comparar_indices' in locals() else [indice_principal]):
        st.info("ℹ️ **SELIC**: Representado por ETF de renda fixa brasileira (IMA-B). Valores mostram rendimento acumulado calculado.")
    
    col_comp1, col_comp2 = st.columns(2)
    
    with col_comp1:
        comparar_indices = st.multiselect(
            "Outros Índices",
            [idx for idx in ["USD/BRL", "EUR/BRL", "IBOV", "SELIC"] if idx != indice_principal],
            key=f"{key_prefix}_comparar_indices"
        )
    
    with col_comp2:
        # Carregar ações Avenue disponíveis
        df_acoes_avenue = carregar_acoes_avenue()
        acoes_disponiveis = []
        if not df_acoes_avenue.empty and "Ticker" in df_acoes_avenue.columns:
            acoes_disponiveis = sorted(df_acoes_avenue["Ticker"].dropna().unique().tolist())
        
        acoes_selecionadas = st.multiselect(
            "Ações Avenue (US)",
            acoes_disponiveis,
            key=f"{key_prefix}_acoes_comparar"
        )
    
    # Mapear tipo de gráfico para intervalo yfinance
    intervalo_map = {
        "Diário": "1d",
        "Semanal": "1wk",
        "Mensal": "1mo"
    }
    
    intervalo = intervalo_map.get(tipo_grafico, "1d")
    periodo = periodo_opcoes.get(periodo_sel, "10y")
    
    # Obter dados do índice principal
    if indice_principal == "USD/BRL":
        df_principal = obter_historico_cotacao_usd_brl(periodo=periodo, intervalo=intervalo)
    else:
        df_principal = obter_historico_indice(indice_principal, periodo=periodo, intervalo=intervalo)
    
    if df_principal.empty:
        st.warning(f"⚠️ Não foi possível obter dados históricos de {indice_principal}.")
    if df_principal.empty:
        st.warning(f"⚠️ Não foi possível obter dados históricos de {indice_principal}.")
        return
    
    # SEMPRE normalizar dados para comparação (base 100) - garante escalas comparáveis
    df_principal_norm = df_principal.copy()
    valor_inicial = df_principal_norm["Close"].iloc[0]
    df_principal_norm["Normalized"] = (df_principal_norm["Close"] / valor_inicial) * 100
    
    fig = px.line(
        df_principal_norm,
        x="Date",
        y="Normalized",
        title=f"Comparação de Índices e Ações - {tipo_grafico} ({periodo_sel})",
        labels={"Date": "Data", "Normalized": "Índice (Base 100)"}
    )
    fig.data[0].name = indice_principal
    fig.data[0].showlegend = True
    
    # Adicionar outros índices para comparação
    for indice in comparar_indices:
        df_indice = obter_historico_indice(indice, periodo=periodo, intervalo=intervalo)
        if not df_indice.empty:
            valor_inicial_idx = df_indice["Close"].iloc[0]
            df_indice["Normalized"] = (df_indice["Close"] / valor_inicial_idx) * 100
            fig.add_scatter(
                x=df_indice["Date"],
                y=df_indice["Normalized"],
                mode="lines",
                name=indice
            )
    
    # Adicionar ações selecionadas
    for acao in acoes_selecionadas:
        df_acao = obter_historico_acao(acao, periodo=periodo, intervalo=intervalo)
        if not df_acao.empty:
            valor_inicial_acao = df_acao["Close"].iloc[0]
            df_acao["Normalized"] = (df_acao["Close"] / valor_inicial_acao) * 100
            fig.add_scatter(
                x=df_acao["Date"],
                y=df_acao["Normalized"],
                mode="lines",
                name=f"{acao} (US)"
            )
    
    # Adicionar média móvel se solicitado
    if mostrar_media and len(df_principal_norm) > 30:
        df_principal_norm["MA30"] = df_principal_norm["Normalized"].rolling(window=30).mean()
        fig.add_scatter(
            x=df_principal_norm["Date"],
            y=df_principal_norm["MA30"],
            mode="lines",
            name=f"{indice_principal} - MA30",
            line=dict(dash="dash", color="orange")
        )
    
    # Configurar layout
    fig.update_layout(
        yaxis_title="Índice (Base 100 = início do período)",
        hovermode="x unified",
        showlegend=True,
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
    )
    
    st.plotly_chart(fig, use_container_width=True, key=f"grafico_historico_cotacao_{key_prefix}")
    
    # Estatísticas comparativas para todos os ativos/índices (igual ao gráfico de baixo)
    st.markdown(f"#### 📈 Estatísticas Comparativas (Base 100)")
    todos_ativos = [indice_principal] + comparar_indices + acoes_selecionadas
    num_cols = min(4, len(todos_ativos))
    cols_stat = st.columns(num_cols)
    for idx, ativo in enumerate(todos_ativos[:num_cols*2]):  # Mostrar até 8 ativos
        col_idx = idx % num_cols
        with cols_stat[col_idx]:
            try:
                if ativo == indice_principal:
                    df_stat = df_principal
                elif ativo in comparar_indices:
                    df_stat = obter_historico_indice(ativo, periodo=periodo, intervalo=intervalo)
                elif ativo in acoes_selecionadas:
                    df_stat = obter_historico_acao(ativo, periodo=periodo, intervalo=intervalo)
                else:
                    continue
                if not df_stat.empty and "Close" in df_stat.columns:
                    df_stat = df_stat.dropna(subset=["Close"])
                    if not df_stat.empty and len(df_stat) > 0:
                        valor_stat = df_stat["Close"].iloc[-1]
                        valor_inicial_stat = df_stat["Close"].iloc[0]
                        if pd.notna(valor_stat) and pd.notna(valor_inicial_stat) and valor_inicial_stat != 0:
                            variacao_stat = ((valor_stat - valor_inicial_stat) / valor_inicial_stat) * 100
                            # Para índices de câmbio, usar formato apropriado
                            if ativo in ["USD/BRL", "EUR/BRL"]:
                                st.metric(
                                    ativo,
                                    f"{valor_stat:.4f}",
                                    f"{variacao_stat:+.1f}%"
                                )
                            elif ativo in ["IBOV", "SELIC"]:
                                st.metric(
                                    ativo,
                                    f"{valor_stat:.2f}",
                                    f"{variacao_stat:+.1f}%"
                                )
                            else:
                                st.metric(
                                    ativo,
                                    f"{valor_stat:.2f}",
                                    f"{variacao_stat:+.1f}%"
                                )
                        else:
                            st.warning(f"{ativo}: Dados inválidos")
            except Exception as e:
                st.warning(f"Erro ao processar {ativo}")
        # Quebra de linha a cada 4 colunas
        if (idx + 1) % num_cols == 0 and idx < len(todos_ativos) - 1:
            cols_stat = st.columns(num_cols)
    
    # ========== GRÁFICO DE CONVERSÃO DE MOEDA ==========
    st.markdown("---")
    st.subheader("💱 Análise Comparativa em Mesma Moeda")
    
    col_moeda1, col_moeda2 = st.columns(2)
    
    with col_moeda1:
        moeda_conversao = st.selectbox(
            "Converter tudo para:",
            ["BRL (Real Brasileiro)", "USD (Dólar)"],
            key=f"{key_prefix}_moeda_conversao"
        )
    
    with col_moeda2:
        st.info("💡 Todos os índices e ações serão convertidos para a mesma moeda para comparação")
    
    # Determinar moeda alvo
    moeda_alvo = "BRL" if "BRL" in moeda_conversao else "USD"
    
    # Obter cotação histórica USD/BRL para conversão
    df_cotacao_usd_brl = obter_historico_cotacao_usd_brl(periodo=periodo, intervalo=intervalo)
    
    # Criar figura de conversão
    fig_moeda = px.line(
        title=f"Comparação de Índices e Ações em {moeda_alvo} (base 100) - {tipo_grafico} ({periodo_sel})",
        labels={"Date": "Data", "Valor": f"Índice (base 100) em {moeda_alvo}"}
    )

    def normalizar_base_100(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or "Close" not in df.columns:
            return df
        df_n = df.copy()
        df_n["Close"] = pd.to_numeric(df_n["Close"], errors="coerce")
        df_n = df_n.dropna(subset=["Close"])
        if df_n.empty:
            return df_n
        base = df_n["Close"].iloc[0]
        if pd.isna(base) or base == 0:
            return df_n
        df_n["Close"] = (df_n["Close"] / base) * 100
        return df_n
    
    # Função para converter dados
    def converter_dados_para_moeda(df, moeda_origem, moeda_alvo):
        """Converte dados para a moeda alvo usando cotação histórica"""
        if df.empty or "Date" not in df.columns or "Close" not in df.columns:
            return df
        
        df_convertido = df.copy()

        if moeda_origem == moeda_alvo:
            return df_convertido

        if df_cotacao_usd_brl.empty or "Date" not in df_cotacao_usd_brl.columns or "Close" not in df_cotacao_usd_brl.columns:
            return df_convertido

        # Padronizar Date (tz-naive) e ordenar para merge_asof
        df_convertido["Date"] = pd.to_datetime(df_convertido["Date"], errors="coerce", utc=True).dt.tz_convert(None)
        df_convertido["Close"] = pd.to_numeric(df_convertido["Close"], errors="coerce")
        df_convertido = df_convertido.dropna(subset=["Date", "Close"]).sort_values("Date")
        if df_convertido.empty:
            return df_convertido

        df_cotacao_temp = df_cotacao_usd_brl[["Date", "Close"]].copy()
        df_cotacao_temp["Date"] = pd.to_datetime(df_cotacao_temp["Date"], errors="coerce", utc=True).dt.tz_convert(None)
        df_cotacao_temp["Cotacao_USD_BRL"] = pd.to_numeric(df_cotacao_temp["Close"], errors="coerce")
        df_cotacao_temp = df_cotacao_temp.dropna(subset=["Date", "Cotacao_USD_BRL"]).sort_values("Date")
        if df_cotacao_temp.empty:
            return df_convertido

        # Alinhar por "última cotação conhecida" (evita buracos por feriados/calendários diferentes)
        df_convertido = pd.merge_asof(
            df_convertido,
            df_cotacao_temp[["Date", "Cotacao_USD_BRL"]],
            on="Date",
            direction="backward",
        )

        # Garantir cotação preenchida no começo da série também
        df_convertido["Cotacao_USD_BRL"] = df_convertido["Cotacao_USD_BRL"].ffill().bfill()

        # Converter
        if moeda_origem == "USD" and moeda_alvo == "BRL":
            df_convertido["Close"] = df_convertido["Close"] * df_convertido["Cotacao_USD_BRL"]
        elif moeda_origem == "BRL" and moeda_alvo == "USD":
            df_convertido.loc[df_convertido["Cotacao_USD_BRL"] <= 0, "Cotacao_USD_BRL"] = pd.NA
            df_convertido["Close"] = df_convertido["Close"] / df_convertido["Cotacao_USD_BRL"]

        df_convertido = df_convertido.drop(columns=["Cotacao_USD_BRL"], errors="ignore")
        df_convertido = df_convertido.dropna(subset=["Close"])
        return df_convertido
    
    # Adicionar índice principal convertido
    if indice_principal in ["USD/BRL", "EUR/BRL"]:
        # Taxas de câmbio não são convertíveis da mesma forma
        # Para USD/BRL em USD, seria sempre 1/cotacao, o que não faz sentido
        # Vamos mostrar como está
        df_principal_conv = df_principal.copy()
        nome_moeda = indice_principal
    elif indice_principal == "IBOV":
        # IBOV está em BRL
        df_principal_conv = converter_dados_para_moeda(df_principal, "BRL", moeda_alvo)
        nome_moeda = indice_principal
    elif indice_principal == "SELIC":
        # SELIC está em BRL (BRCR11)
        df_principal_conv = converter_dados_para_moeda(df_principal, "BRL", moeda_alvo)
        nome_moeda = indice_principal
    else:
        df_principal_conv = df_principal.copy()
        nome_moeda = indice_principal
    
    df_principal_plot = normalizar_base_100(df_principal_conv)
    if not df_principal_plot.empty and "Close" in df_principal_plot.columns:
        fig_moeda.add_scatter(
            x=df_principal_plot["Date"],
            y=df_principal_plot["Close"],
            mode="lines",
            name=nome_moeda
        )
    
    # Adicionar índices comparativos convertidos
    for indice in comparar_indices:
        df_ind = obter_historico_indice(indice, periodo=periodo, intervalo=intervalo)
        if not df_ind.empty:
            # Determinar moeda origem do índice e converter
            if indice in ["USD/BRL", "EUR/BRL"]:
                # Taxas de câmbio - mostrar como está
                df_ind_conv = df_ind.copy()
            elif indice in ["IBOV", "SELIC"]:
                # Índices brasileiros estão em BRL
                df_ind_conv = converter_dados_para_moeda(df_ind, "BRL", moeda_alvo)
            else:
                df_ind_conv = df_ind.copy()
            
            if not df_ind_conv.empty and "Close" in df_ind_conv.columns:
                # Remover valores NaN antes de plotar
                df_ind_conv = df_ind_conv.dropna(subset=["Close"])
                if not df_ind_conv.empty:
                    df_ind_plot = normalizar_base_100(df_ind_conv)
                    fig_moeda.add_scatter(
                        x=df_ind_plot["Date"],
                        y=df_ind_plot["Close"],
                        mode="lines",
                        name=indice
                    )
    
    # Adicionar ações convertidas
    for acao in acoes_selecionadas:
        df_acao = obter_historico_acao(acao, periodo=periodo, intervalo=intervalo)
        if not df_acao.empty:
            # Ações US estão em USD, converter para BRL se necessário
            df_acao_conv = converter_dados_para_moeda(df_acao, "USD", moeda_alvo)
            
            if not df_acao_conv.empty and "Close" in df_acao_conv.columns:
                # Remover valores NaN
                df_acao_conv = df_acao_conv.dropna(subset=["Close"])
                if not df_acao_conv.empty:
                    df_acao_plot = normalizar_base_100(df_acao_conv)
                    fig_moeda.add_scatter(
                        x=df_acao_plot["Date"],
                        y=df_acao_plot["Close"],
                        mode="lines",
                        name=f"{acao} ({moeda_alvo})"
                    )
    
    # Configurar layout do gráfico de moeda
    fig_moeda.update_layout(
        hovermode="x unified",
        showlegend=True,
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
        yaxis_title=f"Índice (base 100) em {moeda_alvo}"
    )
    
    st.plotly_chart(fig_moeda, use_container_width=True, key=f"grafico_moeda_cotacao_{key_prefix}")
    
    # Estatísticas do período convertidas
    st.markdown(f"#### 📊 Estatísticas em {moeda_alvo}")
    
    # Criar colunas para cada ativo selecionado
    todos_ativos = [indice_principal] + comparar_indices + acoes_selecionadas
    
    # Limitar a 4 colunas por linha
    num_cols = min(4, len(todos_ativos))
    cols_stat = st.columns(num_cols)
    
    for idx, ativo in enumerate(todos_ativos[:num_cols*2]):  # Mostrar até 8 ativos
        col_idx = idx % num_cols
        with cols_stat[col_idx]:
            try:
                if ativo == indice_principal:
                    df_stat = df_principal_conv
                elif ativo in comparar_indices:
                    df_stat = obter_historico_indice(ativo, periodo=periodo, intervalo=intervalo)
                    # Converter apenas se não for índice de câmbio
                    if ativo in ["IBOV", "SELIC"]:
                        df_stat = converter_dados_para_moeda(df_stat, "BRL", moeda_alvo)
                elif ativo in acoes_selecionadas:
                    df_stat = obter_historico_acao(ativo, periodo=periodo, intervalo=intervalo)
                    df_stat = converter_dados_para_moeda(df_stat, "USD", moeda_alvo)
                else:
                    continue
                
                if not df_stat.empty and "Close" in df_stat.columns:
                    # Remover NaN
                    df_stat = df_stat.dropna(subset=["Close"])
                    
                    if not df_stat.empty and len(df_stat) > 0:
                        valor_stat = df_stat["Close"].iloc[-1]
                        valor_inicial_stat = df_stat["Close"].iloc[0]
                        
                        # Verificar se valores são válidos
                        if pd.notna(valor_stat) and pd.notna(valor_inicial_stat) and valor_inicial_stat != 0:
                            variacao_stat = ((valor_stat - valor_inicial_stat) / valor_inicial_stat) * 100
                            
                            # Para índices de câmbio, usar formato apropriado
                            if ativo in ["USD/BRL", "EUR/BRL"]:
                                st.metric(
                                    ativo,
                                    f"{valor_stat:.4f}",
                                    f"{variacao_stat:+.1f}%"
                                )
                            # Para índices (IBOV/SELIC), não rotular como moeda
                            elif ativo in ["IBOV", "SELIC"]:
                                st.metric(
                                    ativo,
                                    f"{valor_stat:.2f}",
                                    f"{variacao_stat:+.1f}%"
                                )
                            else:
                                st.metric(
                                    ativo,
                                    f"{valor_stat:.2f} {moeda_alvo}",
                                    f"{variacao_stat:+.1f}%"
                                )
                        else:
                            st.warning(f"{ativo}: Dados inválidos")
            except Exception as e:
                st.warning(f"Erro ao processar {ativo}")
        
        # Quebra de linha a cada 4 colunas
        if (idx + 1) % num_cols == 0 and idx < len(todos_ativos) - 1:
            cols_stat = st.columns(num_cols)




def aba_acoes_avenue():
    """
    Aba para visualização de ações extraídas dos PDFs Avenue.
    Inclui conversão de moeda, exibição de cotação e gráfico histórico.
    """
    st.header("📈 Ações Avenue")
    
    # Carregar dados
    df_acoes = carregar_acoes_avenue()
    
    if df_acoes.empty:
        st.info("📭 Nenhuma ação extraída. Faça upload de PDFs na página de Upload.")
        return
    
    # Padronizar
    df_padrao = padronizar_acoes_avenue(df_acoes)
    
    # ========== SELEÇÃO DE MOEDA ==========
    moeda_selecionada = st.radio(
        "💱 Exibir valores em:",
        ["USD (Dólar)", "BRL (Real)"],
        index=1,  # BRL por padrão
        key="avenue_acoes_moeda",
        horizontal=True
    )
    moeda = "BRL" if "BRL" in moeda_selecionada else "USD"
    
    # Obter cotações para exibição posterior
    cotacao_atual = obter_cotacao_atual_usd_brl()
    mes_ano_ref = None
    cotacao_mes = cotacao_atual
    def _ordena_meses(meses):
        def _key(m):
            try:
                mes, ano = m.split("/")
                return int(ano)*100+int(mes)
            except Exception:
                return m
        return sorted(meses, key=_key)

    if "Mês/Ano" in df_padrao.columns:
        meses_disponiveis = _ordena_meses(df_padrao["Mês/Ano"].dropna().unique())
        if meses_disponiveis:
            mes_ano_ref = meses_disponiveis[-1]
            cotacao_mes = obter_cotacao_mes(mes_ano_ref)
    
    # ========== CONVERSÃO DE VALORES ==========
    # Os valores extraídos do PDF Avenue vêm em USD.
    # Para exibir em BRL, convertemos USD->BRL usando a cotação do mês/ano da linha.
    df_visualizacao = df_padrao.copy()

    if "Valor_USD_Original" not in df_visualizacao.columns and "Valor de Mercado" in df_visualizacao.columns:
        df_visualizacao["Valor_USD_Original"] = pd.to_numeric(df_visualizacao["Valor de Mercado"], errors="coerce")
    if "Preco_USD_Original" not in df_visualizacao.columns and "Preço" in df_visualizacao.columns:
        df_visualizacao["Preco_USD_Original"] = pd.to_numeric(df_visualizacao["Preço"], errors="coerce")

    if moeda == "BRL":
        if "Valor_USD_Original" in df_visualizacao.columns:
            if "Mês/Ano" in df_visualizacao.columns:
                df_visualizacao["Valor de Mercado"] = df_visualizacao.apply(
                    lambda row: converter_usd_para_brl(row["Valor_USD_Original"], row["Mês/Ano"]) 
                    if pd.notna(row.get("Mês/Ano")) and pd.notna(row.get("Valor_USD_Original"))
                    else row.get("Valor de Mercado"),
                    axis=1
                )
            else:
                df_visualizacao["Valor de Mercado"] = df_visualizacao["Valor_USD_Original"] * cotacao_atual

        if "Preco_USD_Original" in df_visualizacao.columns:
            if "Mês/Ano" in df_visualizacao.columns:
                df_visualizacao["Preço"] = df_visualizacao.apply(
                    lambda row: converter_usd_para_brl(row["Preco_USD_Original"], row["Mês/Ano"]) 
                    if pd.notna(row.get("Mês/Ano")) and pd.notna(row.get("Preco_USD_Original"))
                    else row.get("Preço"),
                    axis=1
                )
            else:
                df_visualizacao["Preço"] = df_visualizacao["Preco_USD_Original"] * cotacao_atual
    else:
        # USD: mantém os valores originais
        if "Valor_USD_Original" in df_visualizacao.columns:
            df_visualizacao["Valor de Mercado"] = df_visualizacao["Valor_USD_Original"]
        if "Preco_USD_Original" in df_visualizacao.columns:
            df_visualizacao["Preço"] = df_visualizacao["Preco_USD_Original"]
    
    # ========== MÉTRICAS PRINCIPAIS ==========
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.metric("📊 Total de Posições", len(df_visualizacao))
    
    with col2:
        valor_total = df_visualizacao.get("Valor de Mercado", pd.Series()).sum()
        st.metric("💰 Valor Total de Mercado", formatar_valor_moeda(valor_total, moeda))
    
    with col3:
        quantidade_total = df_visualizacao.get("Quantidade", pd.Series()).sum()
        st.metric("📦 Quantidade Total", f"{quantidade_total:,.2f}")
    
    with col4:
        if "Usuário" in df_visualizacao.columns:
            usuarios = df_visualizacao["Usuário"].nunique()
            st.metric("👤 Usuários", usuarios)
        else:
            st.metric("👤 Usuários", 0)
    
    with col5:
        if mes_ano_ref:
            st.metric(f"💱 Cotação ({mes_ano_ref})", f"R$ {cotacao_mes:.2f}")
        else:
            st.metric("💱 Cotação (Ref)", f"R$ {cotacao_mes:.2f}")
    
    with col6:
        st.metric("💹 Cotação (Atual)", f"R$ {cotacao_atual:.2f}")
    
    st.markdown("---")
    
    # ========== FILTROS ==========
    col_f1, col_f2, col_f3 = st.columns(3)
    
    filtro_aplicado = False
    
    with col_f1:
        if "Ticker" in df_visualizacao.columns:
            tickers = sorted(df_visualizacao["Ticker"].unique())
            tickers_sel = st.multiselect(
                "Ticker",
                tickers,
                default=tickers,
                key="avenue_acoes_ticker"
            )
            filtro_aplicado = len(tickers_sel) < len(tickers)
    
    with col_f2:
        if "Usuário" in df_visualizacao.columns:
            usuarios = sorted(df_visualizacao["Usuário"].unique())
            usuarios_sel = st.multiselect(
                "Usuário",
                usuarios,
                default=usuarios,
                key="avenue_acoes_usuario"
            )
            filtro_aplicado = filtro_aplicado or len(usuarios_sel) < len(usuarios)
    
    with col_f3:
        if "Mês/Ano" in df_visualizacao.columns:
            meses = _ordena_meses(df_visualizacao["Mês/Ano"].unique())
            mes_sel = st.selectbox(
                "Mês/Ano",
                meses,
                index=len(meses)-1 if meses else 0,
                key="avenue_acoes_mes"
            )
            # Atualizar cotação do mês selecionado
            if mes_sel:
                cotacao_selecionada = obter_cotacao_mes(mes_sel)
    
    # Aplicar filtros
    df_filtrado = df_visualizacao
    
    if "Ticker" in df_visualizacao.columns and filtro_aplicado:
        if 'tickers_sel' in locals():
            df_filtrado = df_filtrado[df_filtrado["Ticker"].isin(tickers_sel)]
    
    if "Usuário" in df_visualizacao.columns and filtro_aplicado:
        if 'usuarios_sel' in locals():
            df_filtrado = df_filtrado[df_filtrado["Usuário"].isin(usuarios_sel)]
    
    if "Mês/Ano" in df_visualizacao.columns:
        if 'mes_sel' in locals() and mes_sel:
            df_filtrado = df_filtrado[df_filtrado["Mês/Ano"] == mes_sel]
    
    # ========== ORDENAÇÃO ==========
    col_ord1, col_ord2 = st.columns(2)
    
    with col_ord1:
        ordenacao = st.selectbox(
            "Ordenar por",
            ["Valor de Mercado (maior)", "Valor de Mercado (menor)", "Ticker (A-Z)", "Quantidade (maior)"],
            key="avenue_acoes_ordem"
        )
    
    # Aplicar ordenação
    if ordenacao == "Valor de Mercado (maior)":
        df_filtrado = df_filtrado.sort_values("Valor de Mercado", ascending=False)
    elif ordenacao == "Valor de Mercado (menor)":
        df_filtrado = df_filtrado.sort_values("Valor de Mercado", ascending=True)
    elif ordenacao == "Ticker (A-Z)":
        df_filtrado = df_filtrado.sort_values("Ticker", ascending=True)
    elif ordenacao == "Quantidade (maior)":
        df_filtrado = df_filtrado.sort_values("Quantidade", ascending=False)
    
    # Enriquecer com Setor/Segmento via cache local
    try:
        if os.path.exists(TICKER_INFO_PATH) and "Ticker" in df_filtrado.columns:
            cache_mtime = os.path.getmtime(TICKER_INFO_PATH)
            cache_df = _read_ticker_info_cached(TICKER_INFO_PATH, cache_mtime)
            cols_cache = [c for c in ["Ticker", "Setor", "Segmento"] if c in cache_df.columns]
            if cols_cache and "Setor" not in df_filtrado.columns:
                df_filtrado = df_filtrado.merge(cache_df[cols_cache], on="Ticker", how="left")
                df_filtrado["Setor"] = df_filtrado["Setor"].fillna("Ações Dólar")
                df_filtrado["Segmento"] = df_filtrado["Segmento"].fillna("Ações Dólar")
    except Exception:
        pass

    # Remover colunas auxiliares da exibição
    colunas_exibir = [col for col in df_filtrado.columns if not col.endswith("_Original")]
    
    # ========== EXIBIR TABELA ==========
    st.subheader("📊 Posições")
    st.dataframe(df_filtrado[colunas_exibir], use_container_width=True, hide_index=True)
    
    # ========== GRÁFICOS ==========
    st.markdown("---")
    st.subheader("📈 Análise")
    
    col_chart1, col_chart2 = st.columns(2)

    # Filtro Top N
    opcoes_top = ["Top 10", "Top 15", "Top 20", "Top 30", "Todos"]
    col_filtro_top1, col_filtro_top2 = st.columns(2)
    with col_filtro_top1:
        top_sel1 = st.selectbox("Quantidade (Posições)", opcoes_top, index=0, key="avenue_top_posicoes")
        top_n1 = int(top_sel1.split()[1]) if top_sel1 != "Todos" else None
    with col_filtro_top2:
        top_sel2 = st.selectbox("Quantidade (Quantidades)", opcoes_top, index=0, key="avenue_top_quantidades")
        top_n2 = int(top_sel2.split()[1]) if top_sel2 != "Todos" else None

    with col_chart1:
        if "Ticker" in df_filtrado.columns and "Valor de Mercado" in df_filtrado.columns:
            dist_ticker = df_filtrado.groupby("Ticker")["Valor de Mercado"].sum().sort_values(ascending=False)
            if top_n1:
                dist_ticker = dist_ticker.head(top_n1)
            fig = px.bar(
                dist_ticker,
                title=f"Top {top_n1 if top_n1 else 'Todos'} Maiores Posições",
                labels={"value": f"Valor ({moeda})", "index": "Ticker"}
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_chart2:
        if "Ativo" in df_filtrado.columns and "Quantidade" in df_filtrado.columns:
            dist_qtd = df_filtrado.sort_values("Quantidade", ascending=False)
            if top_n2:
                dist_qtd = dist_qtd.head(top_n2)
            dist_qtd = dist_qtd[['Ativo', 'Quantidade']].copy()
            dist_qtd["Ticker"] = dist_qtd["Ativo"].apply(extrair_ticker_curto)
            dist_qtd["Ticker"].fillna(dist_qtd["Ativo"], inplace=True)
            fig = px.bar(dist_qtd, x="Ticker", y="Quantidade", title=f"Top {top_n2 if top_n2 else 'Todos'} Maiores Quantidades")
            fig.update_traces(customdata=dist_qtd["Ativo"], hovertemplate="<b>%{customdata}</b><br>Ticker: %{x}<br>Qtd: %{y:,.2f}<extra></extra>")
            st.plotly_chart(fig, use_container_width=True)


def aba_proventos_avenue():
    """
    Aba para visualização de dividendos extraídos dos PDFs Avenue.
    Inclui conversão de moeda, exibição de cotação e gráfico histórico.
    """
    st.header("🪙 Proventos Avenue")
    
    # Carregar dados
    df_divid = carregar_dividendos_avenue()
    
    if df_divid.empty:
        st.info("📭 Nenhum provento extraído. Faça upload de PDFs na página de Upload.")
        return
    
    # Padronizar (nota: isso cria Valor Bruto/Impostos a partir de heurísticas)
    df_padrao = padronizar_dividendos_avenue(df_divid)
    
    # ========== SELEÇÃO DE MOEDA ==========
    moeda_selecionada = st.radio(
        "💱 Exibir valores em:",
        ["USD (Dólar)", "BRL (Real)"],
        index=1,  # BRL por padrão
        key="avenue_divid_moeda",
        horizontal=True
    )
    moeda = "BRL" if "BRL" in moeda_selecionada else "USD"
    
    # Obter cotações para exibição posterior
    cotacao_atual = obter_cotacao_atual_usd_brl()
    mes_ano_ref = None
    cotacao_mes = cotacao_atual
    def _ordena_meses(meses):
        def _key(m):
            try:
                mes, ano = m.split("/")
                return int(ano)*100+int(mes)
            except Exception:
                return m
        return sorted(meses, key=_key)

    if "Data" in df_padrao.columns and not df_padrao.empty:
        data_mais_recente = df_padrao["Data"].max()
        if pd.notna(data_mais_recente):
            mes_ano_ref = f"{data_mais_recente.month:02d}/{data_mais_recente.year}"
            cotacao_mes = obter_cotacao_mes(mes_ano_ref)
    
    # ========== CONVERSÃO DE VALORES ==========
    # Dividendos do PDF Avenue também vêm em USD.
    df_visualizacao = df_padrao.copy()

    for col_valor in ["Valor Bruto", "Impostos", "Valor Líquido"]:
        if col_valor not in df_visualizacao.columns:
            continue
        col_original = f"{col_valor.replace(' ', '_')}_USD_Original"
        if col_original not in df_visualizacao.columns:
            df_visualizacao[col_original] = pd.to_numeric(df_visualizacao[col_valor], errors="coerce")

    if moeda == "BRL":
        for col_valor in ["Valor Bruto", "Impostos", "Valor Líquido"]:
            col_original = f"{col_valor.replace(' ', '_')}_USD_Original"
            if col_original not in df_visualizacao.columns:
                continue
            if "Data" in df_visualizacao.columns:
                df_visualizacao[col_valor] = df_visualizacao.apply(
                    lambda row: converter_usd_para_brl(
                        row[col_original],
                        f"{row['Data'].month:02d}/{row['Data'].year}"
                    ) if pd.notna(row.get("Data")) and pd.notna(row.get(col_original)) else row.get(col_valor),
                    axis=1
                )
            else:
                df_visualizacao[col_valor] = df_visualizacao[col_original] * cotacao_atual
    else:
        # USD
        for col_valor in ["Valor Bruto", "Impostos", "Valor Líquido"]:
            col_original = f"{col_valor.replace(' ', '_')}_USD_Original"
            if col_original in df_visualizacao.columns:
                df_visualizacao[col_valor] = df_visualizacao[col_original]
    
    # ========== MÉTRICAS PRINCIPAIS ==========
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        total_registros = len(df_visualizacao)
        st.metric("📊 Total de Proventos", total_registros)
    
    with col2:
        valor_bruto_total = df_visualizacao.get("Valor Bruto", pd.Series()).sum()
        st.metric("💰 Valor Bruto Total", formatar_valor_moeda(valor_bruto_total, moeda))
    
    with col3:
        impostos_total = df_visualizacao.get("Impostos", pd.Series()).sum()
        st.metric("🧾 Impostos Totais", formatar_valor_moeda(impostos_total, moeda))
    
    with col4:
        valor_liquido_total = df_visualizacao.get("Valor Líquido", pd.Series()).sum()
        st.metric("💸 Valor Líquido Total", formatar_valor_moeda(valor_liquido_total, moeda))
    
    with col5:
        if mes_ano_ref:
            st.metric(f"💱 Cotação ({mes_ano_ref})", f"R$ {cotacao_mes:.2f}")
        else:
            st.metric("💱 Cotação (Ref)", f"R$ {cotacao_mes:.2f}")
    
    with col6:
        st.metric("💹 Cotação (Atual)", f"R$ {cotacao_atual:.2f}")
    
    st.markdown("---")
    
    # ========== FILTROS ==========
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    
    with col_f1:
        if "Ativo" in df_visualizacao.columns:
            ativos = ["Todos"] + sorted([a for a in df_visualizacao["Ativo"].unique() if pd.notna(a)])
            ativos_sel = st.multiselect(
                "Ativo",
                ativos,
                default=["Todos"],
                key="avenue_divid_ativo"
            )
    
    with col_f2:
        data_range = None
        if "Data" in df_visualizacao.columns:
            data_min = df_visualizacao["Data"].min()
            data_max = df_visualizacao["Data"].max()
            if pd.notna(data_min) and pd.notna(data_max):
                data_range = st.date_input(
                    "Período",
                    value=(data_min.date(), data_max.date()),
                    key="avenue_divid_data"
                )
    
    with col_f3:
        if "Fonte" in df_visualizacao.columns:
            fontes = ["Todos"] + sorted([f for f in df_visualizacao["Fonte"].unique() if pd.notna(f)])
            fontes_sel = st.multiselect(
                "Usuário",
                fontes,
                default=["Todos"],
                key="avenue_divid_fonte"
            )
    
    with col_f4:
        ordenacao = st.selectbox(
            "Ordenar por",
            ["Data (mais recente)", "Data (mais antigo)", "Valor Líquido (maior)", "Valor Líquido (menor)", "Ativo (A-Z)"],
            key="avenue_divid_ordem"
        )
    
    # Aplicar filtros
    df_filtrado = df_visualizacao.copy()
    
    if "Ativo" in df_visualizacao.columns and "Todos" not in ativos_sel:
        df_filtrado = df_filtrado[df_filtrado["Ativo"].isin(ativos_sel)]
    
    if "Data" in df_visualizacao.columns and data_range and len(data_range) == 2:
        df_filtrado = df_filtrado[
            (df_filtrado["Data"].dt.date >= data_range[0]) &
            (df_filtrado["Data"].dt.date <= data_range[1])
        ]
    
    if "Fonte" in df_visualizacao.columns and "Todos" not in fontes_sel:
        df_filtrado = df_filtrado[df_filtrado["Fonte"].isin(fontes_sel)]
    
    # Aplicar ordenação
    if ordenacao == "Data (mais recente)":
        df_filtrado = df_filtrado.sort_values("Data", ascending=False)
    elif ordenacao == "Data (mais antigo)":
        df_filtrado = df_filtrado.sort_values("Data", ascending=True)
    elif ordenacao == "Valor Líquido (maior)":
        df_filtrado = df_filtrado.sort_values("Valor Líquido", ascending=False)
    elif ordenacao == "Valor Líquido (menor)":
        df_filtrado = df_filtrado.sort_values("Valor Líquido", ascending=True)
    elif ordenacao == "Ativo (A-Z)":
        df_filtrado = df_filtrado.sort_values("Ativo", ascending=True)
    
    # Remover colunas auxiliares da exibição
    colunas_exibir = [col for col in df_filtrado.columns if not col.endswith("_Original")]
    
    # ========== FORMATAR PARA EXIBIÇÃO ==========
    # Criar cópia para exibição com impostos negativos
    df_exibicao = df_filtrado[colunas_exibir].copy()
    
    # Garantir que "Impostos" sejam exibidos como negativos (para fins visuais)
    if "Impostos" in df_exibicao.columns:
        df_exibicao["Impostos"] = df_exibicao["Impostos"].apply(
            lambda x: -abs(x) if pd.notna(x) and x != 0 else x
        )
    
    # ========== EXIBIR TABELA ==========
    st.subheader("📊 Proventos")
    st.dataframe(df_exibicao, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # ========== RESUMO POR ATIVO ==========
    st.subheader("📋 Resumo por Ativo")
    if "Ativo" in df_filtrado.columns and not df_filtrado.empty:
        resumo = df_filtrado.groupby("Ativo").agg({
            "Valor Bruto": "sum",
            "Impostos": "sum",
            "Valor Líquido": "sum"
        }).reset_index().sort_values("Valor Líquido", ascending=False)
        
        # Garantir que Impostos sejam negativos na exibição
        if "Impostos" in resumo.columns:
            resumo["Impostos"] = resumo["Impostos"].apply(
                lambda x: -abs(float(x)) if pd.notna(x) and x != 0 else 0.0
            )
        
        # Formatar valores para exibição
        resumo_exibir = resumo.copy()
        for col in ["Valor Bruto", "Impostos", "Valor Líquido"]:
            if col in resumo_exibir.columns:
                resumo_exibir[col] = resumo_exibir[col].apply(lambda x: formatar_valor_moeda(x, moeda))
        
        st.dataframe(resumo_exibir, use_container_width=True, hide_index=True)
    
    # ========== GRÁFICO HISTÓRICO DE COTAÇÃO ==========
    exibir_grafico_historico_cotacao(key_prefix="proventos_avenue")


def aba_dividendo_consolidado():
    """
    Aba para visualização consolidada de dividendos (integra Avenue e outros).
    """
    st.header("💼 Dividendo Consolidado")
    
    # Filtro para fonte dos proventos
    tipo_provento = st.radio(
        "Origem dos Proventos:",
        ["Proventos Avenue", "Proventos Gerais", "Todos"],
        index=0,
        horizontal=True,
        key="consolidado_tipo_provento"
    )

    # Carregar dados
    df_avenue = carregar_dividendos_avenue()
    df_avenue_padrao = padronizar_dividendos_avenue(df_avenue) if not df_avenue.empty else pd.DataFrame()
    df_gerais = carregar_proventos_gerais()

    if tipo_provento == "Proventos Avenue":
        df_consolidado = df_avenue_padrao
    elif tipo_provento == "Proventos Gerais":
        df_consolidado = df_gerais
    else:
        df_consolidado = pd.concat([df_avenue_padrao, df_gerais], ignore_index=True)

    if df_consolidado.empty:
        st.info("📭 Nenhum dividendo disponível. Faça upload de PDFs na página de Upload.")
        return
    
    # Padronizar coluna Data para Timestamp
    if "Data" in df_consolidado.columns:
        df_consolidado["Data"] = pd.to_datetime(df_consolidado["Data"], errors="coerce")
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total de Registros", len(df_consolidado))
    
    with col2:
        valor_bruto_total = df_consolidado.get("Valor Bruto", pd.Series()).sum()
        st.metric("Valor Bruto Total", f"${valor_bruto_total:,.2f}")
    
    with col3:
        impostos_total = df_consolidado.get("Impostos", pd.Series()).sum()
        st.metric("Impostos Totais", f"${impostos_total:,.2f}")
    
    with col4:
        valor_liquido_total = df_consolidado.get("Valor Líquido", pd.Series()).sum()
        st.metric("Valor Líquido Total", f"${valor_liquido_total:,.2f}")
    
    st.markdown("---")
    
    # Filtros
    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        if "Ativo" in df_consolidado.columns:
            ativos = sorted(df_consolidado["Ativo"].unique())
            ativos_sel = st.multiselect(
                "Ativo",
                ativos,
                default=ativos,
                key="consolidado_ativo"
            )
    
    with col_f2:
        if "Data" in df_consolidado.columns:
            data_min = df_consolidado["Data"].min()
            data_max = df_consolidado["Data"].max()
            try:
                data_range = st.date_input(
                    "Período",
                    value=(data_min.date() if pd.notna(data_min) else None, 
                           data_max.date() if pd.notna(data_max) else None),
                    key="consolidado_data"
                )
            except:
                data_range = None
    
    with col_f3:
        if "Fonte" in df_consolidado.columns:
            fontes = sorted(df_consolidado["Fonte"].unique())
            fontes_sel = st.multiselect(
                "Fonte",
                fontes,
                default=fontes,
                key="consolidado_fonte"
            )
    
    # Aplicar filtros
    df_filtrado = df_consolidado
    
    if "Ativo" in df_consolidado.columns:
        df_filtrado = df_filtrado[df_filtrado["Ativo"].isin(ativos_sel)]
    
    if "Data" in df_consolidado.columns and data_range and len(data_range) == 2:
        try:
            df_filtrado = df_filtrado[
                (df_filtrado["Data"].dt.date >= data_range[0]) &
                (df_filtrado["Data"].dt.date <= data_range[1])
            ]
        except:
            pass
    
    if "Fonte" in df_consolidado.columns:
        df_filtrado = df_filtrado[df_filtrado["Fonte"].isin(fontes_sel)]
    
    # Ordenação
    ordenacao = st.selectbox(
        "Ordenar por",
        ["Data (mais recente)", "Data (mais antigo)", "Valor Líquido (maior)", "Valor Líquido (menor)", "Ativo (A-Z)"],
        key="consolidado_ordem"
    )
    
    if ordenacao == "Data (mais recente)":
        df_filtrado = df_filtrado.sort_values("Data", ascending=False)
    elif ordenacao == "Data (mais antigo)":
        df_filtrado = df_filtrado.sort_values("Data", ascending=True)
    elif ordenacao == "Valor Líquido (maior)":
        df_filtrado = df_filtrado.sort_values("Valor Líquido", ascending=False)
    elif ordenacao == "Valor Líquido (menor)":
        df_filtrado = df_filtrado.sort_values("Valor Líquido", ascending=True)
    elif ordenacao == "Ativo (A-Z)":
        df_filtrado = df_filtrado.sort_values("Ativo", ascending=True)
    
    # Exibir tabela
    st.subheader("📊 Dividendos")
    st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
    
    # Exportação
    st.markdown("---")
    st.subheader("📥 Exportar Dados")
    
    col_exp1, col_exp2 = st.columns(2)
    
    with col_exp1:
        csv = df_filtrado.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="📥 Baixar como CSV",
            data=csv,
            file_name=f"dividendos_consolidado_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    
    with col_exp2:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_filtrado.to_excel(writer, index=False, sheet_name="Dividendos")
        buffer.seek(0)
        st.download_button(
            label="📥 Baixar como Excel",
            data=buffer,
            file_name=f"dividendos_consolidado_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    # Análise
    st.markdown("---")
    st.subheader("📈 Análise")
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        if "Ativo" in df_filtrado.columns and "Valor Líquido" in df_filtrado.columns:
            dist_ativo = df_filtrado.groupby("Ativo")["Valor Líquido"].sum().sort_values(ascending=False)
            max_val = dist_ativo.values.max() if len(dist_ativo.values) else 0
            tickers_x = [extrair_ticker_curto(a) or str(a) for a in dist_ativo.index]
            fig = px.bar(
                x=tickers_x,
                y=dist_ativo.values,
                title="Dividendos por Ativo",
                labels={"x": "Ativo", "y": "Valor Líquido ($)"},
                text=[f"{v:,.2f}" for v in dist_ativo.values]
            )
            fig.update_traces(
                textposition="outside",
                cliponaxis=False,
                customdata=list(dist_ativo.index),
                hovertemplate="<b>%{customdata}</b><br>Ticker: %{x}<br>Valor: %{y:,.2f}<extra></extra>"
            )
            fig.update_layout(yaxis_tickformat=",.2f", margin=dict(t=60))
            if max_val > 0:
                fig.update_yaxes(range=[0, max_val * 1.15])
            st.plotly_chart(fig, use_container_width=True)
    
    with col_chart2:
        if "Data" in df_filtrado.columns and "Valor Líquido" in df_filtrado.columns:
            # Preencher todos os meses do range
            data_min = df_filtrado["Data"].min()
            data_max = df_filtrado["Data"].max()
            # Bimestral correto
            periodo = st.session_state.get("periodo_prov", "Mensal") if "periodo_prov" in st.session_state else "Mensal"
            if periodo == "Bimestral":
                df_temp = df_filtrado.copy()
                df_temp["bimestre_ini"] = pd.to_datetime(df_temp["Data"].dt.year.astype(str) + "-" + ((df_temp["Data"].dt.month.sub(1) // 2)*2 + 1).astype(str).str.zfill(2) + "-01")
                group = df_temp.groupby("bimestre_ini")["Valor Líquido"].sum()
                idx = pd.date_range(data_min.replace(day=1), data_max.replace(day=1), freq="2MS")
                group = group.reindex(idx, fill_value=0)
                evolucao = group
                evolucao.index = [d.strftime("%Y-%m") for d in evolucao.index]
            elif periodo == "Semestral":
                df_temp = df_filtrado.copy()
                df_temp["semestre_ini"] = pd.to_datetime(df_temp["Data"].dt.year.astype(str) + "-" + ((df_temp["Data"].dt.month <= 6).map({True: '01', False: '07'})) + "-01")
                group = df_temp.groupby("semestre_ini")["Valor Líquido"].sum()
                # Gera todos os semestres do range
                semestres = []
                ano_ini = data_min.year
                ano_fim = data_max.year
                for ano in range(ano_ini, ano_fim+1):
                    semestres.append(pd.Timestamp(f"{ano}-01-01"))
                    semestres.append(pd.Timestamp(f"{ano}-07-01"))
                semestres = [s for s in semestres if s >= data_min.replace(day=1) and s <= data_max.replace(day=1)]
                group = group.reindex(semestres, fill_value=0)
                evolucao = group
                evolucao.index = [d.strftime("%Y-%m") for d in evolucao.index]
            else:
                idx = pd.period_range(data_min, data_max, freq="M")
                evolucao = df_filtrado.groupby(df_filtrado["Data"].dt.to_period("M"))["Valor Líquido"].sum().reindex(idx, fill_value=0)
                evolucao.index = evolucao.index.astype(str)
            fig = px.line(
                x=evolucao.index,
                y=evolucao.values,
                title="Evolução de Dividendos",
                labels={"x": "Período", "y": "Valor Líquido ($)"},
                text=[f"{v:,.2f}" for v in evolucao.values]
            )
            fig.update_traces(textposition="top center", mode="lines+markers+text")
            fig.update_layout(yaxis_tickformat=",.2f", xaxis_tickmode="array", xaxis_tickvals=list(evolucao.index), xaxis_ticktext=list(evolucao.index))
            st.plotly_chart(fig, use_container_width=True)
    
    # Resumo por ativo
    st.markdown("---")
    st.subheader("💹 Resumo por Ativo")
    if "Ativo" in df_filtrado.columns:
        resumo = df_filtrado.groupby("Ativo").agg({
            "Valor Bruto": "sum",
            "Impostos": "sum",
            "Valor Líquido": "sum"
        }).reset_index().sort_values("Valor Líquido", ascending=False)
        if "Impostos" in resumo.columns:
            resumo["Impostos"] = resumo["Impostos"].apply(lambda x: float(x) if x <= 0 else -abs(float(x)))
        st.dataframe(resumo, use_container_width=True, hide_index=True)
    
    # Resumo por mês
    st.markdown("---")
    st.subheader("📅 Resumo por Período")
    if "Data" in df_filtrado.columns:
        resumo_mes = df_filtrado.groupby(df_filtrado["Data"].dt.to_period("M")).agg({
            "Valor Bruto": "sum",
            "Impostos": "sum",
            "Valor Líquido": "sum"
        }).reset_index()
        resumo_mes.columns = ["Período", "Valor Bruto", "Impostos", "Valor Líquido"]
        resumo_mes["Período"] = resumo_mes["Período"].astype(str)
        if "Impostos" in resumo_mes.columns:
            resumo_mes["Impostos"] = resumo_mes["Impostos"].apply(lambda x: float(x) if x <= 0 else -abs(float(x)))
        st.dataframe(resumo_mes, use_container_width=True, hide_index=True)
