
import os
import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf

from modules.usuarios import carregar_usuarios, salvar_usuarios
from modules.upload_relatorio import carregar_historico_parquet, ACOES_PATH, RENDA_FIXA_PATH, PROVENTOS_PATH, padronizar_tabelas, padronizar_dividendos
from modules.avenue_views import aba_acoes_avenue, aba_proventos_avenue, padronizar_dividendos_avenue, carregar_dividendos_avenue
from src.modules.alerts import calcular_projecao_avancada
import io

st.set_page_config(page_title="Invest - Controle de Investimentos", layout="wide")
st.title("💰 Invest - Controle de Investimentos")


# Carregar histórico consolidado
try:
    df = carregar_historico_parquet()
except Exception:
    df = pd.DataFrame()

# Carregar usuários persistentes
df_usuarios = carregar_usuarios()

# Função para carregar DataFrame Parquet
def carregar_df_parquet(path):
    if os.path.exists(path):
        try:
            return pd.read_parquet(path)
        except Exception:
            return pd.DataFrame()
    else:
        return pd.DataFrame()

# Carrega dados base
df_acoes_raw = carregar_df_parquet(ACOES_PATH)
df_rf_raw = carregar_df_parquet(RENDA_FIXA_PATH)
df_prov_raw = carregar_df_parquet(PROVENTOS_PATH)
df_padronizado = padronizar_tabelas(df_acoes_raw, df_rf_raw)

# Dividendos consolidado (inclui avenue)
df_dividendos = padronizar_dividendos(df_prov_raw)
df_dividendos_avenue_raw = carregar_dividendos_avenue()
df_dividendos_avenue = padronizar_dividendos_avenue(df_dividendos_avenue_raw) if not df_dividendos_avenue_raw.empty else pd.DataFrame()

if not df_dividendos_avenue.empty:
    df_dividendos = pd.concat([df_dividendos, df_dividendos_avenue], ignore_index=True)

# Fonte passa a ser o usuário para simplificar filtro
if not df_dividendos.empty:
    # Preenche Usuário: prioriza coluna existente, senão usa Fonte, senão "Importado"
    if "Usuário" not in df_dividendos.columns:
        df_dividendos["Usuário"] = None
    if "Fonte" not in df_dividendos.columns:
        df_dividendos["Fonte"] = None
    df_dividendos["Usuário"] = df_dividendos["Usuário"].fillna(df_dividendos.get("Fonte", "")).replace("", "Importado")
    # remove sufixo (MM/AAAA) entre parênteses
    df_dividendos["Usuário"] = df_dividendos["Usuário"].astype(str).str.replace(r"\s*\(\d{2}/\d{4}\)$", "", regex=True)
    df_dividendos["Fonte"] = df_dividendos["Usuário"]

    # Ativo: se vazio, usa Produto
    if "Ativo" not in df_dividendos.columns:
        df_dividendos["Ativo"] = None
    if "Produto" in df_dividendos.columns:
        df_dividendos["Ativo"] = df_dividendos["Ativo"].fillna(df_dividendos["Produto"])
    df_dividendos["Ativo"] = df_dividendos["Ativo"].fillna("").astype(str)

    # Normalizações
    if "Fonte" in df_dividendos.columns:
        df_dividendos["Fonte"] = df_dividendos["Fonte"].fillna("").astype(str)
    if "Data" in df_dividendos.columns:
        df_dividendos["Data"] = pd.to_datetime(df_dividendos["Data"], errors="coerce")

# Tabs para visualização por categoria e consolidado
tab_consolidado, tab_acoes, tab_rf, tab_td, tab_dividendos, tab_prov, tab_acoes_avenue, tab_proventos_avenue, tab5, tab6 = st.tabs([
    "Consolidado", "Ações", "Renda Fixa", "Tesouro Direto", "Dividendos Consolidado", "Proventos", 
    "🏦 Ações Avenue", "💰 Proventos Avenue", "Cadastro", "Inserção Manual"
])

# Aba Ações Avenue
with tab_acoes_avenue:
    aba_acoes_avenue()

# Aba Proventos Avenue
with tab_proventos_avenue:
    aba_proventos_avenue()

# Aba Cadastro de Usuários
with tab5:
    st.header("Cadastro de Usuários")
    nome = st.text_input("Nome do usuário")
    cpf = st.text_input("CPF")
    if st.button("Adicionar Usuário"):
        if nome and cpf:
            novo_usuario = pd.DataFrame([{"Nome": nome, "CPF": cpf}])
            df_usuarios = pd.concat([df_usuarios, novo_usuario], ignore_index=True).drop_duplicates()
            salvar_usuarios(df_usuarios)
            st.success(f"{nome} adicionado!")
        else:
            st.error("Preencha todos os campos.")
    st.table(df_usuarios)



