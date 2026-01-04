import os
import streamlit as st
import pandas as pd
import plotly.express as px

from modules.usuarios import carregar_usuarios, salvar_usuarios
from modules.upload_relatorio import ACOES_PATH, RENDA_FIXA_PATH, PROVENTOS_PATH, padronizar_tabelas, padronizar_dividendos
from modules.avenue_views import aba_acoes_avenue, aba_proventos_avenue, padronizar_dividendos_avenue, carregar_dividendos_avenue, padronizar_acoes_avenue, carregar_acoes_avenue
from modules.cotacoes import converter_usd_para_brl

st.set_page_config(page_title="Invest - Controle de Investimentos", layout="wide")
st.title("💰 Invest - Controle de Investimentos")

# ========== FUNÇÕES AUXILIARES ==========

def carregar_df_parquet(path):
    if os.path.exists(path):
        try:
            return pd.read_parquet(path)
        except Exception:
            return pd.DataFrame()
    else:
        return pd.DataFrame()

def aplicar_filtros_padrao(df, chave_prefixo="filtro"):
    """Aplica filtros padrão: Mês/Ano, Usuário, Tipo"""
    if df.empty:
        return df
    
    # Obter opções de filtro
    meses = sorted(df["Mês/Ano"].dropna().unique()) if "Mês/Ano" in df.columns else []
    usuarios = sorted(df["Usuário"].dropna().unique()) if "Usuário" in df.columns else []
    tipos = sorted(df["Tipo"].dropna().unique()) if "Tipo" in df.columns else []
    
    # Criar filtros
    cols = st.columns(3)
    
    with cols[0]:
        mes_sel = st.selectbox("Mês/Ano", meses, index=len(meses)-1 if meses else 0, key=f"{chave_prefixo}_mes") if meses else None
    
    with cols[1]:
        usuarios_sel = st.multiselect("Usuário", usuarios, default=usuarios, key=f"{chave_prefixo}_user") if usuarios else []
    
    with cols[2]:
        if tipos and len(tipos) > 1:
            tipos_sel = st.multiselect("Tipo", tipos, default=tipos, key=f"{chave_prefixo}_tipo")
        else:
            tipos_sel = tipos
    
    # Aplicar filtros
    df_filtrado = df.copy()
    if mes_sel:
        df_filtrado = df_filtrado[df_filtrado["Mês/Ano"] == mes_sel]
    if usuarios_sel:
        df_filtrado = df_filtrado[df_filtrado["Usuário"].isin(usuarios_sel)]
    if tipos_sel:
        df_filtrado = df_filtrado[df_filtrado["Tipo"].isin(tipos_sel)]
    
    return df_filtrado

def exibir_metricas_valor(df, col_valor="Valor"):
    """Exibe métricas de valor total e por tipo"""
    if df.empty or col_valor not in df.columns:
        return
    
    # Valor total
    valor_total = df[col_valor].sum()
    st.metric("💰 Valor Total", f"R$ {valor_total:,.2f}")
    
    # Por tipo se disponível
    if "Tipo" in df.columns:
        tipos = df["Tipo"].unique()
        if len(tipos) > 1:
            st.markdown("---")
            st.subheader("Por Tipo")
            cols = st.columns(min(len(tipos), 4))
            for idx, tipo in enumerate(sorted(tipos)):
                with cols[idx % 4]:
                    valor_tipo = df[df["Tipo"] == tipo][col_valor].sum()
                    st.metric(tipo, f"R$ {valor_tipo:,.2f}")

