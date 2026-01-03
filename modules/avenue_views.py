"""
Módulo para visualização de dados extraídos dos PDFs da Avenue.
Fornece funções para exibir as abas:
- Ações Avenue
- Proventos Avenue (Dividendos)
- Dividendo Consolidado
"""

import os
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io

from modules.upload_pdf_avenue import (
    extrair_acoes_pdf,
    extrair_dividendos_pdf,
    processar_pasta_pdfs,
    ACOES_PDF_PATH,
    DIVIDENDOS_PDF_PATH
)
from modules.upload_relatorio import ACOES_PATH, PROVENTOS_PATH


def carregar_acoes_avenue() -> pd.DataFrame:
    """
    Carrega dados de ações extraídas dos PDFs Avenue.
    Procura por parquets salvos ou retorna DataFrame vazio.
    """
    if os.path.exists(ACOES_PDF_PATH):
        try:
            return pd.read_parquet(ACOES_PDF_PATH)
        except Exception as e:
            st.warning(f"Erro ao carregar ações Avenue: {e}")
            return pd.DataFrame()
    
    return pd.DataFrame()


def carregar_dividendos_avenue() -> pd.DataFrame:
    """
    Carrega dados de dividendos extraídos dos PDFs Avenue.
    """
    if os.path.exists(DIVIDENDOS_PDF_PATH):
        try:
            return pd.read_parquet(DIVIDENDOS_PDF_PATH)
        except Exception as e:
            st.warning(f"Erro ao carregar dividendos Avenue: {e}")
            return pd.DataFrame()
    
    return pd.DataFrame()


def padronizar_acoes_avenue(df: pd.DataFrame) -> pd.DataFrame:
    """
    Padroniza as colunas de ações extraídas.
    
    Transforma:
    - Produto → Ativo
    - Ticker → Ticker
    - Quantidade Disponível → Quantidade
    - Preço de Fechamento → Preço
    - Valor → Valor de Mercado
    """
    if df.empty:
        return df
    
    df_padrao = df.copy()
    
    # Mapear colunas
    colunas_mapeadas = {
        "Produto": "Ativo",
        "Ticker": "Ticker",
        "Quantidade Disponível": "Quantidade",
        "Preço de Fechamento": "Preço",
        "Valor": "Valor de Mercado"
    }
    
    # Renomear colunas que existem
    df_padrao = df_padrao.rename(columns={k: v for k, v in colunas_mapeadas.items() if k in df_padrao.columns})
    
    # Adicionar colunas de metadados se existirem
    colunas_mantidas = [col for col in ["Ativo", "Ticker", "Quantidade", "Preço", "Valor de Mercado", "Mês/Ano", "Usuário"] 
                        if col in df_padrao.columns or col in colunas_mapeadas.values()]
    
    return df_padrao[colunas_mantidas] if colunas_mantidas else df_padrao


def padronizar_dividendos_avenue(df: pd.DataFrame) -> pd.DataFrame:
    """
    Padroniza os dividendos extraídos dos PDFs.
    
    Estrutura esperada do DataFrame de entrada:
    - Produto, Data de Pagamento, Tipo de Provento, Valor Líquido, Mês/Ano, Usuário
    
    Padroniza para:
    - Data, Ativo, Valor Bruto, Impostos, Valor Líquido, Fonte
    
    Nota: PDFs Avenue não fornecem Valor Bruto/Impostos separados, apenas Valor Líquido.
    """
    if df.empty:
        return df
    
    df_padrao = df.copy()
    
    # Renomear colunas principais
    if "Data de Pagamento" in df_padrao.columns:
        df_padrao["Data"] = pd.to_datetime(df_padrao["Data de Pagamento"], format="%d/%m/%Y", errors="coerce")
    
    # Ativo (usa ticker/produto extraído)
    if "Produto" in df_padrao.columns:
        df_padrao["Ativo"] = df_padrao["Produto"]
    else:
        df_padrao["Ativo"] = "N/A"
    
    # Valores
    if "Valor Líquido" in df_padrao.columns:
        df_padrao["Valor Líquido"] = df_padrao["Valor Líquido"].astype(float)
    
    # Para Avenue, vamos usar uma heurística:
    # Se tipo é "Retenção de Impostos", é um imposto (valor negativo)
    # Se é "Dividendo" ou "Juros", é um crédito
    
    df_padrao["Valor Bruto"] = 0.0
    df_padrao["Impostos"] = 0.0
    
    for idx, row in df_padrao.iterrows():
        if "Retenção" in str(row.get("Tipo de Provento", "")):
            df_padrao.at[idx, "Impostos"] = float(row.get("Valor Líquido", 0))
            df_padrao.at[idx, "Valor Bruto"] = 0.0
        else:
            df_padrao.at[idx, "Valor Bruto"] = float(row.get("Valor Líquido", 0))
            df_padrao.at[idx, "Impostos"] = 0.0
    
    # Fonte passa a ser o usuário para facilitar filtro
    if "Usuário" in df_padrao.columns:
        df_padrao["Fonte"] = df_padrao["Usuário"]
    else:
        df_padrao["Fonte"] = "Avenue"
    
    # Selecionar apenas colunas finais
    colunas_finais = ["Data", "Ativo", "Valor Bruto", "Impostos", "Valor Líquido", "Fonte", "Usuário", "Mês/Ano"]

    return df_padrao[[col for col in colunas_finais if col in df_padrao.columns]]


