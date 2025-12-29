import pandas as pd
import os

ACOES_PATH = "data/acoes.parquet"
RENDA_FIXA_PATH = "data/renda_fixa.parquet"
PROVENTOS_PATH = "data/proventos.parquet"

def ler_relatorio_excel(file, usuario, mes_ano):
    xls = pd.ExcelFile(file)
    historico = []

    for nome in xls.sheet_names:
        if "Ações" in nome:
            df_acoes = pd.read_excel(xls, sheet_name=nome, skiprows=1)
            df_acoes["Tipo"] = "Ações"
            historico.append(df_acoes)
        if "Renda Fixa" in nome:
            df_rf = pd.read_excel(xls, sheet_name=nome, skiprows=1)
            df_rf["Tipo"] = "Renda Fixa"
            historico.append(df_rf)
    if historico:
        df_total = pd.concat(historico, ignore_index=True)

        # Normalizar nomes das colunas
        df_total.columns = [str(col).strip().replace("\n", " ").replace("  ", " ").replace("  ", " ") for col in df_total.columns]
        df_total.columns = [col.replace(".", "").replace("-", "_").replace("/", "_") for col in df_total.columns]
        df_total.columns = [col.replace("  ", " ").replace("  ", " ") for col in df_total.columns]

        # Garantir que as colunas 'Mês/Ano' e 'Usuário' existam exatamente com esses nomes
        df_total["Mês/Ano"] = mes_ano
        df_total["Usuário"] = usuario

        # Corrigir colunas numéricas: remover linhas com valores não numéricos
        for col in df_total.columns:
            if df_total[col].dtype == object:
                df_total[col] = pd.to_numeric(df_total[col], errors='ignore')
        num_cols = df_total.select_dtypes(include=['float', 'int']).columns
        if len(num_cols) > 0:
            df_total = df_total.dropna(subset=num_cols, how='all')

        return df_total
    else:
        return pd.DataFrame()

    PROVENTOS_PATH = "data/proventos.parquet"

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
    if os.path.exists(path):
        df_antigo = pd.read_parquet(path)
        usuario = df_tipo["Usuário"].iloc[0]
        mes_ano = df_tipo["Mês/Ano"].iloc[0]
        df_antigo = df_antigo[~((df_antigo["Usuário"] == usuario) & (df_antigo["Mês/Ano"] == mes_ano))]
        df_consolidado = pd.concat([df_antigo, df_tipo], ignore_index=True)
    else:
        df_consolidado = df_tipo
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
