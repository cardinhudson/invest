import pdfplumber
from pathlib import Path

# Procura PDFs de dezembro
pdf_dir = Path("Relatorios/Avenue")
all_pdfs = list(pdf_dir.rglob("*.pdf"))

print(f"Total de PDFs encontrados: {len(all_pdfs)}\n")

# Procura PDFs com dezembro/12 no nome
dezembro_pdfs = [p for p in all_pdfs if '12' in p.name.lower() or 'dezembro' in p.name.lower()]

if dezembro_pdfs:
    print(f"PDFs de dezembro: {len(dezembro_pdfs)}\n")
    for pdf in dezembro_pdfs[:2]:
        print(f"\n{'='*100}")
        print(f"ANALISANDO: {pdf.name}")
        print('='*100)
        
        with pdfplumber.open(pdf) as document:
            print(f"Total de páginas: {len(document.pages)}\n")
            
            # Procura a seção de equities
            for page_num in range(len(document.pages)):
                page = document.pages[page_num]
                text = page.extract_text()
                
                # Verifica se tem dados de ações
                if any(keyword in text for keyword in ["EQUITIES", "GLOBAL X", "ISHARES", "INVESCO", "VANGUARD"]):
                    print(f"\n>>> PÁGINA {page_num + 1} - ENCONTRADO CONTEÚDO")
                    print("-" * 100)
                    
                    lines = text.split('\n')
                    # Mostra as linhas relevantes
                    show_lines = False
                    count = 0
                    for i, line in enumerate(lines):
                        if "EQUITIES" in line or "OPTIONS" in line:
                            show_lines = True
                            count = 0
                        
                        if show_lines:
                            print(f"{i:3d}: {line}")
                            count += 1
                            if count > 60:  # Mostra 60 linhas depois de EQUITIES
                                break
                    
                    # Também tenta extrair as tabelas
                    print("\n>>> TABELAS EXTRAÍDAS:")
                    print("-" * 100)
                    tables = page.extract_tables()
                    for table_idx, table in enumerate(tables):
                        print(f"\nTabela {table_idx + 1}:")
                        for row_idx, row in enumerate(table[:10]):  # Primeiras 10 linhas
                            print(f"  Row {row_idx}: {row}")
                    
                    break
else:
    print("Nenhum PDF de dezembro encontrado. Listando PDFs disponíveis:")
    for pdf in sorted(all_pdfs)[:10]:
        print(f"  - {pdf.name}")