def aba_acoes_avenue():
    """
    Aba para visualização de ações extraídas dos PDFs Avenue.
    """
    st.header("📈 Ações Avenue")
    
    # Carregar dados
    df_acoes = carregar_acoes_avenue()
    
    if df_acoes.empty:
        st.info("📭 Nenhuma ação extraída. Faça upload de PDFs na página de Upload.")
        return
    
    # Padronizar
    df_padrao = padronizar_acoes_avenue(df_acoes)
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total de Posições", len(df_padrao))
    
    with col2:
        valor_total = df_padrao.get("Valor de Mercado", pd.Series()).sum()
        st.metric("Valor Total de Mercado", f"${valor_total:,.2f}")
    
    with col3:
        quantidade_total = df_padrao.get("Quantidade", pd.Series()).sum()
        st.metric("Quantidade Total", f"{quantidade_total:,.2f}")
    
    with col4:
        if "Usuário" in df_padrao.columns:
            usuarios = df_padrao["Usuário"].nunique()
            st.metric("Usuários", usuarios)
    
    st.markdown("---")
    
    # Filtros
    col_f1, col_f2, col_f3 = st.columns(3)
    
    filtro_aplicado = False
    
    with col_f1:
        if "Ticker" in df_padrao.columns:
            tickers = sorted(df_padrao["Ticker"].unique())
            tickers_sel = st.multiselect(
                "Ticker",
                tickers,
                default=tickers,
                key="avenue_acoes_ticker"
            )
            filtro_aplicado = len(tickers_sel) < len(tickers)
    
    with col_f2:
        if "Usuário" in df_padrao.columns:
            usuarios = sorted(df_padrao["Usuário"].unique())
            usuarios_sel = st.multiselect(
                "Usuário",
                usuarios,
                default=usuarios,
                key="avenue_acoes_usuario"
            )
            filtro_aplicado = filtro_aplicado or len(usuarios_sel) < len(usuarios)
    
    with col_f3:
        if "Mês/Ano" in df_padrao.columns:
            meses = sorted(df_padrao["Mês/Ano"].unique())
            meses_sel = st.multiselect(
                "Mês/Ano",
                meses,
                default=meses,
                key="avenue_acoes_mes"
            )
            filtro_aplicado = filtro_aplicado or len(meses_sel) < len(meses)
    
    # Aplicar filtros
    df_filtrado = df_padrao
    
    if "Ticker" in df_padrao.columns and filtro_aplicado:
        if 'tickers_sel' in locals():
            df_filtrado = df_filtrado[df_filtrado["Ticker"].isin(tickers_sel)]
    
    if "Usuário" in df_padrao.columns and filtro_aplicado:
        if 'usuarios_sel' in locals():
            df_filtrado = df_filtrado[df_filtrado["Usuário"].isin(usuarios_sel)]
    
    if "Mês/Ano" in df_padrao.columns and filtro_aplicado:
        if 'meses_sel' in locals():
            df_filtrado = df_filtrado[df_filtrado["Mês/Ano"].isin(meses_sel)]
    
    # Ordenação
    col_ord1, col_ord2 = st.columns(2)
    
    with col_ord1:
        ordenacao = st.selectbox(
            "Ordenar por",
            ["Valor (maior)", "Valor (menor)", "Ticker (A-Z)", "Quantidade (maior)"],
            key="avenue_acoes_ordem"
        )
    
    # Aplicar ordenação
    if ordenacao == "Valor (maior)":
        df_filtrado = df_filtrado.sort_values("Valor de Mercado", ascending=False)
    elif ordenacao == "Valor (menor)":
        df_filtrado = df_filtrado.sort_values("Valor de Mercado", ascending=True)
    elif ordenacao == "Ticker (A-Z)":
        df_filtrado = df_filtrado.sort_values("Ticker", ascending=True)
    elif ordenacao == "Quantidade (maior)":
        df_filtrado = df_filtrado.sort_values("Quantidade", ascending=False)
    
    # Exibir tabela
    st.subheader("📊 Posições")
    st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
    
    # Gráficos
    st.markdown("---")
    st.subheader("📈 Análise")
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        if "Ticker" in df_filtrado.columns and "Valor de Mercado" in df_filtrado.columns:
            dist_ticker = df_filtrado.groupby("Ticker")["Valor de Mercado"].sum().sort_values(ascending=False).head(10)
            fig = px.bar(dist_ticker, title="Top 10 Maiores Posições", labels={"value": "Valor ($)", "index": "Ticker"})
            st.plotly_chart(fig, use_container_width=True)
    
    with col_chart2:
        if "Ativo" in df_filtrado.columns and "Quantidade" in df_filtrado.columns:
            dist_qtd = df_filtrado.nlargest(10, "Quantidade")[["Ativo", "Quantidade"]]
            fig = px.bar(dist_qtd, x="Ativo", y="Quantidade", title="Top 10 Maiores Quantidades")
            st.plotly_chart(fig, use_container_width=True)


