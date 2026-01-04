import pdfplumber
from pathlib import Path
import re

# Analisar PDFs para entender estrutura de dividendos
pdf_giselle = Path("Relatorios/Avenue/Giselle Cardin/Doc_101579_STATEMENT_6AU71559_2024_01_31_142026_74011_AM_RVE6fZSu.pdf")

print("ANÁLISE DE DIVIDENDOS - PDF Janeiro 2024")
print("="*120)

with pdfplumber.open(pdf_giselle) as doc:
    for page_num, page in enumerate(doc.pages):
        text = page.extract_text()
        
        if "DIVIDEND" in text or "PROVENTOS" in text:
            print(f"\n>>> PÁGINA {page_num + 1} - ENCONTROU DIVIDENDOS\n")
            
            # Extrai a seção
            match = re.search(
                r'(?:DIVIDENDS AND INTEREST|DIVIDEND|PROVENTOS)(.*?)(?:MISCELLANEOUS|Total Dividends|$)',
                text,
                re.DOTALL
            )
            
            if match:
                section = match.group(1)
                lines = section.split('\n')
                
                print("LINHAS BRUTAS:")
                print("-"*120)
                for i, line in enumerate(lines[:40]):
                    if line.strip():
                        print(f"{i:2d}: '{line}'")
                
                # Mostra tudo
                print("\n\nTEXTO COMPLETO DA SEÇÃO:")
                print("-"*120)
                print(section[:2000])
            
            break

print("\n\nAGORA TESTANDO COM PDF DE DEZEMBRO (HUDSON):")
print("="*120)

pdf_hudson_dez = Path("Relatorios/Avenue/Hudson Cardin/Doc_101579_STATEMENT_6AV40121_2024_12_31_142026_73157_AM_eRVKImAs.pdf")

with pdfplumber.open(pdf_hudson_dez) as doc:
    for page_num, page in enumerate(doc.pages):
        text = page.extract_text()
        
        if "DIVIDEND" in text:
            print(f"\n>>> PÁGINA {page_num + 1} - ENCONTROU DIVIDENDOS\n")
            
            match = re.search(
                r'(?:DIVIDENDS AND INTEREST|DIVIDEND)(.*?)(?:MISCELLANEOUS|Total Dividends|Total Cash|$)',
                text,
                re.DOTALL
            )
            
            if match:
                section = match.group(1)
                lines = section.split('\n')
                
                print("LINHAS BRUTAS:")
                print("-"*120)
                for i, line in enumerate(lines[:50]):
                    if line.strip():
                        print(f"{i:2d}: '{line}'")
