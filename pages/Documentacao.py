import streamlit as st
import os
import pandas as pd
from datetime import datetime
# Criar índices no sidebar
try:
    from modules.upload_relatorio import ACOES_PATH, RENDA_FIXA_PATH, PROVENTOS_PATH
    tem_upload_relatorio = True
except:
    tem_upload_relatorio = False

st.set_page_config(page_title="Documentação - Invest", page_icon="📚", layout="wide")

# Função para obter mês atual em português
def obter_mes_atual():
    """Retorna o mês atual em português"""
    meses = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }
    agora = datetime.now()
    return meses[agora.month]

# Cabeçalho compacto
mes_atual = obter_mes_atual()
ano_atual = datetime.now().year
versao_atual = "1.0.0"

st.markdown(f"""
<div style='display: flex; justify-content: space-between; align-items: center; color: #fff; padding: 8px 10px; font-size: 0.85rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-bottom: 1px solid #5a4fcf; margin-bottom: 10px;'>
    <div style='flex: 1;'>📚 Documentação Completa do Invest | Versão {versao_atual} | {mes_atual} {ano_atual}</div>
</div>
""", unsafe_allow_html=True)

# CSS para melhorar visualização
st.markdown("""
    <style>
        h1 {
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        .stTabs [data-baseweb="tab"] {
            padding: 10px 20px;
            font-weight: 600;
        }
    </style>
""", unsafe_allow_html=True)

st.title("📚 Documentação Completa do Sistema Invest")

# Sidebar com índices
st.sidebar.markdown("## 📑 Índice")
st.sidebar.markdown("---")

# Criar índices no sidebar
# ...restante do código...
