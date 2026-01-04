"""
Parser v3 para Dividendos de PDFs Avenue
Melhoria sobre versão anterior:
- Suporta múltiplas páginas
- Extrai todas as informações (data, ticker, valores, imposto)
- Calcula corretamente o valor líquido
- Usa mapeamento de descrição para ticker
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
        'VANGUARD INDEX FUNDS VANGUARD GROWTH': 'VUG',
        'VANGUARD SPECIALIZED FUNDS VANGUARD REAL ESTATE': 'VNQ',
        'VANGUARD SPECIALIZED FUNDS VANGUARD DIVIDEND APPRECIATION': 'VIG',
        'VANGUARD GLOBAL EX': 'VNQI',
        'VANGUARD INTL EQUITY': 'VNQI',
        'VANGUARD TOTAL WORLD': 'VT',
    }
    
    # Padrão para linhas com DIVIDEND
    PADRAO_DIVIDEND = re.compile(
        r'DIVIDEND\s+(\d{1,2}/\d{1,2}/\d{2})\s+([CO])\s+(.+)'
    )
    
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
        match = re.search(r'\b([A-Z]{1,6})\s*$', descricao)
        if match:
            ticker = match.group(1)
            if ticker not in ['ETF', 'BOND', 'FUND', 'TRUST', 'U', 'S', 'II', 'USD']:
                return ticker
        
        # Busca no mapa de descrições
        descricao_upper = descricao.upper()
        for descricao_chave, ticker_valor in self.DESCRICAO_TICKER_MAP.items():
            if descricao_chave in descricao_upper:
                return ticker_valor
        
        return None
    
    def _processar_secao_dividendos(self, texto: str) -> List[Dividendo]:
        """Processa texto bruto da seção de dividendos"""
        dividendos = []
        linhas = texto.split('\n')
        
        i = 0
        while i < len(linhas):
            linha = linhas[i].strip()
            
            # Procura por padrão DIVIDEND
            if linha.startswith('DIVIDEND'):
                match = self.PADRAO_DIVIDEND.match(linha)
                
                if match:
                    data_pagamento_raw = match.group(1)
                    account_type = match.group(2)
                    descricao_1 = match.group(3).strip()
                    valor_bruto_str = match.group(4).strip()
                    
                    # Coleta valores até encontrar "WH" (imposto) e "SHS"
                    imposto = 0.0
                    descricao_2 = ""
                    descricao_3 = ""
                    
                    i += 1
                    
                    # Próxima linha geralmente tem descrição + WH + imposto
                    if i < len(linhas):
                        proxima = linhas[i].strip()
                        
                        # Se tem "WH", extrai imposto
                        if 'WH' in proxima:
                            # Separa descrição e imposto
                            parts = proxima.split('WH')
                            descricao_2 = parts[0].strip()
                            imposto_str = parts[1].strip() if len(parts) > 1 else ""
                            imposto = self._limpar_valor(imposto_str) or 0.0
                        else:
                            descricao_2 = proxima
                        
                        i += 1
                    
                    # Próxima linhas para coletar resto da descrição
                    while i < len(linhas):
                        proxima = linhas[i].strip()
                        
                        if proxima.startswith('SHS') or 'SHS' in proxima:
                            # Fim do bloco de descrição
                            break
                        elif proxima.startswith(('REC', 'PAY', 'CUSIP', 'NON-', 'CASH', 'DIVIDEND', 'Total')):
                            break
                        elif proxima and proxima != 'ETF':
                            # Continua coletando descrição
                            if descricao_3:
                                descricao_3 += " " + proxima
                            else:
                                descricao_3 = proxima
                            i += 1
                        elif proxima == 'ETF':
                            descricao_3 = 'ETF'
                            i += 1
                        else:
                            i += 1
                    
                    # Monta descrição completa
                    descricao_completa = descricao_1
                    if descricao_2:
                        descricao_completa += " " + descricao_2
                    if descricao_3:
                        descricao_completa += " " + descricao_3
                    
                    # Extrai ticker
                    ticker = self._extrair_ticker_da_descricao(descricao_completa)
                    
                    # Formata data (12/20/24 -> 12/20/2024)
                    data_parts = data_pagamento_raw.split('/')
                    if len(data_parts) == 3:
                        try:
                            mes, dia, ano = data_parts
                            ano_int = int(ano)
                            if ano_int < 50:
                                ano_int += 2000
                            elif ano_int < 100:
                                ano_int += 1900
                            data_formatada = f"{mes}/{dia}/{ano_int}"
                        except:
                            data_formatada = data_pagamento_raw
                    else:
                        data_formatada = data_pagamento_raw
                    
                    # Calcula valor líquido
                    valor_bruto = self._limpar_valor(valor_bruto_str) or 0.0
                    valor_liquido = valor_bruto - imposto
                    
                    # Cria objeto
                    dividendo = Dividendo(
                        data_pagamento=data_formatada,
                        produto=descricao_completa,
                        ticker=ticker or "UNKNOWN",
                        valor_bruto=valor_bruto,
                        imposto=imposto,
                        valor_liquido=valor_liquido,
                        mes_ano=self.mes_ano,
                        usuario=self.usuario
                    )
                    
                    # Valida
                    if dividendo.valor_bruto > 0 and dividendo.ticker != "UNKNOWN":
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
            # Extrai mês/ano do nome do arquivo
            nome_arquivo = Path(caminho_pdf).name
            self.mes_ano = self._extrair_mes_ano_do_nome(nome_arquivo)
            
            # Coleta texto de TODAS as páginas que têm dividendos
            texto_completo = ""
            
            for page in doc.pages:
                text = page.extract_text()
                
                # Procura por "DIVIDEND" ou "DIVIDENDS AND INTEREST"
                if "DIVIDEND" in text:
                    # Extrai a seção
                    match = re.search(
                        r'(?:DIVIDENDS AND INTEREST|DIVIDEND)(.*?)(?:MISCELLANEOUS|TOTAL PRICED|ACCOUNT|Total Dividends|$)',
                        text,
                        re.DOTALL
                    )
                    
                    if match:
                        texto_completo += "\n" + match.group(1)
            
            # Processa o texto coletado
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


# Função pública
def extrair_dividendos_pdf_v3(arquivo_pdf: str, usuario: str, mes_ano: str = "12/2024") -> pd.DataFrame:
    """
    Extrai dividendos de um PDF Avenue
    
    Args:
        arquivo_pdf: Caminho para o PDF
        usuario: Nome do usuário (ex: "Giselle Cardin")
        mes_ano: Mês/ano no formato MM/YYYY (extraído automaticamente)
    
    Returns:
        DataFrame com colunas: Data Comex, Produto, Ticker, 
        Valor Bruto, Imposto, Valor Líquido, Mês/Ano, Usuário
    """
    parser = ParseadorDividendosPDFV3(mes_ano, usuario)
    return parser.extrair_do_pdf(arquivo_pdf)


# Testes
if __name__ == "__main__":
    # Teste com PDF de dividendos
    pdf_hudson = "Relatorios/Avenue/Hudson Cardin/Doc_101579_STATEMENT_6AV40121_2024_12_31_142026_73157_AM_eRVKImAs.pdf"
    
    print("Testando parser de dividendos v3...\n")
    df = extrair_dividendos_pdf_v3(pdf_hudson, "Hudson Cardin")
    
    print(f"Dividendos extraídos: {len(df)}")
    print(f"\nTodos os dividendos:")
    print(df.to_string())
    print(f"\n\nResumo:")
    print(f"  Total Bruto: ${df['Valor Bruto'].sum():.2f}")
    print(f"  Total Imposto: ${df['Imposto'].sum():.2f}")
    print(f"  Total Líquido: ${df['Valor Líquido'].sum():.2f}")
    print(f"  Tickers: {df['Ticker'].unique().tolist()}")
