import pandas as pd
import os

USUARIOS_PATH = "data/usuarios.parquet"

def carregar_usuarios():
    if os.path.exists(USUARIOS_PATH):
        return pd.read_parquet(USUARIOS_PATH)
    else:
        return pd.DataFrame(columns=["Nome", "CPF"])

def salvar_usuarios(df_usuarios):
    df_usuarios.to_parquet(USUARIOS_PATH)
