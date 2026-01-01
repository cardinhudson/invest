import streamlit as st
st.set_page_config(layout="wide")
import pandas as pd
import os
import importlib
import modules.upload_relatorio as ur
from modules.usuarios import carregar_usuarios
import datetime

ur = importlib.reload(ur)
ler_relatorio_excel = ur.ler_relatorio_excel
salvar_tipo_parquet = ur.salvar_tipo_parquet
ACOES_PATH = ur.ACOES_PATH
RENDA_FIXA_PATH = ur.RENDA_FIXA_PATH
PROVENTOS_PATH = ur.PROVENTOS_PATH
salvar_arquivo_upload = ur.salvar_arquivo_upload
salvar_arquivo_upload_path = ur.salvar_arquivo_upload_path
listar_uploads = ur.listar_uploads
extrair_mes_ano_nome = ur.extrair_mes_ano_nome

st.title("📊 Upload de Relatórios Mensais")
st.markdown("---")

# Processar pasta inteira
with st.expander("📂 Processar pasta inteira de relatórios"):
    pasta_base = st.text_input("Pasta base", value="C:\\GIT\\invest\\Relatorios")
    usar_subpasta_usuario = st.checkbox("Usar nome da subpasta como usuário", value=True)
    usuario_lote = st.selectbox(
        "Usuário padrão (caso não use subpasta)",
        sorted(carregar_usuarios()["Nome"].unique()) if not carregar_usuarios().empty else [],
        disabled=usar_subpasta_usuario,
        help="Se desligar a opção acima, este usuário será usado para todos os arquivos",
    )
    processar_lote = st.button("🚀 Processar pasta", use_container_width=True)

    if processar_lote:
        if not os.path.isdir(pasta_base):
            st.error("Pasta inválida. Ajuste o caminho e tente novamente.")
        else:
            total_a = total_rf = total_p = 0
            skip_sem_mes = []
            skip_sem_usuario = []
            arquivos = []
            for raiz, _dirs, files in os.walk(pasta_base):
                for f in files:
                    if not f.lower().endswith(".xlsx"):
                        continue
                    caminho = os.path.join(raiz, f)
                    arquivos.append(caminho)

            if not arquivos:
                st.warning("Nenhum arquivo .xlsx encontrado na pasta.")
            else:
                progress = st.progress(0.0)
                for i, caminho in enumerate(arquivos, 1):
                    user_atual = os.path.basename(os.path.dirname(caminho)) if usar_subpasta_usuario else usuario_lote
                    if not user_atual:
                        skip_sem_usuario.append(caminho)
                        progress.progress(i / len(arquivos))
                        continue
                    mes_ano = extrair_mes_ano_nome(os.path.basename(caminho))
                    if not mes_ano:
                        skip_sem_mes.append(caminho)
                        progress.progress(i / len(arquivos))
                        continue
                    try:
                        df_acoes, df_rf, df_prov = ler_relatorio_excel(caminho, user_atual, mes_ano)
                        salvar_arquivo_upload_path(caminho, user_atual, mes_ano)
                        if not df_acoes.empty:
                            salvar_tipo_parquet(
                                df_acoes,
                                ACOES_PATH,
                                chaves_substituicao=["Mês/Ano", "Usuário"],
                                dedup_subset=["Mês/Ano", "Usuário", "Produto"],
                            )
                            total_a += len(df_acoes)
                        if not df_rf.empty:
                            salvar_tipo_parquet(
                                df_rf,
                                RENDA_FIXA_PATH,
                                chaves_substituicao=["Mês/Ano", "Usuário"],
                                dedup_subset=["Mês/Ano", "Usuário", "Produto", "Código"],
                            )
                            total_rf += len(df_rf)
                        if not df_prov.empty:
                            salvar_tipo_parquet(
                                df_prov,
                                PROVENTOS_PATH,
                                chaves_substituicao=["Mês/Ano", "Usuário"],
                                dedup_subset=["Mês/Ano", "Usuário", "Produto", "Data de Pagamento", "Valor Líquido"],
                            )
                            total_p += len(df_prov)
                    except Exception as exc:
                        st.warning(f"Falha ao processar {caminho}: {exc}")
                    progress.progress(i / len(arquivos))

                st.success(f"Lote concluído. Ações: {total_a}, Renda Fixa: {total_rf}, Proventos: {total_p}")
                if skip_sem_mes:
                    st.warning(f"Arquivos ignorados por não ter MM/AAAA no nome: {len(skip_sem_mes)}")
                    st.caption("\n".join(skip_sem_mes))
                if skip_sem_usuario:
                    st.warning(f"Arquivos ignorados por falta de usuário: {len(skip_sem_usuario)}")
                    st.caption("\n".join(skip_sem_usuario))