def aba_proventos_avenue():
    """
    Aba para visualização de dividendos extraídos dos PDFs Avenue.
    """
    st.header("💰 Proventos Avenue")
    
    # Carregar dados
    df_divid = carregar_dividendos_avenue()
    
    if df_divid.empty:
        st.info("📭 Nenhum provento extraído. Faça upload de PDFs na página de Upload.")
        return
    
    # Padronizar (nota: isso cria Valor Bruto/Impostos a partir de heurísticas)
    df_padrao = padronizar_dividendos_avenue(df_divid)
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total de Registros", len(df_padrao))
    
    with col2:
        valor_bruto_total = df_padrao.get("Valor Bruto", pd.Series()).sum()
        st.metric("Valor Bruto Total", f"${valor_bruto_total:,.2f}")
    
    with col3:
        impostos_total = df_padrao.get("Impostos", pd.Series()).sum()
        st.metric("Impostos Totais", f"${impostos_total:,.2f}")
    
    with col4:
        valor_liquido_total = df_padrao.get("Valor Líquido", pd.Series()).sum()
        st.metric("Valor Líquido Total", f"${valor_liquido_total:,.2f}")
    
    st.markdown("---")
    
    # Filtros
    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        if "Ativo" in df_padrao.columns:
            ativos = sorted(df_padrao["Ativo"].unique())
            ativos_sel = st.multiselect(
                "Ativo",
                ativos,
                default=ativos,
                key="avenue_divid_ativo"
            )
    
    with col_f2:
        data_range = None
        if "Data" in df_padrao.columns:
            data_min = df_padrao["Data"].min()
            data_max = df_padrao["Data"].max()
            if pd.notna(data_min) and pd.notna(data_max):
                data_range = st.date_input(
                    "Período",
                    value=(data_min.date(), data_max.date()),
                    key="avenue_divid_data"
                )
            else:
                data_range = st.date_input(
                    "Período",
                    key="avenue_divid_data"
                )
    
    with col_f3:
        if "Fonte" in df_padrao.columns:
            fontes = sorted(df_padrao["Fonte"].unique())
            fontes_sel = st.multiselect(
                "Usuário",
                fontes,
                default=fontes,
                key="avenue_divid_fonte"
            )
    
    # Aplicar filtros
    df_filtrado = df_padrao
    
    if "Ativo" in df_padrao.columns:
        df_filtrado = df_filtrado[df_filtrado["Ativo"].isin(ativos_sel)]
    
    if "Data" in df_padrao.columns and data_range and len(data_range) == 2:
        df_filtrado = df_filtrado[
            (df_filtrado["Data"].dt.date >= data_range[0]) &
            (df_filtrado["Data"].dt.date <= data_range[1])
        ]
    
    if "Fonte" in df_padrao.columns:
        df_filtrado = df_filtrado[df_filtrado["Fonte"].isin(fontes_sel)]
    
    # Ordenação
    ordenacao = st.selectbox(
        "Ordenar por",
        ["Data (mais recente)", "Data (mais antigo)", "Valor Líquido (maior)", "Valor Líquido (menor)"],
        key="avenue_divid_ordem"
    )
    
    if ordenacao == "Data (mais recente)":
        df_filtrado = df_filtrado.sort_values("Data", ascending=False)
    elif ordenacao == "Data (mais antigo)":
        df_filtrado = df_filtrado.sort_values("Data", ascending=True)
    elif ordenacao == "Valor Líquido (maior)":
        df_filtrado = df_filtrado.sort_values("Valor Líquido", ascending=False)
    elif ordenacao == "Valor Líquido (menor)":
        df_filtrado = df_filtrado.sort_values("Valor Líquido", ascending=True)
    
    # Exibir tabela
    st.subheader("📊 Proventos")
    st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
    
    # Gráficos
    st.markdown("---")
    st.subheader("📈 Análise")
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        if "Ativo" in df_filtrado.columns and "Valor Líquido" in df_filtrado.columns:
            dist_ativo = df_filtrado.groupby("Ativo")["Valor Líquido"].sum().sort_values(ascending=False)
            fig = px.pie(values=dist_ativo.values, names=dist_ativo.index, title="Distribuição de Proventos por Ativo")
            st.plotly_chart(fig, use_container_width=True)
    
    with col_chart2:
        if "Data" in df_filtrado.columns and "Valor Líquido" in df_filtrado.columns:
            evolucao = df_filtrado.groupby(df_filtrado["Data"].dt.to_period("M"))["Valor Líquido"].sum()
            evolucao.index = evolucao.index.astype(str)
            fig = px.line(x=evolucao.index, y=evolucao.values, title="Evolução de Proventos", 
                         labels={"x": "Período", "y": "Valor ($)"})
            st.plotly_chart(fig, use_container_width=True)
    
    # Resumo por ativo
    st.markdown("---")
    st.subheader("📋 Resumo por Ativo")
    if "Ativo" in df_filtrado.columns:
        resumo = df_filtrado.groupby("Ativo").agg({
            "Valor Bruto": "sum",
            "Impostos": "sum",
            "Valor Líquido": "sum"
        }).reset_index().sort_values("Valor Líquido", ascending=False)
        st.dataframe(resumo, use_container_width=True, hide_index=True)


