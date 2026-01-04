"""
Inspecionar detalhe dos PDFs antigos
"""

import pdfplumber

pdf_antigo = "Relatorios/Avenue/Giselle Cardin/Stmt_20250131.pdf"

print("="*100)
print(f"ANÁLISE DETALHADA: {pdf_antigo}")
print("="*100)

with pdfplumber.open(pdf_antigo) as pdf:
    print(f"\nTotal de páginas: {len(pdf.pages)}\n")
    
    # Página 1: Cabeçalho
    print("=" * 100)
    print("PÁGINA 1")
    print("=" * 100)
    text_p1 = pdf.pages[0].extract_text()
    print(text_p1[:800])
    
    # Página 2: Provavelmente EQUITIES
    print("\n" + "=" * 100)
    print("PÁGINA 2 (Seção de Ativos)")
    print("=" * 100)
    text_p2 = pdf.pages[1].extract_text()
    lines_p2 = text_p2.split('\n')
    for i, line in enumerate(lines_p2[:40], 1):
        print(f"[{i:2d}] {line}")
    
    # Página 3
    print("\n" + "=" * 100)
    print("PÁGINA 3")
    print("=" * 100)
    text_p3 = pdf.pages[2].extract_text()
    lines_p3 = text_p3.split('\n')
    for i, line in enumerate(lines_p3[:30], 1):
        print(f"[{i:2d}] {line}")
