import streamlit as st
from modules.upload_relatorio import ler_relatorio_excel, salvar_tipo_parquet, ACOES_PATH, RENDA_FIXA_PATH, PROVENTOS_PATH
from modules.usuarios import carregar_usuarios

st.header("Upload de Relatórios Mensais (B3/Corretora)")

# Carregar usuários cadastrados
df_usuarios = carregar_usuarios()
usuarios_cadastrados = sorted(df_usuarios["Nome"].unique()) if not df_usuarios.empty else []
usuario = st.selectbox("Nome do usuário/dono do relatório", usuarios_cadastrados, index=0 if usuarios_cadastrados else None, placeholder="Selecione um usuário")

import datetime
anos = list(range(2020, datetime.datetime.now().year + 2))
meses = [f"{i:02d}" for i in range(1, 13)]
periodos_possiveis = [f"{mes}/{ano}" for ano in anos for mes in meses]
import os
def get_periodos_disponiveis(path, usuario):
    if not usuario:
        return []
    if os.path.exists(path):
        df = pd.read_parquet(path)
        usados = df[df["Usuário"] == usuario]["Mês/Ano"].unique()
        return [p for p in periodos_possiveis if p not in usados]
    return periodos_possiveis

tab1, tab2, tab3 = st.tabs(["Ações", "Renda Fixa", "Proventos"])

with tab1:
    st.subheader("Upload de Ações")
    periodo_acoes = st.selectbox("Mês/Ano do relatório (Ações)", get_periodos_disponiveis(ACOES_PATH, usuario), key="acoes")
    file_acoes = st.file_uploader("Selecione o arquivo Excel (.xlsx) (Ações)", type="xlsx", key="file_acoes")
    if file_acoes and usuario and periodo_acoes:
        df_acoes, _, _ = ler_relatorio_excel(file_acoes, usuario, periodo_acoes)
        if not df_acoes.empty:
            df_consolidado = salvar_tipo_parquet(df_acoes, ACOES_PATH)
            st.success("Ações processadas e salvas!")
            st.dataframe(df_acoes)
            st.subheader("Histórico consolidado de Ações:")
            st.dataframe(df_consolidado)
        else:
            st.error("Arquivo não contém aba de Ações.")

with tab2:
    st.subheader("Upload de Renda Fixa")
    periodo_rf = st.selectbox("Mês/Ano do relatório (Renda Fixa)", get_periodos_disponiveis(RENDA_FIXA_PATH, usuario), key="rf")
    file_rf = st.file_uploader("Selecione o arquivo Excel (.xlsx) (Renda Fixa)", type="xlsx", key="file_rf")
    if file_rf and usuario and periodo_rf:
        _, df_rf, _ = ler_relatorio_excel(file_rf, usuario, periodo_rf)
        if not df_rf.empty:
            df_consolidado = salvar_tipo_parquet(df_rf, RENDA_FIXA_PATH)
            st.success("Renda Fixa processada e salva!")
            st.dataframe(df_rf)
            st.subheader("Histórico consolidado de Renda Fixa:")
            st.dataframe(df_consolidado)
        else:
            st.error("Arquivo não contém aba de Renda Fixa.")

with tab3:
    st.subheader("Upload de Proventos")
    periodo_prov = st.selectbox("Mês/Ano do relatório (Proventos)", get_periodos_disponiveis(PROVENTOS_PATH, usuario), key="prov")
    file_prov = st.file_uploader("Selecione o arquivo Excel (.xlsx) (Proventos)", type="xlsx", key="file_prov")
    if file_prov and usuario and periodo_prov:
        _, _, df_prov = ler_relatorio_excel(file_prov, usuario, periodo_prov)
        if not df_prov.empty:
            df_consolidado = salvar_tipo_parquet(df_prov, PROVENTOS_PATH)
            st.success("Proventos processados e salvos!")
            st.dataframe(df_prov)
            st.subheader("Histórico consolidado de Proventos:")
            st.dataframe(df_consolidado)
        else:
            st.error("Arquivo não contém aba de Proventos.")
