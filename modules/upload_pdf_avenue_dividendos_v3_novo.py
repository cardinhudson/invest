"""
Parser simplificado e robusto para Dividendos de PDFs Avenue V3
"""

import re
from pathlib import Path
from typing import Optional, List, Dict
import pdfplumber
import pandas as pd
from dataclasses import dataclass


@dataclass
class Dividendo:
    """Representa um dividendo extraído do PDF"""
    data_pagamento: str
    produto: str
    ticker: str
    valor_bruto: float
    imposto: float
    valor_liquido: float
    mes_ano: str
    usuario: str


class ParseadorDividendosPDFV3:
    """Parser robusto para dividendos em PDFs Avenue"""
    
    # Mapeamento de descrição para ticker
    DESCRICAO_TICKER_MAP = {
        'GLOBAL X FUNDS': 'DIV',
        'GLOBAL X SUPERDIVIDEND': 'SDIV',
        'GLOBAL X SUPERDIVIDEND REIT': 'SRET',
        'ISHARES CORE S&P 500': 'IVV',
        'ISHARES 20 PLUS YEAR TREASURY': 'TLT',
        'ISHARES IBOXX': 'LQD',
        'ISHARES MSCI EMERGING': 'EEM',
        'ISHARES CORE U S AGGREGATE': 'AGG',
        'ISHARES TRUST EMERGING MARKETS': 'EMB',
        'INVESCO S&P 500 QUALITY': 'SPHQ',
        'INVESCO S&P 500 HIGH DIVID': 'SPHD',
        'INVESCO HIGH YIELD EQUITY': 'PEY',
        'INVESCO KBW HIGH DIVID YIELD FINL': 'KBWD',
        'INVESCO KBW PREMIUM YIELD': 'KBWY',
        'VANGUARD GROWTH': 'VUG',
        'VANGUARD REAL ESTATE': 'VNQ',
        'VANGUARD DIVIDEND APPRECIATION': 'VIG',
        'VANGUARD GLOBAL EX': 'VNQI',
        'VANGUARD INTL EQUITY': 'VNQI',
        'VANGUARD TOTAL WORLD': 'VT',
    }
    
    def __init__(self, mes_ano: str, usuario: str):
        self.mes_ano = mes_ano
        self.usuario = usuario
    
    def _limpar_valor(self, valor_str: str) -> Optional[float]:
        """Converte string de valor para float"""
        if not valor_str:
            return None
        
        valor_str = str(valor_str).strip().replace("$", "").strip()
        
        if "," in valor_str and "." in valor_str:
            valor_str = valor_str.replace(",", "")
        elif "," in valor_str and "." not in valor_str:
            partes = valor_str.split(",")
            if len(partes[-1]) == 2:
                valor_str = valor_str.replace(",", ".")
            else:
                valor_str = valor_str.replace(",", "")
        
        try:
            return float(valor_str)
        except ValueError:
            return None
    
    def _extrair_mes_ano_do_nome(self, nome_arquivo: str) -> str:
        """Extrai mês/ano do nome do arquivo"""
        match = re.search(r'(\d{4})_(\d{2})_\d{2}', nome_arquivo)
        if match:
            ano, mes = match.groups()
            return f"{mes}/{ano}"
        return self.mes_ano
    
    def _extrair_ticker_da_descricao(self, descricao: str) -> Optional[str]:
        """Tenta extrair ticker da descrição"""
        descricao_upper = descricao.upper()
        
        # Procura no mapa
        for descricao_chave, ticker_valor in self.DESCRICAO_TICKER_MAP.items():
            if descricao_chave in descricao_upper:
                return ticker_valor
        
        # Tenta extrair do final
        match = re.search(r'\b([A-Z]{1,6})\s*$', descricao)
        if match:
            ticker = match.group(1)
            if ticker not in ['ETF', 'BOND', 'FUND', 'TRUST', 'U', 'S', 'II', 'USD', 'ON', 'WH']:
                return ticker
        
        return None
    
    def _processar_secao_dividendos(self, texto: str) -> List[Dividendo]:
        """Processa texto bruto da seção de dividendos"""
        dividendos = []
        linhas = texto.split('\n')
        
        i = 0
        while i < len(linhas):
            linha = linhas[i].strip()
            
            # Procura por linhas que começam com "DIVIDEND"
            if linha.startswith('DIVIDEND '):
                # Padrão: DIVIDEND 12/20/24 C ISHARES CORE S&P 500 ETF 2.134185 7.89
                match = re.match(r'DIVIDEND\s+(\d{1,2}/\d{1,2}/\d{2})\s+([CO])\s+(.+)', linha)
                
                if match:
                    data_raw = match.group(1)  # 12/20/24
                    acct_type = match.group(2)  # C or O
                    resto = match.group(3)  # ISHARES CORE S&P 500 ETF 2.134185 7.89
                    
                    # Extrai números do final
                    numeros = re.findall(r'[\d.,]+', resto)
                    
                    # Últimé provavelmente o valor bruto
                    if numeros:
                        valor_bruto_str = numeros[-1]
                        # Remove de resto
                        descricao_1 = re.sub(r'\s*[\d.,]+\s*$', '', resto).strip()
                    else:
                        valor_bruto_str = "0"
                        descricao_1 = resto
                    
                    # Coleta próximas linhas
                    i += 1
                    imposto = 0.0
                    descricao_completa = descricao_1
                    
                    # Próxima linha (pode ter WH ou continuação de descrição)
                    if i < len(linhas):
                        proxima = linhas[i].strip()
                        
                        if 'WH' in proxima:
                            # Extrai imposto
                            parts = proxima.split('WH')
                            if parts[0].strip():
                                descricao_completa += " " + parts[0].strip()
                            imposto = self._limpar_valor(parts[1].strip()) if len(parts) > 1 else 0.0
                            i += 1
                        else:
                            descricao_completa += " " + proxima
                            i += 1
                    
                    # Próximas linhas até encontrar "REC", "PAY", etc
                    while i < len(linhas):
                        proxima = linhas[i].strip()
                        
                        if proxima.startswith(('REC', 'PAY', 'NON-', 'CASH', 'CUSIP', 'DIVIDEND', 'Total')):
                            break
                        elif proxima == 'ETF':
                            descricao_completa += " ETF"
                            i += 1
                            break
                        elif proxima:
                            descricao_completa += " " + proxima
                            i += 1
                        else:
                            i += 1
                    
                    # Formata data
                    data_parts = data_raw.split('/')
                    try:
                        mes, dia, ano_curto = data_parts
                        ano = int(ano_curto)
                        if ano < 50:
                            ano += 2000
                        else:
                            ano += 1900
                        data_formatada = f"{mes}/{dia}/{ano}"
                    except:
                        data_formatada = data_raw
                    
                    # Extrai ticker
                    ticker = self._extrair_ticker_da_descricao(descricao_completa)
                    
                    # Calcula valores
                    valor_bruto = self._limpar_valor(valor_bruto_str) or 0.0
                    valor_liquido = valor_bruto - imposto
                    
                    # Valida
                    if valor_bruto > 0 and ticker:
                        dividendo = Dividendo(
                            data_pagamento=data_formatada,
                            produto=descricao_completa,
                            ticker=ticker,
                            valor_bruto=valor_bruto,
                            imposto=imposto,
                            valor_liquido=valor_liquido,
                            mes_ano=self.mes_ano,
                            usuario=self.usuario
                        )
                        dividendos.append(dividendo)
                else:
                    i += 1
            else:
                i += 1
        
        return dividendos
    
    def extrair_do_pdf(self, caminho_pdf: str) -> pd.DataFrame:
        """Extrai todos os dividendos do PDF"""
        dividendos = []
        
        with pdfplumber.open(caminho_pdf) as doc:
            # Extrai mês/ano do nome
            nome_arquivo = Path(caminho_pdf).name
            self.mes_ano = self._extrair_mes_ano_do_nome(nome_arquivo)
            
            # Coleta texto de TODAS as páginas com dividendos
            texto_completo = ""
            
            for page in doc.pages:
                text = page.extract_text()
                
                if "DIVIDEND" in text:
                    # Extrai seção
                    match = re.search(
                        r'(?:DIVIDENDS AND INTEREST|DIVIDEND)(.*?)(?:MISCELLANEOUS|TOTAL PRICED|Total Dividends|$)',
                        text,
                        re.DOTALL
                    )
                    
                    if match:
                        texto_completo += "\n" + match.group(1)
            
            # Processa
            if texto_completo:
                dividendos_extraidos = self._processar_secao_dividendos(texto_completo)
                dividendos.extend(dividendos_extraidos)
        
        # Converte para DataFrame
        if dividendos:
            df = pd.DataFrame([{
                'Data Comex': div.data_pagamento,
                'Produto': div.produto,
                'Ticker': div.ticker,
                'Valor Bruto': div.valor_bruto,
                'Imposto': div.imposto,
                'Valor Líquido': div.valor_liquido,
                'Mês/Ano': div.mes_ano,
                'Usuário': div.usuario
            } for div in dividendos])
            return df
        else:
            return pd.DataFrame()


