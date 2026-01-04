"""Inspecionador detalhado de PDFs antigos"""

import pdfplumber
from pathlib import Path

pdf_file = Path("Relatorios/Avenue/Giselle Cardin/Stmt_20250131.pdf")

print("=" * 80)
print(f"INSPEÇÃO: {pdf_file.name}")
print("=" * 80)

with pdfplumber.open(str(pdf_file)) as pdf:
    print(f"\nTotal de páginas: {len(pdf.pages)}\n")
    
    # Página 2 (índice 1) - onde estão os ativos
    page = pdf.pages[1]
    
    print("PÁGINA 2 - SEÇÃO DE EQUITIES")
    print("-" * 80)
    
    text = page.extract_text()
    linhas = text.split('\n')
    
    # Procurar a seção EQUITIES
    em_secao = False
    inicio = -1
    
    for i, linha in enumerate(linhas):
        if "EQUITIES / OPTIONS" in linha:
            em_secao = True
            inicio = i
            print(f"\n🔍 INÍCIO SEÇÃO EQUITIES (linha {i}):")
            continue
        
        if em_secao:
            if "Total Equities" in linha or "Total Cash" in linha or "---" in linha and i > inicio + 5:
                print(f"\n🛑 FIM SEÇÃO (linha {i})")
                break
            
            print(f"Linha {i:2d}: {repr(linha)}")

print("\n" + "=" * 80)
print("ANÁLISE DE ESTRUTURA")
print("=" * 80)

# Procurar padrões
with pdfplumber.open(str(pdf_file)) as pdf:
    page = pdf.pages[1]
    
    # Tentar extrair tabela
    tables = page.extract_tables()
    if tables:
        print(f"\n✅ Tabelas encontradas: {len(tables)}")
        for i, table in enumerate(tables):
            print(f"\nTabela {i + 1}:")
            for row in table[:10]:  # Primeiras 10 linhas
                print(f"  {row}")
    else:
        print("\n❌ Nenhuma tabela estruturada encontrada")
        
        # Tentar com pdfplumber table detection
        print("\nTentando extract_table() direto:")
        table = page.extract_table()
        if table:
            print(f"✅ Tabela extraída com {len(table)} linhas")
            for row in table[:10]:
                print(f"  {row}")
