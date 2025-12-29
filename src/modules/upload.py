import pandas as pd

__all__ = [
    'validar_csv',
    'importar_csv'
]

# =========================
# Função para validar CSV
# =========================
def validar_csv(df):
    """
    Verifica se o CSV contém as colunas obrigatórias:
    Pessoa, Produto, Categoria, Valor, Moeda
    """
    colunas_obrigatorias = ["Pessoa", "Produto", "Categoria", "Valor", "Moeda"]
    for coluna in colunas_obrigatorias:
        if coluna not in df.columns:
            return False
    return True

# =========================
# Função para importar CSV
# =========================
def importar_csv(file):
    """
    Lê o arquivo CSV e retorna uma lista de dicionários para integrar ao sistema.
    """
    try:
        df = pd.read_csv(file)
        if validar_csv(df):
            return df.to_dict(orient="records")
        else:
            raise ValueError("CSV inválido. Colunas obrigatórias: Pessoa, Produto, Categoria, Valor, Moeda")
    except Exception as e:
        raise ValueError(f"Erro ao importar CSV: {e}")