# Aba Consolidado (tudo junto)
with tab_consolidado:
    st.header("🔄 Consolidação (Ações + Renda Fixa)")
    
    meses_disponiveis = sorted(df_padronizado["Mês/Ano"].dropna().unique()) if not df_padronizado.empty else []
    
    if meses_disponiveis:
        col_sel1, col_sel2 = st.columns(2)
        with col_sel1:
            mes_consolidado = st.selectbox(
                "Selecione Mês/Ano para consolidação",
                meses_disponiveis,
                index=len(meses_disponiveis) - 1,
                key="consolidacao_mes_app"
            )

        usuarios_mes = sorted(df_padronizado.get("Usuário", pd.Series()).dropna().unique())

        with col_sel2:
            usuarios_sel = st.multiselect(
                "Usuário",
                usuarios_mes,
                default=usuarios_mes,
                key="consolidacao_usuario_app",
                help="Filtra posições do mês pelo usuário"
            )

        df_consolidado = df_padronizado
        if mes_consolidado:
            df_consolidado = df_consolidado[df_consolidado["Mês/Ano"] == mes_consolidado]
        if usuarios_sel:
            df_consolidado = df_consolidado[df_consolidado["Usuário"].isin(usuarios_sel)]
        
        if not df_consolidado.empty:
            st.success(f"✅ {len(df_consolidado)} posições consolidadas")
            st.metric("Valor total consolidado", f"{df_consolidado['Valor'].sum():,.2f}")
            
            # Resumo por tipo
            col1, col2, col3 = st.columns(3)
            with col1:
                valor_acoes = df_consolidado[df_consolidado["Tipo"] == "Ações"]["Valor"].sum()
                st.metric("Ações", f"{valor_acoes:,.2f}")
            with col2:
                valor_rf = df_consolidado[df_consolidado["Tipo"] == "Renda Fixa"]["Valor"].sum()
                st.metric("Renda Fixa", f"{valor_rf:,.2f}")
            with col3:
                valor_td = df_consolidado[df_consolidado["Tipo"] == "Tesouro Direto"]["Valor"].sum()
                st.metric("Tesouro Direto", f"{valor_td:,.2f}")
            
            st.markdown("---")
            st.subheader("📊 Posições Consolidadas")
            st.dataframe(df_consolidado, use_container_width=True)
            
            # Gráfico de distribuição
            dist_tipo = df_consolidado.groupby("Tipo")["Valor"].sum()
            st.bar_chart(dist_tipo)
        else:
            st.warning("Nenhum dado disponível para o mês selecionado")
    else:
        st.info("Sem dados de Ações ou Renda Fixa")

# Aba Ações
with tab_acoes:
    st.header("Ações")
    df_acoes = df_padronizado[df_padronizado.get("Tipo") == "Ações"] if not df_padronizado.empty else pd.DataFrame()
    if df_acoes.empty:
        st.info("Sem dados de Ações")
    else:
        meses = sorted(df_acoes["Mês/Ano"].dropna().unique()) if "Mês/Ano" in df_acoes.columns else []
        usuarios = sorted(df_acoes["Usuário"].dropna().unique()) if "Usuário" in df_acoes.columns else []
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            mes_sel = st.selectbox("Mês/Ano", meses, index=len(meses)-1 if meses else 0, key="acao_mes") if meses else None
        with col_f2:
            usuarios_sel = st.multiselect("Usuário", usuarios, default=usuarios, key="acao_user") if usuarios else []

        df_view = df_acoes
        if mes_sel:
            df_view = df_view[df_view["Mês/Ano"] == mes_sel]
        if usuarios_sel:
            df_view = df_view[df_view["Usuário"].isin(usuarios_sel)]

        st.metric("Valor total", f"{df_view.get('Valor', pd.Series()).sum():,.2f}")
        st.dataframe(df_view, use_container_width=True)

