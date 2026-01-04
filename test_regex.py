#!/usr/bin/env python3
import re

linhas = [
    'GLOBAL X FDS DIV C 27.9718 16.952 474.18 480.56 -1% 34 7.226%',
    'ISHARES CORE S&P 500 ETF IVV C 2.09908 485.20 1,018.47 995.99 2 14 15.520',
    'ISHARES 20 PLUS YEAR TREASURY TLT C 4.9267 96.66 476.21 487.15 -2 16 7.257',
]

for linha in linhas:
    print(f'Testando: {linha[:60]}')
    # Use raw string com pattern
    pattern = r'^(.+?)\s+([CO])\s+([\d.]+)\s+[\$]?([\d.,]+)\s+[\$]?([\d.,]+)'
    match = re.search(pattern, linha)
    if match:
        desc = match.group(1).strip()
        print(f'  DESC: {desc}')
        print(f'  QTD: {match.group(3)}, PREÇO: {match.group(4)}, VALOR: {match.group(5)}')
    else:
        print('  NO MATCH')
    print()