def gerar_graficos_distribuicao(df, col_valor="Valor", cores="Blues", key_prefixo="dist"):
    """Gera gráficos de pizza e barras para distribuição"""
    if df.empty or "Tipo" not in df.columns:
        return
    
    st.markdown("---")
    st.subheader("📊 Distribuição")
    
    # Pizza por tipo
    dist_tipo = df.groupby("Tipo")[col_valor].sum()
    fig_pie = px.pie(
        names=dist_tipo.index,
        values=dist_tipo.values,
        title="Distribuição por Tipo",
        hole=0.3,
        color_discrete_sequence=getattr(px.colors.sequential, cores),
        labels={"names": "Tipo", "values": "Valor"}
    )
    fig_pie.update_traces(
        textinfo="label+percent+value",
        texttemplate="%{label}<br>R$%{value:,.2f} (%{percent})"
    )
    st.plotly_chart(fig_pie, use_container_width=True, key=f"{key_prefixo}_pie")
    
    # Barras top ativos
    if "Ativo" in df.columns:
        top_n = 10
        top_ativos = df.groupby("Ativo")[col_valor].sum().nlargest(top_n).sort_values(ascending=False)
        if not top_ativos.empty:
            st.subheader(f"🏆 Top {top_n} Ativos")
            fig_bar = px.bar(
                x=top_ativos.index,
                y=top_ativos.values,
                labels={"x": "Ativo", "y": "Valor (R$)"},
                text=[f"R$ {v:,.2f}" for v in top_ativos.values]
            )
            fig_bar.update_traces(textposition="outside")
            fig_bar.update_layout(yaxis_tickformat=",.2f")
            st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefixo}_bar")

def gerar_graficos_evolucao(df: pd.DataFrame, coluna_valor: str = "Valor Líquido", coluna_data: str = "Data", chave_periodo: str = "periodo"):
    """Gera gráficos de evolução de proventos (barras, linha e crescimento %)"""
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
            df_temp = df.copy()
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
            df_temp = df.copy()
            df_temp["semestre_ini"] = pd.to_datetime(df_temp[coluna_data].dt.year.astype(str) + "-" + ((df_temp[coluna_data].dt.month <= 6).map({True: '01', False: '07'})) + "-01")
            group = df_temp.groupby("semestre_ini")[coluna_valor].sum()
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

        # Gráfico de barras
        st.subheader("Gráfico de Barras - Valor Recebido")
        fig_bar = px.bar(
            x=df_group.index,
            y=df_group.values,
            labels={"x": "Período", "y": coluna_valor},
            text=[f"{v:,.2f}" for v in df_group.values]
        )
        fig_bar.update_traces(textposition="outside")
        fig_bar.update_layout(yaxis_tickformat=",.2f", xaxis_tickmode="array", xaxis_tickvals=list(df_group.index), xaxis_ticktext=list(df_group.index))
        st.plotly_chart(fig_bar, use_container_width=True, key=f"{chave_periodo}_bar")

        # Gráfico de linha
        st.subheader("Gráfico de Linha - Valor Recebido")
        fig_line = px.line(
            x=df_group.index,
            y=df_group.values,
            labels={"x": "Período", "y": coluna_valor},
            text=[f"{v:,.2f}" for v in df_group.values]
        )
        fig_line.update_traces(textposition="top center", mode="lines+markers+text")
        fig_line.update_layout(yaxis_tickformat=",.2f", xaxis_tickmode="array", xaxis_tickvals=list(df_group.index), xaxis_ticktext=list(df_group.index))
        st.plotly_chart(fig_line, use_container_width=True, key=f"{chave_periodo}_line")

        # Gráfico percentual
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
        st.plotly_chart(fig_pct, use_container_width=True, key=f"{chave_periodo}_pct")

        return True
    except Exception as e:
        st.error(f"Erro ao gerar gráficos: {e}")
        return False

def gerar_grafico_top_pagadores(df: pd.DataFrame, coluna_ativo: str = "Ativo", coluna_valor: str = "Valor Líquido", coluna_data: str = "Data", chave_prefixo: str = "top"):
    """Gera gráfico vertical com top pagadores de dividendos"""
    if df.empty or coluna_ativo not in df.columns or coluna_valor not in df.columns:
        return False
    
    # Garantir que Data é datetime
    if coluna_data in df.columns:
        df[coluna_data] = pd.to_datetime(df[coluna_data], errors="coerce")
    
    col_periodo, col_mes, col_top = st.columns(3)
    
    with col_periodo:
        tipo_periodo = st.selectbox("Período", ["Mensal", "Anual"], key=f"{chave_prefixo}_tipo_periodo")
    
    with col_mes:
        if tipo_periodo == "Mensal":
            periodos_disponiveis = sorted(df[coluna_data].dt.to_period("M").unique().astype(str))
            if periodos_disponiveis:
                periodo_sel = st.selectbox("Mês", periodos_disponiveis, index=len(periodos_disponiveis)-1, key=f"{chave_prefixo}_mes")
                df_filtrado = df[df[coluna_data].dt.to_period("M").astype(str) == periodo_sel]
            else:
                df_filtrado = df
        else:
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
        st.plotly_chart(fig_top, use_container_width=True, key=f"{chave_prefixo}_bar")

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

