"""
Parser Melhorado para Ações PDF Avenue - SUPORTA AMBOS OS FORMATOS
- Novo (Hudson/Giselle moderno): 12+ páginas, seção complexa
- Antigo (Stmt_YYYYMMDD.pdf): 5 páginas, formato tabular simples
"""

import re
import pdfplumber
import pandas as pd
from typing import Dict, List, Tuple, Optional
from pathlib import Path


class ParseadorAcoesPDFV4:
    """Parser de ações Avenue compatível com AMBOS os formatos"""

    DESCRICAO_TICKER_MAP = {
        "GLOBAL X FDS": "QQQS",
        "GLOBAL X FUNDS": "SRET",
        "GLOBAL X NASDAQ": "QQQS",
        "ISHARES CORE": "IVV",
        "ISHARES": "IVV",
        "VANGUARD GROWTH": "VUG",
        "VANGUARD DIVIDEND": "VIG",
        "VANGUARD INDEX": "VUG",
        "VANGUARD SPECIALIZED": "VIG",
        "S&P 500 HIGH DIVID": "SPHD",
        "S&P 500 QUALITY": "SPHQ",
        "INVESCO S&P 500": "SPHQ",
        "HIGH YIELD EQUITY": "PEY",
        "KBW HIGH DIVID": "KBWD",
        "DIVIDEND APPRECIATION": "VIG",
    }

    TICKERS_CONHECIDOS = {
        "QQQS", "SRET", "IVV", "VUG", "VIG", "SPHD", "SPHQ", "PEY", "KBWD", 
        "DIV", "SDIV", "AGG", "EEM", "LQD", "TLT", "VNQ", "VNQI", "VT", "KBWY"
    }

    def __init__(self, usuario_nome: str = "Importado"):
        self.usuario_nome = usuario_nome
        self.formato_detectado = None

    def _limpar_valor(self, valor_str: str) -> float:
        """Converte string de valor para float"""
        if not valor_str:
            return 0.0
        valor_str = valor_str.strip().replace("$", "").replace(",", "")
        try:
            return float(valor_str)
        except ValueError:
            return 0.0

    def _detectar_formato(self, pdf_path: str) -> str:
        """Detecta se é novo ou formato antigo"""
        with pdfplumber.open(pdf_path) as pdf:
            # Formato antigo: "PORTFOLIO SUMMARY" na página 2
            if len(pdf.pages) <= 5:
                text_p2 = pdf.pages[1].extract_text() if len(pdf.pages) > 1 else ""
                if "PORTFOLIO SUMMARY" in text_p2 and "EQUITIES / OPTIONS" in text_p2:
                    return "ANTIGO"
            
            # Formato novo: "EQUITIES / SECURITIES" em página 3+
            for page in pdf.pages[2:]:
                text = page.extract_text()
                if "EQUITIES" in text and "SECURITIES" in text:
                    return "NOVO"
        
        return "NOVO"  # Padrão

    def _extrair_formato_antigo(self, pdf_path: str) -> List[Dict]:
        """Extrai ações do formato antigo com regex exato"""
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
                
                # Regex para estrutura: DESCRIÇÃO TICKER CUSIP_TYPE QTY PREÇO $ VALOR ...
                # Exemplo: iShares Core S&P 500 ETF IVV C 1.12263 604.66 $ 678.81 $ 660.87 2.71% 98.953%
                
                # Procurar pelo primeiro símbolo em CAPS de 2-5 letras (é o ticker)
                match = re.search(r'(.+?)\s+([A-Z]{2,5})\s+([A-Z])\s+([\d.]+)\s+([\d.]+)', linha)
                
                if match:
                    try:
                        descricao = match.group(1).strip()      # iShares Core S&P 500 ETF
                        ticker = match.group(2).strip()         # IVV
                        cusip_type = match.group(3).strip()     # C
                        quantidade = float(match.group(4))       # 1.12263
                        preco = float(match.group(5))            # 604.66
                        
                        # O valor está após o próximo $
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
        """Extrai ações do formato novo (implementação inline)"""
        acoes = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                todas_linhas = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        linhas = text.split('\n')
                        todas_linhas.extend(linhas)
                
                # Procurar seção EQUITIES
                em_equities = False
                for linha in todas_linhas:
                    if "EQUITIES / SECURITIES" in linha or ("EQUITIES" in linha and "SECURITIES" in linha):
                        em_equities = True
                        continue
                    
                    if not em_equities:
                        continue
                    
                    # Parar na próxima seção
                    if "Total Equities" in linha or "Total Portfolio" in linha:
                        break
                    
                    if not linha.strip() or "---" in linha:
                        continue
                    
                    # Extrair ticker
                    ticker_match = re.search(r'\b([A-Z]{2,5})\b', linha)
                    if ticker_match:
                        ticker = ticker_match.group(1)
                        
                        # Validar ticket
                        if ticker in self.TICKERS_CONHECIDOS or self._extrair_ticker_da_descricao(linha) == ticker:
                            numeros = re.findall(r'[\d.,]+', linha)
                            
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
                                    if acao["Valor"] > 0:  # Validar
                                        acoes.append(acao)
                                except (ValueError, IndexError):
                                    continue
        except Exception as e:
            print(f"Erro ao extrair formato novo: {e}")
        
        return acoes

    def _extrair_ticker_da_descricao(self, descricao: str) -> str:
        """Extrai ticker da descrição"""
        descricao_upper = descricao.upper()
        for pattern, ticker in self.DESCRICAO_TICKER_MAP.items():
            if pattern in descricao_upper:
                return ticker
        return ""

    def extrair(self, pdf_path: str) -> List[Dict]:
        """Extrai ações detectando automaticamente o formato"""
        self.formato_detectado = self._detectar_formato(pdf_path)
        print(f"[Parser V4] Formato detectado: {self.formato_detectado} ✅")
        
        if self.formato_detectado == "ANTIGO":
            acoes = self._extrair_formato_antigo(pdf_path)
        else:
            acoes = self._extrair_formato_novo(pdf_path)
        
        print(f"✅ Ações extraídas: {len(acoes)}")
        
        for acao in acoes[:3]:  # Mostrar primeiras 3
            print(f"  Ticker: {acao['Ticker']}, "
                  f"Produto: {acao['Produto'][:30]}, "
                  f"Qtd: {acao['Quantidade Disponível']}, "
                  f"Valor: {acao['Valor']}")
        
        return acoes


def extrair_acoes_pdf_v4(pdf_path: str, usuario: str = "Importado") -> pd.DataFrame:
    """Interface pública para extrair ações"""
    parser = ParseadorAcoesPDFV4(usuario)
    acoes = parser.extrair(pdf_path)
    
    if acoes:
        df = pd.DataFrame(acoes)
        return df[["Produto", "Ticker", "Código de Negociação", "Quantidade Disponível", 
                   "Preço de Fechamento", "Valor", "Mês/Ano", "Usuário"]]
    
    return pd.DataFrame()


if __name__ == "__main__":
    # Teste com arquivos antigos
    from pathlib import Path
    
    pdf_dir = Path("Relatorios/Giselle Cardin")
    
    for pdf_file in pdf_dir.glob("Stmt_*.pdf"):
        print(f"\n{'='*60}")
        print(f"Testando: {pdf_file.name}")
        print(f"{'='*60}")
        
        df = extrair_acoes_pdf_v4(str(pdf_file), "Giselle Cardin")
        
        if not df.empty:
            print("\nDados extraídos:")
            print(df.to_string())
        else:
            print("⚠️ Nenhuma ação extraída")
