"""Rotinas para buscar e validar a tabela de opções do site opcoes.net.br.

Nota importante (2026-01):
Na página https://opcoes.net.br/opcoes/bovespa a tabela principal é renderizada
no navegador via JavaScript (DataTables) e preenchida por uma chamada AJAX.
Por isso, `pandas.read_html` no HTML da página não consegue ler a tabela de opções.

Esta implementação busca os dados diretamente do endpoint usado pela própria página:
`/listaopcoes/completa` (JSON), e entrega um DataFrame pronto para consulta,
filtro e exportação.

O layout pode mudar; quando isso acontecer, o módulo levanta um erro explícito
para que o script seja ajustado.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import unicodedata

import pandas as pd
import requests

OPCOESNET_URL = "https://opcoes.net.br/opcoes/bovespa"
OPCOESNET_JSON_URL = "https://opcoes.net.br/listaopcoes/completa"

PASTA_DADOS = Path("data")
PASTA_DADOS.mkdir(exist_ok=True)
ARQ_OPCOESNET = PASTA_DADOS / "opcoes_net_bovespa.parquet"


class LayoutOpcoesNetMudouError(RuntimeError):
    """Lançado quando não foi possível encontrar/validar a tabela esperada."""


@dataclass(frozen=True)
class LayoutCheckResult:
    ok: bool
    colunas_encontradas: list[str]
    colunas_faltando: list[str]
    mensagem: str


def _strip_accents(text: str) -> str:
    if text is None:
        return ""
    return "".join(c for c in unicodedata.normalize("NFKD", str(text)) if not unicodedata.combining(c))


def _norm_col(col: str) -> str:
    c = _strip_accents(col)
    c = str(c).strip().upper()
    c = " ".join(c.split())
    return c


def _canonical_expected_columns() -> dict[str, set[str]]:
    """Mapa: coluna canônica -> aliases aceitos (normalizados)."""

    def N(s: str) -> str:
        return _norm_col(s)

    return {
        # Mapeamento esperado do endpoint JSON (títulos de coluna)
        "CODIGO": {N("Ticker"), N("Código"), N("Codigo")},
        "TIPO": {N("Tipo"), N("CALL"), N("PUT")},
        "STRIKE": {N("Strike"), N("Exercício"), N("Exercicio")},
        "VENCIMENTO": {N("Vencimento"), N("Vcto"), N("Venc")},
        "PREMIO": {N("Último"), N("Ultimo"), N("Prêmio"), N("Premio")},
        "ATIVO": {N("IdAcao"), N("Ativo"), N("Papel"), N("Underlying")},
    }


def _mapear_colunas(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    """Tenta mapear colunas do site para um conjunto canônico.

    Retorna (df_renomeado, mapeamento {col_canônica: col_original}).
    """
    if df is None or df.empty:
        return df, {}

    expected = _canonical_expected_columns()
    orig_cols = list(df.columns)
    norm_to_orig: dict[str, str] = {_norm_col(c): c for c in orig_cols}

    mapping: dict[str, str] = {}
    for canonical, aliases in expected.items():
        found_orig = None
        for alias in aliases:
            if alias in norm_to_orig:
                found_orig = norm_to_orig[alias]
                break
        if found_orig is not None:
            mapping[canonical] = found_orig

    # Renomeia apenas o que encontrou (não força)
    rename_dict = {orig: canonical for canonical, orig in mapping.items()}
    df2 = df.rename(columns=rename_dict).copy()
    return df2, mapping


def validar_layout_opcoesnet(
    df: pd.DataFrame,
    obrigatorias: list[str] | None = None,
) -> LayoutCheckResult:
    """Valida se o DataFrame parece ser a tabela principal de opções.

    `obrigatorias` usa nomes canônicos: CODIGO, TIPO, STRIKE, VENCIMENTO, PREMIO.
    """
    if obrigatorias is None:
        obrigatorias = ["CODIGO", "TIPO", "STRIKE", "VENCIMENTO", "PREMIO"]

    if df is None or df.empty:
        return LayoutCheckResult(
            ok=False,
            colunas_encontradas=[],
            colunas_faltando=obrigatorias,
            mensagem="Nenhuma tabela encontrada (DataFrame vazio).",
        )

    cols = [str(c) for c in df.columns]
    faltando = [c for c in obrigatorias if c not in cols]

    if faltando:
        return LayoutCheckResult(
            ok=False,
            colunas_encontradas=cols,
            colunas_faltando=faltando,
            mensagem=(
                "Layout do site parece ter mudado: colunas obrigatórias ausentes: "
                + ", ".join(faltando)
            ),
        )

    return LayoutCheckResult(
        ok=True,
        colunas_encontradas=cols,
        colunas_faltando=[],
        mensagem="OK",
    )


def _headers_padrao() -> dict:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.7,en;q=0.6",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": OPCOESNET_URL,
    }


def _cache_buster_5min() -> str:
    now = datetime.now()
    return f"{now.year}-{now.month}-{now.day}_{now.hour}h{now.minute // 5}"


def _fetch_listaopcoes_completa(
    id_acao: str,
    id_lista: str = "ML",
    listar_vencimentos: bool = True,
    vencimentos: list[str] | None = None,
    cotacoes: bool = True,
    timeout: int = 30,
) -> dict:
    params: dict[str, str] = {
        "cache": _cache_buster_5min(),
        "au": "False",
        "uinhc": "0",
        "idLista": str(id_lista or "ML"),
        "idAcao": str(id_acao or ""),
        "listarVencimentos": "true" if listar_vencimentos else "false",
        "cotacoes": "true" if cotacoes else "false",
    }
    if vencimentos:
        params["vencimentos"] = ",".join([str(v).strip() for v in vencimentos if str(v).strip()])

    resp = requests.get(
        OPCOESNET_JSON_URL,
        params=params,
        headers=_headers_padrao(),
        timeout=timeout,
    )
    resp.raise_for_status()
    try:
        payload = resp.json()
    except Exception as e:
        raise LayoutOpcoesNetMudouError("Resposta não é JSON (endpoint pode ter mudado).") from e

    if not payload or payload.get("success") is not True:
        raise LayoutOpcoesNetMudouError("Endpoint retornou success=False (layout/contrato pode ter mudado).")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise LayoutOpcoesNetMudouError("Endpoint retornou payload inesperado (sem campo 'data').")
    return data


def listar_vencimentos_opcoesnet(id_acao: str, id_lista: str = "ML", timeout: int = 30) -> list[dict]:
    """Lista vencimentos disponíveis no opcoes.net.br para um ativo base.

    Retorna itens como {"value": "YYYY-MM-DD", "text": "dd/mm", "selected": bool}.
    """
    if not id_acao or not str(id_acao).strip():
        return []
    data = _fetch_listaopcoes_completa(
        id_acao=str(id_acao).strip().upper(),
        id_lista=id_lista,
        listar_vencimentos=True,
        cotacoes=False,
        timeout=timeout,
    )
    vencs = data.get("vencimentos") or []
    return vencs if isinstance(vencs, list) else []


def buscar_opcoes_opcoesnet_bovespa(
    url: str = OPCOESNET_URL,
    obrigatorias: list[str] | None = None,
    id_acao: str | None = None,
    id_lista: str = "ML",
    todos_vencimentos: bool = False,
    vencimentos: list[str] | None = None,
) -> pd.DataFrame:
    """Busca opções do opcoes.net.br (B3) e retorna DataFrame padronizado.

    Como a tabela é carregada via AJAX, buscamos do endpoint JSON.

    Args:
        id_acao: ticker B3 do ativo base (ex: PETR4). Recomendado para evitar downloads enormes.
        id_lista: lista do site (default: 'ML' = Mais líquidos)
        todos_vencimentos: se True, busca todos os vencimentos disponíveis (pode ser pesado)

    Raises:
        LayoutOpcoesNetMudouError: se o endpoint/layout mudar.
    """

    if obrigatorias is None:
        obrigatorias = ["CODIGO", "TIPO", "STRIKE", "VENCIMENTO", "PREMIO"]

    if not id_acao or not str(id_acao).strip():
        raise LayoutOpcoesNetMudouError(
            "Para buscar opções pelo opcoes.net.br, informe um ativo base (ex: PETR4)."
        )

    # 1) Primeira chamada: obtém lista de vencimentos e (por padrão) retorna o vencimento selecionado.
    data0 = _fetch_listaopcoes_completa(
        id_acao=str(id_acao).strip().upper(),
        id_lista=id_lista,
        listar_vencimentos=True,
        cotacoes=True,
    )
    vencs = data0.get("vencimentos") or []
    cols = data0.get("columns") or data0.get("colunas") or data0.get("aoColumns") or []

    def _titles_from_columns(columns: list[dict]) -> list[str]:
        return [str(c.get("title", "")).strip() for c in columns if isinstance(c, dict)]

    titles = _titles_from_columns(cols) if isinstance(cols, list) else []

    def _df_from_data(data: dict, vencimento_iso: str | None) -> pd.DataFrame:
        rows = data.get("cotacoesOpcoes") or data.get("rows") or []
        if not isinstance(rows, list):
            rows = []

        # Alguns retornos vêm sem 'columns'; inferimos do primeiro item.
        local_titles = titles
        if not local_titles and rows:
            first = rows[0]
            if isinstance(first, dict):
                local_titles = list(first.keys())
            elif isinstance(first, (list, tuple)):
                local_titles = [str(i) for i in range(len(first))]

        if rows and isinstance(rows[0], dict):
            df = pd.DataFrame(rows)
        else:
            df = pd.DataFrame(rows, columns=local_titles if local_titles else None)

        # Enriquecimento: vencimento vem do filtro (não é coluna no grid)
        if vencimento_iso:
            df["Vencimento"] = vencimento_iso
        else:
            df["Vencimento"] = None

        # Renomeia para canônico
        rename = {
            "Ticker": "CODIGO",
            "Tipo": "TIPO",
            "Strike": "STRIKE",
            "Último": "PREMIO",
            "IdAcao": "ATIVO",
            "Vencimento": "VENCIMENTO",
        }
        df = df.rename(columns=rename)

        if "CODIGO" in df.columns:
            # O site pode inserir quebras de linha no ticker; removemos whitespace.
            df["CODIGO"] = (
                df["CODIGO"].astype(str).str.upper().str.replace(r"\s+", "", regex=True).str.strip()
            )

        # Tipos
        if "VENCIMENTO" in df.columns:
            df["VENCIMENTO"] = pd.to_datetime(df["VENCIMENTO"], errors="coerce")
        if "STRIKE" in df.columns:
            df["STRIKE"] = pd.to_numeric(df["STRIKE"], errors="coerce")
        if "PREMIO" in df.columns:
            df["PREMIO"] = pd.to_numeric(df["PREMIO"], errors="coerce")
        if "TIPO" in df.columns:
            df["TIPO"] = df["TIPO"].astype(str).str.upper().str.strip()
        if "ATIVO" in df.columns:
            df["ATIVO"] = df["ATIVO"].astype(str).str.upper().str.strip()

        if "VENCIMENTO" in df.columns:
            df["Mês Vencimento"] = pd.to_datetime(df["VENCIMENTO"], errors="coerce").dt.strftime("%m/%Y")

        df["Fonte"] = "opcoes.net.br"
        df["Coletado Em"] = datetime.now()
        return df

    # Determina vencimento selecionado no retorno
    selected = [v.get("value") for v in vencs if isinstance(v, dict) and v.get("selected")]
    selected_iso = selected[0] if selected else None

    frames: list[pd.DataFrame] = []

    # Se o usuário passou vencimentos explícitos, sempre respeita.
    if vencimentos:
        for venc_iso in vencimentos:
            venc_iso = str(venc_iso).strip()
            if not venc_iso:
                continue
            data_v = _fetch_listaopcoes_completa(
                id_acao=str(id_acao).strip().upper(),
                id_lista=id_lista,
                listar_vencimentos=False,
                vencimentos=[venc_iso],
                cotacoes=True,
            )
            frames.append(_df_from_data(data_v, venc_iso))
    elif todos_vencimentos and vencs:
        # Busca um por vencimento, para conseguir etiquetar corretamente
        for v in vencs:
            if not isinstance(v, dict) or not v.get("value"):
                continue
            venc_iso = str(v.get("value"))
            data_v = _fetch_listaopcoes_completa(
                id_acao=str(id_acao).strip().upper(),
                id_lista=id_lista,
                listar_vencimentos=False,
                vencimentos=[venc_iso],
                cotacoes=True,
            )
            frames.append(_df_from_data(data_v, venc_iso))
    else:
        frames.append(_df_from_data(data0, selected_iso))

    df_out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    # Mapeamento tolerante (caso títulos mudem levemente)
    df_out, _ = _mapear_colunas(df_out)

    check = validar_layout_opcoesnet(df_out, obrigatorias=obrigatorias)
    if not check.ok:
        raise LayoutOpcoesNetMudouError(check.mensagem + (" Colunas encontradas: " + ", ".join(check.colunas_encontradas) if check.colunas_encontradas else ""))

    return df_out


def salvar_cache_opcoesnet(df: pd.DataFrame, path: Path | None = None) -> None:
    if path is None:
        path = ARQ_OPCOESNET
    if df is None or df.empty:
        return
    path.parent.mkdir(exist_ok=True, parents=True)
    df.to_parquet(path, index=False)


def carregar_cache_opcoesnet(path: Path | None = None) -> pd.DataFrame:
    if path is None:
        path = ARQ_OPCOESNET
    try:
        if path.exists():
            return pd.read_parquet(path)
    except Exception:
        return pd.DataFrame()
    return pd.DataFrame()


def exportar_opcoesnet_para_excel(df: pd.DataFrame) -> bytes:
    """Exporta DataFrame para Excel em memória (bytes)."""
    from io import BytesIO

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Opcoes")
    return output.getvalue()
