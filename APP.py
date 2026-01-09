import os
import json
from datetime import datetime
from io import BytesIO
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import yfinance as yf
from modules.ticker_info import CACHE_PATH as TICKER_INFO_PATH

from modules.usuarios import carregar_usuarios, salvar_usuarios
from modules.upload_relatorio import ACOES_PATH, RENDA_FIXA_PATH, PROVENTOS_PATH, padronizar_tabelas, padronizar_dividendos
from modules.avenue_views import aba_acoes_avenue, aba_proventos_avenue, padronizar_dividendos_avenue, carregar_dividendos_avenue, padronizar_acoes_avenue, carregar_acoes_avenue
from modules.cotacoes import converter_usd_para_brl, obter_historico_indice
from modules.posicao_atual import preparar_posicao_base, atualizar_cotacoes, dataframe_para_excel_bytes, preparar_tabela_posicao_estilizada
from modules.investimentos_manuais import (
    carregar_caixa,
    registrar_caixa,
    carregar_caixa_movimentos,
    registrar_caixa_movimentos,
    CAIXA_PATH,
    CAIXA_MOVS_PATH,
    ACOES_MANUAIS_PATH,
    carregar_acoes as carregar_acoes_man,
    registrar_acao_manual,
    caixa_para_dividendos,
    caixa_para_consolidado,
    acoes_para_consolidado,
    dataframe_para_excel_bytes as df_manual_para_excel,
)
from modules.opcoes import (
    consultar_opcoes_disponiveis,
    carregar_vendas_opcoes,
    registrar_venda_opcao,
    atualizar_status_opcao,
    opcoes_para_dividendos_sinteticos,
    filtrar_opcoes,
    exportar_vendas_para_excel,
    calcular_estatisticas_opcoes,
    ARQ_VENDAS_OPCOES,
)

from modules.opcoes_net import (
    buscar_opcoes_opcoesnet_bovespa,
    carregar_cache_opcoesnet,
    salvar_cache_opcoesnet,
    exportar_opcoesnet_para_excel,
    LayoutOpcoesNetMudouError,
    listar_vencimentos_opcoesnet,
)


@st.cache_data(ttl=300, show_spinner=False)
def _listar_vencimentos_opcoesnet_cached(id_acao: str) -> list[dict]:
    id_acao = (id_acao or "").strip().upper()
    if not id_acao:
        return []
    return listar_vencimentos_opcoesnet(id_acao)

# Alguns símbolos foram adicionados recentemente ao módulo; em ambiente Streamlit
# pode existir cache de import durante hot-reload. Fazemos fallback com reload.
try:
    from modules.investimentos_manuais import calcular_caixa, excluir_caixa, excluir_acoes
except ImportError:
    import importlib
    import modules.investimentos_manuais as _im

    _im = importlib.reload(_im)
    calcular_caixa = _im.calcular_caixa
    excluir_caixa = _im.excluir_caixa
    excluir_acoes = _im.excluir_acoes

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

# Aplica estilo global SUPER AGRESSIVO para aumentar o tamanho de TODOS os cartões st.metric
st.markdown("""
<style>
/* Aumenta o tamanho dos cartões st.metric em 30% (0.72 → 0.936) */
[data-testid="stMetric"] {
    font-size: 0.936rem !important;
    padding: 0.5rem !important;
}
[data-testid="stMetric"] * {
    font-size: 0.936rem !important;
}
[data-testid="stMetric"] label {
    font-size: 0.936rem !important;
    margin-bottom: 0.2rem !important;
}
[data-testid="stMetricValue"] {
    font-size: 0.936rem !important;
}
[data-testid="stMetricDelta"] {
    font-size: 0.768rem !important;
}
div[data-testid="stMetricValue"] {
    font-size: 0.936rem !important;
}
</style>
""", unsafe_allow_html=True)

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


