import os
import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf

from modules.usuarios import carregar_usuarios, salvar_usuarios
from modules.upload_relatorio import carregar_historico_parquet, ACOES_PATH, RENDA_FIXA_PATH, PROVENTOS_PATH, padronizar_tabelas, padronizar_dividendos
from modules.avenue_views import aba_acoes_avenue, aba_proventos_avenue, padronizar_dividendos_avenue, carregar_dividendos_avenue, padronizar_acoes_avenue, carregar_acoes_avenue
from modules.cotacoes import converter_usd_para_brl
from src.modules.alerts import calcular_projecao_avancada
import io

st.set_page_config(page_title="Invest - Controle de Investimentos", layout="wide")
st.title("💰 Invest - Controle de Investimentos")


# Função auxiliar para gerar gráficos de evolução de proventos
def gerar_graficos_evolucao(df: pd.DataFrame, coluna_valor: str = "Valor Líquido", coluna_data: str = "Data", chave_periodo: str = "periodo"):
    """
    Gera gráficos de evolução de proventos (barras, linha e crescimento %)
    """
    if df.empty or coluna_valor not in df.columns:
        return False
    
    # Garantir que Data é datetime
    if coluna_data in df.columns:
        df[coluna_data] = pd.to_datetime(df[coluna_data], errors="coerce")
    
    periodos = ["Mensal", "Bimestral", "Trimestral", "Semestral", "Anual"]
    periodo = st.selectbox("Período", periodos, key=chave_periodo)
    
    try:
        # Definir range de datas completo
        if df[coluna_data].isnull().all():
            st.warning("Sem datas válidas para evolução.")
            return False
        data_min = df[coluna_data].min()
        data_max = df[coluna_data].max()
        if periodo == "Mensal":
            freq = "M"
            idx = pd.period_range(data_min, data_max, freq=freq)
            df_group = df.groupby(df[coluna_data].dt.to_period("M"))[coluna_valor].sum().reindex(idx, fill_value=0)
        elif periodo == "Bimestral":
            # Agrupar de 2 em 2 meses reais
            df_temp = df.copy()
            df_temp["bimestre"] = ((df_temp[coluna_data].dt.month.sub(1) // 2) + 1).astype(str) + "/" + df_temp[coluna_data].dt.year.astype(str)
            # Criar label tipo '1/2023', '2/2023', ...
            df_temp["bimestre_label"] = df_temp[coluna_data].dt.year.astype(str) + "-" + ((df_temp[coluna_data].dt.month.sub(1) // 2)*2 + 1).astype(str).str.zfill(2) + "/" + (df_temp[coluna_data].dt.year.astype(str))
            # Agrupar por ano e bimestre
            df_temp["bimestre_ini"] = pd.to_datetime(df_temp[coluna_data].dt.year.astype(str) + "-" + ((df_temp[coluna_data].dt.month.sub(1) // 2)*2 + 1).astype(str).str.zfill(2) + "-01")
            group = df_temp.groupby("bimestre_ini")[coluna_valor].sum()
            idx = pd.date_range(data_min.replace(day=1), data_max.replace(day=1), freq="2MS")
            group = group.reindex(idx, fill_value=0)
            df_group = group
            df_group.index = [d.strftime("%Y-%m") for d in df_group.index]
        elif periodo == "Trimestral":
            freq = "Q"
            idx = pd.period_range(data_min, data_max, freq=freq)
            df_group = df.groupby(df[coluna_data].dt.to_period("Q"))[coluna_valor].sum().reindex(idx, fill_value=0)
        elif periodo == "Semestral":
            # Agrupar de 6 em 6 meses reais (jan-jun, jul-dez)
            df_temp = df.copy()
            df_temp["semestre_ini"] = pd.to_datetime(df_temp[coluna_data].dt.year.astype(str) + "-" + ((df_temp[coluna_data].dt.month <= 6).map({True: '01', False: '07'})) + "-01")
            group = df_temp.groupby("semestre_ini")[coluna_valor].sum()
            # Gera todos os semestres do range
            semestres = []
            ano_ini = data_min.year
            ano_fim = data_max.year
            for ano in range(ano_ini, ano_fim+1):
                semestres.append(pd.Timestamp(f"{ano}-01-01"))
                semestres.append(pd.Timestamp(f"{ano}-07-01"))
            semestres = [s for s in semestres if s >= data_min.replace(day=1) and s <= data_max.replace(day=1)]
            group = group.reindex(semestres, fill_value=0)
            df_group = group
            df_group.index = [d.strftime("%Y-%m") for d in df_group.index]
        elif periodo == "Anual":
            freq = "Y"
            idx = pd.period_range(data_min, data_max, freq=freq)
            df_group = df.groupby(df[coluna_data].dt.to_period("Y"))[coluna_valor].sum().reindex(idx, fill_value=0)
        df_group.index = df_group.index.astype(str)

        # Gráfico de barras com rótulo
        st.subheader("Gráfico de Barras - Valor Recebido")
        fig_bar = px.bar(
            x=df_group.index,
            y=df_group.values,
            labels={"x": "Período", "y": coluna_valor},
            text=[f"{v:,.2f}" for v in df_group.values]
        )
        fig_bar.update_traces(textposition="outside")
        fig_bar.update_layout(yaxis_tickformat=",.2f", xaxis_tickmode="array", xaxis_tickvals=list(df_group.index), xaxis_ticktext=list(df_group.index))
        st.plotly_chart(fig_bar, use_container_width=True)

        # Gráfico de linha com rótulo
        st.subheader("Gráfico de Linha - Valor Recebido")
        fig_line = px.line(
            x=df_group.index,
            y=df_group.values,
            labels={"x": "Período", "y": coluna_valor},
            text=[f"{v:,.2f}" for v in df_group.values]
        )
        fig_line.update_traces(textposition="top center", mode="lines+markers+text")
        fig_line.update_layout(yaxis_tickformat=",.2f", xaxis_tickmode="array", xaxis_tickvals=list(df_group.index), xaxis_ticktext=list(df_group.index))
        st.plotly_chart(fig_line, use_container_width=True)

        # Gráfico de linha percentual
        st.subheader("Gráfico de Linha - Percentual de Crescimento (%)")
        df_pct = df_group.pct_change().fillna(0) * 100
        fig_pct = px.line(
            x=df_group.index,
            y=df_pct.values,
            labels={"x": "Período", "y": "% Crescimento"},
            text=[f"{v:.2f}%" for v in df_pct.values]
        )
        fig_pct.update_traces(textposition="top center", mode="lines+markers+text")
        fig_pct.update_layout(yaxis_tickformat=".2f", xaxis_tickmode="array", xaxis_tickvals=list(df_group.index), xaxis_ticktext=list(df_group.index))
        st.plotly_chart(fig_pct, use_container_width=True)

        return True
    except Exception as e:
        st.error(f"Erro ao gerar gráficos: {e}")
        return False


# Função auxiliar para gerar gráfico de top pagadores
def gerar_grafico_top_pagadores(df: pd.DataFrame, coluna_ativo: str = "Ativo", coluna_valor: str = "Valor Líquido", coluna_data: str = "Data", chave_prefixo: str = "top"):
    """
    Gera gráfico vertical com top pagadores de dividendos
    """
    if df.empty or coluna_ativo not in df.columns or coluna_valor not in df.columns:
        return False
    
    # Garantir que Data é datetime
    if coluna_data in df.columns:
        df[coluna_data] = pd.to_datetime(df[coluna_data], errors="coerce")
    
    col_periodo, col_mes, col_top = st.columns(3)
    
    with col_periodo:
        tipo_periodo = st.selectbox(
            "Período",
            ["Mensal", "Anual"],
            key=f"{chave_prefixo}_tipo_periodo"
        )
    
    with col_mes:
        if tipo_periodo == "Mensal":
            periodos_disponiveis = sorted(df[coluna_data].dt.to_period("M").unique().astype(str))
            if periodos_disponiveis:
                periodo_sel = st.selectbox("Mês", periodos_disponiveis, index=len(periodos_disponiveis)-1, key=f"{chave_prefixo}_mes")
                df_filtrado = df[df[coluna_data].dt.to_period("M").astype(str) == periodo_sel]
            else:
                df_filtrado = df
        else:  # Anual
            anos_disponiveis = sorted(df[coluna_data].dt.year.unique().astype(str))
            if anos_disponiveis:
                ano_sel = st.selectbox("Ano", anos_disponiveis, index=len(anos_disponiveis)-1, key=f"{chave_prefixo}_ano")
                df_filtrado = df[df[coluna_data].dt.year.astype(str) == ano_sel]
            else:
                df_filtrado = df
    
    with col_top:
        opcoes_top = ["Top 5", "Top 10", "Top 15", "Top 20", "Top 25"]
        top_sel = st.selectbox("Quantidade", opcoes_top, index=1, key=f"{chave_prefixo}_quantidade")
        top_num = int(top_sel.split()[1])
    
    try:
        # Agrupar por ativo e somar, ordenar do maior para o menor
        top_ativos = df_filtrado.groupby(coluna_ativo)[coluna_valor].sum().sort_values(ascending=False).head(top_num)

        st.subheader(f"Top {top_num} Maiores Pagadores - {tipo_periodo}")
        fig_top = px.bar(
            x=top_ativos.index,
            y=top_ativos.values,
            labels={"x": coluna_ativo, "y": coluna_valor},
            text=[f"{v:,.2f}" for v in top_ativos.values]
        )
        fig_top.update_traces(textposition="outside")
        fig_top.update_layout(yaxis_tickformat=",.2f")
        st.plotly_chart(fig_top, use_container_width=True)

        # Tabela com os valores, do maior para o menor
        st.subheader(f"Detalhes - Top {top_num}")
        df_top_table = pd.DataFrame({
            "Ativo": top_ativos.index,
            "Valor Total": [f"{v:,.2f}" for v in top_ativos.values]
        }).reset_index(drop=True)
        st.dataframe(df_top_table, use_container_width=True, hide_index=True)

        return True
    except Exception as e:
        st.error(f"Erro ao gerar gráfico de top pagadores: {e}")
        return False


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
    # Converter valores USD para BRL usando cotação do mês correspondente
    if "Valor Bruto" in df_dividendos_avenue.columns and "Data" in df_dividendos_avenue.columns:
        df_dividendos_avenue["Valor Bruto"] = df_dividendos_avenue.apply(
            lambda row: converter_usd_para_brl(row["Valor Bruto"], f"{row['Data'].month:02d}/{row['Data'].year}") if pd.notna(row["Data"]) else row["Valor Bruto"],
            axis=1
        )
    if "Impostos" in df_dividendos_avenue.columns and "Data" in df_dividendos_avenue.columns:
        df_dividendos_avenue["Impostos"] = df_dividendos_avenue.apply(
            lambda row: converter_usd_para_brl(row["Impostos"], f"{row['Data'].month:02d}/{row['Data'].year}") if pd.notna(row["Data"]) else row["Impostos"],
            axis=1
        )
    if "Valor Líquido" in df_dividendos_avenue.columns and "Data" in df_dividendos_avenue.columns:
        df_dividendos_avenue["Valor Líquido"] = df_dividendos_avenue.apply(
            lambda row: converter_usd_para_brl(row["Valor Líquido"], f"{row['Data'].month:02d}/{row['Data'].year}") if pd.notna(row["Data"]) else row["Valor Líquido"],
            axis=1
        )
    
    df_dividendos = pd.concat([df_dividendos, df_dividendos_avenue], ignore_index=True)

# Ações Avenue consolidadas
df_acoes_avenue_raw = carregar_acoes_avenue()
df_acoes_avenue_padrao = pd.DataFrame()
if not df_acoes_avenue_raw.empty:
    df_acoes_avenue_padrao = padronizar_acoes_avenue(df_acoes_avenue_raw)
    
    # Converter valores USD para BRL usando cotação do mês correspondente
    if "Valor" in df_acoes_avenue_padrao.columns and "Mês/Ano" in df_acoes_avenue_padrao.columns:
        df_acoes_avenue_padrao["Valor"] = df_acoes_avenue_padrao.apply(
            lambda row: converter_usd_para_brl(row["Valor"], row["Mês/Ano"]) if pd.notna(row["Mês/Ano"]) else row["Valor"],
            axis=1
        )
    if "Preço" in df_acoes_avenue_padrao.columns and "Mês/Ano" in df_acoes_avenue_padrao.columns:
        df_acoes_avenue_padrao["Preço"] = df_acoes_avenue_padrao.apply(
            lambda row: converter_usd_para_brl(row["Preço"], row["Mês/Ano"]) if pd.notna(row["Mês/Ano"]) else row["Preço"],
            axis=1
        )
    
    df_acoes_avenue_padrao["Tipo"] = "Ações Dólar"
    df_acoes_avenue_padrao["Fonte"] = "Avenue"
    # Garantir colunas esperadas
    for col in ["Mês/Ano", "Usuário"]:
        if col not in df_acoes_avenue_padrao.columns:
            df_acoes_avenue_padrao[col] = None

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
tab_acoes, tab_acoes_avenue, tab_acoes_consolidadas, tab_rf, tab_rf_consolidada, tab_td, tab_prov, tab_proventos_avenue, tab_dividendos, tab_consolidado, tab5, tab6 = st.tabs([
    "📈 Ações", "🏦 Ações Avenue", "🌎 Ações Consolidadas", "💵 Renda Fixa", "🏛️ Renda Fixa Consolidada", "💰 Tesouro Direto", "💸 Proventos", "🪙 Proventos Avenue", "💲 Dividendos Consolidado", "🔄 Consolidação", "👤 Cadastro", "📝 Inserção Manual"
])

# Aba Ações Avenue
with tab_acoes_avenue:
    aba_acoes_avenue()

# Aba Ações Consolidadas (Ações BR + Ações Avenue)
with tab_acoes_consolidadas:
    st.header("🌎 Ações Consolidadas (Brasil + Avenue)")
    
    # Combinar ações brasileiras e ações Avenue
    df_acoes_br = df_padronizado[df_padronizado.get("Tipo") == "Ações"] if not df_padronizado.empty else pd.DataFrame()
    df_acoes_usd = df_acoes_avenue_padrao.copy() if not df_acoes_avenue_padrao.empty else pd.DataFrame()
    
    # Combinar os DataFrames
    df_acoes_todas = pd.DataFrame()
    if not df_acoes_br.empty and not df_acoes_usd.empty:
        colunas_comuns = list(set(df_acoes_br.columns) & set(df_acoes_usd.columns))
        df_acoes_todas = pd.concat(
            [df_acoes_br[colunas_comuns], df_acoes_usd[colunas_comuns]],
            ignore_index=True
        )
    elif not df_acoes_br.empty:
        df_acoes_todas = df_acoes_br.copy()
    elif not df_acoes_usd.empty:
        df_acoes_todas = df_acoes_usd.copy()
    
    if df_acoes_todas.empty:
        st.info("Sem dados de Ações")
    else:
        # Filtros
        meses = sorted(df_acoes_todas["Mês/Ano"].dropna().unique()) if "Mês/Ano" in df_acoes_todas.columns else []
        usuarios = sorted(df_acoes_todas["Usuário"].dropna().unique()) if "Usuário" in df_acoes_todas.columns else []
        tipos = sorted(df_acoes_todas["Tipo"].dropna().unique()) if "Tipo" in df_acoes_todas.columns else []
        
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            mes_sel_cons = st.selectbox("Mês/Ano", meses, index=len(meses)-1 if meses else 0, key="acao_cons_mes") if meses else None
        with col_f2:
            usuarios_sel_cons = st.multiselect("Usuário", usuarios, default=usuarios, key="acao_cons_user") if usuarios else []
        with col_f3:
            tipos_sel_cons = st.multiselect("Tipo", tipos, default=tipos, key="acao_cons_tipo") if tipos else []
        
        # Aplicar filtros
        df_view_cons = df_acoes_todas
        if mes_sel_cons:
            df_view_cons = df_view_cons[df_view_cons["Mês/Ano"] == mes_sel_cons]
        if usuarios_sel_cons:
            df_view_cons = df_view_cons[df_view_cons["Usuário"].isin(usuarios_sel_cons)]
        if tipos_sel_cons:
            df_view_cons = df_view_cons[df_view_cons["Tipo"].isin(tipos_sel_cons)]
        
        # Métricas
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            valor_total = df_view_cons.get("Valor", pd.Series()).sum()
            st.metric("Valor Total", f"R$ {valor_total:,.2f}")
        with col_m2:
            valor_br = df_view_cons[df_view_cons["Tipo"] == "Ações"]["Valor"].sum() if "Tipo" in df_view_cons.columns else 0
            st.metric("Ações Brasil", f"R$ {valor_br:,.2f}")
        with col_m3:
            valor_usd = df_view_cons[df_view_cons["Tipo"] == "Ações Dólar"]["Valor"].sum() if "Tipo" in df_view_cons.columns else 0
            st.metric("Ações Dólar (USD)", f"R$ {valor_usd:,.2f}")
        
        st.markdown("---")
        
        # Tabela
        st.subheader("📋 Posições")
        st.dataframe(df_view_cons, use_container_width=True)
        
        # Gráficos
        if not df_view_cons.empty:
            st.markdown("---")
            st.subheader("📉 Distribuição")
            
            # Gráfico de pizza por tipo (Brasil vs Dólar)
            if "Tipo" in df_view_cons.columns:
                dist_tipo = df_view_cons.groupby("Tipo")["Valor"].sum()
                fig_pie_tipo = px.pie(
                    names=dist_tipo.index,
                    values=dist_tipo.values,
                    title="Distribuição por Tipo",
                    hole=0.3,
                    color_discrete_sequence=px.colors.sequential.RdBu,
                    labels={"names": "Tipo", "values": "Valor"}
                )
                fig_pie_tipo.update_traces(
                    textinfo="label+percent+value",
                    texttemplate="%{label}<br>R$%{value:,.2f} (%{percent})"
                )
                st.plotly_chart(fig_pie_tipo, use_container_width=True)
            
            # Gráfico de barras por ativo
            top_n = 10
            top_ativos = df_view_cons.groupby("Ativo")["Valor"].sum().nlargest(top_n).sort_values(ascending=False)
            if not top_ativos.empty:
                st.subheader(f"🏆 Top {top_n} Ativos por Valor")
                fig_bar = px.bar(
                    x=top_ativos.index,
                    y=top_ativos.values,
                    labels={"x": "Ativo", "y": "Valor (R$)"},
                    text=[f"R$ {v:,.2f}" for v in top_ativos.values],
                    color_discrete_sequence=["#1f77b4"]
                )
                fig_bar.update_traces(textposition="outside")
                fig_bar.update_layout(yaxis_tickformat=",.2f")
                st.plotly_chart(fig_bar, use_container_width=True)

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
    st.header("🔄 Consolidação (Ações + Renda Fixa + Avenue)")
    
    # Combinar df_padronizado com ações Avenue
    df_consolidacao = df_padronizado.copy()
    if not df_acoes_avenue_padrao.empty:
        # Manter apenas colunas comuns
        colunas_comuns = list(set(df_consolidacao.columns) & set(df_acoes_avenue_padrao.columns))
        df_consolidacao = pd.concat(
            [df_consolidacao[colunas_comuns], df_acoes_avenue_padrao[colunas_comuns]],
            ignore_index=True
        )
    
    meses_disponiveis = sorted(df_consolidacao["Mês/Ano"].dropna().unique()) if not df_consolidacao.empty else []
    
    if meses_disponiveis:
        col_sel1, col_sel2 = st.columns(2)
        with col_sel1:
            mes_consolidado = st.selectbox(
                "Selecione Mês/Ano para consolidação",
                meses_disponiveis,
                index=len(meses_disponiveis) - 1,
                key="consolidacao_mes_app"
            )

        usuarios_mes = sorted(df_consolidacao.get("Usuário", pd.Series()).dropna().unique())

        with col_sel2:
            usuarios_sel = st.multiselect(
                "Usuário",
                usuarios_mes,
                default=usuarios_mes,
                key="consolidacao_usuario_app",
                help="Filtra posições do mês pelo usuário"
            )

        df_consolidado = df_consolidacao
        # Filtrar Opções
        if "Tipo" in df_consolidado.columns:
            df_consolidado = df_consolidado[df_consolidado["Tipo"] != "Opções"]
        if mes_consolidado:
            df_consolidado = df_consolidado[df_consolidado["Mês/Ano"] == mes_consolidado]
        if usuarios_sel:
            df_consolidado = df_consolidado[df_consolidado["Usuário"].isin(usuarios_sel)]
        
        if not df_consolidado.empty:
            st.success(f"✅ {len(df_consolidado)} posições consolidadas")
            st.metric("Valor total consolidado", f"{df_consolidado['Valor'].sum():,.2f}")
            
            # Resumo por tipo
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                valor_acoes = df_consolidado[df_consolidado["Tipo"] == "Ações"]["Valor"].sum()
                st.metric("Ações", f"{valor_acoes:,.2f}")
            with col2:
                valor_acoes_dolar = df_consolidado[df_consolidado["Tipo"] == "Ações Dólar"]["Valor"].sum()
                st.metric("Ações Dólar", f"{valor_acoes_dolar:,.2f}")
            with col3:
                valor_rf = df_consolidado[df_consolidado["Tipo"] == "Renda Fixa"]["Valor"].sum()
                st.metric("Renda Fixa", f"{valor_rf:,.2f}")
            with col4:
                valor_td = df_consolidado[df_consolidado["Tipo"] == "Tesouro Direto"]["Valor"].sum()
                st.metric("Tesouro Direto", f"{valor_td:,.2f}")
            
            st.markdown("---")
            st.subheader("📊 Posições Consolidadas")
            st.dataframe(df_consolidado, use_container_width=True)
            
            # Gráfico de distribuição
            dist_tipo = df_consolidado.groupby("Tipo")["Valor"].sum()
            fig_pie = px.pie(
                names=dist_tipo.index,
                values=dist_tipo.values,
                title="Distribuição por Tipo",
                hole=0.3,
                color_discrete_sequence=px.colors.sequential.Blues,
                labels={"names": "Tipo", "values": "Valor"}
            )
            fig_pie.update_traces(textinfo="label+percent+value", texttemplate="%{label}<br>R$%{value:,.2f} (%{percent})")
            fig_pie.update_layout(showlegend=True)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.warning("Nenhum dado disponível para o mês selecionado")
    else:
        st.info("Sem dados de Ações, Renda Fixa ou Avenue")

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

# Aba Renda Fixa Consolidada (Renda Fixa + Tesouro Direto)
with tab_rf_consolidada:
    st.header("🏛️ Renda Fixa Consolidada (Renda Fixa + Tesouro Direto)")
    
    # Combinar Renda Fixa e Tesouro Direto
    df_rf_data = df_padronizado[df_padronizado.get("Tipo") == "Renda Fixa"] if not df_padronizado.empty else pd.DataFrame()
    df_td_data = df_padronizado[df_padronizado.get("Tipo") == "Tesouro Direto"] if not df_padronizado.empty else pd.DataFrame()
    
    # Combinar os DataFrames (ambos já têm as mesmas colunas padronizadas)
    df_rf_todas = pd.DataFrame()
    if not df_rf_data.empty and not df_td_data.empty:
        df_rf_todas = pd.concat([df_rf_data, df_td_data], ignore_index=True)
    elif not df_rf_data.empty:
        df_rf_todas = df_rf_data.copy()
    elif not df_td_data.empty:
        df_rf_todas = df_td_data.copy()
    
    if df_rf_todas.empty:
        st.info("Sem dados de Renda Fixa ou Tesouro Direto")
    else:
        # Filtros
        meses_rf_cons = sorted(df_rf_todas["Mês/Ano"].dropna().unique()) if "Mês/Ano" in df_rf_todas.columns else []
        usuarios_rf_cons = sorted(df_rf_todas["Usuário"].dropna().unique()) if "Usuário" in df_rf_todas.columns else []
        tipos_rf_cons = sorted(df_rf_todas["Tipo"].dropna().unique()) if "Tipo" in df_rf_todas.columns else []
        
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            mes_sel_rf_cons = st.selectbox("Mês/Ano", meses_rf_cons, index=len(meses_rf_cons)-1 if meses_rf_cons else 0, key="rf_cons_mes") if meses_rf_cons else None
        with col_f2:
            usuarios_sel_rf_cons = st.multiselect("Usuário", usuarios_rf_cons, default=usuarios_rf_cons, key="rf_cons_user") if usuarios_rf_cons else []
        with col_f3:
            tipos_sel_rf_cons = st.multiselect("Tipo", tipos_rf_cons, default=tipos_rf_cons, key="rf_cons_tipo") if tipos_rf_cons else []
        
        # Aplicar filtros
        df_view_rf_cons = df_rf_todas
        if mes_sel_rf_cons:
            df_view_rf_cons = df_view_rf_cons[df_view_rf_cons["Mês/Ano"] == mes_sel_rf_cons]
        if usuarios_sel_rf_cons:
            df_view_rf_cons = df_view_rf_cons[df_view_rf_cons["Usuário"].isin(usuarios_sel_rf_cons)]
        if tipos_sel_rf_cons:
            df_view_rf_cons = df_view_rf_cons[df_view_rf_cons["Tipo"].isin(tipos_sel_rf_cons)]
        
        # Métricas
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            valor_total_rf = df_view_rf_cons.get("Valor", pd.Series()).sum()
            st.metric("Valor Total", f"R$ {valor_total_rf:,.2f}")
        with col_m2:
            valor_rf_only = df_view_rf_cons[df_view_rf_cons["Tipo"] == "Renda Fixa"]["Valor"].sum() if "Tipo" in df_view_rf_cons.columns else 0
            st.metric("Renda Fixa", f"R$ {valor_rf_only:,.2f}")
        with col_m3:
            valor_td_only = df_view_rf_cons[df_view_rf_cons["Tipo"] == "Tesouro Direto"]["Valor"].sum() if "Tipo" in df_view_rf_cons.columns else 0
            st.metric("Tesouro Direto", f"R$ {valor_td_only:,.2f}")
        
        st.markdown("---")
        
        # Tabela
        st.subheader("📋 Posições")
        st.dataframe(df_view_rf_cons, use_container_width=True)
        
        # Gráficos
        if not df_view_rf_cons.empty:
            st.markdown("---")
            st.subheader("📉 Distribuição")
            
            # Gráfico de pizza por tipo (Renda Fixa vs Tesouro Direto)
            if "Tipo" in df_view_rf_cons.columns:
                dist_tipo_rf = df_view_rf_cons.groupby("Tipo")["Valor"].sum()
                fig_pie_rf = px.pie(
                    names=dist_tipo_rf.index,
                    values=dist_tipo_rf.values,
                    title="Distribuição por Tipo",
                    hole=0.3,
                    color_discrete_sequence=px.colors.sequential.Greens,
                    labels={"names": "Tipo", "values": "Valor"}
                )
                fig_pie_rf.update_traces(
                    textinfo="label+percent+value",
                    texttemplate="%{label}<br>R$%{value:,.2f} (%{percent})"
                )
                st.plotly_chart(fig_pie_rf, use_container_width=True)
            
            # Gráfico de barras por ativo
            top_n_rf = 10
            top_ativos_rf = df_view_rf_cons.groupby("Ativo")["Valor"].sum().nlargest(top_n_rf).sort_values(ascending=False)
            if not top_ativos_rf.empty:
                st.subheader(f"🏆 Top {top_n_rf} Ativos por Valor")
                fig_bar_rf = px.bar(
                    x=top_ativos_rf.index,
                    y=top_ativos_rf.values,
                    labels={"x": "Ativo", "y": "Valor (R$)"},
                    text=[f"R$ {v:,.2f}" for v in top_ativos_rf.values],
                    color_discrete_sequence=["#2ca02c"]
                )
                fig_bar_rf.update_traces(textposition="outside")
                fig_bar_rf.update_layout(yaxis_tickformat=",.2f")
                st.plotly_chart(fig_bar_rf, use_container_width=True)

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
    
    # Filtro de origem dos proventos
    col_filtro_origem = st.columns(1)[0]
    with col_filtro_origem:
        tipo_provento = st.radio(
            "Origem dos Proventos:",
            ["Proventos Avenue", "Proventos Gerais", "Todos"],
            index=2,
            horizontal=True,
            key="consolidado_tipo_provento_app"
        )
    
    # Carregar e consolidar dados conforme seleção
    from modules.avenue_views import carregar_proventos_gerais
    
    df_div_avenue_raw = carregar_dividendos_avenue()
    df_div_avenue_proc = padronizar_dividendos_avenue(df_div_avenue_raw) if not df_div_avenue_raw.empty else pd.DataFrame()
    
    df_div_gerais_proc = carregar_proventos_gerais()
    
    if tipo_provento == "Proventos Avenue":
        df_div_filtrado_origem = df_div_avenue_proc
    elif tipo_provento == "Proventos Gerais":
        df_div_filtrado_origem = df_div_gerais_proc
    else:  # "Todos"
        df_div_filtrado_origem = pd.concat([df_div_avenue_proc, df_div_gerais_proc], ignore_index=True) if not df_div_avenue_proc.empty or not df_div_gerais_proc.empty else pd.DataFrame()
    
    if df_div_filtrado_origem.empty:
        st.info("📭 Nenhum dividendo disponível para a origem selecionada. Faça upload de PDFs na página de Upload.")
    else:
        # Padronizar Data
        if "Data" in df_div_filtrado_origem.columns:
            df_div_filtrado_origem["Data"] = pd.to_datetime(df_div_filtrado_origem["Data"], errors="coerce")
        
        st.success(f"✅ {len(df_div_filtrado_origem)} dividendos registrados")
        
        # Métricas principais
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total de Registros", len(df_div_filtrado_origem))
        with col2:
            valor_bruto_total = df_div_filtrado_origem.get("Valor Bruto", pd.Series()).sum()
            st.metric("Valor Bruto Total", f"R$ {valor_bruto_total:,.2f}")
        with col3:
            impostos_total = df_div_filtrado_origem.get("Impostos", pd.Series()).sum()
            st.metric("Impostos Totais", f"R$ {impostos_total:,.2f}")
        with col4:
            valor_liquido_total = df_div_filtrado_origem.get("Valor Líquido", pd.Series()).sum()
            st.metric("Valor Líquido Total", f"R$ {valor_liquido_total:,.2f}")
        
        st.markdown("---")
        
        # Filtros
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        
        with col_f1:
            if "Ativo" in df_div_filtrado_origem.columns:
                ativos = ["Todos"] + sorted([a for a in df_div_filtrado_origem["Ativo"].unique() if pd.notna(a)])
                ativos_sel = st.multiselect(
                    "Ativo",
                    ativos,
                    default=["Todos"],
                    key="div_ativo_app"
                )
                if "Todos" not in ativos_sel:
                    df_div_filtrado_origem = df_div_filtrado_origem[df_div_filtrado_origem["Ativo"].isin(ativos_sel)]
        
        with col_f2:
            if "Fonte" in df_div_filtrado_origem.columns:
                fontes = ["Todos"] + sorted([f for f in df_div_filtrado_origem["Fonte"].unique() if pd.notna(f)])
                fontes_sel = st.multiselect(
                    "Usuário",
                    fontes,
                    default=["Todos"],
                    key="div_fonte_app"
                )
                if "Todos" not in fontes_sel:
                    df_div_filtrado_origem = df_div_filtrado_origem[df_div_filtrado_origem["Fonte"].isin(fontes_sel)]
        
        with col_f3:
            if "Data" in df_div_filtrado_origem.columns:
                data_min = df_div_filtrado_origem["Data"].min()
                data_max = df_div_filtrado_origem["Data"].max()
                try:
                    data_range = st.date_input(
                        "Período",
                        value=(data_min.date() if pd.notna(data_min) else None, 
                               data_max.date() if pd.notna(data_max) else None),
                        key="div_data_app"
                    )
                    if len(data_range) == 2:
                        df_div_filtrado_origem = df_div_filtrado_origem[
                            (df_div_filtrado_origem["Data"].dt.date >= data_range[0]) &
                            (df_div_filtrado_origem["Data"].dt.date <= data_range[1])
                        ]
                except:
                    pass
        
        with col_f4:
            ordenacao = st.selectbox(
                "Ordenar por",
                ["Data (mais recente)", "Data (mais antigo)", "Valor Líquido (maior)", "Valor Líquido (menor)", "Ativo (A-Z)"],
                key="div_ordenacao_app"
            )
        
        # Aplicar ordenação
        if ordenacao == "Data (mais recente)":
            df_div_filtrado_origem = df_div_filtrado_origem.sort_values("Data", ascending=False)
        elif ordenacao == "Data (mais antigo)":
            df_div_filtrado_origem = df_div_filtrado_origem.sort_values("Data", ascending=True)
        elif ordenacao == "Valor Líquido (maior)":
            df_div_filtrado_origem = df_div_filtrado_origem.sort_values("Valor Líquido", ascending=False)
        elif ordenacao == "Valor Líquido (menor)":
            df_div_filtrado_origem = df_div_filtrado_origem.sort_values("Valor Líquido", ascending=True)
        elif ordenacao == "Ativo (A-Z)":
            df_div_filtrado_origem = df_div_filtrado_origem.sort_values("Ativo", ascending=True)
        
        # Exibir tabela
        st.subheader("📊 Dividendos")
        st.dataframe(df_div_filtrado_origem, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Gráficos de evolução
        st.subheader("📈 Evolução dos Proventos")
        gerar_graficos_evolucao(df_div_filtrado_origem, coluna_valor="Valor Líquido", coluna_data="Data", chave_periodo="periodo_div_consolidado")
        
        st.markdown("---")
        
        # Gráfico de top pagadores
        st.subheader("🏆 Maiores Pagadores")
        gerar_grafico_top_pagadores(df_div_filtrado_origem, coluna_ativo="Ativo", coluna_valor="Valor Líquido", coluna_data="Data", chave_prefixo="top_div_consolidado")


with tab_prov:
    st.header("💸 Proventos")
    df_prov = df_prov_raw.copy()
    
    if df_prov.empty:
        st.info("📭 Nenhum provento disponível.")
    else:
        # Padronizar Data
        if "Mês/Ano" in df_prov.columns:
            df_prov["Data"] = pd.to_datetime(df_prov["Mês/Ano"], format="%m/%Y", errors="coerce")
        elif "Data" not in df_prov.columns:
            df_prov["Data"] = pd.NaT
        
        st.success(f"✅ {len(df_prov)} proventos registrados")
        
        # Métricas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total de Registros", len(df_prov))
        with col2:
            valor_bruto_total = df_prov.get("Valor Bruto", pd.Series()).sum()
            st.metric("Valor Bruto Total", f"R$ {valor_bruto_total:,.2f}")
        with col3:
            valor_liquido_total = df_prov.get("Valor Líquido", pd.Series()).sum()
            st.metric("Valor Líquido Total", f"R$ {valor_liquido_total:,.2f}")
        
        st.markdown("---")
        
        # Filtros
        col_f1, col_f2, col_f3 = st.columns(3)
        
        with col_f1:
            if "Produto" in df_prov.columns:
                produtos = ["Todos"] + sorted([p for p in df_prov["Produto"].unique() if pd.notna(p)])
                produtos_sel = st.multiselect(
                    "Produto/Ativo",
                    produtos,
                    default=["Todos"],
                    key="prov_produto"
                )
                if "Todos" not in produtos_sel:
                    df_prov = df_prov[df_prov["Produto"].isin(produtos_sel)]
        
        with col_f2:
            if "Mês/Ano" in df_prov.columns:
                meses = ["Todos"] + sorted([m for m in df_prov["Mês/Ano"].unique() if pd.notna(m)])
                meses_sel = st.multiselect(
                    "Mês/Ano",
                    meses,
                    default=["Todos"],
                    key="prov_mes"
                )
                if "Todos" not in meses_sel:
                    df_prov = df_prov[df_prov["Mês/Ano"].isin(meses_sel)]
        
        with col_f3:
            ordenacao = st.selectbox(
                "Ordenar por",
                ["Mês/Ano (mais recente)", "Mês/Ano (mais antigo)", "Valor Líquido (maior)", "Valor Líquido (menor)"],
                key="prov_ordem"
            )
            
            if ordenacao == "Mês/Ano (mais recente)":
                df_prov = df_prov.sort_values("Data", ascending=False)
            elif ordenacao == "Mês/Ano (mais antigo)":
                df_prov = df_prov.sort_values("Data", ascending=True)
            elif ordenacao == "Valor Líquido (maior)":
                df_prov = df_prov.sort_values("Valor Líquido", ascending=False)
            elif ordenacao == "Valor Líquido (menor)":
                df_prov = df_prov.sort_values("Valor Líquido", ascending=True)
        
        st.markdown("---")
        st.subheader("📊 Proventos")
        st.dataframe(df_prov, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Gráficos de evolução
        st.subheader("📈 Evolução dos Proventos Recebidos")
        gerar_graficos_evolucao(df_prov, coluna_valor="Valor Líquido", coluna_data="Data", chave_periodo="periodo_prov")
        
        st.markdown("---")
        
        # Gráfico de top pagadores
        st.subheader("🏆 Maiores Pagadores")
        gerar_grafico_top_pagadores(df_prov, coluna_ativo="Produto", coluna_valor="Valor Líquido", coluna_data="Data", chave_prefixo="top_prov")

## As abas de Gráficos, Histórico e Comparações podem ser reimplementadas aqui se desejado, usando os novos DataFrames separados ou o consolidado.


# Aba Inserção Manual
with tab6:
    st.header("Inserção Manual de Investimentos")
    st.info("Funcionalidade em desenvolvimento.")
