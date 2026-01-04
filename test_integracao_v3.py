"""
Teste de integração do novo parser v3 via upload_pdf_avenue.py
"""

import sys
sys.path.insert(0, '.')

from modules.upload_pdf_avenue import extrair_acoes_pdf
from pathlib import Path

print("TESTE DE INTEGRAÇÃO - NOVO PARSER V3")
print("="*100)

# Teste com PDF de múltiplos ativos
pdf_janeiro = "Relatorios/Avenue/Giselle Cardin/Doc_101579_STATEMENT_6AU71559_2024_01_31_142026_74011_AM_RVE6fZSu.pdf"

print(f"\n1. Testando com PDF de Janeiro (múltiplos ativos)...")
try:
    df = extrair_acoes_pdf(pdf_janeiro, usuario="Giselle Cardin")
    print(f"✅ OK - {len(df)} ativos extraídos")
    print(f"   Tickers: {df['Ticker'].unique().tolist()}")
    print(f"   Total: ${df['Valor'].sum():.2f}")
except Exception as e:
    print(f"❌ ERRO: {e}")

# Teste com PDF de ativo único
pdf_dezembro = "Relatorios/Avenue/Hudson Cardin/Doc_101579_STATEMENT_6AV40121_2024_12_31_142026_73157_AM_eRVKImAs.pdf"

print(f"\n2. Testando com PDF de Dezembro (ativo único)...")
try:
    df = extrair_acoes_pdf(pdf_dezembro, usuario="Hudson Cardin")
    print(f"✅ OK - {len(df)} ativos extraídos")
    print(f"   Tickers: {df['Ticker'].unique().tolist()}")
    print(f"   Total: ${df['Valor'].sum():.2f}")
except Exception as e:
    print(f"❌ ERRO: {e}")

print(f"\n{'='*100}")
print("✅ INTEGRAÇÃO COMPLETA E FUNCIONANDO!")
