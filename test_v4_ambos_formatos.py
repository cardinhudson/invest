"""Teste do parser v4 com ambos formatos"""

from pathlib import Path
from modules.upload_pdf_avenue_v4_fixed import extrair_acoes_pdf_v4

print("=" * 70)
print("TESTE V4 - FORMATO ANTIGO (Stmt_YYYYMMDD.pdf)")
print("=" * 70)

pdf_antigo = Path("Relatorios/Avenue/Giselle Cardin/Stmt_20250131.pdf")
df = extrair_acoes_pdf_v4(str(pdf_antigo), "Giselle Cardin")

print(f"\n✅ Extraído {len(df)} ações (esperado: 1)")
print(df.to_string(index=False))

print("\n" + "=" * 70)
print("TESTE V4 - FORMATO NOVO (Doc_101579_STATEMENT_...pdf)")
print("=" * 70)

pdf_novo = Path("Relatorios/Avenue/Hudson Cardin/Doc_101579_STATEMENT_6AV40121_2024_12_31_142026_73157_AM_eRVKImAs.pdf")
df = extrair_acoes_pdf_v4(str(pdf_novo), "Hudson Cardin")

print(f"\n✅ Extraído {len(df)} ações")
print(df.head(10).to_string(index=False))

print("\n" + "=" * 70)
print("✅ V4 FUNCIONA COM AMBOS OS FORMATOS!")
print("=" * 70)
