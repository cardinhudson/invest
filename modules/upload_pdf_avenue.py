"""
Processamento de PDFs Avenue (ações e dividendos).
Extrai dados, salva em Parquet e oferece utilitários para processamento em lote.
"""

from __future__ import annotations

import os
import re
from difflib import get_close_matches
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

try:
    import pdfplumber
except ImportError:  # pragma: no cover
    pdfplumber = None


PDF_UPLOADS_DIR = "uploads/pdf_avenue"
ACOES_PDF_PATH = "data/acoes_avenue.parquet"
DIVIDENDOS_PDF_PATH = "data/dividendos_avenue.parquet"


# ---------------------------------------------------------------------------
# Utilitários básicos
# ---------------------------------------------------------------------------

def garantir_diretorio_pdf() -> None:
    """Garante que o diretório padrão de uploads existe."""
    Path(PDF_UPLOADS_DIR).mkdir(parents=True, exist_ok=True)


def extrair_mes_ano_pdf(nome_arquivo: str) -> Optional[str]:
    """Extrai MM/AAAA de nomes como Stmt_20251130.pdf."""
    match = re.search(r"(\d{4})(\d{2})(\d{2})", nome_arquivo)
    if match:
        ano, mes, _dia = match.groups()
        return f"{mes}/{ano}"
    return None


def limpar_texto_pdf(texto: str) -> str:
    """Normaliza texto removendo espaços duplicados."""
    texto = str(texto or "").strip()
    return re.sub(r"\s+", " ", texto)


def _token_is_ticker(cand: str, proibidos: Optional[Set[str]] = None) -> bool:
    cand = cand.strip("'\" ").upper()
    if not (1 <= len(cand) <= 6 and cand.isalpha()):
        return False
    if proibidos and cand in proibidos:
        return False
    # Rejeita apenas fragmentos óbvios de palavras portuguesas (não inglesas como AND que podem ser tickers)
    fragmentos_invalidos = {"DO", "DE", "DA", "EM", "NO", "NA", "OS", "AS", "UM", "UMA", "AO"}
    if cand in fragmentos_invalidos:
        return False
    return True


def _carregar_tickers_portfolio(usuario: str, mes_ano: Optional[str]) -> Set[str]:
    """Carrega tickers já salvos para usar como fallback de identificação."""
    if not os.path.exists(ACOES_PDF_PATH):
        return set()
    try:
        df = pd.read_parquet(ACOES_PDF_PATH)
    except Exception:
        return set()

    if not df.empty:
        if usuario:
            df = df[df.get("Usuário") == usuario]
        if mes_ano:
            df = df[df.get("Mês/Ano") == mes_ano]
    if "Ticker" not in df.columns:
        return set()
    return {
        str(t).strip().upper()
        for t in df["Ticker"].dropna()
        if _token_is_ticker(str(t).strip().upper())
    }


def _ticker_por_portfolio(
    tickers_portfolio: Set[str],
    tokens: List[str],
    proibidos: Set[str],
) -> Optional[str]:
    if not tickers_portfolio:
        return None
    tokens_validos = [
        tok.strip("'\" ").upper()
        for tok in tokens
        if tok and _token_is_ticker(tok.strip("'\" "), proibidos)
    ]
    for tok in tokens_validos:
        match = get_close_matches(tok, list(tickers_portfolio), n=1, cutoff=0.6)
        if match:
            return match[0]
    if len(tickers_portfolio) == 1:
        return next(iter(tickers_portfolio))
    return None


# ---------------------------------------------------------------------------
# Ações
# ---------------------------------------------------------------------------

def extrair_acoes_pdf(arquivo_pdf: str, usuario: str = "Importado", mes_ano: Optional[str] = None) -> pd.DataFrame:
    """Extrai posições em ações de um PDF Avenue."""
    if pdfplumber is None:
        raise ImportError("pdfplumber não está instalado. Execute: pip install pdfplumber")
    if not os.path.exists(arquivo_pdf):
        raise FileNotFoundError(f"Arquivo não encontrado: {arquivo_pdf}")

    mes_ano_resolvido = mes_ano or extrair_mes_ano_pdf(os.path.basename(arquivo_pdf)) or "01/2025"
    acoes: List[Dict] = []

    with pdfplumber.open(arquivo_pdf) as pdf:
        for page in pdf.pages:
            texto = page.extract_text()
            tabelas = page.extract_tables()

            if tabelas:
                for tabela in tabelas:
                    acoes.extend(_processar_tabela_acoes(tabela, usuario, mes_ano_resolvido))

            if texto and not acoes:
                acoes.extend(_extrair_acoes_de_texto(texto, usuario, mes_ano_resolvido))

    if not acoes:
        return pd.DataFrame()

    df = pd.DataFrame(acoes)
    return df.drop_duplicates(subset=["Produto", "Ticker", "Quantidade Disponível"])


