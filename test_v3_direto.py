"""Testar parser v3 diretamente"""

from modules.upload_pdf_avenue_v3 import ParseadorAcoesPDFV3
from pathlib import Path

pdf_novo = Path("Relatorios/Avenue/Hudson Cardin/Doc_101579_STATEMENT_6AV40121_2024_12_31_142026_73157_AM_eRVKImAs.pdf")

print("=" * 70)
print(f"TESTE DIRETO V3: {pdf_novo.name}")
print("=" * 70)

try:
    parser = ParseadorAcoesPDFV3("Hudson Cardin")
    acoes = parser.extrair(str(pdf_novo))
    
    print(f"\n✅ Ações extraídas: {len(acoes)}")
    if acoes:
        for acao in acoes[:5]:
            print(f"  {acao}")
except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()
