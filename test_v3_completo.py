from modules.upload_pdf_avenue_v3 import extrair_acoes_pdf_v3
from pathlib import Path
import os

# Testa com múltiplos PDFs
pdf_dir = Path("Relatorios/Avenue/Giselle Cardin")
giselle_pdfs = sorted(list(pdf_dir.glob("*.pdf")))

print("TESTES COM PDFs DE GISELLE CARDIN")
print("="*100)

total_ok = 0
total_erro = 0

for pdf in giselle_pdfs[:5]:  # Testa 5 PDFs
    try:
        df = extrair_acoes_pdf_v3(str(pdf), "Giselle Cardin")
        status = "✅ OK" if len(df) > 0 else "⚠️ SEM DADOS"
        total_ok += 1 if len(df) > 0 else 0
        
        print(f"{status} {pdf.name}")
        print(f"    → {len(df)} ativos extraídos | Total: ${df['Valor'].sum():.2f} | Tickers: {df['Ticker'].unique().tolist()}")
        
    except Exception as e:
        print(f"❌ ERRO {pdf.name}")
        print(f"    → {str(e)[:80]}")
        total_erro += 1

print(f"\n{'='*100}")
print(f"Resumo: {total_ok} OK | {total_erro} ERRO")

# Testa também com Hudson (ativo único)
print(f"\n\nTESTES COM PDFs DE HUDSON CARDIN")
print("="*100)

hudson_dir = Path("Relatorios/Avenue/Hudson Cardin")
hudson_pdfs = sorted(list(hudson_dir.glob("*.pdf")))

for pdf in hudson_pdfs[:3]:  # Testa 3 PDFs
    try:
        df = extrair_acoes_pdf_v3(str(pdf), "Hudson Cardin")
        status = "✅ OK" if len(df) > 0 else "⚠️ SEM DADOS"
        
        print(f"{status} {pdf.name}")
        print(f"    → {len(df)} ativos extraídos | Total: ${df['Valor'].sum():.2f} | Tickers: {df['Ticker'].unique().tolist()}")
        
    except Exception as e:
        print(f"❌ ERRO {pdf.name}")
        print(f"    → {str(e)[:80]}")