def _processar_tabela_acoes(tabela: List[List[str]], usuario: str, mes_ano: str) -> List[Dict]:
    acoes: List[Dict] = []
    if not tabela or len(tabela) < 2:
        return acoes

    header_idx = None
    inicio_dados = 0
    for idx, linha in enumerate(tabela):
        linha_lower = [str(cel).lower() for cel in linha if cel]
        if any(p in " ".join(linha_lower) for p in ["ativo", "quantidade", "preço", "valor", "ticker", "symbol", "price", "quantity"]):
            header_idx = idx
            inicio_dados = idx + 1
            break
    if header_idx is None:
        inicio_dados = 1

    for linha in tabela[inicio_dados:]:
        linha_clean = [limpar_texto_pdf(cel) for cel in linha]
        if not linha_clean or not linha_clean[0]:
            continue
        primeira_coluna = linha_clean[0].lower()
        if any(p in primeira_coluna for p in ["total", "subtotal", "saldo", "discriminação"]):
            continue
        if len(linha_clean) < 4:
            continue
        produto = linha_clean[0]
        ticker = linha_clean[1] if len(linha_clean) > 1 else ""
        try:
            quantidade = float(linha_clean[2].replace(",", ".")) if len(linha_clean) > 2 else 0.0
            preco = float(linha_clean[3].replace(",", ".")) if len(linha_clean) > 3 else 0.0
        except ValueError:
            continue
        valor = quantidade * preco
        if quantidade <= 0 or valor <= 0:
            continue
        acoes.append(
            {
                "Produto": produto,
                "Ticker": ticker,
                "Código de Negociação": ticker,
                "Quantidade Disponível": quantidade,
                "Preço de Fechamento": preco,
                "Valor": valor,
                "Mês/Ano": mes_ano,
                "Usuário": usuario,
            }
        )
    return acoes


def _extrair_acoes_de_texto(texto: str, usuario: str, mes_ano: str) -> List[Dict]:
    acoes: List[Dict] = []
    if "PORTFOLIO SUMMARY" not in texto:
        return acoes

    linhas = texto.split("\n")
    em_portfolio = False
    for linha in linhas:
        linha_strip = linha.strip()
        if "PORTFOLIO SUMMARY" in linha_strip:
            em_portfolio = True
            continue
        if em_portfolio and ("Total Equities" in linha_strip or "Total Cash" in linha_strip):
            em_portfolio = False
            continue
        if not em_portfolio or not linha_strip:
            continue
        if any(
            palavra in linha_strip.lower()
            for palavra in ["symbol", "description", "cusip", "quantity", "price", "value", "account type", "market price", "annual income", "equities / options"]
        ):
            continue
        partes = linha_strip.split()
        if len(partes) < 7:
            continue
        idx_tipo = -1
        for j, parte in enumerate(partes):
            if parte in ["C", "O"]:
                idx_tipo = j
                break
        if idx_tipo <= 0:
            continue
        ticker = partes[idx_tipo - 1]
        if not _token_is_ticker(ticker):
            continue
        if idx_tipo + 2 >= len(partes):
            continue
        try:
            quantidade = float(partes[idx_tipo + 1].replace(",", "."))
            preco = float(partes[idx_tipo + 2].replace(",", "."))
        except ValueError:
            continue
        valor = quantidade * preco
        if not (quantidade > 0 and preco > 0 and valor > 0 and quantidade < 10_000_000):
            continue
        descricao = " ".join(partes[: idx_tipo - 1]) if idx_tipo > 1 else ticker
        acoes.append(
            {
                "Produto": descricao,
                "Ticker": ticker,
                "Código de Negociação": ticker,
                "Quantidade Disponível": quantidade,
                "Preço de Fechamento": preco,
                "Valor": valor,
                "Mês/Ano": mes_ano,
                "Usuário": usuario,
            }
        )
    return acoes


# ---------------------------------------------------------------------------
# Dividendos
# ---------------------------------------------------------------------------

