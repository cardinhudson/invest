import pdfplumber
from pathlib import Path

# Caminho do PDF
pdf_path = Path("Relatorios/Avenue/Hudson Cardin/Doc_101579_STATEMENT_6AV40121_2024_12_31_142026_73157_AM_eRVKImAs.pdf")

with pdfplumber.open(pdf_path) as pdf:
    print(f"Total de páginas: {len(pdf.pages)}\n")
    
    # Verificar páginas 5-7 (índices 4-6)
    for page_num in [4, 5, 6]:  # páginas 5, 6, 7
        print(f"\n{'='*80}")
        print(f"PÁGINA {page_num+1}")
        print('='*80)
        
        page = pdf.pages[page_num]
        text = page.extract_text()
        
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if 'DIVIDEND' in line or 'WH' in line or (i > 0 and 'DIVIDEND' in lines[max(0, i-3):i]):
                print(f"[{i:3d}] {line}")
