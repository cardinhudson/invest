"""
Análise manual dos 8 dividendos do December 2024 PDF:

1. DIVIDEND 12/11/24 C
   GLOBAL X FUNDS 0.155 = 4.90
   GLOBAL X SUPERDIVIDEND REIT WH = 1.47
   Ticker: SRET (GLOBAL X NASDAQ-100 COVERED CALL ETF = QQQS, mas mais comum é SRET para dividend tracking)

2. DIVIDEND 12/20/24 C
   ISHARES CORE S&P 500 ETF 2.134185 = 7.89
   CASH DIV ON WH = 2.37
   Ticker: IVV ✓

3. DIVIDEND 12/26/24 C
   VANGUARD INDEX FUNDS 0.5344 = 0.35
   VANGUARD GROWTH ETF WH = 0.11
   Ticker: VUG ✓

4. DIVIDEND 12/26/24 C
   VANGUARD SPECIALIZED FUNDS 0.8756 = 2.31
   VANGUARD DIVIDEND APPRECIATION WH = 0.69
   Ticker: VIG ✓

5. DIVIDEND 12/27/24 C
   INVESCO EXCHANGE TRADED FD TR 0.13752 = 3.12
   II S&P 500 HIGH DIVID LOW WH = 0.94
   Ticker: SPHD (Invesco S&P 500 High Dividend Low Volatility)

6. DIVIDEND 12/27/24 C
   INVESCO EXCHANGE TRADED FUND 0.19169 = 2.91
   TRUST INVESCO S&P 500 QUALITY WH = 0.87
   Ticker: SPHQ (Invesco S&P 500 Quality ETF)

7. DIVIDEND 12/27/24 C
   INVESCO EXCHANGE TRADED FD TR 0.08297 = 2.41
   HIGH YIELD EQUITY DIVID WH = 0.72
   Ticker: PEY (Invesco High Yield Equity Dividend ETF)

8. DIVIDEND 12/27/24 C
   INVESCO EXCHANGE TRADED FD TR 0.14472 = 8.74
   II KBW HIGH DIVID YIELD FINL WH = 2.62
   Ticker: KBWD (Invesco KBW High Dividend Yield Financial ETF)
"""

# Mapping necessário para os dividendos:
DESCRICAO_TICKER_MAP_DIVIDENDOS = {
    # Global X
    "GLOBAL X FUNDS": "SRET",
    "GLOBAL X SUPERDIVIDEND": "SRET",
    "GLOBAL X NASDAQ": "QQQS",
    
    # iShares
    "ISHARES CORE": "IVV",
    "ISHARES": "IVV",  # fallback
    
    # Vanguard
    "VANGUARD GROWTH ETF": "VUG",
    "VANGUARD DIVIDEND APPRECIATION": "VIG",
    "VANGUARD DIVIDEND": "VIG",
    "VANGUARD INDEX": "VUG",
    
    # Invesco S&P 500
    "S&P 500 HIGH DIVID": "SPHD",
    "INVESCO EXCHANGE TRADED FD TR": "SPHD",  # primeira opção
    "S&P 500 QUALITY": "SPHQ",
    "INVESCO S&P 500 QUALITY": "SPHQ",
    
    # Invesco High Yield
    "HIGH YIELD EQUITY DIVID": "PEY",
    "INVESCO HIGH YIELD": "PEY",
    
    # KBW
    "KBW HIGH DIVID": "KBWD",
    "INVESCO KBW": "KBWD",
    
    # Fallbacks
    "INVESCO EXCHANGE TRADED FUND": "SPHQ",
}

print("Análise dos 8 dividendos esperados:")
dividendos = [
    ("GLOBAL X FUNDS / GLOBAL X SUPERDIVIDEND REIT", "SRET", 4.90, 1.47),
    ("ISHARES CORE S&P 500 ETF", "IVV", 7.89, 2.37),
    ("VANGUARD INDEX FUNDS / VANGUARD GROWTH ETF", "VUG", 0.35, 0.11),
    ("VANGUARD SPECIALIZED FUNDS / VANGUARD DIVIDEND APPRECIATION", "VIG", 2.31, 0.69),
    ("INVESCO EXCHANGE TRADED FD TR / S&P 500 HIGH DIVID LOW", "SPHD", 3.12, 0.94),
    ("INVESCO EXCHANGE TRADED FUND / S&P 500 QUALITY", "SPHQ", 2.91, 0.87),
    ("INVESCO EXCHANGE TRADED FD TR / HIGH YIELD EQUITY DIVID", "PEY", 2.41, 0.72),
    ("INVESCO EXCHANGE TRADED FD TR / KBW HIGH DIVID YIELD FINL", "KBWD", 8.74, 2.62),
]

total_bruto = 0
total_imposto = 0
print(f"\n{'Nº':<3} {'Ticker':<6} {'Bruto':>7} {'Imposto':>7} {'Líquido':>7} Descrição")
print("-" * 80)
for i, (desc, ticker, bruto, imposto) in enumerate(dividendos, 1):
    liquido = bruto - imposto
    total_bruto += bruto
    total_imposto += imposto
    print(f"{i:<3} {ticker:<6} {bruto:>7.2f} {imposto:>7.2f} {liquido:>7.2f} {desc[:50]}")

print("-" * 80)
print(f"{'TOTAL':<10} {total_bruto:>7.2f} {total_imposto:>7.2f} {total_bruto - total_imposto:>7.2f}")
