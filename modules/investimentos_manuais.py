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
CAIXA_MOVS_PATH = os.path.join("data", "investimentos_manuais_caixa_movimentos.parquet")
ACOES_PATH = os.path.join("data", "investimentos_manuais_acoes.parquet")
ACOES_MANUAIS_PATH = ACOES_PATH


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
            # Status do mês: fechado = valor final confirmado
            if "Fechado" not in df.columns:
                df["Fechado"] = True
            return df
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def _parse_mes_ano_ts(mes_ano: str) -> Optional[pd.Timestamp]:
    mes = str(mes_ano or "").strip()
    if not mes:
        return None
    ts = pd.to_datetime("01/" + mes, format="%d/%m/%Y", errors="coerce")
    if pd.isna(ts):
        return None
    return ts


def _next_mes_ano(mes_ano: str) -> Optional[str]:
    ts = _parse_mes_ano_ts(mes_ano)
    if ts is None:
        return None
    nxt = ts + pd.DateOffset(months=1)
    return nxt.strftime("%m/%Y")


def salvar_caixa(df: pd.DataFrame) -> None:
    _ensure_dir(CAIXA_PATH)
    try:
        df.to_parquet(CAIXA_PATH, index=False)
    except Exception:
        pass


def carregar_caixa_movimentos() -> pd.DataFrame:
    """Carrega movimentações detalhadas do caixa (depósitos/saques) do disco."""
    if os.path.exists(CAIXA_MOVS_PATH):
        try:
            df = pd.read_parquet(CAIXA_MOVS_PATH)
            if not isinstance(df, pd.DataFrame) or df.empty:
                return pd.DataFrame()

            # Migração leve de schema/colunas
            if "Mes" in df.columns and "Mês" not in df.columns:
                df = df.rename(columns={"Mes": "Mês"})
            if "Nome Caixa" not in df.columns:
                df["Nome Caixa"] = "Caixa Principal"
            if "Usuário" not in df.columns:
                df["Usuário"] = "Manual"
            if "Tipo" not in df.columns:
                df["Tipo"] = "Depósito"
            if "Valor" in df.columns:
                df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce")
            if "Data" in df.columns:
                df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
            if "ID" not in df.columns:
                df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
            if "Descrição" not in df.columns:
                df["Descrição"] = ""
            if "Categoria" not in df.columns:
                df["Categoria"] = ""
            if "Data Registro" not in df.columns:
                df["Data Registro"] = datetime.now()

            # Manter somente colunas esperadas (se existirem)
            cols = [
                c
                for c in [
                    "ID",
                    "Usuário",
                    "Nome Caixa",
                    "Mês",
                    "Data",
                    "Tipo",
                    "Valor",
                    "Descrição",
                    "Categoria",
                    "Data Registro",
                ]
                if c in df.columns
            ]
            return df[cols].copy()
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def salvar_caixa_movimentos(df: pd.DataFrame) -> None:
    _ensure_dir(CAIXA_MOVS_PATH)
    try:
        df.to_parquet(CAIXA_MOVS_PATH, index=False)
    except Exception:
        pass


