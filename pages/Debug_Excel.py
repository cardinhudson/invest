import streamlit as st
import pandas as pd

st.title("🔍 Debug - Análise do Excel")

file = st.file_uploader("📁 Selecione o arquivo Excel para análise", type=["xlsx"])

if file:
    xls = pd.ExcelFile(file)
    
    st.success(f"✅ Arquivo carregado: {file.name}")
    st.write(f"**Abas disponíveis:** {xls.sheet_names}")
    
    st.markdown("---")
    
    for nome_aba in xls.sheet_names:
        with st.expander(f"📊 Aba: {nome_aba}", expanded=True):
            st.write(f"**Nome exato da aba:** `{nome_aba}`")
            
            # Tentar ler com skiprows=1 (como nas funções)
            try:
                df = pd.read_excel(xls, sheet_name=nome_aba, skiprows=1)
                
                st.write(f"**Total de linhas:** {len(df)}")
                st.write(f"**Total de colunas:** {len(df.columns)}")
                st.write(f"**Colunas disponíveis:**")
                
                for i, col in enumerate(df.columns):
                    st.write(f"  {i+1}. `{col}`")
                
                st.write("**Primeiras 5 linhas:**")
                st.dataframe(df.head(5))
                
                # Verificar se tem dados
                primeira_col = df.columns[0]
                st.write(f"**Valores na primeira coluna '{primeira_col}':**")
                st.write(df[primeira_col].head(10).tolist())
                
            except Exception as e:
                st.error(f"Erro ao ler aba: {e}")