# ========== CARREGAR DADOS ==========

df_usuarios = carregar_usuarios()

# Dados brasileiros
df_acoes_raw = carregar_df_parquet(ACOES_PATH)
df_rf_raw = carregar_df_parquet(RENDA_FIXA_PATH)
df_prov_raw = carregar_df_parquet(PROVENTOS_PATH)
df_padronizado = padronizar_tabelas(df_acoes_raw, df_rf_raw)

# Dados Avenue
df_acoes_avenue_raw = carregar_acoes_avenue()
df_dividendos_avenue_raw = carregar_dividendos_avenue()

# Padronizar e converter Avenue
df_acoes_avenue_padrao = pd.DataFrame()
if not df_acoes_avenue_raw.empty:
    df_acoes_avenue_padrao = padronizar_acoes_avenue(df_acoes_avenue_raw)
    
    # Converter USD para BRL
    if "Valor de Mercado" in df_acoes_avenue_padrao.columns and "Mês/Ano" in df_acoes_avenue_padrao.columns:
        df_acoes_avenue_padrao["Valor de Mercado"] = df_acoes_avenue_padrao.apply(
            lambda row: converter_usd_para_brl(row["Valor de Mercado"], row["Mês/Ano"]) if pd.notna(row["Mês/Ano"]) else row["Valor de Mercado"],
            axis=1
        )
    if "Preço" in df_acoes_avenue_padrao.columns and "Mês/Ano" in df_acoes_avenue_padrao.columns:
        df_acoes_avenue_padrao["Preço"] = df_acoes_avenue_padrao.apply(
            lambda row: converter_usd_para_brl(row["Preço"], row["Mês/Ano"]) if pd.notna(row["Mês/Ano"]) else row["Preço"],
            axis=1
        )
    
    df_acoes_avenue_padrao["Tipo"] = "Ações Dólar"
    
    # Adicionar coluna "Valor" para compatibilidade com consolidação
    if "Valor de Mercado" in df_acoes_avenue_padrao.columns:
        df_acoes_avenue_padrao["Valor"] = df_acoes_avenue_padrao["Valor de Mercado"]
    
    for col in ["Mês/Ano", "Usuário"]:
        if col not in df_acoes_avenue_padrao.columns:
            df_acoes_avenue_padrao[col] = None

# Padronizar dividendos
df_dividendos_br = padronizar_dividendos(df_prov_raw)

# Extrair Usuário da coluna Fonte para dividendos BR
if not df_dividendos_br.empty and "Fonte" in df_dividendos_br.columns:
    df_dividendos_br["Usuário"] = df_dividendos_br["Fonte"].astype(str).str.replace(r"\s*\(\d{2}/\d{4}\)$", "", regex=True)
    df_dividendos_br["Usuário"] = df_dividendos_br["Usuário"].fillna("Não informado")

df_dividendos_avenue = padronizar_dividendos_avenue(df_dividendos_avenue_raw) if not df_dividendos_avenue_raw.empty else pd.DataFrame()

# Converter dividendos Avenue para BRL
if not df_dividendos_avenue.empty:
    for col_valor in ["Valor Bruto", "Impostos", "Valor Líquido"]:
        if col_valor in df_dividendos_avenue.columns and "Data" in df_dividendos_avenue.columns:
            df_dividendos_avenue[col_valor] = df_dividendos_avenue.apply(
                lambda row: converter_usd_para_brl(row[col_valor], f"{row['Data'].month:02d}/{row['Data'].year}") 
                if pd.notna(row["Data"]) and pd.notna(row[col_valor]) else row[col_valor],
                axis=1
            )