# Aba Renda Fixa
with tab_rf:
    st.header("Renda Fixa")
    df_rf = df_padronizado[df_padronizado.get("Tipo") == "Renda Fixa"] if not df_padronizado.empty else pd.DataFrame()
    if df_rf.empty:
        st.info("Sem dados de Renda Fixa")
    else:
        meses = sorted(df_rf["Mês/Ano"].dropna().unique()) if "Mês/Ano" in df_rf.columns else []
        usuarios = sorted(df_rf["Usuário"].dropna().unique()) if "Usuário" in df_rf.columns else []
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            mes_sel_rf = st.selectbox("Mês/Ano", meses, index=len(meses)-1 if meses else 0, key="rf_mes") if meses else None
        with col_f2:
            usuarios_sel_rf = st.multiselect("Usuário", usuarios, default=usuarios, key="rf_user") if usuarios else []

        df_view_rf = df_rf
        if mes_sel_rf:
            df_view_rf = df_view_rf[df_view_rf["Mês/Ano"] == mes_sel_rf]
        if usuarios_sel_rf:
            df_view_rf = df_view_rf[df_view_rf["Usuário"].isin(usuarios_sel_rf)]

        st.metric("Valor total", f"{df_view_rf.get('Valor', pd.Series()).sum():,.2f}")
        st.dataframe(df_view_rf, use_container_width=True)

# Aba Tesouro Direto
with tab_td:
    st.header("Tesouro Direto")
    df_td = df_padronizado[df_padronizado.get("Tipo") == "Tesouro Direto"] if not df_padronizado.empty else pd.DataFrame()
    if df_td.empty:
        st.info("Nenhuma posição de Tesouro Direto encontrada")
    else:
        meses_td = sorted(df_td["Mês/Ano"].dropna().unique()) if "Mês/Ano" in df_td.columns else []
        usuarios_td = sorted(df_td["Usuário"].dropna().unique()) if "Usuário" in df_td.columns else []
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            mes_sel_td = st.selectbox("Mês/Ano", meses_td, index=len(meses_td)-1 if meses_td else 0, key="td_mes") if meses_td else None
        with col_f2:
            usuarios_sel_td = st.multiselect("Usuário", usuarios_td, default=usuarios_td, key="td_user") if usuarios_td else []

        df_view_td = df_td
        if mes_sel_td:
            df_view_td = df_view_td[df_view_td["Mês/Ano"] == mes_sel_td]
        if usuarios_sel_td:
            df_view_td = df_view_td[df_view_td["Usuário"].isin(usuarios_sel_td)]

        st.metric("Valor total Tesouro Direto", f"R$ {df_view_td.get('Valor', pd.Series()).sum():,.2f}")
        st.dataframe(df_view_td, use_container_width=True)


