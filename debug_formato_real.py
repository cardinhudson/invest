import pdfplumber
from pathlib import Path

pdf_path = Path("Relatorios/Avenue/Giselle Cardin/Doc_101579_STATEMENT_6AU71559_2024_01_31_142026_74011_AM_RVE6fZSu.pdf")

print(f"Analisando: {pdf_path.name}\n")
print("="*120)

with pdfplumber.open(pdf_path) as doc:
    # Encontra a página com EQUITIES
    for page_num, page in enumerate(doc.pages):
        text = page.extract_text()
        
        if "EQUITIES" in text:
            print(f"PÁGINA {page_num + 1} - FORMATO TEXTO PURO:\n")
            
            lines = text.split('\n')
            
            # Encontra a linha de EQUITIES
            start_idx = None
            for i, line in enumerate(lines):
                if "EQUITIES" in line:
                    start_idx = i
                    break
            
            if start_idx:
                print("LINHAS BRUTAS DO PDF:")
                print("-"*120)
                for i in range(start_idx, min(start_idx + 50, len(lines))):
                    print(f"{i:2d}: '{lines[i]}'")
            
            # Também tenta extrair tabelas
            print("\n\nTABELAS DO PDF:")
            print("-"*120)
            
            tables = page.extract_tables()
            for table_idx, table in enumerate(tables):
                print(f"\nTabela {table_idx + 1} ({len(table)} linhas):")
                for row_idx, row in enumerate(table):
                    if row_idx < 20:  # Primeiras 20 linhas
                        print(f"  Row {row_idx}: {row}")
            
            break

print("\n\nAGORA VAMOS EXTRAIR COM REGEX:")
print("="*120)

# Teste com regex
import re

with pdfplumber.open(pdf_path) as doc:
    for page in doc.pages:
        text = page.extract_text()
        
        if "EQUITIES" in text:
            # Extrai seção EQUITIES
            match = re.search(r'EQUITIES / OPTIONS(.*?)(?:Total Equities|TOTAL PORTFOLIO|$)', text, re.DOTALL)
            if match:
                equities_section = match.group(1).strip()
                print("SEÇÃO EQUITIES EXTRAÍDA:")
                print(equities_section[:2000])
                
                # Tenta encontrar padrão das linhas
                print("\n\nTENTANDO REGEX PATTERN:")
                lines = equities_section.split('\n')
                
                # Pattern para: DESCRIÇÃO ... TICKER ... QUANTIDADE ... PREÇO ... VALOR
                for line in lines[:30]:
                    if line.strip():
                        print(f"  '{line}'")
            
            break
