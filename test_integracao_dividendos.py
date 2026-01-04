"""
Teste de integração: Extrair ações E dividendos usando o módulo upload_pdf_avenue
"""

import sys
from pathlib import Path

# Adiciona o diretório modules ao path
sys.path.insert(0, str(Path(__file__).parent))

from modules.upload_pdf_avenue import extrair_acoes_pdf, extrair_dividendos_pdf

pdf_path = "Relatorios/Avenue/Hudson Cardin/Doc_101579_STATEMENT_6AV40121_2024_12_31_142026_73157_AM_eRVKImAs.pdf"
usuario = "Hudson Cardin"

print("="*80)
print("TESTE DE INTEGRAÇÃO: EXTRAÇÃO DE AÇÕES E DIVIDENDOS")
print("="*80)

# Teste 1: Ações
print("\n1. Extraindo AÇÕES...")
try:
    df_acoes = extrair_acoes_pdf(pdf_path, usuario)
    print(f"✅ Ações extraídas: {len(df_acoes)}")
    if not df_acoes.empty:
        print(f"   Colunas: {list(df_acoes.columns)}")
        print(f"   Tickers: {df_acoes['Ticker'].unique().tolist()}")
        print(f"\n   Primeiras 3 ações:")
        print(df_acoes[['Ticker', 'Produto', 'Quantidade Disponível', 'Valor']].head(3).to_string())
except Exception as e:
    print(f"❌ Erro ao extrair ações: {e}")

# Teste 2: Dividendos
print("\n" + "="*80)
print("2. Extraindo DIVIDENDOS...")
try:
    df_dividendos = extrair_dividendos_pdf(pdf_path, usuario)
    print(f"✅ Dividendos extraídos: {len(df_dividendos)}")
    if not df_dividendos.empty:
        print(f"   Colunas: {list(df_dividendos.columns)}")
        print(f"   Tickers: {sorted(df_dividendos['Ticker'].unique().tolist())}")
        print(f"\n   Todos os dividendos:")
        print(df_dividendos[['Ticker', 'Valor Bruto', 'Imposto', 'Valor Líquido']].to_string())
        print(f"\n   RESUMO:")
        print(f"   Total Bruto: ${df_dividendos['Valor Bruto'].sum():.2f}")
        print(f"   Total Imposto: ${df_dividendos['Imposto'].sum():.2f}")
        print(f"   Total Líquido: ${df_dividendos['Valor Líquido'].sum():.2f}")
except Exception as e:
    print(f"❌ Erro ao extrair dividendos: {e}")

print("\n" + "="*80)
print("FIM DO TESTE")
print("="*80)
