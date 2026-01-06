import os
import json
from datetime import datetime
from io import BytesIO
import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from modules.ticker_info import CACHE_PATH as TICKER_INFO_PATH

from modules.usuarios import carregar_usuarios, salvar_usuarios
from modules.upload_relatorio import ACOES_PATH, RENDA_FIXA_PATH, PROVENTOS_PATH, padronizar_tabelas, padronizar_dividendos
from modules.avenue_views import aba_acoes_avenue, aba_proventos_avenue, padronizar_dividendos_avenue, carregar_dividendos_avenue, padronizar_acoes_avenue, carregar_acoes_avenue
from modules.cotacoes import converter_usd_para_brl, obter_historico_indice
from modules.posicao_atual import preparar_posicao_base, atualizar_cotacoes, dataframe_para_excel_bytes, preparar_tabela_posicao_estilizada
from modules.investimentos_manuais import (
    carregar_caixa,
    registrar_caixa,
    carregar_acoes as carregar_acoes_man,
    registrar_acao_manual,
    caixa_para_dividendos,
    acoes_para_consolidado,
    dataframe_para_excel_bytes as df_manual_para_excel,
)

@st.cache_data(show_spinner=False)
def carregar_cache_ticker_info():
    if os.path.exists(TICKER_INFO_PATH):
        try:
            df = pd.read_parquet(TICKER_INFO_PATH)
            if not df.empty and "Ticker" in df.columns:
                return df
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

st.set_page_config(page_title="Invest - Controle de Investimentos", layout="wide")
st.title("💰 Invest - Controle de Investimentos")

# ========== FUNÇÕES AUXILIARES ==========

@st.cache_data(show_spinner=False)
def _read_parquet_cached(path: str, mtime: float):
    return pd.read_parquet(path)

def carregar_df_parquet(path):
    if os.path.exists(path):
        try:
            mtime = os.path.getmtime(path)
            return _read_parquet_cached(path, mtime)
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
        usuarios_opcoes = ["Todos"] + usuarios if usuarios else []
        usuarios_sel = st.multiselect(
            "Usuário",
            usuarios_opcoes,
            default=["Todos"] if usuarios else [],
            key=f"{chave_prefixo}_user"
        ) if usuarios else []
        # Se "Todos" está selecionado, seleciona todos
        if "Todos" in usuarios_sel:
            usuarios_sel = usuarios
    
    with cols[2]:
        if tipos and len(tipos) > 1:
            tipos_opcoes = ["Todos"] + tipos
            tipos_sel = st.multiselect(
                "Tipo",
                tipos_opcoes,
                default=["Todos"] if tipos else [],
                key=f"{chave_prefixo}_tipo"
            )
            if "Todos" in tipos_sel:
                tipos_sel = tipos
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
    

    col_pie1, col_pie2 = st.columns(2)

    with col_pie1:
        st.markdown("<div style='display:flex;align-items:center;gap:0.5em;'><h5 style='margin-bottom:0;margin-top:0;'>Distribuição por Tipo</h5></div>", unsafe_allow_html=True)
        dist_tipo = df.groupby("Tipo")[col_valor].sum()
        fig_pie = px.pie(
            names=dist_tipo.index,
            values=dist_tipo.values,
            hole=0.3,
            color_discrete_sequence=getattr(px.colors.sequential, cores),
            labels={"names": "Tipo", "values": "Valor"}
        )
        fig_pie.update_traces(
            textinfo="label+percent+value",
            texttemplate="%{label}<br>R$%{value:,.2f} (%{percent})"
        )
        fig_pie.update_layout(
            legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center"),
        )
        st.plotly_chart(fig_pie, use_container_width=True, key=f"{key_prefixo}_pie")

    with col_pie2:
        opcoes_dim = []
        if "Setor" in df.columns:
            opcoes_dim.append("Setor")
        if "Segmento" in df.columns:
            opcoes_dim.append("Segmento")
        if opcoes_dim:
            col_tit, col_filtro = st.columns([2,2])
            with col_tit:
                st.markdown("<div style='display:flex;align-items:center;gap:0.5em;'><h5 style='margin-bottom:0;margin-top:0;'>Distribuição por</h5></div>", unsafe_allow_html=True)
            with col_filtro:
                dim_sel = st.radio("", opcoes_dim, horizontal=True, key=f"{key_prefixo}_dim")
            dist_dim = df.groupby(dim_sel)[col_valor].sum()
            dist_dim = dist_dim[dist_dim > 0]
            if not dist_dim.empty:
                fig_pie_dim = px.pie(
                    names=dist_dim.index,
                    values=dist_dim.values,
                    hole=0.3,
                    labels={"names": dim_sel, "values": "Valor"}
                )
                fig_pie_dim.update_layout(
                    legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center"),
                    margin=dict(t=40)
                )
                fig_pie_dim.update_traces(textinfo="label+percent", texttemplate="%{label}<br>%{percent}")
                st.plotly_chart(fig_pie_dim, use_container_width=True, key=f"{key_prefixo}_pie_dim")
            else:
                st.info(f"Sem dados para {dim_sel}.")
    
    # Barras top ativos
    eixo_categoria = "Ticker" if "Ticker" in df.columns else "Ativo"
    eixo_hover = "Ativo" if "Ativo" in df.columns else eixo_categoria

    if eixo_categoria in df.columns:
        opcoes_top_dist = ["Top 10", "Top 15", "Top 20", "Top 30", "Todos"]
        top_sel_dist = st.selectbox(f"Quantidade ({eixo_categoria})", opcoes_top_dist, index=0, key=f"{key_prefixo}_top_dist")
        top_n = int(top_sel_dist.split()[1]) if top_sel_dist != "Todos" else None
        
        top_ativos = df.groupby(eixo_categoria)[col_valor].sum().sort_values(ascending=False)
        if top_n:
            top_ativos = top_ativos.head(top_n)
        
        if not top_ativos.empty:
            titulo_dist = f"Top {top_n}" if top_n else "Todos"
            st.subheader(f"🏆 {titulo_dist} {eixo_categoria}")
            max_val = top_ativos.values.max() if len(top_ativos.values) else 0
            tickers_x = [extrair_ticker(a) or str(a) for a in top_ativos.index] if eixo_categoria == "Ativo" else list(top_ativos.index)
            from plotly.colors import sample_colorscale
            blues = px.colors.sequential.Blues  # maior = azul escuro
            n = len(top_ativos)
            valores = np.array(top_ativos.values)
            norm = (valores - valores.min()) / (valores.max() - valores.min()) if valores.max() > valores.min() else np.full(n, 0.5)
            bar_colors = sample_colorscale(blues[::-1], norm)
            fig_bar = px.bar(
                x=tickers_x,
                y=top_ativos.values,
                labels={"x": eixo_categoria, "y": "Valor (R$)"},
                text=[f"R$ {v:,.2f}" for v in top_ativos.values],
                color_discrete_sequence=bar_colors
            )
            fig_bar.update_traces(
                textposition="outside",
                cliponaxis=False,
                customdata=list(top_ativos.index),
                hovertemplate=f"<b>%{{customdata}}</b><br>{eixo_categoria}: %{{x}}<br>Valor: R$ %{{y:,.2f}}<extra></extra>",
                marker_color=bar_colors
            )
            fig_bar.update_layout(yaxis_tickformat=",.2f", margin=dict(t=60))
            if max_val > 0:
                fig_bar.update_yaxes(range=[0, max_val * 1.15])
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
        max_val = df_group.values.max() if len(df_group.values) else 0
        from plotly.colors import sample_colorscale
        blues = px.colors.sequential.Blues[::-1]
        n = len(df_group)
        valores = np.array(df_group.values)
        norm = (valores - valores.min()) / (valores.max() - valores.min()) if valores.max() > valores.min() else np.full(n, 0.5)
        bar_colors = sample_colorscale(blues, norm)
        fig_bar = px.bar(
            x=df_group.index,
            y=df_group.values,
            labels={"x": "Período", "y": coluna_valor},
            text=[f"{v:,.2f}" for v in df_group.values],
            color_discrete_sequence=bar_colors
        )
        fig_bar.update_traces(textposition="outside", cliponaxis=False, marker_color=bar_colors)
        fig_bar.update_layout(yaxis_tickformat=",.2f", xaxis_tickmode="array", xaxis_tickvals=list(df_group.index), xaxis_ticktext=list(df_group.index), margin=dict(t=60))
        if max_val > 0:
            fig_bar.update_yaxes(range=[0, max_val * 1.15])
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
        opcoes_top = ["Top 10", "Top 15", "Top 20", "Top 30", "Todos"]
        top_sel = st.selectbox("Quantidade", opcoes_top, index=0, key=f"{chave_prefixo}_quantidade")
        top_num = int(top_sel.split()[1]) if top_sel != "Todos" else None
    
    try:
        eixo_categoria = "Ticker" if "Ticker" in df_filtrado.columns else coluna_ativo
        top_ativos = df_filtrado.groupby(eixo_categoria)[coluna_valor].sum().sort_values(ascending=False)
        if top_num:
            top_ativos = top_ativos.head(top_num)

        titulo_top = f"Top {top_num}" if top_num else "Todos"
        st.subheader(f"{titulo_top} Maiores Pagadores - {tipo_periodo}")
        max_val = top_ativos.values.max() if len(top_ativos.values) else 0
        tickers_x = list(top_ativos.index)
        from plotly.colors import sample_colorscale
        blues = px.colors.sequential.Blues[::-1]
        n = len(top_ativos)
        valores = np.array(top_ativos.values)
        norm = (valores - valores.min()) / (valores.max() - valores.min()) if valores.max() > valores.min() else np.full(n, 0.5)
        bar_colors = sample_colorscale(blues, norm)
        fig_top = px.bar(
            x=tickers_x,
            y=top_ativos.values,
            labels={"x": eixo_categoria, "y": coluna_valor},
            text=[f"{v:,.2f}" for v in top_ativos.values],
            color_discrete_sequence=bar_colors
        )
        fig_top.update_traces(
            textposition="outside",
            cliponaxis=False,
            customdata=list(top_ativos.index),
            hovertemplate=f"<b>%{{customdata}}</b><br>{eixo_categoria}: %{{x}}<br>Valor: %{{y:,.2f}}<extra></extra>",
            marker_color=bar_colors
        )
        fig_top.update_layout(yaxis_tickformat=",.2f", margin=dict(t=60))
        if max_val > 0:
            fig_top.update_yaxes(range=[0, max_val * 1.15])
        st.plotly_chart(fig_top, use_container_width=True, key=f"{chave_prefixo}_bar")

        st.subheader(f"Detalhes - {titulo_top}")
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

