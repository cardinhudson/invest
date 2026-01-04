"""
Debug: Verificar quais dividendos estão sendo processados
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

    # Procura por linhas DIVIDEND
    print("Linhas DIVIDEND encontradas:")
    for i, linha in enumerate(todas_linhas):
        if linha.strip().startswith("DIVIDEND "):
            print(f"\n[Linha {i}] {linha}")
            # Mostra as próximas 5 linhas
            for j in range(1, 6):
                if i + j < len(todas_linhas):
                    print(f"  [+{j}] {todas_linhas[i+j]}")