def extrair_dividendos_pdf_v3(arquivo_pdf: str, usuario: str, mes_ano: str = "12/2024") -> pd.DataFrame:
    """
    Extrai dividendos de um PDF Avenue
    
    Args:
        arquivo_pdf: Caminho para o PDF
        usuario: Nome do usuário
        mes_ano: Mês/ano (extraído automaticamente)
    
    Returns:
        DataFrame com colunas: Data Comex, Produto, Ticker, 
        Valor Bruto, Imposto, Valor Líquido, Mês/Ano, Usuário
    """
    parser = ParseadorDividendosPDFV3(mes_ano, usuario)
    return parser.extrair_do_pdf(arquivo_pdf)


if __name__ == "__main__":
    pdf_hudson = "Relatorios/Avenue/Hudson Cardin/Doc_101579_STATEMENT_6AV40121_2024_12_31_142026_73157_AM_eRVKImAs.pdf"
    
    print("Testando parser de dividendos v3 NOVO...\n")
    df = extrair_dividendos_pdf_v3(pdf_hudson, "Hudson Cardin")
    
    print(f"Dividendos extraídos: {len(df)}")
    if len(df) > 0:
        print(f"\nTodos os dividendos:")
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        print(df)
        print(f"\n\nResumo:")
        print(f"  Total Bruto: ${df['Valor Bruto'].sum():.2f}")
        print(f"  Total Imposto: ${df['Imposto'].sum():.2f}")
        print(f"  Total Líquido: ${df['Valor Líquido'].sum():.2f}")
        print(f"  Tickers: {sorted(df['Ticker'].unique().tolist())}")