# Dados manuais (caixa e ações)
df_manual_caixa = carregar_caixa()
df_manual_acoes = carregar_acoes_man()
df_dividendos_caixa = caixa_para_dividendos(df_manual_caixa)

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


def extrair_ticker(valor):
    """Extrai um ticker curto de strings do tipo 'BBAS3 - Banco do Brasil'."""
    if pd.isna(valor):
        return None
    texto = str(valor).strip()
    if not texto:
        return None
    if " - " in texto:
        return texto.split(" - ", 1)[0].strip()
    return texto.split()[0].strip()


def ticker_para_yf(ticker):
    """Normaliza ticker para o formato aceito pelo yfinance."""
    if not ticker:
        return None
    t = str(ticker).strip().upper()
    if "." in t:
        return t
    if t[-1:].isdigit():  # convenção B3
        return f"{t}.SA"
    return t


@st.cache_data(show_spinner=False)
def exibir_tabela_info_tickers(df, titulo="📄 Ticker / Setor / Fundamentais (yfinance)"):
    """Exibe tabela com tickers padronizados e informações de setor/fundamentos via yfinance."""
    if df.empty:
        return

    tickers = []
    if "Ticker" in df.columns:
        tickers = df["Ticker"].dropna().astype(str).str.strip().unique().tolist()
    elif "Ativo" in df.columns:
        tickers = df["Ativo"].dropna().astype(str).apply(extrair_ticker).dropna().unique().tolist()
    tickers = sorted({t for t in tickers if t})
    if not tickers:
        return

    cache_df = carregar_cache_ticker_info()
    if cache_df.empty:
        return

    base = pd.DataFrame({"Ticker": tickers})
    cols = [c for c in ["Ticker", "Setor", "Segmento", "Ticker_YF", "QuoteType"] if c in cache_df.columns]
    out = base.merge(cache_df[cols], on="Ticker", how="left")
    st.subheader(titulo)
    st.dataframe(out, use_container_width=True, hide_index=True)


def enriquecer_com_setor_segmento(df):
    """Adiciona colunas Setor e Segmento a partir do cache local (parquet)."""
    if df.empty:
        return df

    df_work = df.copy()
    if "Ticker" not in df_work.columns:
        if "Ativo" in df_work.columns:
            df_work["Ticker"] = df_work["Ativo"].apply(extrair_ticker)
        else:
            if "Tipo" in df_work.columns:
                df_work["Setor"] = df_work.get("Setor", df_work["Tipo"])
                df_work["Segmento"] = df_work.get("Segmento", df_work["Tipo"])
            return df_work

    tickers_curto = df_work["Ticker"].dropna().astype(str).str.strip().unique().tolist()
    tickers_curto = sorted({t for t in tickers_curto if t})
    if not tickers_curto:
        df_out = df_work.copy()
        df_out["Setor"] = df_out.get("Setor", df_out.get("Tipo"))
        df_out["Segmento"] = df_out.get("Segmento", df_out.get("Tipo"))
        return df_out

    cache_df = carregar_cache_ticker_info()
    cache_map = cache_df.set_index("Ticker").to_dict(orient="index") if (not cache_df.empty and "Ticker" in cache_df.columns) else {}

    df_out = df_work.copy()
    df_out["Setor"] = df_out.get("Setor") if "Setor" in df_out.columns else df_out["Ticker"].map(lambda t: cache_map.get(str(t).strip(), {}).get("Setor"))
    df_out["Segmento"] = df_out.get("Segmento") if "Segmento" in df_out.columns else df_out["Ticker"].map(lambda t: cache_map.get(str(t).strip(), {}).get("Segmento"))

    # Preencher vazios (inclui renda fixa) com o próprio Tipo para não ficar em branco
    if "Tipo" in df_out.columns:
        df_out["Setor"] = df_out["Setor"].fillna(df_out["Tipo"])
        df_out["Segmento"] = df_out["Segmento"].fillna(df_out["Tipo"])

    return df_out

df_dividendos_br_cons = preparar_dividendos_consolidado(df_dividendos_br, "Proventos Gerais")
df_dividendos_avenue_cons = preparar_dividendos_consolidado(df_dividendos_avenue, "Proventos Avenue")
df_dividendos_caixa_cons = preparar_dividendos_consolidado(df_dividendos_caixa, "Manual Caixa")
df_dividendos_consolidado = pd.concat([df_dividendos_br_cons, df_dividendos_avenue_cons, df_dividendos_caixa_cons], ignore_index=True)

# Separar por tipo
df_acoes_br = df_padronizado[df_padronizado["Tipo"] == "Ações"].copy() if not df_padronizado.empty else pd.DataFrame()
df_renda_fixa = df_padronizado[df_padronizado["Tipo"] == "Renda Fixa"].copy() if not df_padronizado.empty else pd.DataFrame()
df_tesouro = df_padronizado[df_padronizado["Tipo"] == "Tesouro Direto"].copy() if not df_padronizado.empty else pd.DataFrame()

# ========== INTERFACE COM TABS REORGANIZADAS ==========

