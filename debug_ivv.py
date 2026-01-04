#!/usr/bin/env python3
import re
from modules.upload_pdf_avenue_v2 import AcoesTableParser, _resolve_ticker_from_description
import pdfplumber

pdf_path = r'Relatorios\Avenue\Giselle Cardin\Doc_101579_STATEMENT_6AU71559_2024_01_31_142026_74011_AM_RVE6fZSu.pdf'

parser = AcoesTableParser(pdf_path, usuario='Giselle')

with pdfplumber.open(pdf_path) as pdf:
    page = pdf.pages[2]
    text = page.extract_text()
    linhas = text.split('\n')
    
    print('=== PROCURANDO IVV ===\n')
    
    for i, linha in enumerate(linhas):
        if 'IVV' in linha:
            print(f'Linha encontrada: {linha}')
            print()
            
            # Testar regex
            pattern = r'^(.+?)\s+([CO])\s+([\d.]+)\s+[\$]?([\d.,]+)\s+[\$]?([\d.,]+)'
            match = re.search(pattern, linha)
            
            if match:
                desc_raw = match.group(1).strip()
                qtd_str = match.group(3)
                preco_str = match.group(4)
                valor_str = match.group(5)
                
                print(f'DESC RAW: {desc_raw}')
                print(f'QTD: {qtd_str}, PREÇO: {preco_str}, VALOR: {valor_str}')
                
                # Limpar valores
                qtd = parser._limpar_valor(qtd_str)
                preco = parser._limpar_valor(preco_str)
                valor = parser._limpar_valor(valor_str)
                
                print(f'QTD limpo: {qtd}, PREÇO limpo: {preco}, VALOR limpo: {valor}')
                
                # Validação
                print(f'\nValidações:')
                print(f'  qtd > 0: {qtd > 0 if qtd else False}')
                print(f'  preco > 0: {preco > 0 if preco else False}')
                print(f'  valor > 0: {valor > 0 if valor else False}')
                
                # Ticker
                tokens = desc_raw.split()
                print(f'\nTokens: {tokens}')
                
                ticker = None
                for idx, token in enumerate(reversed(tokens)):
                    token_clean = token.strip("'\" ").upper()
                    print(f'  Token[{idx}] = {token_clean} (len={len(token_clean)})')
                    if 1 <= len(token_clean) <= 6 and token_clean.isalpha():
                        palavras_comuns = {"AND", "ETF", "ETN", "FUND", "TRUST", "BOND", "REIT", "STOCK", "PLUS", "YEAR", "THE", "ON", "OF", "BD"}
                        if token_clean not in palavras_comuns:
                            print(f'    -> VÁLIDO, usando como ticker!')
                            ticker = token_clean
                            break
                        else:
                            print(f'    -> Palavra comum, pulando')
                
                print(f'\nTicker final: {ticker}')
                
                # Test mapping
                mapped_ticker = _resolve_ticker_from_description(desc_raw)
                print(f'Mapped ticker: {mapped_ticker}')
