import pdfplumber
from pathlib import Path
import re

pdf_hudson = Path("Relatorios/Avenue/Hudson Cardin/Doc_101579_STATEMENT_6AV40121_2024_12_31_142026_73157_AM_eRVKImAs.pdf")

with pdfplumber.open(pdf_hudson) as doc:
    # Procura páginas com DIVIDEND
    for page_num in [4, 5, 6]:  # Páginas onde vimos DIVIDEND
        page = doc.pages[page_num]
        text = page.extract_text()
        
        if "DIVIDEND" in text:
            print(f"\n>>> PÁGINA {page_num + 1} - ANALISANDO ESTRUTURA\n")
            
            # Mostra o texto completo linha por linha
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if i > 70:
                    break
                print(f"{i:2d}: '{line}'")
