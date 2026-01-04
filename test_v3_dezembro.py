from modules.upload_pdf_avenue_v3 import extrair_acoes_pdf_v3
from pathlib import Path

# Testa com PDFs de dezembro (ativo único)
hudson_dir = Path("Relatorios/Avenue/Hudson Cardin")
dezembro_pdfs = [p for p in hudson_dir.glob("*.pdf") if "2024_12" in p.name or "2025" in p.name]

print(f"TESTE COM PDFs DE DEZEMBRO/2025 (ATIVO ÚNICO)")
print("="*100)

for pdf in sorted(dezembro_pdfs)[:5]:
    try:
        df = extrair_acoes_pdf_v3(str(pdf), "Hudson Cardin")
        status = "✅ OK" if len(df) > 0 else "⚠️ SEM DADOS"
        
        print(f"{status} {pdf.name}")
        if len(df) > 0:
            print(df.to_string())
            print()
        
    except Exception as e:
        import traceback
        print(f"❌ ERRO {pdf.name}")
        traceback.print_exc()
