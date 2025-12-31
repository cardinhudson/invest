"""
Script de teste para debug do processamento de upload
"""
import pandas as pd
import sys

# Simular um ExcelFile com as abas esperadas
print("=" * 80)
print("TESTE DE DEBUG - Processamento de Upload")
print("=" * 80)

# Criar dados de teste
print("\n1. Criando dados de teste simulados...")

# Simular aba de Ações
dados_acoes = {
    "Produto": ["PETR4", "VALE3", "TOTAL"],
    "Instituição": ["XP", "XP", ""],
    "Valor Atualizado": [1000.50, 2000.75, 3001.25],
    "Quantidade": [10, 20, 30]
}
df_acoes_teste = pd.DataFrame(dados_acoes)
print("\nDados de Ações (simulados):")
print(df_acoes_teste)

# Simular aba de Renda Fixa
dados_rf = {
    "Produto": ["CDB XP", "LCI BB", "TOTAL"],
    "Instituição": ["XP", "BB", ""],
    "Valor Atualizado MTM": [5000.00, 3000.00, 8000.00],
    "Valor Atualizado CURVA": [None, None, None]
}
df_rf_teste = pd.DataFrame(dados_rf)
print("\nDados de Renda Fixa (simulados):")
print(df_rf_teste)

# Testar a lógica de filtro
print("\n2. Testando filtros...")

# Filtro de ações
print("\n--- Testando filtro de Ações ---")
df_acoes_filtrado = df_acoes_teste.copy()
print(f"Linhas iniciais: {len(df_acoes_filtrado)}")

# Remover total/subtotal
df_acoes_filtrado = df_acoes_filtrado[~df_acoes_filtrado["Produto"].astype(str).str.lower().str.contains("total|subtotal", na=False)]
print(f"Após remover total/subtotal: {len(df_acoes_filtrado)}")

# Converter valor
df_acoes_filtrado["Valor"] = pd.to_numeric(df_acoes_filtrado["Valor Atualizado"], errors="coerce")
print(f"Valores válidos: {df_acoes_filtrado['Valor'].notna().sum()}")

# Filtrar por Produto e Valor válidos
df_acoes_filtrado = df_acoes_filtrado[
    (df_acoes_filtrado["Produto"].notna()) & 
    (df_acoes_filtrado["Produto"].astype(str).str.strip() != "") &
    (df_acoes_filtrado["Valor"].notna()) & 
    (df_acoes_filtrado["Valor"] > 0)
]
print(f"Linhas finais: {len(df_acoes_filtrado)}")
print(df_acoes_filtrado)

# Filtro de Renda Fixa
print("\n--- Testando filtro de Renda Fixa ---")
df_rf_filtrado = df_rf_teste.copy()
print(f"Linhas iniciais: {len(df_rf_filtrado)}")

# Criar coluna Valor
df_rf_filtrado["Valor"] = None
if "Valor Atualizado MTM" in df_rf_filtrado.columns:
    df_rf_filtrado["Valor"] = pd.to_numeric(df_rf_filtrado["Valor Atualizado MTM"], errors="coerce")
    
print(f"Valores de MTM: {df_rf_filtrado['Valor'].notna().sum()}")

# Remover total/subtotal
df_rf_filtrado = df_rf_filtrado[~df_rf_filtrado["Produto"].astype(str).str.lower().str.contains("total|subtotal", na=False)]
print(f"Após remover total/subtotal: {len(df_rf_filtrado)}")

# Filtrar por Produto e Valor válidos
df_rf_filtrado = df_rf_filtrado[
    (df_rf_filtrado["Produto"].notna()) & 
    (df_rf_filtrado["Produto"].astype(str).str.strip() != "") &
    (df_rf_filtrado["Valor"].notna()) & 
    (df_rf_filtrado["Valor"] > 0)
]
print(f"Linhas finais: {len(df_rf_filtrado)}")
print(df_rf_filtrado)

print("\n" + "=" * 80)
print("CONCLUSÃO DO TESTE")
print("=" * 80)
print(f"✓ Ações: {len(df_acoes_filtrado)} linhas válidas")
print(f"✓ Renda Fixa: {len(df_rf_filtrado)} linhas válidas")
print("\nSe ambos têm linhas > 0, a lógica de filtro está correta!")
print("O problema pode estar no mapeamento de colunas ou nos nomes das abas do Excel.")
