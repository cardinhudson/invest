"""
Debug: Entender por que primeiro GLOBAL X FDS não é extraído
"""

import pdfplumber
import re
from pathlib import Path

pdf_path = "Relatorios/Avenue/Hudson Cardin/Doc_101579_STATEMENT_6AV40121_2024_12_31_142026_73157_AM_eRVKImAs.pdf"

with pdfplumber.open(pdf_path) as pdf:
    todas_linhas = []
    for page_num, page in enumerate(pdf.pages):
        texto = page.extract_text()
        if texto:
            linhas = texto.split("\n")
            todas_linhas.extend(linhas)

    # Análise manual dos primeiros 3 dividendos
    print("ANÁLISE DOS 3 PRIMEIROS DIVIDENDOS:\n")
    
    # 1. GLOBAL X FDS
    print("="*80)
    print("1. GLOBAL X FDS")
    linha = "DIVIDEND 12/11/24 C GLOBAL X FDS $0.196 $5.14"
    print(f"Linha original: {linha}")
    match = re.match(r"DIVIDEND\s+(\d{1,2}/\d{1,2}/\d{2})\s+([CO])\s+(.+)", linha)
    if match:
        data, co, resto = match.groups()
        print(f"Data: {data}, CO: {co}, Resto: {resto}")
        numeros = re.findall(r"[\d.,]+", resto)
        print(f"Números encontrados: {numeros}")
        print(f"Último número (valor): {numeros[-1]}")
    print()
    
    # 2. GLOBAL X FUNDS
    print("="*80)
    print("2. GLOBAL X FUNDS")
    linha = "DIVIDEND 12/11/24 C GLOBAL X FUNDS 0.155 4.90"
    print(f"Linha original: {linha}")
    match = re.match(r"DIVIDEND\s+(\d{1,2}/\d{1,2}/\d{2})\s+([CO])\s+(.+)", linha)
    if match:
        data, co, resto = match.groups()
        print(f"Data: {data}, CO: {co}, Resto: {resto}")
        numeros = re.findall(r"[\d.,]+", resto)
        print(f"Números encontrados: {numeros}")
        print(f"Último número (valor): {numeros[-1]}")
    print()

    # 3. ISHARES
    print("="*80)
    print("3. ISHARES CORE")
    linha = "DIVIDEND 12/20/24 C ISHARES CORE S&P 500 ETF 2.134185 7.89"
    print(f"Linha original: {linha}")
    match = re.match(r"DIVIDEND\s+(\d{1,2}/\d{1,2}/\d{2})\s+([CO])\s+(.+)", linha)
    if match:
        data, co, resto = match.groups()
        print(f"Data: {data}, CO: {co}, Resto: {resto}")
        numeros = re.findall(r"[\d.,]+", resto)
        print(f"Números encontrados: {numeros}")
        print(f"Último número (valor): {numeros[-1]}")
