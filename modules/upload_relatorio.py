def remover_linhas_totais(df, col_valor, palavras_totais=["total", "totais"]):
    df = df.copy()
    # Remove linhas onde todas as colunas estão vazias
    df = df.dropna(how="all")
    # Remove linhas onde a coluna de valor contém palavras de totalização
    if col_valor in df.columns:
        mask = df[col_valor].astype(str).str.lower().str.contains('|'.join(palavras_totais))
        df = df[~mask]
    # Remove linhas onde qualquer coluna essencial está vazia
    colunas_essenciais = [col for col in df.columns if col not in ["Usuário", "Mês/Ano"]]
    if colunas_essenciais:
        df = df.dropna(subset=colunas_essenciais, how="any")
    # Remove linhas após a última linha válida (onde a coluna de valor não é vazia)
    if col_valor in df.columns:
        last_valid = df[df[col_valor].notna()].index.max()
        if pd.notna(last_valid):
            df = df.loc[:last_valid]
    return df
def limpar_colunas_duplicadas(df):
    # Renomeia colunas duplicadas adicionando sufixo incremental
    cols = pd.Series(df.columns)
    for dup in cols[cols.duplicated()].unique():
        idxs = cols[cols == dup].index.tolist()
        for i, idx in enumerate(idxs):
            if i == 0:
                continue
            cols[idx] = f"{dup}.{i}"
    df.columns = cols
    return df
PARQUET_PATH = "data/historico_investimentos.parquet"
import pandas as pd
import os

ACOES_PATH = "data/acoes.parquet"
RENDA_FIXA_PATH = "data/renda_fixa.parquet"
PROVENTOS_PATH = "data/proventos.parquet"