def extrair_dividendos_pdf(
    arquivo_pdf: str,
    usuario: str = "Importado",
    mes_ano: Optional[str] = None,
    tickers_portfolio: Optional[Set[str]] = None,
) -> pd.DataFrame:
    """Extrai dividendos recebidos de um PDF Avenue."""
    if pdfplumber is None:
        raise ImportError("pdfplumber não está instalado. Execute: pip install pdfplumber")
    if not os.path.exists(arquivo_pdf):
        raise FileNotFoundError(f"Arquivo não encontrado: {arquivo_pdf}")

    mes_ano_resolvido = mes_ano or extrair_mes_ano_pdf(os.path.basename(arquivo_pdf)) or "01/2025"
    portfolio_set = set(tickers_portfolio or set()) | _carregar_tickers_portfolio(usuario, mes_ano_resolvido)
    dividendos: List[Dict] = []

    with pdfplumber.open(arquivo_pdf) as pdf:
        for page in pdf.pages:
            texto = page.extract_text()
            tabelas = page.extract_tables()

            if tabelas:
                for tabela in tabelas:
                    dividendos.extend(_processar_tabela_dividendos(tabela, usuario, mes_ano_resolvido))

            if texto:
                dividendos.extend(
                    _extrair_dividendos_de_texto(texto, usuario, mes_ano_resolvido, portfolio_set)
                )

    if not dividendos:
        return pd.DataFrame()

    df = pd.DataFrame(dividendos)
    return df.drop_duplicates(subset=["Produto", "Data de Pagamento", "Valor Líquido"])


def _processar_tabela_dividendos(tabela: List[List[str]], usuario: str, mes_ano: str) -> List[Dict]:
    dividendos: List[Dict] = []
    if not tabela or len(tabela) < 2:
        return dividendos

    header_idx = None
    inicio_dados = 0
    for idx, linha in enumerate(tabela):
        linha_lower = [str(cel).lower() for cel in linha if cel]
        if any(p in " ".join(linha_lower) for p in ["data", "ativo", "valor", "provento", "dividendo"]):
            header_idx = idx
            inicio_dados = idx + 1
            break
    if header_idx is None:
        inicio_dados = 1

    for linha in tabela[inicio_dados:]:
        linha_clean = [limpar_texto_pdf(cel) for cel in linha]
        if not linha_clean or not linha_clean[0]:
            continue
        primeira_coluna = linha_clean[0].lower()
        if any(p in primeira_coluna for p in ["total", "subtotal", "saldo"]):
            continue
        if len(linha_clean) < 3:
            continue
        data = linha_clean[0]
        produto = linha_clean[1]
        try:
            valor = float(linha_clean[2].replace(",", "."))
        except ValueError:
            continue
        if valor == 0:
            continue
        dividendos.append(
            {
                "Produto": produto or "Dividendo",
                "Data de Pagamento": data,
                "Tipo de Provento": "Dividendo",
                "Valor Líquido": valor,
                "Mês/Ano": mes_ano,
                "Usuário": usuario,
            }
        )
    return dividendos