def registrar_caixa_movimentos(
    mes_ano: str,
    usuario: str,
    nome_caixa: str,
    movimentos: pd.DataFrame,
) -> pd.DataFrame:
    """Sobrescreve as movimentações de um mês/usuário/caixa com base no DataFrame informado."""
    mes = str(mes_ano).strip()
    usr = (usuario or "Manual").strip() or "Manual"
    nome_cx = (nome_caixa or "Caixa Principal").strip() or "Caixa Principal"

    df_all = carregar_caixa_movimentos()
    if df_all.empty:
        df_all = pd.DataFrame(
            columns=[
                "ID",
                "Usuário",
                "Nome Caixa",
                "Mês",
                "Data",
                "Tipo",
                "Valor",
                "Descrição",
                "Categoria",
                "Data Registro",
            ]
        )

    mv = movimentos if isinstance(movimentos, pd.DataFrame) else pd.DataFrame()
    mv = mv.copy()

    if mv.empty:
        # Se vier vazio, apenas remove as movimentações existentes daquele mês/usuário/caixa
        mask_rm = (
            (df_all.get("Mês", pd.Series(dtype=str)).astype(str) == mes)
            & (df_all.get("Usuário", pd.Series(dtype=str)).astype(str) == usr)
            & (df_all.get("Nome Caixa", pd.Series(dtype=str)).astype(str) == nome_cx)
        )
        df_out = df_all[~mask_rm].copy() if not df_all.empty else df_all
        salvar_caixa_movimentos(df_out)
        return df_out

    # Normalizar/garantir colunas
    mv["Usuário"] = usr
    mv["Nome Caixa"] = nome_cx
    mv["Mês"] = mes

    if "Data" in mv.columns:
        mv["Data"] = pd.to_datetime(mv["Data"], errors="coerce")
    else:
        mv["Data"] = pd.NaT

    mv["Tipo"] = mv.get("Tipo", "Depósito").astype(str)
    mv["Valor"] = pd.to_numeric(mv.get("Valor"), errors="coerce")
    mv["Descrição"] = mv.get("Descrição", "").fillna("").astype(str)
    mv["Categoria"] = mv.get("Categoria", "").fillna("").astype(str)

    if "ID" not in mv.columns:
        mv["ID"] = [str(uuid.uuid4()) for _ in range(len(mv))]
    else:
        mv["ID"] = mv["ID"].astype(str)
        mv.loc[mv["ID"].str.strip().eq(""), "ID"] = [str(uuid.uuid4()) for _ in range(int((mv["ID"].str.strip().eq("")).sum()))]

    mv["Data Registro"] = datetime.now()

    # Remover linhas inválidas
    mv = mv.dropna(subset=["Valor"], how="any")
    mv = mv[mv["Valor"].fillna(0.0) != 0.0].copy()

    # Sobrescrever subset
    mask = (
        (df_all.get("Mês", pd.Series(dtype=str)).astype(str) == mes)
        & (df_all.get("Usuário", pd.Series(dtype=str)).astype(str) == usr)
        & (df_all.get("Nome Caixa", pd.Series(dtype=str)).astype(str) == nome_cx)
    )
    df_keep = df_all[~mask].copy() if not df_all.empty else df_all

    cols = [
        "ID",
        "Usuário",
        "Nome Caixa",
        "Mês",
        "Data",
        "Tipo",
        "Valor",
        "Descrição",
        "Categoria",
        "Data Registro",
    ]
    mv_out = mv[[c for c in cols if c in mv.columns]].copy()
    df_out = pd.concat([df_keep, mv_out], ignore_index=True)
    salvar_caixa_movimentos(df_out)
    return df_out


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
    fechado: bool = True,
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

    fechado_bool = bool(fechado)

    def _sum_movs(v) -> float:
        if v is None:
            return 0.0
        if isinstance(v, (list, tuple, pd.Series, np.ndarray)):
            return float(pd.to_numeric(pd.Series(list(v)), errors="coerce").fillna(0.0).sum())
        x = pd.to_numeric(v, errors="coerce")
        return 0.0 if pd.isna(x) else float(x)

    # Modo novo (preferencial)
    if valor_final is not None or depositos is not None or saques is not None or (rentabilidade_pct is None):
        vi = _parse_num(valor_inicial)
        if pd.isna(vi) or vi <= 0:
            raise ValueError("Valor Inicial deve ser maior que zero")

        dep_total = _sum_movs(depositos)
        saq_total = _sum_movs(saques)

        # Se mês não está fechado, não calcula rentabilidade/ganho (fica 0) e mantém VF=VI
        if not fechado_bool:
            vf = float(vi)
            rent_calc = 0.0
            ganho = 0.0
        else:
            vf = _parse_num(valor_final)
            if pd.isna(vf):
                raise ValueError("Valor Final precisa ser numérico")
            dep_total, saq_total, rent_calc, ganho = calcular_caixa(
                valor_inicial=vi,
                depositos=dep_total,
                saques=saq_total,
                valor_final=vf,
            )

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
            "Fechado": bool(fechado_bool),
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
            "Fechado": True,
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

    # Se o mês foi fechado, cria/atualiza automaticamente o mês seguinte com VI = VF
    if bool(novo.get("Fechado")):
        prox = _next_mes_ano(mes)
        if prox:
            # Assegura coluna Fechado
            if "Fechado" not in df_out.columns:
                df_out["Fechado"] = True

            mask_next = (
                (df_out.get("Mês", pd.Series(dtype=str)).astype(str) == prox)
                & (df_out.get("Usuário", pd.Series(dtype=str)).astype(str) == usr)
                & (df_out.get("Nome Caixa", pd.Series(dtype=str)).astype(str) == nome_cx)
            )

            vf_prev = float(novo.get("Valor Final") or 0.0)

            if mask_next.any():
                # Atualiza apenas se o próximo mês não estiver fechado
                idxs = df_out.index[mask_next].tolist()
                idx = idxs[-1]
                fechado_next = bool(df_out.loc[idx, "Fechado"]) if "Fechado" in df_out.columns else False
                if not fechado_next:
                    old_vi = pd.to_numeric(df_out.loc[idx, "Valor Inicial"], errors="coerce") if "Valor Inicial" in df_out.columns else np.nan
                    df_out.loc[idx, "Valor Inicial"] = vf_prev
                    # Mantém VF=VI em mês aberto quando estava igual ao VI anterior ou ausente
                    if "Valor Final" in df_out.columns:
                        old_vf = pd.to_numeric(df_out.loc[idx, "Valor Final"], errors="coerce")
                        if pd.isna(old_vf) or (not pd.isna(old_vi) and not pd.isna(old_vf) and float(old_vf) == float(old_vi)):
                            df_out.loc[idx, "Valor Final"] = vf_prev
                    if "Rentabilidade (%)" in df_out.columns:
                        df_out.loc[idx, "Rentabilidade (%)"] = 0.0
                    if "Ganho" in df_out.columns:
                        df_out.loc[idx, "Ganho"] = 0.0
            else:
                novo_prox = {
                    "ID": str(uuid.uuid4()),
                    "Usuário": usr,
                    "Nome Caixa": nome_cx,
                    "Mês": prox,
                    "Valor Inicial": vf_prev,
                    "Depósitos": 0.0,
                    "Saques": 0.0,
                    "Valor Final": vf_prev,
                    "Rentabilidade (%)": 0.0,
                    "Ganho": 0.0,
                    "Fechado": False,
                    "Data Registro": datetime.now(),
                }
                df_out = pd.concat([df_out, pd.DataFrame([novo_prox])], ignore_index=True)

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

            # Migração de schema (versões antigas -> compra/venda)
            if "Mês/Ano" in df.columns and "Mês Compra" not in df.columns:
                df["Mês Compra"] = df["Mês/Ano"].astype(str)
            if "Quantidade" in df.columns and "Quantidade Compra" not in df.columns:
                df["Quantidade Compra"] = pd.to_numeric(df["Quantidade"], errors="coerce")
            if "Mês Venda" not in df.columns:
                df["Mês Venda"] = ""
            if "Quantidade Venda" not in df.columns:
                df["Quantidade Venda"] = 0.0

            # Preço de compra (opcional) para precificar o 1º mês (antes do fechamento mensal)
            if "Preço Compra" not in df.columns:
                df["Preço Compra"] = np.nan

            # Normalizações
            if "Usuário" not in df.columns:
                df["Usuário"] = "Manual"
            if "Ticker" in df.columns:
                df["Ticker"] = df["Ticker"].astype(str).apply(lambda x: (extrair_ticker(x) or str(x)).strip().upper())
            if "Ticker_YF" in df.columns:
                df["Ticker_YF"] = df["Ticker_YF"].astype(str)

            # Garantir numéricos
            for col in ["Quantidade Compra", "Quantidade Venda", "Preço Compra"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

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


def registrar_acao_manual(
    ticker: str,
    quantidade,
    mes_ano: str,
    usuario: str = "Manual",
    preco_compra: Optional[float] = None,
) -> Tuple[pd.DataFrame, dict]:
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
    pc = _parse_num(preco_compra)
    if not pd.isna(pc) and pc < 0:
        raise ValueError("Preço de compra não pode ser negativo")
    df = carregar_acoes()
    novo = pd.DataFrame([
        {
            "ID": str(uuid.uuid4()),
            "Usuário": usuario or "Manual",
            "Tipo": tipo,
            "Ticker": tnorm,
            "Ticker_YF": sym,
            # Compra/Venda (lote)
            "Quantidade Compra": float(qtd),
            "Mês Compra": mes,
            "Quantidade Venda": 0.0,
            "Mês Venda": "",
            "Preço Compra": (float(pc) if not pd.isna(pc) and float(pc) > 0 else np.nan),

            # Campos legados (compatibilidade UI antiga)
            "Quantidade": float(qtd),
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
    if "Fechado" in dfd.columns:
        try:
            dfd = dfd[dfd["Fechado"].astype(bool)].copy()
        except Exception:
            pass
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
    
    Cada caixa aparece como Tipo='Renda Fixa' (mesma categoria) com Nome Caixa como identificador.
    Inclui a coluna Fonte='Manual Caixa' para permitir tratamentos específicos (ex.: rentabilidade).
    """
    if df_caixa is None or df_caixa.empty:
        return pd.DataFrame()
    df = df_caixa.copy()

    # Se o mês está em aberto, o "valor" do caixa fica no valor inicial (carregamento)
    if "Fechado" in df.columns:
        try:
            fechado_mask = df["Fechado"].astype(bool)
        except Exception:
            fechado_mask = pd.Series(True, index=df.index)
        vi_num = pd.to_numeric(df.get("Valor Inicial"), errors="coerce")
        vf_num = pd.to_numeric(df.get("Valor Final"), errors="coerce")
        df["_ValorCaixa"] = np.where(fechado_mask.fillna(True), vf_num, vi_num)
    else:
        df["_ValorCaixa"] = pd.to_numeric(df.get("Valor Final"), errors="coerce")
    
    # Usar Nome Caixa como Ativo
    df["Ativo"] = df.get("Nome Caixa", "Caixa").fillna("Caixa")
    df["Ticker"] = df["Ativo"]  # Ticker = Nome Caixa para consistência
    df["Quantidade"] = 1.0  # Caixa sempre tem quantidade 1
    df["Preço"] = df.get("_ValorCaixa", 0.0)  # mês aberto usa Valor Inicial
    df["Valor"] = df.get("_ValorCaixa", 0.0)
    df["Tipo"] = "Renda Fixa"
    df["Usuário"] = df.get("Usuário", "Manual").fillna("Manual")
    df["Fonte"] = "Manual Caixa"
    
    # Converter Mês (MM/YYYY) para Mês/Ano
    mes_col = "Mês" if "Mês" in df.columns else "Mes" if "Mes" in df.columns else None
    if mes_col:
        df["Mês/Ano"] = df[mes_col].astype(str)
    else:
        df["Mês/Ano"] = None
    
    cols = [c for c in ["Ativo", "Ticker", "Quantidade", "Preço", "Valor", "Tipo", "Usuário", "Mês/Ano", "Fonte"] if c in df.columns]
    out = df[cols].copy()
    return out


def dataframe_para_excel_bytes(df: pd.DataFrame, sheet_name: str = "planilha") -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()
