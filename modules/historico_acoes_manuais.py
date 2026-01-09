import pandas as pd
import numpy as np


def parse_mes_ano_to_period(mes_ano) -> pd.Period | None:
    if mes_ano is None or (isinstance(mes_ano, float) and np.isnan(mes_ano)):
        return None
    txt = str(mes_ano).strip()
    if not txt:
        return None
    try:
        mm, yyyy = txt.split("/")
        return pd.Period(f"{int(yyyy):04d}-{int(mm):02d}", freq="M")
    except Exception:
        return None


def expand_lotes_para_posicao_mensal(
    df_lotes: pd.DataFrame,
    ate_periodo: pd.Period | None = None,
) -> pd.DataFrame:
    """Expande lotes (compras + vendas) em uma posição mensal (quantidade) por ativo.

    Regras:
    - Compra em Mês Compra adiciona quantidade naquele mês e se mantém nos meses seguintes.
    - Venda em Mês Venda reduz quantidade naquele mês e se mantém reduzida nos meses seguintes.
    - Linhas com quantidade <= 0 são removidas.

    Retorna colunas:
    - Usuário, Ticker, Ticker_YF, Moeda, Periodo, Quantidade
    """
    if df_lotes is None or df_lotes.empty:
        return pd.DataFrame(columns=["Usuário", "Ticker", "Ticker_YF", "Moeda", "Periodo", "Quantidade"])

    df = df_lotes.copy()

    if "Usuário" not in df.columns:
        df["Usuário"] = "Manual"
    df["Usuário"] = df["Usuário"].fillna("Manual").astype(str)

    if "Mês Compra" not in df.columns and "Mês/Ano" in df.columns:
        df["Mês Compra"] = df["Mês/Ano"].astype(str)
    if "Quantidade Compra" not in df.columns and "Quantidade" in df.columns:
        df["Quantidade Compra"] = pd.to_numeric(df["Quantidade"], errors="coerce")
    if "Mês Venda" not in df.columns:
        df["Mês Venda"] = ""
    if "Quantidade Venda" not in df.columns:
        df["Quantidade Venda"] = 0.0

    df["Quantidade Compra"] = pd.to_numeric(df.get("Quantidade Compra"), errors="coerce").fillna(0.0)
    df["Quantidade Venda"] = pd.to_numeric(df.get("Quantidade Venda"), errors="coerce").fillna(0.0)

    df["Ticker"] = df.get("Ticker", "").astype(str).str.strip().str.upper()
    df["Ticker_YF"] = df.get("Ticker_YF", "").astype(str).str.strip()
    df["Moeda"] = df.get("Moeda", "BRL").fillna("BRL").astype(str).str.strip().str.upper()

    p_compra = df["Mês Compra"].apply(parse_mes_ano_to_period)
    df = df[p_compra.notna()].copy()
    if df.empty:
        return pd.DataFrame(columns=["Usuário", "Ticker", "Ticker_YF", "Moeda", "Periodo", "Quantidade"])

    df["PeriodoCompra"] = p_compra[p_compra.notna()].astype("period[M]")
    p_venda = df["Mês Venda"].apply(lambda x: parse_mes_ano_to_period(x) if str(x).strip() else None)
    df["PeriodoVenda"] = p_venda

    p_min = df["PeriodoCompra"].min()
    p_max = ate_periodo or pd.Period(pd.Timestamp.today().strftime("%Y-%m"), freq="M")
    periodos = pd.period_range(p_min, p_max, freq="M")

    eventos = []
    compras = df[["Usuário", "Ticker", "Ticker_YF", "Moeda", "PeriodoCompra", "Quantidade Compra"]].copy()
    compras = compras[compras["Quantidade Compra"] > 0]
    if not compras.empty:
        compras = compras.rename(columns={"PeriodoCompra": "Periodo", "Quantidade Compra": "Delta"})
        eventos.append(compras[["Usuário", "Ticker", "Ticker_YF", "Moeda", "Periodo", "Delta"]])

    vendas = df[["Usuário", "Ticker", "Ticker_YF", "Moeda", "PeriodoVenda", "Quantidade Venda"]].copy()
    vendas = vendas[vendas["PeriodoVenda"].notna() & (vendas["Quantidade Venda"] > 0)]
    if not vendas.empty:
        vendas["Delta"] = -pd.to_numeric(vendas["Quantidade Venda"], errors="coerce").fillna(0.0)
        vendas = vendas.rename(columns={"PeriodoVenda": "Periodo"})
        eventos.append(vendas[["Usuário", "Ticker", "Ticker_YF", "Moeda", "Periodo", "Delta"]])

    if not eventos:
        return pd.DataFrame(columns=["Usuário", "Ticker", "Ticker_YF", "Moeda", "Periodo", "Quantidade"])

    ev = pd.concat(eventos, ignore_index=True)
    ev = ev.groupby(["Usuário", "Ticker", "Ticker_YF", "Moeda", "Periodo"], as_index=False).agg(Delta=("Delta", "sum"))

    out_rows = []
    for (usr, tck, sym, moeda), grp in ev.groupby(["Usuário", "Ticker", "Ticker_YF", "Moeda"]):
        g = grp.set_index("Periodo").reindex(periodos, fill_value=0.0)
        g.index.name = "Periodo"
        g = g.reset_index()
        g["Quantidade"] = pd.to_numeric(g["Delta"], errors="coerce").fillna(0.0).cumsum()
        g = g[g["Quantidade"] > 0].copy()
        if g.empty:
            continue
        g["Usuário"] = usr
        g["Ticker"] = tck
        g["Ticker_YF"] = sym
        g["Moeda"] = moeda
        out_rows.append(g[["Usuário", "Ticker", "Ticker_YF", "Moeda", "Periodo", "Quantidade"]])

    if not out_rows:
        return pd.DataFrame(columns=["Usuário", "Ticker", "Ticker_YF", "Moeda", "Periodo", "Quantidade"])

    return pd.concat(out_rows, ignore_index=True)
