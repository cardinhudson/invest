import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from io import BytesIO
import contextlib
import io

import yfinance as yf

from modules.ticker_info import (
    CACHE_PATH as TICKER_INFO_PATH,
    _load_cache as _load_ticker_info_cache,
    atualizar_cache_tickers,
    ticker_para_yfinance,
    extrair_ticker,
)


st.set_page_config(page_title="Análise Fundamentalista", page_icon="📊", layout="wide")


def _as_float(v):
    try:
        if v is None:
            return None
        if isinstance(v, (int, float, np.number)) and np.isfinite(v):
            return float(v)
        vv = float(v)
        if np.isfinite(vv):
            return vv
        return None
    except Exception:
        return None


def _to_percent_0_100(v) -> float | None:
    """Normaliza valores que podem vir como fração (0-1) ou percent (0-100)."""
    vv = _as_float(v)
    if vv is None:
        return None
    # Heurística simples: >1 tende a já estar em %.
    if abs(vv) > 1.0:
        return vv
    return vv * 100.0


def _to_ratio_0_1(v) -> float | None:
    """Normaliza valores que podem vir como fração (0-1) ou percent (0-100) para fração."""
    vv = _as_float(v)
    if vv is None:
        return None
    if abs(vv) > 1.0:
        return vv / 100.0
    return vv


def _fmt_2(v) -> str:
    vv = _as_float(v)
    if vv is None:
        return "—"
    s = f"{vv:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_percent(v) -> str:
    vv = _to_percent_0_100(v)
    if vv is None:
        return "—"
    s = f"{vv:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s}%"


def _compute_annual_metrics(
    income_a: pd.DataFrame,
    balance_a: pd.DataFrame,
    shares_outstanding: float | None,
) -> pd.DataFrame:
    """Métricas anuais para preencher histórico quando trimestral é curto."""
    income_a = _to_datetime_index_cols(income_a)
    balance_a = _to_datetime_index_cols(balance_a)

    if income_a.empty and balance_a.empty:
        return pd.DataFrame()

    if not income_a.empty:
        income_a = income_a.copy()
        income_a.index = income_a.index.astype(str)
    if not balance_a.empty:
        balance_a = balance_a.copy()
        balance_a.index = balance_a.index.astype(str)

    revenue = _pick_first(income_a, ["Total Revenue", "TotalRevenue", "Revenue"])
    net_income = _pick_first(income_a, ["Net Income", "NetIncome", "Net Income Applicable To Common Shares"])

    equity = _pick_first(balance_a, ["Total Stockholder Equity", "TotalStockholderEquity", "Stockholders Equity"])
    total_debt = _pick_first(balance_a, ["Total Debt", "TotalDebt"])

    dates = pd.Index([])
    if not revenue.empty:
        dates = dates.union(revenue.index)
    if not equity.empty:
        dates = dates.union(equity.index)

    dates = pd.to_datetime(dates, errors="coerce")
    if getattr(dates, "tz", None) is not None:
        dates = dates.tz_localize(None)
    dates = dates.dropna().sort_values()
    if len(dates) == 0:
        return pd.DataFrame()

    df = pd.DataFrame(index=dates)

    def _reindex(s: pd.Series) -> pd.Series:
        if s is None or len(s) == 0:
            return pd.Series(index=dates, dtype=float)
        s2 = s.copy()
        s2.index = pd.to_datetime(s2.index, errors="coerce")
        if getattr(s2.index, "tz", None) is not None:
            s2.index = s2.index.tz_localize(None)
        s2 = s2.dropna()
        return s2.reindex(dates)

    df["Receita"] = _reindex(revenue)
    df["Lucro Líquido"] = _reindex(net_income)
    df["Patrimônio Líquido"] = _reindex(equity)
    df["Dívida Total"] = _reindex(total_debt)

    df["Margem Líquida"] = np.where(
        df["Receita"].notna() & (df["Receita"] != 0) & df["Lucro Líquido"].notna(),
        df["Lucro Líquido"] / df["Receita"],
        np.nan,
    )

    df["Dívida/Patrimônio"] = np.where(
        df["Patrimônio Líquido"].notna() & (df["Patrimônio Líquido"] != 0) & df["Dívida Total"].notna(),
        df["Dívida Total"] / df["Patrimônio Líquido"],
        np.nan,
    )

    df["ROE"] = np.where(
        df["Patrimônio Líquido"].notna() & (df["Patrimônio Líquido"] != 0) & df["Lucro Líquido"].notna(),
        df["Lucro Líquido"] / df["Patrimônio Líquido"],
        np.nan,
    )

    if shares_outstanding and shares_outstanding > 0:
        df["BVPS"] = df["Patrimônio Líquido"] / float(shares_outstanding)
        df["EPS"] = df["Lucro Líquido"] / float(shares_outstanding)

    return df.reset_index().rename(columns={"index": "Data"})


def _format_month_label(ts: pd.Timestamp) -> str:
    return ts.strftime("%m/%Y")


def _pick_price_column(df: pd.DataFrame) -> str | None:
    if df is None or df.empty:
        return None
    if "Close" in df.columns:
        return "Close"
    if "Adj Close" in df.columns:
        return "Adj Close"
    numeric_cols = [c for c in df.columns if c != "Data" and pd.api.types.is_numeric_dtype(df[c])]
    return numeric_cols[0] if numeric_cols else None


def _to_datetime_index_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Converte colunas do tipo datetime-like em DateTimeIndex, se possível."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    out = df.copy()
    try:
        out.columns = pd.to_datetime(out.columns)
        if getattr(out.columns, "tz", None) is not None:
            out.columns = out.columns.tz_localize(None)
    except Exception:
        return out
    return out