def aba_dividendo_consolidado():
    """
    Aba para visualização consolidada de dividendos (integra Avenue e outros).
    """
    st.header("💼 Dividendo Consolidado")
    
    # Carregar dados
    df_avenue = carregar_dividendos_avenue()
    df_avenue_padrao = padronizar_dividendos_avenue(df_avenue) if not df_avenue.empty else pd.DataFrame()
    
    # Aqui você pode adicionar dados de outras fontes
    # Por enquanto, consolidamos apenas Avenue
    df_consolidado = df_avenue_padrao
    
    if df_consolidado.empty:
        st.info("📭 Nenhum dividendo disponível. Faça upload de PDFs na página de Upload.")
        return
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total de Registros", len(df_consolidado))
    
    with col2:
        valor_bruto_total = df_consolidado.get("Valor Bruto", pd.Series()).sum()
        st.metric("Valor Bruto Total", f"${valor_bruto_total:,.2f}")
    
    with col3:
        impostos_total = df_consolidado.get("Impostos", pd.Series()).sum()
        st.metric("Impostos Totais", f"${impostos_total:,.2f}")
    
    with col4:
        valor_liquido_total = df_consolidado.get("Valor Líquido", pd.Series()).sum()
        st.metric("Valor Líquido Total", f"${valor_liquido_total:,.2f}")
    
    st.markdown("---")
    
    # Filtros
    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        if "Ativo" in df_consolidado.columns:
            ativos = sorted(df_consolidado["Ativo"].unique())
            ativos_sel = st.multiselect(
                "Ativo",
                ativos,
                default=ativos,
                key="consolidado_ativo"
            )
    
    with col_f2:
        if "Data" in df_consolidado.columns:
            data_min = df_consolidado["Data"].min()
            data_max = df_consolidado["Data"].max()
            try:
                data_range = st.date_input(
                    "Período",
                    value=(data_min.date() if pd.notna(data_min) else None, 
                           data_max.date() if pd.notna(data_max) else None),
                    key="consolidado_data"
                )
            except:
                data_range = None
    
    with col_f3:
        if "Fonte" in df_consolidado.columns:
            fontes = sorted(df_consolidado["Fonte"].unique())
            fontes_sel = st.multiselect(
                "Fonte",
                fontes,
                default=fontes,
                key="consolidado_fonte"
            )
    
    # Aplicar filtros
    df_filtrado = df_consolidado
    
    if "Ativo" in df_consolidado.columns:
        df_filtrado = df_filtrado[df_filtrado["Ativo"].isin(ativos_sel)]
    
    if "Data" in df_consolidado.columns and data_range and len(data_range) == 2:
        try:
            df_filtrado = df_filtrado[
                (df_filtrado["Data"].dt.date >= data_range[0]) &
                (df_filtrado["Data"].dt.date <= data_range[1])
            ]
        except:
            pass
    
    if "Fonte" in df_consolidado.columns:
        df_filtrado = df_filtrado[df_filtrado["Fonte"].isin(fontes_sel)]
    
    # Ordenação
    ordenacao = st.selectbox(
        "Ordenar por",
        ["Data (mais recente)", "Data (mais antigo)", "Valor Líquido (maior)", "Valor Líquido (menor)", "Ativo (A-Z)"],
        key="consolidado_ordem"
    )
    
    if ordenacao == "Data (mais recente)":
        df_filtrado = df_filtrado.sort_values("Data", ascending=False)
    elif ordenacao == "Data (mais antigo)":
        df_filtrado = df_filtrado.sort_values("Data", ascending=True)
    elif ordenacao == "Valor Líquido (maior)":
        df_filtrado = df_filtrado.sort_values("Valor Líquido", ascending=False)
    elif ordenacao == "Valor Líquido (menor)":
        df_filtrado = df_filtrado.sort_values("Valor Líquido", ascending=True)
    elif ordenacao == "Ativo (A-Z)":
        df_filtrado = df_filtrado.sort_values("Ativo", ascending=True)
    
    # Exibir tabela
    st.subheader("📊 Dividendos")
    st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
    
    # Exportação
    st.markdown("---")
    st.subheader("📥 Exportar Dados")
    
    col_exp1, col_exp2 = st.columns(2)
    
    with col_exp1:
        csv = df_filtrado.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="📥 Baixar como CSV",
            data=csv,
            file_name=f"dividendos_consolidado_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    
    with col_exp2:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_filtrado.to_excel(writer, index=False, sheet_name="Dividendos")
        buffer.seek(0)
        st.download_button(
            label="📥 Baixar como Excel",
            data=buffer,
            file_name=f"dividendos_consolidado_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    # Análise
    st.markdown("---")
    st.subheader("📈 Análise")
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        if "Ativo" in df_filtrado.columns and "Valor Líquido" in df_filtrado.columns:
            dist_ativo = df_filtrado.groupby("Ativo")["Valor Líquido"].sum().sort_values(ascending=False)
            fig = px.bar(dist_ativo, title="Dividendos por Ativo", labels={"value": "Valor Líquido ($)", "index": "Ativo"})
            st.plotly_chart(fig, use_container_width=True)
    
    with col_chart2:
        if "Data" in df_filtrado.columns and "Valor Líquido" in df_filtrado.columns:
            evolucao = df_filtrado.groupby(df_filtrado["Data"].dt.to_period("M"))["Valor Líquido"].sum()
            evolucao.index = evolucao.index.astype(str)
            fig = px.line(x=evolucao.index, y=evolucao.values, title="Evolução de Dividendos", 
                         labels={"x": "Período", "y": "Valor Líquido ($)"})
            st.plotly_chart(fig, use_container_width=True)
    
    # Resumo por ativo
    st.markdown("---")
    st.subheader("💹 Resumo por Ativo")
    if "Ativo" in df_filtrado.columns:
        resumo = df_filtrado.groupby("Ativo").agg({
            "Valor Bruto": "sum",
            "Impostos": "sum",
            "Valor Líquido": "sum"
        }).reset_index().sort_values("Valor Líquido", ascending=False)
        st.dataframe(resumo, use_container_width=True, hide_index=True)
    
    # Resumo por mês
    st.markdown("---")
    st.subheader("📅 Resumo por Período")
    if "Data" in df_filtrado.columns:
        resumo_mes = df_filtrado.groupby(df_filtrado["Data"].dt.to_period("M")).agg({
            "Valor Bruto": "sum",
            "Impostos": "sum",
            "Valor Líquido": "sum"
        }).reset_index()
        resumo_mes.columns = ["Período", "Valor Bruto", "Impostos", "Valor Líquido"]
        resumo_mes["Período"] = resumo_mes["Período"].astype(str)
        st.dataframe(resumo_mes, use_container_width=True, hide_index=True)
