from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

from modules.cotacoes import obter_cotacao_atual_eur_brl, obter_cotacao_atual_usd_brl
from modules.ticker_info import extrair_ticker, ticker_para_yfinance


def _parse_num_misto(valor) -> float:
    if pd.isna(valor):
        return np.nan
    if isinstance(valor, (int, float, np.integer, np.floating)):
        try:
            return float(valor)
        except Exception:
            return np.nan

    txt = str(valor).strip()
    if not txt:
        return np.nan

    txt = (
        txt.replace("R$", "")
        .replace("US$", "")
        .replace("$", "")
        .replace("%", "")
        .replace("\u00a0", " ")
        .replace(" ", "")
    )

    negativo = False
    if txt.startswith("(") and txt.endswith(")"):
        negativo = True
        txt = txt[1:-1]

    if txt.startswith("+"):
        txt = txt[1:]
    elif txt.startswith("-"):
        negativo = True
        txt = txt[1:]

    if not txt:
        return np.nan

    if "." in txt and "," in txt:
        txt_norm = txt.replace(".", "").replace(",", ".")
    elif "," in txt:
        txt_norm = txt.replace(".", "").replace(",", ".")
    elif "." in txt:
        partes = txt.split(".")
        if len(partes) > 2:
            txt_norm = "".join(partes)
        else:
            if len(partes) == 2 and len(partes[1]) == 3 and partes[0].isdigit() and partes[1].isdigit():
                txt_norm = "".join(partes)
            else:
                txt_norm = txt
    else:
        txt_norm = txt

    try:
        num = float(txt_norm)
        return -num if negativo else num
    except Exception:
        return np.nan


def _parse_mes_ano_to_periodo(valor) -> Optional[pd.Period]:
    if pd.isna(valor):
        return None
    s = str(valor).strip()
    if not s:
        return None

    # Formatos comuns do app: "MM/YYYY" e "YYYY-MM"
    try:
        if "/" in s and len(s.split("/")) == 2:
            dt = pd.to_datetime("01/" + s, format="%d/%m/%Y", errors="coerce")
            if pd.notna(dt):
                return pd.Period(dt, freq="M")
    except Exception:
        pass

    try:
        dt2 = pd.to_datetime(s, errors="coerce", dayfirst=True)
        if pd.notna(dt2):
            return pd.Period(dt2, freq="M")
    except Exception:
        return None

    return None


