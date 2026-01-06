import os
from datetime import datetime
from io import BytesIO
import uuid
from typing import Optional, Tuple

import pandas as pd
import numpy as np
import yfinance as yf

from modules.cotacoes import obter_cotacao_atual_usd_brl, obter_historico_indice
from modules.ticker_info import ticker_para_yfinance, extrair_ticker

CAIXA_PATH = os.path.join("data", "investimentos_manuais_caixa.parquet")
ACOES_PATH = os.path.join("data", "investimentos_manuais_acoes.parquet")


def _ensure_dir(path: str) -> None:
    pasta = os.path.dirname(path)
    if pasta:
        os.makedirs(pasta, exist_ok=True)


def _parse_num(valor) -> float:
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
    else:
        txt_norm = txt
    try:
        num = float(txt_norm)
        return -num if negativo else num
    except Exception:
        return np.nan


def carregar_caixa() -> pd.DataFrame:
    if os.path.exists(CAIXA_PATH):
        try:
            df = pd.read_parquet(CAIXA_PATH)
            if not isinstance(df, pd.DataFrame) or df.empty:
                return pd.DataFrame()
            # Migração leve de schema
            if "Mes" in df.columns and "Mês" not in df.columns:
                df = df.rename(columns={"Mes": "Mês"})
            if "Rentabilidade %" in df.columns and "Rentabilidade (%)" not in df.columns:
                df = df.rename(columns={"Rentabilidade %": "Rentabilidade (%)"})
            # Garante colunas numéricas principais
            for col in ["Valor Inicial", "Depósitos", "Saques", "Valor Final", "Rentabilidade (%)", "Ganho"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            if "ID" not in df.columns:
                df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
            if "Usuário" not in df.columns:
                df["Usuário"] = "Manual"
            # Adicionar coluna Nome Caixa se não existir (suporte a múltiplos caixas)
            if "Nome Caixa" not in df.columns:
                df["Nome Caixa"] = "Caixa Principal"
            return df
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def salvar_caixa(df: pd.DataFrame) -> None:
    _ensure_dir(CAIXA_PATH)
    try:
        df.to_parquet(CAIXA_PATH, index=False)
    except Exception:
        pass


def calcular_caixa(
    valor_inicial,
    depositos,
    saques,
    valor_final,
) -> Tuple[float, float, float, float]:
    """Calcula rentabilidade do caixa.

    Fórmula:
      Rentabilidade (%) = ((ValorFinal - soma(depositos) + soma(saques)) - ValorInicial) / ValorInicial * 100

    Retorna: (depositos_total, saques_total, rent_pct, ganho)
    """
    vi = _parse_num(valor_inicial)
    vf = _parse_num(valor_final)
    if pd.isna(vi) or vi <= 0:
        raise ValueError("Valor Inicial deve ser maior que zero")
    if pd.isna(vf):
        raise ValueError("Valor Final precisa ser numérico")

    dep_total = 0.0
    if depositos is not None:
        if isinstance(depositos, (list, tuple, pd.Series, np.ndarray)):
            dep_total = float(pd.to_numeric(pd.Series(list(depositos)), errors="coerce").fillna(0.0).sum())
        else:
            dep_total = float(pd.to_numeric(depositos, errors="coerce") or 0.0)

    saq_total = 0.0
    if saques is not None:
        if isinstance(saques, (list, tuple, pd.Series, np.ndarray)):
            saq_total = float(pd.to_numeric(pd.Series(list(saques)), errors="coerce").fillna(0.0).sum())
        else:
            saq_total = float(pd.to_numeric(saques, errors="coerce") or 0.0)

    ganho = (vf - dep_total + saq_total) - vi
    rent_pct = (ganho / vi) * 100.0
    return dep_total, saq_total, float(rent_pct), float(ganho)


def registrar_caixa(
    mes_ano: str,
    valor_inicial,
    rentabilidade_pct=None,
    usuario: str = "Manual",
    depositos=None,
    saques=None,
    valor_final=None,
    nome_caixa: str = "Caixa Principal",
) -> pd.DataFrame:
    """Registra Caixa.

    Compatível com dois modos:
    - Novo: informar valor_inicial, depositos/saques e valor_final (rentabilidade é calculada).
    - Legado: informar valor_inicial e rentabilidade_pct (ganho = valor_inicial * rent%).
    """
    mes = str(mes_ano).strip()
    usr = (usuario or "Manual").strip() or "Manual"
    nome_cx = (nome_caixa or "Caixa Principal").strip() or "Caixa Principal"

    df = carregar_caixa()

    # Modo novo (preferencial)
    if valor_final is not None or depositos is not None or saques is not None:
        dep_total, saq_total, rent_calc, ganho = calcular_caixa(
            valor_inicial=valor_inicial,
            depositos=depositos,
            saques=saques,
            valor_final=valor_final,
        )
        vi = _parse_num(valor_inicial)
        vf = _parse_num(valor_final)
        novo = {
            "ID": str(uuid.uuid4()),
            "Usuário": usr,
            "Nome Caixa": nome_cx,
            "Mês": mes,
            "Valor Inicial": float(vi),
            "Depósitos": float(dep_total),
            "Saques": float(saq_total),
            "Valor Final": float(vf),
            "Rentabilidade (%)": float(rent_calc),
            "Ganho": float(ganho),
            "Data Registro": datetime.now(),
        }
    else:
        # Modo legado
        vi = _parse_num(valor_inicial)
        rent = _parse_num(rentabilidade_pct)
        if pd.isna(vi) or pd.isna(rent):
            raise ValueError("Valor e rentabilidade precisam ser numéricos")
        ganho = float(vi) * (float(rent) / 100.0)
        novo = {
            "ID": str(uuid.uuid4()),
            "Usuário": usr,
            "Nome Caixa": nome_cx,
            "Mês": mes,
            "Valor Inicial": float(vi),
            "Depósitos": 0.0,
            "Saques": 0.0,
            "Valor Final": float(vi) + float(ganho),
            "Rentabilidade (%)": float(rent),
            "Ganho": float(ganho),
            "Data Registro": datetime.now(),
        }

    # Apenas um registro por mês/usuário/nome_caixa: sobrescreve se existir
    if not df.empty:
        mes_col = "Mês" if "Mês" in df.columns else "Mes" if "Mes" in df.columns else None
        if mes_col and "Usuário" in df.columns and "Nome Caixa" in df.columns:
            mask = (
                (df[mes_col].astype(str) == mes) & 
                (df["Usuário"].astype(str) == usr) &
                (df["Nome Caixa"].astype(str) == nome_cx)
            )
            df = df[~mask].copy()
        elif mes_col and "Usuário" in df.columns:
            # Compatibilidade legado - sobrescreve por mês/usuário
            mask = (df[mes_col].astype(str) == mes) & (df["Usuário"].astype(str) == usr)
            df = df[~mask].copy()

    df_out = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
    salvar_caixa(df_out)
    return df_out


def excluir_caixa(ids=None, tudo: bool = False) -> pd.DataFrame:
    df = carregar_caixa()
    if df.empty:
        return df
    if tudo:
        df_out = df.iloc[0:0].copy()
        salvar_caixa(df_out)
        return df_out
    if ids is None:
        return df
    ids_set = set([str(i) for i in (ids if isinstance(ids, (list, tuple, set, pd.Series, np.ndarray)) else [ids])])
    if "ID" not in df.columns:
        return df
    df_out = df[~df["ID"].astype(str).isin(ids_set)].copy()
    salvar_caixa(df_out)
    return df_out


def carregar_acoes() -> pd.DataFrame:
    if os.path.exists(ACOES_PATH):
        try:
            df = pd.read_parquet(ACOES_PATH)
            if not isinstance(df, pd.DataFrame) or df.empty:
                return pd.DataFrame()
            if "ID" not in df.columns:
                df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
            return df
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def salvar_acoes(df: pd.DataFrame) -> None:
    _ensure_dir(ACOES_PATH)
    try:
        df.to_parquet(ACOES_PATH, index=False)
    except Exception:
        pass


def _buscar_preco_moeda(ticker: str) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    sym = ticker_para_yfinance(ticker)
    if not sym:
        return None, None, None
    try:
        tk = yf.Ticker(sym)
        price = None
        info_sym = sym
        try:
            fi = getattr(tk, "fast_info", None)
            if fi:
                price = fi.last_price if hasattr(fi, "last_price") else fi.get("lastPrice") if isinstance(fi, dict) else None
                curr = fi.currency if hasattr(fi, "currency") else fi.get("currency") if isinstance(fi, dict) else None
            else:
                curr = None
        except Exception:
            curr = None
        if price is None:
            hist = tk.history(period="1d")
            if isinstance(hist, pd.DataFrame) and (not hist.empty) and ("Close" in hist.columns):
                px_last = hist["Close"].dropna()
                if not px_last.empty:
                    price = float(px_last.iloc[-1])
        if price is None:
            info = tk.info if hasattr(tk, "info") else {}
            if isinstance(info, dict):
                price = info.get("regularMarketPrice") or info.get("previousClose")
                curr = curr or info.get("currency")
        curr_final = (curr or "").strip().upper() or None
        return (float(price) if price is not None else None, curr_final, info_sym)
    except Exception:
        return None, None, None


def _cotacao_para_brl(moeda: Optional[str]) -> float:
    if not moeda or moeda.upper() == "BRL":
        return 1.0
    if moeda.upper() == "USD":
        try:
            return float(obter_cotacao_atual_usd_brl())
        except Exception:
            return 1.0
    if moeda.upper() == "EUR":
        try:
            hist = obter_historico_indice("EUR/BRL", periodo="10d", intervalo="1d")
            if hist is not None and not hist.empty:
                close = pd.to_numeric(hist.get("Close"), errors="coerce").dropna()
                if close.size:
                    return float(close.iloc[-1])
        except Exception:
            return 1.0
        return 1.0
    return 1.0


def registrar_acao_manual(ticker: str, quantidade, mes_ano: str, usuario: str = "Manual") -> Tuple[pd.DataFrame, dict]:
    qtd = _parse_num(quantidade)
    if pd.isna(qtd) or qtd <= 0:
        raise ValueError("Quantidade deve ser maior que zero")
    preco, moeda, sym = _buscar_preco_moeda(ticker)
    if preco is None:
        raise ValueError("Não foi possível obter preço para o ticker informado")
    fx = _cotacao_para_brl(moeda)
    preco_brl = preco * fx
    valor_total = qtd * preco
    valor_total_brl = qtd * preco_brl
    tnorm = extrair_ticker(ticker) or ticker
    tipo = "Ações"
    if (moeda or "").upper() == "USD":
        tipo = "Ações Dólar"
    elif (moeda or "").upper() == "EUR":
        tipo = "Ações Euro"

    mes = str(mes_ano).strip()
    df = carregar_acoes()
    novo = pd.DataFrame([
        {
            "ID": str(uuid.uuid4()),
            "Usuário": usuario or "Manual",
            "Tipo": tipo,
            "Ticker": tnorm,
            "Ticker_YF": sym,
            "Quantidade": qtd,
            "Preço Atual": preco,
            "Moeda": moeda or "BRL",
            "FX para BRL": fx,
            "Preço BRL": preco_brl,
            "Valor Total": valor_total,
            "Valor": valor_total_brl,
            "Mês/Ano": mes,
            "Data Registro": datetime.now(),
        }
    ])
    df_out = pd.concat([df, novo], ignore_index=True)
    salvar_acoes(df_out)
    meta = {
        "preco": preco,
        "moeda": moeda or "BRL",
        "fx": fx,
        "preco_brl": preco_brl,
        "valor_total": valor_total,
        "valor_total_brl": valor_total_brl,
        "tipo": tipo,
    }
    return df_out, meta


def excluir_acoes(ids=None, tudo: bool = False) -> pd.DataFrame:
    df = carregar_acoes()
    if df.empty:
        return df
    if tudo:
        df_out = df.iloc[0:0].copy()
        salvar_acoes(df_out)
        return df_out
    if ids is None:
        return df
    ids_set = set([str(i) for i in (ids if isinstance(ids, (list, tuple, set, pd.Series, np.ndarray)) else [ids])])
    if "ID" not in df.columns:
        return df
    df_out = df[~df["ID"].astype(str).isin(ids_set)].copy()
    salvar_acoes(df_out)
    return df_out


def caixa_para_dividendos(df_caixa: pd.DataFrame) -> pd.DataFrame:
    """Converte registros de caixa para formato de dividendos/proventos.
    
    Cada caixa aparece como um ativo separado usando o Nome Caixa.
    """
    if df_caixa is None or df_caixa.empty:
        return pd.DataFrame(columns=["Data", "Ativo", "Valor Líquido", "Usuário", "Fonte"])
    dfd = df_caixa.copy()
    mes_col = "Mês" if "Mês" in dfd.columns else "Mes" if "Mes" in dfd.columns else None
    if mes_col is None:
        return pd.DataFrame(columns=["Data", "Ativo", "Valor Líquido", "Usuário", "Fonte"])
    dfd["Data"] = pd.to_datetime("01/" + dfd[mes_col].astype(str), format="%d/%m/%Y", errors="coerce")
    dfd = dfd[dfd["Data"].notna()].copy()
    # Usar Nome Caixa como identificador do ativo
    dfd["Ativo"] = dfd.get("Nome Caixa", "Caixa").fillna("Caixa")
    dfd["Valor Líquido"] = pd.to_numeric(dfd.get("Ganho"), errors="coerce").fillna(0.0)
    dfd["Usuário"] = dfd.get("Usuário", "Manual").fillna("Manual")
    dfd["Fonte"] = "Manual Caixa"
    return dfd[["Data", "Ativo", "Valor Líquido", "Usuário", "Fonte"]]


def acoes_para_consolidado(df_acoes: pd.DataFrame) -> pd.DataFrame:
    if df_acoes is None or df_acoes.empty:
        return pd.DataFrame()
    df = df_acoes.copy()
    df["Ativo"] = df.get("Ticker")
    df["Preço"] = df.get("Preço BRL")
    df["Valor"] = df.get("Valor")
    if "Mês/Ano" not in df.columns:
        df["Mês/Ano"] = None
    df["Tipo"] = df.get("Tipo", "Ações")
    df["Usuário"] = df.get("Usuário", "Manual").fillna("Manual")
    cols = [c for c in ["Ativo", "Ticker", "Quantidade", "Preço", "Valor", "Tipo", "Usuário", "Mês/Ano"] if c in df.columns]
    return df[cols]


def caixa_para_consolidado(df_caixa: pd.DataFrame) -> pd.DataFrame:
    """Converte registros de caixa para formato de consolidado (tabs de investimento).
    
    Cada caixa aparece como Tipo='Caixa' com Nome Caixa como identificador.
    """
    if df_caixa is None or df_caixa.empty:
        return pd.DataFrame()
    df = df_caixa.copy()
    
    # Usar Nome Caixa como Ativo
    df["Ativo"] = df.get("Nome Caixa", "Caixa").fillna("Caixa")
    df["Ticker"] = df["Ativo"]  # Ticker = Nome Caixa para consistência
    df["Quantidade"] = 1.0  # Caixa sempre tem quantidade 1
    df["Preço"] = df.get("Valor Final", 0.0)  # Preço = Valor Final do mês
    df["Valor"] = df.get("Valor Final", 0.0)
    df["Tipo"] = "Caixa"
    df["Usuário"] = df.get("Usuário", "Manual").fillna("Manual")
    
    # Converter Mês (MM/YYYY) para Mês/Ano
    mes_col = "Mês" if "Mês" in df.columns else "Mes" if "Mes" in df.columns else None
    if mes_col:
        df["Mês/Ano"] = df[mes_col].astype(str)
    else:
        df["Mês/Ano"] = None
    
    cols = [c for c in ["Ativo", "Ticker", "Quantidade", "Preço", "Valor", "Tipo", "Usuário", "Mês/Ano"] if c in df.columns]
    return df[cols]


def dataframe_para_excel_bytes(df: pd.DataFrame, sheet_name: str = "planilha") -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()
