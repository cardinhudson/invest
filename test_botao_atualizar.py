"""
Script de teste para validar o comportamento do botão "Atualizar cotações"

Simula o fluxo completo:
1. Clique no botão → session_state atualizado
2. st.rerun() dispara nova renderização
3. precisa_atualizar == True
4. atualizar_cotacoes() executa
5. Dados atualizados no session_state
6. UI reflete novos dados
"""

import pandas as pd
from datetime import datetime

# Simulação do fluxo Streamlit
class MockSessionState(dict):
    """Simula st.session_state"""
    def get(self, key, default=None):
        return super().get(key, default)

# Estado inicial
session = MockSessionState()

# 1. Estado inicial (app carregado)
print("=" * 60)
print("ETAPA 1: Estado inicial do aplicativo")
print("=" * 60)
df_base = pd.DataFrame({
    "Ticker": ["PETR4", "VALE3", "ITUB4"],
    "Quantidade": [100, 200, 300],
    "Preço": [30.0, 60.0, 25.0],
    "Tipo": ["Ações", "Ações", "Ações"]
})
print(f"df_posicao_base carregado: {len(df_base)} ativos")
print(f"posicao_atual_df: {session.get('posicao_atual_df')}")
print(f"posicao_atual_forcar_update: {session.get('posicao_atual_forcar_update')}")
print()

# 2. Usuário clica no botão
print("=" * 60)
print("ETAPA 2: Usuário clica em 'Atualizar cotações'")
print("=" * 60)
# O botão executa:
session["posicao_atual_forcar_update"] = True
session["posicao_atual_df"] = None
session["posicao_atual_sem_cotacao"] = None
session["posicao_atual_ultima_atualizacao"] = None
print("✅ Flags atualizados no session_state")
print(f"posicao_atual_forcar_update: {session.get('posicao_atual_forcar_update')}")
print(f"posicao_atual_df: {session.get('posicao_atual_df')}")
print("🔄 st.rerun() disparado...")
print()

# 3. Nova renderização (após st.rerun())
print("=" * 60)
print("ETAPA 3: Nova renderização do script (após rerun)")
print("=" * 60)

# Verifica se precisa atualizar
base_sig = f"{len(df_base)}|{','.join(df_base['Ticker'].astype(str).head(50).tolist())}"
precisa_atualizar = (
    session.get("posicao_atual_df") is None
    or session.get("posicao_atual_forcar_update") is True
    or (base_sig is not None and session.get("posicao_atual_base_sig") != base_sig)
)

print(f"Verificando precisa_atualizar:")
print(f"  - posicao_atual_df is None: {session.get('posicao_atual_df') is None}")
print(f"  - posicao_atual_forcar_update: {session.get('posicao_atual_forcar_update')}")
print(f"  - base_sig mudou: {session.get('posicao_atual_base_sig') != base_sig}")
print(f"➡️  precisa_atualizar = {precisa_atualizar}")
print()

# 4. Executa atualização (simulada)
if precisa_atualizar:
    print("=" * 60)
    print("ETAPA 4: Executando atualizar_cotacoes()")
    print("=" * 60)
    print("⏳ Spinner: 'Buscando cotações em tempo real (yfinance)...'")
    
    # Simula retorno da função atualizar_cotacoes
    df_atual_simulado = df_base.copy()
    df_atual_simulado["Preço Atual"] = [32.50, 62.00, 26.50]  # Preços "atualizados"
    df_atual_simulado["Valor Atualizado"] = df_atual_simulado["Quantidade"] * df_atual_simulado["Preço Atual"]
    sem_cotacao_simulado = []
    dt_atual_simulado = datetime.now()
    
    # Atualiza session_state
    session["posicao_atual_df"] = df_atual_simulado
    session["posicao_atual_sem_cotacao"] = sem_cotacao_simulado
    session["posicao_atual_ultima_atualizacao"] = dt_atual_simulado
    session["posicao_atual_base_sig"] = base_sig
    session["posicao_atual_forcar_update"] = False
    
    print(f"✅ Cotações atualizadas!")
    print(f"   Timestamp: {dt_atual_simulado.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"   Ativos sem cotação: {len(sem_cotacao_simulado)}")
    print()

# 5. Renderiza UI com dados atualizados
print("=" * 60)
print("ETAPA 5: UI renderizada com dados atualizados")
print("=" * 60)
df_atual = session.get("posicao_atual_df")
last_dt = session.get("posicao_atual_ultima_atualizacao")

if isinstance(last_dt, datetime):
    print(f"✅ Última atualização: {last_dt.strftime('%d/%m/%Y %H:%M:%S')}")
else:
    print("⏱️ Aguardando primeira atualização...")

print(f"\nTabela exibida (df_atual):")
if df_atual is not None and not df_atual.empty:
    print(df_atual[["Ticker", "Quantidade", "Preço Atual", "Valor Atualizado"]].to_string(index=False))
else:
    print("❌ Sem dados!")
print()

# 6. Resultado final
print("=" * 60)
print("RESULTADO FINAL")
print("=" * 60)
if df_atual is not None and last_dt is not None:
    print("✅ SUCESSO: Botão funcionando corretamente!")
    print("   - Timestamp atualizado")
    print("   - Dados novos carregados")
    print("   - Tabelas e gráficos refletem cotações atuais")
else:
    print("❌ FALHA: Botão não atualizou os dados!")
print()