def ler_relatorio_excel(file, usuario, mes_ano):
    import streamlit as st
    xls = pd.ExcelFile(file)
    df_acoes = pd.DataFrame()
    df_rf = pd.DataFrame()
    df_prov = pd.DataFrame()

    # Cabeçalho padrão para ações
    colunas_acoes = [
        "Produto", "Instituição", "Conta", "Código de Negociação", "CNPJ da Empresa", "Código ISIN / Distribuição",
        "Tipo", "Escriturador", "Quantidade", "Quantidade Disponível", "Quantidade Indisponível", "Motivo",
        "Preço de Fechamento", "Valor Atualizado"
    ]
    # Cabeçalhos padrão para Renda Fixa e Proventos
    colunas_rf = [
        "Produto", "Instituição", "Conta", "Código de Negociação", "CNPJ da Empresa", "Código ISIN / Distribuição",
        "Tipo", "Escriturador", "Quantidade", "Quantidade Disponível", "Quantidade Indisponível", "Motivo",
        "Preço de Fechamento", "Valor Atualizado"
    ]
    colunas_prov = [
        "Produto", "Instituição", "Conta", "Código de Negociação", "CNPJ da Empresa", "Código ISIN / Distribuição",
        "Tipo de Provento", "Data de Pagamento", "Quantidade", "Valor do Provento", "Valor Líquido", "Mês/Ano", "Usuário"
    ]

    def normalizar_nome(col):
        return (
            str(col)
            .strip()
            .replace("\n", " ")
            .replace("  ", " ")
            .replace("  ", " ")
            .replace(".", "")
            .replace("-", "_")
            .replace("/", "_")
            .replace("ã", "a").replace("á", "a").replace("â", "a").replace("é", "e").replace("ê", "e")
            .replace("í", "i").replace("ó", "o").replace("ô", "o").replace("õ", "o").replace("ú", "u")
            .replace("ç", "c")
            .lower()
        )
    colunas_acoes_norm = [normalizar_nome(c) for c in colunas_acoes]
    colunas_rf_norm = [normalizar_nome(c) for c in colunas_rf]
    colunas_prov_norm = [normalizar_nome(c) for c in colunas_prov]

    colunas_essenciais = [
        "Produto",
        "Código de Negociação",
        "Quantidade Disponível",
        "Preço de Fechamento",
        "Valor Atualizado",
        "Mês/Ano",
        "Usuário"
    ]
    for nome in xls.sheet_names:
        if "Ações" in nome:
            # Detectar automaticamente o cabeçalho correto
            df_tmp = pd.read_excel(xls, sheet_name=nome, header=None)
            header_row = None
            for i in range(min(10, len(df_tmp))):
                row = df_tmp.iloc[i].astype(str).str.lower().tolist()
                if ("produto" in row or "codigo de negociacao" in row) and ("quantidade disponivel" in row or "valor atualizado" in row):
                    header_row = i
                    break
            if header_row is not None:
                df_acoes = pd.read_excel(xls, sheet_name=nome, header=header_row)
            else:
                df_acoes = pd.read_excel(xls, sheet_name=nome, skiprows=1)
            df_acoes = limpar_colunas_duplicadas(df_acoes)
            # Normalizar nomes das colunas lidas
            colunas_lidas_norm = [normalizar_nome(c) for c in df_acoes.columns]
            mapeamento = {}
            for i, col_norm in enumerate(colunas_lidas_norm):
                for j, col_padrao in enumerate(colunas_acoes_norm):
                    if col_norm == col_padrao:
                        mapeamento[df_acoes.columns[i]] = colunas_acoes[j]
            df_acoes = df_acoes.rename(columns=mapeamento)
            df_acoes["Mês/Ano"] = mes_ano
            df_acoes["Usuário"] = usuario
            # Manter apenas as colunas essenciais
            df_acoes = df_acoes[[c for c in colunas_essenciais if c in df_acoes.columns]]
            # Remover linhas de totais/extras
            df_acoes = remover_linhas_totais(df_acoes, "Valor Atualizado")
        if "Renda Fixa" in nome:
            # Detectar automaticamente o cabeçalho correto
            df_tmp = pd.read_excel(xls, sheet_name=nome, header=None)
            header_row = None
            for i in range(min(10, len(df_tmp))):
                row = df_tmp.iloc[i].astype(str).str.lower().tolist()
                if ("produto" in row or "codigo de negociacao" in row) and ("quantidade disponivel" in row or "valor atualizado" in row or "valor atualizado curva" in row):
                    header_row = i
                    break
            if header_row is not None:
                df_rf = pd.read_excel(xls, sheet_name=nome, header=header_row)
            else:
                df_rf = pd.read_excel(xls, sheet_name=nome, skiprows=1)
            df_rf = limpar_colunas_duplicadas(df_rf)
            df_rf["Mês/Ano"] = mes_ano
            df_rf["Usuário"] = usuario
            if "Código" not in df_rf.columns and "Código de Negociação" in df_rf.columns:
                df_rf = df_rf.rename(columns={"Código de Negociação": "Código"})
            # Padronizar coluna de valor
            if "Valor Atualizado CURVA" in df_rf.columns:
                df_rf["Valor Atualizado"] = df_rf["Valor Atualizado CURVA"]
            # Se Valor Atualizado está vazio, nulo ou '-', preenche com Valor Atualizado MTM
            if "Valor Atualizado MTM" in df_rf.columns:
                mask_vazio = (
                    df_rf["Valor Atualizado"].isna() |
                    (df_rf["Valor Atualizado"].astype(str).str.strip() == "") |
                    (df_rf["Valor Atualizado"].astype(str).str.strip() == "-")
                )
                df_rf.loc[mask_vazio, "Valor Atualizado"] = df_rf.loc[mask_vazio, "Valor Atualizado MTM"]
            # Manter apenas as colunas essenciais
            df_rf = df_rf[[c for c in colunas_essenciais if c in df_rf.columns]]
            # Remover linhas de totais/extras
            df_rf = remover_linhas_totais(df_rf, "Valor Atualizado")
        if "Proventos" in nome:
            # Detectar automaticamente o cabeçalho correto
            df_tmp = pd.read_excel(xls, sheet_name=nome, header=None)
            header_row = None
            for i in range(min(10, len(df_tmp))):
                row = df_tmp.iloc[i].astype(str).str.lower().tolist()
                if ("produto" in row or "tipo de provento" in row) and ("valor liquido" in row or "valor do provento" in row):
                    header_row = i
                    break
            if header_row is not None:
                df_prov = pd.read_excel(xls, sheet_name=nome, header=header_row)
            else:
                df_prov = pd.read_excel(xls, sheet_name=nome, skiprows=1)
            df_prov = limpar_colunas_duplicadas(df_prov)
            df_prov["Mês/Ano"] = mes_ano
            df_prov["Usuário"] = usuario
            if "Código" not in df_prov.columns and "Código de Negociação" in df_prov.columns:
                df_prov = df_prov.rename(columns={"Código de Negociação": "Código"})
            # Selecionar apenas as colunas essenciais para proventos
            # Mapeamento robusto de colunas
            mapeamento_prov = {}
            for col in df_prov.columns:
                col_norm = normalizar_nome(col)
                if col_norm.startswith("pagamento"):
                    mapeamento_prov[col] = "Data de Pagamento"
                elif col_norm.startswith("tipo de evento") or col_norm.startswith("tipo de provento"):
                    mapeamento_prov[col] = "Tipo de Provento"
                elif col_norm.startswith("valor liquido"):
                    mapeamento_prov[col] = "Valor Líquido"
                elif col_norm.startswith("produto"):
                    mapeamento_prov[col] = "Produto"
            df_prov = df_prov.rename(columns=mapeamento_prov)
            colunas_essenciais_prov = [
                "Produto", "Data de Pagamento", "Tipo de Provento", "Valor Líquido", "Mês/Ano", "Usuário"
            ]
            # Adicionar colunas faltantes como vazias para garantir exibição
            for col in colunas_essenciais_prov:
                if col not in df_prov.columns:
                    df_prov[col] = ""
            df_prov = df_prov.loc[:,~df_prov.columns.duplicated()]
            df_prov = df_prov[colunas_essenciais_prov]
            # Remover linhas de totais/extras (linhas com 'Total' ou 'R$' sem valor numérico)
            if "Valor Líquido" in df_prov.columns:
                # Remove linhas onde Valor Líquido contém 'Total' ou não é número
                mask_total = df_prov["Valor Líquido"].astype(str).str.lower().str.contains("total")
                mask_vazio = ~df_prov["Valor Líquido"].astype(str).str.replace("R$", "").str.replace(",", ".").str.replace(" ", "").str.replace("-", "").str.replace(".", "", regex=False).str.isnumeric()
                df_prov = df_prov[~mask_total & ~mask_vazio]
                # Converter Valor Líquido para número
                df_prov["Valor Líquido"] = df_prov["Valor Líquido"].astype(str).str.replace("R$", "").str.replace(" ", "").str.replace(",", ".").str.replace("-", "0").astype(float)

    return df_acoes, df_rf, df_prov

    def ler_relatorio_excel(file, usuario, mes_ano):
        xls = pd.ExcelFile(file)
        df_acoes = pd.DataFrame()
        df_rf = pd.DataFrame()
        df_prov = pd.DataFrame()

        for nome in xls.sheet_names:
            if "Ações" in nome:
                df_acoes = pd.read_excel(xls, sheet_name=nome, skiprows=1)
                df_acoes["Mês/Ano"] = mes_ano
                df_acoes["Usuário"] = usuario
                if "Código" not in df_acoes.columns and "Código de Negociação" in df_acoes.columns:
                    df_acoes = df_acoes.rename(columns={"Código de Negociação": "Código"})
            if "Renda Fixa" in nome:
                df_rf = pd.read_excel(xls, sheet_name=nome, skiprows=1)
                df_rf["Mês/Ano"] = mes_ano
                df_rf["Usuário"] = usuario
                if "Código" not in df_rf.columns and "Código de Negociação" in df_rf.columns:
                    df_rf = df_rf.rename(columns={"Código de Negociação": "Código"})
            if "Proventos" in nome:
                df_prov = pd.read_excel(xls, sheet_name=nome, skiprows=1)
                df_prov["Mês/Ano"] = mes_ano
                df_prov["Usuário"] = usuario
                if "Código" not in df_prov.columns and "Código de Negociação" in df_prov.columns:
                    df_prov = df_prov.rename(columns={"Código de Negociação": "Código"})

        return df_acoes, df_rf, df_prov