# Consolidar dividendos com coluna "Fonte Provento"
def preparar_dividendos_consolidado(df, fonte_nome):
    if df.empty:
        return pd.DataFrame()
    df = df.copy()
    
    # Extrair Usuário da coluna Fonte removendo padrão (MM/YYYY)
    if "Fonte" in df.columns:
        df["Usuário"] = df["Fonte"].astype(str).str.replace(r"\s*\(\d{2}/\d{4}\)$", "", regex=True)
    elif "Usuário" not in df.columns:
        df["Usuário"] = None
    
    df["Usuário"] = df["Usuário"].fillna("Não informado")
    
    # Adicionar coluna Fonte Provento
    df["Fonte Provento"] = fonte_nome
    
    # Normalizar Data
    if "Data" in df.columns:
        df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
    
    return df

df_dividendos_br_cons = preparar_dividendos_consolidado(df_dividendos_br, "Proventos Gerais")
df_dividendos_avenue_cons = preparar_dividendos_consolidado(df_dividendos_avenue, "Proventos Avenue")
df_dividendos_consolidado = pd.concat([df_dividendos_br_cons, df_dividendos_avenue_cons], ignore_index=True)

# Separar por tipo
df_acoes_br = df_padronizado[df_padronizado["Tipo"] == "Ações"].copy() if not df_padronizado.empty else pd.DataFrame()
df_renda_fixa = df_padronizado[df_padronizado["Tipo"] == "Renda Fixa"].copy() if not df_padronizado.empty else pd.DataFrame()
df_tesouro = df_padronizado[df_padronizado["Tipo"] == "Tesouro Direto"].copy() if not df_padronizado.empty else pd.DataFrame()

# ========== INTERFACE COM TABS REORGANIZADAS ==========

tab_acoes, tab_renda_fixa, tab_proventos, tab_outros = st.tabs([
    "📈 Ações",
    "💵 Renda Fixa",
    "💸 Proventos",
    "⚙️ Outros"
])

# ============ TAB AÇÕES ============
with tab_acoes:
    subtab_br, subtab_dolar, subtab_consolidadas = st.tabs([
        "Ações BR",
        "Ações Dólar (Avenue)",
        "Ações Consolidadas"
    ])
    
    # --- Ações BR ---
    with subtab_br:
        st.header("📊 Ações Brasil")
        
        if df_acoes_br.empty:
            st.info("Sem dados de Ações Brasil")
        else:
            df_view = aplicar_filtros_padrao(df_acoes_br, "acoes_br")
            exibir_metricas_valor(df_view)
            
            with st.expander("📋 Ver Tabela Completa", expanded=False):
                st.dataframe(df_view, use_container_width=True)
            
            gerar_graficos_distribuicao(df_view, cores="Blues", key_prefixo="acoes_br")
    
    # --- Ações Dólar ---
    with subtab_dolar:
        aba_acoes_avenue()
    
    # --- Ações Consolidadas ---
    with subtab_consolidadas:
        st.header("🌎 Ações Consolidadas")
        
        # Combinar ações BR e Dólar
        df_acoes_todas = pd.DataFrame()
        if not df_acoes_br.empty and not df_acoes_avenue_padrao.empty:
            colunas_comuns = list(set(df_acoes_br.columns) & set(df_acoes_avenue_padrao.columns))
            df_acoes_todas = pd.concat(
                [df_acoes_br[colunas_comuns], df_acoes_avenue_padrao[colunas_comuns]],
                ignore_index=True
            )
        elif not df_acoes_br.empty:
            df_acoes_todas = df_acoes_br.copy()
        elif not df_acoes_avenue_padrao.empty:
            df_acoes_todas = df_acoes_avenue_padrao.copy()
        
        if df_acoes_todas.empty:
            st.info("Sem dados de Ações")
        else:
            df_view = aplicar_filtros_padrao(df_acoes_todas, "acoes_cons")
            exibir_metricas_valor(df_view)
            
            with st.expander("📋 Ver Tabela Completa", expanded=False):
                st.dataframe(df_view, use_container_width=True)
            
            gerar_graficos_distribuicao(df_view, cores="RdBu", key_prefixo="acoes_cons")

