"""
Parser V4 Corrigido - Suporta AMBOS formatos (Antigo e Novo)
- Antigo: Stmt_YYYYMMDD.pdf (5 páginas, tabela simples)
- Novo: Doc_101579_STATEMENT_...pdf (12+ páginas, estrutura complexa)
"""

import re
import pdfplumber
import pandas as pd
from typing import Dict, List
from pathlib import Path


class ParseadorAcoesPDFV4:
    """Parser que auto-detecta e extrai de ambos formatos"""

    TICKERS_CONHECIDOS = {
        "QQQS", "SRET", "IVV", "VUG", "VIG", "SPHD", "SPHQ", "PEY", "KBWD",
        "DIV", "SDIV", "AGG", "EEM", "LQD", "TLT", "VNQ", "VNQI", "VT", "KBWY"
    }

    def __init__(self, usuario_nome: str = "Importado"):
        self.usuario_nome = usuario_nome

    def _limpar_valor(self, valor_str: str) -> float:
        if not valor_str:
            return 0.0
        valor_str = valor_str.strip().replace("$", "").replace(",", "").replace("%", "")
        try:
            return float(valor_str)
        except ValueError:
            return 0.0

    def _detectar_formato(self, pdf_path: str) -> str:
        """Detecta se é ANTIGO (Stmt_YYYYMMDD.pdf) ou NOVO"""
        with pdfplumber.open(pdf_path) as pdf:
            # ANTIGO: 5 páginas, "PORTFOLIO SUMMARY" + "EQUITIES / OPTIONS" na pág 2
            if len(pdf.pages) <= 5:
                text_p2 = pdf.pages[1].extract_text() if len(pdf.pages) > 1 else ""
                if "PORTFOLIO SUMMARY" in text_p2 and "EQUITIES / OPTIONS" in text_p2:
                    return "ANTIGO"
            
            # NOVO: "EQUITIES / SECURITIES" em página 3+
            for page in pdf.pages[2:]:
                text = page.extract_text()
                if "EQUITIES" in text and "SECURITIES" in text:
                    return "NOVO"
        
        return "NOVO"

    def _extrair_formato_antigo(self, pdf_path: str) -> List[Dict]:
        """
        Extrai ações do formato antigo (Stmt_YYYYMMDD.pdf)
        Estrutura: DESCRIÇÃO TICKER CUSIP_TYPE QTY PREÇO $ VALOR ...
        Exemplo: iShares Core S&P 500 ETF IVV C 1.12263 604.66 $ 678.81 $ 660.87 2.71% 98.953%
        """
        acoes = []
        
        with pdfplumber.open(pdf_path) as pdf:
            if len(pdf.pages) < 2:
                return acoes
            
            text = pdf.pages[1].extract_text()
            linhas = text.split('\n')
            
            em_secao = False
            for linha in linhas:
                if "EQUITIES / OPTIONS" in linha:
                    em_secao = True
                    continue
                
                if not em_secao:
                    continue
                
                if "Total Equities" in linha or "Total Cash" in linha:
                    break
                
                if not linha.strip():
                    continue
                
                # Regex: (.+?) = descrição, ([A-Z]{2,5}) = ticker, ([A-Z]) = cusip type,
                #        ([\d.]+) = quantidade, ([\d.]+) = preço
                match = re.search(r'(.+?)\s+([A-Z]{2,5})\s+([A-Z])\s+([\d.]+)\s+([\d.]+)', linha)
                
                if match:
                    try:
                        descricao = match.group(1).strip()
                        ticker = match.group(2).strip()
                        cusip_type = match.group(3).strip()
                        quantidade = float(match.group(4))
                        preco = float(match.group(5))
                        
                        # Valor está após o próximo $
                        valor_match = re.search(r'\$\s*([\d.]+)', linha[match.end():])
                        valor = float(valor_match.group(1)) if valor_match else 0.0
                        
                        acao = {
                            "Produto": descricao,
                            "Ticker": ticker,
                            "Código de Negociação": ticker,
                            "Quantidade Disponível": quantidade,
                            "Preço de Fechamento": preco,
                            "Valor": valor,
                            "Mês/Ano": "01/2025",
                            "Usuário": self.usuario_nome
                        }
                        acoes.append(acao)
                    except (ValueError, AttributeError):
                        continue
        
        return acoes

    def _extrair_formato_novo(self, pdf_path: str) -> List[Dict]:
        """
        Extrai ações do formato novo usando o parser V3
        Se V3 não disponível, usa fallback inline
        """
        acoes = []
        
        try:
            # Tentar importar e usar o parser V3 que já funciona bem
            from modules.upload_pdf_avenue_v3 import ParseadorAcoesPDFV3
            
            print(f"[V4] Tentando usar V3 para {Path(pdf_path).name}")
            parser_v3 = ParseadorAcoesPDFV3("01/2025", self.usuario_nome)
            df_v3 = parser_v3.extrair_do_pdf(pdf_path)
            
            print(f"[V4] V3 retornou {len(df_v3)} ações")
            
            # Converter DataFrame V3 para lista de dicts V4
            if not df_v3.empty:
                for _, row in df_v3.iterrows():
                    acao = {
                        "Produto": str(row.get("Produto", "")),
                        "Ticker": str(row.get("Ticker", "")),
                        "Código de Negociação": str(row.get("Ticker", "")),
                        "Quantidade Disponível": float(row.get("Quantidade Disponível", 0)),
                        "Preço de Fechamento": float(row.get("Preço de Fechamento", 0)),
                        "Valor": float(row.get("Valor", 0)),
                        "Mês/Ano": str(row.get("Mês/Ano", "01/2025")),
                        "Usuário": self.usuario_nome
                    }
                    acoes.append(acao)
                print(f"[V4] Converteu {len(acoes)} ações")
            
            return acoes
        except Exception as e:
            print(f"⚠️ Parser V3 falhou: {type(e).__name__}: {e}")
        
        # Fallback: extração inline do formato novo
        try:
            with pdfplumber.open(pdf_path) as pdf:
                todas_linhas = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        linhas = text.split('\n')
                        todas_linhas.extend(linhas)
                
                em_equities = False
                for linha in todas_linhas:
                    if "EQUITIES / SECURITIES" in linha:
                        em_equities = True
                        continue
                    
                    if not em_equities:
                        continue
                    
                    if "Total Equities" in linha or "Total Portfolio" in linha:
                        break
                    
                    if not linha.strip() or "---" in linha or "SYMBOL" in linha:
                        continue
                    
                    # Procurar ticker
                    ticker_match = re.search(r'\b([A-Z]{2,5})\b', linha)
                    if ticker_match:
                        ticker = ticker_match.group(1)
                        
                        if ticker in self.TICKERS_CONHECIDOS:
                            numeros = re.findall(r'[\d.]+', linha)
                            
                            if len(numeros) >= 2:
                                try:
                                    acao = {
                                        "Produto": linha.split(ticker)[0].strip() or ticker,
                                        "Ticker": ticker,
                                        "Código de Negociação": ticker,
                                        "Quantidade Disponível": self._limpar_valor(numeros[0]),
                                        "Preço de Fechamento": self._limpar_valor(numeros[1]) if len(numeros) > 1 else 0.0,
                                        "Valor": self._limpar_valor(numeros[-1]),
                                        "Mês/Ano": "01/2025",
                                        "Usuário": self.usuario_nome
                                    }
                                    if acao["Valor"] > 0:
                                        acoes.append(acao)
                                except (ValueError, IndexError):
                                    continue
        except Exception as e:
            print(f"❌ Erro no fallback: {e}")
        
        return acoes

    def extrair(self, pdf_path: str) -> List[Dict]:
        """Extrai ações detectando automaticamente o formato"""
        formato = self._detectar_formato(pdf_path)
        print(f"[Parser V4] Formato detectado: {formato} ✅")
        
        if formato == "ANTIGO":
            return self._extrair_formato_antigo(pdf_path)
        else:
            return self._extrair_formato_novo(pdf_path)


def extrair_acoes_pdf_v4(pdf_path: str, usuario: str = "Importado") -> pd.DataFrame:
    """Função pública para extrair ações de qualquer formato"""
    parser = ParseadorAcoesPDFV4(usuario)
    acoes = parser.extrair(pdf_path)
    
    if acoes:
        df = pd.DataFrame(acoes)
        colunas_ordem = ["Produto", "Ticker", "Código de Negociação", 
                         "Quantidade Disponível", "Preço de Fechamento", "Valor", "Mês/Ano", "Usuário"]
        return df[[col for col in colunas_ordem if col in df.columns]]
    
    return pd.DataFrame()
