import os
import re
from datetime import datetime
from typing import Iterable, List, Optional

import pandas as pd
import requests
import yfinance as yf

CACHE_PATH = os.path.join("data", "ticker_info.parquet")
SEC_TICKER_MAP_PATH = os.path.join("data", "sec_company_tickers.parquet")

SEC_USER_AGENT = os.getenv("SEC_USER_AGENT") or "invest-app (no-email-configured)"

ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")
FMP_API_KEY = os.getenv("FMP_API_KEY")


_B3_RE = re.compile(r"^[A-Z]{4}\d{1,2}$")
_US_RE = re.compile(r"^[A-Z]{1,6}$")


def extrair_ticker(valor) -> Optional[str]:
    if pd.isna(valor):
        return None
    texto = str(valor).strip()
    if not texto:
        return None
    if " - " in texto:
        texto = texto.split(" - ", 1)[0].strip()
    return texto.split()[0].strip()


def _ticker_valido(t: str) -> bool:
    t = (t or "").strip().upper()
    if not t:
        return False
    if "." in t:
        # já normalizado (ex: PETR4.SA)
        base = t.split(".", 1)[0]
        return bool(_B3_RE.match(base) or _US_RE.match(base))
    return bool(_B3_RE.match(t) or _US_RE.match(t))


def ticker_para_yfinance(ticker: str) -> Optional[str]:
    t = extrair_ticker(ticker)
    if not t:
        return None
    t = t.strip().upper()
    if "." in t:
        return t
    if _B3_RE.match(t):
        return f"{t}.SA"
    return t


def _load_cache(path: str = CACHE_PATH) -> pd.DataFrame:
    if os.path.exists(path):
        try:
            df = pd.read_parquet(path)
            if not isinstance(df, pd.DataFrame):
                return pd.DataFrame()
            return df
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def _save_cache(df: pd.DataFrame, path: str = CACHE_PATH) -> None:
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        df.to_parquet(path, index=False)
    except Exception:
        return


def _fetch_alpha_vantage_overview(symbol: str) -> dict:
    if not ALPHAVANTAGE_API_KEY:
        return {}
    if not symbol or symbol.endswith(".SA"):
        return {}
    try:
        url = "https://www.alphavantage.co/query"
        params = {"function": "OVERVIEW", "symbol": symbol, "apikey": ALPHAVANTAGE_API_KEY}
        r = requests.get(url, params=params, timeout=8)
        if r.status_code != 200:
            return {}
        data = r.json() if r.content else {}
        # AlphaVantage retorna chaves com letras maiúsculas
        if not isinstance(data, dict) or not data or "Symbol" not in data:
            return {}
        return {
            "Setor": data.get("Sector"),
            "Segmento": data.get("Industry"),
        }
    except Exception:
        return {}


def _fetch_fmp_profile(symbol: str) -> dict:
    if not FMP_API_KEY:
        return {}
    if not symbol or symbol.endswith(".SA"):
        return {}
    try:
        url = f"https://financialmodelingprep.com/api/v3/profile/{symbol}"
        r = requests.get(url, params={"apikey": FMP_API_KEY}, timeout=8)
        if r.status_code != 200:
            return {}
        data = r.json() if r.content else []
        if not isinstance(data, list) or not data:
            return {}
        item = data[0] if isinstance(data[0], dict) else {}
        return {
            "Setor": item.get("sector"),
            "Segmento": item.get("industry"),
        }
    except Exception:
        return {}


def _sic_para_setor(sic: Optional[int]) -> Optional[str]:
    """Mapeamento simples de SIC -> macro setor (divisões SIC)."""
    try:
        if sic is None:
            return None
        s = int(sic)
    except Exception:
        return None

    if 100 <= s <= 999:
        return "Agriculture"
    if 1000 <= s <= 1499:
        return "Mining"
    if 1500 <= s <= 1799:
        return "Construction"
    if 2000 <= s <= 3999:
        return "Manufacturing"
    if 4000 <= s <= 4999:
        return "Transportation/Utilities"
    if 5000 <= s <= 5199:
        return "Wholesale"
    if 5200 <= s <= 5999:
        return "Retail"
    if 6000 <= s <= 6799:
        return "Finance/Insurance"
    if 7000 <= s <= 8999:
        return "Services"
    if 9100 <= s <= 9729:
        return "Public Administration"
    return None


