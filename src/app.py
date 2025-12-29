
import streamlit as st

st.set_page_config(page_title="Sistema de Investimentos", layout="wide")

st.title("Sistema de Investimentos")
st.markdown("""
Gerencie seus investimentos, veja evolução histórica, dividendos, comparações e projeções.

Utilize o menu lateral para navegar entre as páginas:
- **Resumo**
- **Gráficos**
- **Histórico**
- **Comparações**
- **Cadastro**
- **Inserção Manual**
- **Upload CSV**
- **Alertas e Projeções**
- **Upload Relatório Mensal** (para importar arquivos Excel mensais da B3/corretora)
""")

st.info("Selecione uma página no menu lateral para começar.")