def _extrair_dividendos_de_texto(
    texto: str,
    usuario: str,
    mes_ano: str,
    tickers_portfolio: Set[str],
) -> List[Dict]:
    dividendos: List[Dict] = []

    # Mantém caso geral, mas agora considera retenções/créditos em português
    if "DIVIDEND" not in texto and "INTEREST" not in texto and "Retenção" not in texto and "Retencao" not in texto:
        return dividendos

    linhas = texto.split("\n")
    em_dividendos = False
    last_ticker: Optional[str] = None
    contexto: List[str] = []
    proibidos = {
        "DIVIDEND",
        "DIVIDENDS",
        "INTEREST",
        "RETENCAO",
        "RETENÇÃO",
        "IMPOSTOS",
        "C",
        "O",
        "D",
        "CREDIT",
        "CRÉDITO",
        "DIVIDENDOS",
        "JUROS",
        "SOBRE",
        "STOCK",
        "LENDING",
        "ACCRUED",
        "FROM",
        "WITH",
    }

    def _linha_eh_provento(l: str) -> bool:
        u = l.upper()
        return (
            "DIVIDEND" in u
            or "INTEREST" in u
            or "RETENCAO" in u
            or "RETENÇÃO" in u
            or "DIVIDENDO" in u
            or "CRÉDITO" in u
            or "CREDITO" in u
        )

    for i, linha_raw in enumerate(linhas):
        linha = linha_raw.strip()
        if linha:
            contexto.append(linha)
            if len(contexto) > 6:
                contexto.pop(0)

        if "DIVIDENDS AND INTEREST" in linha:
            em_dividendos = True
            continue
        if em_dividendos and (
            "Total Buy / Sell" in linha or "All investment" in linha or "Total Dividends" in linha
        ):
            em_dividendos = False
            continue
        if not em_dividendos or not linha:
            continue

        clean_line = linha.strip("'\" ")
        if _token_is_ticker(clean_line) and len(clean_line.split()) == 1 and clean_line.isalpha():
            last_ticker = clean_line
            continue

        prox_linha = linhas[i + 1].strip() if i + 1 < len(linhas) else ""
        prox2_linha = linhas[i + 2].strip() if i + 2 < len(linhas) else ""

        # Verifica se próxima linha é um ticker isolado (padrão mais comum)
        prox_linha_clean = None
        if prox_linha:
            prox_candidate = prox_linha.strip("'\" ")
            # Linha isolada com apenas um token que parece ticker
            if (len(prox_candidate.split()) == 1 and 
                _token_is_ticker(prox_candidate, proibidos) and
                prox_candidate.upper() not in proibidos):
                prox_linha_clean = prox_candidate.upper()

        if not _linha_eh_provento(linha):
            continue

        try:
            partes = linha.split()
            todas_partes = partes + prox_linha.split() + prox2_linha.split()

            data = None
            for parte in todas_partes:
                if "/" in parte and len(parte) == 10:
                    data = parte
                    break
            if not data:
                continue

            linha_valor = ""
            for candidato_valor in (linha, prox_linha, prox2_linha):
                if "$" in candidato_valor:
                    linha_valor = candidato_valor
                    break
            if not linha_valor:
                continue
            idx_cifrao = linha_valor.rfind("$")
            valor_str = linha_valor[idx_cifrao + 1 :].strip().split()[0]
            valor = float(valor_str.replace(",", "."))
            if valor <= 0:
                continue

            ulinha = linha.upper()
            tipo = "Dividendo"
            if "INTEREST" in ulinha:
                tipo = "Juros"
            elif "RETENCAO" in ulinha or "RETENÇÃO" in ulinha:
                tipo = "Retenção de Impostos"

            # PRIORIDADE 1: ticker na próxima linha (isolado)
            ticker: Optional[str] = None
            if prox_linha_clean:
                ticker = prox_linha_clean
            
            # PRIORIDADE 2: ticker na mesma linha (antes do $)
            if not ticker:
                idx_cifrao_token = None
                for j, p in enumerate(partes):
                    if "$" in p:
                        idx_cifrao_token = j
                        break
                if idx_cifrao_token is None:
                    idx_cifrao_token = len(partes)

                for j in range(idx_cifrao_token - 1, -1, -1):
                    cand = partes[j].strip("',\" ")
                    if _token_is_ticker(cand, proibidos):
                        ticker = cand.upper()
                        break

            # PRIORIDADE 3: último ticker visto em linha isolada
            if not ticker and last_ticker:
                ticker = last_ticker

            # PRIORIDADE 4: busca no contexto recente
            if not ticker:
                for ctx in reversed(contexto[:-1]):
                    for token in ctx.split():
                        cand = token.strip("',\" ")
                        if _token_is_ticker(cand, proibidos):
                            ticker = cand.upper()
                            break
                    if ticker:
                        break

            # PRIORIDADE 5: matching com portfolio
            if not ticker:
                ticker = _ticker_por_portfolio(tickers_portfolio, todas_partes, proibidos)

            produto = ticker if ticker else "Dividendo"
            dividendos.append(
                {
                    "Produto": produto,
                    "Data de Pagamento": data,
                    "Tipo de Provento": tipo,
                    "Valor Líquido": valor,
                    "Mês/Ano": mes_ano,
                    "Usuário": usuario,
                }
            )
        except Exception:
            continue

    return dividendos


# ---------------------------------------------------------------------------
# Persistência
# ---------------------------------------------------------------------------

def salvar_acoes_pdf_parquet(df_acoes: pd.DataFrame, path: str = ACOES_PDF_PATH) -> pd.DataFrame:
    if df_acoes.empty:
        return df_acoes
    Path(os.path.dirname(path) or ".").mkdir(parents=True, exist_ok=True)
    existente = pd.DataFrame()
    if os.path.exists(path):
        try:
            existente = pd.read_parquet(path)
        except Exception:
            existente = pd.DataFrame()
    combinado = pd.concat([existente, df_acoes], ignore_index=True)
    combinado = combinado.drop_duplicates(
        subset=["Mês/Ano", "Usuário", "Produto", "Ticker", "Quantidade Disponível"], keep="last"
    )
    for col in ["Quantidade Disponível", "Preço de Fechamento", "Valor"]:
        if col in combinado.columns:
            combinado[col] = pd.to_numeric(combinado[col], errors="coerce")
    combinado.to_parquet(path)
    return combinado