def _load_sec_ticker_map() -> pd.DataFrame:
    if os.path.exists(SEC_TICKER_MAP_PATH):
        try:
            return pd.read_parquet(SEC_TICKER_MAP_PATH)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def _save_sec_ticker_map(df: pd.DataFrame) -> None:
    try:
        os.makedirs(os.path.dirname(SEC_TICKER_MAP_PATH) or ".", exist_ok=True)
        df.to_parquet(SEC_TICKER_MAP_PATH, index=False)
    except Exception:
        return


def _get_sec_cik_for_ticker(ticker: str) -> Optional[str]:
    """Resolve ticker US -> CIK via arquivo público da SEC. Sem API key.

    A SEC exige User-Agent.
    """
    t = (ticker or "").strip().upper()
    if not t or "." in t:
        return None

    df_map = _load_sec_ticker_map()
    if not df_map.empty and "ticker" in df_map.columns and "cik" in df_map.columns:
        hit = df_map[df_map["ticker"] == t]
        if not hit.empty:
            return str(hit["cik"].iloc[0]).zfill(10)

    # Baixa mapa completo (cache local). Fonte: https://www.sec.gov/files/company_tickers.json
    try:
        headers = {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate", "Host": "www.sec.gov"}
        r = requests.get("https://www.sec.gov/files/company_tickers.json", headers=headers, timeout=12)
        if r.status_code != 200:
            return None
        data = r.json()
        if not isinstance(data, dict):
            return None

        rows = []
        for _k, v in data.items():
            if not isinstance(v, dict):
                continue
            tk = str(v.get("ticker") or "").strip().upper()
            cik = v.get("cik_str")
            title = v.get("title")
            if not tk or cik is None:
                continue
            rows.append({"ticker": tk, "cik": int(cik), "title": title})

        if rows:
            df_new = pd.DataFrame(rows)
            df_new = df_new.drop_duplicates(subset=["ticker"], keep="last")
            _save_sec_ticker_map(df_new)
            hit = df_new[df_new["ticker"] == t]
            if not hit.empty:
                return str(int(hit["cik"].iloc[0])).zfill(10)
    except Exception:
        return None

    return None


def _fetch_sec_company_sic(ticker: str) -> dict:
    """Busca SIC e descrição via SEC submissions endpoint. Sem API key."""
    t = (ticker or "").strip().upper()
    if not t or t.endswith(".SA") or "." in t:
        return {}

    cik = _get_sec_cik_for_ticker(t)
    if not cik:
        return {}

    try:
        headers = {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate", "Host": "data.sec.gov"}
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        r = requests.get(url, headers=headers, timeout=12)
        if r.status_code != 200:
            return {}
        data = r.json() if r.content else {}
        if not isinstance(data, dict):
            return {}

        sic = data.get("sic")
        sic_desc = data.get("sicDescription")
        return {
            "SIC": sic,
            "Setor": _sic_para_setor(sic),
            "Segmento": sic_desc,
        }
    except Exception:
        return {}


def atualizar_cache_tickers(tickers: Iterable[str], path: str = CACHE_PATH) -> pd.DataFrame:
    """Atualiza cache local (parquet) com Setor/Segmento via yfinance.

    - Só consulta tickers faltantes.
    - Para ETFs, yfinance costuma não ter 'sector/industry'. Neste caso usa:
      - Segmento = category (quando disponível)
      - Setor = quoteType (ex: 'ETF')
    """
    tickers_lista: List[str] = []
    for t in tickers:
        t2 = extrair_ticker(t)
        if t2:
            t2 = t2.upper()
            if _ticker_valido(t2):
                tickers_lista.append(t2)
    tickers_lista = sorted(set(tickers_lista))
    if not tickers_lista:
        return _load_cache(path)

    cache_df = _load_cache(path)
    cache_map = {}
    if not cache_df.empty and "Ticker" in cache_df.columns:
        cache_map = cache_df.set_index("Ticker").to_dict(orient="index")

    def _postprocess_cache(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return df
        if "Ticker" not in df.columns:
            return df
        if "Ticker_YF" not in df.columns:
            df["Ticker_YF"] = None
        if "Setor" not in df.columns:
            df["Setor"] = None
        if "Segmento" not in df.columns:
            df["Segmento"] = None

        def _is_blank(v) -> bool:
            if v is None:
                return True
            if isinstance(v, str) and not v.strip():
                return True
            return False

        mudou = False
        for col in ["Setor", "Segmento"]:
            mask = df[col].apply(_is_blank)
            if not mask.any():
                continue
            sym = df.loc[mask, "Ticker_YF"].fillna("").astype(str)
            tk = df.loc[mask, "Ticker"].fillna("").astype(str)
            preenchido = []
            for s, t in zip(sym.tolist(), tk.tolist()):
                s = (s or "").strip().upper()
                t = (t or "").strip().upper()
                if s.endswith(".SA"):
                    preenchido.append("Ações BR")
                elif _US_RE.match(t) or _US_RE.match(s):
                    preenchido.append("Ações Dólar")
                else:
                    preenchido.append("Outros")
            df.loc[mask, col] = preenchido
            mudou = True

        if mudou:
            df = df.drop_duplicates(subset=["Ticker"], keep="last")
            _save_cache(df, path)

        return df

    def _precisa_atualizar(linha: dict) -> bool:
        if not isinstance(linha, dict):
            return True
        setor = linha.get("Setor")
        segmento = linha.get("Segmento")
        if setor is None or (isinstance(setor, str) and not setor.strip()):
            return True
        if segmento is None or (isinstance(segmento, str) and not segmento.strip()):
            return True
        return False

    faltantes = [t for t in tickers_lista if (t not in cache_map) or _precisa_atualizar(cache_map.get(t, {}))]
    if not faltantes:
        return _postprocess_cache(cache_df)

    # Montar símbolos yfinance
    mapa_yf = {t: ticker_para_yfinance(t) for t in faltantes}
    syms = [s for s in mapa_yf.values() if s]
    if not syms:
        return cache_df

    try:
        tk = yf.Tickers(" ".join(syms))
    except Exception:
        return cache_df

    novas = []
    for t_raw, sym in mapa_yf.items():
        info = {}
        try:
            t_obj = tk.tickers.get(sym)
            if t_obj is not None:
                info = t_obj.get_info() or {}
        except Exception:
            info = {}

        quote_type = info.get("quoteType")
        setor = info.get("sector")
        segmento = info.get("industry")

        # Fallbacks úteis para ETFs
        if not segmento:
            segmento = info.get("category")
        if not setor:
            setor = quote_type

        # Fallback: outras APIs para preencher Setor/Segmento quando yfinance não traz
        if (not setor or not segmento) and sym:
            # 1) SEC/EDGAR (sem chave) - bom para empresas US
            sec_extra = _fetch_sec_company_sic(sym)
            if sec_extra:
                setor = setor or sec_extra.get("Setor")
                segmento = segmento or sec_extra.get("Segmento")

        if (not setor or not segmento) and sym:
            extra = _fetch_alpha_vantage_overview(sym)
            if not extra:
                extra = _fetch_fmp_profile(sym)
            if extra:
                setor = setor or extra.get("Setor")
                segmento = segmento or extra.get("Segmento")

        # Preenchimento mínimo para não deixar nulo
        if not setor:
            if sym and sym.endswith(".SA"):
                setor = "Ações BR"
            elif sym:
                setor = "Ações Dólar"
            else:
                setor = quote_type or "Ações"

        if not segmento:
            if sym and sym.endswith(".SA"):
                segmento = "Ações BR"
            elif sym:
                segmento = "Ações Dólar"
            else:
                segmento = quote_type or "Ações"

        novas.append(
            {
                "Ticker": t_raw,
                "Ticker_YF": sym,
                "Setor": setor,
                "Segmento": segmento,
                "QuoteType": quote_type,
                "AtualizadoEm": datetime.now().isoformat(timespec="seconds"),
            }
        )

    if novas:
        novos_df = pd.DataFrame(novas)
        cache_df = pd.concat([cache_df, novos_df], ignore_index=True) if not cache_df.empty else novos_df
        # Dedup pelo ticker
        cache_df = cache_df.drop_duplicates(subset=["Ticker"], keep="last")

        cache_df = _postprocess_cache(cache_df)

    return cache_df


def atualizar_cache_por_df(df: pd.DataFrame, path: str = CACHE_PATH) -> pd.DataFrame:
    """Extrai tickers de um DataFrame de origem e atualiza o cache."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return _load_cache(path)

    candidatos = []
    # Preferir coluna Ticker quando existe (evita palavras do campo Produto)
    if "Ticker" in df.columns:
        candidatos = df["Ticker"].dropna().astype(str).tolist()
    elif "Ativo" in df.columns:
        candidatos = df["Ativo"].dropna().astype(str).tolist()
    elif "Produto" in df.columns:
        candidatos = df["Produto"].dropna().astype(str).tolist()

    return atualizar_cache_tickers(candidatos, path=path)