# Visualizar histórico existente
with st.expander("📈 Consultar histórico (sem novo upload)"):
    cols_hist = st.columns(3)
    # Ações
    with cols_hist[0]:
        if os.path.exists(ACOES_PATH):
            df_hist = pd.read_parquet(ACOES_PATH)
            meses = sorted(df_hist["Mês/Ano"].dropna().unique()) if not df_hist.empty else []
            if meses:
                mes_sel = st.selectbox("Mês/Ano", meses, index=len(meses) - 1, key="hist_acoes_mes")
                df_view = df_hist[df_hist["Mês/Ano"] == mes_sel]
                st.metric("Valor total", df_view["Valor"].sum())
                st.dataframe(df_view, use_container_width=True)
            else:
                st.info("Sem dados de Ações")
        else:
            st.info("Sem dados de Ações")
    # Renda Fixa
    with cols_hist[1]:
        if os.path.exists(RENDA_FIXA_PATH):
            df_hist = pd.read_parquet(RENDA_FIXA_PATH)
            meses = sorted(df_hist["Mês/Ano"].dropna().unique()) if not df_hist.empty else []
            if meses:
                mes_sel = st.selectbox("Mês/Ano", meses, index=len(meses) - 1, key="hist_rf_mes")
                df_view = df_hist[df_hist["Mês/Ano"] == mes_sel]
                st.metric("Valor total", df_view["Valor"].sum())
                st.dataframe(df_view, use_container_width=True)
            else:
                st.info("Sem dados de Renda Fixa")
        else:
            st.info("Sem dados de Renda Fixa")
    # Proventos
    with cols_hist[2]:
        if os.path.exists(PROVENTOS_PATH):
            df_hist = pd.read_parquet(PROVENTOS_PATH)
            meses = sorted(df_hist["Mês/Ano"].dropna().unique()) if not df_hist.empty else []
            if meses:
                mes_sel = st.selectbox("Mês/Ano", meses, index=len(meses) - 1, key="hist_prov_mes")
                df_view = df_hist[df_hist["Mês/Ano"] == mes_sel]
                st.metric("Total do mês", df_view["Valor Líquido"].sum())
                st.dataframe(df_view, use_container_width=True)
                st.markdown("---")
                agrupado = df_hist.groupby("Mês/Ano")["Valor Líquido"].sum().reset_index().sort_values("Mês/Ano")
                st.bar_chart(agrupado.set_index("Mês/Ano"))
            else:
                st.info("Sem dados de Proventos")
        else:
            st.info("Sem dados de Proventos")

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
                # Salvar arquivo original
                caminho_arquivo = salvar_arquivo_upload(file, usuario, mes_ano)
                st.info(f"Arquivo original salvo em: {caminho_arquivo}")
                # Processar o arquivo
                df_acoes, df_rf, df_prov = ler_relatorio_excel(file, usuario, mes_ano)
                
                st.markdown("---")
                st.subheader("📋 Resultados do Processamento")
                
                # Criar abas para visualização
                tab1, tab2, tab3 = st.tabs(["💼 Ações", "🏦 Renda Fixa", "💰 Proventos"])
                
                # Tab Ações
                with tab1:
                    if not df_acoes.empty:
                        salvo_acoes = salvar_tipo_parquet(
                            df_acoes,
                            ACOES_PATH,
                            chaves_substituicao=["Mês/Ano", "Usuário"],
                            dedup_subset=["Mês/Ano", "Usuário", "Produto"]
                        )
                        st.info(f"💾 Dados salvos em: {ACOES_PATH}")
                        meses_acoes = sorted(salvo_acoes["Mês/Ano"].dropna().unique()) if not salvo_acoes.empty else []
                        if meses_acoes:
                            mes_sel = st.selectbox("Mês/Ano (snapshot)", meses_acoes, index=len(meses_acoes) - 1, key="mes_acoes")
                            df_view = salvo_acoes[salvo_acoes["Mês/Ano"] == mes_sel]
                            st.success(f"✅ {len(df_view)} linhas no mês selecionado")
                            st.metric("Valor total", df_view["Valor"].sum())
                            st.dataframe(df_view, use_container_width=True)
                        else:
                            st.warning("⚠️ Nenhum dado de Ações encontrado")
                    else:
                        st.warning("⚠️ Nenhum dado de Ações encontrado no arquivo")
                
                # Tab Renda Fixa
                with tab2:
                    if not df_rf.empty:
                        salvo_rf = salvar_tipo_parquet(
                            df_rf,
                            RENDA_FIXA_PATH,
                            chaves_substituicao=["Mês/Ano", "Usuário"],
                            dedup_subset=["Mês/Ano", "Usuário", "Produto", "Código"]
                        )
                        st.info(f"💾 Dados salvos em: {RENDA_FIXA_PATH}")
                        meses_rf = sorted(salvo_rf["Mês/Ano"].dropna().unique()) if not salvo_rf.empty else []
                        if meses_rf:
                            mes_sel_rf = st.selectbox("Mês/Ano (snapshot)", meses_rf, index=len(meses_rf) - 1, key="mes_rf")
                            df_view_rf = salvo_rf[salvo_rf["Mês/Ano"] == mes_sel_rf]
                            st.success(f"✅ {len(df_view_rf)} linhas no mês selecionado")
                            st.metric("Valor total", df_view_rf["Valor"].sum())
                            st.dataframe(df_view_rf, use_container_width=True)
                        else:
                            st.warning("⚠️ Nenhum dado de Renda Fixa encontrado")
                    else:
                        st.warning("⚠️ Nenhum dado de Renda Fixa encontrado no arquivo")
                
                # Tab Proventos
                with tab3:
                    if not df_prov.empty:
                        salvo_prov = salvar_tipo_parquet(
                            df_prov,
                            PROVENTOS_PATH,
                            chaves_substituicao=["Mês/Ano", "Usuário"],
                            dedup_subset=["Mês/Ano", "Usuário", "Produto", "Data de Pagamento", "Valor Líquido"]
                        )
                        st.info(f"💾 Dados salvos em: {PROVENTOS_PATH}")
                        meses_prov = sorted(salvo_prov["Mês/Ano"].dropna().unique()) if not salvo_prov.empty else []
                        if meses_prov:
                            mes_sel_prov = st.selectbox("Mês/Ano", meses_prov, index=len(meses_prov) - 1, key="mes_prov")
                            df_view_prov = salvo_prov[salvo_prov["Mês/Ano"] == mes_sel_prov]
                            st.success(f"✅ {len(df_view_prov)} linhas no mês selecionado")
                            st.metric("Total do mês", df_view_prov["Valor Líquido"].sum())
                            st.dataframe(df_view_prov, use_container_width=True)
                            st.markdown("---")
                            agrupado = salvo_prov.groupby("Mês/Ano")["Valor Líquido"].sum().reset_index().sort_values("Mês/Ano")
                            st.bar_chart(agrupado.set_index("Mês/Ano"))
                        else:
                            st.warning("⚠️ Nenhum dado de Proventos encontrado")
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
    
    st.markdown("---")
    st.subheader("🗂 Histórico de Uploads")
    historico = listar_uploads()
    if historico:
        df_hist = pd.DataFrame(historico)
        st.dataframe(df_hist.sort_values("data_upload", ascending=False), use_container_width=True)
    else:
        st.info("Nenhum upload realizado ainda.")
