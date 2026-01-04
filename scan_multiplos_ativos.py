import pdfplumber
from pathlib import Path
import re

pdf_dir = Path("Relatorios/Avenue")
all_pdfs = list(pdf_dir.rglob("*.pdf"))

print("Procurando PDFs com MÚLTIPLOS ativos...\n")

# Scan de todos os PDFs
for pdf_path in sorted(all_pdfs)[:15]:  # Verifica os primeiros 15
    try:
        with pdfplumber.open(pdf_path) as doc:
            full_text = ""
            for page in doc.pages:
                full_text += page.extract_text()
            
            # Conta quantas linhas com tickers encontra
            ticker_pattern = r'\b([A-Z]{1,6})\s+[CO]\s+[\d.,]+'
            matches = re.findall(ticker_pattern, full_text)
            
            if len(matches) > 1:
                print(f"✓ {pdf_path.name}")
                print(f"  → {len(matches)} tickers encontrados: {set(matches)}\n")
            elif len(matches) == 1:
                print(f"• {pdf_path.name} - 1 ticker ({matches[0]})")
                
    except Exception as e:
        print(f"✗ {pdf_path.name} - Erro: {str(e)[:50]}")