# ============ TAB RENDA FIXA ============
with tab_renda_fixa:
    subtab_rf, subtab_td, subtab_rf_cons = st.tabs([
        "Renda Fixa",
        "Tesouro Direto",
        "Renda Fixa Consolidada"
    ])
    
    # --- Renda Fixa ---
    with subtab_rf:
        st.header("💵 Renda Fixa")
        
        if df_renda_fixa.empty:
            st.info("Sem dados de Renda Fixa")
        else:
            df_view = aplicar_filtros_padrao(df_renda_fixa, "rf")
            exibir_metricas_valor(df_view)
            
            with st.expander("📋 Ver Tabela Completa", expanded=False):
                st.dataframe(df_view, use_container_width=True)
            
            gerar_graficos_distribuicao(df_view, cores="Greens", key_prefixo="rf")
    
    # --- Tesouro Direto ---
    with subtab_td:
        st.header("💰 Tesouro Direto")
        
        if df_tesouro.empty:
            st.info("Sem dados de Tesouro Direto")
        else:
            df_view = aplicar_filtros_padrao(df_tesouro, "td")
            exibir_metricas_valor(df_view)
            
            with st.expander("📋 Ver Tabela Completa", expanded=False):
                st.dataframe(df_view, use_container_width=True)
            
            gerar_graficos_distribuicao(df_view, cores="Oranges", key_prefixo="td")
    
    # --- Renda Fixa Consolidada ---
    with subtab_rf_cons:
        st.header("🏛️ Renda Fixa Consolidada")
        
        # Combinar RF e TD
        df_rf_todas = pd.DataFrame()
        if not df_renda_fixa.empty and not df_tesouro.empty:
            df_rf_todas = pd.concat([df_renda_fixa, df_tesouro], ignore_index=True)
        elif not df_renda_fixa.empty:
            df_rf_todas = df_renda_fixa.copy()
        elif not df_tesouro.empty:
            df_rf_todas = df_tesouro.copy()
        
        if df_rf_todas.empty:
            st.info("Sem dados de Renda Fixa ou Tesouro Direto")
        else:
            df_view = aplicar_filtros_padrao(df_rf_todas, "rf_cons")
            exibir_metricas_valor(df_view)
            
            with st.expander("📋 Ver Tabela Completa", expanded=False):
                st.dataframe(df_view, use_container_width=True)
            
            gerar_graficos_distribuicao(df_view, cores="Greens", key_prefixo="rf_cons")