def preparar_posicao_base(df_cons: pd.DataFrame, agrupar_por_usuario: bool = False) -> pd.DataFrame:
    """Prepara um DF base para atualização de cotação.

    - Para `Tipo == "Ações Dólar"`, assume que `Preço` está em USD.
    - Para os demais, assume BRL.

    Entrada (colunas podem variar):
    - Ticker (ou Ativo), Tipo, Usuário, Quantidade (preferida), Quantidade Disponível (fallback), Preço/Preco, Mês/Ano.

    Saída:
    - (opcional Usuário), Tipo, Moeda, Ticker, Quantidade, Preço, Valor Base
    """
    if df_cons is None or df_cons.empty:
        cols = ["Tipo", "Moeda", "Ticker", "Quantidade", "Preço", "Valor Base"]
        if agrupar_por_usuario:
            cols = ["Usuário"] + cols
        return pd.DataFrame(columns=cols)

    dfp = df_cons.copy()

    if "Ticker" in dfp.columns:
        tick = dfp["Ticker"]
        if "Ativo" in dfp.columns:
            tick = tick.where(tick.notna() & (tick.astype(str).str.strip() != ""), dfp["Ativo"])
    else:
        tick = dfp.get("Ativo")

    dfp["Ticker"] = tick.apply(extrair_ticker) if tick is not None else None
    dfp["Ticker"] = dfp["Ticker"].fillna("").astype(str).str.strip().str.upper()
    dfp = dfp[dfp["Ticker"] != ""].copy()

    if "Tipo" not in dfp.columns:
        dfp["Tipo"] = "N/A"
    dfp["Tipo"] = dfp["Tipo"].fillna("N/A")

    if "Usuário" not in dfp.columns:
        dfp["Usuário"] = "Não informado"
    dfp["Usuário"] = dfp["Usuário"].fillna("Não informado")

    if dfp.empty:
        cols = ["Tipo", "Moeda", "Ticker", "Quantidade", "Preço", "Valor Base"]
        if agrupar_por_usuario:
            cols = ["Usuário"] + cols
        return pd.DataFrame(columns=cols)

    # Preferir "Quantidade" (patrimônio). Fallback para "Quantidade Disponível" para compatibilidade.
    qtd = dfp["Quantidade"] if "Quantidade" in dfp.columns else None
    if qtd is None:
        qtd = dfp["Quantidade Disponível"] if "Quantidade Disponível" in dfp.columns else 0.0
    else:
        if "Quantidade Disponível" in dfp.columns:
            qtd = qtd.where(qtd.notna(), dfp["Quantidade Disponível"])
    dfp["Quantidade"] = pd.to_numeric(pd.Series(qtd).apply(_parse_num_misto), errors="coerce").fillna(0.0)

    if "Preço" in dfp.columns:
        dfp["Preço"] = pd.to_numeric(dfp["Preço"].apply(_parse_num_misto), errors="coerce")
    elif "Preco" in dfp.columns:
        dfp["Preço"] = pd.to_numeric(dfp["Preco"].apply(_parse_num_misto), errors="coerce")
    else:
        dfp["Preço"] = np.nan

    # Moeda: se já vier no consolidado, preservar (evita problemas com espaços/unicode no Tipo).
    # Fallback: inferir pelo Tipo.
    tipo_norm = dfp["Tipo"].astype(str)
    tipo_norm = tipo_norm.str.replace("\u00a0", " ", regex=False).str.strip().str.upper()
    moeda_inferida = np.select(
        [tipo_norm == "AÇÕES DÓLAR", tipo_norm == "AÇÕES EURO"],
        ["USD", "EUR"],
        default="BRL",
    )
    if "Moeda" in dfp.columns:
        moeda_raw = dfp["Moeda"].fillna("").astype(str)
        moeda_raw = moeda_raw.str.replace("\u00a0", " ", regex=False).str.strip().str.upper()
        moeda_raw = moeda_raw.replace({"R$": "BRL", "US$": "USD", "€": "EUR"})
        moeda_raw = moeda_raw.where(moeda_raw.isin(["BRL", "USD", "EUR"]), "")
        dfp["Moeda"] = moeda_raw.where(moeda_raw != "", moeda_inferida)
    else:
        dfp["Moeda"] = moeda_inferida

    # Valor base do mês (para RF/TD/Opções e fallback geral)
    if "Valor" in dfp.columns:
        dfp["Valor Base"] = pd.to_numeric(dfp["Valor"].apply(_parse_num_misto), errors="coerce")
    elif "Valor de Mercado" in dfp.columns:
        dfp["Valor Base"] = pd.to_numeric(dfp["Valor de Mercado"].apply(_parse_num_misto), errors="coerce")
    else:
        dfp["Valor Base"] = np.nan

    # Se existir Mês/Ano, usa o último mês como "posição atual"
    if "Mês/Ano" in dfp.columns:
        dfp["Periodo"] = dfp["Mês/Ano"].apply(_parse_mes_ano_to_periodo)
        dfp = dfp[dfp["Periodo"].notna()].copy()
        if not dfp.empty:
            ultimo = dfp["Periodo"].max()
            dfp = dfp[dfp["Periodo"] == ultimo].copy()

    # Preço histórico: média ponderada por quantidade quando possível
    mask_preco = dfp["Preço"].notna() & (dfp["Preço"] > 0) & (dfp["Quantidade"] > 0)
    dfp["_qp"] = np.where(mask_preco, dfp["Quantidade"] * dfp["Preço"], 0.0)
    dfp["_q"] = np.where(mask_preco, dfp["Quantidade"], 0.0)

    group_cols = ["Tipo", "Moeda", "Ticker"]
    if agrupar_por_usuario:
        group_cols = ["Usuário"] + group_cols

    agg = (
        dfp.groupby(group_cols, as_index=False)
        .agg(
            Quantidade=("Quantidade", "sum"),
            _qp=("_qp", "sum"),
            _q=("_q", "sum"),
            **{"Valor Base": ("Valor Base", "sum")},
        )
        .sort_values(group_cols)
        .reset_index(drop=True)
    )
    agg["Preço"] = np.where(agg["_q"] > 0, agg["_qp"] / agg["_q"], np.nan)
    df_out = agg.drop(columns=["_qp", "_q"])

    return df_out


