"""Teste direto do v3 com o PDF hudson"""

from modules.upload_pdf_avenue_v3 import ParseadorAcoesPDFV3
from pathlib import Path

pdf_novo = Path("Relatorios/Avenue/Hudson Cardin/Doc_101579_STATEMENT_6AV40121_2024_12_31_142026_73157_AM_eRVKImAs.pdf")

print("=" * 70)
print(f"TESTE DIRETO V3: {pdf_novo.name}")
print("=" * 70)

try:
    parser = ParseadorAcoesPDFV3("12/2024", "Hudson Cardin")
    df = parser.extrair_do_pdf(str(pdf_novo))
    
    print(f"\n✅ DataFrame com {len(df)} ações")
    print(df.head().to_string())
except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()
