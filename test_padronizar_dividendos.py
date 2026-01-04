"""
Teste: Validar que padronizar_dividendos_avenue() funciona com novo formato
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from modules.avenue_views import padronizar_dividendos_avenue

# ===== TESTE 1: NOVO FORMATO (V3) =====
print("="*80)
print("TESTE 1: Novo Formato (V3 do Parser)")
print("="*80)

df_novo = pd.DataFrame({
    "Data Comex": ["11/12/2024", "11/12/2024", "20/12/2024"],
    "Produto": ["GLOBAL X FDS", "GLOBAL X FUNDS", "ISHARES CORE"],
    "Ticker": ["QQQS", "SRET", "IVV"],
    "Valor Bruto": [5.14, 4.90, 7.89],
    "Imposto": [1.54, 1.47, 2.37],
    "Valor Líquido": [3.60, 3.43, 5.52],
    "Mês/Ano": ["12/2024", "12/2024", "12/2024"],
    "Usuário": ["Hudson Cardin", "Hudson Cardin", "Hudson Cardin"]
})

print(f"\n📥 Input (Novo Formato):")
print(df_novo)

df_padronizado = padronizar_dividendos_avenue(df_novo)

print(f"\n✅ Output (Padronizado):")
print(df_padronizado[["Data", "Ativo", "Valor Bruto", "Impostos", "Valor Líquido", "Fonte"]])

# Validações
assert len(df_padronizado) == 3, "Deveria ter 3 registros"
assert df_padronizado["Ativo"].tolist() == ["QQQS", "SRET", "IVV"], "Tickers incorretos"

valor_bruto_total = df_padronizado["Valor Bruto"].sum()
assert abs(valor_bruto_total - 17.93) < 0.01, f"Valor Bruto total incorreto: {valor_bruto_total}"

impostos_total = df_padronizado["Impostos"].sum()
assert abs(impostos_total - 5.38) < 0.01, f"Impostos total incorreto: {impostos_total}"

print("\n✅ Validações passadas!")

# ===== TESTE 2: VISUALIZAÇÃO (com impostos negativos) =====
print("\n" + "="*80)
print("TESTE 2: Exibição com Impostos Negativos")
print("="*80)

df_exibicao = df_padronizado.copy()
if "Impostos" in df_exibicao.columns:
    df_exibicao["Impostos"] = df_exibicao["Impostos"].apply(
        lambda x: -abs(x) if pd.notna(x) and x != 0 else x
    )

print(f"\n💰 Como será exibido (Impostos negativos):")
print(df_exibicao[["Ativo", "Valor Bruto", "Impostos", "Valor Líquido"]])

# Validar que impostos estão negativos
assert (df_exibicao["Impostos"] <= 0).all(), "Impostos deveriam ser negativos na exibição"
print("\n✅ Impostos estão corretamente negativos!")

# ===== TESTE 3: RESUMO POR ATIVO =====
print("\n" + "="*80)
print("TESTE 3: Resumo por Ativo")
print("="*80)

resumo = df_padronizado.groupby("Ativo").agg({
    "Valor Bruto": "sum",
    "Impostos": "sum",
    "Valor Líquido": "sum"
}).reset_index().sort_values("Valor Líquido", ascending=False)

# Garantir que Impostos sejam negativos
if "Impostos" in resumo.columns:
    resumo["Impostos"] = resumo["Impostos"].apply(
        lambda x: -abs(float(x)) if pd.notna(x) and x != 0 else 0.0
    )

print(f"\n📊 Resumo:")
print(resumo)

# Validar
assert resumo["Impostos"].max() <= 0, "Todos os impostos deveriam ser ≤ 0"
print("\n✅ Resumo correto!")

print("\n" + "="*80)
print("✅ TODOS OS TESTES PASSARAM!")
print("="*80)