def _buscar_preco_yfinance(ticker: str) -> Tuple[Optional[float], Optional[str], Optional[float], Optional[float]]:
    """Retorna (preco_atual, ticker_yf, preco_anterior, variacao_pct)."""
    t0 = (ticker or "").strip().upper()
    if not t0:
        return None, None, None, None

    sym = ticker_para_yfinance(t0) or t0

    try:
        tk = yf.Ticker(sym)
        preco_atual = None
        preco_anterior = None
        variacao_pct = None

        # Tentar obter info completo (tem variação % e previousClose)
        try:
            info = tk.info or {}
            preco_atual = info.get("regularMarketPrice") or info.get("currentPrice")
            preco_anterior = info.get("previousClose") or info.get("regularMarketPreviousClose")
            variacao_pct = info.get("regularMarketChangePercent")
            
            if preco_atual is not None and float(preco_atual) > 0:
                return float(preco_atual), sym, float(preco_anterior) if preco_anterior else None, float(variacao_pct) if variacao_pct else None
        except Exception:
            pass

        # Fallback: histórico de 5 dias para calcular variação
        try:
            hist = tk.history(period="5d")
            if isinstance(hist, pd.DataFrame) and (not hist.empty) and ("Close" in hist.columns):
                closes = pd.to_numeric(hist["Close"], errors="coerce").dropna()
                if len(closes) >= 2:
                    preco_atual = float(closes.iloc[-1])
                    preco_anterior = float(closes.iloc[-2])
                    variacao_pct = ((preco_atual / preco_anterior) - 1.0) * 100.0
                    return preco_atual, sym, preco_anterior, variacao_pct
                elif len(closes) == 1:
                    preco_atual = float(closes.iloc[-1])
                    return preco_atual, sym, None, None
        except Exception:
            pass

        # Histórico intraday como último recurso
        try:
            hist_intra = tk.history(period="1d", interval="1m")
            if isinstance(hist_intra, pd.DataFrame) and (not hist_intra.empty) and ("Close" in hist_intra.columns):
                px_last = pd.to_numeric(hist_intra["Close"], errors="coerce").dropna()
                if not px_last.empty:
                    return float(px_last.iloc[-1]), sym, None, None
        except Exception:
            pass

        return None, sym, None, None
    except Exception:
        return None, sym, None, None


