import streamlit as st
st.set_page_config(layout="wide")
import pandas as pd
from modules.upload_relatorio import ler_relatorio_excel, salvar_tipo_parquet, ACOES_PATH, RENDA_FIXA_PATH, PROVENTOS_PATH
from modules.usuarios import carregar_usuarios
import datetime

st.title("📊 Upload de Relatórios Mensais")
st.markdown("---")

# Carregar usuários
df_usuarios = carregar_usuarios()
usuarios_cadastrados = sorted(df_usuarios["Nome"].unique()) if not df_usuarios.empty else []

# Formulário de upload
with st.form("form_upload"):
    st.subheader("1️⃣ Dados do Relatório")
    
    col1, col2 = st.columns(2)
    
    with col1:
        usuario = st.selectbox(
            "👤 Usuário/Dono do Relatório", 
            usuarios_cadastrados,
            help="Selecione o usuário responsável pelos investimentos"
        )
    
    with col2:
        # Gerar períodos disponíveis
        anos = list(range(2020, datetime.datetime.now().year + 2))
        meses = [f"{i:02d}" for i in range(1, 13)]
        periodos = [f"{mes}/{ano}" for ano in anos for mes in meses]
        
        mes_ano = st.selectbox(
            "📅 Mês/Ano do Relatório",
            periodos,
            index=len(periodos) - 1,  # Último período por padrão
            help="Selecione o período do relatório"
        )
    
    st.subheader("2️⃣ Arquivo Excel")
    file = st.file_uploader(
        "📁 Selecione o arquivo Excel (.xlsx)",
        type=["xlsx"],
        help="Faça upload do relatório consolidado da B3/Corretora"
    )
    
    st.markdown("---")
    processar = st.form_submit_button("🚀 Processar Relatório", type="primary", use_container_width=True)

# Processar quando o botão for clicado
if processar:
    if not file:
        st.error("❌ Por favor, selecione um arquivo Excel!")
    elif not usuario:
        st.error("❌ Por favor, selecione um usuário!")
    elif not mes_ano:
        st.error("❌ Por favor, selecione o mês/ano!")
    else:
        with st.spinner("⏳ Processando relatório..."):
            try:
                # Processar o arquivo
                df_acoes, df_rf, df_prov = ler_relatorio_excel(file, usuario, mes_ano)
                
                st.markdown("---")
                st.subheader("📋 Resultados do Processamento")
                
                # Criar abas para visualização
                tab1, tab2, tab3 = st.tabs(["💼 Ações", "🏦 Renda Fixa", "💰 Proventos"])
                
                # Tab Ações
                with tab1:
                    if not df_acoes.empty:
                        st.success(f"✅ {len(df_acoes)} linhas processadas")
                        st.dataframe(df_acoes, use_container_width=True)
                        salvar_tipo_parquet(df_acoes, ACOES_PATH)
                        st.info(f"💾 Dados salvos em: {ACOES_PATH}")
                    else:
                        st.warning("⚠️ Nenhum dado de Ações encontrado no arquivo")
                
                # Tab Renda Fixa
                with tab2:
                    if not df_rf.empty:
                        st.success(f"✅ {len(df_rf)} linhas processadas")
                        st.dataframe(df_rf, use_container_width=True)
                        salvar_tipo_parquet(df_rf, RENDA_FIXA_PATH)
                        st.info(f"💾 Dados salvos em: {RENDA_FIXA_PATH}")
                    else:
                        st.warning("⚠️ Nenhum dado de Renda Fixa encontrado no arquivo")
                
                # Tab Proventos
                with tab3:
                    if not df_prov.empty:
                        st.success(f"✅ {len(df_prov)} linhas processadas")
                        st.dataframe(df_prov, use_container_width=True)
                        salvar_tipo_parquet(df_prov, PROVENTOS_PATH)
                        st.info(f"💾 Dados salvos em: {PROVENTOS_PATH}")
                    else:
                        st.warning("⚠️ Nenhum dado de Proventos encontrado no arquivo")
                
                # Resumo final
                st.markdown("---")
                total_linhas = len(df_acoes) + len(df_rf) + len(df_prov)
                
                if total_linhas > 0:
                    st.success(f"🎉 **Processamento concluído com sucesso!** Total: {total_linhas} linhas processadas")
                    
                    # Métricas
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Ações", len(df_acoes))
                    with col2:
                        st.metric("Renda Fixa", len(df_rf))
                    with col3:
                        st.metric("Proventos", len(df_prov))
                else:
                    st.error("❌ Nenhum dado foi encontrado no arquivo. Verifique se o arquivo contém as abas: Ações, Renda Fixa ou Proventos")
            
            except Exception as e:
                st.error(f"❌ Erro ao processar o arquivo: {str(e)}")
                st.exception(e)

# Informações de ajuda
with st.expander("ℹ️ Ajuda - Formato do Arquivo"):
    st.markdown("""
    ### 📝 Requisitos do Arquivo Excel
    
    O arquivo deve conter pelo menos uma das seguintes abas:
    
    #### 💼 Aba "Ações"
    - Deve conter as colunas: Produto, Valor Atualizado, Instituição, etc.
    - Linhas de total/subtotal serão automaticamente removidas
    
    #### 🏦 Aba "Renda Fixa"
    - Deve conter as colunas: Produto, Valor Atualizado MTM ou Valor Atualizado CURVA, etc.
    - Linhas de total/subtotal serão automaticamente removidas
    
    #### 💰 Aba "Proventos"
    - Deve conter as colunas: Produto, Valor Líquido, Data de Pagamento, Tipo de Provento
    - Linhas de total/subtotal serão automaticamente removidas
    
    ### ⚙️ Processamento Automático
    - ✅ Remove linhas vazias
    - ✅ Remove linhas de total/subtotal
    - ✅ Valida valores numéricos
    - ✅ Sobrescreve dados do mesmo período/usuário
    - ✅ Mantém dados de outros períodos
    """)

# Verificar arquivos salvos
with st.expander("📂 Arquivos Salvos"):
    import os
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if os.path.exists(ACOES_PATH):
            df_temp = pd.read_parquet(ACOES_PATH)
            st.info(f"**Ações**\n\n{len(df_temp)} linhas")
        else:
            st.warning("Sem dados de Ações")
    
    with col2:
        if os.path.exists(RENDA_FIXA_PATH):
            df_temp = pd.read_parquet(RENDA_FIXA_PATH)
            st.info(f"**Renda Fixa**\n\n{len(df_temp)} linhas")
        else:
            st.warning("Sem dados de Renda Fixa")
    
    with col3:
        if os.path.exists(PROVENTOS_PATH):
            df_temp = pd.read_parquet(PROVENTOS_PATH)
            st.info(f"**Proventos**\n\n{len(df_temp)} linhas")
        else:
            st.warning("Sem dados de Proventos")