def _flatten_statement(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
    """Transforma demonstrativo (linhas=contas, colunas=datas) em tabela longa."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame(columns=["Data", "Conta", "Valor", "Fonte"])

    df2 = _to_datetime_index_cols(df)
    df2 = df2.copy()
    df2.index = df2.index.astype(str)

    long = (
        df2.reset_index()
        .rename(columns={"index": "Conta"})
        .melt(id_vars=["Conta"], var_name="Data", value_name="Valor")
    )
    long["Data"] = pd.to_datetime(long["Data"], errors="coerce")
    long["Valor"] = pd.to_numeric(long["Valor"], errors="coerce")
    long["Fonte"] = prefix
    long = long.dropna(subset=["Data"]).sort_values(["Data", "Conta"]).reset_index(drop=True)
    return long


def _pick_first(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
    """Retorna a primeira linha disponível dentre as contas candidatas."""
    if df is None or df.empty:
        return pd.Series(dtype=float)
    for name in candidates:
        if name in df.index:
            return pd.to_numeric(df.loc[name], errors="coerce")
    return pd.Series(dtype=float)


def _parse_yf_date(v) -> pd.Timestamp | None:
    """Converte datas do yfinance (epoch seconds, datetime, string) para Timestamp."""
    try:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return None
        # yfinance costuma retornar epoch (segundos)
        if isinstance(v, (int, np.integer)):
            return pd.to_datetime(int(v), unit="s", errors="coerce")
        if isinstance(v, (float, np.floating)):
            return pd.to_datetime(int(v), unit="s", errors="coerce")
        ts = pd.to_datetime(v, errors="coerce")
        return ts
    except Exception:
        return None


@st.cache_data(ttl=86400, show_spinner=False)
def _validar_tickers_em_lote(tickers_display: tuple[str, ...]) -> list[str]:
    """Valida tickers via yfinance em lote (leve), retornando os que têm histórico recente."""
    if not tickers_display:
        return []

    # Map display -> yfinance
    disp = [str(t).strip() for t in tickers_display if str(t).strip()]
    if not disp:
        return []
    yf_map = {t: (ticker_para_yfinance(t) or t) for t in disp}
    yf_list = list(dict.fromkeys([yf_map[t] for t in disp]))

    try:
        # yfinance pode imprimir mensagens no console; suprimimos para não poluir logs do Streamlit.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            df = yf.download(
                tickers=yf_list,
                period="5d",
                interval="1d",
                group_by="ticker",
                auto_adjust=False,
                threads=True,
                progress=False,
            )
    except Exception:
        return []

    if df is None or getattr(df, "empty", True):
        return []

    valid_yf: set[str] = set()
    try:
        if isinstance(df.columns, pd.MultiIndex):
            # MultiIndex: (ticker, campo)
            for t in yf_list:
                try:
                    sub = df[t]
                    close = None
                    if isinstance(sub, pd.DataFrame):
                        if "Close" in sub.columns:
                            close = sub["Close"]
                        elif "Adj Close" in sub.columns:
                            close = sub["Adj Close"]
                    if close is not None and pd.to_numeric(close, errors="coerce").dropna().shape[0] > 0:
                        valid_yf.add(t)
                except Exception:
                    continue
        else:
            # Single ticker
            close = None
            if "Close" in df.columns:
                close = df["Close"]
            elif "Adj Close" in df.columns:
                close = df["Adj Close"]
            if close is not None and pd.to_numeric(close, errors="coerce").dropna().shape[0] > 0:
                valid_yf.add(yf_list[0])
    except Exception:
        return []

    # Voltar para display (mantém somente os que validaram)
    out = [t for t in disp if (yf_map.get(t) in valid_yf)]
    # remover duplicados preservando ordem
    seen = set()
    out = [t for t in out if not (t.upper() in seen or seen.add(t.upper()))]
    return out


def _filtrar_sugestoes_validas(sugestoes: list[str], limite: int = 250) -> list[str]:
    """Filtra sugestões com validação em lote, limitando custo."""
    if not sugestoes:
        return []
    base = [s for s in sugestoes if str(s).strip()]
    base = list(dict.fromkeys([str(s).strip() for s in base]))
    if not base:
        return []
    subset = base[:limite]
    valid = _validar_tickers_em_lote(tuple(subset))
    return valid


def _quarter_end_for_today() -> pd.Timestamp:
    now = pd.Timestamp.now().normalize()
    try:
        return pd.Period(now, freq="Q").end_time.normalize()
    except Exception:
        q = ((now.month - 1) // 3) + 1
        if q == 1:
            return pd.Timestamp(year=now.year, month=3, day=31)
        if q == 2:
            return pd.Timestamp(year=now.year, month=6, day=30)
        if q == 3:
            return pd.Timestamp(year=now.year, month=9, day=30)
        return pd.Timestamp(year=now.year, month=12, day=31)


def _year_end_for_current_year() -> pd.Timestamp:
    y = pd.Timestamp.now().year
    return pd.Timestamp(year=y, month=12, day=31)


def _month_end_for_today() -> pd.Timestamp:
    now = pd.Timestamp.now().normalize()
    try:
        return pd.Period(now, freq="M").end_time.normalize()
    except Exception:
        return (now + pd.offsets.MonthEnd(0)).normalize()


def _expand_quarterly_with_annual(q_metrics: pd.DataFrame, a_metrics: pd.DataFrame) -> pd.DataFrame:
    """Replica valores anuais nos 4 trimestres do mesmo ano para preencher buracos/anos antigos.

    Regra: o que existir no trimestral prevalece; o anual só preenche períodos sem dado.
    """
    q = q_metrics.copy() if isinstance(q_metrics, pd.DataFrame) else pd.DataFrame()
    a = a_metrics.copy() if isinstance(a_metrics, pd.DataFrame) else pd.DataFrame()

    if q.empty and a.empty:
        return pd.DataFrame()

    if not q.empty:
        q["Data"] = pd.to_datetime(q.get("Data"), errors="coerce")
        if pd.api.types.is_datetime64tz_dtype(q["Data"]):
            q["Data"] = q["Data"].dt.tz_localize(None)
        q = q.dropna(subset=["Data"]).sort_values("Data")

    if a.empty:
        return q

    a["Data"] = pd.to_datetime(a.get("Data"), errors="coerce")
    if pd.api.types.is_datetime64tz_dtype(a["Data"]):
        a["Data"] = a["Data"].dt.tz_localize(None)
    a = a.dropna(subset=["Data"]).sort_values("Data")
    if a.empty:
        return q

    a_year = a.set_index("Data").resample("YE").last()
    rows = []
    for dt, row in a_year.iterrows():
        if pd.isna(dt):
            continue
        y = int(pd.Timestamp(dt).year)
        q_dates = [
            pd.Timestamp(year=y, month=3, day=31),
            pd.Timestamp(year=y, month=6, day=30),
            pd.Timestamp(year=y, month=9, day=30),
            pd.Timestamp(year=y, month=12, day=31),
        ]
        for qd in q_dates:
            r = row.to_dict()
            r["Data"] = qd
            rows.append(r)

    a_quarters = pd.DataFrame(rows)
    if a_quarters.empty:
        return q

    if q.empty:
        combined = a_quarters
    else:
        qa = a_quarters.set_index("Data")
        qq = q.set_index("Data")
        # Trimestral SEMPRE prevalece; anual só completa períodos sem dado.
        combined = qq.combine_first(qa).reset_index()

    combined["Data"] = pd.to_datetime(combined["Data"], errors="coerce")
    combined = combined.dropna(subset=["Data"]).sort_values("Data")
    return combined


def _period_label(ts: pd.Timestamp, periodicidade: str) -> str:
    if periodicidade == "Mensal":
        return _format_month_label(ts)
    if periodicidade == "Trimestral":
        return f"T{((ts.month - 1) // 3) + 1}/{ts.year}"
    return ts.strftime("%Y")


def _build_indicators_periodic(
    periodicidade: str,
    price_df: pd.DataFrame,
    dividends_df: pd.DataFrame,
    q_metrics: pd.DataFrame,
    a_metrics: pd.DataFrame,

) -> pd.DataFrame:
    """Monta indicadores em frequência Mensal/Trimestral/Anual, sem inventar períodos vazios."""
    if periodicidade not in ["Mensal", "Trimestral", "Anual"]:
        return pd.DataFrame()

    # Mensal: usa base mensal (preço mensal + dividendos) e injeta métricas trimestrais/anuais quando existirem
    if periodicidade == "Mensal":
        q_full = _expand_quarterly_with_annual(q_metrics, a_metrics)
        base = _monthlyize_indicators(price_df, dividends_df, q_full, a_metrics, None)
        if base is None or base.empty:
            return pd.DataFrame()
        base = base.rename(columns={"Mês": "Data"})
        base["Data"] = pd.to_datetime(base.get("Data"), errors="coerce")
        if pd.api.types.is_datetime64tz_dtype(base["Data"]):
            base["Data"] = base["Data"].dt.tz_localize(None)
        base = base.dropna(subset=["Data"]).sort_values("Data")
        base["Período"] = base["Data"].apply(lambda x: _period_label(pd.to_datetime(x), "Mensal") if pd.notna(x) else "")

        # Projeção mensal: recalcular com preço atual usando o último trimestre disponível
        try:
            proj_dt = _month_end_for_today()
            last_dt = pd.to_datetime(base["Data"], errors="coerce").dropna().max()

            col_last = _pick_price_column(price_df) if isinstance(price_df, pd.DataFrame) else None
            last_px = (
                pd.to_numeric(price_df[col_last], errors="coerce").dropna().iloc[-1]
                if isinstance(price_df, pd.DataFrame) and (not price_df.empty) and col_last and col_last in price_df.columns
                else None
            )

            q_src = q_metrics.copy() if isinstance(q_metrics, pd.DataFrame) else pd.DataFrame()
            if not q_src.empty:
                q_src["Data"] = pd.to_datetime(q_src.get("Data"), errors="coerce")
                if pd.api.types.is_datetime64tz_dtype(q_src["Data"]):
                    q_src["Data"] = q_src["Data"].dt.tz_localize(None)
                q_src = q_src.dropna(subset=["Data"]).sort_values("Data")

            # fallback: anual
            a_src = a_metrics.copy() if isinstance(a_metrics, pd.DataFrame) else pd.DataFrame()
            if not a_src.empty:
                a_src["Data"] = pd.to_datetime(a_src.get("Data"), errors="coerce")
                if pd.api.types.is_datetime64tz_dtype(a_src["Data"]):
                    a_src["Data"] = a_src["Data"].dt.tz_localize(None)
                a_src = a_src.dropna(subset=["Data"]).sort_values("Data")

            if (
                proj_dt is not None
                and (last_dt is not None)
                and pd.notna(last_dt)
                and pd.Timestamp(proj_dt) > pd.Timestamp(last_dt)
                and isinstance(last_px, (int, float, np.number))
                and np.isfinite(float(last_px))
                and ((not q_src.empty) or (not a_src.empty))
            ):
                src = (q_src.iloc[-1].to_dict() if not q_src.empty else a_src.iloc[-1].to_dict())
                proj = {c: np.nan for c in base.columns}
                proj["Data"] = proj_dt
                proj["Preço"] = float(last_px)

                # DY 12m com preço atual
                if isinstance(dividends_df, pd.DataFrame) and not dividends_df.empty:
                    d = dividends_df.copy()
                    d["Data"] = pd.to_datetime(d.get("Data"), errors="coerce")
                    if pd.api.types.is_datetime64tz_dtype(d["Data"]):
                        d["Data"] = d["Data"].dt.tz_localize(None)
                    d["Dividendo"] = pd.to_numeric(d.get("Dividendo"), errors="coerce")
                    d = d.dropna(subset=["Data", "Dividendo"]).sort_values("Data")
                    cutoff = pd.Timestamp.now().normalize() - pd.DateOffset(months=12)
                    div_12m = float(d.loc[d["Data"] >= cutoff, "Dividendo"].sum()) if not d.empty else 0.0
                    proj["Dividend Yield"] = (div_12m / float(last_px)) if float(last_px) > 0 else np.nan

                bvps = _as_float(src.get("BVPS"))
                if bvps and bvps > 0:
                    proj["P/VP"] = float(last_px) / bvps

                eps_ttm = _as_float(src.get("EPS TTM"))
                eps = _as_float(src.get("EPS"))
                if eps_ttm and eps_ttm > 0:
                    proj["P/L"] = float(last_px) / eps_ttm
                elif eps and eps > 0:
                    proj["P/L"] = float(last_px) / eps

                proj["Período"] = _period_label(pd.to_datetime(proj_dt), "Mensal")
                base = pd.concat([base, pd.DataFrame([proj])], ignore_index=True)
                base = base.drop_duplicates(subset=["Data"], keep="last").sort_values("Data")
        except Exception:
            pass

        return base

    freq = "QE" if periodicidade == "Trimestral" else "YE"
    metrics = q_metrics if periodicidade == "Trimestral" else a_metrics
    if metrics is None or metrics.empty:
        # fallback: se trimestral vazio mas anual existe, replica anual nos trimestres
        if periodicidade == "Trimestral" and isinstance(a_metrics, pd.DataFrame) and not a_metrics.empty:
            metrics = _expand_quarterly_with_annual(pd.DataFrame(), a_metrics)
        else:
            return pd.DataFrame()

    # Se trimestral for curto, complementa com anual (anos antigos / trimestres vazios)
    if periodicidade == "Trimestral" and isinstance(a_metrics, pd.DataFrame) and not a_metrics.empty:
        metrics = _expand_quarterly_with_annual(metrics, a_metrics)

    m = metrics.copy()
    m["Data"] = pd.to_datetime(m.get("Data"), errors="coerce")
    if pd.api.types.is_datetime64tz_dtype(m["Data"]):
        m["Data"] = m["Data"].dt.tz_localize(None)
    m = m.dropna(subset=["Data"]).sort_values("Data").set_index("Data")
    m = m.resample(freq).last()

    # Preço do período
    p = price_df.copy() if isinstance(price_df, pd.DataFrame) else pd.DataFrame()
    if not p.empty and "Data" in p.columns:
        p["Data"] = pd.to_datetime(p["Data"], errors="coerce")
        if pd.api.types.is_datetime64tz_dtype(p["Data"]):
            p["Data"] = p["Data"].dt.tz_localize(None)
        col_price = _pick_price_column(p)
        if col_price:
            p[col_price] = pd.to_numeric(p[col_price], errors="coerce")
            p = p.dropna(subset=["Data", col_price]).sort_values("Data").set_index("Data")
            p = p.resample(freq).last().rename(columns={col_price: "Preço"})[["Preço"]]
        else:
            p = pd.DataFrame(index=m.index)
    else:
        p = pd.DataFrame(index=m.index)

    out = m.join(p, how="left")

    # Dividend Yield (12m) no fim do período (se houver dividendos)
    if isinstance(dividends_df, pd.DataFrame) and not dividends_df.empty and "Preço" in out.columns:
        d = dividends_df.copy()
        d["Data"] = pd.to_datetime(d.get("Data"), errors="coerce")
        if pd.api.types.is_datetime64tz_dtype(d["Data"]):
            d["Data"] = d["Data"].dt.tz_localize(None)
        d["Dividendo"] = pd.to_numeric(d.get("Dividendo"), errors="coerce")
        d = d.dropna(subset=["Data", "Dividendo"]).sort_values("Data")
        if not d.empty:
            yields = []
            for dt in out.index:
                cutoff = pd.Timestamp(dt) - pd.DateOffset(months=12)
                div_12m = d.loc[(d["Data"] > cutoff) & (d["Data"] <= dt), "Dividendo"].sum()
                px = _as_float(out.loc[dt, "Preço"]) if "Preço" in out.columns else None
                y = (float(div_12m) / float(px)) if px and px > 0 else np.nan
                yields.append(y)
            out["Dividend Yield"] = yields

    # P/VP e P/L
    if "BVPS" in out.columns and "Preço" in out.columns:
        out["P/VP"] = np.where(out["BVPS"].notna() & (out["BVPS"] > 0) & out["Preço"].notna(), out["Preço"] / out["BVPS"], np.nan)

    if "Preço" in out.columns:
        if periodicidade == "Trimestral" and "EPS TTM" in out.columns:
            out["P/L"] = np.where(out["EPS TTM"].notna() & (out["EPS TTM"] > 0) & out["Preço"].notna(), out["Preço"] / out["EPS TTM"], np.nan)
            # Fallback: quando EPS TTM não existir/for NaN, tenta EPS anual
            if "EPS" in out.columns:
                pl_eps = np.where(out["EPS"].notna() & (out["EPS"] > 0) & out["Preço"].notna(), out["Preço"] / out["EPS"], np.nan)
                out["P/L"] = pd.Series(out["P/L"], index=out.index).combine_first(pd.Series(pl_eps, index=out.index))
        elif periodicidade == "Anual" and "EPS" in out.columns:
            out["P/L"] = np.where(out["EPS"].notna() & (out["EPS"] > 0) & out["Preço"].notna(), out["Preço"] / out["EPS"], np.nan)

    # Complemento no modo Anual (anos sem relatório anual):
    # usa o último trimestre realizado e recalcula com preço do fechamento do ano (ou cotação atual no ano corrente).
    try:
        if periodicidade == "Anual":
            now = pd.Timestamp.now()
            current_year = int(now.year)

            # Base trimestral (fonte para anos sem anual)
            q_src = q_metrics.copy() if isinstance(q_metrics, pd.DataFrame) else pd.DataFrame()
            if not q_src.empty:
                q_src["Data"] = pd.to_datetime(q_src.get("Data"), errors="coerce")
                if pd.api.types.is_datetime64tz_dtype(q_src["Data"]):
                    q_src["Data"] = q_src["Data"].dt.tz_localize(None)
                q_src = q_src.dropna(subset=["Data"]).sort_values("Data")

            # Preços para lookup
            p_src = price_df.copy() if isinstance(price_df, pd.DataFrame) else pd.DataFrame()
            col_last = _pick_price_column(p_src) if isinstance(p_src, pd.DataFrame) else None
            if isinstance(p_src, pd.DataFrame) and (not p_src.empty) and ("Data" in p_src.columns) and col_last and col_last in p_src.columns:
                p_src["Data"] = pd.to_datetime(p_src.get("Data"), errors="coerce")
                if pd.api.types.is_datetime64tz_dtype(p_src["Data"]):
                    p_src["Data"] = p_src["Data"].dt.tz_localize(None)
                p_src[col_last] = pd.to_numeric(p_src[col_last], errors="coerce")
                p_src = p_src.dropna(subset=["Data", col_last]).sort_values("Data")
            else:
                p_src = pd.DataFrame()

            def _price_asof(dt: pd.Timestamp) -> float | None:
                if p_src.empty or not col_last:
                    return None
                dt = pd.to_datetime(dt, errors="coerce")
                if pd.isna(dt):
                    return None
                hit = p_src[p_src["Data"] <= dt]
                if hit.empty:
                    return None
                v = hit.iloc[-1][col_last]
                return float(v) if pd.notna(v) else None

            def _div_yield_12m_at(dt: pd.Timestamp, px: float) -> float | None:
                if not isinstance(px, (int, float, np.number)) or not np.isfinite(float(px)) or float(px) <= 0:
                    return None
                if not (isinstance(dividends_df, pd.DataFrame) and not dividends_df.empty):
                    return None
                d = dividends_df.copy()
                d["Data"] = pd.to_datetime(d.get("Data"), errors="coerce")
                if pd.api.types.is_datetime64tz_dtype(d["Data"]):
                    d["Data"] = d["Data"].dt.tz_localize(None)
                d["Dividendo"] = pd.to_numeric(d.get("Dividendo"), errors="coerce")
                d = d.dropna(subset=["Data", "Dividendo"]).sort_values("Data")
                if d.empty:
                    return None
                cutoff = pd.Timestamp(dt).normalize() - pd.DateOffset(months=12)
                div_12m = float(d.loc[(d["Data"] > cutoff) & (d["Data"] <= dt), "Dividendo"].sum())
                return (div_12m / float(px)) if float(px) > 0 else None

            # De onde começa a série anual
            start_year = None
            if out.index is not None and len(out.index) > 0:
                try:
                    start_year = int(pd.Timestamp(out.index.min()).year)
                except Exception:
                    start_year = None
            if start_year is None and not q_src.empty:
                try:
                    start_year = int(pd.to_datetime(q_src["Data"], errors="coerce").dropna().min().year)
                except Exception:
                    start_year = None
            if start_year is None:
                start_year = current_year

            years_with_annual = {int(pd.Timestamp(ix).year) for ix in out.index}
            for y in range(start_year, current_year + 1):
                # Regra: anual sempre tem prioridade no modo anual
                if y in years_with_annual:
                    continue

                year_end = pd.Timestamp(year=y, month=12, day=31)
                cutoff_dt = year_end if y < current_year else now

                # Fonte: último trimestre até o cutoff
                src = {}
                if not q_src.empty:
                    hit_q = q_src[q_src["Data"] <= cutoff_dt]
                    if not hit_q.empty:
                        src = hit_q.iloc[-1].to_dict()

                # Preço: fechamento do ano (ano passado) ou último fechamento (ano atual)
                px = _price_asof(year_end) if y < current_year else _price_asof(now)
                if px is None:
                    continue

                proj_dt = pd.Timestamp(year=y, month=12, day=31, hour=12)
                proj = {c: np.nan for c in out.columns}
                proj["Preço"] = float(px)

                for k in ["BVPS", "EPS TTM", "EPS"]:
                    if k in out.columns and k in src:
                        proj[k] = src.get(k)

                dy = _div_yield_12m_at(year_end if y < current_year else now, float(px))
                if dy is not None:
                    proj["Dividend Yield"] = dy

                bvps = _as_float(src.get("BVPS"))
                if bvps and bvps > 0:
                    proj["P/VP"] = float(px) / bvps

                eps_ttm = _as_float(src.get("EPS TTM"))
                eps = _as_float(src.get("EPS"))
                if eps_ttm and eps_ttm > 0:
                    proj["P/L"] = float(px) / eps_ttm
                elif eps and eps > 0:
                    proj["P/L"] = float(px) / eps

                out.loc[proj_dt] = pd.Series(proj)
    except Exception:
        pass

    out = out.reset_index().rename(columns={"index": "Data"})
    out["Data"] = pd.to_datetime(out.get("Data"), errors="coerce")
    if pd.api.types.is_datetime64tz_dtype(out["Data"]):
        out["Data"] = out["Data"].dt.tz_localize(None)
    # Normalizar e fixar no meio-dia para evitar deslocamento por timezone no browser.
    out["Data"] = out["Data"].dt.normalize() + pd.Timedelta(hours=12)
    out = out.dropna(subset=["Data"]).sort_values("Data")
    out["Período"] = out["Data"].apply(lambda x: _period_label(pd.to_datetime(x), periodicidade) if pd.notna(x) else "")
    return out


@st.cache_data(ttl=600, show_spinner=False)
def _yf_info(ticker_yf: str) -> dict:
    try:
        return yf.Ticker(ticker_yf).info or {}
    except Exception:
        return {}


@st.cache_data(ttl=600, show_spinner=False)
def _yf_history_price(ticker_yf: str, period: str) -> pd.DataFrame:
    try:
        df = yf.Ticker(ticker_yf).history(period=period, auto_adjust=False)
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.reset_index().rename(columns={"Date": "Data"})
        df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
        if pd.api.types.is_datetime64tz_dtype(df["Data"]):
            df["Data"] = df["Data"].dt.tz_localize(None)
        return df.dropna(subset=["Data"]).sort_values("Data")
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False)
def _yf_dividends(ticker_yf: str) -> pd.DataFrame:
    try:
        s = yf.Ticker(ticker_yf).dividends
        if s is None or len(s) == 0:
            return pd.DataFrame(columns=["Data", "Dividendo"])
        df = s.reset_index()
        df.columns = ["Data", "Dividendo"]
        df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
        if pd.api.types.is_datetime64tz_dtype(df["Data"]):
            df["Data"] = df["Data"].dt.tz_localize(None)
        df["Dividendo"] = pd.to_numeric(df["Dividendo"], errors="coerce")
        return df.dropna(subset=["Data"]).sort_values("Data")
    except Exception:
        return pd.DataFrame(columns=["Data", "Dividendo"])


@st.cache_data(ttl=3600, show_spinner=False)
def _yf_statements(ticker_yf: str) -> dict:
    """Busca demonstrativos anuais e trimestrais disponíveis via yfinance."""
    tk = yf.Ticker(ticker_yf)

    out = {
        "income_annual": pd.DataFrame(),
        "income_quarterly": pd.DataFrame(),
        "balance_annual": pd.DataFrame(),
        "balance_quarterly": pd.DataFrame(),
        "cash_annual": pd.DataFrame(),
        "cash_quarterly": pd.DataFrame(),
        "earnings_annual": pd.DataFrame(),
        "earnings_quarterly": pd.DataFrame(),
    }

    # Os nomes variam conforme versão do yfinance; tentamos várias propriedades.
    attr_candidates = {
        "income_annual": ["financials", "income_stmt"],
        "income_quarterly": ["quarterly_financials", "quarterly_income_stmt"],
        "balance_annual": ["balance_sheet"],
        "balance_quarterly": ["quarterly_balance_sheet"],
        "cash_annual": ["cashflow", "cashflow_stmt"],
        "cash_quarterly": ["quarterly_cashflow", "quarterly_cashflow_stmt"],
        "earnings_annual": ["earnings"],
        "earnings_quarterly": ["quarterly_earnings"],
    }

    for key, attrs in attr_candidates.items():
        for attr in attrs:
            try:
                df = getattr(tk, attr)
                if isinstance(df, pd.DataFrame) and not df.empty:
                    out[key] = df
                    break
            except Exception:
                continue

    return out


def _compute_quarterly_metrics(
    income_q: pd.DataFrame,
    balance_q: pd.DataFrame,
    shares_outstanding: float | None,
) -> pd.DataFrame:
    """Monta métricas trimestrais e depois permitirá reamostrar para mensal."""
    income_q = _to_datetime_index_cols(income_q)
    balance_q = _to_datetime_index_cols(balance_q)

    if income_q.empty and balance_q.empty:
        return pd.DataFrame()

    # Normalizar índices
    if not income_q.empty:
        income_q = income_q.copy()
        income_q.index = income_q.index.astype(str)
    if not balance_q.empty:
        balance_q = balance_q.copy()
        balance_q.index = balance_q.index.astype(str)

    # Candidatos comuns no yfinance
    revenue = _pick_first(income_q, ["Total Revenue", "TotalRevenue", "Revenue"])
    net_income = _pick_first(income_q, ["Net Income", "NetIncome", "Net Income Applicable To Common Shares"])
    ebitda = _pick_first(income_q, ["EBITDA", "Ebitda"])

    equity = _pick_first(balance_q, ["Total Stockholder Equity", "TotalStockholderEquity", "Stockholders Equity"])
    total_debt = _pick_first(balance_q, ["Total Debt", "TotalDebt"])

    # Datas disponíveis: união de colunas
    dates = pd.Index([])
    if not revenue.empty:
        dates = dates.union(revenue.index)
    if not equity.empty:
        dates = dates.union(equity.index)

    dates = pd.to_datetime(dates, errors="coerce")
    if getattr(dates, "tz", None) is not None:
        dates = dates.tz_localize(None)
    dates = dates.dropna().sort_values()
    if len(dates) == 0:
        return pd.DataFrame()

    df = pd.DataFrame(index=dates)

    def _reindex(s: pd.Series) -> pd.Series:
        if s is None or len(s) == 0:
            return pd.Series(index=dates, dtype=float)
        s2 = s.copy()
        s2.index = pd.to_datetime(s2.index, errors="coerce")
        if getattr(s2.index, "tz", None) is not None:
            s2.index = s2.index.tz_localize(None)
        s2 = s2.dropna()
        return s2.reindex(dates)

    df["Receita"] = _reindex(revenue)
    df["Lucro Líquido"] = _reindex(net_income)
    df["EBITDA"] = _reindex(ebitda)
    df["Patrimônio Líquido"] = _reindex(equity)
    df["Dívida Total"] = _reindex(total_debt)

    # Métricas derivadas
    df["Margem Líquida"] = np.where(
        df["Receita"].notna() & (df["Receita"] != 0) & df["Lucro Líquido"].notna(),
        df["Lucro Líquido"] / df["Receita"],
        np.nan,
    )

    df["Dívida/Patrimônio"] = np.where(
        df["Patrimônio Líquido"].notna() & (df["Patrimônio Líquido"] != 0) & df["Dívida Total"].notna(),
        df["Dívida Total"] / df["Patrimônio Líquido"],
        np.nan,
    )

    df["ROE"] = np.where(
        df["Patrimônio Líquido"].notna() & (df["Patrimônio Líquido"] != 0) & df["Lucro Líquido"].notna(),
        df["Lucro Líquido"] / df["Patrimônio Líquido"],
        np.nan,
    )

    # Book value per share e EPS aproximado (TTM) quando houver shares
    if shares_outstanding and shares_outstanding > 0:
        df["BVPS"] = df["Patrimônio Líquido"] / float(shares_outstanding)

        # EPS TTM aproximado via soma dos 4 últimos trimestres
        ni = df["Lucro Líquido"].copy()
        ni_ttm = ni.rolling(4, min_periods=1).sum()
        df["EPS TTM"] = ni_ttm / float(shares_outstanding)

    return df.reset_index().rename(columns={"index": "Data"})


def _monthlyize_indicators(
    price_df: pd.DataFrame,
    dividends_df: pd.DataFrame,
    q_metrics: pd.DataFrame,
    a_metrics: pd.DataFrame,
    shares_outstanding: float | None,
) -> pd.DataFrame:
    """Cria uma base mensal com preço e indicadores (método melhor esforço)."""
    if price_df is None or price_df.empty:
        return pd.DataFrame()

    p = price_df.copy()
    p = p.dropna(subset=["Data"]).sort_values("Data")
    if pd.api.types.is_datetime64tz_dtype(p["Data"]):
        p["Data"] = p["Data"].dt.tz_localize(None)
    p["Close"] = pd.to_numeric(p.get("Close"), errors="coerce")
    p = p.dropna(subset=["Close"])

    p = p.set_index("Data")
    p_m = p.resample("ME").last()[["Close"]].rename(columns={"Close": "Preço"})

    # Dividendos: soma mensal + trailing 12m
    div_m = pd.DataFrame(index=p_m.index)
    if dividends_df is not None and not dividends_df.empty:
        d = dividends_df.copy()
        d = d.dropna(subset=["Data"]).sort_values("Data")
        if pd.api.types.is_datetime64tz_dtype(d["Data"]):
            d["Data"] = d["Data"].dt.tz_localize(None)
        d["Dividendo"] = pd.to_numeric(d["Dividendo"], errors="coerce")
        d = d.dropna(subset=["Dividendo"])
        d = d.set_index("Data").resample("ME").sum().rename(columns={"Dividendo": "Dividendos (mês)"})
        div_m = div_m.join(d, how="left")
    div_m["Dividendos (mês)"] = div_m.get("Dividendos (mês)").fillna(0.0)
    div_m["Dividendos (12m)"] = div_m["Dividendos (mês)"].rolling(12, min_periods=1).sum()
    div_m["Dividend Yield"] = np.where(
        p_m["Preço"].notna() & (p_m["Preço"] > 0),
        div_m["Dividendos (12m)"] / p_m["Preço"],
        np.nan,
    )

    out = p_m.join(div_m, how="left")

    # Métricas trimestrais -> mensal (ffill)
    if q_metrics is not None and not q_metrics.empty:
        qm = q_metrics.copy()
        qm["Data"] = pd.to_datetime(qm["Data"], errors="coerce")
        if pd.api.types.is_datetime64tz_dtype(qm["Data"]):
            qm["Data"] = qm["Data"].dt.tz_localize(None)
        qm = qm.dropna(subset=["Data"]).sort_values("Data").set_index("Data")
        qm_m = qm.resample("ME").last()
        out = out.join(qm_m, how="left")

    # Métricas anuais -> mensal (ffill) e preencher lacunas (especialmente anos anteriores)
    if a_metrics is not None and not a_metrics.empty:
        am = a_metrics.copy()
        am["Data"] = pd.to_datetime(am["Data"], errors="coerce")
        if pd.api.types.is_datetime64tz_dtype(am["Data"]):
            am["Data"] = am["Data"].dt.tz_localize(None)
        am = am.dropna(subset=["Data"]).sort_values("Data").set_index("Data")
        am_m = am.resample("ME").last()

        for col in am_m.columns:
            if col not in out.columns:
                out[col] = am_m[col]
            else:
                out[col] = out[col].combine_first(am_m[col])

    # P/VP e P/L aproximados
    if "BVPS" in out.columns:
        out["P/VP"] = np.where(out["BVPS"].notna() & (out["BVPS"] > 0), out["Preço"] / out["BVPS"], np.nan)

    if "EPS TTM" in out.columns:
        out["P/L"] = np.where(out["EPS TTM"].notna() & (out["EPS TTM"] > 0), out["Preço"] / out["EPS TTM"], np.nan)

    # Preencher lacunas de P/L usando EPS anual (quando disponível)
    if "EPS" in out.columns:
        pl_eps = np.where(out["EPS"].notna() & (out["EPS"] > 0), out["Preço"] / out["EPS"], np.nan)
        pl_eps = pd.Series(pl_eps, index=out.index)
        if "P/L" not in out.columns:
            out["P/L"] = pl_eps
        else:
            out["P/L"] = out["P/L"].combine_first(pl_eps)

    out = out.reset_index().rename(columns={"Data": "Mês"})
    return out


def _export_excel_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for name, df in sheets.items():
            safe = (name or "Sheet")[:31]
            (df if isinstance(df, pd.DataFrame) else pd.DataFrame()).to_excel(writer, index=False, sheet_name=safe)
    return output.getvalue()


st.title("📊 Análise Fundamentalista (yfinance)")

with st.sidebar:
    st.subheader("🔎 Seleção")

    # Lista sugerida de tickers via cache local
    cache_df = _load_ticker_info_cache(TICKER_INFO_PATH)
    sugestoes = []
    if isinstance(cache_df, pd.DataFrame) and (not cache_df.empty) and "Ticker" in cache_df.columns:
        sugestoes = sorted(cache_df["Ticker"].dropna().astype(str).str.strip().unique().tolist())

    somente_validos = st.checkbox("Mostrar somente tickers válidos", value=True)
    sugestoes_validas = sugestoes
    if somente_validos and sugestoes:
        sugestoes_validas = _filtrar_sugestoes_validas(sugestoes)

    modo = st.radio("Modo", ["Selecionar", "Digitar"], horizontal=True)

    if modo == "Selecionar" and sugestoes_validas:
        ticker_in = st.selectbox("Ticker", sugestoes_validas, index=0)
    else:
        ticker_in = st.text_input("Ticker", value="PETR4")

    periodo = st.selectbox("Período de preço", ["6mo", "1y", "2y", "5y", "10y", "max"], index=3)

    comparar_com = st.multiselect(
        "Comparar preços com",
        options=[t for t in sugestoes_validas if t],
        default=[],
        help="Seleciona outros tickers para sobrepor no gráfico de preços.",
    )
    comparar_com_txt = st.text_input(
        "Comparar (digite tickers separados por vírgula)",
        value="",
        help="Ex.: PETR4, VALE3, AAPL",
    )

    st.markdown("---")
    if st.button("🔄 Atualizar dados (limpar cache)"):
        st.cache_data.clear()
        st.rerun()


ticker_base = extrair_ticker(ticker_in) or ""
if not ticker_base:
    st.info("Informe um ticker para iniciar.")
    st.stop()

ticker_yf = ticker_para_yfinance(ticker_base) or ticker_base

# Atualizar cache local de setor/segmento para o ticker selecionado
try:
    atualizar_cache_tickers([ticker_base])
except Exception:
    pass

info = _yf_info(ticker_yf)
price_df = _yf_history_price(ticker_yf, periodo)
dividends_df = _yf_dividends(ticker_yf)
statements = _yf_statements(ticker_yf)

# Header com identificação
nome = info.get("shortName") or info.get("longName") or ticker_base
setor = info.get("sector")
segmento = info.get("industry")
moeda = info.get("currency")

col_a, col_b, col_c, col_d = st.columns([2, 1, 1, 1])
with col_a:
    st.subheader(f"{nome} ({ticker_yf})")
    if setor or segmento:
        st.caption(f"Setor: {setor or '—'} | Segmento: {segmento or '—'}")
with col_b:
    st.metric("Moeda", moeda or "—")
with col_c:
    st.metric("Market Cap", f"{info.get('marketCap'):,}" if info.get("marketCap") else "—")
with col_d:
    st.metric("Atualizado em", datetime.now().strftime("%d/%m/%Y %H:%M"))

# Alertas de disponibilidade
if price_df.empty:
    st.error("Sem histórico de preços disponível para este ticker no yfinance.")
    st.stop()

with st.expander("📈 Preço", expanded=True):
    # Controles (também no corpo para ficar sempre visível)
    with st.expander("Comparação de preços", expanded=False):
        comparar_corpo = st.multiselect(
            "Comparar com",
            options=[t for t in sugestoes_validas if t],
            default=[],
        )
        comparar_corpo_txt = st.text_input(
            "Comparar com (texto)",
            value="",
        )

    tickers_comparacao = []
    try:
        from_sidebar = list(comparar_com or [])
        from_body = list(comparar_corpo or [])

        txt_all = ",".join(
            [
                (comparar_com_txt or ""),
                (comparar_corpo_txt or ""),
            ]
        )
        from_txt = [t.strip() for t in txt_all.split(",") if t.strip()]

        tickers_comparacao = [
            t for t in (from_sidebar + from_body + from_txt) if t and t.upper() != ticker_base.upper()
        ]
        # remover duplicados preservando ordem
        seen = set()
        tickers_comparacao = [t for t in tickers_comparacao if not (t.upper() in seen or seen.add(t.upper()))]
    except Exception:
        tickers_comparacao = []

    price_frames = []

    base_col = _pick_price_column(price_df)
    if not base_col:
        st.error("Histórico de preços retornou sem coluna de preço (Close/Adj Close).")
    else:
        base_plot = price_df[["Data", base_col]].rename(columns={base_col: "Preço"}).copy()
        base_plot["Ticker"] = ticker_base
        price_frames.append(base_plot)

        for t in tickers_comparacao:
            ty = ticker_para_yfinance(t) or t
            df_t = _yf_history_price(ty, periodo)
            col_t = _pick_price_column(df_t)
            if df_t is None or df_t.empty or not col_t:
                continue
            dft = df_t[["Data", col_t]].rename(columns={col_t: "Preço"}).copy()
            dft["Ticker"] = t
            price_frames.append(dft)

        df_price_all = pd.concat(price_frames, ignore_index=True) if price_frames else pd.DataFrame()
        if not df_price_all.empty:
            df_price_all["Data"] = pd.to_datetime(df_price_all["Data"], errors="coerce")
            if pd.api.types.is_datetime64tz_dtype(df_price_all["Data"]):
                df_price_all["Data"] = df_price_all["Data"].dt.tz_localize(None)
            df_price_all["Preço"] = pd.to_numeric(df_price_all["Preço"], errors="coerce")
            df_price_all = df_price_all.dropna(subset=["Data", "Preço"]).sort_values(["Data", "Ticker"])

        if df_price_all.empty:
            st.error("Não foi possível montar o gráfico de preços (sem dados numéricos após limpeza).")
        else:
            fig_price = px.line(
                df_price_all,
                x="Data",
                y="Preço",
                color="Ticker",
                title="Histórico de Preços (comparativo)",
                labels={"Preço": "Preço"},
            )

            # Hover sempre com 2 casas
            fig_price.update_traces(hovertemplate="%{x|%d/%m/%Y}<br>%{y:.2f}<extra></extra>")

            # Rótulo apenas no último ponto quando houver só uma linha (evita milhares de textos)
            if len(fig_price.data) == 1:
                df_last = df_price_all.dropna(subset=["Data", "Preço"]).sort_values("Data")
                if not df_last.empty:
                    last = df_last.iloc[-1]
                    fig_price.add_trace(
                        go.Scatter(
                            x=[last["Data"]],
                            y=[last["Preço"]],
                            mode="markers+text",
                            text=[f"{float(last['Preço']):.2f}"],
                            textposition="top center",
                            textfont_size=8,
                            marker=dict(size=6),
                            showlegend=False,
                            hoverinfo="skip",
                        )
                    )

            fig_price.update_layout(margin=dict(t=60))
            st.plotly_chart(fig_price, use_container_width=True)

with st.expander("💸 Dividendos", expanded=False):
    # Próximas datas (quando disponíveis no yfinance)
    try:
        now = pd.Timestamp.now().normalize()
        future_rows = []
        ex_dt = _parse_yf_date(info.get("exDividendDate"))
        div_dt = _parse_yf_date(info.get("dividendDate"))
        if ex_dt is not None and pd.notna(ex_dt) and ex_dt.tzinfo is not None:
            ex_dt = ex_dt.tz_localize(None)
        if div_dt is not None and pd.notna(div_dt) and div_dt.tzinfo is not None:
            div_dt = div_dt.tz_localize(None)

        if ex_dt is not None and pd.notna(ex_dt) and ex_dt.normalize() >= now:
            future_rows.append({"Evento": "Ex-dividend", "Data": ex_dt.normalize()})
        if div_dt is not None and pd.notna(div_dt) and div_dt.normalize() >= now:
            future_rows.append({"Evento": "Pagamento (dividendDate)", "Data": div_dt.normalize()})

        if future_rows:
            df_future = pd.DataFrame(future_rows).sort_values("Data")
            df_future["Data"] = pd.to_datetime(df_future["Data"], errors="coerce").dt.strftime("%d/%m/%Y")
            st.caption("Próximas datas (yfinance)")
            st.dataframe(df_future, use_container_width=True, hide_index=True)
        else:
            st.caption("Próximas datas (yfinance): não disponível para este ativo.")
    except Exception:
        st.caption("Próximas datas (yfinance): não disponível para este ativo.")

    if dividends_df.empty:
        st.warning("Sem dados de dividendos disponíveis no yfinance para este ticker.")
    else:
        fig_div = px.bar(
            dividends_df,
            x="Data",
            y="Dividendo",
            title="Dividendos pagos (histórico)",
            labels={"Dividendo": "Dividendo"},
        )
        fig_div.update_traces(
            hovertemplate="%{x|%d/%m/%Y}<br>%{y:.2f}<extra></extra>",
            texttemplate="%{y:.2f}",
            textposition="outside",
            textfont_size=8,
            cliponaxis=False,
        )
        fig_div.update_layout(margin=dict(t=60))
        st.plotly_chart(fig_div, use_container_width=True)

with st.expander("🧾 Indicadores (melhor esforço via yfinance)", expanded=True):

    # Indicadores pontuais (info)
    pl_info = info.get("trailingPE")
    pvp_info = info.get("priceToBook")
    dy_info = info.get("dividendYield")
    roe_info = info.get("returnOnEquity")

    cards = st.columns(4)
    with cards[0]:
        st.metric("P/L (info)", _fmt_2(pl_info))
    with cards[1]:
        st.metric("P/VP (info)", _fmt_2(pvp_info))
    with cards[2]:
        # Preferir DY calculado (12m) quando houver dados de dividendos/preço.
        dy_calc_ratio = None
        try:
            if dividends_df is not None and not dividends_df.empty:
                last_price_col = _pick_price_column(price_df)
                last_price = (
                    pd.to_numeric(price_df[last_price_col], errors="coerce").dropna().iloc[-1] if last_price_col else None
                )
                last_dt = pd.to_datetime(price_df["Data"], errors="coerce").dropna().iloc[-1]
                if last_price and last_price > 0 and pd.notna(last_dt):
                    d = dividends_df.copy()
                    d["Data"] = pd.to_datetime(d["Data"], errors="coerce")
                    d = d.dropna(subset=["Data"])
                    cutoff = last_dt - pd.DateOffset(months=12)
                    div_12m = pd.to_numeric(d.loc[d["Data"] >= cutoff, "Dividendo"], errors="coerce").dropna().sum()
                    dy_calc_ratio = (div_12m / float(last_price)) if div_12m and last_price else None
        except Exception:
            dy_calc_ratio = None

        st.metric("Dividend Yield (12m)", _fmt_percent(dy_calc_ratio if dy_calc_ratio is not None else dy_info))
    with cards[3]:
        st.metric("ROE (info)", _fmt_percent(roe_info))

    st.caption(f"Setor: {setor or '—'} | Segmento: {segmento or '—'}")

    # Série trimestral/anual (derivada)
    shares = info.get("sharesOutstanding")
    shares = float(shares) if isinstance(shares, (int, float)) and shares > 0 else None

    q_metrics = _compute_quarterly_metrics(
        income_q=(
            statements.get("income_quarterly")
            if isinstance(statements.get("income_quarterly"), pd.DataFrame)
            else pd.DataFrame()
        ),
        balance_q=(
            statements.get("balance_quarterly")
            if isinstance(statements.get("balance_quarterly"), pd.DataFrame)
            else pd.DataFrame()
        ),
        shares_outstanding=shares,
    )

    income_a = (
        statements.get("income_annual") if isinstance(statements.get("income_annual"), pd.DataFrame) else pd.DataFrame()
    )
    bal_a = (
        statements.get("balance_annual") if isinstance(statements.get("balance_annual"), pd.DataFrame) else pd.DataFrame()
    )
    a_metrics = _compute_annual_metrics(income_a, bal_a, shares)

    periodicidade = st.radio("Mostrar indicadores", ["Mensal", "Trimestral", "Anual"], horizontal=True)
    serie = _build_indicators_periodic(periodicidade, price_df, dividends_df, q_metrics, a_metrics)

    if serie.empty:
        st.warning("Sem dados suficientes para montar indicadores nesta periodicidade (limitação do yfinance para este ativo).")
    else:
        # Filtro por período na série
        c1, _c2 = st.columns([1, 3])
        with c1:
            datas = pd.to_datetime(serie["Data"], errors="coerce")
            datas = datas.dropna().drop_duplicates().sort_values()
            if datas.empty:
                st.info("Sem períodos disponíveis para filtrar.")
                st.stop()

            labels = [_period_label(ts, periodicidade) for ts in datas]
            map_label_to_ts = dict(zip(labels, datas.tolist()))
            sel_ini = st.selectbox("Início", labels, index=0)
            labels_fim = labels[labels.index(sel_ini) :]
            sel_fim = st.selectbox("Fim", labels_fim, index=len(labels_fim) - 1)
            dt_ini = map_label_to_ts[sel_ini]
            dt_fim = map_label_to_ts[sel_fim]

        m = serie.copy()
        m["Data"] = pd.to_datetime(m["Data"], errors="coerce")
        m = m.dropna(subset=["Data"])
        m = m[(m["Data"] >= pd.to_datetime(dt_ini)) & (m["Data"] <= pd.to_datetime(dt_fim))]
        if m.empty:
            st.info("Sem dados no intervalo selecionado.")
            st.stop()

        indicadores_plot = [
            ("P/L", "P/L"),
            ("P/VP", "P/VP"),
            ("Dividend Yield", "Dividend Yield"),
            ("ROE", "ROE"),
            ("Margem Líquida", "Margem Líquida"),
            ("Dívida/Patrimônio", "Dívida/Patrimônio"),
            ("EBITDA", "EBITDA"),
            ("Lucro Líquido", "Lucro Líquido"),
            ("Receita", "Receita"),
            ("Patrimônio Líquido", "Patrimônio Líquido"),
        ]

        tabs = st.tabs([t for t, _ in indicadores_plot])
        for tab, (titulo, col) in zip(tabs, indicadores_plot):
            with tab:
                if col not in m.columns:
                    st.info("Sem dados disponíveis.")
                    continue

                df_plot = m[["Data", col]].copy()
                df_plot["Data"] = pd.to_datetime(df_plot.get("Data"), errors="coerce")
                if pd.api.types.is_datetime64tz_dtype(df_plot["Data"]):
                    df_plot["Data"] = df_plot["Data"].dt.tz_localize(None)
                df_plot["Data"] = df_plot["Data"].dt.normalize() + pd.Timedelta(hours=12)
                df_plot[col] = pd.to_numeric(df_plot[col], errors="coerce")
                df_plot = df_plot.dropna(subset=["Data", col]).sort_values("Data")
                if df_plot.empty:
                    st.info("Sem dados disponíveis.")
                    continue

                if col in ["Dividend Yield", "ROE", "Margem Líquida"]:
                    df_plot[col] = df_plot[col] * 100.0
                    y_label = "%"
                else:
                    y_label = col

                fig = px.line(
                    df_plot,
                    x="Data",
                    y=col,
                    title=f"{titulo} ({periodicidade})",
                    labels={col: y_label},
                )
                x_min = pd.to_datetime(df_plot["Data"], errors="coerce").min()
                x_max = pd.to_datetime(df_plot["Data"], errors="coerce").max()
                if pd.notna(x_min) and pd.notna(x_max):
                    # Para evitar a percepção de que 31/12 cai no ano seguinte (tick em 01/01),
                    # ancoramos os ticks anuais em 31/12 também no Mensal/Trimestral.
                    if periodicidade in ["Anual", "Trimestral", "Mensal"]:
                        tick0 = pd.Timestamp(year=int(x_min.year), month=12, day=31, hour=12)
                        pad = pd.Timedelta(days=45) if periodicidade == "Anual" else pd.Timedelta(days=20)
                        fig.update_xaxes(
                            type="date",
                            tickformat="%Y",
                            dtick="M12",
                            tick0=tick0,
                            range=[x_min - pad, x_max + pad],
                            rangemode="normal",
                        )
                    else:
                        fig.update_xaxes(type="date")
                else:
                    fig.update_xaxes(type="date")

                if periodicidade == "Anual":
                    # Rótulos de dados em todos os pontos no anual
                    fig.update_traces(
                        mode="lines+markers+text",
                        text=[f"{float(v):.2f}" for v in df_plot[col].tolist()],
                        textposition="top center",
                        textfont_size=9,
                        hovertemplate="%{x|%d/%m/%Y}<br>%{y:.2f}<extra></extra>",
                        cliponaxis=False,
                    )
                else:
                    fig.update_traces(
                        mode="lines+markers",
                        hovertemplate="%{x|%d/%m/%Y}<br>%{y:.2f}<extra></extra>",
                    )

                # Nos demais modos, mantém rótulo só no último ponto (evita poluição)
                if periodicidade != "Anual":
                    last = df_plot.iloc[-1]
                    fig.add_trace(
                        go.Scatter(
                            x=[last["Data"]],
                            y=[last[col]],
                            mode="markers+text",
                            text=[f"{float(last[col]):.2f}"],
                            textposition="top center",
                            textfont_size=8,
                            marker=dict(size=6),
                            showlegend=False,
                            hoverinfo="skip",
                            cliponaxis=False,
                        )
                    )

                fig.update_layout(margin=dict(t=60))
                st.plotly_chart(fig, use_container_width=True)

# =============================
# 4) Tabela de dados financeiros
# =============================
with st.expander("📑 Demonstrativos (yfinance)", expanded=False):
    income_a = statements.get("income_annual") if isinstance(statements.get("income_annual"), pd.DataFrame) else pd.DataFrame()
    income_q = (
        statements.get("income_quarterly") if isinstance(statements.get("income_quarterly"), pd.DataFrame) else pd.DataFrame()
    )
    bal_a = statements.get("balance_annual") if isinstance(statements.get("balance_annual"), pd.DataFrame) else pd.DataFrame()
    bal_q = (
        statements.get("balance_quarterly") if isinstance(statements.get("balance_quarterly"), pd.DataFrame) else pd.DataFrame()
    )

    st.caption("Income (Anual)")
    st.dataframe(income_a, use_container_width=True)

    st.caption("Income (Trimestral)")
    st.dataframe(income_q, use_container_width=True)

    st.caption("Balanço (Anual)")
    st.dataframe(bal_a, use_container_width=True)

    st.caption("Balanço (Trimestral)")
    st.dataframe(bal_q, use_container_width=True)

# =============================
# 5) Comparativo setorial
# =============================
with st.expander("🏷️ Comparativo setorial", expanded=False):

    # Usar cache local (parquet) para sugerir pares do mesmo setor/segmento
    cache_df2 = _load_ticker_info_cache(TICKER_INFO_PATH)
    setor_local = None
    segmento_local = None
    try:
        if isinstance(cache_df2, pd.DataFrame) and not cache_df2.empty and "Ticker" in cache_df2.columns:
            hit = cache_df2[cache_df2["Ticker"].astype(str).str.upper() == ticker_base.upper()]
            if not hit.empty:
                setor_local = (hit["Setor"].iloc[0] if "Setor" in hit.columns else None)
                segmento_local = (hit["Segmento"].iloc[0] if "Segmento" in hit.columns else None)
    except Exception:
        pass

    st.caption(f"Setor (yfinance): {setor or '—'} | Segmento (yfinance): {segmento or '—'}")
    if setor_local or segmento_local:
        st.caption(f"Setor (cache): {setor_local or '—'} | Segmento (cache): {segmento_local or '—'}")

    pares = []
    if isinstance(cache_df2, pd.DataFrame) and not cache_df2.empty and "Ticker" in cache_df2.columns:
        dfp = cache_df2.copy()
        if setor_local and "Setor" in dfp.columns:
            dfp = dfp[dfp["Setor"] == setor_local]
        if segmento_local and "Segmento" in dfp.columns:
            # Se tiver segmento, filtra também (mais restrito)
            dfp2 = dfp[dfp["Segmento"] == segmento_local]
            if not dfp2.empty:
                dfp = dfp2
        pares = sorted(dfp["Ticker"].dropna().astype(str).str.strip().unique().tolist())

    pares = [t for t in pares if t.upper() != ticker_base.upper()]
    try:
        if pares:
            pares = _validar_tickers_em_lote(tuple(pares))
    except Exception:
        pass

    peers_sel = st.multiselect("Pares do mesmo setor/segmento", pares, default=pares[:5])
    peers = [ticker_base] + peers_sel

    # Buscar indicadores atuais para comparação (info)
    rows = []
    for t in peers:
        ty = ticker_para_yfinance(t) or t
        inf = _yf_info(ty)
        dy_pct = _to_percent_0_100(inf.get("dividendYield"))
        roe_pct = _to_percent_0_100(inf.get("returnOnEquity"))
        rows.append(
            {
                "Ticker": t,
                "P/L": _as_float(inf.get("trailingPE")),
                "P/VP": _as_float(inf.get("priceToBook")),
                "Dividend Yield": dy_pct,
                "ROE": roe_pct,
                "Setor": inf.get("sector"),
                "Segmento": inf.get("industry"),
            }
        )

    cmp_df = pd.DataFrame(rows)
    if cmp_df.empty:
        st.info("Sem dados para comparar.")
    else:
        cmp_show = cmp_df.copy()
        for col in ["P/L", "P/VP"]:
            if col in cmp_show.columns:
                cmp_show[col] = cmp_show[col].apply(lambda v: _fmt_2(v))
        for col in ["Dividend Yield", "ROE"]:
            if col in cmp_show.columns:
                cmp_show[col] = cmp_show[col].apply(lambda v: _fmt_percent(v))

        st.dataframe(cmp_show, use_container_width=True, hide_index=True)

        metrica = st.selectbox("Métrica para gráfico", ["P/L", "P/VP", "Dividend Yield", "ROE"], index=0)
        dfp = cmp_df.copy()
        dfp[metrica] = pd.to_numeric(dfp[metrica], errors="coerce")
        dfp = dfp.dropna(subset=[metrica])
        if dfp.empty:
            st.info("Sem valores numéricos para plotar.")
        else:
            fig_cmp = px.bar(dfp, x="Ticker", y=metrica, title=f"Comparativo: {metrica}")
            fig_cmp.update_traces(
                hovertemplate="%{x}<br>%{y:.2f}<extra></extra>",
                texttemplate="%{y:.2f}",
                textposition="outside",
                textfont_size=8,
                cliponaxis=False,
            )
            fig_cmp.update_layout(margin=dict(t=60))
            st.plotly_chart(fig_cmp, use_container_width=True)

# =============================
# 6) Exportação
# =============================
with st.expander("⬇️ Exportação", expanded=False):

    # Indicadores para exportação (trimestral/anual)
    try:
        shares_exp = info.get("sharesOutstanding")
        shares_exp = float(shares_exp) if isinstance(shares_exp, (int, float)) and shares_exp > 0 else None

        q_metrics_exp = _compute_quarterly_metrics(
            income_q=(
                statements.get("income_quarterly")
                if isinstance(statements.get("income_quarterly"), pd.DataFrame)
                else pd.DataFrame()
            ),
            balance_q=(
                statements.get("balance_quarterly")
                if isinstance(statements.get("balance_quarterly"), pd.DataFrame)
                else pd.DataFrame()
            ),
            shares_outstanding=shares_exp,
        )

        income_a_exp = (
            statements.get("income_annual") if isinstance(statements.get("income_annual"), pd.DataFrame) else pd.DataFrame()
        )
        bal_a_exp = (
            statements.get("balance_annual") if isinstance(statements.get("balance_annual"), pd.DataFrame) else pd.DataFrame()
        )
        a_metrics_exp = _compute_annual_metrics(income_a_exp, bal_a_exp, shares_exp)

        indicadores_mensais = _build_indicators_periodic("Mensal", price_df, dividends_df, q_metrics_exp, a_metrics_exp)
        indicadores_trimestrais = _build_indicators_periodic(
            "Trimestral", price_df, dividends_df, q_metrics_exp, a_metrics_exp
        )
        indicadores_anuais = _build_indicators_periodic("Anual", price_df, dividends_df, q_metrics_exp, a_metrics_exp)
    except Exception:
        indicadores_mensais = pd.DataFrame()
        indicadores_trimestrais = pd.DataFrame()
        indicadores_anuais = pd.DataFrame()

    export_sheets = {
        "indicadores_mensais": indicadores_mensais if isinstance(indicadores_mensais, pd.DataFrame) else pd.DataFrame(),
        "indicadores_trimestrais": indicadores_trimestrais if isinstance(indicadores_trimestrais, pd.DataFrame) else pd.DataFrame(),
        "indicadores_anuais": indicadores_anuais if isinstance(indicadores_anuais, pd.DataFrame) else pd.DataFrame(),
        "precos": price_df if isinstance(price_df, pd.DataFrame) else pd.DataFrame(),
        "dividendos": dividends_df if isinstance(dividends_df, pd.DataFrame) else pd.DataFrame(),
        "comparativo_setorial": cmp_df if isinstance(cmp_df, pd.DataFrame) else pd.DataFrame(),
        "income_anual": income_a if isinstance(income_a, pd.DataFrame) else pd.DataFrame(),
        "income_trimestral": income_q if isinstance(income_q, pd.DataFrame) else pd.DataFrame(),
        "balanco_anual": bal_a if isinstance(bal_a, pd.DataFrame) else pd.DataFrame(),
        "balanco_trimestral": bal_q if isinstance(bal_q, pd.DataFrame) else pd.DataFrame(),
    }

    base_csv = (
        indicadores_mensais
        if isinstance(indicadores_mensais, pd.DataFrame) and not indicadores_mensais.empty
        else (
            indicadores_trimestrais
            if isinstance(indicadores_trimestrais, pd.DataFrame) and not indicadores_trimestrais.empty
            else (indicadores_anuais if isinstance(indicadores_anuais, pd.DataFrame) and not indicadores_anuais.empty else price_df)
        )
    )
    csv_main = base_csv.to_csv(index=False, sep=",", encoding="utf-8-sig").encode("utf-8-sig")

    c_exp1, c_exp2 = st.columns(2)
    with c_exp1:
        st.download_button(
            "Exportar CSV (principal)",
            data=csv_main,
            file_name=f"fundamentalista_{ticker_base}.csv",
            mime="text/csv",
        )

    with c_exp2:
        try:
            xlsx = _export_excel_bytes(export_sheets)
            st.download_button(
                "Exportar Excel (todas as abas)",
                data=xlsx,
                file_name=f"fundamentalista_{ticker_base}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception:
            st.warning("Não foi possível gerar Excel. Verifique se 'openpyxl' está instalado.")