tab_acoes, tab_renda_fixa, tab_proventos, tab_consolidacao, tab_posicao, tab_outros = st.tabs([
    "📈 Ações",
    "💵 Renda Fixa",
    "💸 Proventos",
    "📊 Consolidação",
    "📌 Posição Atual",
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
            df_view = enriquecer_com_setor_segmento(df_view)
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
            df_view = enriquecer_com_setor_segmento(df_view)
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
            df_view = enriquecer_com_setor_segmento(df_view)
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
            df_view = enriquecer_com_setor_segmento(df_view)
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
            df_view = enriquecer_com_setor_segmento(df_view)
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
                        if "Todos" in usuarios_sel:
                            usuarios_sel = usuarios
                        df_filtrado = df_filtrado[df_filtrado["Usuário"].isin(usuarios_sel)]
            
            with col_f3:
                if "Ativo" in df_filtrado.columns:
                    ativos = sorted(df_filtrado["Ativo"].dropna().unique())
                    if len(ativos) > 0:
                        ativos_opcoes = ["Todos"] + ativos
                        ativos_sel = st.multiselect("Ativo", ativos_opcoes, default=["Todos"], key="div_cons_ativo")
                        if ativos_sel:
                            if "Todos" in ativos_sel:
                                ativos_sel = ativos
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

# ============ TAB CONSOLIDAÇÃO ============
with tab_consolidacao:
    st.header("📊 Consolidação Geral")

    subtab_investimento, subtab_rentabilidade = st.tabs([
        "💼 Investimento",
        "📈 Rentabilidade",
    ])

    frames_consolidados = []
    if not df_padronizado.empty:
        frames_consolidados.append(df_padronizado.copy())
    if not df_acoes_avenue_padrao.empty:
        frames_consolidados.append(df_acoes_avenue_padrao.copy())

    df_consolidado_geral = pd.concat(frames_consolidados, ignore_index=True) if frames_consolidados else pd.DataFrame()

    with subtab_investimento:
        if df_consolidado_geral.empty:
            st.info("Sem dados para consolidação.")
        else:
            if "Valor" not in df_consolidado_geral.columns:
                if "Valor de Mercado" in df_consolidado_geral.columns:
                    df_consolidado_geral["Valor"] = df_consolidado_geral["Valor de Mercado"]
            df_view = aplicar_filtros_padrao(df_consolidado_geral, "cons_geral")
            df_view_enriquecido = enriquecer_com_setor_segmento(df_view)
            exibir_metricas_valor(df_view_enriquecido)

            with st.expander("📋 Ver Tabela Completa", expanded=False):
                st.dataframe(df_view_enriquecido, use_container_width=True)

            gerar_graficos_distribuicao(df_view_enriquecido, cores="Purples", key_prefixo="cons_geral")
            exibir_tabela_info_tickers(df_view_enriquecido)

    with subtab_rentabilidade:
        st.subheader("📈 Rentabilidade (sem aportes)")

        RENTAB_PARQUET_PATH = "data/rentabilidade_base.parquet"
        RENTAB_META_PATH = "data/rentabilidade_base_meta.json"

        def _norm_key(valor) -> str:
            if pd.isna(valor):
                return ""
            txt = str(valor).strip()
            if not txt:
                return ""
            if " - " in txt:
                txt = txt.split(" - ", 1)[0].strip()
            return txt.upper()

        def _parse_num_misto(valor):
            """Parse numérico tolerante (pt-BR e US), sem destruir strings com milhar."""
            if pd.isna(valor):
                return np.nan
            if isinstance(valor, (int, float, np.integer, np.floating)):
                try:
                    return float(valor)
                except Exception:
                    return np.nan
            txt = str(valor).strip()
            if not txt:
                return np.nan
            # remove símbolos comuns
            txt = txt.replace("R$", "").replace("US$", "").replace("$", "")
            txt = txt.replace("%", "").replace("\u00a0", " ")
            txt = txt.replace(" ", "")
            # parênteses para negativo
            negativo = False
            if txt.startswith("(") and txt.endswith(")"):
                negativo = True
                txt = txt[1:-1]
            # sinais
            if txt.startswith("+"):
                txt = txt[1:]
            elif txt.startswith("-"):
                negativo = True
                txt = txt[1:]

            if not txt:
                return np.nan

            # Se tem "." e ",": assume pt-BR (milhar "." e decimal ",")
            if "." in txt and "," in txt:
                txt_norm = txt.replace(".", "").replace(",", ".")
            # Só vírgula: assume decimal
            elif "," in txt:
                txt_norm = txt.replace(".", "").replace(",", ".")
            # Só ponto: pode ser decimal ou milhar
            elif "." in txt:
                partes = txt.split(".")
                # Ex.: 14.000 (milhar) / 1.234.567
                if len(partes) > 2:
                    txt_norm = "".join(partes)
                else:
                    # uma ocorrência: se exatamente 3 dígitos após ponto, tratar como milhar
                    if len(partes) == 2 and len(partes[1]) == 3 and partes[0].isdigit() and partes[1].isdigit():
                        txt_norm = "".join(partes)
                    else:
                        txt_norm = txt
            else:
                txt_norm = txt

            try:
                num = float(txt_norm)
                return -num if negativo else num
            except Exception:
                return np.nan

        def _parse_mes_ano_to_periodo(mes_ano) -> pd.Period | None:
            if pd.isna(mes_ano):
                return None
            txt = str(mes_ano).strip()
            if not txt:
                return None
            try:
                mm, yyyy = txt.split("/")
                return pd.Period(f"{int(yyyy):04d}-{int(mm):02d}", freq="M")
            except Exception:
                return None

        def _periodo_to_label(p: pd.Period) -> str:
            try:
                return p.strftime("%m/%Y")
            except Exception:
                return str(p)

        def _to_periodo_end(freq: str, p: pd.Period) -> tuple[pd.Period, str]:
            if freq == "Mensal":
                return p, _periodo_to_label(p)

            if freq == "Anual":
                end_p = pd.Period(f"{p.year:04d}-12", freq="M")
                return end_p, "12/" + str(p.year)

            if freq == "Bimestral":
                bloco = ((p.month - 1) // 2) + 1
                end_month = bloco * 2
                end_p = pd.Period(f"{p.year:04d}-{end_month:02d}", freq="M")
                return end_p, f"{end_month:02d}/{p.year}"

            if freq == "Trimestral":
                bloco = ((p.month - 1) // 3) + 1
                end_month = bloco * 3
                end_p = pd.Period(f"{p.year:04d}-{end_month:02d}", freq="M")
                return end_p, f"{end_month:02d}/{p.year}"

            if freq == "Semestral":
                bloco = ((p.month - 1) // 6) + 1
                end_month = bloco * 6
                end_p = pd.Period(f"{p.year:04d}-{end_month:02d}", freq="M")
                return end_p, f"{end_month:02d}/{p.year}"

            return p, _periodo_to_label(p)

        def _ler_meta() -> dict:
            try:
                if os.path.exists(RENTAB_META_PATH):
                    with open(RENTAB_META_PATH, "r", encoding="utf-8") as f:
                        return json.load(f)
            except Exception:
                return {}
            return {}

        def _salvar_meta(meta: dict) -> None:
            try:
                pasta = os.path.dirname(RENTAB_META_PATH)
                if pasta and not os.path.exists(pasta):
                    os.makedirs(pasta)
                with open(RENTAB_META_PATH, "w", encoding="utf-8") as f:
                    json.dump(meta, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        def _meta_atual() -> dict:
            # Usa mtimes dos parquets que alimentam posições/proventos
            def _mtime(path: str):
                try:
                    return os.path.getmtime(path) if os.path.exists(path) else None
                except Exception:
                    return None

            return {
                "acoes": _mtime(ACOES_PATH),
                "renda_fixa": _mtime(RENDA_FIXA_PATH),
                "proventos": _mtime(PROVENTOS_PATH),
                "rentab_version": 7,
            }

        def _preparar_posicoes(df_cons: pd.DataFrame) -> pd.DataFrame:
            if df_cons.empty:
                return pd.DataFrame(columns=["Usuário", "Tipo", "Chave", "Periodo", "PeriodoStr", "PeriodoOrd", "Quantidade", "Preco", "Valor"])

            dfp = df_cons.copy()

            # Quantidade: para patrimônio, preferir "Quantidade". Manter fallback para "Quantidade Disponível"
            # pois alguns relatórios/formatos antigos só trazem a coluna disponível.
            # Como o consolidado contém a união das colunas, a decisão precisa ser por-linha.
            qtd = dfp["Quantidade"] if "Quantidade" in dfp.columns else None
            if qtd is None:
                qtd = dfp["Quantidade Disponível"] if "Quantidade Disponível" in dfp.columns else 0.0
            else:
                if "Quantidade Disponível" in dfp.columns:
                    qtd = qtd.where(qtd.notna(), dfp["Quantidade Disponível"])
            dfp["Quantidade"] = qtd
            dfp["Quantidade"] = dfp["Quantidade"].apply(_parse_num_misto)
            dfp["Quantidade"] = pd.to_numeric(dfp["Quantidade"], errors="coerce").fillna(0.0)

            # Preço: usar exclusivamente a coluna 'Preço' (não derivar de Valor/Quantidade)
            if "Preço" in dfp.columns:
                dfp["Preco"] = dfp["Preço"].apply(_parse_num_misto)
            else:
                dfp["Preco"] = np.nan
            dfp["Preco"] = dfp["Preco"].where(dfp["Preco"].notna() & (dfp["Preco"] > 0))

            # Valor (para fallback controlado em tipos sem preço no relatório)
            if "Valor" in dfp.columns:
                dfp["ValorSrc"] = dfp["Valor"].apply(_parse_num_misto)
            elif "Valor de Mercado" in dfp.columns:
                dfp["ValorSrc"] = dfp["Valor de Mercado"].apply(_parse_num_misto)
            else:
                dfp["ValorSrc"] = np.nan
            dfp["ValorSrc"] = pd.to_numeric(dfp["ValorSrc"], errors="coerce")

            # Fallback de Preço apenas para tipos onde frequentemente não vem preço (RF/TD)
            mask_sem_preco = dfp["Preco"].isna() | (dfp["Preco"] <= 0)
            mask_tipo_fallback = dfp.get("Tipo").isin(["Renda Fixa", "Tesouro Direto"])
            mask_qtd_ok = pd.to_numeric(dfp["Quantidade"], errors="coerce").fillna(0.0) > 0
            mask_val_ok = pd.to_numeric(dfp["ValorSrc"], errors="coerce").fillna(0.0) > 0
            mask_fallback = mask_sem_preco & mask_tipo_fallback & mask_qtd_ok & mask_val_ok
            if mask_fallback.any():
                dfp.loc[mask_fallback, "Preco"] = dfp.loc[mask_fallback, "ValorSrc"] / dfp.loc[mask_fallback, "Quantidade"]
                dfp["Preco"] = dfp["Preco"].where(dfp["Preco"].notna() & (dfp["Preco"] > 0))

            if "Usuário" not in dfp.columns:
                dfp["Usuário"] = "Não informado"
            dfp["Usuário"] = dfp["Usuário"].fillna("Não informado")

            if "Tipo" not in dfp.columns:
                dfp["Tipo"] = "N/A"
            dfp["Tipo"] = dfp["Tipo"].fillna("N/A")

            # Chave: preferir ticker, senão Ativo
            if "Ticker" in dfp.columns:
                chave = dfp["Ticker"].apply(_norm_key)
                if "Ativo" in dfp.columns:
                    vazio = chave.astype(str).str.strip() == ""
                    chave = chave.where(~vazio, dfp["Ativo"].apply(_norm_key))
            else:
                chave = dfp.get("Ativo", "").apply(_norm_key)
            dfp["Chave"] = chave

            dfp["Periodo"] = dfp.get("Mês/Ano").apply(_parse_mes_ano_to_periodo)
            dfp = dfp[dfp["Periodo"].notna()].copy()
            dfp["PeriodoStr"] = dfp["Periodo"].astype(str)  # YYYY-MM
            dfp["PeriodoOrd"] = dfp["Periodo"].apply(lambda p: int(p.ordinal))

            # Agregar por usuário/tipo/chave/mês
            def _first_non_null(s: pd.Series):
                s2 = s.dropna()
                return s2.iloc[0] if len(s2) else np.nan

            dfp = dfp.groupby(["Usuário", "Tipo", "Chave", "PeriodoStr", "PeriodoOrd"], as_index=False).agg(
                Quantidade=("Quantidade", "sum"),
                Preco=("Preco", _first_non_null),
            )
            dfp["Valor"] = (pd.to_numeric(dfp["Quantidade"], errors="coerce").fillna(0.0) * pd.to_numeric(dfp["Preco"], errors="coerce")).fillna(0.0)
            return dfp

        def _preparar_dividendos(df_div: pd.DataFrame) -> pd.DataFrame:
            if df_div is None or df_div.empty:
                return pd.DataFrame(columns=["Usuário", "Chave", "PeriodoStr", "Dividendos"])

            dfd = df_div.copy()
            if "Usuário" not in dfd.columns:
                dfd["Usuário"] = "Não informado"
            dfd["Usuário"] = dfd["Usuário"].fillna("Não informado")

            if "Data" in dfd.columns:
                dfd["Data"] = pd.to_datetime(dfd["Data"], errors="coerce")
            else:
                dfd["Data"] = pd.NaT
            dfd = dfd[dfd["Data"].notna()].copy()
            dfd["PeriodoStr"] = dfd["Data"].dt.to_period("M").astype(str)

            if "Ativo" in dfd.columns:
                dfd["Chave"] = dfd["Ativo"].apply(_norm_key)
            else:
                dfd["Chave"] = ""

            if "Valor Líquido" in dfd.columns:
                dfd["Dividendos"] = dfd["Valor Líquido"].apply(_parse_num_misto)
            else:
                dfd["Dividendos"] = 0.0
            dfd["Dividendos"] = pd.to_numeric(dfd["Dividendos"], errors="coerce").fillna(0.0)
            
            # Soma simples de dividendos por ativo/mês (sem dividir por quantidade do provento)
            dfd = dfd.groupby(["Usuário", "Chave", "PeriodoStr"], as_index=False).agg(Dividendos=("Dividendos", "sum"))
            return dfd

        def _calcular_base_rentabilidade(df_pos: pd.DataFrame, df_div: pd.DataFrame) -> pd.DataFrame:
            if df_pos.empty:
                return pd.DataFrame(columns=[
                    "Usuário", "Tipo", "Chave", "MesAno",
                    "QuantidadeAnterior", "QuantidadeAtual", "QuantidadeBase",
                    "PrecoAnterior", "PrecoAtual", "ValorInicial", "ValorFinal",
                    "Dividendos", "RetornoPct",
                    "PeriodoStr", "PeriodoOrd",
                ])

            dfp = df_pos.sort_values(["Usuário", "Tipo", "Chave", "PeriodoOrd"]).copy()

            dfp["PeriodoOrdPrev"] = dfp.groupby(["Usuário", "Tipo", "Chave"])["PeriodoOrd"].shift(1)
            dfp["QuantidadeAnterior"] = dfp.groupby(["Usuário", "Tipo", "Chave"])["Quantidade"].shift(1)
            dfp["PrecoAnterior"] = dfp.groupby(["Usuário", "Tipo", "Chave"])["Preco"].shift(1)
            dfp["PeriodoStrPrev"] = dfp.groupby(["Usuário", "Tipo", "Chave"])["PeriodoStr"].shift(1)

            dfp["QuantidadeAnterior"] = pd.to_numeric(dfp["QuantidadeAnterior"], errors="coerce").fillna(0.0)
            dfp["QuantidadeAtual"] = pd.to_numeric(dfp["Quantidade"], errors="coerce").fillna(0.0)
            dfp["PrecoAnterior"] = pd.to_numeric(dfp["PrecoAnterior"], errors="coerce")
            dfp["PrecoAtual"] = pd.to_numeric(dfp["Preco"], errors="coerce")

            # Mantém apenas meses consecutivos para evitar saltos grandes
            dfp = dfp[dfp["PeriodoOrdPrev"].notna()].copy()
            dfp = dfp[(dfp["PeriodoOrd"] - dfp["PeriodoOrdPrev"]) == 1].copy()

            # Quantidade base = quantidade do mês anterior (com proteção se houve venda)
            dfp["QuantidadeBase"] = pd.to_numeric(dfp["QuantidadeAnterior"], errors="coerce").fillna(0.0)

            dfp["ValorInicial"] = (dfp["QuantidadeBase"] * dfp["PrecoAnterior"]).fillna(0.0)
            dfp["ValorFinal"] = (dfp["QuantidadeBase"] * dfp["PrecoAtual"]).fillna(0.0)

            # Dividendos por ativo no mês corrente (soma simples)
            if df_div is not None and not df_div.empty:
                dfp = dfp.merge(df_div, on=["Usuário", "Chave", "PeriodoStr"], how="left")
                dfp["Dividendos"] = pd.to_numeric(dfp["Dividendos"], errors="coerce").fillna(0.0)
            else:
                dfp["Dividendos"] = 0.0

            dfp["RetornoPct"] = np.where(
                dfp["ValorInicial"] > 0,
                ((dfp["ValorFinal"] + dfp["Dividendos"]) - dfp["ValorInicial"]) / dfp["ValorInicial"] * 100.0,
                np.nan,
            )

            # Label MM/YYYY a partir de PeriodoStr
            try:
                per = pd.PeriodIndex(dfp["PeriodoStr"], freq="M")
                dfp["MesAno"] = per.strftime("%m/%Y")
            except Exception:
                dfp["MesAno"] = dfp["PeriodoStr"].astype(str)

            cols = [
                "Usuário", "Tipo", "Chave", "MesAno",
                "QuantidadeAnterior", "QuantidadeAtual", "QuantidadeBase",
                "PrecoAnterior", "PrecoAtual", "ValorInicial", "ValorFinal",
                "Dividendos", "RetornoPct",
                "PeriodoStr", "PeriodoOrd",
            ]
            return dfp[cols]

        def _carregar_ou_gerar_base(df_posicoes: pd.DataFrame, df_div: pd.DataFrame) -> pd.DataFrame:
            meta_old = _ler_meta()
            meta_new = _meta_atual()
            needs_rebuild = (meta_old != meta_new) or (not os.path.exists(RENTAB_PARQUET_PATH))

            if not needs_rebuild:
                try:
                    return pd.read_parquet(RENTAB_PARQUET_PATH)
                except Exception:
                    needs_rebuild = True

            df_pos = _preparar_posicoes(df_posicoes)
            df_div_prep = _preparar_dividendos(df_div)
            base = _calcular_base_rentabilidade(df_pos, df_div_prep)

            try:
                pasta = os.path.dirname(RENTAB_PARQUET_PATH)
                if pasta and not os.path.exists(pasta):
                    os.makedirs(pasta)
                base.to_parquet(RENTAB_PARQUET_PATH, index=False)
                _salvar_meta(meta_new)
            except Exception:
                pass

            return base

        def _agregar_composto(df_mensal: pd.DataFrame, freq: str, group_col: str) -> pd.DataFrame:
            if df_mensal.empty:
                return df_mensal

            df = df_mensal.copy()
            # Converte PeriodoStr -> Period (para ordenação/agregação)
            per = pd.PeriodIndex(df["PeriodoStr"].astype(str), freq="M")
            df["Periodo"] = per
            df["Fator"] = 1.0 + (pd.to_numeric(df["RetornoPct"], errors="coerce") / 100.0)

            def _bucket(p: pd.Period):
                end_p, label = _to_periodo_end(freq, p)
                return end_p, label

            tmp = df["Periodo"].apply(_bucket)
            df["PeriodoEnd"] = tmp.apply(lambda t: t[0])
            df["Label"] = tmp.apply(lambda t: t[1])

            grp_cols = [group_col, "PeriodoEnd", "Label"]
            agg = df.groupby(grp_cols, as_index=False).agg(
                Fator=("Fator", "prod"),
                Dividendos=("Dividendos", "sum"),
                ValorInicial=("ValorInicial", "sum"),
                ValorFinal=("ValorFinal", "sum"),
            )
            agg["RetornoPct"] = (agg["Fator"] - 1.0) * 100.0
            return agg

        if df_consolidado_geral.empty:
            st.info("Sem dados de posições para calcular rentabilidade.")
        else:
            # Gera / carrega base detalhada (ativo x mês) e salva em parquet
            base = _carregar_ou_gerar_base(df_consolidado_geral, df_dividendos_consolidado)
            if base.empty:
                st.info("Dados insuficientes para calcular rentabilidade (precisa de meses consecutivos e ativos com preço/quantidade).")
            else:
                usuarios_disp = sorted([u for u in base["Usuário"].dropna().unique()])
                tipos_disp = sorted([t for t in base["Tipo"].dropna().unique()])
                ativos_disp = sorted([a for a in base["Chave"].dropna().unique() if str(a).strip() != ""])

                col_f1, col_f2, col_f3 = st.columns(3)
                with col_f1:
                    usuarios_opcoes = ["Todos"] + usuarios_disp
                    usuarios_sel = st.multiselect("Usuário", usuarios_opcoes, default=["Todos"], key="rentab_usuarios")
                    if "Todos" in usuarios_sel:
                        usuarios_sel = usuarios_disp
                with col_f2:
                    tipos_opcoes = ["Todos"] + tipos_disp
                    tipos_sel = st.multiselect("Tipo", tipos_opcoes, default=["Todos"], key="rentab_tipos")
                    if "Todos" in tipos_sel:
                        tipos_sel = tipos_disp
                with col_f3:
                    modo_vis = st.selectbox("Visualização", ["Total (Carteira)", "Por Ativo"], index=0, key="rentab_modo")

                col_a1, _col_a2 = st.columns(2)
                with col_a1:
                    ativos_opcoes = ["Todos"] + ativos_disp
                    ativos_sel = st.multiselect("Ativo/Ticker", ativos_opcoes, default=["Todos"], key="rentab_ativos")
                    if "Todos" in ativos_sel:
                        ativos_sel = ativos_disp

                base_f = base.copy()
                if usuarios_sel:
                    base_f = base_f[base_f["Usuário"].isin(usuarios_sel)]
                if tipos_sel:
                    base_f = base_f[base_f["Tipo"].isin(tipos_sel)]
                if ativos_sel:
                    base_f = base_f[base_f["Chave"].isin(ativos_sel)]

                # ===== Evolução patrimonial bruta (mensal, sem “tratar” além do sum) =====
                st.markdown("---")
                st.subheader("💚 Evolução Patrimonial Bruta")

                df_patr_src = df_consolidado_geral.copy()
                if usuarios_sel and "Usuário" in df_patr_src.columns:
                    df_patr_src = df_patr_src[df_patr_src["Usuário"].isin(usuarios_sel)]
                if tipos_sel and "Tipo" in df_patr_src.columns:
                    df_patr_src = df_patr_src[df_patr_src["Tipo"].isin(tipos_sel)]
                if "Valor" not in df_patr_src.columns and "Valor de Mercado" in df_patr_src.columns:
                    df_patr_src["Valor"] = df_patr_src["Valor de Mercado"]
                df_patr_src["Valor"] = pd.to_numeric(df_patr_src.get("Valor"), errors="coerce").fillna(0.0)
                df_patr_src["Periodo"] = df_patr_src.get("Mês/Ano").apply(_parse_mes_ano_to_periodo)
                df_patr_src = df_patr_src[df_patr_src["Periodo"].notna()].copy()
                df_patr_src["Label"] = df_patr_src["Periodo"].apply(_periodo_to_label)
                df_patr = df_patr_src.groupby(["Periodo", "Label"], as_index=False).agg(Valor=("Valor", "sum")).sort_values(["Periodo"])

                if df_patr.empty:
                    st.info("Sem dados para evolução patrimonial.")
                else:
                    from plotly.colors import sample_colorscale
                    greens = px.colors.sequential.Greens
                    n_bars = len(df_patr)
                    # Ordena os valores para mapear o degradê corretamente
                    valores = df_patr["Valor"].values
                    ordem = valores.argsort()
                    # Gera um array de posições normalizadas para o degradê
                    norm = (valores - valores.min()) / (valores.max() - valores.min()) if valores.max() > valores.min() else [0.5]*n_bars
                    # Aplica o degradê: menor valor = verde claro, maior = verde escuro
                    bar_colors = sample_colorscale(greens, norm)

                    fig_patr = px.bar(
                        x=df_patr["Label"],
                        y=df_patr["Valor"],
                        labels={"x": "Período", "y": "Patrimônio (R$)"},
                        text=[f"R$ {v:,.2f}" for v in df_patr["Valor"].values],
                        title="Patrimônio Bruto (Mensal)"
                    )
                    fig_patr.update_traces(textposition="outside", cliponaxis=False, marker_color=bar_colors)
                    fig_patr.update_layout(yaxis_tickformat=",.2f", margin=dict(t=60))
                    st.plotly_chart(fig_patr, use_container_width=True, key="rentab_patrimonio")

                # ===== Rentabilidade (juros compostos a partir da base mensal por ativo) =====
                st.markdown("---")
                st.subheader("📈 Rentabilidade")
                freq_sel = st.selectbox(
                    "Período (Rentabilidade)",
                    ["Mensal", "Bimestral", "Trimestral", "Semestral", "Anual"],
                    index=0,
                    key="rentab_freq"
                )

                modo_retorno = st.radio(
                    "Retorno exibido",
                    ["Com dividendos", "Sem dividendos"],
                    index=0,
                    horizontal=True,
                    key="rentab_modo_retorno",
                )
                usar_dividendos = modo_retorno == "Com dividendos"
                sufixo_retorno = "com dividendos" if usar_dividendos else "sem dividendos"

                st.markdown("#### Seleção de Usuários para o Gráfico")
                if modo_vis == "Total (Carteira)":
                    mensal = base_f.groupby(["Usuário", "PeriodoStr"], as_index=False).agg(
                        ValorInicial=("ValorInicial", "sum"),
                        ValorFinal=("ValorFinal", "sum"),
                        Dividendos=("Dividendos", "sum"),
                    )
                    mensal["RetornoPct"] = np.where(
                        mensal["ValorInicial"] > 0,
                        ((mensal["ValorFinal"] + (mensal["Dividendos"] if usar_dividendos else 0.0)) - mensal["ValorInicial"]) / mensal["ValorInicial"] * 100.0,
                        np.nan,
                    )
                    mensal = mensal.rename(columns={"Usuário": "Serie"})

                    # Total (todos usuários selecionados)
                    total = mensal.groupby(["PeriodoStr"], as_index=False).agg(
                        ValorInicial=("ValorInicial", "sum"),
                        ValorFinal=("ValorFinal", "sum"),
                        Dividendos=("Dividendos", "sum"),
                    )
                    total["RetornoPct"] = np.where(
                        total["ValorInicial"] > 0,
                        ((total["ValorFinal"] + (total["Dividendos"] if usar_dividendos else 0.0)) - total["ValorInicial"]) / total["ValorInicial"] * 100.0,
                        np.nan,
                    )
                    total["Serie"] = "Total"
                    mensal = pd.concat([mensal, total], ignore_index=True)
                    series_disponiveis = sorted(mensal["Serie"].unique(), key=lambda x: (x != "Total", x))
                else:
                    mensal = base_f.groupby(["Chave", "PeriodoStr"], as_index=False).agg(
                        ValorInicial=("ValorInicial", "sum"),
                        ValorFinal=("ValorFinal", "sum"),
                        Dividendos=("Dividendos", "sum"),
                    )
                    mensal["RetornoPct"] = np.where(
                        mensal["ValorInicial"] > 0,
                        ((mensal["ValorFinal"] + (mensal["Dividendos"] if usar_dividendos else 0.0)) - mensal["ValorInicial"]) / mensal["ValorInicial"] * 100.0,
                        np.nan,
                    )
                    mensal = mensal.rename(columns={"Chave": "Serie"})
                    series_disponiveis = sorted(mensal["Serie"].unique())

                # Caixa de seleção de séries (usuários ou ativos)
                series_opcoes = ["Total"] + [s for s in series_disponiveis if s != "Total"]
                series_sel = st.multiselect(
                    "Usuários/Séries exibidas no gráfico",
                    options=series_opcoes,
                    default=series_opcoes,
                    key="rentab_series_grafico"
                )
                # Filtra as séries selecionadas
                df_plot = _agregar_composto(mensal, freq_sel, group_col="Serie")
                df_plot = df_plot[df_plot["PeriodoEnd"].notna()].sort_values(["PeriodoEnd", "Serie"]).copy()
                df_plot = df_plot[df_plot["Serie"].isin(series_sel)]

                # Aplica os mesmos filtros de seleção do gráfico na tabela base mensal
                base_tbl = base_f.copy()
                if modo_vis == "Total (Carteira)":
                    usuarios_graf = [s for s in series_sel if s != "Total"]
                    if usuarios_graf:
                        base_tbl = base_tbl[base_tbl["Usuário"].isin(usuarios_graf)]
                else:
                    series_graf = [s for s in series_sel if s != "Total"]
                    if series_graf:
                        base_tbl = base_tbl[base_tbl["Chave"].isin(series_graf)]

                # Ajusta RetornoPct exibido na base mensal conforme modo (com/sem dividendos)
                if "ValorInicial" in base_tbl.columns and "ValorFinal" in base_tbl.columns:
                    base_tbl["RetornoPct"] = np.where(
                        pd.to_numeric(base_tbl["ValorInicial"], errors="coerce") > 0,
                        (
                            (
                                pd.to_numeric(base_tbl["ValorFinal"], errors="coerce")
                                + (pd.to_numeric(base_tbl["Dividendos"], errors="coerce") if usar_dividendos and "Dividendos" in base_tbl.columns else 0.0)
                            )
                            - pd.to_numeric(base_tbl["ValorInicial"], errors="coerce")
                        )
                        / pd.to_numeric(base_tbl["ValorInicial"], errors="coerce")
                        * 100.0,
                        np.nan,
                    )

                # Rótulos apenas para a série Total (1 casa decimal)
                df_plot["text"] = np.where(
                    df_plot["Serie"] == "Total",
                    df_plot["RetornoPct"].round(1).astype(str) + "%",
                    None,
                )

                fig = px.line(
                    df_plot,
                    x="Label",
                    y="RetornoPct",
                    color="Serie",
                    markers=True,
                    labels={"Label": "Período", "RetornoPct": "Rentabilidade (%)"},
                    title=f"Rentabilidade {freq_sel} (juros compostos) — {sufixo_retorno}",
                    text="text",
                )
                fig.update_traces(textposition="top center")
                fig.update_layout(margin=dict(t=60))
                st.plotly_chart(fig, use_container_width=True, key="rentab_chart")

                # Gráfico de rentabilidade acumulada (juros compostos)
                if not df_plot.empty:
                    df_acum = []
                    for serie, grp in df_plot.groupby("Serie"):
                        grp_sorted = grp.sort_values("PeriodoEnd").copy()
                        fator = (1 + pd.to_numeric(grp_sorted["RetornoPct"], errors="coerce") / 100.0).cumprod()
                        grp_sorted["RetornoAcumPct"] = (fator - 1.0) * 100.0
                        df_acum.append(grp_sorted)
                    df_acum = pd.concat(df_acum, ignore_index=True) if df_acum else pd.DataFrame()

                    fig_acum = px.line(
                        df_acum,
                        x="Label",
                        y="RetornoAcumPct",
                        color="Serie",
                        markers=True,
                        labels={"Label": "Período", "RetornoAcumPct": "Rentabilidade Acumulada (%)"},
                        title=f"Rentabilidade Acumulada {freq_sel} (juros compostos) — {sufixo_retorno}",
                    )
                    fig_acum.update_layout(margin=dict(t=60))
                    st.plotly_chart(fig_acum, use_container_width=True, key="rentab_chart_acum")

                # ===== Rentabilidade por Tipo de Investimento =====
                st.markdown("---")
                st.subheader("📊 Rentabilidade por Tipo de Investimento")
                
                freq_tipo = st.selectbox(
                    "Período (Rentabilidade por Tipo)",
                    ["Mensal", "Bimestral", "Trimestral", "Semestral", "Anual"],
                    index=0,
                    key="rentab_freq_tipo"
                )
                
                # Agrupa por Tipo ao invés de Usuário
                mensal_tipo = base_f.groupby(["Tipo", "PeriodoStr"], as_index=False).agg(
                    ValorInicial=("ValorInicial", "sum"),
                    ValorFinal=("ValorFinal", "sum"),
                    Dividendos=("Dividendos", "sum"),
                )
                mensal_tipo["RetornoPct"] = np.where(
                    mensal_tipo["ValorInicial"] > 0,
                    ((mensal_tipo["ValorFinal"] + (mensal_tipo["Dividendos"] if usar_dividendos else 0.0)) - mensal_tipo["ValorInicial"]) / mensal_tipo["ValorInicial"] * 100.0,
                    np.nan,
                )
                mensal_tipo = mensal_tipo.rename(columns={"Tipo": "Serie"})
                
                # Total (todos tipos)
                total_tipo = mensal_tipo.groupby(["PeriodoStr"], as_index=False).agg(
                    ValorInicial=("ValorInicial", "sum"),
                    ValorFinal=("ValorFinal", "sum"),
                    Dividendos=("Dividendos", "sum"),
                )
                total_tipo["RetornoPct"] = np.where(
                    total_tipo["ValorInicial"] > 0,
                    ((total_tipo["ValorFinal"] + (total_tipo["Dividendos"] if usar_dividendos else 0.0)) - total_tipo["ValorInicial"]) / total_tipo["ValorInicial"] * 100.0,
                    np.nan,
                )
                total_tipo["Serie"] = "Total"
                mensal_tipo = pd.concat([mensal_tipo, total_tipo], ignore_index=True)
                
                # Filtra as séries selecionadas
                df_plot_tipo = _agregar_composto(mensal_tipo, freq_tipo, group_col="Serie")
                df_plot_tipo = df_plot_tipo[df_plot_tipo["PeriodoEnd"].notna()].sort_values(["PeriodoEnd", "Serie"]).copy()
                
                tipos_unicos = sorted([t for t in df_plot_tipo["Serie"].unique() if t != "Total"])
                series_opcoes_tipo = ["Total"] + tipos_unicos
                series_sel_tipo = st.multiselect(
                    "Tipos de investimento exibidos no gráfico",
                    options=series_opcoes_tipo,
                    default=series_opcoes_tipo,
                    key="rentab_series_tipo"
                )
                df_plot_tipo = df_plot_tipo[df_plot_tipo["Serie"].isin(series_sel_tipo)]
                
                # Rótulos apenas para Total
                df_plot_tipo["text"] = np.where(
                    df_plot_tipo["Serie"] == "Total",
                    df_plot_tipo["RetornoPct"].round(1).astype(str) + "%",
                    None,
                )
                
                # Gráfico de rentabilidade por tipo (mensal)
                fig_tipo = px.line(
                    df_plot_tipo,
                    x="Label",
                    y="RetornoPct",
                    color="Serie",
                    markers=True,
                    labels={"Label": "Período", "RetornoPct": "Rentabilidade (%)"},
                    title=f"Rentabilidade Mensal por Tipo (juros compostos) — {sufixo_retorno}",
                    text="text",
                )
                fig_tipo.update_traces(textposition="top center")
                fig_tipo.update_layout(margin=dict(t=60))
                st.plotly_chart(fig_tipo, use_container_width=True, key="rentab_chart_tipo")
                
                # Gráfico de rentabilidade acumulada por tipo
                if not df_plot_tipo.empty:
                    df_acum_tipo = []
                    for serie, grp in df_plot_tipo.groupby("Serie"):
                        grp_sorted = grp.sort_values("PeriodoEnd").copy()
                        fator = (1 + pd.to_numeric(grp_sorted["RetornoPct"], errors="coerce") / 100.0).cumprod()
                        grp_sorted["RetornoAcumPct"] = (fator - 1.0) * 100.0
                        df_acum_tipo.append(grp_sorted)
                    df_acum_tipo = pd.concat(df_acum_tipo, ignore_index=True) if df_acum_tipo else pd.DataFrame()
                    
                    fig_acum_tipo = px.line(
                        df_acum_tipo,
                        x="Label",
                        y="RetornoAcumPct",
                        color="Serie",
                        markers=True,
                        labels={"Label": "Período", "RetornoAcumPct": "Rentabilidade Acumulada (%)"},
                        title=f"Rentabilidade Acumulada Mensal por Tipo (juros compostos) — {sufixo_retorno}",
                    )
                    fig_acum_tipo.update_layout(margin=dict(t=60))
                    st.plotly_chart(fig_acum_tipo, use_container_width=True, key="rentab_chart_acum_tipo")

                with st.expander("📋 Ver base mensal (ativo x mês)", expanded=False):
                    cols_show = [
                        "Usuário", "Tipo", "Chave", "MesAno",
                        "QuantidadeAnterior", "QuantidadeAtual", "QuantidadeBase",
                        "PrecoAnterior", "PrecoAtual", "ValorInicial", "ValorFinal",
                        "Dividendos", "RetornoPct",
                    ]
                    cols_show = [c for c in cols_show if c in base_tbl.columns]
                    st.dataframe(base_tbl[cols_show], use_container_width=True, hide_index=True)

                    with st.expander("📋 Ver tabela do gráfico", expanded=False):
                        tabela = df_plot[["Serie", "Label", "RetornoPct"]].copy()
                        tabela["RetornoPct"] = pd.to_numeric(tabela["RetornoPct"], errors="coerce")
                        st.dataframe(tabela, use_container_width=True, hide_index=True)

# ============ TAB POSIÇÃO ATUAL ============
with tab_posicao:
    st.header("📌 Posição Atual")

    # Para Posição Atual, queremos Ações Dólar em USD (para aplicar câmbio atual na atualização)
    df_acoes_avenue_pos_usd = pd.DataFrame()
    if not df_acoes_avenue_raw.empty:
        try:
            df_acoes_avenue_pos_usd = padronizar_acoes_avenue(df_acoes_avenue_raw)
            df_acoes_avenue_pos_usd["Tipo"] = "Ações Dólar"
            for col in ["Mês/Ano", "Usuário"]:
                if col not in df_acoes_avenue_pos_usd.columns:
                    df_acoes_avenue_pos_usd[col] = None
        except Exception:
            df_acoes_avenue_pos_usd = pd.DataFrame()

    frames_consolidados = []
    if not df_padronizado.empty:
        frames_consolidados.append(df_padronizado.copy())
    if not df_acoes_avenue_pos_usd.empty:
        frames_consolidados.append(df_acoes_avenue_pos_usd.copy())

    df_consolidado_geral = pd.concat(frames_consolidados, ignore_index=True) if frames_consolidados else pd.DataFrame()

    # Mesmos filtros da aba 💼 Investimento (inclui opção "Todos")
    df_base_filtrada = aplicar_filtros_padrao(df_consolidado_geral, "posicao_atual")
    df_posicao_base = preparar_posicao_base(df_base_filtrada, agrupar_por_usuario=False)

    if df_posicao_base.empty:
        st.info("Sem dados de posição para atualizar.")
    else:
        col_a, col_b = st.columns([1, 2])
        with col_a:
            if st.button("Atualizar cotações", key="posicao_atual_btn_atualizar"):
                st.session_state["posicao_atual_forcar_update"] = True

        last_dt = st.session_state.get("posicao_atual_ultima_atualizacao")
        with col_b:
            if isinstance(last_dt, datetime):
                st.caption(f"Última atualização: {last_dt.strftime('%d/%m/%Y %H:%M:%S')}")

        # Se a base mudou (ex: novo upload), força atualização
        try:
            base_sig = f"{len(df_posicao_base)}|{','.join(df_posicao_base['Ticker'].astype(str).head(50).tolist())}"  # assinatura leve
        except Exception:
            base_sig = None

        precisa_atualizar = (
            st.session_state.get("posicao_atual_df") is None
            or st.session_state.get("posicao_atual_forcar_update") is True
            or (base_sig is not None and st.session_state.get("posicao_atual_base_sig") != base_sig)
        )

        if precisa_atualizar:
            with st.spinner("Buscando cotações em tempo real (yfinance)..."):
                df_atual, sem_cotacao, dt_atual = atualizar_cotacoes(df_posicao_base)
            st.session_state["posicao_atual_df"] = df_atual
            st.session_state["posicao_atual_sem_cotacao"] = sem_cotacao
            st.session_state["posicao_atual_ultima_atualizacao"] = dt_atual
            st.session_state["posicao_atual_base_sig"] = base_sig
            st.session_state["posicao_atual_forcar_update"] = False

        df_atual = st.session_state.get("posicao_atual_df")
        sem_cotacao = st.session_state.get("posicao_atual_sem_cotacao") or []

        if sem_cotacao:
            st.warning(
                "Sem cotação via yfinance (usando último preço do histórico quando disponível): "
                + ", ".join(sem_cotacao)
            )

        # Câmbio atual (se houver Ações Dólar)
        try:
            fx = pd.to_numeric(df_atual.get("Cotação USD/BRL"), errors="coerce")
            fx_val = float(fx.dropna().iloc[0]) if fx is not None and fx.dropna().size else None
        except Exception:
            fx_val = None
        if fx_val is not None:
            st.caption(f"USD/BRL (atual): {fx_val:,.4f}")

        # Copiar modelo da aba 💼 Investimento: métricas + gráfico de distribuição
        df_view = df_atual.copy()
        df_view["Valor"] = df_view.get("Valor Atualizado")
        if "Ativo" not in df_view.columns:
            df_view["Ativo"] = df_view.get("Ticker")

        df_view_enriquecido = enriquecer_com_setor_segmento(df_view)

        # Cards (padrão mercado): Total + USD/BRL + EUR/BRL (com variação %)
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        total_val = float(pd.to_numeric(df_view_enriquecido.get("Valor"), errors="coerce").fillna(0).sum())
        with c1:
            st.metric("💰 Valor Total (Atualizado)", f"R$ {total_val:,.2f}")

        def _cotacao_e_delta(indice: str):
            try:
                h = obter_historico_indice(indice, periodo="10d", intervalo="1d")
                if h is None or h.empty or "Close" not in h.columns:
                    return None, None
                close = pd.to_numeric(h["Close"], errors="coerce").dropna()
                if close.size < 2:
                    return float(close.iloc[-1]) if close.size else None, None
                last = float(close.iloc[-1])
                prev = float(close.iloc[-2])
                if prev <= 0:
                    return last, None
                return last, (last / prev - 1.0) * 100.0
            except Exception:
                return None, None

        usd, usd_delta = _cotacao_e_delta("USD/BRL")
        eur, eur_delta = _cotacao_e_delta("EUR/BRL")
        with c2:
            if usd is None:
                st.metric("USD/BRL", "—")
            else:
                st.metric("USD/BRL", f"R$ {usd:,.4f}", (f"{usd_delta:+.2f}%" if usd_delta is not None else None))
        with c3:
            if eur is None:
                st.metric("EUR/BRL", "—")
            else:
                st.metric("EUR/BRL", f"R$ {eur:,.4f}", (f"{eur_delta:+.2f}%" if eur_delta is not None else None))

        # Mantém o detalhamento por tipo (mesmo padrão de Investimento)
        # exibir_metricas_valor(df_view_enriquecido, col_valor="Valor")  # Removido para evitar duplicidade visual

        # Painéis: Top 5 Altas / Top 5 Baixas
        st.markdown("---")
        col_up, col_down = st.columns(2)
        base_mov = df_view_enriquecido.copy()
        base_mov["Variação %"] = pd.to_numeric(base_mov.get("Variação %"), errors="coerce")
        base_mov = base_mov.dropna(subset=["Variação %"]).copy()
        cols_mov = [c for c in ["Ticker", "Tipo", "Variação %", "Preço Histórico (BRL)", "Preço Atual", "Valor Atualizado"] if c in base_mov.columns]

        with col_up:
            st.subheader("📈 Maiores Altas (Top 5)")
            if base_mov.empty:
                st.info("Sem dados suficientes para calcular variação.")
            else:
                df_top_up = base_mov.nlargest(5, "Variação %")[cols_mov].copy()
                _, sty_up = preparar_tabela_posicao_estilizada(df_top_up)
                st.dataframe(sty_up, use_container_width=True, hide_index=True)

        with col_down:
            st.subheader("📉 Maiores Baixas (Top 5)")
            if base_mov.empty:
                st.info("Sem dados suficientes para calcular variação.")
            else:
                df_top_down = base_mov.nsmallest(5, "Variação %")[cols_mov].copy()
                _, sty_down = preparar_tabela_posicao_estilizada(df_top_down)
                st.dataframe(sty_down, use_container_width=True, hide_index=True)

        with st.expander("📋 Ver tabela completa (posição atualizada)", expanded=False):
            df_tab, sty = preparar_tabela_posicao_estilizada(df_view_enriquecido)
            st.dataframe(sty, use_container_width=True, hide_index=True)

        gerar_graficos_distribuicao(df_view_enriquecido, col_valor="Valor", cores="Purples", key_prefixo="posicao_atual")
        exibir_tabela_info_tickers(df_view_enriquecido)

        # Exportação
        st.markdown("---")
        csv_bytes = df_view_enriquecido.to_csv(index=False, sep=",", encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            "Exportar CSV",
            data=csv_bytes,
            file_name="posicao_atual.csv",
            mime="text/csv",
            key="posicao_atual_download_csv",
        )

        try:
            xlsx_bytes = dataframe_para_excel_bytes(df_view_enriquecido, sheet_name="posicao_atual")
            st.download_button(
                "Exportar Excel",
                data=xlsx_bytes,
                file_name="posicao_atual.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="posicao_atual_download_xlsx",
            )
        except Exception:
            st.info("Não foi possível gerar o Excel. Verifique se o pacote 'openpyxl' está instalado.")

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
        st.header("📝 Inserção Manual")
        
        # Abas secundárias para Caixa e Ações
        sec_caixa, sec_acoes, sec_view = st.tabs([
            "💵 Caixa",
            "📈 Ações",
            "📊 Investimentos Manuais"
        ])
        
        # --- Caixa ---
        with sec_caixa:
            st.subheader("💵 Registrar Caixa")
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                mes_caixa = st.text_input(
                    "Mês (MM/YYYY)",
                    value=pd.Timestamp.now().strftime("%m/%Y"),
                    key="caixa_mes"
                )
            with col_c2:
                usr_caixa = st.selectbox(
                    "Usuário",
                    options=sorted(df_usuarios.get("Nome", pd.Series()).dropna().unique().tolist()) + ["Manual"],
                    index=None,
                    key="caixa_usr"
                )
            
            col_c3, col_c4 = st.columns(2)
            with col_c3:
                val_caixa = st.number_input(
                    "Valor Inicial (R$)",
                    min_value=0.0,
                    step=100.0,
                    key="caixa_val"
                )
            with col_c4:
                rent_caixa = st.number_input(
                    "Rentabilidade (%)",
                    min_value=0.0,
                    step=0.1,
                    key="caixa_rent"
                )
            
            if st.button("Registrar Caixa", key="btn_reg_caixa"):
                try:
                    df_caixa_new = registrar_caixa(
                        mes_caixa,
                        val_caixa,
                        rent_caixa,
                        usuario=usr_caixa or "Manual"
                    )
                    st.success(f"✅ Caixa registrado para {mes_caixa}")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro: {e}")
            
            st.markdown("---")
            st.subheader("Registros de Caixa")
            df_caixa_view = carregar_caixa()
            if not df_caixa_view.empty:
                st.dataframe(df_caixa_view, use_container_width=True, hide_index=True)
                csv_caixa = df_caixa_view.to_csv(index=False)
                st.download_button(
                    "📥 CSV Caixa",
                    csv_caixa,
                    "caixa.csv",
                    "text/csv",
                    key="dl_csv_caixa"
                )
            else:
                st.info("Sem registros de caixa.")
        
        # --- Ações ---
        with sec_acoes:
            st.subheader("📈 Inserir Ação Manual")
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                ticker_acao = st.text_input(
                    "Ticker (ex: BBAS3, AAPL)",
                    key="acao_ticker"
                )
            with col_a2:
                mes_acao = st.text_input(
                    "Mês (MM/YYYY)",
                    value=pd.Timestamp.now().strftime("%m/%Y"),
                    key="acao_mes"
                )
            
            col_a3, col_a4 = st.columns(2)
            with col_a3:
                qtd_acao = st.number_input(
                    "Quantidade",
                    min_value=0.0,
                    step=1.0,
                    key="acao_qtd"
                )
            with col_a4:
                usr_acao = st.selectbox(
                    "Usuário",
                    options=sorted(df_usuarios.get("Nome", pd.Series()).dropna().unique().tolist()) + ["Manual"],
                    index=None,
                    key="acao_usr"
                )
            
            if st.button("Buscar Preço e Registrar", key="btn_reg_acao"):
                if not ticker_acao or qtd_acao <= 0:
                    st.error("❌ Preencha ticker e quantidade.")
                else:
                    with st.spinner("Buscando preço no yfinance..."):
                        try:
                            df_acoes_new, meta = registrar_acao_manual(
                                ticker_acao,
                                qtd_acao,
                                mes_acao,
                                usuario=usr_acao or "Manual"
                            )
                            st.success(f"✅ Ação {ticker_acao} registrada!")
                            st.markdown(f"""
**Resumo:**
- **Tipo:** {meta['tipo']}
- **Preço Atual:** {meta['moeda']} {meta['preco']:.4f}
- **Cotação:** 1 {meta['moeda']} = R$ {meta['fx']:.4f}
- **Preço BRL:** R$ {meta['preco_brl']:.2f}
- **Valor Total:** R$ {meta['valor_total_brl']:,.2f}
                            """)
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erro: {e}")
            
            st.markdown("---")
            st.subheader("Ações Inseridas")
            df_acoes_view = carregar_acoes_man()
            if not df_acoes_view.empty:
                st.dataframe(df_acoes_view, use_container_width=True, hide_index=True)
                csv_acoes = df_acoes_view.to_csv(index=False)
                st.download_button(
                    "📥 CSV Ações",
                    csv_acoes,
                    "acoes_manuais.csv",
                    "text/csv",
                    key="dl_csv_acoes"
                )
            else:
                st.info("Sem ações inseridas manualmente.")
        
        # --- Visualizar ---
        with sec_view:
            st.subheader("📊 Investimentos Manuais")
            
            tabs_man = st.tabs(["Consolidado", "Caixa", "Ações"])
            
            with tabs_man[0]:
                st.markdown("**Consolidado (Caixa + Ações)**")
                df_caixa_all = carregar_caixa()
                df_acoes_all = carregar_acoes_man()
                
                consolidado_parts = []
                if not df_caixa_all.empty:
                    df_caixa_view_cons = df_caixa_all[[
                        "Usuário", "Mes", "Valor Inicial", "Rentabilidade %", "Ganho"
                    ]].copy()
                    df_caixa_view_cons["Tipo"] = "Caixa"
                    consolidado_parts.append(df_caixa_view_cons)
                
                if not df_acoes_all.empty:
                    df_acoes_view_cons = df_acoes_all[[
                        "Usuário", "Tipo", "Ticker", "Quantidade", "Preço BRL", "Valor", "Mês/Ano"
                    ]].rename(columns={"Mês/Ano": "Mes"}).copy()
                    consolidado_parts.append(df_acoes_view_cons)
                
                if consolidado_parts:
                    df_consolidado_man = pd.concat(consolidado_parts, ignore_index=True)
                    st.dataframe(df_consolidado_man, use_container_width=True, hide_index=True)
                    
                    # Exportar consolidado
                    csv_cons = df_consolidado_man.to_csv(index=False)
                    st.download_button(
                        "📥 CSV Consolidado",
                        csv_cons,
                        "investimentos_manuais.csv",
                        "text/csv",
                        key="dl_csv_cons"
                    )
                    
                    try:
                        xlsx_cons = df_manual_para_excel(df_consolidado_man, sheet_name="investimentos_manuais")
                        st.download_button(
                            "📥 Excel",
                            xlsx_cons,
                            "investimentos_manuais.xlsx",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_xlsx_cons"
                        )
                    except Exception:
                        st.info("Excel não disponível.")
                else:
                    st.info("Sem dados manuais.")
            
            with tabs_man[1]:
                st.markdown("**Caixa**")
                df_caixa_view_det = carregar_caixa()
                if not df_caixa_view_det.empty:
                    st.dataframe(df_caixa_view_det, use_container_width=True, hide_index=True)
                else:
                    st.info("Sem registros de caixa.")
            
            with tabs_man[2]:
                st.markdown("**Ações**")
                df_acoes_view_det = carregar_acoes_man()
                if not df_acoes_view_det.empty:
                    st.dataframe(df_acoes_view_det, use_container_width=True, hide_index=True)
                else:
                    st.info("Sem ações inseridas manualmente.")
    
    # --- Documentação ---
    with subtab_doc:
        st.header("📚 Documentação")
        st.markdown("""
## Inserção Manual

### 💵 Caixa
- Registre o valor inicial do caixa no mês e a rentabilidade (%).
- O sistema calcula o ganho (Valor Inicial × Rentabilidade / 100).
- O ganho é automaticamente integrado à aba **Rentabilidade** como "Dividendos".

### 📈 Ações
- Insira o ticker (ex: BBAS3, AAPL) e a quantidade.
- O sistema busca automaticamente:
  - Preço atual via **yfinance**
  - Moeda da ação (USD, EUR, BRL)
  - Cotação para BRL (se necessário)
- Categorização automática:
  - "Ações Dólar" (USD)
  - "Ações Euro" (EUR)
  - "Ações BRL" (BRL)

### 📊 Exportação
- CSV: compatível com Excel e ferramentas de análise.
- Excel: formato .xlsx com formatação.

---

**Nota:** Todos os dados são salvos automaticamente em parquets (formato otimizado para análise de séries temporais).
        """)

