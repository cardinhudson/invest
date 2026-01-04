"""
Análise dos PDFs de formato antigo de Giselle Cardin
"""

import pdfplumber
from pathlib import Path

pdfs_antigos = [
    "Relatorios/Avenue/Giselle Cardin/Stmt_20250131.pdf",
    "Relatorios/Avenue/Giselle Cardin/Stmt_20250228.pdf"
]

pdf_novo = "Relatorios/Avenue/Giselle Cardin/Doc_101579_STATEMENT_6AU71559_2024_01_31_142026_74011_AM_RVE6fZSu.pdf"

print("="*100)
print("ANÁLISE: Comparar Formato Antigo vs Novo")
print("="*100)

# Analisar novo formato
print("\n📄 NOVO FORMATO (Documento padrão):")
print(f"   {Path(pdf_novo).name}")
with pdfplumber.open(pdf_novo) as pdf:
    print(f"   Total de páginas: {len(pdf.pages)}")
    # Buscar por "DIVIDEND" ou "EQUITIES"
    for page_num, page in enumerate(pdf.pages[:5]):  # Primeiras 5 páginas
        text = page.extract_text()
        if "EQUITIES" in text:
            print(f"   ✅ 'EQUITIES' encontrado na página {page_num + 1}")
            break
    else:
        print(f"   ❌ 'EQUITIES' não encontrado")

print("\n" + "="*100)

# Analisar formatos antigos
for pdf_path in pdfs_antigos:
    if not Path(pdf_path).exists():
        print(f"❌ {Path(pdf_path).name} - NÃO ENCONTRADO")
        continue
    
    print(f"\n📄 FORMATO ANTIGO: {Path(pdf_path).name}")
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            print(f"   Total de páginas: {len(pdf.pages)}")
            
            # Analisar primeira página
            text_p1 = pdf.pages[0].extract_text()[:500] if len(pdf.pages) > 0 else ""
            
            # Procurar por palavras-chave
            keywords = ["EQUITIES", "DIVIDEND", "SECURITIES", "HOLDINGS", "CASH", "Ação", "Ativo"]
            found_keywords = [kw for kw in keywords if kw in text_p1]
            
            if found_keywords:
                print(f"   Palavras-chave encontradas: {', '.join(found_keywords)}")
            else:
                print(f"   ❌ Nenhuma palavra-chave padrão encontrada")
            
            # Buscar por estrutura
            print(f"   Estrutura (primeiras linhas):")
            lines = text_p1.split('\n')[:10]
            for i, line in enumerate(lines[:5], 1):
                if line.strip():
                    print(f"      [{i}] {line.strip()[:80]}")
            
            # Verificar se tem seção de EQUITIES em qualquer página
            print(f"   Procurando por seções...")
            for page_num, page in enumerate(pdf.pages):
                text = page.extract_text()
                if "EQUITIES" in text or "HOLDINGS" in text or "AÇÕES" in text:
                    print(f"      ✅ Seção de ativos encontrada na página {page_num + 1}")
                    break
            else:
                print(f"      ⚠️  Seção de ativos não encontrada")
                
    except Exception as e:
        print(f"   ❌ Erro ao processar: {e}")

print("\n" + "="*100)
print("CONCLUSÃO")
print("="*100)
