import streamlit as st
import os
import pandas as pd
from modules.upload_relatorio import ACOES_PATH, RENDA_FIXA_PATH, PROVENTOS_PATH

st.set_page_config(layout="wide")
st.title("📖 Sobre o Projeto - Investimentos B3")

st.markdown("""
# Investimentos B3 - Documentação e Funcionamento

Este projeto foi criado para facilitar o upload, processamento e análise de relatórios mensais de investimentos da B3 e corretoras, com histórico acumulativo, filtros por período e visualização de proventos.

## Funcionalidades principais
- **Upload de relatórios Excel**: Processa arquivos com abas de Ações, Renda Fixa e Proventos, detectando cabeçalhos automaticamente.
- **Acúmulo histórico**: Cada upload substitui apenas o snapshot do mesmo mês/usuário, mantendo o histórico dos demais meses.
- **Filtros por mês**: Visualização de posição patrimonial e proventos por mês, sem somar posições de meses diferentes.
- **Proventos acumulados**: Gráfico de proventos recebidos mês a mês.
- **Consulta de histórico**: Visualize dados já processados sem novo upload.
- **Robustez**: O sistema detecta automaticamente o início do cabeçalho e o tipo de cada aba, evitando erros comuns de leitura.

## Como usar
1. Acesse a página **Upload de Relatórios Mensais**.
2. Preencha os dados do usuário e período, faça upload do Excel.
3. O sistema processa as abas, salva os dados e permite filtrar por mês nas abas de Ações, Renda Fixa e Proventos.
4. Consulte o histórico a qualquer momento pelo expander no topo da página.

## Regras e dicas para o Excel
- As abas podem ter nomes variados (ex: "Ações", "Renda Fixa", "Proventos"), o sistema identifica pelo conteúdo.
- O cabeçalho pode começar em qualquer linha; o sistema detecta automaticamente.
- As colunas essenciais são buscadas mesmo que venham com nomes levemente diferentes.
- Linhas de total/subtotal e vazias são removidas automaticamente.
- Colunas numéricas são convertidas corretamente para evitar erros de gravação.

## Estrutura dos arquivos
- Os dados processados são salvos em arquivos Parquet:
    - `data/acoes.parquet`
    - `data/renda_fixa.parquet`
    - `data/proventos.parquet`
- Os uploads originais ficam em `uploads/`.

## Como evitar erros
- Sempre inclua as colunas essenciais nas abas do Excel (veja exemplos na página de upload).
- Não altere manualmente os arquivos Parquet.
- Se aparecer erro de leitura, confira se o cabeçalho está presente e se as colunas estão nomeadas corretamente.
- O sistema é tolerante a variações, mas nomes muito diferentes podem exigir ajuste futuro.

## Contato e melhorias
- Para dúvidas, sugestões ou reportar bugs, registre um issue no repositório ou entre em contato com o responsável pelo projeto.

---

### Status dos dados atuais
""")

col1, col2, col3 = st.columns(3)
with col1:
    if os.path.exists(ACOES_PATH):
        df = pd.read_parquet(ACOES_PATH)
        st.metric("Snapshots de Ações", len(df["Mês/Ano"].unique()))
        st.info(f"Linhas totais: {len(df)}")
    else:
        st.warning("Sem dados de Ações")
with col2:
    if os.path.exists(RENDA_FIXA_PATH):
        df = pd.read_parquet(RENDA_FIXA_PATH)
        st.metric("Snapshots de Renda Fixa", len(df["Mês/Ano"].unique()))
        st.info(f"Linhas totais: {len(df)}")
    else:
        st.warning("Sem dados de Renda Fixa")
with col3:
    if os.path.exists(PROVENTOS_PATH):
        df = pd.read_parquet(PROVENTOS_PATH)
        st.metric("Meses de Proventos", len(df["Mês/Ano"].unique()))
        st.info(f"Linhas totais: {len(df)}")
    else:
        st.warning("Sem dados de Proventos")

st.markdown("""
---

#### Esta página serve como referência para o funcionamento, regras e boas práticas do sistema. Sempre consulte aqui antes de abrir um chamado ou alterar arquivos do projeto.
""")
