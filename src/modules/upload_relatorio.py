
import pandas as pd
import os

PARQUET_PATH = "data/historico_investimentos.parquet"

def ler_relatorio_excel(file, usuario, mes_ano):
    xls = pd.ExcelFile(file)
    historico = []

    for nome in xls.sheet_names:
        if "Ações" in nome:
            df_acoes = pd.read_excel(xls, sheet_name=nome, skiprows=1)
            df_acoes = df_acoes.dropna(how='all')
            df_acoes["Tipo"] = "Ações"
            if not df_acoes.empty:
                print('Ações:', df_acoes.head())
                historico.append(df_acoes)
        if "Renda Fixa" in nome:
            df_rf = pd.read_excel(xls, sheet_name=nome, skiprows=1)
            df_rf = df_rf.dropna(how='all')
            df_rf["Tipo"] = "Renda Fixa"
            if not df_rf.empty:
                print('Renda Fixa:', df_rf.head())
                historico.append(df_rf)
        if "Proventos" in nome:
            df_prov = pd.read_excel(xls, sheet_name=nome, skiprows=0)
            df_prov = df_prov.dropna(how='all')
            df_prov["Tipo"] = "Proventos"
            if not df_prov.empty:
                print('Proventos:', df_prov.head())
                historico.append(df_prov)
    if historico:
        df_total = pd.concat(historico, ignore_index=True)
        df_total["Mês/Ano"] = mes_ano
        df_total["Usuário"] = usuario
        return df_total
    else:
        return pd.DataFrame()


def salvar_historico_parquet(df_novo):
    # Carrega histórico existente, se houver
    if os.path.exists(PARQUET_PATH):
        df_antigo = pd.read_parquet(PARQUET_PATH)
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
