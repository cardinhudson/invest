import re
import pdfplumber
from pathlib import Path

pdf_path = Path("Relatorios/Avenue/Giselle Cardin/Doc_101579_STATEMENT_6AU71559_2024_01_31_142026_74011_AM_RVE6fZSu.pdf")

with pdfplumber.open(pdf_path) as doc:
    for page in doc.pages:
        text = page.extract_text()
        
        if "VANGUARD" in text:
            # Procura a seção completa
            match = re.search(
                r'EQUITIES\s*/\s*OPTIONS(.*?)(?:Total Equities|TOTAL PRICED PORTFOLIO|$)',
                text,
                re.DOTALL
            )
            
            if match:
                section = match.group(1)
                print("SEÇÃO EQUITIES COMPLETA:")
                print("="*100)
                lines = section.split('\n')
                for i, line in enumerate(lines):
                    if line.strip():
                        print(f"{i:2d}: '{line}'")
            break