def atualizar_cotacoes(df_posicao: pd.DataFrame) -> Tuple[pd.DataFrame, List[str], datetime]:
    """Atualiza cotação em tempo real via yfinance com fallback no histórico.

    Entrada mínima:
    - Ticker, Quantidade, Preço (histórico)

    Saída:
    - Ticker, Quantidade, Preço Atual, Valor Atualizado (+ colunas auxiliares)
    """
    if df_posicao is None or df_posicao.empty:
        return pd.DataFrame(columns=["Ticker", "Quantidade", "Preço Atual", "Valor Atualizado"]), [], datetime.now()

    df = df_posicao.copy()

    if "Ticker" not in df.columns:
        raise ValueError("df_posicao precisa ter a coluna 'Ticker'")
    if "Quantidade" not in df.columns:
        raise ValueError("df_posicao precisa ter a coluna 'Quantidade'")
    if "Preço" not in df.columns:
        df["Preço"] = np.nan
    if "Tipo" not in df.columns:
        df["Tipo"] = "N/A"
    if "Moeda" not in df.columns:
        df["Moeda"] = "BRL"
    if "Valor Base" not in df.columns:
        df["Valor Base"] = np.nan

    df["Ticker"] = df["Ticker"].fillna("").astype(str).str.strip().str.upper()
    df["Quantidade"] = pd.to_numeric(df["Quantidade"].apply(_parse_num_misto), errors="coerce").fillna(0.0)
    df["Preço"] = pd.to_numeric(df["Preço"].apply(_parse_num_misto), errors="coerce")
    df["Valor Base"] = pd.to_numeric(df["Valor Base"].apply(_parse_num_misto), errors="coerce")
    df["Moeda"] = df["Moeda"].fillna("BRL").astype(str).str.strip().str.upper()
    df["Tipo"] = df["Tipo"].fillna("N/A").astype(str).str.strip()

    cotacao_usd_brl = obter_cotacao_atual_usd_brl()
    cotacao_eur_brl = obter_cotacao_atual_eur_brl()

    # Só atualiza cotação em tempo real para ações
    tipos_atualizaveis = {"Ações", "Ações Dólar", "Ações Euro"}

    precos_brl: List[Optional[float]] = []
    precos_usd: List[Optional[float]] = []
    precos_eur: List[Optional[float]] = []
    fontes: List[str] = []
    tickers_yf: List[Optional[str]] = []
    sem_cotacao: List[str] = []
    cotacoes_fx: List[Optional[float]] = []
    cotacoes_eur: List[Optional[float]] = []
    preco_hist_brl: List[Optional[float]] = []
    precos_anteriores: List[Optional[float]] = []
    variacoes_pct: List[Optional[float]] = []

    for _, row in df.iterrows():
        tk = str(row.get("Ticker") or "").strip().upper()
        moeda = str(row.get("Moeda") or "BRL").strip().upper()
        preco_hist = row.get("Preço")
        tipo = str(row.get("Tipo") or "N/A").strip()
        valor_base = row.get("Valor Base")

        # Tipos sem cotação (RF/TD/Opções etc): manter o valor do mês
        if tipo not in tipos_atualizaveis:
            sym = None
            tickers_yf.append(sym)
            fontes.append("Base (mês)")
            precos_anteriores.append(np.nan)
            variacoes_pct.append(np.nan)

            if moeda == "USD":
                cotacoes_fx.append(float(cotacao_usd_brl))
                cotacoes_eur.append(np.nan)
                precos_usd.append(np.nan)
                precos_eur.append(np.nan)
                precos_brl.append(np.nan)
                preco_hist_brl.append(np.nan)
            elif moeda == "EUR":
                cotacoes_fx.append(np.nan)
                cotacoes_eur.append(float(cotacao_eur_brl) if pd.notna(cotacao_eur_brl) else np.nan)
                precos_usd.append(np.nan)
                precos_eur.append(np.nan)
                precos_brl.append(np.nan)
                preco_hist_brl.append(np.nan)
            else:
                cotacoes_fx.append(np.nan)
                cotacoes_eur.append(np.nan)
                precos_usd.append(np.nan)
                precos_eur.append(np.nan)
                precos_brl.append(np.nan)
                preco_hist_brl.append(np.nan)

            continue

        preco_yf, sym, preco_ant_yf, var_pct_yf = _buscar_preco_yfinance(tk)

        preco_base = None
        fonte = None
        if preco_yf is None or not (isinstance(preco_yf, (int, float)) and float(preco_yf) > 0):
            if pd.notna(preco_hist) and float(preco_hist) > 0:
                preco_base = float(preco_hist)
                fonte = "Histórico"
                sem_cotacao.append(tk)
            else:
                preco_base = np.nan
                fonte = "Não encontrado"
                sem_cotacao.append(tk)
        else:
            preco_base = float(preco_yf)
            fonte = "yfinance"

        # Salvar preço anterior e variação % do yfinance
        precos_anteriores.append(preco_ant_yf if preco_ant_yf is not None else np.nan)
        variacoes_pct.append(var_pct_yf if var_pct_yf is not None else np.nan)

        if moeda == "USD":
            cotacoes_fx.append(float(cotacao_usd_brl))
            cotacoes_eur.append(np.nan)
            precos_usd.append(preco_base if pd.notna(preco_base) else np.nan)
            precos_eur.append(np.nan)
            precos_brl.append(float(preco_base) * float(cotacao_usd_brl) if pd.notna(preco_base) else np.nan)
            if pd.notna(preco_hist) and float(preco_hist) > 0:
                preco_hist_brl.append(float(preco_hist) * float(cotacao_usd_brl))
            else:
                preco_hist_brl.append(np.nan)
        elif moeda == "EUR":
            cotacoes_fx.append(np.nan)
            cotacoes_eur.append(float(cotacao_eur_brl) if pd.notna(cotacao_eur_brl) else np.nan)
            precos_usd.append(np.nan)
            precos_eur.append(preco_base if pd.notna(preco_base) else np.nan)
            if pd.notna(preco_base) and pd.notna(cotacao_eur_brl) and float(cotacao_eur_brl) > 0:
                precos_brl.append(float(preco_base) * float(cotacao_eur_brl))
            else:
                precos_brl.append(np.nan)
            if pd.notna(preco_hist) and float(preco_hist) > 0 and pd.notna(cotacao_eur_brl) and float(cotacao_eur_brl) > 0:
                preco_hist_brl.append(float(preco_hist) * float(cotacao_eur_brl))
            else:
                preco_hist_brl.append(np.nan)
        else:
            cotacoes_fx.append(np.nan)
            cotacoes_eur.append(np.nan)
            precos_usd.append(np.nan)
            precos_eur.append(np.nan)
            precos_brl.append(preco_base)
            preco_hist_brl.append(float(preco_hist) if pd.notna(preco_hist) else np.nan)

        fontes.append(fonte)
        tickers_yf.append(sym)

    df["Ticker YF"] = tickers_yf
    df["Preço Atual"] = pd.to_numeric(precos_brl, errors="coerce")
    df["Preço Atual (USD)"] = pd.to_numeric(precos_usd, errors="coerce")
    df["Cotação USD/BRL"] = pd.to_numeric(cotacoes_fx, errors="coerce")
    df["Preço Atual (EUR)"] = pd.to_numeric(precos_eur, errors="coerce")
    df["Cotação EUR/BRL"] = pd.to_numeric(cotacoes_eur, errors="coerce")
    df["Preço Anterior"] = pd.to_numeric(precos_anteriores, errors="coerce")
    df["Variação % YF"] = pd.to_numeric(variacoes_pct, errors="coerce")
    df["Fonte Preço"] = fontes
    df["Preço Histórico"] = pd.to_numeric(df["Preço"], errors="coerce")
    df["Preço Histórico (BRL)"] = pd.to_numeric(preco_hist_brl, errors="coerce")

    # Valor atualizado:
    # - Para ações: Quantidade × Preço Atual (em BRL)
    # - Para demais tipos: manter Valor Base (convertendo se necessário)
    mask_atualiza = df["Tipo"].isin(list(tipos_atualizaveis))

    moeda_norm = df["Moeda"].astype(str).str.upper()
    vb = pd.to_numeric(df["Valor Base"], errors="coerce")
    valor_base_brl = np.select(
        [moeda_norm == "USD", moeda_norm == "EUR"],
        [vb * float(cotacao_usd_brl), vb * float(cotacao_eur_brl) if pd.notna(cotacao_eur_brl) else np.nan],
        default=vb,
    )

    df["Valor Atualizado"] = np.where(
        mask_atualiza,
        df["Quantidade"] * df["Preço Atual"],
        valor_base_brl,
    )

    # Fallback final: se ação ficou NaN (sem preço e sem histórico), usa Valor Base do mês
    df["Valor Atualizado"] = np.where(
        pd.to_numeric(df["Valor Atualizado"], errors="coerce").notna(),
        df["Valor Atualizado"],
        valor_base_brl,
    )

    # Variação %: Usar variação do yfinance quando disponível, senão calcular com preço anterior
    df["Variação %"] = np.where(
        df["Variação % YF"].notna(),
        df["Variação % YF"],
        np.where(
            mask_atualiza & df["Preço Anterior"].notna() & (df["Preço Anterior"] > 0) & df["Preço Atual"].notna(),
            (df["Preço Atual"] / df["Preço Anterior"] - 1.0) * 100.0,
            np.nan
        )
    )

    atualizado_em = datetime.now()

    # Lista de tickers onde não veio cotação em tempo real
    sem_cotacao = sorted({t for t in sem_cotacao if t})

    # Ordena por valor atualizado desc
    df = df.sort_values(["Valor Atualizado", "Ticker"], ascending=[False, True]).reset_index(drop=True)

    return df, sem_cotacao, atualizado_em


