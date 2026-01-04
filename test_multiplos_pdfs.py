"""
Teste com múltiplos PDFs: Giselle Cardin (Janeiro) e Hudson Cardin (Dezembro)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from modules.upload_pdf_avenue import extrair_acoes_pdf, extrair_dividendos_pdf

# Testes
testes = [
    ("Giselle Cardin (Jan/2024)", "Relatorios/Avenue/Giselle Cardin/Doc_101579_STATEMENT_6AU71559_2024_01_31_142026_74011_AM_RVE6fZSu.pdf", "Giselle Cardin"),
    ("Hudson Cardin (Dez/2024)", "Relatorios/Avenue/Hudson Cardin/Doc_101579_STATEMENT_6AV40121_2024_12_31_142026_73157_AM_eRVKImAs.pdf", "Hudson Cardin"),
]

print("="*100)
print("TESTE COMPLETO: EXTRAÇÃO DE AÇÕES E DIVIDENDOS EM MÚLTIPLOS PDFs")
print("="*100)

for nome_teste, pdf_path, usuario in testes:
    print(f"\n{'─'*100}")
    print(f"📄 {nome_teste}")
    print(f"{'─'*100}")
    
    if not Path(pdf_path).exists():
        print(f"❌ PDF não encontrado: {pdf_path}")
        continue
    
    # Ações
    try:
        df_acoes = extrair_acoes_pdf(pdf_path, usuario)
        n_acoes = len(df_acoes)
        print(f"✅ Ações: {n_acoes} extraídas")
        if not df_acoes.empty:
            tickers = sorted(df_acoes['Ticker'].unique().tolist())
            valor_total = df_acoes['Valor'].sum()
            print(f"   Tickers: {', '.join(tickers)}")
            print(f"   Valor Total: ${valor_total:,.2f}")
    except Exception as e:
        print(f"❌ Erro ao extrair ações: {str(e)[:80]}")
    
    # Dividendos
    try:
        df_divs = extrair_dividendos_pdf(pdf_path, usuario)
        n_divs = len(df_divs)
        print(f"✅ Dividendos: {n_divs} extraídos")
        if not df_divs.empty:
            tickers = sorted(df_divs['Ticker'].unique().tolist())
            valor_total = df_divs['Valor Líquido'].sum()
            print(f"   Tickers: {', '.join(tickers)}")
            print(f"   Valor Líquido Total: ${valor_total:,.2f}")
        else:
            print(f"   (Nenhum dividendo neste período)")
    except Exception as e:
        print(f"❌ Erro ao extrair dividendos: {str(e)[:80]}")

print(f"\n{'='*100}")
print("FIM DOS TESTES")
print(f"{'='*100}")
