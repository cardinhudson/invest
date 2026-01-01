import os
import re
import pandas as pd

PARQUET_PATH = "data/historico_investimentos.parquet"
ACOES_PATH = "data/acoes.parquet"
RENDA_FIXA_PATH = "data/renda_fixa.parquet"
PROVENTOS_PATH = "data/proventos.parquet"
UPLOADS_DIR = "uploads"


def garantir_colunas(df: pd.DataFrame, colunas):
    df = df.copy()
    for col in colunas:
        if col not in df.columns:
            df[col] = None
    return df


def coerci_numericos(df: pd.DataFrame, palavras=None) -> pd.DataFrame:
    if palavras is None:
        palavras = ["valor", "preço", "preco", "quantidade"]
    df = df.copy()
    for col in df.columns:
        col_lower = str(col).lower()
        if any(p in col_lower for p in palavras):
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def extrair_mes_ano_nome(nome: str):
    # Suporta padrões numéricos (01-2025, 01_2025, 012025, 01/2025)
    padrao_num = re.search(r"(0[1-9]|1[0-2])[-_\\/]?((20|19)\d{2})", nome)
    if padrao_num:
        mm, aaaa = padrao_num.group(1), padrao_num.group(2)
        return f"{mm}/{aaaa}"

    # Suporta nomes de mês em português, ex.: relatorio-consolidado-mensal-2024-abril.xlsx
    meses = {
        "janeiro": "01", "jan": "01",
        "fevereiro": "02", "fev": "02",
        "marco": "03", "março": "03", "mar": "03",
        "abril": "04", "abr": "04",
        "maio": "05", "mai": "05",
        "junho": "06", "jun": "06",
        "julho": "07", "jul": "07",
        "agosto": "08", "ago": "08",
        "setembro": "09", "set": "09",
        "outubro": "10", "out": "10",
        "novembro": "11", "nov": "11",
        "dezembro": "12", "dez": "12",
    }
    nome_low = nome.lower().replace("ç", "c").replace("ã", "a").replace("â", "a").replace("á", "a").replace("à", "a").replace("é", "e").replace("ê", "e").replace("í", "i").replace("ó", "o").replace("ô", "o").replace("õ", "o").replace("ú", "u")
    # Busca ano e mês por palavras, aceitando separadores - _ ou espaço
    ano_match = re.search(r"(20|19)\d{2}", nome_low)
    if ano_match:
        ano = ano_match.group(0)
        for nome_mes, mm in meses.items():
            if nome_mes in nome_low:
                return f"{mm}/{ano}"
    return None


def limpar_colunas_duplicadas(df: pd.DataFrame) -> pd.DataFrame:
    cols = pd.Series(df.columns)
    for dup in cols[cols.duplicated()].unique():
        idxs = cols[cols == dup].index.tolist()
        for i, idx in enumerate(idxs):
            if i == 0:
                continue
            cols[idx] = f"{dup}.{i}"
    df.columns = cols
    return df


def normalizar_nome_sheet(nome: str) -> str:
    return nome.lower().replace("ções", "coes").replace("ção", "cao").replace("ã", "a").replace("á", "a").replace("â", "a")


def detectar_header(df_tmp: pd.DataFrame, palavras_chave, max_linhas: int = 8):
    for i in range(min(max_linhas, len(df_tmp))):
        row = df_tmp.iloc[i].astype(str).str.lower().tolist()
        acertos = sum(any(p in cel for cel in row) for p in palavras_chave)
        if acertos >= 2:
            return i
    return None


def classificar_sheet(nome: str, df: pd.DataFrame):
    cols_lower = [str(c).lower() for c in df.columns]
    def score(keys):
        return sum(any(k in c for c in cols_lower) for k in keys)

    bonus_acao = 1 if any(k in normalizar_nome_sheet(nome) for k in ["acao", "acoes", "renda variavel", "variavel"]) else 0
    bonus_rf = 1 if any(k in normalizar_nome_sheet(nome) for k in ["renda fixa", "rf"]) else 0
    bonus_prov = 1 if any(k in normalizar_nome_sheet(nome) for k in ["provento", "proventos", "rendimentos"]) else 0

    score_acoes = score(["código de negociação", "codigo de negociacao", "escriturador", "preço de fechamento", "valor atualizado", "isin"]) + bonus_acao
    score_rf = score(["mtm", "curva", "indexador", "regime", "vencimento", "emissor", "contraparte"]) + bonus_rf
    score_prov = score(["provento", "rendimentos", "pagamento", "valor líquido", "valor liquido"]) + bonus_prov

    max_score = max(score_acoes, score_rf, score_prov)
    if max_score == 0:
        return None
    if max_score == score_acoes:
        return "acoes"
    if max_score == score_rf:
        return "rf"
    return "prov"


