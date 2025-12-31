import streamlit as st
st.set_page_config(layout="wide")
import pandas as pd
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
    return periodos_possiveis


# Upload único para todas as categorias
st.subheader("Upload de Relatório Completo (Ações, Renda Fixa e Proventos)")
periodos_disponiveis = list(set(get_periodos_disponiveis(ACOES_PATH, usuario)) & set(get_periodos_disponiveis(RENDA_FIXA_PATH, usuario)) & set(get_periodos_disponiveis(PROVENTOS_PATH, usuario)))
periodos_disponiveis = sorted(periodos_disponiveis)
mes_ano = st.selectbox("Mês/Ano do relatório", periodos_disponiveis, index=0 if periodos_disponiveis else None, placeholder="Selecione o mês/ano")
file = st.file_uploader("Selecione o arquivo Excel (.xlsx)", type="xlsx")

if file and usuario and mes_ano:
    df_acoes, df_rf, df_prov = ler_relatorio_excel(file, usuario, mes_ano)
    sucesso = False
    st.write("DataFrame de Ações após processamento:")
    st.dataframe(df_acoes)
    st.write("DataFrame de Renda Fixa após processamento:")
    st.dataframe(df_rf)
    st.write("DataFrame de Proventos após processamento:")
    st.dataframe(df_prov)
    if not df_acoes.empty:
        salvar_tipo_parquet(df_acoes, ACOES_PATH)
        st.success("Ações processadas e salvas!")
        sucesso = True
    if not df_rf.empty:
        salvar_tipo_parquet(df_rf, RENDA_FIXA_PATH)
        st.success("Renda Fixa processada e salva!")
        sucesso = True
    if not df_prov.empty:
        salvar_tipo_parquet(df_prov, PROVENTOS_PATH)
        st.success("Proventos processados e salvos!")
        sucesso = True
    if not sucesso:
        st.error("Arquivo não contém nenhuma das abas esperadas (Ações, Renda Fixa, Proventos).")
else:
    st.info("Preencha todos os campos e selecione o arquivo.")