# Aba Dividendos Consolidado
with tab_dividendos:
    st.header("💰 Dividendos Consolidado")
    
    if df_dividendos.empty:
        st.info("Nenhum dividendo registrado")
    else:
        st.success(f"✅ {len(df_dividendos)} dividendos registrados")
        
        # Métricas principais
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Valor Total Líquido", f"R$ {df_dividendos['Valor Líquido'].sum():,.2f}")
        with col2:
            st.metric("Valor Total Bruto", f"R$ {df_dividendos['Valor Bruto'].sum():,.2f}")
        with col3:
            impostos_total = df_dividendos['Impostos'].sum()
            st.metric("Impostos Retidos", f"R$ {impostos_total:,.2f}")
        
        st.markdown("---")
        
        # Filtros
        col_f1, col_f2, col_f3 = st.columns(3)
        
        with col_f1:
            ativo_sel = st.multiselect(
                "Ativo",
                sorted(df_dividendos["Ativo"].unique()),
                default=sorted(df_dividendos["Ativo"].unique()),
                key="div_ativo"
            )
        
        with col_f2:
            fonte_sel = st.multiselect(
                "Usuário",
                sorted(df_dividendos["Fonte"].unique()),
                default=sorted(df_dividendos["Fonte"].unique()),
                key="div_fonte"
            )
        
        with col_f3:
            ordenacao = st.selectbox(
                "Ordenar por",
                ["Data (mais recente)", "Data (mais antigo)", "Valor (maior)", "Valor (menor)", "Ativo (A-Z)"],
                key="div_ordenacao"
            )
        
        # Aplicar filtros
        df_div_filtrado = df_dividendos
        if ativo_sel:
            df_div_filtrado = df_div_filtrado[df_div_filtrado["Ativo"].isin(ativo_sel)]
        if fonte_sel:
            df_div_filtrado = df_div_filtrado[df_div_filtrado["Fonte"].isin(fonte_sel)]
        
        # Aplicar ordenação
        if ordenacao == "Data (mais recente)":
            df_div_filtrado = df_div_filtrado.sort_values("Data", ascending=False)
        elif ordenacao == "Data (mais antigo)":
            df_div_filtrado = df_div_filtrado.sort_values("Data", ascending=True)
        elif ordenacao == "Valor (maior)":
            df_div_filtrado = df_div_filtrado.sort_values("Valor Líquido", ascending=False)
        elif ordenacao == "Valor (menor)":
            df_div_filtrado = df_div_filtrado.sort_values("Valor Líquido", ascending=True)
        elif ordenacao == "Ativo (A-Z)":
            df_div_filtrado = df_div_filtrado.sort_values("Ativo", ascending=True)
        
        # Exibir tabela
        st.subheader("📊 Dividendos")
        st.dataframe(df_div_filtrado, use_container_width=True)
        
        # Exportação
        st.markdown("---")
        st.subheader("📥 Exportar Dados")
        
        col_exp1, col_exp2 = st.columns(2)
        
        with col_exp1:
            csv = df_div_filtrado.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="📥 Baixar como CSV",
                data=csv,
                file_name="dividendos_consolidado.csv",
                mime="text/csv"
            )
        
        with col_exp2:
            # Excel export
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df_div_filtrado.to_excel(writer, index=False, sheet_name="Dividendos")
            buffer.seek(0)
            st.download_button(
                label="📥 Baixar como Excel",
                data=buffer,
                file_name="dividendos_consolidado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        # Resumo por ativo
        st.markdown("---")
        st.subheader("💹 Resumo por Ativo")
        resumo_ativo = df_div_filtrado.groupby("Ativo").agg({
            "Valor Líquido": "sum",
            "Valor Bruto": "sum",
            "Impostos": "sum"
        }).reset_index().sort_values("Valor Líquido", ascending=False)
        st.dataframe(resumo_ativo, use_container_width=True)
        
        # Gráfico de distribuição
        st.markdown("---")
        st.subheader("📈 Distribuição por Ativo")
        dist_ativo = df_div_filtrado.groupby("Ativo")["Valor Líquido"].sum().sort_values(ascending=False)
        st.bar_chart(dist_ativo)


with tab_prov:
    st.header("Proventos")
    df_prov = df_prov_raw
    st.dataframe(df_prov)
    st.header("Evolução dos Proventos Recebidos")
    periodos = ["Mensal", "Bimestral", "Trimestral", "Semestral", "Anual"]
    periodo = st.selectbox("Período", periodos, key="periodo_prov")
    if not df_prov.empty and "Mês/Ano" in df_prov.columns and "Valor Líquido" in df_prov.columns:
        try:
            df_prov["Data"] = pd.to_datetime(df_prov["Mês/Ano"], format="%m/%Y")
            if periodo == "Mensal":
                df_group = df_prov.groupby([df_prov["Data"].dt.to_period("M")])["Valor Líquido"].sum()
            elif periodo == "Bimestral":
                df_group = df_prov.groupby([df_prov["Data"].dt.to_period("2M")])["Valor Líquido"].sum()
            elif periodo == "Trimestral":
                df_group = df_prov.groupby([df_prov["Data"].dt.to_period("Q")])["Valor Líquido"].sum()
            elif periodo == "Semestral":
                df_group = df_prov.groupby([df_prov["Data"].dt.to_period("6M")])["Valor Líquido"].sum()
            elif periodo == "Anual":
                df_group = df_prov.groupby([df_prov["Data"].dt.year])["Valor Líquido"].sum()
            df_group.index = df_group.index.astype(str)
            st.subheader("Gráfico de Barras - Valor Recebido")
            st.bar_chart(df_group)
            st.subheader("Gráfico de Linha - Valor Recebido")
            st.line_chart(df_group)
            # Gráfico de percentual mês a mês
            st.subheader("Gráfico de Linha - Percentual de Crescimento (%)")
            df_pct = df_group.pct_change().fillna(0) * 100
            st.line_chart(df_pct)
        except Exception as e:
            st.error(f"Erro ao gerar gráficos: {e}")
    elif not df_prov.empty:
        st.info("Dados insuficientes para gráfico de evolução.")
    else:
        st.info("Nenhum dado consolidado encontrado. Faça upload de relatórios na página apropriada.")

## As abas de Gráficos, Histórico e Comparações podem ser reimplementadas aqui se desejado, usando os novos DataFrames separados ou o consolidado.


# Aba Inserção Manual
with tab6:
    st.header("Inserção Manual de Investimentos")
    st.info("Funcionalidade em desenvolvimento.")
