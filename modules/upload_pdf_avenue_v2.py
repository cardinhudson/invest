"""
Processamento melhorado de PDFs Avenue (v2).
Suporta dois modelos de PDFs com melhor extração de tickers e valores.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


# ============================================================================
# MAPEAMENTO DE DESCRIÇÕES PARA TICKERS (BASEADO EM PADRÃO AVENUE)
# ============================================================================

DESCRICAO_TICKER_MAP = {
    # Global X
    "global x fds div": "DGDV",  # Superdividend US Equity
    "global x superdividend u s etf": "DGDV",
    "global x fds sdiv": "SDIV",  # Superdividend US Equity ETF
    "global x superdividend etf": "SDIV",
    "global x funds sret": "SRET",  # Superdividend REIT ETF
    "global x superdividend reit": "SRET",
    
    # iShares Core
    "ishares core s&p 500": "IVV",
    "ishares core s p 500": "IVV",
    
    # iShares Bonds
    "ishares 20 plus year treasury": "TLT",
    "ishares 20 plus year treasury bond": "TLT",
    "ishares iboxx": "LQD",
    "ishares iboxx $ investment": "LQD",
    "ishares iboxx investment grade": "LQD",
    
    # iShares Aggregate Bonds
    "ishares core u s aggregate": "AGG",
    "ishares core aggregate bond": "AGG",
    
    # iShares Emerging Markets
    "ishares msci emerging": "EEM",
    "ishares msci emerging markets": "EEM",
    
    # Invesco
    "invesco s&p 500 quality": "SPHQ",
    "invesco kbw high": "KBWD",
    "invesco kbw premium": "KBWY",
    
    # Vanguard
    "vanguard growth": "VUG",
    "vanguard index funds vug": "VUG",
    "vanguard real estate": "VNQ",
    "vanguard dividend appreciation": "VIG",
    "vanguard specialized funds vig": "VIG",
    "vanguard global ex": "VNQI",
    "vanguard intl equity": "VT",
    "vanguard total world": "VT",
}


def _normalize_description(desc: str) -> str:
    """Normaliza descrição para matching com mapper."""
    desc = str(desc or "").lower().strip()
    # Remove caracteres especiais e múltiplos espaços
    desc = re.sub(r"[&$%]", "", desc)
    desc = re.sub(r"\s+", " ", desc)
    return desc.strip()


def _resolve_ticker_from_description(desc: str, proibidos: Optional[Set[str]] = None) -> Optional[str]:
    """Resolve ticker usando mapeamento de descrição."""
    desc_norm = _normalize_description(desc)
    
    # Busca exata
    for key, ticker in DESCRICAO_TICKER_MAP.items():
        if key in desc_norm:
            if ticker and (not proibidos or ticker not in proibidos):
                return ticker
    
    # Busca por padrão (palavras-chave presentes)
    for key, ticker in DESCRICAO_TICKER_MAP.items():
        if ticker is None:
            continue
        # Verifica se as palavras-chave aparecem em ordem
        key_words = key.split()
        desc_words = desc_norm.split()
        
        # Se tem pelo menos 2/3 das palavras-chave
        matches = sum(1 for kw in key_words if any(kw in dw for dw in desc_words))
        if len(key_words) > 0 and matches >= len(key_words) * 0.66:
            if not proibidos or ticker not in proibidos:
                return ticker
    
    return None


# ============================================================================
# CLASSES DE PARSER PARA AÇÕES
# ============================================================================

@dataclass
class AcaoExtraida:
    """Dados extraídos de uma ação."""
    produto: str  # Descrição do ativo
    ticker: str
    quantidade: float
    preco: float
    valor: float
    mes_ano: str
    usuario: str


class AcoesPdfParser:
    """Parser base para extrair ações de PDFs Avenue."""
    
    def __init__(self, arquivo_pdf: str, usuario: str = "Importado", mes_ano: Optional[str] = None):
        self.arquivo_pdf = arquivo_pdf
        self.usuario = usuario
        self.mes_ano = mes_ano or self._extrair_mes_ano()
        self.acoes: List[AcaoExtraida] = []
    
    def _extrair_mes_ano(self) -> str:
        """Extrai MM/AAAA do nome do arquivo."""
        nome = os.path.basename(self.arquivo_pdf)
        
        # Padrão: YYYY_MM_DD
        match = re.search(r"(\d{4})_(\d{2})_(\d{2})", nome)
        if match:
            ano, mes, _ = match.groups()
            if 1 <= int(mes) <= 12:
                return f"{mes}/{ano}"
        
        # Padrão: YYYYMMDD
        match = re.search(r"(\d{4})(\d{2})(\d{2})", nome)
        if match:
            ano, mes, _ = match.groups()
            if 1 <= int(mes) <= 12:
                return f"{mes}/{ano}"
        
        return "01/2025"
    
    def parse(self) -> List[AcaoExtraida]:
        """Parse principal - a ser sobrescrito."""
        raise NotImplementedError
    
    def _limpar_valor(self, valor_str: str) -> Optional[float]:
        """Limpa e converte string de valor para float."""
        if not valor_str:
            return None
        
        valor_str = str(valor_str).strip()
        # Remove $
        valor_str = valor_str.replace("$", "").strip()
        
        # Determinar se vírgula é separador de casa decimal ou de milhares
        # Padrão: se tem . antes de vírgula, vírgula é milhar
        if "," in valor_str and "." in valor_str:
            # Padrão: 1,234.56 (milhar com vírgula, decimal com ponto)
            valor_str = valor_str.replace(",", "")
        elif "," in valor_str and "." not in valor_str:
            # Pode ser 1,234 (inteiro com separador de milhar) ou 1,23 (decimal com vírgula)
            # Usar heurística: se tem só um separador e < 3 dígitos após, é decimal
            parts = valor_str.split(",")
            if len(parts) == 2 and len(parts[1]) == 2:
                # Provavelmente decimal
                valor_str = valor_str.replace(",", ".")
            else:
                # Separador de milhar
                valor_str = valor_str.replace(",", "")
        
        try:
            return float(valor_str)
        except ValueError:
            return None
    
    def _validar_acao(self, acao: AcaoExtraida) -> bool:
        """Valida dados extraídos."""
        # Validar quantidade e preço
        if acao.quantidade <= 0 or acao.preco <= 0:
            return False
        
        # Validar ticker
        if not acao.ticker or not (1 <= len(acao.ticker) <= 6 and acao.ticker.replace(".", "").isalpha()):
            return False
        
        # Validar valor (tolerância de 1% para erros de arredondamento)
        valor_esperado = acao.quantidade * acao.preco
        if abs(acao.valor - valor_esperado) > valor_esperado * 0.01:
            acao.valor = valor_esperado
        
        return True


class AcoesTableParser(AcoesPdfParser):
    """Parser que extrai ações de TABELAS nos PDFs."""
    
    def parse(self) -> List[AcaoExtraida]:
        """Extrai ações das tabelas detectadas por pdfplumber."""
        if pdfplumber is None:
            raise ImportError("pdfplumber não está instalado")
        
        with pdfplumber.open(self.arquivo_pdf) as pdf:
            for page_num, page in enumerate(pdf.pages):
                # Procurar por tabelas nas páginas 2-4 (Portfolio Summary)
                if page_num < 1 or page_num > 4:
                    continue
                
                text = page.extract_text()
                if "PORTFOLIO SUMMARY" not in text and "EQUITIES / OPTIONS" not in text:
                    continue
                
                # Primeiro tentar por texto estruturado (mais confiável para este PDF)
                self._processar_por_texto(text)
                
                # Depois tentar tabelas como fallback
                tables = page.extract_tables()
                if tables and not self.acoes:
                    for table in tables:
                        self._processar_tabela(table)
        
        return self.acoes
    
    def _processar_tabela(self, table: List[List[str]]) -> None:
        """Processa uma tabela extraída."""
        if not table or len(table) < 2:
            return
        
        # Encontrar header
        header_row = None
        for idx, linha in enumerate(table):
            linha_lower = " ".join([str(c).lower() for c in linha if c])
            if any(p in linha_lower for p in ["symbol", "description", "quantity", "price", "value"]):
                header_row = idx
                break
        
        if header_row is None:
            header_row = 0
        
        # Processar linhas de dados
        for linha in table[header_row + 1:]:
            self._processar_linha_tabela(linha)
    
    def _processar_linha_tabela(self, linha: List[str]) -> None:
        """Processa uma linha individual da tabela."""
        # Limpar e normalizar
        linha_clean = [str(c).strip() for c in linha if c]
        
        if not linha_clean or len(linha_clean) < 3:
            return
        
        # Verificar se é linha de dados válida
        primeira = linha_clean[0].lower()
        if any(p in primeira for p in ["total", "subtotal", "saldo", "page", "account"]):
            return
        
        # Padrão do PDF Avenue:
        # DESCRIÇÃO | ACCOUNT_TYPE | QUANTIDADE | PREÇO | VALOR | ...
        # Exemplo: ["GLOBAL X FDS DIV", "C", "27.9718", "$16.952", "$474.18", ...]
        
        # Tentar extrair componentes
        if len(linha_clean) >= 5:
            descricao = linha_clean[0]
            
            # O account type é geralmente "C" ou "O"
            # Procurar pelo primeiro numérico após o tipo
            idx_quantidade = None
            for i in range(1, len(linha_clean)):
                try:
                    float(linha_clean[i].replace(",", ".").replace("$", ""))
                    idx_quantidade = i
                    break
                except ValueError:
                    continue
            
            if idx_quantidade is None or idx_quantidade + 2 >= len(linha_clean):
                return
            
            # Extrair valores
            try:
                quantidade = self._limpar_valor(linha_clean[idx_quantidade])
                preco = self._limpar_valor(linha_clean[idx_quantidade + 1])
                valor = self._limpar_valor(linha_clean[idx_quantidade + 2])
                
                if quantidade is None or preco is None or valor is None:
                    return
            except (ValueError, IndexError):
                return
            
            # Resolver ticker
            ticker = _resolve_ticker_from_description(descricao)
            if not ticker:
                # Tentar encontrar ticker na descrição (último token de 1-6 caracteres)
                tokens = descricao.split()
                for token in reversed(tokens):
                    token_clean = token.strip("'\" ").upper()
                    if 1 <= len(token_clean) <= 6 and token_clean.isalpha():
                        ticker = token_clean
                        break
            
            if not ticker:
                return
            
            acao = AcaoExtraida(
                produto=descricao,
                ticker=ticker.upper(),
                quantidade=quantidade,
                preco=preco,
                valor=valor,
                mes_ano=self.mes_ano,
                usuario=self.usuario,
            )
            
            if self._validar_acao(acao):
                self.acoes.append(acao)
    
    def _processar_por_texto(self, texto: str) -> None:
        """Processa por padrões de texto (mais confiável para PDFs Avenue)."""
        linhas = texto.split("\n")
        
        # Encontrar início da seção EQUITIES
        inicio_idx = 0
        for i, linha in enumerate(linhas):
            if "EQUITIES / OPTIONS" in linha:
                inicio_idx = i + 1
                break
        
        # Processamos cada linha potencial de ação
        i = inicio_idx
        while i < len(linhas):
            linha = linhas[i].strip()
            i += 1
            
            if not linha:
                continue
            
            # Verificar se chegou ao fim da seção
            if "Total Equities" in linha or "Total Cash" in linha or "Total Buy" in linha or "ACCOUNT" in linha:
                break
            
            # Pular linhas de descrição continuada (linhas que só têm texto)
            if not re.search(r"[\d.]+", linha):
                continue
            
            # Padrão 1: Com account type (C ou O) 
            # GLOBAL X FDS DIV C 27.9718 $16.952 $474.18 $480.56 -1% $34 7.226%
            match = re.search(r"^(.+?)\s+([CO])\s+([\d.]+)\s+\$?([\d.,]+)\s+\$?([\d.,]+)", linha)
            
            if not match:
                continue
            
            try:
                descricao_raw = match.group(1).strip()
                # account_type = match.group(2)
                quantidade_str = match.group(3)
                preco_str = match.group(4)
                valor_str = match.group(5)
                
                quantidade = self._limpar_valor(quantidade_str)
                preco = self._limpar_valor(preco_str)
                valor = self._limpar_valor(valor_str)
                
                if quantidade is None or preco is None or valor is None:
                    continue
                
                if quantidade <= 0 or preco <= 0 or valor <= 0:
                    continue
                
                # Extrair TICKER da descrição
                ticker = None
                descricao_limpa = descricao_raw
                
                # Estratégia 1: Procurar por ticker isolado explícito (ex: "IVV", "TLT", "LQD", "SPHQ")
                # Esses tickers aparecem em maiúsculas de 1-6 chars, geralmente antes/depois da descrição
                tokens = descricao_raw.split()
                
                # Procurar de trás para frente (mais comum estar no fim)
                for idx, token in enumerate(reversed(tokens)):
                    token_clean = token.strip("'\" ").upper()
                    # Validar: 1-6 caracteres, apenas letras
                    if 1 <= len(token_clean) <= 6 and token_clean.isalpha():
                        # Não aceitar palavras-chave comuns
                        palavras_comuns = {"AND", "ETF", "ETN", "FUND", "TRUST", "BOND", "REIT", "STOCK", "PLUS", "YEAR", "THE", "ON", "OF", "BD"}
                        if token_clean not in palavras_comuns:
                            ticker = token_clean
                            # Remover ticker da descrição se foi no fim
                            if idx == 0 and len(tokens) > 1:
                                descricao_limpa = " ".join(tokens[:-1])
                            break
                
                # Estratégia 2: Usar mapeamento se não encontrou
                if not ticker:
                    ticker = _resolve_ticker_from_description(descricao_raw)
                    descricao_limpa = descricao_raw
                
                # Estratégia 3: Procurar de frente para trás se ainda não achou
                if not ticker:
                    for token in tokens:
                        token_clean = token.strip("'\" ").upper()
                        if 1 <= len(token_clean) <= 6 and token_clean.isalpha():
                            if token_clean not in {"AND", "ETF", "ETN", "FUND", "TRUST", "BOND", "REIT"}:
                                ticker = token_clean
                                break
                
                ticker = ticker or "UNKNOWN"
                
                acao = AcaoExtraida(
                    produto=descricao_limpa,
                    ticker=ticker,
                    quantidade=quantidade,
                    preco=preco,
                    valor=valor,
                    mes_ano=self.mes_ano,
                    usuario=self.usuario,
                )
                
                if self._validar_acao(acao):
                    self.acoes.append(acao)
            
            except (ValueError, IndexError, AttributeError):
                continue


# ============================================================================
# CLASSES DE PARSER PARA DIVIDENDOS
# ============================================================================

@dataclass
class DividendoExtraido:
    """Dados extraídos de um dividendo."""
    produto: str
    data_pagamento: str
    tipo_provento: str
    valor_liquido: float
    mes_ano: str
    usuario: str


class DividendosPdfParser:
    """Parser base para extrair dividendos de PDFs Avenue."""
    
    def __init__(
        self,
        arquivo_pdf: str,
        usuario: str = "Importado",
        mes_ano: Optional[str] = None,
        tickers_portfolio: Optional[Set[str]] = None,
    ):
        self.arquivo_pdf = arquivo_pdf
        self.usuario = usuario
        self.mes_ano = mes_ano or self._extrair_mes_ano()
        self.tickers_portfolio = tickers_portfolio or set()
        self.dividendos: List[DividendoExtraido] = []
    
    def _extrair_mes_ano(self) -> str:
        """Extrai MM/AAAA do nome do arquivo."""
        nome = os.path.basename(self.arquivo_pdf)
        
        match = re.search(r"(\d{4})_(\d{2})_(\d{2})", nome)
        if match:
            ano, mes, _ = match.groups()
            if 1 <= int(mes) <= 12:
                return f"{mes}/{ano}"
        
        match = re.search(r"(\d{4})(\d{2})(\d{2})", nome)
        if match:
            ano, mes, _ = match.groups()
            if 1 <= int(mes) <= 12:
                return f"{mes}/{ano}"
        
        return "01/2025"
    
    def parse(self) -> List[DividendoExtraido]:
        """Parse principal."""
        raise NotImplementedError
    
    def _limpar_valor(self, valor_str: str) -> Optional[float]:
        """Limpa e converte string de valor para float."""
        if not valor_str:
            return None
        
        valor_str = str(valor_str).strip()
        valor_str = valor_str.replace("$", "").replace(",", ".").strip()
        
        try:
            return float(valor_str)
        except ValueError:
            return None
    
    def _validar_dividendo(self, dividendo: DividendoExtraido) -> bool:
        """Valida dados extraídos."""
        if dividendo.valor_liquido <= 0:
            return False
        
        if not dividendo.produto or not dividendo.data_pagamento:
            return False
        
        return True


class DividendosTableParser(DividendosPdfParser):
    """Parser que extrai dividendos de TABELAS."""
    
    def parse(self) -> List[DividendoExtraido]:
        """Extrai dividendos das tabelas."""
        if pdfplumber is None:
            raise ImportError("pdfplumber não está instalado")
        
        with pdfplumber.open(self.arquivo_pdf) as pdf:
            for page_num, page in enumerate(pdf.pages):
                # Dividendos geralmente estão nas páginas 4+
                if page_num < 3:
                    continue
                
                text = page.extract_text()
                if "DIVIDEND" not in text and "dividend" not in text.lower():
                    continue
                
                # Tentar extrair tabelas
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        self._processar_tabela(table)
                else:
                    # Fallback: processar por texto
                    self._processar_por_texto(text)
        
        return self.dividendos
    
    def _processar_tabela(self, table: List[List[str]]) -> None:
        """Processa tabela de dividendos."""
        if not table or len(table) < 2:
            return
        
        for linha in table[1:]:
            self._processar_linha_tabela(linha)
    
    def _processar_linha_tabela(self, linha: List[str]) -> None:
        """Processa uma linha de dividendo."""
        linha_clean = [str(c).strip() for c in linha if c]
        
        if not linha_clean or len(linha_clean) < 3:
            return
        
        # Padrão de tabela de dividendos (pode variar)
        # DATA | PRODUTO | VALOR | ...
        if len(linha_clean) >= 3:
            data = linha_clean[0]
            produto = linha_clean[1]
            valor_str = linha_clean[2]
            
            valor = self._limpar_valor(valor_str)
            
            if valor is None:
                return
            
            # Resolver ticker/produto
            ticker = _resolve_ticker_from_description(produto)
            produto_final = ticker if ticker else produto
            
            dividendo = DividendoExtraido(
                produto=produto_final,
                data_pagamento=data,
                tipo_provento="Dividendo",
                valor_liquido=valor,
                mes_ano=self.mes_ano,
                usuario=self.usuario,
            )
            
            if self._validar_dividendo(dividendo):
                self.dividendos.append(dividendo)
    
    def _processar_por_texto(self, texto: str) -> None:
        """Fallback: processa por padrões de texto."""
        # Buscar seção de dividendos
        if "DIVIDENDS AND INTEREST" not in texto and "DIVIDEND" not in texto:
            return
        
        # Extrair linhas relevantes
        linhas = texto.split("\n")
        em_dividendos = False
        
        for i, linha in enumerate(linhas):
            if "DIVIDENDS AND INTEREST" in linha:
                em_dividendos = True
                continue
            
            if em_dividendos and ("Total" in linha or "FUNDS" in linha):
                em_dividendos = False
                break
            
            if not em_dividendos:
                continue
            
            # Procurar por padrão de data
            if re.search(r"\d{2}/\d{2}/\d{2}", linha):
                # Pode ser uma linha de dividendo
                match = re.search(r"(\d{2}/\d{2}/\d{2})", linha)
                if match:
                    data = match.group(1)
                    
                    # Procurar valor com $
                    valor_match = re.search(r"\$?([\d.,]+)", linha)
                    if valor_match:
                        valor_str = valor_match.group(1)
                        valor = self._limpar_valor(valor_str)
                        
                        if valor and valor > 0:
                            # Procurar ticker
                            ticker = None
                            
                            # Procurar próxima linha
                            if i + 1 < len(linhas):
                                prox = linhas[i + 1].strip()
                                tokens = prox.split()
                                for token in tokens:
                                    token_clean = token.strip("'\" ").upper()
                                    if 1 <= len(token_clean) <= 6 and token_clean.isalpha():
                                        ticker = token_clean
                                        break
                            
                            produto = ticker if ticker else "Dividendo"
                            
                            dividendo = DividendoExtraido(
                                produto=produto,
                                data_pagamento=data,
                                tipo_provento="Dividendo",
                                valor_liquido=valor,
                                mes_ano=self.mes_ano,
                                usuario=self.usuario,
                            )
                            
                            if self._validar_dividendo(dividendo):
                                self.dividendos.append(dividendo)


# ============================================================================
# FUNÇÕES PÚBLICAS (compatíveis com API anterior)
# ============================================================================

def extrair_acoes_pdf_v2(
    arquivo_pdf: str,
    usuario: str = "Importado",
    mes_ano: Optional[str] = None,
) -> pd.DataFrame:
    """Extrai ações de um PDF Avenue (v2 melhorada)."""
    if pdfplumber is None:
        raise ImportError("pdfplumber não está instalado")
    
    parser = AcoesTableParser(arquivo_pdf, usuario=usuario, mes_ano=mes_ano)
    acoes = parser.parse()
    
    if not acoes:
        return pd.DataFrame()
    
    data = [
        {
            "Produto": acao.produto,
            "Ticker": acao.ticker,
            "Código de Negociação": acao.ticker,
            "Quantidade Disponível": acao.quantidade,
            "Preço de Fechamento": acao.preco,
            "Valor": acao.valor,
            "Mês/Ano": acao.mes_ano,
            "Usuário": acao.usuario,
        }
        for acao in acoes
    ]
    
    df = pd.DataFrame(data)
    return df.drop_duplicates(subset=["Ticker", "Quantidade Disponível", "Mês/Ano", "Usuário"])


def extrair_dividendos_pdf_v2(
    arquivo_pdf: str,
    usuario: str = "Importado",
    mes_ano: Optional[str] = None,
    tickers_portfolio: Optional[Set[str]] = None,
) -> pd.DataFrame:
    """Extrai dividendos de um PDF Avenue (v2 melhorada)."""
    if pdfplumber is None:
        raise ImportError("pdfplumber não está instalado")
    
    parser = DividendosTableParser(
        arquivo_pdf,
        usuario=usuario,
        mes_ano=mes_ano,
        tickers_portfolio=tickers_portfolio,
    )
    dividendos = parser.parse()
    
    if not dividendos:
        return pd.DataFrame()
    
    data = [
        {
            "Produto": div.produto,
            "Data de Pagamento": div.data_pagamento,
            "Tipo de Provento": div.tipo_provento,
            "Valor Líquido": div.valor_liquido,
            "Mês/Ano": div.mes_ano,
            "Usuário": div.usuario,
        }
        for div in dividendos
    ]
    
    df = pd.DataFrame(data)
    return df.drop_duplicates(subset=["Produto", "Data de Pagamento", "Valor Líquido", "Mês/Ano", "Usuário"])


def testar_extracao(arquivo_pdf: str, usuario: str = "Importado") -> None:
    """Função de teste para validar extração."""
    print(f"\n{'='*80}")
    print(f"TESTE: {os.path.basename(arquivo_pdf)}")
    print(f"{'='*80}\n")
    
    # Ações
    df_acoes = extrair_acoes_pdf_v2(arquivo_pdf, usuario=usuario)
    print(f"✓ Ações extraídas: {len(df_acoes)}")
    print(df_acoes[["Produto", "Ticker", "Quantidade Disponível", "Preço de Fechamento", "Valor"]].to_string())
    
    # Dividendos
    tickers = set(df_acoes["Ticker"].dropna().unique())
    df_divs = extrair_dividendos_pdf_v2(arquivo_pdf, usuario=usuario, tickers_portfolio=tickers)
    print(f"\n✓ Dividendos extraídos: {len(df_divs)}")
    if not df_divs.empty:
        print(df_divs[["Produto", "Data de Pagamento", "Valor Líquido"]].to_string())
    
    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    # Teste rápido
    base_dir = r"Relatorios\Avenue"
    
    for folder in os.listdir(base_dir):
        folder_path = os.path.join(base_dir, folder)
        if not os.path.isdir(folder_path):
            continue
        
        pdfs = [f for f in os.listdir(folder_path) if f.endswith(".pdf")]
        if not pdfs:
            continue
        
        pdf_path = os.path.join(folder_path, pdfs[0])
        testar_extracao(pdf_path, usuario=folder)
        break
