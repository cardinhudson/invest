
import streamlit as st
st.set_page_config(layout="wide")
from modules.upload_relatorio import ler_relatorio_excel, salvar_historico_parquet, carregar_historico_parquet
from modules.usuarios import carregar_usuarios


st.header("Upload de Relatórios Mensais (B3/Corretora)")

# Carregar usuários cadastrados
df_usuarios = carregar_usuarios()
usuarios_cadastrados = sorted(df_usuarios["Nome"].unique()) if not df_usuarios.empty else []
usuario = st.selectbox("Nome do usuário/dono do relatório", usuarios_cadastrados, index=0 if usuarios_cadastrados else None, placeholder="Selecione um usuário")

# Filtro de período (Mês/Ano) como selectbox, mostrando apenas meses/anos ainda não cadastrados para o usuário
import datetime
df_consolidado = carregar_historico_parquet()
anos = list(range(2020, datetime.datetime.now().year + 2))
meses = [f"{i:02d}" for i in range(1, 13)]
periodos_possiveis = [f"{mes}/{ano}" for ano in anos for mes in meses]
periodos_disponiveis = periodos_possiveis
if usuario:
    if not df_consolidado.empty:
        usados = df_consolidado[df_consolidado["Usuário"] == usuario]["Mês/Ano"].unique()
        periodos_disponiveis = [p for p in periodos_possiveis if p not in usados]
    else:
        periodos_disponiveis = periodos_possiveis
else:
    periodos_disponiveis = []
mes_ano = st.selectbox("Mês/Ano do relatório (ex: 01/2025)", periodos_disponiveis, index=0 if periodos_disponiveis else None, placeholder="Selecione o mês/ano")
file = st.file_uploader("Selecione o arquivo Excel (.xlsx)", type="xlsx")

if file and usuario and mes_ano:
    df_historico = ler_relatorio_excel(file, usuario, mes_ano)
    if not df_historico.empty:
        df_consolidado = salvar_historico_parquet(df_historico)
        st.success("Arquivo processado e salvo com sucesso!")
        st.dataframe(df_historico)
        st.subheader("Histórico consolidado (todos os meses e usuários):")
        st.dataframe(df_consolidado)
    else:
        st.error("Arquivo não contém as abas esperadas.")
else:
    st.info("Preencha todos os campos e selecione o arquivo. É necessário cadastrar pelo menos um usuário na tela principal.")


# Exibir histórico consolidado sempre que quiser
st.subheader("Histórico consolidado atual:")
df_consolidado = carregar_historico_parquet()
st.dataframe(df_consolidado)

# Botão para download em Excel
import io
if not df_consolidado.empty:
    buffer = io.BytesIO()
    df_consolidado.to_excel(buffer, index=False, engine='openpyxl')
    buffer.seek(0)
    st.download_button(
        label="Baixar histórico em Excel (.xlsx)",
        data=buffer,
        file_name="historico_investimentos.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