def remover_totais_e_vazios(df: pd.DataFrame, colunas_essenciais) -> pd.DataFrame:
    df = df.copy()
    # Remove qualquer linha que traga palavras de totalização em qualquer coluna
    mask_total = df.apply(
        lambda row: any(re.search(r"\b(sub)?total\b", str(val).lower()) for val in row), axis=1
    )
    df = df[~mask_total]

    # Exige valor presente nas colunas essenciais (evita linhas de total com produto vazio)
    if colunas_essenciais:
        keep_mask = pd.Series(True, index=df.index)
        for col in colunas_essenciais:
            if col not in df.columns:
                continue
            serie = df[col]
            valido = (
                serie.notna()
                & (serie.astype(str).str.strip() != "")
                & (serie.astype(str).str.strip() != "-")
                & (~serie.astype(str).str.lower().isin(["nan", "none"]))
            )
            keep_mask &= valido
        df = df[keep_mask]
    return df


def criar_coluna_valor_renda_fixa(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Valor"] = df.get("Valor Atualizado MTM")
    if "Valor Atualizado CURVA" in df.columns:
        mask = df["Valor"].isna() | (df["Valor"] == "") | (df["Valor"] == "-")
        df.loc[mask, "Valor"] = df.loc[mask, "Valor Atualizado CURVA"]
    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce")
    return df


def criar_coluna_valor_acoes(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Valor"] = pd.to_numeric(df.get("Valor Atualizado"), errors="coerce")
    return df


def filtrar_linhas_ativas(df: pd.DataFrame, coluna_valor: str) -> pd.DataFrame:
    df = df.copy()
    if coluna_valor not in df.columns:
        return df.iloc[0:0]
    df[coluna_valor] = pd.to_numeric(df[coluna_valor], errors="coerce")
    df = df[df[coluna_valor].notnull() & (df[coluna_valor] > 0)]
    return df


def filtrar_proventos(df: pd.DataFrame, colunas_essenciais) -> pd.DataFrame:
    df = remover_totais_e_vazios(df, colunas_essenciais)
    if len(df) > 1:
        ultima = df.iloc[-1]
        if (
            any(str(ultima.get(col, "")).lower().strip() in ["total", "subtotal", ""] for col in colunas_essenciais)
            or pd.isna(ultima.get("Produto"))
            or str(ultima.get("Produto", "")).strip() == ""
        ):
            df = df.iloc[:-1]
    if "Valor Líquido" in df.columns:
        df["Valor Líquido"] = pd.to_numeric(df["Valor Líquido"], errors="coerce")
        df = df[df["Valor Líquido"].notnull() & (df["Valor Líquido"] > 0)]
    return df


def ler_relatorio_excel(file, usuario: str, mes_ano: str):
    xls = pd.ExcelFile(file)
    df_acoes_lista = []
    df_rf_lista = []
    df_prov_lista = []

    for nome in xls.sheet_names:
        df_tmp = pd.read_excel(xls, sheet_name=nome, header=None)
        header_row = detectar_header(df_tmp, ["produto", "valor", "quantidade", "codigo", "pagamento", "provento"])
        if header_row is None:
            header_row = 0
        df_sheet = pd.read_excel(xls, sheet_name=nome, header=header_row)
        df_sheet = limpar_colunas_duplicadas(df_sheet)
        tipo = classificar_sheet(nome, df_sheet)

        if tipo == "rf":
            df_rf = df_sheet
            colunas_essenciais_rf = [
                "Produto", "Instituição", "Emissor", "Código", "Indexador", "Tipo de regime", "Data de Emissão", "Vencimento",
                "Quantidade", "Quantidade Disponível", "Quantidade Indisponível", "Motivo", "Contraparte",
                "Preço Atualizado MTM", "Valor Atualizado MTM", "Preço Atualizado CURVA", "Valor Atualizado CURVA"
            ]
            for col in colunas_essenciais_rf:
                if col not in df_rf.columns:
                    for c in df_rf.columns:
                        if col.lower() in str(c).lower():
                            df_rf[col] = df_rf[c]
            df_rf = garantir_colunas(df_rf, colunas_essenciais_rf)
            df_rf = criar_coluna_valor_renda_fixa(df_rf)
            df_rf["Mês/Ano"] = mes_ano
            df_rf["Usuário"] = usuario
            df_rf = remover_totais_e_vazios(df_rf, ["Produto", "Valor"])
            df_rf = filtrar_linhas_ativas(df_rf, "Valor")
            df_rf = df_rf[colunas_essenciais_rf + ["Valor", "Mês/Ano", "Usuário"]]
            df_rf_lista.append(df_rf)

        elif tipo == "acoes":
            df_acoes = df_sheet
            colunas_essenciais_acoes = [
                "Produto", "Instituição", "Conta", "Código de Negociação", "CNPJ da Empresa", "Código ISIN / Distribuição",
                "Tipo", "Escriturador", "Quantidade", "Quantidade Disponível", "Quantidade Indisponível", "Motivo",
                "Preço de Fechamento", "Valor Atualizado"
            ]
            for col in colunas_essenciais_acoes:
                if col not in df_acoes.columns:
                    for c in df_acoes.columns:
                        if col.lower() in str(c).lower():
                            df_acoes[col] = df_acoes[c]
            df_acoes = garantir_colunas(df_acoes, colunas_essenciais_acoes)
            df_acoes = criar_coluna_valor_acoes(df_acoes)
            df_acoes["Mês/Ano"] = mes_ano
            df_acoes["Usuário"] = usuario
            df_acoes = remover_totais_e_vazios(df_acoes, ["Produto", "Valor"])
            df_acoes = filtrar_linhas_ativas(df_acoes, "Valor")
            df_acoes = df_acoes[colunas_essenciais_acoes + ["Valor", "Mês/Ano", "Usuário"]]
            df_acoes_lista.append(df_acoes)

        elif tipo == "prov":
            df_prov = df_sheet
            colunas_essenciais_prov = ["Produto", "Data de Pagamento", "Tipo de Provento", "Valor Líquido"]
            for col in colunas_essenciais_prov:
                if col not in df_prov.columns:
                    for c in df_prov.columns:
                        if col.lower() in str(c).lower():
                            df_prov[col] = df_prov[c]
            df_prov = garantir_colunas(df_prov, colunas_essenciais_prov)
            df_prov["Mês/Ano"] = mes_ano
            df_prov["Usuário"] = usuario
            df_prov = filtrar_proventos(df_prov, colunas_essenciais_prov)
            df_prov = df_prov[colunas_essenciais_prov + ["Mês/Ano", "Usuário"]]
            df_prov_lista.append(df_prov)

    df_acoes_final = pd.concat(df_acoes_lista, ignore_index=True) if df_acoes_lista else pd.DataFrame()
    df_rf_final = pd.concat(df_rf_lista, ignore_index=True) if df_rf_lista else pd.DataFrame()
    df_prov_final = pd.concat(df_prov_lista, ignore_index=True) if df_prov_lista else pd.DataFrame()

    return df_acoes_final, df_rf_final, df_prov_final


def salvar_tipo_parquet(df_tipo: pd.DataFrame, path: str, chaves_substituicao=None, dedup_subset=None):
    pasta = os.path.dirname(path)
    if not os.path.exists(pasta):
        os.makedirs(pasta)
    if df_tipo.empty:
        print(f"Nada para salvar em {path}")
        return df_tipo
    existente = pd.DataFrame()
    if os.path.exists(path):
        try:
            existente = pd.read_parquet(path)
        except Exception:
            existente = pd.DataFrame()
    if chaves_substituicao and not existente.empty:
        chaves_substituicao = [c for c in chaves_substituicao if c in existente.columns and c in df_tipo.columns]
        if chaves_substituicao:
            tuplas_novas = set(df_tipo[chaves_substituicao].itertuples(index=False, name=None))
            existente = existente[~existente[chaves_substituicao].apply(tuple, axis=1).isin(tuplas_novas)]
    combinado = pd.concat([existente, df_tipo], ignore_index=True)
    combinado = coerci_numericos(combinado)
    if dedup_subset:
        dedup_subset = [c for c in dedup_subset if c in combinado.columns]
        if dedup_subset:
            combinado = combinado.drop_duplicates(subset=dedup_subset, keep="last")
    print(f"Salvando {len(combinado)} linhas em {path}")
    combinado.to_parquet(path)
    return combinado


def salvar_arquivo_upload(file, usuario: str, mes_ano: str):
    if not os.path.exists(UPLOADS_DIR):
        os.makedirs(UPLOADS_DIR)
    safe_periodo = mes_ano.replace("/", "-")
    safe_usuario = usuario.replace(" ", "_")
    caminho = os.path.join(UPLOADS_DIR, f"{safe_usuario}_{safe_periodo}.xlsx")
    with open(caminho, "wb") as f:
        f.write(file.getbuffer())
    return caminho


def salvar_arquivo_upload_path(path: str, usuario: str, mes_ano: str):
    if not os.path.exists(UPLOADS_DIR):
        os.makedirs(UPLOADS_DIR)
    safe_periodo = mes_ano.replace("/", "-")
    safe_usuario = usuario.replace(" ", "_")
    base = os.path.basename(path)
    caminho = os.path.join(UPLOADS_DIR, f"{safe_usuario}_{safe_periodo}_{base}")
    try:
        with open(path, "rb") as src, open(caminho, "wb") as dst:
            dst.write(src.read())
    except Exception:
        # Em caso de erro de cópia, ainda retorna o destino esperado
        return caminho
    return caminho


def listar_uploads():
    if not os.path.exists(UPLOADS_DIR):
        return []
    arquivos = []
    for nome in os.listdir(UPLOADS_DIR):
        caminho = os.path.join(UPLOADS_DIR, nome)
        registro = {"arquivo": nome, "data_upload": os.path.getmtime(caminho)}
        arquivos.append(registro)
    return arquivos


def carregar_historico_parquet():
    if os.path.exists(PARQUET_PATH):
        return pd.read_parquet(PARQUET_PATH)
    return pd.DataFrame()