def _normalizar_df_caixa(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if "Mes" in out.columns and "Mês" not in out.columns:
        out = out.rename(columns={"Mes": "Mês"})
    if "Rentabilidade %" in out.columns and "Rentabilidade (%)" not in out.columns:
        out = out.rename(columns={"Rentabilidade %": "Rentabilidade (%)"})
    if "Nome Caixa" not in out.columns:
        out["Nome Caixa"] = "Caixa Principal"
    if "Usuário" not in out.columns:
        out["Usuário"] = "Manual"
    if "ID" not in out.columns:
        import uuid

        out["ID"] = [str(uuid.uuid4()) for _ in range(len(out))]
    if "Fechado" not in out.columns:
        out["Fechado"] = True
    for col in ["Valor Inicial", "Depósitos", "Saques", "Valor Final", "Rentabilidade (%)", "Ganho"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def _normalizar_df_caixa_movs(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if "Mes" in out.columns and "Mês" not in out.columns:
        out = out.rename(columns={"Mes": "Mês"})
    if "Nome Caixa" not in out.columns:
        out["Nome Caixa"] = "Caixa Principal"
    if "Usuário" not in out.columns:
        out["Usuário"] = "Manual"
    if "ID" not in out.columns:
        import uuid

        out["ID"] = [str(uuid.uuid4()) for _ in range(len(out))]
    if "Valor" in out.columns:
        out["Valor"] = pd.to_numeric(out["Valor"], errors="coerce")
    if "Data" in out.columns:
        out["Data"] = pd.to_datetime(out["Data"], errors="coerce")
    if "Tipo" in out.columns:
        out["Tipo"] = out["Tipo"].astype(str)
    return out


def carregar_caixa_fast() -> pd.DataFrame:
    # Usa cache por mtime (carregar_df_parquet já é cacheado via _read_parquet_cached)
    df = carregar_df_parquet(CAIXA_PATH)
    return _normalizar_df_caixa(df)


def carregar_caixa_movimentos_fast() -> pd.DataFrame:
    df = carregar_df_parquet(CAIXA_MOVS_PATH)
    return _normalizar_df_caixa_movs(df)

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
    
    # Armazenar mês selecionado em session_state para usar em outras abas (key diferente do widget)
    if chave_prefixo == "cons_geral" and mes_sel:
        st.session_state["cons_geral_mes_value"] = mes_sel
    
    # Aplicar filtros
    df_filtrado = df.copy()
    if mes_sel:
        df_filtrado = df_filtrado[df_filtrado["Mês/Ano"] == mes_sel]
    if usuarios_sel:
        df_filtrado = df_filtrado[df_filtrado["Usuário"].isin(usuarios_sel)]
    if tipos_sel:
        df_filtrado = df_filtrado[df_filtrado["Tipo"].isin(tipos_sel)]
    
    return df_filtrado

def exibir_metricas_valor(df, col_valor="Valor", salvar_no_session_state_key=None, df_mes_anterior=None, label_comparacao=None):
    """Exibe métricas de valor total e por tipo com comparação vs mês anterior
    
    Args:
        df: DataFrame atual
        col_valor: Nome da coluna de valor
        salvar_no_session_state_key: Key para salvar valor total no session_state
        df_mes_anterior: DataFrame do mês anterior para comparação
        label_comparacao: Label do mês de comparação (ex: "12/2025")
    """
    if df.empty or col_valor not in df.columns:
        return
    
    import unicodedata

    def _to_num_series(s: pd.Series) -> pd.Series:
        if s is None:
            return pd.Series(dtype="float")
        if not isinstance(s, pd.Series):
            s = pd.Series(s)
        if pd.api.types.is_numeric_dtype(s):
            return pd.to_numeric(s, errors="coerce")
        txt = s.astype(str)
        txt = (
            txt.str.replace("R$", "", regex=False)
            .str.replace("US$", "", regex=False)
            .str.replace("$", "", regex=False)
            .str.replace("%", "", regex=False)
            .str.replace("\u00a0", " ", regex=False)
            .str.replace(" ", "", regex=False)
        )
        # normaliza pt-BR/US: remove milhar e usa '.' como decimal
        txt = txt.str.replace(r"\.(?=\d{3}(\D|$))", "", regex=True)
        txt = txt.str.replace(",", ".", regex=False)
        return pd.to_numeric(txt, errors="coerce")

    def _norm_tipo(v) -> str:
        s = "" if pd.isna(v) else str(v)
        s = unicodedata.normalize("NFKD", s)
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
        s = " ".join(s.strip().split())
        return s.lower()

    # Valor total
    valor_total = _to_num_series(df[col_valor]).fillna(0).sum()
    
    # Calcular variação % vs mês anterior
    delta_total = None
    if df_mes_anterior is not None and not df_mes_anterior.empty and col_valor in df_mes_anterior.columns:
        valor_anterior = _to_num_series(df_mes_anterior[col_valor]).fillna(0).sum()
        if valor_anterior > 0:
            delta_total = ((valor_total - valor_anterior) / valor_anterior) * 100.0
    
    if delta_total is not None and label_comparacao:
        st.metric("💰 Valor Total", f"R$ {valor_total:,.2f}", f"{delta_total:+.2f}% vs {label_comparacao}")
    else:
        st.metric("💰 Valor Total", f"R$ {valor_total:,.2f}")
    
    # Salvar no session_state se solicitado
    if salvar_no_session_state_key:
        st.session_state[salvar_no_session_state_key] = float(valor_total)
    
    # Por tipo se disponível
    if "Tipo" in df.columns:
        df_tmp = df.copy()
        df_tmp["_tipo_norm"] = df_tmp["Tipo"].apply(_norm_tipo)
        df_prev = None
        if df_mes_anterior is not None and not df_mes_anterior.empty and "Tipo" in df_mes_anterior.columns:
            df_prev = df_mes_anterior.copy()
            df_prev["_tipo_norm"] = df_prev["Tipo"].apply(_norm_tipo)

        tipos = df_tmp["Tipo"].dropna().unique()
        if len(tipos) > 1:
            st.subheader("Por Tipo")
            cols = st.columns(min(len(tipos), 5))
            for idx, tipo in enumerate(sorted(tipos)):
                with cols[idx % 5]:
                    tipo_norm = _norm_tipo(tipo)
                    valor_tipo = pd.to_numeric(
                        df_tmp[df_tmp["_tipo_norm"] == tipo_norm][col_valor],
                        errors="coerce",
                    )
                    valor_tipo = _to_num_series(valor_tipo).fillna(0).sum()
                    
                    # Calcular variação % vs mês anterior para este tipo
                    delta_tipo = None
                    if df_prev is not None and col_valor in df_prev.columns:
                        valor_tipo_anterior = pd.to_numeric(
                            df_prev[df_prev["_tipo_norm"] == tipo_norm][col_valor],
                            errors="coerce",
                        )
                        valor_tipo_anterior = _to_num_series(valor_tipo_anterior).fillna(0).sum()
                        if valor_tipo_anterior > 0:
                            delta_tipo = ((valor_tipo - valor_tipo_anterior) / valor_tipo_anterior) * 100.0
                    
                    if delta_tipo is not None and label_comparacao:
                        st.metric(tipo, f"R$ {valor_tipo:,.2f}", f"{delta_tipo:+.2f}% vs {label_comparacao}")
                    else:
                        st.metric(tipo, f"R$ {valor_tipo:,.2f}")

def gerar_graficos_distribuicao(df, col_valor="Valor", cores="Blues", key_prefixo="dist"):
    """Gera gráficos de pizza e barras para distribuição"""
    if df.empty or "Tipo" not in df.columns:
        return
    
    st.subheader("📊 Distribuição")
    

    col_pie1, col_pie2 = st.columns(2)

    with col_pie1:
        st.markdown("<div style='display:flex;align-items:center;gap:0.5em;'><h5 style='margin-bottom:0;margin-top:0;'>Distribuição por Tipo</h5></div>", unsafe_allow_html=True)
        dist_tipo = df.groupby("Tipo")[col_valor].sum()
        # Degrade: maior valor = cor mais escura
        paleta = getattr(px.colors.sequential, cores)[::-1]
        fig_pie = px.pie(
            names=dist_tipo.index,
            values=dist_tipo.values,
            hole=0.3,
            color_discrete_sequence=paleta,
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
                # Degrade: maior valor = cor mais escura
                paleta_dim = getattr(px.colors.sequential, cores)[::-1]
                fig_pie_dim = px.pie(
                    names=dist_dim.index,
                    values=dist_dim.values,
                    hole=0.3,
                    color_discrete_sequence=paleta_dim,
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
            # Usar a mesma paleta de cores passada como parâmetro (Blues, Greens, Purples, etc)
            paleta_bar = getattr(px.colors.sequential, cores)[::-1]  # maior = cor mais escura
            n = len(top_ativos)
            valores = np.array(top_ativos.values)
            norm = (valores - valores.min()) / (valores.max() - valores.min()) if valores.max() > valores.min() else np.full(n, 0.5)
            bar_colors = sample_colorscale(paleta_bar[::-1], norm)
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

def gerar_graficos_evolucao(
    df: pd.DataFrame,
    coluna_valor: str = "Valor Líquido",
    coluna_data: str = "Data",
    chave_periodo: str = "periodo",
    serie_posicao_mensal: pd.Series | None = None,
):
    """Gera gráficos de evolução de proventos (barras, linha e crescimento %).

    Se `serie_posicao_mensal` for informada (índice "YYYY-MM"), adiciona um gráfico de linha
    de Dividend Yield (%) acima do gráfico de barras (compartilhando o mesmo eixo X) quando
    o período selecionado for Mensal.
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

        # Gráfico de barras com média móvel
        st.subheader("Gráfico de Barras - Valor Recebido")
        
        # Seletor de período para média móvel
        col_mm1, col_mm2 = st.columns([3, 1])
        with col_mm1:
            st.write("")
        with col_mm2:
            periodo_mm = st.selectbox("Média Móvel", ["Sem MM", "3 meses", "6 meses", "9 meses", "12 meses"], key=f"{chave_periodo}_mm_selector")
        
        max_val = df_group.values.max() if len(df_group.values) else 0
        from plotly.colors import sample_colorscale
        blues = px.colors.sequential.Blues  # maior valor = azul mais escuro
        n = len(df_group)
        valores = np.array(df_group.values)
        norm = (valores - valores.min()) / (valores.max() - valores.min()) if valores.max() > valores.min() else np.full(n, 0.5)
        bar_colors = sample_colorscale(blues, norm)
        # Se houver base de posição mensal, montar subplots (Yield + Barras) bem colados e com o mesmo eixo X
        usar_yield = (serie_posicao_mensal is not None) and (periodo == "Mensal")
        if usar_yield:
            try:
                s_pos = serie_posicao_mensal.copy()
                if not isinstance(s_pos, pd.Series):
                    s_pos = pd.Series(s_pos)
                s_pos.index = s_pos.index.astype(str)
                s_pos = pd.to_numeric(s_pos, errors="coerce")
                s_pos = s_pos.reindex(df_group.index).fillna(0.0)

                div_vals = pd.to_numeric(pd.Series(df_group.values, index=df_group.index), errors="coerce").fillna(0.0)
                dy = np.where(s_pos.values > 0, (div_vals.values / s_pos.values) * 100.0, np.nan)

                fig_bar = make_subplots(
                    rows=2,
                    cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.02,
                    row_heights=[0.35, 0.65],
                )

                fig_bar.add_trace(
                    go.Scatter(
                        x=df_group.index,
                        y=dy,
                        mode="lines+markers",
                        name="Dividend Yield (%)",
                        hovertemplate="%{x}<br>Yield: %{y:.2f}%<extra></extra>",
                    ),
                    row=1,
                    col=1,
                )

                fig_bar.add_trace(
                    go.Bar(
                        x=df_group.index,
                        y=df_group.values,
                        name=coluna_valor,
                        marker_color=bar_colors,
                        text=[f"{v:,.2f}" for v in df_group.values],
                        textposition="outside",
                        cliponaxis=False,
                        hovertemplate="%{x}<br>Valor: R$ %{y:,.2f}<extra></extra>",
                    ),
                    row=2,
                    col=1,
                )

                # Formatação eixos
                fig_bar.update_yaxes(title_text="Dividend Yield (%)", ticksuffix="%", tickformat=".2f", row=1, col=1)
                fig_bar.update_yaxes(title_text=coluna_valor, tickformat=",.2f", row=2, col=1)
            except Exception:
                usar_yield = False

        if not usar_yield:
            fig_bar = px.bar(
                x=df_group.index,
                y=df_group.values,
                labels={"x": "Período", "y": coluna_valor},
                text=[f"{v:,.2f}" for v in df_group.values],
                color_discrete_sequence=bar_colors
            )
            fig_bar.update_traces(textposition="outside", cliponaxis=False, marker_color=bar_colors)
        
        # Adicionar linha de média móvel se selecionada
        if periodo_mm != "Sem MM":
            periodo_num = int(periodo_mm.split()[0])
            mm_values = pd.Series(df_group.values).rolling(window=periodo_num, center=False, min_periods=1).mean()
            trace_mm = go.Scatter(
                x=df_group.index,
                y=mm_values,
                mode="lines+markers",
                name=f"MM {periodo_num}m",
                line=dict(color="red", width=3, dash="dash"),
                marker=dict(size=6),
                hovertemplate="%{x}<br>MM: R$ %{y:,.2f}<extra></extra>",
            )

            # Quando o gráfico está em subplots (Yield + Barras), a MM deve ficar no painel das barras.
            if "make_subplots" in str(type(fig_bar)) and usar_yield:
                fig_bar.add_trace(trace_mm, row=2, col=1)
            else:
                fig_bar.add_trace(trace_mm)
        
        fig_bar.update_layout(
            xaxis_tickmode="array",
            xaxis_tickvals=list(df_group.index),
            xaxis_ticktext=list(df_group.index),
            margin=dict(t=60),
            hovermode="x unified",
            showlegend=False,
        )
        if max_val > 0:
            # Ajusta apenas o eixo do valor (barras)
            try:
                if usar_yield:
                    fig_bar.update_yaxes(range=[0, max_val * 1.15], row=2, col=1)
                else:
                    fig_bar.update_yaxes(range=[0, max_val * 1.15])
            except Exception:
                pass
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
        # Padrão pedido: quando Mensal, usar azul; quando Anual, manter roxo.
        paleta = (px.colors.sequential.Blues[::-1] if tipo_periodo == "Mensal" else px.colors.sequential.Purples[::-1])
        n = len(top_ativos)
        valores = np.array(top_ativos.values)
        norm = (valores - valores.min()) / (valores.max() - valores.min()) if valores.max() > valores.min() else np.full(n, 0.5)
        bar_colors = sample_colorscale(paleta, norm)
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
usuarios_list = sorted(df_usuarios.get("Nome", pd.Series()).dropna().unique().tolist()) if not df_usuarios.empty else []

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


def _parse_mes_ano_to_period_global(mes_ano) -> pd.Period | None:
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


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def _yf_close_mensal(sym: str) -> pd.Series:
    sym = (sym or "").strip()
    if not sym:
        return pd.Series(dtype=float)
    try:
        hist = yf.Ticker(sym).history(period="max", interval="1d", auto_adjust=False)
        if not isinstance(hist, pd.DataFrame) or hist.empty or "Close" not in hist.columns:
            return pd.Series(dtype=float)
        s = pd.to_numeric(hist["Close"], errors="coerce")
        s.index = pd.to_datetime(s.index, errors="coerce")
        s = s[~s.index.isna()].copy()
        if s.empty:
            return pd.Series(dtype=float)
        s_m = s.resample("M").last().dropna()
        s_m.index = s_m.index.to_period("M")
        return s_m
    except Exception:
        return pd.Series(dtype=float)


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def _fx_mensal(moeda: str) -> pd.Series:
    m = (moeda or "").strip().upper()
    if not m or m == "BRL":
        return pd.Series(dtype=float)
    idx = None
    if m == "USD":
        idx = "USD/BRL"
    elif m == "EUR":
        idx = "EUR/BRL"
    if not idx:
        return pd.Series(dtype=float)
    try:
        hist = obter_historico_indice(idx, periodo="max", intervalo="1d")
        if hist is None or hist.empty:
            return pd.Series(dtype=float)
        h = hist.copy()
        # Alguns retornos vêm com coluna 'Date' ao invés de índice de datas
        if "Date" in h.columns:
            h["Date"] = pd.to_datetime(h["Date"], errors="coerce")
            h = h[h["Date"].notna()].copy()
            h = h.set_index("Date")

        close = pd.to_numeric(h.get("Close"), errors="coerce")
        close.index = pd.to_datetime(close.index, errors="coerce")
        # Remove timezone se existir
        try:
            if hasattr(close.index, "tz") and close.index.tz is not None:
                close.index = close.index.tz_localize(None)
        except Exception:
            pass

        close = close[~close.index.isna()].copy()
        close_m = close.resample("M").last().dropna()
        close_m.index = close_m.index.to_period("M")
        return close_m
    except Exception:
        return pd.Series(dtype=float)


def _ler_json_safe(path: str) -> dict:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
                return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}
    return {}


def _salvar_json_safe(path: str, obj: dict) -> None:
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj or {}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _mtime_or_none(path: str):
    try:
        return os.path.getmtime(path) if path and os.path.exists(path) else None
    except Exception:
        return None


def _load_or_build_parquet_cached(
    parquet_path: str,
    meta_path: str,
    meta_new: dict,
    build_fn,
) -> pd.DataFrame:
    meta_old = _ler_json_safe(meta_path)
    if meta_old == meta_new and os.path.exists(parquet_path):
        return carregar_df_parquet(parquet_path)
    df = build_fn()
    try:
        os.makedirs(os.path.dirname(parquet_path) or ".", exist_ok=True)
        if isinstance(df, pd.DataFrame):
            df.to_parquet(parquet_path, index=False)
        _salvar_json_safe(meta_path, meta_new)
    except Exception:
        pass
    return df if isinstance(df, pd.DataFrame) else pd.DataFrame()


def _preco_compra_overrides(df_lotes: pd.DataFrame) -> pd.DataFrame:
    """Retorna preços de compra para usar no mês da compra (média ponderada por quantidade).

    Saída: colunas [Ticker_YF, Moeda, Periodo, Preço Compra]
    """
    if df_lotes is None or df_lotes.empty:
        return pd.DataFrame(columns=["Ticker_YF", "Moeda", "Periodo", "Preço Compra"])

    df = df_lotes.copy()
    if "Preço Compra" not in df.columns:
        return pd.DataFrame(columns=["Ticker_YF", "Moeda", "Periodo", "Preço Compra"])

    if "Mês Compra" not in df.columns and "Mês/Ano" in df.columns:
        df["Mês Compra"] = df["Mês/Ano"].astype(str)
    if "Quantidade Compra" not in df.columns and "Quantidade" in df.columns:
        df["Quantidade Compra"] = pd.to_numeric(df["Quantidade"], errors="coerce")

    df["Preço Compra"] = pd.to_numeric(df.get("Preço Compra"), errors="coerce").fillna(0.0)
    df["Quantidade Compra"] = pd.to_numeric(df.get("Quantidade Compra"), errors="coerce").fillna(0.0)
    df["Ticker_YF"] = df.get("Ticker_YF", "").astype(str).str.strip()
    df["Moeda"] = df.get("Moeda", "BRL").fillna("BRL").astype(str).str.strip().str.upper()

    p_compra = df["Mês Compra"].apply(_parse_mes_ano_to_period_global)
    df = df[p_compra.notna()].copy()
    if df.empty:
        return pd.DataFrame(columns=["Ticker_YF", "Moeda", "Periodo", "Preço Compra"])
    df["Periodo"] = p_compra[p_compra.notna()].astype("period[M]")

    df = df[(df["Preço Compra"] > 0) & (df["Quantidade Compra"] > 0) & (df["Ticker_YF"].astype(str).str.len() > 0)].copy()
    if df.empty:
        return pd.DataFrame(columns=["Ticker_YF", "Moeda", "Periodo", "Preço Compra"])

    df["_WSum"] = df["Preço Compra"] * df["Quantidade Compra"]
    grp = (
        df.groupby(["Ticker_YF", "Moeda", "Periodo"], as_index=False)
        .agg(Qty=("Quantidade Compra", "sum"), WSum=("_WSum", "sum"))
    )
    grp["Preço Compra"] = np.where(grp["Qty"] > 0, grp["WSum"] / grp["Qty"], np.nan)
    out = grp[["Ticker_YF", "Moeda", "Periodo", "Preço Compra"]].copy()
    out["Preço Compra"] = pd.to_numeric(out["Preço Compra"], errors="coerce")
    out = out.dropna(subset=["Preço Compra"]).copy()
    return out


def acoes_manuais_para_consolidado_mensal(df_acoes_lotes: pd.DataFrame) -> pd.DataFrame:
    if df_acoes_lotes is None or df_acoes_lotes.empty:
        return pd.DataFrame()

    df = df_acoes_lotes.copy()
    if "Usuário" not in df.columns:
        df["Usuário"] = "Manual"
    df["Usuário"] = df["Usuário"].fillna("Manual").astype(str)

    # Campos do schema novo (lotes)
    if "Mês Compra" not in df.columns and "Mês/Ano" in df.columns:
        df["Mês Compra"] = df["Mês/Ano"].astype(str)
    if "Quantidade Compra" not in df.columns and "Quantidade" in df.columns:
        df["Quantidade Compra"] = pd.to_numeric(df["Quantidade"], errors="coerce")
    if "Mês Venda" not in df.columns:
        df["Mês Venda"] = ""
    if "Quantidade Venda" not in df.columns:
        df["Quantidade Venda"] = 0.0

    df["Quantidade Compra"] = pd.to_numeric(df.get("Quantidade Compra"), errors="coerce").fillna(0.0)
    df["Quantidade Venda"] = pd.to_numeric(df.get("Quantidade Venda"), errors="coerce").fillna(0.0)

    # Normalizar ticker/símbolo/moeda
    df["Ticker"] = df.get("Ticker", "").astype(str).str.strip().str.upper()
    df["Ticker_YF"] = df.get("Ticker_YF", "").astype(str).str.strip()
    df["Moeda"] = df.get("Moeda", "BRL").fillna("BRL").astype(str).str.strip().str.upper()

    from modules.historico_acoes_manuais import expand_lotes_para_posicao_mensal

    pos = expand_lotes_para_posicao_mensal(df)
    if pos.empty:
        return pd.DataFrame()

    overrides = _preco_compra_overrides(df)

    # Preço mensal + FX mensal (converte para BRL, igual o consolidado de Ações Dólar do app)
    precos = []
    for sym, moeda in pos[["Ticker_YF", "Moeda"]].drop_duplicates().itertuples(index=False):
        sym2 = (sym or "").strip()
        if not sym2:
            continue
        close = _yf_close_mensal(sym2)
        if close.empty:
            continue
        fx = _fx_mensal(moeda)
        if moeda == "BRL" or fx.empty:
            preco_brl = close
        else:
            fx_alinhado = fx.reindex(close.index).ffill().bfill()
            fx_alinhado = pd.to_numeric(fx_alinhado, errors="coerce").fillna(1.0)
            preco_brl = close.mul(fx_alinhado)
        dfp = pd.DataFrame({
            "Ticker_YF": sym2,
            "Moeda": moeda,
            "Periodo": preco_brl.index,
            "Preço": pd.to_numeric(preco_brl.values, errors="coerce"),
        })
        precos.append(dfp)

    df_preco = pd.concat(precos, ignore_index=True) if precos else pd.DataFrame(columns=["Ticker_YF", "Moeda", "Periodo", "Preço"])

    # Aplica override no mês da compra (convertendo para BRL se necessário)
    if not overrides.empty:
        ov = overrides.copy()
        ov["Preço"] = pd.to_numeric(ov["Preço Compra"], errors="coerce")
        ov["FX"] = 1.0
        for m in ov["Moeda"].dropna().unique().tolist():
            m2 = (m or "").upper()
            if m2 == "BRL":
                continue
            fxm = _fx_mensal(m2)
            if fxm.empty:
                continue
            fx_map = fxm.to_dict()
            mask = ov["Moeda"].astype(str).str.upper() == m2
            ov.loc[mask, "FX"] = ov.loc[mask, "Periodo"].map(fx_map)
        ov["FX"] = pd.to_numeric(ov["FX"], errors="coerce").fillna(1.0)
        ov["Preço"] = (pd.to_numeric(ov["Preço"], errors="coerce") * ov["FX"]).astype(float)
        ov2 = ov[["Ticker_YF", "Moeda", "Periodo", "Preço"]].copy()

        df_preco = df_preco.merge(ov2, on=["Ticker_YF", "Moeda", "Periodo"], how="outer", suffixes=("", "_override"))
        if "Preço_override" in df_preco.columns:
            df_preco["Preço"] = pd.to_numeric(df_preco["Preço_override"], errors="coerce").combine_first(
                pd.to_numeric(df_preco["Preço"], errors="coerce")
            )
            df_preco = df_preco.drop(columns=["Preço_override"], errors="ignore")

    pos = pos.merge(df_preco, on=["Ticker_YF", "Moeda", "Periodo"], how="left")
    pos["Preço"] = pd.to_numeric(pos.get("Preço"), errors="coerce")
    pos["Valor"] = (pd.to_numeric(pos["Quantidade"], errors="coerce").fillna(0.0) * pos["Preço"]).fillna(0.0)

    # Tipo (para filtros)
    def _tipo_por_moeda(m: str) -> str:
        m = (m or "").upper()
        if m == "USD":
            return "Ações Dólar"
        if m == "EUR":
            return "Ações Euro"
        return "Ações"

    pos["Tipo"] = pos["Moeda"].apply(_tipo_por_moeda)
    pos["Ativo"] = pos["Ticker"]
    pos["Mês/Ano"] = pos["Periodo"].dt.strftime("%m/%Y")
    pos["Fonte"] = "Manual Ações"

    cols = ["Ativo", "Ticker", "Quantidade", "Preço", "Valor", "Tipo", "Usuário", "Mês/Ano", "Fonte", "Moeda"]
    return pos[cols].copy()


def acoes_manuais_para_posicao_atual(df_acoes_lotes: pd.DataFrame) -> pd.DataFrame:
    """Gera base mensal para Posição Atual mantendo o preço na moeda original.

    - Para USD: Preço em USD e Moeda='USD' (igual o fluxo de Ações Dólar em USD na aba Posição Atual)
    - Para BRL: Preço em BRL e Moeda='BRL'
    """
    if df_acoes_lotes is None or df_acoes_lotes.empty:
        return pd.DataFrame()

    df = df_acoes_lotes.copy()
    if "Usuário" not in df.columns:
        df["Usuário"] = "Manual"
    df["Usuário"] = df["Usuário"].fillna("Manual").astype(str)

    if "Mês Compra" not in df.columns and "Mês/Ano" in df.columns:
        df["Mês Compra"] = df["Mês/Ano"].astype(str)
    if "Quantidade Compra" not in df.columns and "Quantidade" in df.columns:
        df["Quantidade Compra"] = pd.to_numeric(df["Quantidade"], errors="coerce")
    if "Mês Venda" not in df.columns:
        df["Mês Venda"] = ""
    if "Quantidade Venda" not in df.columns:
        df["Quantidade Venda"] = 0.0

    df["Quantidade Compra"] = pd.to_numeric(df.get("Quantidade Compra"), errors="coerce").fillna(0.0)
    df["Quantidade Venda"] = pd.to_numeric(df.get("Quantidade Venda"), errors="coerce").fillna(0.0)

    df["Ticker"] = df.get("Ticker", "").astype(str).str.strip().str.upper()
    df["Ticker_YF"] = df.get("Ticker_YF", "").astype(str).str.strip()
    df["Moeda"] = df.get("Moeda", "BRL").fillna("BRL").astype(str).str.strip().str.upper()

    from modules.historico_acoes_manuais import expand_lotes_para_posicao_mensal

    pos = expand_lotes_para_posicao_mensal(df)
    if pos.empty:
        return pd.DataFrame()

    overrides = _preco_compra_overrides(df)

    # Preço mensal na moeda original (sem FX)
    precos = []
    for sym, moeda in pos[["Ticker_YF", "Moeda"]].drop_duplicates().itertuples(index=False):
        sym2 = (sym or "").strip()
        if not sym2:
            continue
        close = _yf_close_mensal(sym2)
        if close.empty:
            continue
        dfp = pd.DataFrame({
            "Ticker_YF": sym2,
            "Moeda": moeda,
            "Periodo": close.index,
            "Preço": pd.to_numeric(close.values, errors="coerce"),
        })
        precos.append(dfp)

    df_preco = pd.concat(precos, ignore_index=True) if precos else pd.DataFrame(columns=["Ticker_YF", "Moeda", "Periodo", "Preço"])

    if not overrides.empty:
        ov2 = overrides.rename(columns={"Preço Compra": "Preço"})[["Ticker_YF", "Moeda", "Periodo", "Preço"]].copy()
        df_preco = df_preco.merge(ov2, on=["Ticker_YF", "Moeda", "Periodo"], how="outer", suffixes=("", "_override"))
        if "Preço_override" in df_preco.columns:
            df_preco["Preço"] = pd.to_numeric(df_preco["Preço_override"], errors="coerce").combine_first(
                pd.to_numeric(df_preco["Preço"], errors="coerce")
            )
            df_preco = df_preco.drop(columns=["Preço_override"], errors="ignore")
    pos = pos.merge(df_preco, on=["Ticker_YF", "Moeda", "Periodo"], how="left")

    def _tipo_por_moeda(m: str) -> str:
        m = (m or "").upper()
        if m == "USD":
            return "Ações Dólar"
        if m == "EUR":
            return "Ações Euro"
        return "Ações"

    pos["Tipo"] = pos["Moeda"].apply(_tipo_por_moeda)
    pos["Ativo"] = pos["Ticker"]
    pos["Mês/Ano"] = pos["Periodo"].dt.strftime("%m/%Y")
    pos["Fonte"] = "Manual Ações"

    # Valor em moeda original (serve como Valor Base; atualização converte se USD)
    pos["Valor"] = (pd.to_numeric(pos["Quantidade"], errors="coerce").fillna(0.0) * pd.to_numeric(pos.get("Preço"), errors="coerce")).fillna(0.0)

    cols = ["Ativo", "Ticker", "Quantidade", "Preço", "Valor", "Tipo", "Usuário", "Mês/Ano", "Fonte", "Moeda"]
    return pos[cols].copy()


def carregar_acoes_hist_mensal_cached(df_acoes_lotes: pd.DataFrame) -> pd.DataFrame:
    """Histórico mensal (Preço/Valor em BRL) persistido em parquet.

    Recalcula apenas quando o parquet de lotes muda (edições) ou quando muda o mês corrente.
    """
    PARQUET_PATH = "data/investimentos_manuais_acoes_hist_mensal.parquet"
    META_PATH = "data/investimentos_manuais_acoes_hist_mensal_meta.json"
    meta_new = {
        "schema_version": 3,
        "acoes_manuais_mtime": _mtime_or_none(ACOES_MANUAIS_PATH),
        "current_ym": datetime.now().strftime("%Y-%m"),
    }
    return _load_or_build_parquet_cached(
        parquet_path=PARQUET_PATH,
        meta_path=META_PATH,
        meta_new=meta_new,
        build_fn=lambda: acoes_manuais_para_consolidado_mensal(df_acoes_lotes),
    )


def carregar_acoes_posicao_cached(df_acoes_lotes: pd.DataFrame) -> pd.DataFrame:
    """Base mensal para Posição Atual (Preço/Valor na moeda original) persistida em parquet."""
    PARQUET_PATH = "data/investimentos_manuais_acoes_posicao.parquet"
    META_PATH = "data/investimentos_manuais_acoes_posicao_meta.json"
    meta_new = {
        "schema_version": 3,
        "acoes_manuais_mtime": _mtime_or_none(ACOES_MANUAIS_PATH),
        "current_ym": datetime.now().strftime("%Y-%m"),
    }
    return _load_or_build_parquet_cached(
        parquet_path=PARQUET_PATH,
        meta_path=META_PATH,
        meta_new=meta_new,
        build_fn=lambda: acoes_manuais_para_posicao_atual(df_acoes_lotes),
    )


def carregar_caixa_hist_full_cached(df_caixa: pd.DataFrame) -> pd.DataFrame:
    """Histórico completo de caixa com Rentabilidade Acumulada (%) persistido em parquet."""
    PARQUET_PATH = "data/investimentos_manuais_caixa_hist_full.parquet"
    META_PATH = "data/investimentos_manuais_caixa_hist_full_meta.json"
    meta_new = {
        "schema_version": 1,
        "caixa_mtime": _mtime_or_none(CAIXA_PATH),
    }

    def _build() -> pd.DataFrame:
        if df_caixa is None or df_caixa.empty:
            return pd.DataFrame()
        d = df_caixa.copy()
        if "Mês" in d.columns:
            d["Mês"] = d["Mês"].astype(str)
            d["_DataMes"] = pd.to_datetime("01/" + d["Mês"].astype(str), format="%d/%m/%Y", errors="coerce")
        if "Rentabilidade (%)" in d.columns:
            d["Rentabilidade (%)"] = pd.to_numeric(d["Rentabilidade (%)"], errors="coerce").fillna(0.0)

        sort_cols = [c for c in ["Usuário", "Nome Caixa", "_DataMes"] if c in d.columns]
        if sort_cols:
            d = d.sort_values(sort_cols).copy()

        group_cols = [c for c in ["Usuário", "Nome Caixa"] if c in d.columns]
        if "Rentabilidade (%)" in d.columns:
            if group_cols:
                d["Rentabilidade Acumulada (%)"] = (
                    (1 + (d["Rentabilidade (%)"] / 100.0)).groupby([d[c] for c in group_cols]).cumprod() - 1
                ) * 100.0
            else:
                d["Rentabilidade Acumulada (%)"] = ((1 + (d["Rentabilidade (%)"] / 100.0)).cumprod() - 1) * 100.0

        if "_DataMes" in d.columns:
            d = d.drop(columns=["_DataMes"], errors="ignore")
        return d

    return _load_or_build_parquet_cached(
        parquet_path=PARQUET_PATH,
        meta_path=META_PATH,
        meta_new=meta_new,
        build_fn=_build,
    )

# Dividendos sintéticos de opções
df_dividendos_opcoes = opcoes_para_dividendos_sinteticos()

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


@st.cache_data(ttl=120, show_spinner=False)
def _obter_preco_atual_acao_yf_cached(ticker_base: str) -> float | None:
    """Obtém o último Close disponível via yfinance para o ativo base."""
    try:
        import yfinance as yf

        tk = ticker_para_yf((ticker_base or "").strip().upper())
        if not tk:
            return None
        hist = yf.Ticker(tk).history(period="5d")
        if hist is None or hist.empty or "Close" not in hist.columns:
            return None
        close = pd.to_numeric(hist["Close"], errors="coerce").dropna()
        if close.empty:
            return None
        return float(close.iloc[-1])
    except Exception:
        return None


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
df_dividendos_opcoes_cons = preparar_dividendos_consolidado(df_dividendos_opcoes, "Dividendos Sintéticos (Opções)")
df_dividendos_consolidado = pd.concat([
    df_dividendos_br_cons, 
    df_dividendos_avenue_cons, 
    df_dividendos_caixa_cons,
    df_dividendos_opcoes_cons
], ignore_index=True)

# Separar por tipo
df_acoes_br = df_padronizado[df_padronizado["Tipo"] == "Ações"].copy() if not df_padronizado.empty else pd.DataFrame()
df_renda_fixa = df_padronizado[df_padronizado["Tipo"] == "Renda Fixa"].copy() if not df_padronizado.empty else pd.DataFrame()
df_tesouro = df_padronizado[df_padronizado["Tipo"] == "Tesouro Direto"].copy() if not df_padronizado.empty else pd.DataFrame()

# ========== INTERFACE COM TABS REORGANIZADAS ==========

tab_acoes, tab_renda_fixa, tab_proventos, tab_opcoes, tab_consolidacao, tab_posicao, tab_outros = st.tabs([
    "📈 Ações",
    "💵 Renda Fixa",
    "💸 Proventos",
    "🎯 Opções",
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
        aba_acoes_avenue(exibir_metricas_valor_fn=exibir_metricas_valor)
    
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

            # Gráfico por fonte (Usuário extraído de Fonte)
            if "Usuário" in df_dividendos_br.columns and "Valor Líquido" in df_dividendos_br.columns:
                st.markdown("---")
                st.subheader("📊 Distribuição por Fonte")
                dist_fonte_br = (
                    df_dividendos_br.groupby("Usuário")["Valor Líquido"]
                    .sum()
                    .sort_values(ascending=False)
                )
                paleta = px.colors.sequential.Blues  # maior valor = azul mais escuro
                from plotly.colors import sample_colorscale
                n = len(dist_fonte_br)
                valores = dist_fonte_br.values
                norm = (valores - valores.min()) / (valores.max() - valores.min()) if valores.max() > valores.min() else [0.5] * n
                pie_colors = sample_colorscale(paleta, norm)
                fig_pie_fonte_br = px.pie(
                    names=dist_fonte_br.index,
                    values=dist_fonte_br.values,
                    title="Distribuição por Fonte",
                    hole=0.3,
                    labels={"names": "Fonte", "values": "Valor Líquido"},
                    color_discrete_sequence=pie_colors,
                )
                fig_pie_fonte_br.update_traces(
                    textinfo="label+percent+value",
                    texttemplate="%{label}<br>R$%{value:,.2f} (%{percent})",
                )
                st.plotly_chart(fig_pie_fonte_br, use_container_width=True, key="div_br_pie_fonte")
            
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
            # ===== Filtrar esta página para proventos apenas de Ações (BRL/USD/EUR) =====
            TIPOS_ACOES = {"Ações", "Ações Dólar", "Ações Euro"}

            def _to_num_series_local(s: pd.Series) -> pd.Series:
                if s is None:
                    return pd.Series(dtype="float")
                if not isinstance(s, pd.Series):
                    s = pd.Series(s)
                if pd.api.types.is_numeric_dtype(s):
                    return pd.to_numeric(s, errors="coerce")
                txt = s.astype(str)
                txt = (
                    txt.str.replace("R$", "", regex=False)
                    .str.replace("US$", "", regex=False)
                    .str.replace("$", "", regex=False)
                    .str.replace("%", "", regex=False)
                    .str.replace("\u00a0", " ", regex=False)
                    .str.replace(" ", "", regex=False)
                )
                txt = txt.str.replace(r"\.(?=\d{3}(\D|$))", "", regex=True)
                txt = txt.str.replace(",", ".", regex=False)
                return pd.to_numeric(txt, errors="coerce")

            def _ticker_curto_local(v) -> str:
                t = extrair_ticker(v)
                t = "" if t is None else str(t).strip().upper()
                if t.endswith(".SA"):
                    t = t[:-3]
                return t

            # Base de posição mensal (BRL) para calcular Dividend Yield
            pos_parts = []
            if not df_padronizado.empty and "Tipo" in df_padronizado.columns:
                d0 = df_padronizado[df_padronizado["Tipo"].isin(list(TIPOS_ACOES))].copy()
                if not d0.empty:
                    if "Valor" not in d0.columns and "Valor de Mercado" in d0.columns:
                        d0["Valor"] = d0["Valor de Mercado"]
                    pos_parts.append(d0)

            if not df_acoes_avenue_padrao.empty:
                d1 = df_acoes_avenue_padrao.copy()
                if "Tipo" in d1.columns:
                    d1 = d1[d1["Tipo"].isin(list(TIPOS_ACOES))].copy()
                pos_parts.append(d1)

            df_acoes_manuais_hist_brl = pd.DataFrame()
            if df_manual_acoes is not None and not df_manual_acoes.empty:
                try:
                    df_acoes_manuais_hist_brl = carregar_acoes_hist_mensal_cached(df_manual_acoes)
                except Exception:
                    df_acoes_manuais_hist_brl = pd.DataFrame()
            if df_acoes_manuais_hist_brl is not None and not df_acoes_manuais_hist_brl.empty:
                d2 = df_acoes_manuais_hist_brl.copy()
                if "Tipo" in d2.columns:
                    d2 = d2[d2["Tipo"].isin(list(TIPOS_ACOES))].copy()
                pos_parts.append(d2)

            df_pos_acoes = pd.concat(pos_parts, ignore_index=True) if pos_parts else pd.DataFrame()
            if not df_pos_acoes.empty:
                if "Ticker" not in df_pos_acoes.columns and "Ativo" in df_pos_acoes.columns:
                    df_pos_acoes["Ticker"] = df_pos_acoes["Ativo"].apply(_ticker_curto_local)
                else:
                    df_pos_acoes["Ticker"] = df_pos_acoes.get("Ticker").apply(_ticker_curto_local)

                if "Mês/Ano" in df_pos_acoes.columns:
                    dt_mes = pd.to_datetime("01/" + df_pos_acoes["Mês/Ano"].astype(str), format="%d/%m/%Y", errors="coerce")
                    df_pos_acoes["PeriodoStr"] = dt_mes.dt.to_period("M").astype(str)
                else:
                    df_pos_acoes["PeriodoStr"] = None

                if "Valor" not in df_pos_acoes.columns and "Valor de Mercado" in df_pos_acoes.columns:
                    df_pos_acoes["Valor"] = df_pos_acoes["Valor de Mercado"]
                df_pos_acoes["Valor"] = _to_num_series_local(df_pos_acoes.get("Valor"))

                df_pos_acoes = df_pos_acoes[df_pos_acoes["Ticker"].astype(str).str.strip() != ""].copy()
                df_pos_acoes = df_pos_acoes[df_pos_acoes["PeriodoStr"].notna()].copy()

            tickers_pos = set(df_pos_acoes["Ticker"].dropna().astype(str).str.upper().tolist()) if not df_pos_acoes.empty else set()

            # Fallback adicional via cache de ticker_info (quando existir)
            tickers_cache = set()
            try:
                cache_df = carregar_cache_ticker_info()
                if not cache_df.empty and "Ticker" in cache_df.columns:
                    cache_df = cache_df.copy()
                    cache_df["Ticker"] = cache_df["Ticker"].astype(str).str.strip().str.upper()
                    qt = cache_df.get("QuoteType")
                    if qt is not None:
                        qt = qt.astype(str).str.strip().str.upper()
                        cache_df = cache_df[qt.isin(["EQUITY", "ETF"])]
                    tickers_cache = set(cache_df["Ticker"].dropna().tolist())
            except Exception:
                tickers_cache = set()

            # Aplicar filtro de ações ao consolidado de proventos
            df_base_prov = df_dividendos_consolidado.copy()
            if "Ativo" in df_base_prov.columns:
                df_base_prov["Ticker"] = df_base_prov["Ativo"].apply(_ticker_curto_local)
            elif "Ticker" in df_base_prov.columns:
                df_base_prov["Ticker"] = df_base_prov["Ticker"].apply(_ticker_curto_local)
            else:
                df_base_prov["Ticker"] = ""

            tickers_validos = tickers_pos.union(tickers_cache)
            df_base_prov = df_base_prov[df_base_prov["Ticker"].isin(tickers_validos)].copy() if tickers_validos else df_base_prov.iloc[0:0].copy()

            st.success(f"✅ {len(df_base_prov)} registros (apenas Ações)")
            
            # Métricas
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Registros", len(df_base_prov))
            with col2:
                st.metric("Valor Bruto", f"R$ {df_base_prov.get('Valor Bruto', pd.Series()).sum():,.2f}")
            with col3:
                st.metric("Impostos", f"R$ {df_base_prov.get('Impostos', pd.Series()).sum():,.2f}")
            with col4:
                st.metric("Valor Líquido", f"R$ {df_base_prov.get('Valor Líquido', pd.Series()).sum():,.2f}")
            
            st.markdown("---")
            
            # Filtros
            col_f1, col_f2, col_f3 = st.columns(3)
            
            df_filtrado = df_base_prov.copy()
            
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
                dist_fonte = df_filtrado.groupby("Fonte Provento")["Valor Líquido"].sum().sort_values(ascending=False)
                # Degrade: maior valor = cor mais escura (azul escuro)
                paleta = px.colors.sequential.Blues
                from plotly.colors import sample_colorscale
                n = len(dist_fonte)
                valores = dist_fonte.values
                norm = (valores - valores.min()) / (valores.max() - valores.min()) if valores.max() > valores.min() else [0.5]*n
                pie_colors = sample_colorscale(paleta, norm)
                fig_pie_fonte = px.pie(
                    names=dist_fonte.index,
                    values=dist_fonte.values,
                    title="Distribuição por Fonte",
                    hole=0.3,
                    labels={"names": "Fonte", "values": "Valor Líquido"},
                    color_discrete_sequence=pie_colors
                )
                fig_pie_fonte.update_traces(
                    textinfo="label+percent+value",
                    texttemplate="%{label}<br>R$%{value:,.2f} (%{percent})"
                )
                st.plotly_chart(fig_pie_fonte, use_container_width=True, key="div_cons_pie_fonte")
            
            # Gráficos de evolução
            st.markdown("---")

            # Série de posição mensal (somente ações) para cálculo do Dividend Yield (%)
            serie_pos = None
            try:
                df_pos_f = df_pos_acoes.copy() if not df_pos_acoes.empty else pd.DataFrame()

                # Reaplica filtro de usuário do widget (se existir)
                if "Usuário" in df_pos_f.columns and "Usuário" in df_filtrado.columns:
                    usuarios_sel_atual = None
                    try:
                        usuarios_sel_atual = usuarios_sel
                    except Exception:
                        usuarios_sel_atual = None
                    if usuarios_sel_atual:
                        df_pos_f = df_pos_f[df_pos_f["Usuário"].isin(usuarios_sel_atual)].copy()

                # Reaplica filtro de ativo do widget (se existir)
                ativos_sel_atual = None
                try:
                    ativos_sel_atual = ativos_sel
                except Exception:
                    ativos_sel_atual = None
                if ativos_sel_atual:
                    tick_sel = [_ticker_curto_local(a) for a in ativos_sel_atual]
                    tick_sel = [t for t in tick_sel if t]
                    if tick_sel:
                        df_pos_f = df_pos_f[df_pos_f["Ticker"].isin(tick_sel)].copy()

                if not df_pos_f.empty:
                    serie_pos = df_pos_f.groupby("PeriodoStr")["Valor"].sum()
            except Exception:
                serie_pos = None

            gerar_graficos_evolucao(
                df_filtrado,
                coluna_valor="Valor Líquido",
                coluna_data="Data",
                chave_periodo="periodo_div_cons",
                serie_posicao_mensal=serie_pos,
            )
            
            # Gráfico de top pagadores
            st.markdown("---")
            gerar_grafico_top_pagadores(df_filtrado, coluna_ativo="Ativo", coluna_valor="Valor Líquido", coluna_data="Data", chave_prefixo="top_div_cons")

# ============ TAB OPÇÕES ============
with tab_opcoes:
    st.header("🎯 Opções - Vendas Cobertas")
    
    subtab_consulta, subtab_registro, subtab_historico = st.tabs([
        "🔍 Consultar Opções",
        "📝 Registrar Venda",
        "📊 Histórico & Estatísticas"
    ])
    
    # ===== SUBTAB: CONSULTAR OPÇÕES =====
    with subtab_consulta:
        st.subheader("Consultar Opções Disponíveis")

        st.info("Fonte de dados: opcoes.net.br (B3). Selecione ativo e vencimento antes de atualizar para reduzir memória/tempo.")

        # Cache para opcoes.net.br (mantém apenas o último resultado carregado)
        df_opcoesnet_cache = st.session_state.get("opcoesnet_df_cache")
        if not isinstance(df_opcoesnet_cache, pd.DataFrame):
            df_opcoesnet_cache = pd.DataFrame()
        
        # Obter lista de ações da carteira
        acoes_disponiveis = []
        
        # Ações BR
        if not df_acoes_br.empty and "Ativo" in df_acoes_br.columns:
            acoes_disponiveis.extend(df_acoes_br["Ativo"].unique().tolist())
        
        # Ações Avenue
        if not df_acoes_avenue_padrao.empty and "Ativo" in df_acoes_avenue_padrao.columns:
            acoes_disponiveis.extend(df_acoes_avenue_padrao["Ativo"].unique().tolist())
        
        # Ações manuais
        if not df_manual_acoes.empty and "Ticker" in df_manual_acoes.columns:
            acoes_disponiveis.extend(df_manual_acoes["Ticker"].unique().tolist())
        
        # Normalizar: extrair apenas ticker (parte antes do '-' ou espaço, remover .SA)
        def _normalizar_ticker_b3(ticker: str) -> str:
            if not ticker:
                return ""
            t = str(ticker).strip().upper()
            # Remover quebras de linha e espaços duplos
            t = " ".join(t.split())
            # Se tem ' - ', pega apenas a parte antes
            if " - " in t:
                t = t.split(" - ", 1)[0].strip()
            # Remove .SA se existir
            if t.endswith(".SA"):
                t = t[:-3]
            return t
        
        acoes_disponiveis = sorted(list(set([_normalizar_ticker_b3(a) for a in acoes_disponiveis if _normalizar_ticker_b3(a)])))

        # opcoes.net.br: carrega cache do disco se ainda não existe em memória
        if df_opcoesnet_cache.empty:
            try:
                df_disk = carregar_cache_opcoesnet()
            except Exception:
                df_disk = pd.DataFrame()
            if isinstance(df_disk, pd.DataFrame) and not df_disk.empty:
                df_opcoesnet_cache = df_disk
                st.session_state["opcoesnet_df_cache"] = df_opcoesnet_cache

        st.markdown("### Seleção (antes de atualizar)")

        col_sel1, col_sel2 = st.columns([2, 1])
        with col_sel1:
            modo_ativo = st.radio(
                "Como escolher o ativo base",
                options=["Selecionar da carteira", "Digitar"],
                horizontal=True,
                key="opnet_modo_ativo",
            )

            ativo_base = ""
            if modo_ativo == "Selecionar da carteira" and acoes_disponiveis:
                default_sel = st.session_state.get("opnet_ativo_sel")
                idx = acoes_disponiveis.index(default_sel) if default_sel in acoes_disponiveis else 0
                ativo_base = st.selectbox(
                    "Ativo base (B3)",
                    options=acoes_disponiveis,
                    index=idx,
                    key="opnet_ativo_sel",
                    help="Escolha um ticker da sua carteira (B3).",
                )
            else:
                ativo_base = st.text_input(
                    "Ativo base (B3)",
                    value=st.session_state.get("opnet_ativo_text", ""),
                    placeholder="Ex: PETR4, VALE3, BBAS3",
                    help="Digite o ticker do ativo base (sem .SA).",
                    key="opnet_ativo_text",
                )

            # Normalizar ticker: remover .SA, espaços extras, parte após '-'
            ativo_base = (ativo_base or "").strip().upper()
            ativo_base = " ".join(ativo_base.split())  # Remove quebras de linha e espaços duplos
            if " - " in ativo_base:
                ativo_base = ativo_base.split(" - ", 1)[0].strip()
            if ativo_base.endswith(".SA"):
                ativo_base = ativo_base[:-3]
            st.session_state["opnet_ativo_base"] = ativo_base

            if modo_ativo == "Selecionar da carteira" and not acoes_disponiveis:
                st.info("Sua carteira ainda não tem ações listadas aqui; use 'Digitar'.")

        with col_sel2:
            buscar_todos_vencimentos = st.checkbox(
                "Todos vencimentos",
                value=False,
                help="Se marcado, ignora seleção de mês e busca todos os vencimentos (pode demorar).",
                key="opnet_todos_venc",
            )

        # Seleção única de mês (antes de atualizar)
        vencimentos_sel_opnet = None
        venc_series = None
        meses_from_vencs: list[str] = []

        if ativo_base and not buscar_todos_vencimentos:
            try:
                vencs_raw = _listar_vencimentos_opcoesnet_cached(ativo_base)
            except Exception as e:
                vencs_raw = []
                st.warning(f"⚠️ Não foi possível listar vencimentos para {ativo_base}: {e}")

            vencs_values = [
                str(v.get("value"))
                for v in vencs_raw
                if isinstance(v, dict) and v.get("value")
            ]

            if vencs_values:
                venc_series = pd.to_datetime(pd.Series(vencs_values), errors="coerce")
                meses_from_vencs = sorted(
                    venc_series.dt.strftime("%m/%Y").dropna().unique().tolist()
                )

        meses_prev = st.session_state.get("opnet_meses_sel", [])
        meses_default = [m for m in (meses_prev or []) if m in meses_from_vencs]
        if not meses_default and meses_from_vencs:
            meses_default = meses_from_vencs[:3] if len(meses_from_vencs) > 3 else meses_from_vencs

        meses_opnet = st.multiselect(
            "Mês de vencimento",
            options=meses_from_vencs,
            default=meses_default,
            help="Selecione antes de atualizar para baixar menos dados.",
            key="opnet_meses_sel",
            disabled=(not ativo_base or buscar_todos_vencimentos or not meses_from_vencs),
        )

        if not ativo_base:
            st.caption("Digite/seleciona um ativo para carregar os vencimentos.")
        elif buscar_todos_vencimentos:
            st.caption("Busca por todos os vencimentos está ativa.")
        elif not meses_from_vencs:
            st.caption("Nenhum vencimento listado para este ativo (ou endpoint indisponível).")
        elif meses_opnet and venc_series is not None:
            mask = venc_series.dt.strftime("%m/%Y").isin(meses_opnet)
            vencimentos_sel_opnet = (
                venc_series[mask].dt.strftime("%Y-%m-%d").dropna().unique().tolist()
            )
            st.caption(f"📅 {len(vencimentos_sel_opnet)} vencimento(s) selecionado(s)")

        # Filtros (aplicados no resultado já carregado)
        st.markdown("### Filtros (opcional)")
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            filtro_codigo = st.text_input(
                "Filtrar por código da opção (opcional)",
                placeholder="Ex: BBASA...",
                key="opnet_filtro_codigo",
            )
        with col_f2:
            tipos_sel = st.multiselect(
                "Tipo (opcional)",
                options=["CALL", "PUT"],
                default=["CALL", "PUT"],
                key="opnet_filtro_tipo",
            )
        with col_f3:
            filtro_dist_pct = st.slider(
                "Distância máxima do Strike (%)",
                min_value=0.0,
                max_value=50.0,
                value=10.0,
                step=0.5,
                help="Filtra por |(Strike - Preço Atual)/Preço Atual| ≤ X% (módulo, sem sinal).",
                key="opnet_filtro_dist_pct",
            )

        if st.button("🔄 Atualizar opções (opcoes.net.br)", type="primary"):
            if not ativo_base:
                st.warning("⚠️ Informe o Ativo base (ex: BBAS3) para atualizar.")
                st.stop()

            try:
                venc_info = (
                    f" ({len(vencimentos_sel_opnet)} vencimentos)" if vencimentos_sel_opnet else " (vencimento padrão)"
                )
                with st.spinner(f"Baixando opções de {ativo_base}{venc_info}..."):
                    df_new = buscar_opcoes_opcoesnet_bovespa(
                        id_acao=ativo_base,
                        todos_vencimentos=buscar_todos_vencimentos,
                        vencimentos=vencimentos_sel_opnet,
                    )

                # Aplicar filtros escolhidos (uma única vez, conforme solicitado)
                df_show = df_new.copy()
                if tipos_sel and "TIPO" in df_show.columns:
                    df_show = df_show[df_show["TIPO"].astype(str).isin(tipos_sel)]
                if filtro_codigo and "CODIGO" in df_show.columns:
                    # Normalizar código: remover espaços e fazer match parcial
                    filtro_normalizado = str(filtro_codigo).strip().upper().replace(" ", "")
                    df_show = df_show[
                        df_show["CODIGO"].astype(str).str.upper().str.replace(" ", "", regex=False).str.contains(filtro_normalizado, na=False, regex=False)
                    ]

                if df_show.empty:
                    st.warning(f"⚠️ Nenhuma opção encontrada para {ativo_base} com os filtros aplicados")
                    st.session_state["opcoesnet_df_cache"] = pd.DataFrame()
                    df_opcoesnet_cache = pd.DataFrame()
                else:
                    # Overwrite do cache (reduz memória; evita manter múltiplos ativos)
                    salvar_cache_opcoesnet(df_show)
                    st.session_state["opcoesnet_df_cache"] = df_show
                    df_opcoesnet_cache = df_show

                    vencs_unicos = sorted(df_show["VENCIMENTO"].dropna().unique()) if "VENCIMENTO" in df_show.columns else []
                    st.success(
                        f"✅ {len(df_show)} opções carregadas para {ativo_base} ({len(vencs_unicos)} vencimentos)"
                    )
            except LayoutOpcoesNetMudouError as e:
                st.error(f"⚠️ Layout do site mudou: {e}")
            except Exception as e:
                st.error(f"❌ Erro ao buscar opções: {e}")
                with st.expander("🐛 Detalhes do erro (debug)"):
                    import traceback
                    st.code(traceback.format_exc())

        # Renderizar tabela a partir do cache (último resultado carregado)
        if isinstance(df_opcoesnet_cache, pd.DataFrame) and not df_opcoesnet_cache.empty:
            st.markdown("---")
            st.subheader("Tabela (opcoes.net.br)")

            df_show_net = df_opcoesnet_cache.copy()

            # Preço atual (yfinance) e distância percentual Strike vs preço atual
            ativo_ref = (st.session_state.get("opnet_ativo_base") or "").strip().upper()
            if not ativo_ref and "ATIVO" in df_show_net.columns:
                try:
                    ativo_ref = str(df_show_net["ATIVO"].dropna().astype(str).iloc[0]).strip().upper()
                except Exception:
                    ativo_ref = ""

            preco_atual_acao = _obter_preco_atual_acao_yf_cached(ativo_ref) if ativo_ref else None
            if preco_atual_acao is not None and "STRIKE" in df_show_net.columns:
                strike_num = pd.to_numeric(df_show_net["STRIKE"], errors="coerce")
                df_show_net["Preço Atual"] = float(preco_atual_acao)
                df_show_net["Diferença Strike (%)"] = ((strike_num - float(preco_atual_acao)) / float(preco_atual_acao)) * 100.0
            elif ativo_ref:
                st.caption("Não foi possível obter preço atual via yfinance; filtro de distância do strike ficará indisponível.")

            # Filtrar por distância (módulo, sem sinal)
            if "Diferença Strike (%)" in df_show_net.columns:
                dist_num = pd.to_numeric(df_show_net["Diferença Strike (%)"], errors="coerce")
                df_show_net = df_show_net[dist_num.abs() <= float(filtro_dist_pct)].copy()

            if df_show_net.empty:
                st.warning("⚠️ Nenhuma opção dentro do filtro de distância do strike.")
                st.stop()

            cols_net = [
                c
                for c in [
                    "ATIVO",
                    "CODIGO",
                    "TIPO",
                    "Preço Atual",
                    "STRIKE",
                    "Diferença Strike (%)",
                    "VENCIMENTO",
                    "Mês Vencimento",
                    "PREMIO",
                    "Fonte",
                    "Coletado Em",
                ]
                if c in df_show_net.columns
            ]
            df_show_net = df_show_net[cols_net].copy() if cols_net else df_show_net

            fmt = {}
            if "Preço Atual" in df_show_net.columns:
                fmt["Preço Atual"] = "R$ {:.2f}"
            if "STRIKE" in df_show_net.columns:
                fmt["STRIKE"] = "R$ {:.2f}"
            if "PREMIO" in df_show_net.columns:
                fmt["PREMIO"] = "R$ {:.2f}"
            if "Diferença Strike (%)" in df_show_net.columns:
                fmt["Diferença Strike (%)"] = "{:.2f}%"

            styler = df_show_net.style.format(fmt)
            if "Diferença Strike (%)" in df_show_net.columns:
                try:
                    styler = styler.bar(
                        subset=["Diferença Strike (%)"],
                        align="mid",
                        vmin=-float(filtro_dist_pct),
                        vmax=float(filtro_dist_pct),
                    )
                except Exception:
                    pass

            st.dataframe(styler, use_container_width=True, height=520)

            col_e1, col_e2 = st.columns(2)
            with col_e1:
                csv_bytes = df_show_net.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "⬇️ Baixar CSV",
                    data=csv_bytes,
                    file_name="opcoes_opcoesnet_b3.csv",
                    mime="text/csv",
                )
            with col_e2:
                xlsx_bytes = exportar_opcoesnet_para_excel(df_show_net)
                st.download_button(
                    "⬇️ Baixar Excel",
                    data=xlsx_bytes,
                    file_name="opcoes_opcoesnet_b3.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
    
    # ===== SUBTAB: REGISTRAR VENDA =====
    with subtab_registro:
        st.subheader("Registrar Venda de Opção")
        
        if not usuarios_list:
            st.warning("⚠️ Nenhum usuário cadastrado. Cadastre um usuário em 'Outros > Gerenciar Usuários'")
        else:
            with st.form("form_registro_opcao"):
                col_r1, col_r2 = st.columns(2)
                
                with col_r1:
                    usuario_opcao = st.selectbox("Usuário", usuarios_list)
                    
                    # Ticker (pode ser manual ou da lista)
                    if acoes_disponiveis:
                        usar_ticker_lista = st.checkbox("Selecionar da carteira", value=True)
                        if usar_ticker_lista:
                            ticker_opcao = st.selectbox("Ação", acoes_disponiveis)
                        else:
                            ticker_opcao = st.text_input("Ticker", placeholder="Ex: PETR4.SA")
                    else:
                        ticker_opcao = st.text_input("Ticker", placeholder="Ex: PETR4.SA")
                    
                    tipo_opcao_venda = st.radio("Tipo", ["Call", "Put"], horizontal=True)
                
                with col_r2:
                    strike = st.number_input("Strike (R$)", min_value=0.0, value=0.0, step=0.01)
                    vencimento = st.date_input("Data de Vencimento")
                    quantidade = st.number_input("Quantidade de Contratos", min_value=1, value=1, step=1)
                
                col_r3, col_r4 = st.columns(2)
                
                with col_r3:
                    preco_venda = st.number_input("Preço de Venda (por contrato)", min_value=0.0, value=0.0, step=0.01)
                    premio_recebido = st.number_input("Prêmio Total Recebido (R$)", min_value=0.0, value=0.0, step=0.01)
                
                with col_r4:
                    data_operacao = st.date_input("Data da Operação", value=datetime.now())
                    observacoes = st.text_area("Observações (opcional)", height=100)
                
                # Botão de submit
                submitted = st.form_submit_button("✅ Registrar Venda", type="primary")
                
                if submitted:
                    if not ticker_opcao or strike <= 0 or premio_recebido <= 0:
                        st.error("⚠️ Preencha todos os campos obrigatórios corretamente!")
                    else:
                        sucesso = registrar_venda_opcao(
                            usuario=usuario_opcao,
                            ticker=ticker_opcao,
                            tipo=tipo_opcao_venda,
                            strike=strike,
                            vencimento=vencimento.strftime("%Y-%m-%d"),
                            quantidade=quantidade,
                            preco_venda=preco_venda,
                            premio_recebido=premio_recebido,
                            data_operacao=data_operacao.strftime("%Y-%m-%d"),
                            observacoes=observacoes
                        )
                        
                        if sucesso:
                            st.success("✅ Venda de opção registrada com sucesso!")
                            st.balloons()
                        else:
                            st.error("❌ Erro ao registrar venda de opção")
    
    # ===== SUBTAB: HISTÓRICO & ESTATÍSTICAS =====
    with subtab_historico:
        st.subheader("Histórico de Vendas de Opções")
        
        # Carregar vendas
        df_vendas = carregar_vendas_opcoes()
        
        if df_vendas.empty:
            st.info("Nenhuma venda de opção registrada ainda.")
        else:
            # Estatísticas
            st.markdown("### 📊 Estatísticas Gerais")
            stats = calcular_estatisticas_opcoes(df_vendas)
            
            col_s1, col_s2, col_s3, col_s4 = st.columns(4)
            
            with col_s1:
                st.metric("Total de Vendas", stats["total_vendas"])
            
            with col_s2:
                st.metric("Prêmio Total", f"R$ {stats['premio_total']:,.2f}")
            
            with col_s3:
                st.metric("Prêmio Médio", f"R$ {stats['premio_medio']:,.2f}")
            
            with col_s4:
                st.metric("Opções Ativas", stats["opcoes_ativas"])
            
            st.markdown("---")
            
            # Filtros
            col_fh1, col_fh2, col_fh3 = st.columns(3)
            
            with col_fh1:
                usuarios_opcoes = sorted(df_vendas["Usuário"].unique())
                filtro_usuario = st.multiselect("Filtrar por Usuário", usuarios_opcoes, default=usuarios_opcoes)
            
            with col_fh2:
                status_opcoes = sorted(df_vendas["Status"].unique())
                default_status = [s for s in status_opcoes if s != "Deletada"] or status_opcoes
                filtro_status = st.multiselect("Filtrar por Status", status_opcoes, default=default_status)
            
            with col_fh3:
                tipos_opcoes = sorted(df_vendas["Tipo"].unique())
                filtro_tipo = st.multiselect("Filtrar por Tipo", tipos_opcoes, default=tipos_opcoes)
            
            # Aplicar filtros
            df_vendas_filtrado = df_vendas[
                (df_vendas["Usuário"].isin(filtro_usuario)) &
                (df_vendas["Status"].isin(filtro_status)) &
                (df_vendas["Tipo"].isin(filtro_tipo))
            ]
            
            # Exibir tabela
            st.markdown("### 📋 Tabela de Vendas")
            
            if df_vendas_filtrado.empty:
                st.info("Nenhuma venda com os filtros selecionados")
            else:
                # Preparar tabela para exibição
                df_display = df_vendas_filtrado.copy()
                
                # Formatar datas
                if "Data Operação" in df_display.columns:
                    df_display["Data Operação"] = pd.to_datetime(df_display["Data Operação"]).dt.strftime("%d/%m/%Y")
                if "Vencimento" in df_display.columns:
                    df_display["Vencimento"] = pd.to_datetime(df_display["Vencimento"]).dt.strftime("%d/%m/%Y")
                
                st.dataframe(
                    df_display,
                    use_container_width=True,
                    height=400
                )
                
                # Botões de ação
                st.markdown("---")
                col_a1, col_a2, col_a3 = st.columns(3)
                
                with col_a1:
                    # Exportar para Excel
                    if st.button("📥 Exportar para Excel"):
                        try:
                            caminho = exportar_vendas_para_excel(df_vendas_filtrado)
                            if caminho:
                                st.success(f"✅ Exportado para: {caminho}")
                            else:
                                st.error("❌ Erro ao exportar")
                        except Exception as e:
                            st.error(f"❌ Erro: {e}")
                
                with col_a2:
                    # Atualizar status de uma opção
                    with st.expander("🔄 Atualizar Status"):
                        id_atualizar = st.number_input("ID da Opção", min_value=1, step=1)
                        novo_status = st.selectbox("Novo Status", ["Ativa", "Exercida", "Expirada"])
                        
                        if st.button("Atualizar"):
                            if atualizar_status_opcao(id_atualizar, novo_status):
                                st.success("✅ Status atualizado!")
                                st.rerun()
                            else:
                                st.error("❌ ID não encontrado")

                    # Deletar (soft delete)
                    with st.expander("🗑️ Deletar (mantém histórico)"):
                        id_deletar = st.number_input("ID para deletar", min_value=1, step=1, key="opcao_id_deletar")
                        confirmar = st.checkbox("Confirmo que quero deletar este registro", key="opcao_confirmar_deletar")
                        if st.button("Deletar", type="secondary", key="opcao_btn_deletar"):
                            if not confirmar:
                                st.warning("Marque a confirmação antes de deletar.")
                            else:
                                if atualizar_status_opcao(id_deletar, "Deletada"):
                                    st.success("✅ Registro marcado como Deletada.")
                                    st.rerun()
                                else:
                                    st.error("❌ ID não encontrado")
                
                with col_a3:
                    # Info sobre dividendos sintéticos
                    st.info(f"💰 Dividendos Sintéticos: R$ {df_vendas_filtrado['Prêmio Recebido'].sum():,.2f}")
                
                # Gráficos
                st.markdown("---")
                st.markdown("### 📈 Análises Gráficas")
                
                col_g1, col_g2 = st.columns(2)
                
                with col_g1:
                    # Gráfico de pizza por tipo
                    if "Tipo" in df_vendas_filtrado.columns:
                        df_por_tipo = df_vendas_filtrado.groupby("Tipo")["Prêmio Recebido"].sum().reset_index()
                        fig_tipo = px.pie(
                            df_por_tipo,
                            values="Prêmio Recebido",
                            names="Tipo",
                            title="Prêmios por Tipo de Opção",
                            color_discrete_sequence=px.colors.sequential.Blues[::-1]
                        )
                        st.plotly_chart(fig_tipo, use_container_width=True)
                
                with col_g2:
                    # Gráfico de barras por ticker
                    if "Ticker" in df_vendas_filtrado.columns:
                        df_por_ticker = df_vendas_filtrado.groupby("Ticker")["Prêmio Recebido"].sum().reset_index()
                        df_por_ticker = df_por_ticker.sort_values("Prêmio Recebido", ascending=False).head(10)
                        
                        fig_ticker = px.bar(
                            df_por_ticker,
                            x="Ticker",
                            y="Prêmio Recebido",
                            title="Top 10 Ações - Prêmios Recebidos",
                            color="Prêmio Recebido",
                            color_continuous_scale=px.colors.sequential.Purples[::-1]
                        )
                        fig_ticker.update_layout(showlegend=False)
                        st.plotly_chart(fig_ticker, use_container_width=True)

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
    
    # Adicionar caixas manuais na consolidação
    df_caixa_consolidado = caixa_para_consolidado(df_manual_caixa)
    if not df_caixa_consolidado.empty:
        frames_consolidados.append(df_caixa_consolidado)
    
    # Adicionar ações manuais na consolidação (histórico mensal derivado)
    df_acoes_man_consolidado = carregar_acoes_hist_mensal_cached(df_manual_acoes)
    if not df_acoes_man_consolidado.empty:
        frames_consolidados.append(df_acoes_man_consolidado)

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
            
            # Preparar DataFrame do mês anterior para comparação
            df_mes_anterior_inv = None
            mes_atual_sel = st.session_state.get("cons_geral_mes_value")
            try:
                if mes_atual_sel and "Mês/Ano" in df_consolidado_geral.columns:
                    # Converter mês atual para datetime e calcular mês anterior
                    from datetime import datetime
                    from dateutil.relativedelta import relativedelta
                    dt_atual = datetime.strptime(f"01/{mes_atual_sel}", "%d/%m/%Y")
                    dt_anterior = dt_atual - relativedelta(months=1)
                    mes_anterior_str = dt_anterior.strftime("%m/%Y")
                    
                    # Filtrar pelo mês anterior
                    df_mes_anterior_inv = df_consolidado_geral[
                        df_consolidado_geral["Mês/Ano"] == mes_anterior_str
                    ].copy()
                    if not df_mes_anterior_inv.empty:
                        df_mes_anterior_inv = enriquecer_com_setor_segmento(df_mes_anterior_inv)
                        if "Valor" not in df_mes_anterior_inv.columns:
                            if "Valor de Mercado" in df_mes_anterior_inv.columns:
                                df_mes_anterior_inv["Valor"] = df_mes_anterior_inv["Valor de Mercado"]
            except Exception:
                df_mes_anterior_inv = None
                mes_anterior_str = None
            
            exibir_metricas_valor(
                df_view_enriquecido,
                salvar_no_session_state_key="valor_total_consolidado_mes",
                df_mes_anterior=df_mes_anterior_inv,
                label_comparacao=mes_anterior_str if df_mes_anterior_inv is not None else None
            )

            with st.expander("📋 Ver Tabela Completa", expanded=False):
                st.dataframe(df_view_enriquecido, use_container_width=True)

            gerar_graficos_distribuicao(df_view_enriquecido, cores="Blues", key_prefixo="cons_geral")
            exibir_tabela_info_tickers(df_view_enriquecido)
            
            # Bloco Top 10 Maiores Altas
            st.markdown("---")
            col_up_cons, col_down_cons = st.columns(2)
            
            def _plot_bar_azul_cons(df, valor_col, label_col, titulo, key):
                """Gera gráfico de barras com degrade azul para consolidação"""
                if df.empty:
                    st.info("Sem dados.")
                    return
                df_plot = df.copy()
                df_plot = df_plot.sort_values(valor_col, ascending=False).reset_index(drop=True)
                from plotly.colors import sample_colorscale
                blues = px.colors.sequential.Blues[::-1]
                n = len(df_plot)
                valores = np.array(pd.to_numeric(df_plot[valor_col], errors="coerce"))
                norm = (valores - valores.min()) / (valores.max() - valores.min()) if valores.max() > valores.min() else np.full(n, 0.5)
                bar_colors = sample_colorscale(blues, norm)
                fig = px.bar(
                    df_plot,
                    x=label_col,
                    y=valor_col,
                    title=titulo,
                    color=valores,
                    color_continuous_scale=px.colors.sequential.Blues,
                    labels={label_col: "Ticker", valor_col: "Valor (R$)"},
                )
                fig.update_traces(marker_line_color="rgba(0,0,0,0)", textposition="outside", texttemplate="R$ %{y:,.0f}")
                fig.update_layout(yaxis_tickformat=",.0f", margin=dict(t=60), coloraxis_showscale=False, showlegend=False)
                st.plotly_chart(fig, use_container_width=True, key=key)
            
            with col_up_cons:
                st.subheader("📈 Maiores Altas (Top 10)")
                if "Ticker" in df_view_enriquecido.columns and "Valor" in df_view_enriquecido.columns:
                    df_top_altas = df_view_enriquecido.nlargest(10, "Valor")[["Ticker", "Valor"]].copy()
                    _plot_bar_azul_cons(df_top_altas, "Valor", "Ticker", "🏆 Top 10 - Maiores Valores", key="cons_top10_altas")
                    st.dataframe(df_top_altas, use_container_width=True, hide_index=True)
            
            with col_down_cons:
                st.subheader("📉 Maiores Posições (Top 10)")
                if "Ticker" in df_view_enriquecido.columns and "Quantidade" in df_view_enriquecido.columns:
                    df_top_qtd = df_view_enriquecido.nlargest(10, "Quantidade")[["Ticker", "Quantidade"]].copy()
                    _plot_bar_azul_cons(df_top_qtd, "Quantidade", "Ticker", "🏆 Top 10 - Maior Quantidade", key="cons_top10_qtd")
                    st.dataframe(df_top_qtd, use_container_width=True, hide_index=True)

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
                "vendas_opcoes": _mtime(str(ARQ_VENDAS_OPCOES)),
                "caixa": _mtime(CAIXA_PATH),
                "acoes_manuais": _mtime(ACOES_MANUAIS_PATH),
                # Gatilhos explícitos para mudanças no histórico mensal (BRL) de manuais
                "acoes_manuais_hist_mensal": _mtime("data/investimentos_manuais_acoes_hist_mensal.parquet"),
                "caixa_hist_full": _mtime("data/investimentos_manuais_caixa_hist_full.parquet"),
                "rentab_version": 11,
            }

        def _preparar_caixa_base_rentabilidade(df_caixa: pd.DataFrame) -> pd.DataFrame:
            if df_caixa is None or df_caixa.empty:
                return pd.DataFrame(columns=[
                    "Usuário", "Tipo", "Chave", "MesAno",
                    "QuantidadeAnterior", "QuantidadeAtual", "QuantidadeBase",
                    "PrecoAnterior", "PrecoAtual", "ValorInicial", "ValorFinal",
                    "Dividendos", "RetornoPct",
                    "PeriodoStr", "PeriodoOrd",
                ])

            dfc = df_caixa.copy()
            mes_col = "Mês" if "Mês" in dfc.columns else "Mes" if "Mes" in dfc.columns else None
            if mes_col is None:
                return pd.DataFrame(columns=[
                    "Usuário", "Tipo", "Chave", "MesAno",
                    "QuantidadeAnterior", "QuantidadeAtual", "QuantidadeBase",
                    "PrecoAnterior", "PrecoAtual", "ValorInicial", "ValorFinal",
                    "Dividendos", "RetornoPct",
                    "PeriodoStr", "PeriodoOrd",
                ])

            dfc["Usuário"] = dfc.get("Usuário", "Manual").fillna("Manual")
            dfc["Tipo"] = "Renda Fixa"
            dfc["Chave"] = dfc.get("Nome Caixa", "Caixa").fillna("Caixa").apply(_norm_key)

            dfc["Periodo"] = dfc[mes_col].apply(_parse_mes_ano_to_periodo)
            dfc = dfc[dfc["Periodo"].notna()].copy()
            dfc["PeriodoStr"] = dfc["Periodo"].astype(str)
            dfc["PeriodoOrd"] = dfc["Periodo"].apply(lambda p: int(p.ordinal))

            vi = pd.to_numeric(dfc.get("Valor Inicial"), errors="coerce").fillna(0.0)
            vf = pd.to_numeric(dfc.get("Valor Final"), errors="coerce").fillna(0.0)
            dep = pd.to_numeric(dfc.get("Depósitos"), errors="coerce").fillna(0.0)
            saq = pd.to_numeric(dfc.get("Saques"), errors="coerce").fillna(0.0)
            fluxo = (dep - saq).astype(float)
            fechado = dfc.get("Fechado", True)
            try:
                fechado = fechado.astype(bool)
            except Exception:
                fechado = True

            # Mês em aberto: considerar VF=VI e retorno=0
            vf_eff = np.where(pd.Series(fechado).fillna(True), vf, vi)
            retorno = np.where(
                (pd.Series(fechado).fillna(True)) & (vi > 0),
                ((vf_eff - dep + saq) - vi) / vi * 100.0,
                0.0,
            )

            retorno_s = pd.Series(retorno, index=dfc.index)
            fluxo_s = pd.Series(fluxo, index=dfc.index)

            out = pd.DataFrame({
                "Usuário": dfc["Usuário"].astype(str),
                "Tipo": dfc["Tipo"].astype(str),
                "Chave": dfc["Chave"].astype(str),
                "MesAno": dfc["Periodo"].apply(_periodo_to_label),
                "QuantidadeAnterior": 1.0,
                "QuantidadeAtual": 1.0,
                "QuantidadeBase": 1.0,
                "PrecoAnterior": vi,
                "PrecoAtual": vf_eff,
                "ValorInicial": vi,
                "ValorFinal": vf_eff,
                "Dividendos": 0.0,
                "RetornoPct": pd.to_numeric(retorno_s, errors="coerce").fillna(0.0).astype(float),
                "Fluxo": pd.to_numeric(fluxo_s, errors="coerce").fillna(0.0).astype(float),
                "PeriodoStr": dfc["PeriodoStr"].astype(str),
                "PeriodoOrd": pd.to_numeric(dfc["PeriodoOrd"], errors="coerce").fillna(0).astype(int),
            })

            # Evita linhas com chave vazia
            out = out[out["Chave"].astype(str).str.strip() != ""].copy()
            return out

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

        def _carregar_ou_gerar_base(df_posicoes: pd.DataFrame, df_div: pd.DataFrame, df_caixa: pd.DataFrame) -> pd.DataFrame:
            meta_old = _ler_meta()
            meta_new = _meta_atual()
            needs_rebuild = (meta_old != meta_new) or (not os.path.exists(RENTAB_PARQUET_PATH))

            if not needs_rebuild:
                try:
                    return pd.read_parquet(RENTAB_PARQUET_PATH)
                except Exception:
                    needs_rebuild = True

            # Para rentabilidade, o Caixa precisa usar sua própria fórmula (VI/Dep/Saq/VF)
            # então removemos as linhas de Caixa do consolidado antes de preparar posições,
            # e incluímos depois como base já calculada.
            df_pos_src = df_posicoes.copy() if isinstance(df_posicoes, pd.DataFrame) else pd.DataFrame()
            if not df_pos_src.empty and "Fonte" in df_pos_src.columns:
                df_pos_src = df_pos_src[df_pos_src["Fonte"].astype(str) != "Manual Caixa"].copy()

            df_pos = _preparar_posicoes(df_pos_src)
            df_div_prep = _preparar_dividendos(df_div)
            base = _calcular_base_rentabilidade(df_pos, df_div_prep)

            if "Fluxo" not in base.columns:
                base["Fluxo"] = 0.0

            base_caixa = _preparar_caixa_base_rentabilidade(df_caixa)
            if not base_caixa.empty:
                # Garante mesmas colunas da base
                for c in base.columns:
                    if c not in base_caixa.columns:
                        base_caixa[c] = np.nan
                for c in base_caixa.columns:
                    if c not in base.columns:
                        base[c] = np.nan
                base = pd.concat([base, base_caixa[base.columns]], ignore_index=True)

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
            base = _carregar_ou_gerar_base(df_consolidado_geral, df_dividendos_consolidado, df_manual_caixa)
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
                        Fluxo=("Fluxo", "sum"),
                    )
                    mensal["RetornoPct"] = np.where(
                        mensal["ValorInicial"] > 0,
                        ((mensal["ValorFinal"] + (mensal["Dividendos"] if usar_dividendos else 0.0) - mensal["Fluxo"]) - mensal["ValorInicial"]) / mensal["ValorInicial"] * 100.0,
                        np.nan,
                    )
                    mensal = mensal.rename(columns={"Usuário": "Serie"})

                    # Total (todos usuários selecionados)
                    total = mensal.groupby(["PeriodoStr"], as_index=False).agg(
                        ValorInicial=("ValorInicial", "sum"),
                        ValorFinal=("ValorFinal", "sum"),
                        Dividendos=("Dividendos", "sum"),
                        Fluxo=("Fluxo", "sum"),
                    )
                    total["RetornoPct"] = np.where(
                        total["ValorInicial"] > 0,
                        ((total["ValorFinal"] + (total["Dividendos"] if usar_dividendos else 0.0) - total["Fluxo"]) - total["ValorInicial"]) / total["ValorInicial"] * 100.0,
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
                        Fluxo=("Fluxo", "sum"),
                    )
                    mensal["RetornoPct"] = np.where(
                        mensal["ValorInicial"] > 0,
                        ((mensal["ValorFinal"] + (mensal["Dividendos"] if usar_dividendos else 0.0) - mensal["Fluxo"]) - mensal["ValorInicial"]) / mensal["ValorInicial"] * 100.0,
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
                                - (pd.to_numeric(base_tbl.get("Fluxo", 0.0), errors="coerce") if "Fluxo" in base_tbl.columns else 0.0)
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
                    Fluxo=("Fluxo", "sum"),
                )
                mensal_tipo["RetornoPct"] = np.where(
                    mensal_tipo["ValorInicial"] > 0,
                    ((mensal_tipo["ValorFinal"] + (mensal_tipo["Dividendos"] if usar_dividendos else 0.0) - mensal_tipo["Fluxo"]) - mensal_tipo["ValorInicial"]) / mensal_tipo["ValorInicial"] * 100.0,
                    np.nan,
                )
                mensal_tipo = mensal_tipo.rename(columns={"Tipo": "Serie"})
                
                # Total (todos tipos)
                total_tipo = mensal_tipo.groupby(["PeriodoStr"], as_index=False).agg(
                    ValorInicial=("ValorInicial", "sum"),
                    ValorFinal=("ValorFinal", "sum"),
                    Dividendos=("Dividendos", "sum"),
                    Fluxo=("Fluxo", "sum"),
                )
                total_tipo["RetornoPct"] = np.where(
                    total_tipo["ValorInicial"] > 0,
                    ((total_tipo["ValorFinal"] + (total_tipo["Dividendos"] if usar_dividendos else 0.0) - total_tipo["Fluxo"]) - total_tipo["ValorInicial"] ) / total_tipo["ValorInicial"] * 100.0,
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
    
    # Adicionar caixas manuais na posição atual
    df_caixa_consolidado_pos = caixa_para_consolidado(df_manual_caixa)
    if not df_caixa_consolidado_pos.empty:
        frames_consolidados.append(df_caixa_consolidado_pos)
    
    # Adicionar ações manuais na posição atual (histórico mensal derivado)
    df_acoes_man_consolidado_pos = carregar_acoes_posicao_cached(df_manual_acoes)
    if not df_acoes_man_consolidado_pos.empty:
        frames_consolidados.append(df_acoes_man_consolidado_pos)

    # Referência em BRL (para comparações vs mês selecionado)
    df_acoes_man_ref_brl = carregar_acoes_hist_mensal_cached(df_manual_acoes) if (df_manual_acoes is not None and not df_manual_acoes.empty) else pd.DataFrame()

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
                st.session_state["posicao_atual_df"] = None
                st.session_state["posicao_atual_sem_cotacao"] = None
                st.session_state["posicao_atual_ultima_atualizacao"] = None
                # Limpa caches para garantir atualização completa
                st.cache_data.clear()
                st.rerun()

        # Se a base mudou (ex: novo upload), força atualização
        try:
            # Assinatura leve, mas sensível a moeda/tipo (evita manter valores antigos quando muda BRL/USD/EUR)
            sig_parts = []
            if "Ticker" in df_posicao_base.columns:
                sig_parts.append(df_posicao_base["Ticker"].astype(str))
            if "Moeda" in df_posicao_base.columns:
                sig_parts.append(df_posicao_base["Moeda"].astype(str))
            if "Tipo" in df_posicao_base.columns:
                sig_parts.append(df_posicao_base["Tipo"].astype(str))
            if sig_parts:
                sig = sig_parts[0]
                for s in sig_parts[1:]:
                    sig = sig + "|" + s
                base_sig = f"{len(df_posicao_base)}|{','.join(sig.head(50).tolist())}"
            else:
                base_sig = f"{len(df_posicao_base)}"
        except Exception:
            base_sig = None

        # FIX definitivo: se o servidor ficar ligado, o session_state pode manter as cotações do dia anterior.
        # Força atualização automaticamente quando virar o dia, ou quando a última atualização ficar “velha”.
        now_dt = datetime.now()
        last_dt = st.session_state.get("posicao_atual_ultima_atualizacao")
        stale_by_day = isinstance(last_dt, datetime) and (last_dt.date() != now_dt.date())
        stale_by_age = (not isinstance(last_dt, datetime)) or ((now_dt - last_dt).total_seconds() > 60 * 30)  # 30 min

        precisa_atualizar = (
            st.session_state.get("posicao_atual_df") is None
            or st.session_state.get("posicao_atual_forcar_update") is True
            or (base_sig is not None and st.session_state.get("posicao_atual_base_sig") != base_sig)
            or stale_by_day
            or stale_by_age
        )

        if precisa_atualizar:
            with st.spinner("Buscando cotações em tempo real (yfinance)..."):
                df_atual, sem_cotacao, dt_atual = atualizar_cotacoes(df_posicao_base)
            st.session_state["posicao_atual_df"] = df_atual
            st.session_state["posicao_atual_sem_cotacao"] = sem_cotacao
            st.session_state["posicao_atual_ultima_atualizacao"] = dt_atual
            st.session_state["posicao_atual_base_sig"] = base_sig
            st.session_state["posicao_atual_forcar_update"] = False

        # Exibir timestamp de atualização
        last_dt = st.session_state.get("posicao_atual_ultima_atualizacao")
        with col_b:
            if isinstance(last_dt, datetime):
                st.caption(f"✅ Última atualização: {last_dt.strftime('%d/%m/%Y %H:%M:%S')}")
            else:
                st.caption("⏱️ Aguardando primeira atualização...")

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

        # Cards: USD/BRL + EUR/BRL com variação %
        st.markdown("---")
        with st.container():
            cols = st.columns([1,1,1,1])
            # Valor Total (primeira coluna)
            valor_total = None
            delta_total = None
            label_comparacao = None
            # Recupera os valores já calculados para exibir
            try:
                df_metricas = df_view_enriquecido.copy()
                valor_total = pd.to_numeric(df_metricas["Valor"], errors="coerce").fillna(0).sum()
                # Recupera delta e label do consolidado
                mes_comparacao = st.session_state.get("cons_geral_mes_value") or st.session_state.get("posicao_atual_mes")
                df_mes_comparacao = None
                if mes_comparacao:
                    frames_ref = []
                    if not df_padronizado.empty:
                        frames_ref.append(df_padronizado.copy())
                    if not df_acoes_avenue_padrao.empty:
                        frames_ref.append(df_acoes_avenue_padrao.copy())
                    if not df_caixa_consolidado_pos.empty:
                        frames_ref.append(df_caixa_consolidado_pos.copy())
                    if df_acoes_man_ref_brl is not None and not df_acoes_man_ref_brl.empty:
                        frames_ref.append(df_acoes_man_ref_brl.copy())
                    df_ref = pd.concat(frames_ref, ignore_index=True) if frames_ref else pd.DataFrame()
                    if not df_ref.empty and "Mês/Ano" in df_ref.columns:
                        df_mes_comparacao = df_ref[df_ref["Mês/Ano"] == mes_comparacao]
                        valor_anterior = pd.to_numeric(df_mes_comparacao["Valor"], errors="coerce").fillna(0).sum()
                        if valor_anterior > 0:
                            delta_total = ((valor_total - valor_anterior) / valor_anterior) * 100.0
                            label_comparacao = mes_comparacao
            except Exception:
                pass
            with cols[0]:
                if delta_total is not None and label_comparacao:
                    st.metric("💰 Valor Total", f"R$ {valor_total:,.2f}", f"{delta_total:+.2f}% vs {label_comparacao}")
                else:
                    st.metric("💰 Valor Total", f"R$ {valor_total:,.2f}")
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
            with cols[1]:
                if usd is None:
                    st.metric("USD/BRL", "—")
                else:
                    st.metric("USD/BRL", f"R$ {usd:,.4f}", (f"{usd_delta:+.2f}%" if usd_delta is not None else None))
            with cols[2]:
                if eur is None:
                    st.metric("EUR/BRL", "—")
                else:
                    st.metric("EUR/BRL", f"R$ {eur:,.4f}", (f"{eur_delta:+.2f}%" if eur_delta is not None else None))
            with cols[3]:
                st.empty()

        # Detalhamento por tipo com comparação usando o MES SELECIONADO (mesmos filtros da tela)
        st.markdown("---")

        df_mes_comparacao = None
        # Referência: mês selecionado no CONSOLIDADO (fallback: mês selecionado na própria aba)
        mes_comparacao = st.session_state.get("cons_geral_mes_value") or st.session_state.get("posicao_atual_mes")

        def _resolver_todos(raw_sel, valores_unicos):
            raw_sel = raw_sel or []
            if not isinstance(raw_sel, (list, tuple)):
                raw_sel = [raw_sel]
            raw_sel = [v for v in raw_sel if v is not None]
            if "Todos" in raw_sel:
                return list(valores_unicos)
            return list(raw_sel)

        try:
            if mes_comparacao:
                # IMPORTANTE: usar consolidado em BRL como referência.
                # Para Posição Atual, `df_acoes_avenue_pos_usd` fica em USD (para recalcular com câmbio atual),
                # mas a referência do mês (consolidado) deve usar `df_acoes_avenue_padrao` (já convertida para BRL).
                frames_ref = []
                if not df_padronizado.empty:
                    frames_ref.append(df_padronizado.copy())
                if not df_acoes_avenue_padrao.empty:
                    frames_ref.append(df_acoes_avenue_padrao.copy())
                if not df_caixa_consolidado_pos.empty:
                    frames_ref.append(df_caixa_consolidado_pos.copy())
                if df_acoes_man_ref_brl is not None and not df_acoes_man_ref_brl.empty:
                    frames_ref.append(df_acoes_man_ref_brl.copy())

                df_ref = pd.concat(frames_ref, ignore_index=True) if frames_ref else pd.DataFrame()
                if df_ref.empty:
                    df_mes_comparacao = None
                else:
                    df_mes_comparacao = df_ref.copy()
                if "Mês/Ano" in df_mes_comparacao.columns:
                    df_mes_comparacao = df_mes_comparacao[df_mes_comparacao["Mês/Ano"] == mes_comparacao]

                # Aplicar mesmos filtros da aba Posição Atual (usuário/tipo)
                if "Usuário" in df_mes_comparacao.columns:
                    usuarios_unicos = sorted(df_mes_comparacao["Usuário"].dropna().unique())
                    usuarios_sel = _resolver_todos(st.session_state.get("posicao_atual_user"), usuarios_unicos)
                    if usuarios_sel:
                        df_mes_comparacao = df_mes_comparacao[df_mes_comparacao["Usuário"].isin(usuarios_sel)]

                if "Tipo" in df_mes_comparacao.columns:
                    tipos_unicos = sorted(df_mes_comparacao["Tipo"].dropna().unique())
                    tipos_sel = _resolver_todos(st.session_state.get("posicao_atual_tipo"), tipos_unicos)
                    if tipos_sel:
                        df_mes_comparacao = df_mes_comparacao[df_mes_comparacao["Tipo"].isin(tipos_sel)]

                # Coluna de valor de referência
                if "Valor" in df_mes_comparacao.columns:
                    # Não forçar to_numeric aqui (pode ter 'R$'/'US$'); o parse robusto é feito em exibir_metricas_valor
                    df_mes_comparacao["Valor"] = df_mes_comparacao["Valor"]
                elif "Valor de Mercado" in df_mes_comparacao.columns:
                    df_mes_comparacao["Valor"] = df_mes_comparacao["Valor de Mercado"]
                else:
                    df_mes_comparacao = None

                if df_mes_comparacao is not None and not df_mes_comparacao.empty:
                    df_mes_comparacao = enriquecer_com_setor_segmento(df_mes_comparacao)
                else:
                    df_mes_comparacao = None
        except Exception:
            df_mes_comparacao = None

        # Exibir métricas detalhadas, mas ocultar o campo '💰 Valor Total'
        def exibir_metricas_valor_sem_total(df, col_valor="Valor", salvar_no_session_state_key=None, df_mes_anterior=None, label_comparacao=None):
            import unicodedata
            def _norm_tipo(v) -> str:
                s = "" if pd.isna(v) else str(v)
                s = unicodedata.normalize("NFKD", s)
                s = "".join(ch for ch in s if not unicodedata.combining(ch))
                s = " ".join(s.strip().split())
                return s.lower()
            # Por tipo se disponível
            if "Tipo" in df.columns:
                df_tmp = df.copy()
                df_tmp["_tipo_norm"] = df_tmp["Tipo"].apply(_norm_tipo)
                df_prev = None
                if df_mes_anterior is not None and not df_mes_anterior.empty and "Tipo" in df_mes_anterior.columns:
                    df_prev = df_mes_anterior.copy()
                    df_prev["_tipo_norm"] = df_prev["Tipo"].apply(_norm_tipo)

                tipos = df_tmp["Tipo"].dropna().unique()
                if len(tipos) > 1:
                    st.subheader("Por Tipo")
                    cols = st.columns(min(len(tipos), 5))
                    for idx, tipo in enumerate(sorted(tipos)):
                        with cols[idx % 5]:
                            tipo_norm = _norm_tipo(tipo)
                            valor_tipo = pd.to_numeric(
                                df_tmp[df_tmp["_tipo_norm"] == tipo_norm][col_valor],
                                errors="coerce",
                            ).fillna(0).sum()
                            delta_tipo = None
                            if df_prev is not None and col_valor in df_prev.columns:
                                valor_tipo_anterior = pd.to_numeric(
                                    df_prev[df_prev["_tipo_norm"] == tipo_norm][col_valor],
                                    errors="coerce",
                                ).fillna(0).sum()
                                if valor_tipo_anterior > 0:
                                    delta_tipo = ((valor_tipo - valor_tipo_anterior) / valor_tipo_anterior) * 100.0
                            if delta_tipo is not None and label_comparacao:
                                st.metric(tipo, f"R$ {valor_tipo:,.2f}", f"{delta_tipo:+.2f}% vs {label_comparacao}")
                            else:
                                st.metric(tipo, f"R$ {valor_tipo:,.2f}")

        exibir_metricas_valor_sem_total(
            df_view_enriquecido,
            col_valor="Valor",
            df_mes_anterior=df_mes_comparacao,
            label_comparacao=mes_comparacao
        )

        # Painéis: Top 10 Altas / Top 10 Baixas (apenas ativos com posição no mês selecionado)
        st.markdown("---")
        col_up, col_down = st.columns(2)
        base_mov = df_view_enriquecido.copy()
        base_mov["Variação %"] = pd.to_numeric(base_mov.get("Variação %"), errors="coerce")
        base_mov = base_mov.dropna(subset=["Variação %"]).copy()
        # Ganho/Perda no dia (R$) baseado no % do dia e no valor atual da posição:
        # exemplo: alta 3% e saldo atual 103k -> base = 103k/1.03 = 100k -> ganho = 3k
        if "Valor Atualizado" in base_mov.columns:
            _pct = pd.to_numeric(base_mov["Variação %"], errors="coerce") / 100.0
            _va = pd.to_numeric(base_mov["Valor Atualizado"], errors="coerce")
            _den = (1.0 + _pct).replace(0, np.nan)
            base_mov["Variação Dia (R$)"] = _va - (_va / _den)
        cols_mov = [c for c in ["Ticker", "Tipo", "Variação %", "Variação Dia (R$)", "Preço Atual", "Valor Atualizado"] if c in base_mov.columns]

        def _plot_bar_degrade(df, valor_col, label_col, titulo, key, valor_atualizado_col="Valor Atualizado", preco_hist_col="Preço Histórico (BRL)"):
            if df.empty:
                st.info("Sem ativos com posição no mês/ano selecionado.")
                return
            df_plot = df.copy()
            # Calcular ganho/perda em R$ no dia a partir do % do dia e do valor atual da posição
            if valor_atualizado_col in df_plot.columns and valor_col in df_plot.columns:
                _pct = pd.to_numeric(df_plot[valor_col], errors="coerce") / 100.0
                _va = pd.to_numeric(df_plot[valor_atualizado_col], errors="coerce")
                _den = (1.0 + _pct).replace(0, np.nan)
                df_plot["Variação Dia (R$)"] = _va - (_va / _den)
                valor_col_grafico = "Variação Dia (R$)"
                label_eixo = "Ganho/Perda no dia (R$)"
            else:
                valor_col_grafico = valor_col
                label_eixo = valor_col
            df_plot = df_plot.sort_values(valor_col_grafico, ascending=False).reset_index(drop=True)
            fig = px.bar(
                df_plot,
                x=label_col,
                y=valor_col_grafico,
                title=titulo,
                color=df_plot[valor_col_grafico],
                color_continuous_scale=px.colors.sequential.Purples,
                labels={label_col: "Ticker", valor_col_grafico: label_eixo},
            )
            fig.update_traces(marker_line_color="rgba(0,0,0,0)", textposition="outside", texttemplate="R$ %{y:,.0f}")
            fig.update_layout(yaxis_tickformat=",.0f", margin=dict(t=60), coloraxis_showscale=False, showlegend=False)
            st.plotly_chart(fig, use_container_width=True, key=key)

        with col_up:
            st.subheader("📈 Maiores Altas (Top 10)")
            if "Variação Dia (R$)" in base_mov.columns:
                df_top_up = base_mov.nlargest(10, "Variação Dia (R$)")[cols_mov].copy()
            else:
                df_top_up = base_mov.nlargest(10, "Variação %")[cols_mov].copy()
            _plot_bar_degrade(df_top_up, "Variação %", "Ticker", "🏆 Top 10 Ticker - Altas", key="posicao_top10_up", valor_atualizado_col="Valor Atualizado", preco_hist_col="Preço Histórico (BRL)")
            if not df_top_up.empty:
                _, sty_up = preparar_tabela_posicao_estilizada(df_top_up)
                st.dataframe(sty_up, use_container_width=True, hide_index=True)

        with col_down:
            st.subheader("📉 Maiores Baixas (Top 10)")
            if "Variação Dia (R$)" in base_mov.columns:
                df_top_down = base_mov.nsmallest(10, "Variação Dia (R$)")[cols_mov].copy()
            else:
                df_top_down = base_mov.nsmallest(10, "Variação %")[cols_mov].copy()
            _plot_bar_degrade(df_top_down, "Variação %", "Ticker", "🏆 Top 10 Ticker - Baixas", key="posicao_top10_down", valor_atualizado_col="Valor Atualizado", preco_hist_col="Preço Histórico (BRL)")
            if not df_top_down.empty:
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
            st.subheader("💵 Registrar Múltiplos Caixas")
            st.info("💡 Agora você pode gerenciar várias contas/caixas diferentes, cada uma com sua rentabilidade própria!")
            
            col_c1, col_c2, col_c3 = st.columns(3)
            with col_c1:
                mes_caixa = st.text_input(
                    "Mês (MM/YYYY)",
                    value=pd.Timestamp.now().strftime("%m/%Y"),
                    key="caixa_mes"
                )
            with col_c2:
                usuarios_cadastrados = sorted(df_usuarios.get("Nome", pd.Series()).dropna().unique().tolist())
                usr_caixa = st.selectbox(
                    "Usuário",
                    options=usuarios_cadastrados,
                    index=0 if usuarios_cadastrados else None,
                    key="caixa_usr"
                )
            with col_c3:
                nome_caixa = st.text_input(
                    "Nome do Caixa",
                    value="Caixa Principal",
                    key="caixa_nome",
                    help="Ex: Nubank, Inter, Reserva de Emergência, etc."
                )

            col_c4, col_c5 = st.columns(2)
            with col_c4:
                val_caixa_ini = st.number_input(
                    "Valor Inicial do mês (R$)",
                    min_value=0.0,
                    step=100.0,
                    key="caixa_val_ini"
                )
            with col_c5:
                fechar_mes_caixa = st.checkbox(
                    "Mês fechado (valor final confirmado)",
                    value=False,
                    key="caixa_fechado",
                    help="Enquanto estiver em aberto, o Valor Final fica igual ao Valor Inicial e não cria o próximo mês automaticamente.",
                )

                if fechar_mes_caixa:
                    val_caixa_fim = st.number_input(
                        "Valor Final do mês (R$)",
                        min_value=0.0,
                        step=100.0,
                        key="caixa_val_fim",
                    )
                else:
                    st.number_input(
                        "Valor Final do mês (R$)",
                        min_value=0.0,
                        step=100.0,
                        value=float(val_caixa_ini or 0.0),
                        disabled=True,
                        key="caixa_val_fim_preview",
                        help="Mês em aberto: Valor Final = Valor Inicial. Feche o mês para informar o valor final real.",
                    )
                    val_caixa_fim = float(val_caixa_ini or 0.0)

            st.markdown("#### Movimentações no mês")
            st.caption(
                "Para deixar a página mais rápida, os lançamentos de **Crédito/Débito** ficam apenas no bloco "
                "**✏️ Editar caixa existente** (logo abaixo), onde o mês/usuário/caixa já está selecionado."
            )
            df_mov = pd.DataFrame()

            dep_vals = []
            saq_vals = []
            dep_vals, saq_vals = [], []

            col_calc1, col_calc2 = st.columns(2)
            with col_calc1:
                if st.button("🧮 Calcular rentabilidade", key="btn_calc_caixa"):
                    try:
                        if not st.session_state.get("caixa_fechado", False):
                            st.info("Mês em aberto: rentabilidade/ganho ficam em 0 até você fechar o mês.")
                            dep_total = 0.0
                            saq_total = 0.0
                            rent_pct, ganho = 0.0, 0.0
                        else:
                            dep_total, saq_total, rent_pct, ganho = calcular_caixa(
                                valor_inicial=val_caixa_ini,
                                depositos=0.0,
                                saques=0.0,
                                valor_final=val_caixa_fim,
                            )
                        st.session_state["caixa_calc"] = {
                            "dep_total": dep_total,
                            "saq_total": saq_total,
                            "rent_pct": rent_pct,
                            "ganho": ganho,
                        }
                    except Exception as e:
                        st.error(f"❌ Erro no cálculo: {e}")

            calc = st.session_state.get("caixa_calc", None)
            if isinstance(calc, dict):
                st.markdown("---")
                st.markdown("### 📊 Resultado do Cálculo")
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("💰 Depósitos (R$)", f"R$ {calc['dep_total']:,.2f}")
                with c2:
                    st.metric("💸 Saques (R$)", f"R$ {calc['saq_total']:,.2f}")
                with c3:
                    st.metric("📈 Ganho (R$)", f"R$ {calc['ganho']:,.2f}")
                with c4:
                    st.metric("📊 Rentabilidade (%)", f"{calc['rent_pct']:.2f}%")
                st.caption(f"**Fórmula:** Rentabilidade (%) = ((Valor Final - Depósitos + Saques) - Valor Inicial) / Valor Inicial × 100")

            # Fallback defensivo para evitar NameError caso o Streamlit reordene execução/hot-reload
            nome_caixa = (
                (locals().get("nome_caixa") or "")
                or (st.session_state.get("caixa_nome") or "")
                or "Caixa Principal"
            )

            usr_caixa_safe = (
                (locals().get("usr_caixa") or "")
                or (st.session_state.get("caixa_usr") or "")
                or "Manual"
            )

            if st.button("💾 Salvar Caixa", key="btn_reg_caixa", type="primary"):
                try:
                    df_caixa_new = registrar_caixa(
                        mes_caixa,
                        val_caixa_ini,
                        usuario=usr_caixa_safe,
                        depositos=0.0,
                        saques=0.0,
                        valor_final=val_caixa_fim,
                        nome_caixa=nome_caixa or "Caixa Principal",
                        fechado=bool(st.session_state.get("caixa_fechado", False)),
                    )
                    if isinstance(df_caixa_new, pd.DataFrame):
                        st.session_state["caixa_df_cache"] = df_caixa_new
                    if bool(st.session_state.get("caixa_fechado", False)):
                        st.success(f"✅ Caixa '{nome_caixa}' FECHADO e salvo para {mes_caixa}! Próximo mês será criado/atualizado automaticamente.")
                    else:
                        st.success(f"✅ Caixa '{nome_caixa}' salvo para {mes_caixa} (em aberto).")
                    st.balloons()
                    st.session_state.pop("caixa_calc", None)  # Limpar cálculo anterior
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao salvar: {e}")
            
            st.markdown("---")
            st.subheader("📋 Histórico de Caixas")
            col_load1, col_load2, col_load3 = st.columns([1, 1, 1])
            with col_load1:
                btn_caixa_load = st.button(
                    "📥 Carregar/Atualizar caixas",
                    key="btn_caixa_load",
                    help="Carrega os dados uma vez e mantém em memória; assim a aba não fica lendo o parquet a cada mudança de filtro.",
                )
            with col_load2:
                btn_caixa_clear = st.button(
                    "🧹 Limpar cache",
                    key="btn_caixa_clear",
                    help="Limpa o cache em memória desta aba (não apaga dados).",
                )
            with col_load3:
                pass

            if btn_caixa_clear:
                st.session_state.pop("caixa_df_cache", None)
                st.session_state.pop("caixa_hist_filters_applied", None)
                st.session_state.pop("caixa_hist_df", None)
                st.session_state.pop("caixa_edit_loaded", None)
                st.rerun()

            if btn_caixa_load or ("caixa_df_cache" not in st.session_state):
                try:
                    st.session_state["caixa_df_cache"] = carregar_caixa_fast()
                except Exception:
                    st.session_state["caixa_df_cache"] = carregar_caixa()

            df_caixa_view = st.session_state.get("caixa_df_cache")
            if not isinstance(df_caixa_view, pd.DataFrame):
                df_caixa_view = pd.DataFrame()

            # Tabela com todos os caixas existentes (1 linha por Usuário + Nome Caixa)
            if not df_caixa_view.empty:
                try:
                    df_caixas_exist = df_caixa_view.copy()
                    if "Mês" in df_caixas_exist.columns:
                        df_caixas_exist["Mês"] = df_caixas_exist["Mês"].astype(str)
                        df_caixas_exist["_DataMes"] = pd.to_datetime(
                            "01/" + df_caixas_exist["Mês"].astype(str),
                            format="%d/%m/%Y",
                            errors="coerce",
                        )
                    sort_cols = [c for c in ["Usuário", "Nome Caixa", "_DataMes", "Data Registro"] if c in df_caixas_exist.columns]
                    if sort_cols:
                        df_caixas_exist = df_caixas_exist.sort_values(sort_cols)
                    if "Usuário" in df_caixas_exist.columns and "Nome Caixa" in df_caixas_exist.columns:
                        df_caixas_exist = df_caixas_exist.groupby(["Usuário", "Nome Caixa"], as_index=False).tail(1)
                    if "_DataMes" in df_caixas_exist.columns:
                        df_caixas_exist = df_caixas_exist.drop(columns=["_DataMes"])

                    st.markdown("#### 📌 Caixas existentes")
                    cols_lista = [
                        c for c in ["Usuário", "Nome Caixa", "Mês", "Fechado", "Valor Inicial", "Valor Final"]
                        if c in df_caixas_exist.columns
                    ]
                    st.dataframe(df_caixas_exist[cols_lista], use_container_width=True, hide_index=True)
                except Exception:
                    st.markdown("#### 📌 Caixas existentes")
                    cols_lista = [c for c in ["Usuário", "Nome Caixa", "Mês", "Fechado"] if c in df_caixa_view.columns]
                    st.dataframe(df_caixa_view[cols_lista].drop_duplicates(), use_container_width=True, hide_index=True)

                # Prévia simples do histórico (leve) para garantir visibilidade do que existe
                st.markdown("#### 📋 Histórico (todos os registros)")
                cols_hist_preview = [
                    c
                    for c in [
                        "Nome Caixa",
                        "Usuário",
                        "Mês",
                        "Fechado",
                        "Valor Inicial",
                        "Depósitos",
                        "Saques",
                        "Valor Final",
                        "Rentabilidade (%)",
                        "Ganho",
                    ]
                    if c in df_caixa_view.columns
                ]
                st.dataframe(df_caixa_view[cols_hist_preview], use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum registro de caixa encontrado. Adicione o primeiro caixa acima.")

            col_tog1, col_tog2 = st.columns(2)
            with col_tog1:
                caixa_toggle_edit = st.checkbox(
                    "✏️ Editar caixa existente",
                    value=False,
                    key="caixa_toggle_edit",
                    help="Ative para editar um registro existente (usa os dados já carregados em memória).",
                )
            with col_tog2:
                caixa_toggle_hist_avancado = st.checkbox(
                    "⚙️ Histórico avançado",
                    value=False,
                    key="caixa_toggle_hist_avancado",
                    help="Mostra filtros, resumo, exclusão e exportação (mais pesado).",
                )

            if isinstance(df_caixa_view, pd.DataFrame) and not df_caixa_view.empty:
                if caixa_toggle_edit:
                    with st.expander("✏️ Editar caixa existente (créditos/débitos/valor final)", expanded=False):
                        st.caption(
                            "Use para ir atualizando o mês (ex.: janeiro/2026) com créditos/débitos durante o mês e, no fim, informar o valor final. "
                            "As alterações sobrescrevem o registro do mesmo **Mês + Usuário + Nome do Caixa**."
                        )

                        # Seletores do registro (só carrega/aplica quando apertar o botão)
                        with st.form("caixa_edit_select_form"):
                            col_e1, col_e2, col_e3 = st.columns(3)
                            with col_e1:
                                usuarios_edit = sorted(df_caixa_view.get("Usuário", pd.Series(dtype=str)).dropna().unique().tolist())
                                sel_usr_prev = st.session_state.get("caixa_edit_sel_usr")
                                idx_usr = usuarios_edit.index(sel_usr_prev) if (sel_usr_prev in usuarios_edit) else (0 if usuarios_edit else None)
                                usr_edit = st.selectbox(
                                    "Usuário",
                                    options=usuarios_edit,
                                    index=idx_usr,
                                    key="caixa_edit_usr",
                                )
                            with col_e2:
                                caixas_edit = sorted(df_caixa_view.get("Nome Caixa", pd.Series(dtype=str)).dropna().unique().tolist())
                                sel_nome_prev = st.session_state.get("caixa_edit_sel_nome")
                                idx_nome = caixas_edit.index(sel_nome_prev) if (sel_nome_prev in caixas_edit) else (0 if caixas_edit else None)
                                nome_edit = st.selectbox(
                                    "Nome do Caixa",
                                    options=caixas_edit,
                                    index=idx_nome,
                                    key="caixa_edit_nome",
                                )
                            with col_e3:
                                df_scope_mes = df_caixa_view.copy()
                                if usr_edit and "Usuário" in df_scope_mes.columns:
                                    df_scope_mes = df_scope_mes[df_scope_mes["Usuário"].astype(str) == str(usr_edit)]
                                if nome_edit and "Nome Caixa" in df_scope_mes.columns:
                                    df_scope_mes = df_scope_mes[df_scope_mes["Nome Caixa"].astype(str) == str(nome_edit)]

                                meses_edit = sorted(
                                    df_scope_mes.get("Mês", pd.Series(dtype=str)).dropna().astype(str).unique().tolist(),
                                    reverse=True,
                                )
                                sel_mes_prev = st.session_state.get("caixa_edit_sel_mes")
                                idx_mes = meses_edit.index(sel_mes_prev) if (sel_mes_prev in meses_edit) else (0 if meses_edit else None)
                                mes_edit = st.selectbox(
                                    "Mês (MM/YYYY)",
                                    options=meses_edit,
                                    index=idx_mes,
                                    key="caixa_edit_mes",
                                )

                            btn_load_reg = st.form_submit_button("📥 Carregar registro", type="primary")

                        if btn_load_reg:
                            st.session_state["caixa_edit_sel_usr"] = usr_edit
                            st.session_state["caixa_edit_sel_nome"] = nome_edit
                            st.session_state["caixa_edit_sel_mes"] = mes_edit
                            st.session_state["caixa_edit_loaded"] = True

                        if not st.session_state.get("caixa_edit_loaded", False):
                            st.info("Selecione Usuário/Caixa/Mês e clique em **📥 Carregar registro** para editar.")
                        else:
                            # Usar os valores "carregados" como fonte da verdade
                            usr_edit = st.session_state.get("caixa_edit_sel_usr", usr_edit)
                            nome_edit = st.session_state.get("caixa_edit_sel_nome", nome_edit)
                            mes_edit = st.session_state.get("caixa_edit_sel_mes", mes_edit)

                            df_match = df_caixa_view.copy()
                            if usr_edit and "Usuário" in df_match.columns:
                                df_match = df_match[df_match["Usuário"].astype(str) == str(usr_edit)]
                            if nome_edit and "Nome Caixa" in df_match.columns:
                                df_match = df_match[df_match["Nome Caixa"].astype(str) == str(nome_edit)]
                            if mes_edit and "Mês" in df_match.columns:
                                df_match = df_match[df_match["Mês"].astype(str) == str(mes_edit)]

                            reg = None
                            if not df_match.empty:
                                if "Data Registro" in df_match.columns:
                                    try:
                                        df_match = df_match.sort_values("Data Registro")
                                    except Exception:
                                        pass
                                reg = df_match.iloc[-1].to_dict()

                            if not reg:
                                st.info("Nenhum registro encontrado para este Usuário/Caixa/Mês.")
                            else:
                                def _num_or(v, default: float = 0.0) -> float:
                                    x = pd.to_numeric(v, errors="coerce")
                                    return default if pd.isna(x) else float(x)

                                vi0 = _num_or(reg.get("Valor Inicial", 0.0), 0.0)
                                dep0 = _num_or(reg.get("Depósitos", 0.0), 0.0)
                                saq0 = _num_or(reg.get("Saques", 0.0), 0.0)
                                vf0 = _num_or(reg.get("Valor Final", 0.0), 0.0)
                                fechado0 = bool(reg.get("Fechado", True))

                                fechado_edit = st.checkbox(
                                    "Mês fechado (valor final confirmado)",
                                    value=fechado0,
                                    key="caixa_edit_fechado",
                                    help="Se estiver em aberto, o Valor Final fica igual ao Valor Inicial e não cria o próximo mês.",
                                )

                                col_v1, col_v2 = st.columns(2)
                                with col_v1:
                                    vi_edit = st.number_input(
                                        "Valor Inicial (R$)",
                                        min_value=0.0,
                                        step=100.0,
                                        value=vi0,
                                        key="caixa_edit_vi",
                                    )
                                with col_v2:
                                    if fechado_edit:
                                        vf_edit = st.number_input(
                                            "Valor Final (R$)",
                                            min_value=0.0,
                                            step=100.0,
                                            value=vf0,
                                            key="caixa_edit_vf",
                                        )
                                    else:
                                        st.number_input(
                                            "Valor Final (R$)",
                                            min_value=0.0,
                                            step=100.0,
                                            value=float(vi_edit or 0.0),
                                            disabled=True,
                                            key="caixa_edit_vf_preview",
                                            help="Mês em aberto: Valor Final = Valor Inicial.",
                                        )
                                        vf_edit = float(vi_edit or 0.0)

                                st.markdown("#### Créditos / Débitos do mês")
                                st.caption(
                                    "Adicione linhas de **Crédito** (depósito) ou **Débito** (saque) e o valor. "
                                    "O sistema direciona automaticamente para o caixa selecionado."
                                )

                                df_mov_edit = pd.DataFrame(columns=["ID", "Tipo", "Valor"])
                                try:
                                    try:
                                        df_all_movs = carregar_caixa_movimentos_fast()
                                    except Exception:
                                        df_all_movs = carregar_caixa_movimentos()

                                    if isinstance(df_all_movs, pd.DataFrame) and not df_all_movs.empty:
                                        df_mov_edit_full = df_all_movs[
                                            (df_all_movs.get("Usuário", pd.Series(dtype=str)).astype(str) == str(usr_edit or ""))
                                            & (df_all_movs.get("Nome Caixa", pd.Series(dtype=str)).astype(str) == str(nome_edit or ""))
                                            & (df_all_movs.get("Mês", pd.Series(dtype=str)).astype(str) == str(mes_edit or ""))
                                        ].copy()
                                        if not df_mov_edit_full.empty:
                                            df_mov_edit = df_mov_edit_full[
                                                [c for c in ["ID", "Tipo", "Valor"] if c in df_mov_edit_full.columns]
                                            ].copy()
                                            tipos_norm = df_mov_edit.get("Tipo", pd.Series(dtype=str)).astype(str).str.strip().str.lower()
                                            df_mov_edit["Tipo"] = np.where(tipos_norm.eq("saque"), "Débito", "Crédito")
                                except Exception:
                                    pass

                                if df_mov_edit.empty:
                                    df_mov_edit = pd.DataFrame(
                                        [{"ID": "", "Tipo": "Crédito", "Valor": 0.0}],
                                        columns=["ID", "Tipo", "Valor"],
                                    )

                                editor_key_mov_edit = (
                                    f"caixa_movs_edit_{str(usr_edit or '').strip()}_{str(nome_edit or '').strip()}_{str(mes_edit or '').strip()}"
                                    .replace(" ", "_")
                                    .replace("/", "_")
                                    .replace("\\", "_")
                                )

                                df_mov_edit2 = st.data_editor(
                                    df_mov_edit,
                                    num_rows="dynamic",
                                    use_container_width=True,
                                    key=editor_key_mov_edit,
                                    column_config={
                                        "ID": st.column_config.TextColumn("ID", disabled=True),
                                        "Tipo": st.column_config.SelectboxColumn("Tipo", options=["Crédito", "Débito"], required=True),
                                        "Valor": st.column_config.NumberColumn("Valor (R$)", min_value=0.0, step=10.0, format="%.2f", required=True),
                                    },
                                )

                                dep_edit = 0.0
                                saq_edit = 0.0
                                try:
                                    tipos_e = df_mov_edit2.get("Tipo", pd.Series(dtype=str)).astype(str)
                                    valores_e = pd.to_numeric(df_mov_edit2.get("Valor", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
                                    dep_edit = float(valores_e[tipos_e.str.strip().str.lower().eq("crédito")].sum())
                                    saq_edit = float(valores_e[tipos_e.str.strip().str.lower().eq("débito")].sum())
                                except Exception:
                                    dep_edit, saq_edit = float(dep0), float(saq0)

                                try:
                                    if not fechado_edit:
                                        dep_total_p, saq_total_p, rent_pct_p, ganho_p = float(dep_edit), float(saq_edit), 0.0, 0.0
                                    else:
                                        dep_total_p, saq_total_p, rent_pct_p, ganho_p = calcular_caixa(
                                            valor_inicial=vi_edit,
                                            depositos=dep_edit,
                                            saques=saq_edit,
                                            valor_final=vf_edit,
                                        )
                                    cpr1, cpr2, cpr3, cpr4 = st.columns(4)
                                    with cpr1:
                                        st.metric("Depósitos (R$)", f"R$ {dep_total_p:,.2f}")
                                    with cpr2:
                                        st.metric("Saques (R$)", f"R$ {saq_total_p:,.2f}")
                                    with cpr3:
                                        st.metric("Ganho (R$)", f"R$ {ganho_p:,.2f}")
                                    with cpr4:
                                        st.metric("Rentabilidade (%)", f"{rent_pct_p:.2f}%")
                                except Exception as e:
                                    st.warning(f"Não foi possível calcular prévia: {e}")

                                if st.button("💾 Salvar alterações", key="btn_caixa_edit_save", type="primary"):
                                    try:
                                        try:
                                            if isinstance(df_mov_edit2, pd.DataFrame):
                                                mv_save = df_mov_edit2.copy()
                                                mv_save["Tipo"] = mv_save.get("Tipo", "Crédito").astype(str)
                                                tipos_norm = mv_save["Tipo"].str.strip().str.lower()
                                                mv_save["Tipo"] = np.where(tipos_norm.eq("débito"), "Saque", "Depósito")
                                                mv_save["Data"] = datetime.now().date()
                                                mv_save["Descrição"] = ""
                                                mv_save["Categoria"] = ""
                                                registrar_caixa_movimentos(
                                                    mes_ano=mes_edit,
                                                    usuario=usr_edit or "Manual",
                                                    nome_caixa=nome_edit or "Caixa Principal",
                                                    movimentos=mv_save,
                                                )
                                        except Exception:
                                            pass

                                        df_caixa_after = registrar_caixa(
                                            mes_edit,
                                            vi_edit,
                                            usuario=usr_edit or "Manual",
                                            depositos=dep_edit,
                                            saques=saq_edit,
                                            valor_final=vf_edit,
                                            nome_caixa=nome_edit or "Caixa Principal",
                                            fechado=bool(fechado_edit),
                                        )
                                        if isinstance(df_caixa_after, pd.DataFrame):
                                            st.session_state["caixa_df_cache"] = df_caixa_after
                                        if bool(fechado_edit):
                                            st.success("✅ Alterações salvas e mês fechado! Próximo mês foi criado/atualizado automaticamente.")
                                        else:
                                            st.success("✅ Alterações salvas (mês em aberto).")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Erro ao salvar alterações: {e}")

                if caixa_toggle_hist_avancado:
                    with st.form("caixa_hist_filters_form"):
                        st.caption("Os filtros só são aplicados quando você clicar em **Aplicar filtros**.")
                    # Filtros para visualização
                        col_f1, col_f2, col_f3 = st.columns(3)
                        with col_f1:
                            usuarios_disponiveis = sorted(df_caixa_view["Usuário"].dropna().unique().tolist()) if "Usuário" in df_caixa_view.columns else []
                            filtro_usuario = st.multiselect("Filtrar por Usuário", ["Todos"] + usuarios_disponiveis, default=["Todos"], key="caixa_filtro_usr")
                        with col_f2:
                            caixas_disponiveis = sorted(df_caixa_view["Nome Caixa"].dropna().unique().tolist()) if "Nome Caixa" in df_caixa_view.columns else []
                            filtro_caixa = st.multiselect("Filtrar por Caixa", ["Todos"] + caixas_disponiveis, default=["Todos"], key="caixa_filtro_nome")
                        with col_f3:
                            meses_disponiveis = sorted(df_caixa_view["Mês"].dropna().unique().tolist(), reverse=True) if "Mês" in df_caixa_view.columns else []
                            filtro_mes = st.multiselect("Filtrar por Mês", ["Todos"] + meses_disponiveis, default=["Todos"], key="caixa_filtro_mes")

                        btn_apply_filters = st.form_submit_button("🔎 Aplicar filtros", type="primary")

                    if btn_apply_filters:
                        st.session_state["caixa_hist_filters_applied"] = {
                            "usr": list(filtro_usuario or []),
                            "caixa": list(filtro_caixa or []),
                            "mes": list(filtro_mes or []),
                        }

                    filtros_aplicados = st.session_state.get("caixa_hist_filters_applied")
                    if isinstance(filtros_aplicados, dict):
                        fu = filtros_aplicados.get("usr", ["Todos"])
                        fc = filtros_aplicados.get("caixa", ["Todos"])
                        fm = filtros_aplicados.get("mes", ["Todos"])
                    else:
                        fu, fc, fm = ["Todos"], ["Todos"], ["Todos"]

                    df_caixa_hist = carregar_caixa_hist_full_cached(df_caixa_view)
                    if "Todos" not in fu and fu:
                        df_caixa_hist = df_caixa_hist[df_caixa_hist["Usuário"].isin(fu)]
                    if "Todos" not in fc and fc:
                        df_caixa_hist = df_caixa_hist[df_caixa_hist["Nome Caixa"].isin(fc)]
                    if "Todos" not in fm and fm:
                        df_caixa_hist = df_caixa_hist[df_caixa_hist["Mês"].isin(fm)]

                    if "Mês" in df_caixa_hist.columns:
                        df_caixa_hist["Mês"] = df_caixa_hist["Mês"].astype(str)

                    if not df_caixa_hist.empty:
                        st.markdown("#### 📊 Resumo Geral")
                        col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                        with col_stat1:
                            total_caixas = df_caixa_hist["Nome Caixa"].nunique() if "Nome Caixa" in df_caixa_hist.columns else 0
                            st.metric("Total de Caixas", total_caixas)
                        with col_stat2:
                            total_registros = len(df_caixa_hist)
                            st.metric("Total de Registros", total_registros)
                        with col_stat3:
                            ganho_total = df_caixa_hist["Ganho"].sum() if "Ganho" in df_caixa_hist.columns else 0
                            st.metric("Ganho Total (R$)", f"R$ {ganho_total:,.2f}")
                        with col_stat4:
                            rent_media = df_caixa_hist["Rentabilidade (%)"].mean() if "Rentabilidade (%)" in df_caixa_hist.columns else 0
                            st.metric("Rent. Média (%)", f"{rent_media:.2f}%")

                    cols_caixa_show = [
                        c for c in ["Nome Caixa", "Usuário", "Mês", "Fechado", "Valor Inicial", "Depósitos", "Saques", "Valor Final", "Rentabilidade (%)", "Ganho", "Rentabilidade Acumulada (%)"]
                        if c in df_caixa_hist.columns
                    ]
                    st.dataframe(df_caixa_hist[cols_caixa_show], use_container_width=True, hide_index=True)

                    st.markdown("---")
                    st.markdown("#### 🗑️ Excluir registros")
                    df_del = df_caixa_hist.copy()
                    df_del["Excluir"] = False
                    cols_del = [c for c in ["Excluir", "Nome Caixa", "Usuário", "Mês", "Valor Inicial", "Depósitos", "Saques", "Valor Final", "Rentabilidade (%)", "Ganho", "ID"] if c in df_del.columns]
                    df_del_ed = st.data_editor(
                        df_del[cols_del],
                        use_container_width=True,
                        hide_index=True,
                        disabled=[c for c in cols_del if c != "Excluir"],
                        key="caixa_del_editor",
                    )
                    col_del1, col_del2, col_del3 = st.columns(3)
                    with col_del1:
                        if st.button("🗑️ Excluir selecionados", key="btn_del_caixa"):
                            try:
                                ids_del = df_del_ed.loc[df_del_ed["Excluir"] == True, "ID"].astype(str).tolist() if "ID" in df_del_ed.columns else []
                                if ids_del:
                                    df_after_del = excluir_caixa(ids_del)
                                    if isinstance(df_after_del, pd.DataFrame):
                                        st.session_state["caixa_df_cache"] = df_after_del
                                    st.success(f"✅ {len(ids_del)} registro(s) excluído(s).")
                                    st.rerun()
                                else:
                                    st.info("Nenhum registro selecionado.")
                            except Exception as e:
                                st.error(f"❌ Erro ao excluir: {e}")
                    with col_del2:
                        if st.button("🗑️ Excluir TUDO", key="btn_del_caixa_all"):
                            if st.checkbox("⚠️ Confirmar exclusão total", key="confirm_del_all_caixa"):
                                try:
                                    df_after_del_all = excluir_caixa(tudo=True)
                                    if isinstance(df_after_del_all, pd.DataFrame):
                                        st.session_state["caixa_df_cache"] = df_after_del_all
                                    st.success("✅ Todos os registros de Caixa foram excluídos.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Erro ao excluir tudo: {e}")
                            else:
                                st.warning("⚠️ Marque a caixa de confirmação para excluir tudo.")
                    with col_del3:
                        pass

                    st.markdown("---")
                    st.markdown("#### 📥 Exportar Dados")
                    col_exp1, col_exp2 = st.columns(2)
                    with col_exp1:
                        csv_caixa = df_caixa_hist.to_csv(index=False)
                        st.download_button(
                            "📥 Baixar CSV",
                            csv_caixa,
                            "historico_caixas.csv",
                            "text/csv",
                            key="dl_csv_caixa",
                        )
                    with col_exp2:
                        try:
                            xlsx_caixa = df_manual_para_excel(df_caixa_hist, sheet_name="Caixas")
                            st.download_button(
                                "📥 Baixar Excel",
                                xlsx_caixa,
                                "historico_caixas.xlsx",
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key="dl_xlsx_caixa",
                            )
                        except Exception:
                            st.info("Excel não disponível.")

            else:
                st.info("📭 Nenhum registro de caixa encontrado. Adicione o primeiro caixa acima!")
        
        # --- Ações ---
        with sec_acoes:
            st.subheader("📈 Inserir Ação Manual")
            st.caption(
                "Registre a **compra** com mês/ano e quantidade. Se vender depois, edite o registro e preencha **Mês Venda** e **Quantidade Venda**. "
                "O sistema gera o histórico mensal automaticamente e recalcula valor com a cotação do mês."
            )

            col_a1, col_a2, col_a3 = st.columns(3)
            with col_a1:
                ticker_acao = st.text_input("Ticker (ex: BBAS3, AAPL)", key="acao_ticker")
            with col_a2:
                dt_compra = st.date_input("Data de compra", value=pd.Timestamp.today().date(), key="acao_dt_compra")
                mes_acao = f"{dt_compra.month:02d}/{dt_compra.year}"
            with col_a3:
                qtd_acao = st.number_input("Quantidade comprada", min_value=0.0, step=1.0, key="acao_qtd")

            preco_compra_acao = st.number_input(
                "Preço de compra (opcional — na moeda do ativo)",
                min_value=0.0,
                step=0.01,
                format="%.4f",
                key="acao_preco_compra",
            )

            usuarios_cadastrados = sorted(df_usuarios.get("Nome", pd.Series()).dropna().unique().tolist())
            usr_acao = st.selectbox(
                "Usuário",
                options=usuarios_cadastrados,
                index=0 if usuarios_cadastrados else None,
                key="acao_usr",
            )

            if st.button("✅ Registrar compra", key="btn_reg_acao"):
                if not ticker_acao or qtd_acao <= 0:
                    st.error("❌ Preencha ticker e quantidade.")
                else:
                    with st.spinner("Validando ticker e registrando..."):
                        try:
                            df_acoes_new, meta = registrar_acao_manual(
                                ticker_acao,
                                qtd_acao,
                                mes_acao,
                                usuario=usr_acao or "Manual",
                                preco_compra=(preco_compra_acao if (preco_compra_acao or 0.0) > 0 else None),
                            )
                            st.success(f"✅ Compra registrada para {meta.get('tipo', 'Ações')}: {ticker_acao} ({mes_acao}).")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erro: {e}")
            
            st.markdown("---")
            st.subheader("Ações Inseridas (lotes)")
            df_acoes_view = carregar_acoes_man()
            if not df_acoes_view.empty:
                df_lotes = df_acoes_view.copy()
                # Garantir colunas do schema
                if "Mês Compra" not in df_lotes.columns and "Mês/Ano" in df_lotes.columns:
                    df_lotes["Mês Compra"] = df_lotes["Mês/Ano"].astype(str)
                if "Quantidade Compra" not in df_lotes.columns and "Quantidade" in df_lotes.columns:
                    df_lotes["Quantidade Compra"] = pd.to_numeric(df_lotes["Quantidade"], errors="coerce")
                if "Mês Venda" not in df_lotes.columns:
                    df_lotes["Mês Venda"] = ""
                if "Quantidade Venda" not in df_lotes.columns:
                    df_lotes["Quantidade Venda"] = 0.0
                if "Preço Compra" not in df_lotes.columns:
                    df_lotes["Preço Compra"] = 0.0

                cols_edit = [c for c in ["ID", "Usuário", "Ticker", "Quantidade Compra", "Preço Compra", "Mês Compra", "Quantidade Venda", "Mês Venda", "Moeda", "Ticker_YF"] if c in df_lotes.columns]
                df_lotes_show = df_lotes[cols_edit].copy()

                df_lotes_ed = st.data_editor(
                    df_lotes_show,
                    use_container_width=True,
                    hide_index=True,
                    disabled=[c for c in ["ID", "Moeda", "Ticker_YF"] if c in df_lotes_show.columns],
                    key="acoes_lotes_editor",
                )

                col_sv1, col_sv2 = st.columns(2)
                with col_sv1:
                    if st.button("💾 Salvar alterações (venda/compra)", key="btn_save_lotes"):
                        try:
                            df_new = df_acoes_view.copy()
                            # aplica alterações por ID
                            if "ID" not in df_new.columns or "ID" not in df_lotes_ed.columns:
                                raise ValueError("Sem coluna ID para atualização")
                            df_new["ID"] = df_new["ID"].astype(str)
                            edited = df_lotes_ed.copy()
                            edited["ID"] = edited["ID"].astype(str)

                            # Normalizações e validações básicas
                            edited["Quantidade Compra"] = pd.to_numeric(edited.get("Quantidade Compra"), errors="coerce").fillna(0.0)
                            edited["Quantidade Venda"] = pd.to_numeric(edited.get("Quantidade Venda"), errors="coerce").fillna(0.0)
                            if "Preço Compra" in edited.columns:
                                edited["Preço Compra"] = pd.to_numeric(edited.get("Preço Compra"), errors="coerce").fillna(0.0)
                            edited["Mês Compra"] = edited.get("Mês Compra", "").astype(str)
                            edited["Mês Venda"] = edited.get("Mês Venda", "").fillna("").astype(str)

                            # validar mês
                            p_comp = edited["Mês Compra"].apply(_parse_mes_ano_to_period_global)
                            if p_comp.isna().any():
                                raise ValueError("Há registros com 'Mês Compra' inválido (use MM/YYYY).")
                            p_v = edited["Mês Venda"].apply(lambda x: _parse_mes_ano_to_period_global(x) if str(x).strip() else None)

                            # validar venda
                            invalid_q = edited["Quantidade Venda"] < 0
                            if invalid_q.any():
                                raise ValueError("Quantidade Venda não pode ser negativa.")
                            invalid_gt = edited["Quantidade Venda"] > edited["Quantidade Compra"]
                            if invalid_gt.any():
                                raise ValueError("Quantidade Venda não pode ser maior que Quantidade Compra.")
                            invalid_mes = (p_v.notna()) & (p_v < p_comp)
                            if invalid_mes.any():
                                raise ValueError("Mês Venda não pode ser anterior ao Mês Compra.")

                            if "Preço Compra" in edited.columns:
                                invalid_pc = edited["Preço Compra"] < 0
                                if invalid_pc.any():
                                    raise ValueError("Preço Compra não pode ser negativo.")

                            # aplica
                            for _, row in edited.iterrows():
                                mask = df_new["ID"].astype(str) == str(row["ID"])
                                if not mask.any():
                                    continue
                                for col in ["Usuário", "Ticker", "Quantidade Compra", "Preço Compra", "Mês Compra", "Quantidade Venda", "Mês Venda"]:
                                    if col in df_new.columns and col in edited.columns:
                                        df_new.loc[mask, col] = row.get(col)
                                # manter colunas legadas sincronizadas
                                if "Quantidade" in df_new.columns and "Quantidade Compra" in edited.columns:
                                    df_new.loc[mask, "Quantidade"] = row.get("Quantidade Compra")
                                if "Mês/Ano" in df_new.columns and "Mês Compra" in edited.columns:
                                    df_new.loc[mask, "Mês/Ano"] = row.get("Mês Compra")

                            # salva via módulo
                            from modules.investimentos_manuais import salvar_acoes as _salvar_acoes
                            _salvar_acoes(df_new)
                            st.success("✅ Alterações salvas.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erro ao salvar alterações: {e}")
                with col_sv2:
                    with st.expander("📊 Histórico mensal (posição gerada)", expanded=True):
                        df_hist_brl = carregar_acoes_hist_mensal_cached(df_acoes_view)
                        df_hist_moeda = carregar_acoes_posicao_cached(df_acoes_view)

                        if df_hist_brl.empty and df_hist_moeda.empty:
                            st.info("Sem histórico mensal gerado ainda.")
                        else:
                            # Monta visão única: BRL + Moeda
                            df_brl = df_hist_brl.copy()
                            df_fx = df_hist_moeda.copy()

                            if not df_brl.empty:
                                df_brl = df_brl.rename(columns={"Preço": "Preço (BRL)", "Valor": "Valor (BRL)"})
                            if not df_fx.empty:
                                df_fx = df_fx.rename(columns={"Preço": "Preço (Moeda)", "Valor": "Valor (Moeda)"})

                            # Chaves para merge (tolerante a colunas) — evita usar Quantidade como chave (pode dar mismatch por float)
                            chaves_preferidas = ["Usuário", "Tipo", "Ticker", "Mês/Ano", "Moeda"]
                            chaves = [c for c in chaves_preferidas if (c in df_brl.columns and c in df_fx.columns)]

                            if (not df_brl.empty) and (not df_fx.empty) and chaves:
                                df_hist_view = df_brl.merge(df_fx, on=chaves, how="left")
                            else:
                                df_hist_view = df_brl if not df_brl.empty else df_fx

                            st.dataframe(
                                df_hist_view[[c for c in [
                                    "Usuário", "Tipo", "Ticker", "Moeda", "Quantidade",
                                    "Preço (Moeda)", "Valor (Moeda)",
                                    "Preço (BRL)", "Valor (BRL)",
                                    "Mês/Ano",
                                ] if c in df_hist_view.columns]]
                                .sort_values([c for c in ["Ticker", "Mês/Ano"] if c in df_hist_view.columns]) ,
                                use_container_width=True,
                                hide_index=True,
                            )

                st.markdown("#### Excluir registros")
                df_del_a = df_acoes_view.copy()
                df_del_a["Excluir"] = False
                cols_del_a = [c for c in ["Excluir", "Usuário", "Tipo", "Ticker", "Quantidade", "Preço BRL", "Valor", "Mês/Ano", "ID"] if c in df_del_a.columns]
                df_del_a_ed = st.data_editor(
                    df_del_a[cols_del_a],
                    use_container_width=True,
                    hide_index=True,
                    disabled=[c for c in cols_del_a if c != "Excluir"],
                    key="acoes_del_editor",
                )
                col_da1, col_da2 = st.columns(2)
                with col_da1:
                    if st.button("🗑️ Excluir selecionados (Ações)", key="btn_del_acoes"):
                        try:
                            ids_del = df_del_a_ed.loc[df_del_a_ed["Excluir"] == True, "ID"].astype(str).tolist() if "ID" in df_del_a_ed.columns else []
                            if ids_del:
                                excluir_acoes(ids_del)
                                st.success("Registros excluídos.")
                                st.rerun()
                            else:
                                st.info("Nenhum registro selecionado.")
                        except Exception as e:
                            st.error(f"Erro ao excluir: {e}")
                with col_da2:
                    if st.button("🗑️ Excluir TUDO (Ações)", key="btn_del_acoes_all"):
                        try:
                            excluir_acoes(tudo=True)
                            st.success("Todos os registros de Ações manuais foram excluídos.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao excluir tudo: {e}")

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
                    try:
                        from modules.investimentos_manuais import caixa_para_consolidado as _caixa_para_consolidado
                        df_caixa_cons = _caixa_para_consolidado(df_caixa_all)
                        if not df_caixa_cons.empty:
                            df_caixa_cons["Moeda"] = "BRL"
                            consolidado_parts.append(df_caixa_cons)
                    except Exception as e:
                        st.error(f"❌ Erro ao preparar Caixa para consolidado: {e}")

                if not df_acoes_all.empty:
                    try:
                        df_acoes_cons = carregar_acoes_hist_mensal_cached(df_acoes_all)
                        if not df_acoes_cons.empty:
                            # Valores já estão em BRL (Preço/Valor). Mantém Moeda como moeda da cotação.
                            df_acoes_cons["Moeda Valor"] = "BRL"
                            consolidado_parts.append(df_acoes_cons)
                    except Exception as e:
                        st.error(f"❌ Erro ao preparar Ações para consolidado: {e}")

                if consolidado_parts:
                    df_consolidado_man = pd.concat(consolidado_parts, ignore_index=True)
                    df_consolidado_man["Valor"] = pd.to_numeric(df_consolidado_man.get("Valor"), errors="coerce").fillna(0.0)

                    # Normaliza coluna de mês
                    if "Mês/Ano" in df_consolidado_man.columns:
                        df_consolidado_man = df_consolidado_man.rename(columns={"Mês/Ano": "Mes"})
                    if "Mes" not in df_consolidado_man.columns:
                        df_consolidado_man["Mes"] = ""

                    # Visão enxuta (uma coluna Valor comum para somar)
                    cols_show = [c for c in ["Mes", "Usuário", "Tipo", "Ativo", "Ticker", "Quantidade", "Preço", "Valor", "Moeda", "Moeda Valor", "Fonte"] if c in df_consolidado_man.columns]

                    total_brl = float(df_consolidado_man["Valor"].sum())
                    st.metric("Total (Valor em BRL)", f"R$ {total_brl:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

                    sort_cols = [c for c in ["Mes", "Tipo", "Ticker", "Ativo"] if c in cols_show]
                    df_show = df_consolidado_man[cols_show].copy()
                    if sort_cols:
                        df_show = df_show.sort_values(sort_cols)

                    st.dataframe(
                        df_show,
                        use_container_width=True,
                        hide_index=True,
                    )
                    
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
- Informe o **Valor Inicial** e o **Valor Final** do mês.
- Adicione quantos **depósitos** e **saques** quiser (movimentações do mês).
- A rentabilidade é calculada por:
    - Rentabilidade (%) = ((Valor final - Depósitos + Saques) - Valor inicial) / Valor inicial × 100
- O **Ganho** do Caixa é automaticamente integrado à aba **Rentabilidade** como "Dividendos" na linha "Caixa".

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

# Aplica estilo global para todos os cartões st.metric (reduz 30% o tamanho)
st.markdown("""
<style>
div[data-testid='stMetric'] {font-size: 0.9rem !important;}
div[data-testid='stMetric'] label, div[data-testid='stMetric'] span {font-size: 0.9rem !important;}
</style>
""", unsafe_allow_html=True)

