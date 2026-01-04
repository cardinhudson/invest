import pdfplumber
from pathlib import Path

pdf_path = Path("Relatorios/Avenue/Giselle Cardin/Doc_101579_STATEMENT_6AU71559_2024_01_31_142026_74011_AM_RVE6fZSu.pdf")

with pdfplumber.open(pdf_path) as doc:
    print(f"Total de páginas: {len(doc.pages)}\n")
    
    for page_num, page in enumerate(doc.pages):
        text = page.extract_text()
        
        # Conta tickers
        import re
        tickers = re.findall(r'\b([A-Z]{1,6})\s+[CO]\s+[\d.]', text)
        
        if tickers:
            print(f"Página {page_num + 1}: {len(tickers)} tickers encontrados")
            print(f"  Tickers: {set(tickers)}\n")
            
            # Se tem VANGUARD, mostra as linhas
            if 'VANGUARD' in text:
                print(f"  Detalhes das linhas VANGUARD:")
                lines = text.split('\n')
                for i, line in enumerate(lines):
                    if 'VANGUARD' in line or (i > 0 and 'VANGUARD' in lines[i-1]):
                        print(f"    {line}")
