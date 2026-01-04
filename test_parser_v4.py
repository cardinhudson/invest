"""Teste do parser v4 com PDFs antigos"""

from pathlib import Path
from modules.upload_pdf_avenue_v4_fixed import extrair_acoes_pdf_v4

pdf_dir = Path("Relatorios/Avenue/Giselle Cardin")

print("=" * 70)
print("TESTE PARSER V4 - FORMATOS ANTIGOS (Stmt_YYYYMMDD.pdf)")
print("=" * 70)

for pdf_file in sorted(pdf_dir.glob("Stmt_*.pdf")):
    print(f"\n{'-' * 70}")
    print(f"📄 {pdf_file.name}")
    print(f"{'-' * 70}")
    
    try:
        df = extrair_acoes_pdf_v4(str(pdf_file), "Giselle Cardin")
        
        if not df.empty:
            print(f"\n✅ Ações extraídas: {len(df)}")
            print("\n" + df.to_string(index=False))
            print(f"\nTotal valor: ${df['Valor'].sum():.2f}")
        else:
            print("⚠️ Nenhuma ação extraída")
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 70)
print("FIM DOS TESTES")
print("=" * 70)