def dataframe_para_excel_bytes(df: pd.DataFrame, sheet_name: str = "posicao") -> bytes:
    """Converte DataFrame para bytes de Excel (xlsx)."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    return output.getvalue()


def preparar_tabela_posicao_estilizada(df: pd.DataFrame) -> Tuple[pd.DataFrame, "pd.io.formats.style.Styler"]:
    """Retorna (df_exibicao, styler) com boas práticas para visualização em carteira."""
    if df is None or df.empty:
        vazio = pd.DataFrame(columns=[
            "Símbolo", "Tipo", "Quantidade", "Preço Histórico (BRL)", "Preço Atual", "Variação %", "Valor Atualizado"
        ])
        return vazio, vazio.style

    dfv = df.copy()

    # Colunas amigáveis
    dfv["Símbolo"] = dfv.get("Ticker")

    var = pd.to_numeric(dfv.get("Variação %"), errors="coerce")
    dfv["Tendência"] = np.where(var > 0, "▲", np.where(var < 0, "▼", "•"))

    # Organizar colunas (mantém extras úteis quando existirem)
    cols_base = [
        "Símbolo",
        "Tendência",
        "Tipo",
        "Quantidade",
        "Preço Histórico (BRL)",
        "Preço Atual",
        "Variação %",
        "Valor Atualizado",
        "Fonte Preço",
    ]
    cols_extra = [c for c in ["Preço Atual (USD)", "Cotação USD/BRL", "Preço Atual (EUR)", "Cotação EUR/BRL", "Ticker YF"] if c in dfv.columns]
    cols = [c for c in cols_base if c in dfv.columns] + cols_extra
    dfv = dfv[cols].copy()

    # Funções de estilo
    def _style_variacao(v):
        try:
            if pd.isna(v):
                return "color: #6b7280"  # cinza
            v = float(v)
            if v > 0:
                return "color: #166534; font-weight: 700"  # verde escuro
            if v < 0:
                return "color: #991b1b; font-weight: 700"  # vermelho escuro
            return "color: #374151; font-weight: 600"
        except Exception:
            return ""

    def _style_tendencia(v):
        if v == "▲":
            return "color: #166534; font-weight: 900"
        if v == "▼":
            return "color: #991b1b; font-weight: 900"
        return "color: #374151; font-weight: 700"

    fmt = {
        "Quantidade": "{:,.2f}",
        "Preço Histórico (BRL)": "R$ {:,.2f}",
        "Preço Atual": "R$ {:,.2f}",
        "Valor Atualizado": "R$ {:,.2f}",
        "Variação %": "{:+.2f}%",
        "Preço Atual (USD)": "US$ {:,.2f}",
        "Cotação USD/BRL": "{:,.4f}",
        "Preço Atual (EUR)": "€ {:,.2f}",
        "Cotação EUR/BRL": "{:,.4f}",
    }
    fmt = {k: v for k, v in fmt.items() if k in dfv.columns}

    styler = (
        dfv.style
        .format(fmt, na_rep="—")
        .applymap(_style_tendencia, subset=["Tendência"] if "Tendência" in dfv.columns else None)
        .applymap(_style_variacao, subset=["Variação %"] if "Variação %" in dfv.columns else None)
        .bar(subset=["Variação %"], color=["#fecaca", "#bbf7d0"], vmin=-20, vmax=20)
        .set_properties(**{"white-space": "nowrap"})
    )

    return dfv, styler