def salvar_dividendos_pdf_parquet(df_dividendos: pd.DataFrame, path: str = DIVIDENDOS_PDF_PATH) -> pd.DataFrame:
    if df_dividendos.empty:
        return df_dividendos
    Path(os.path.dirname(path) or ".").mkdir(parents=True, exist_ok=True)
    existente = pd.DataFrame()
    if os.path.exists(path):
        try:
            existente = pd.read_parquet(path)
        except Exception:
            existente = pd.DataFrame()
    combinado = pd.concat([existente, df_dividendos], ignore_index=True)
    combinado = combinado.drop_duplicates(
        subset=["Mês/Ano", "Usuário", "Produto", "Data de Pagamento", "Valor Líquido"],
        keep="last",
    )
    if "Valor Líquido" in combinado.columns:
        combinado["Valor Líquido"] = pd.to_numeric(combinado["Valor Líquido"], errors="coerce")
    combinado.to_parquet(path)
    return combinado


# ---------------------------------------------------------------------------
# Processamento em lote
# ---------------------------------------------------------------------------

def processar_pdf_individual(
    arquivo_pdf: str,
    usuario: str = "Importado",
    mes_ano: Optional[str] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Processa um PDF retornando (acoes, dividendos)."""
    df_acoes = extrair_acoes_pdf(arquivo_pdf, usuario=usuario, mes_ano=mes_ano)
    tickers_portfolio = set(df_acoes["Ticker"].dropna().str.upper()) if not df_acoes.empty else set()
    df_dividendos = extrair_dividendos_pdf(
        arquivo_pdf,
        usuario=usuario,
        mes_ano=mes_ano,
        tickers_portfolio=tickers_portfolio,
    )
    return df_acoes, df_dividendos


def processar_pasta_pdfs(pasta_base: str, usuario: str = "Importado") -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Processa todos os PDFs de uma pasta (e subpastas)."""
    todas_acoes: List[pd.DataFrame] = []
    todos_div: List[pd.DataFrame] = []
    for raiz, _dirs, files in os.walk(pasta_base):
        for f in files:
            if not f.lower().endswith(".pdf"):
                continue
            caminho = os.path.join(raiz, f)
            try:
                df_a, df_d = processar_pdf_individual(caminho, usuario=usuario, mes_ano=None)
                if not df_a.empty:
                    todas_acoes.append(df_a)
                if not df_d.empty:
                    todos_div.append(df_d)
            except Exception:
                continue
    df_acoes = pd.concat(todas_acoes, ignore_index=True) if todas_acoes else pd.DataFrame()
    df_dividendos = pd.concat(todos_div, ignore_index=True) if todos_div else pd.DataFrame()
    return df_acoes, df_dividendos


def listar_pdfs_usuario(usuario: str, raiz_uploads: str = "uploads") -> List[str]:
    caminho_usuario = os.path.join(raiz_uploads, usuario)
    if not os.path.exists(caminho_usuario):
        return []
    pdfs: List[str] = []
    for raiz, _dirs, arquivos in os.walk(caminho_usuario):
        for arquivo in arquivos:
            if arquivo.lower().endswith(".pdf"):
                pdfs.append(os.path.join(raiz, arquivo))
    return sorted(pdfs)


def processar_pdfs_usuario(usuario: str, raiz_uploads: str = "uploads") -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Processa todos os PDFs armazenados para um usuário específico."""
    pdfs = listar_pdfs_usuario(usuario, raiz_uploads)
    todas_acoes: List[pd.DataFrame] = []
    todos_div: List[pd.DataFrame] = []
    for pdf in pdfs:
        try:
            df_a, df_d = processar_pdf_individual(pdf, usuario=usuario, mes_ano=None)
            if not df_a.empty:
                todas_acoes.append(df_a)
            if not df_d.empty:
                todos_div.append(df_d)
        except Exception:
            continue
    df_acoes = pd.concat(todas_acoes, ignore_index=True) if todas_acoes else pd.DataFrame()
    df_dividendos = pd.concat(todos_div, ignore_index=True) if todos_div else pd.DataFrame()
    return df_acoes, df_dividendos


if __name__ == "__main__":  # pragma: no cover
    exemplo = Path(r"C:\Users\hudso\Downloads\Stmt_20251130.pdf")
    if exemplo.exists():
        acoes_df, div_df = processar_pdf_individual(str(exemplo), usuario="Hudson", mes_ano=None)
        print(f"Ações: {len(acoes_df)} | Dividendos: {len(div_df)}")
    else:
        print("Arquivo de exemplo não encontrado.")