def salvar_tipo_parquet(df_tipo, path):
    # Se o DataFrame está vazio, não salva nem tenta acessar iloc[0]
    if df_tipo.empty or len(df_tipo) == 0:
        return df_tipo
    # Limpar linhas de totais e garantir colunas numéricas corretas
    df_tipo = df_tipo.copy()
    # Tentar converter todas as colunas possíveis para numérico, exceto as categóricas
    for col in df_tipo.columns:
        if col not in ["Usuário", "Mês/Ano", "Código", "Tipo"]:
            df_tipo[col] = pd.to_numeric(df_tipo[col], errors="coerce")
    # Remover linhas onde todas as colunas numéricas são NaN (ex: linhas de total)
    num_cols = df_tipo.select_dtypes(include=["float", "int"]).columns
    if len(num_cols) > 0:
        df_tipo = df_tipo.dropna(subset=num_cols, how="all")

    # Definir colunas essenciais conforme o tipo de arquivo
    if 'Valor Líquido' in df_tipo.columns:
        colunas_essenciais = ["Produto", "Data de Pagamento", "Tipo de Provento", "Valor Líquido", "Mês/Ano", "Usuário"]
    else:
        colunas_essenciais = ["Produto", "Código de Negociação", "Quantidade Disponível", "Preço de Fechamento", "Valor Atualizado", "Mês/Ano", "Usuário"]

    # Limpar duplicidade e manter só essenciais no novo
    df_tipo = df_tipo.loc[:,~df_tipo.columns.duplicated()]
    df_tipo = df_tipo[[c for c in colunas_essenciais if c in df_tipo.columns]]

    if os.path.exists(path):
        df_antigo = pd.read_parquet(path)
        # Limpar duplicidade e manter só essenciais no antigo
        df_antigo = df_antigo.loc[:,~df_antigo.columns.duplicated()]
        df_antigo = df_antigo[[c for c in colunas_essenciais if c in df_antigo.columns]]
        usuario = df_tipo["Usuário"].iloc[0]
        mes_ano = df_tipo["Mês/Ano"].iloc[0]
        df_antigo = df_antigo[~((df_antigo["Usuário"] == usuario) & (df_antigo["Mês/Ano"] == mes_ano))]
        df_consolidado = pd.concat([df_antigo, df_tipo], ignore_index=True)
    else:
        df_consolidado = df_tipo
    df_consolidado = df_consolidado.loc[:,~df_consolidado.columns.duplicated()]
    df_consolidado = df_consolidado[[c for c in colunas_essenciais if c in df_consolidado.columns]]
    df_consolidado.to_parquet(path)
    return df_consolidado


def salvar_historico_parquet(df_novo):
    # Carrega histórico existente, se houver
    if os.path.exists(PARQUET_PATH):
        df_antigo = pd.read_parquet(PARQUET_PATH)
        # Remove registros do mesmo usuário e mês/ano
        usuario = df_novo["Usuário"].iloc[0]
        mes_ano = df_novo["Mês/Ano"].iloc[0]
        df_antigo = df_antigo[~((df_antigo["Usuário"] == usuario) & (df_antigo["Mês/Ano"] == mes_ano))]
        df_consolidado = pd.concat([df_antigo, df_novo], ignore_index=True)
    else:
        df_consolidado = df_novo
    # Salva consolidado
    df_consolidado.to_parquet(PARQUET_PATH)
    return df_consolidado

def carregar_historico_parquet():
    if os.path.exists(PARQUET_PATH):
        return pd.read_parquet(PARQUET_PATH)
    else:
        return pd.DataFrame()