# ============ TAB PROVENTOS ============
with tab_proventos:
    subtab_div_br, subtab_div_av, subtab_div_cons = st.tabs([
        "Dividendos BR",
        "Dividendos Avenue",
        "Dividendos Consolidados"
    ])
    
    # --- Dividendos BR ---
    with subtab_div_br:
        st.header("💸 Dividendos Brasil")
        
        if df_dividendos_br.empty:
            st.info("Sem dados de Dividendos Brasil")
        else:
            st.success(f"✅ {len(df_dividendos_br)} registros")
            
            # Métricas
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Valor Bruto", f"R$ {df_dividendos_br.get('Valor Bruto', pd.Series()).sum():,.2f}")
            with col2:
                st.metric("Impostos", f"R$ {df_dividendos_br.get('Impostos', pd.Series()).sum():,.2f}")
            with col3:
                st.metric("Valor Líquido", f"R$ {df_dividendos_br.get('Valor Líquido', pd.Series()).sum():,.2f}")
            
            with st.expander("📋 Ver Tabela Completa", expanded=False):
                st.dataframe(df_dividendos_br, use_container_width=True)
            
            # Gráficos de evolução
            st.markdown("---")
            gerar_graficos_evolucao(df_dividendos_br, coluna_valor="Valor Líquido", coluna_data="Data", chave_periodo="periodo_div_br")
            
            # Gráfico de top pagadores
            st.markdown("---")
            gerar_grafico_top_pagadores(df_dividendos_br, coluna_ativo="Ativo", coluna_valor="Valor Líquido", coluna_data="Data", chave_prefixo="top_div_br")
    
    # --- Dividendos Avenue ---
    with subtab_div_av:
        aba_proventos_avenue()
    
    # --- Dividendos Consolidados ---
    with subtab_div_cons:
        st.header("💰 Dividendos Consolidados")
        
        if df_dividendos_consolidado.empty:
            st.info("Sem dados de Dividendos")
        else:
            st.success(f"✅ {len(df_dividendos_consolidado)} registros")
            
            # Métricas
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Registros", len(df_dividendos_consolidado))
            with col2:
                st.metric("Valor Bruto", f"R$ {df_dividendos_consolidado.get('Valor Bruto', pd.Series()).sum():,.2f}")
            with col3:
                st.metric("Impostos", f"R$ {df_dividendos_consolidado.get('Impostos', pd.Series()).sum():,.2f}")
            with col4:
                st.metric("Valor Líquido", f"R$ {df_dividendos_consolidado.get('Valor Líquido', pd.Series()).sum():,.2f}")
            
            st.markdown("---")
            
            # Filtros
            col_f1, col_f2, col_f3 = st.columns(3)
            
            df_filtrado = df_dividendos_consolidado.copy()
            
            with col_f1:
                if "Fonte Provento" in df_filtrado.columns:
                    fontes = sorted(df_filtrado["Fonte Provento"].dropna().unique())
                    fontes_sel = st.multiselect("Fonte", fontes, default=fontes, key="div_cons_fonte")
                    if fontes_sel:
                        df_filtrado = df_filtrado[df_filtrado["Fonte Provento"].isin(fontes_sel)]
            
            with col_f2:
                if "Usuário" in df_filtrado.columns:
                    usuarios = sorted(df_filtrado["Usuário"].dropna().unique())
                    usuarios_sel = st.multiselect("Usuário", usuarios, default=usuarios, key="div_cons_user")
                    if usuarios_sel:
                        df_filtrado = df_filtrado[df_filtrado["Usuário"].isin(usuarios_sel)]
            
            with col_f3:
                if "Ativo" in df_filtrado.columns:
                    ativos = sorted(df_filtrado["Ativo"].dropna().unique())
                    if len(ativos) > 0:
                        ativos_sel = st.multiselect("Ativo", ativos, key="div_cons_ativo")
                        if ativos_sel:
                            df_filtrado = df_filtrado[df_filtrado["Ativo"].isin(ativos_sel)]
            
            with st.expander("📋 Ver Tabela Completa", expanded=False):
                # Remover coluna Fonte da exibição
                colunas_exibir = [col for col in df_filtrado.columns if col != "Fonte"]
                st.dataframe(df_filtrado[colunas_exibir], use_container_width=True)
            
            # Gráfico por fonte
            if "Fonte Provento" in df_filtrado.columns:
                st.markdown("---")
                st.subheader("📊 Distribuição por Fonte")
                dist_fonte = df_filtrado.groupby("Fonte Provento")["Valor Líquido"].sum()
                fig_pie_fonte = px.pie(
                    names=dist_fonte.index,
                    values=dist_fonte.values,
                    title="Distribuição por Fonte",
                    hole=0.3,
                    labels={"names": "Fonte", "values": "Valor Líquido"}
                )
                fig_pie_fonte.update_traces(
                    textinfo="label+percent+value",
                    texttemplate="%{label}<br>R$%{value:,.2f} (%{percent})"
                )
                st.plotly_chart(fig_pie_fonte, use_container_width=True, key="div_cons_pie_fonte")
            
            # Gráficos de evolução
            st.markdown("---")
            gerar_graficos_evolucao(df_filtrado, coluna_valor="Valor Líquido", coluna_data="Data", chave_periodo="periodo_div_cons")
            
            # Gráfico de top pagadores
            st.markdown("---")
            gerar_grafico_top_pagadores(df_filtrado, coluna_ativo="Ativo", coluna_valor="Valor Líquido", coluna_data="Data", chave_prefixo="top_div_cons")

# ============ TAB OUTROS ============
with tab_outros:
    subtab_cadastro, subtab_insercao, subtab_doc = st.tabs([
        "👤 Cadastro",
        "📝 Inserção Manual",
        "📚 Documentação"
    ])
    
    # --- Cadastro ---
    with subtab_cadastro:
        st.header("👤 Cadastro de Usuários")
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
    
    # --- Inserção Manual ---
    with subtab_insercao:
        st.header("📝 Inserção Manual de Investimentos")
        st.info("Funcionalidade em desenvolvimento.")
    
    # --- Documentação ---
    with subtab_doc:
        st.info("A documentação completa do sistema está disponível na página 'Documentação' do menu lateral.")
