import os
import re
import pandas as pd


def _parse_num_misto(valor):
    """Parse numérico tolerante a formatos pt-BR/US (milhar e decimal)."""
    if pd.isna(valor):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    txt = str(valor).strip()
    if not txt:
        return None
    txt = txt.replace("R$", "").replace("US$", "").replace("$", "")
    txt = txt.replace("%", "").replace("\u00a0", " ").replace(" ", "")
    negativo = False
    if txt.startswith("(") and txt.endswith(")"):
        negativo = True
        txt = txt[1:-1]
    if txt.startswith("+"):
        txt = txt[1:]
    elif txt.startswith("-"):
        negativo = True
        txt = txt[1:]

    if not txt:
        return None

    if "." in txt and "," in txt:
        txt_norm = txt.replace(".", "").replace(",", ".")
    elif "," in txt:
        txt_norm = txt.replace(".", "").replace(",", ".")
    elif "." in txt:
        partes = txt.split(".")
        if len(partes) > 2:
            txt_norm = "".join(partes)
        else:
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
        return None

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
            df[col] = df[col].apply(_parse_num_misto)
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
    df["Valor"] = df["Valor"].apply(_parse_num_misto)
    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce")
    return df


def criar_coluna_valor_acoes(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Valor"] = df.get("Valor Atualizado").apply(_parse_num_misto)
    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce")
    return df


def filtrar_linhas_ativas(df: pd.DataFrame, coluna_valor: str) -> pd.DataFrame:
    df = df.copy()
    if coluna_valor not in df.columns:
        return df.iloc[0:0]
    df[coluna_valor] = df[coluna_valor].apply(_parse_num_misto)
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
        df["Valor Líquido"] = df["Valor Líquido"].apply(_parse_num_misto)
        df["Valor Líquido"] = pd.to_numeric(df["Valor Líquido"], errors="coerce")
        df = df[df["Valor Líquido"].notnull() & (df["Valor Líquido"] > 0)]

    for col in ["Quantidade", "Preço unitário", "Preco unitario"]:
        if col in df.columns:
            df[col] = df[col].apply(_parse_num_misto)
            df[col] = pd.to_numeric(df[col], errors="coerce")
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

        # Para proventos, reler como texto para não perder milhares (ex.: '1.500' -> 1500)
        if tipo == "prov":
            df_sheet = pd.read_excel(xls, sheet_name=nome, header=header_row, dtype=str)
            df_sheet = limpar_colunas_duplicadas(df_sheet)

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
            # Proventos Recebidos: preservar também Quantidade/Preço unitário para cálculo por-ação
            colunas_essenciais_prov = [
                "Produto",
                "Data de Pagamento",
                "Tipo de Provento",
                "Valor Líquido",
                "Instituição",
                "Quantidade",
                "Preço unitário",
            ]

            # Sinônimos comuns nas planilhas
            if "Data de Pagamento" not in df_prov.columns and "Pagamento" in df_prov.columns:
                df_prov["Data de Pagamento"] = df_prov["Pagamento"]
            if "Tipo de Provento" not in df_prov.columns and "Tipo de Evento" in df_prov.columns:
                df_prov["Tipo de Provento"] = df_prov["Tipo de Evento"]
            if "Valor Líquido" not in df_prov.columns:
                for c in df_prov.columns:
                    if str(c).strip().lower() == "valor líquido" or str(c).strip().lower() == "valor liquido" or str(c).strip().lower() == "valor líquido".lower():
                        df_prov["Valor Líquido"] = df_prov[c]
                if "Valor Líquido" not in df_prov.columns and "Valor líquido" in df_prov.columns:
                    df_prov["Valor Líquido"] = df_prov["Valor líquido"]
            if "Preço unitário" not in df_prov.columns:
                for c in df_prov.columns:
                    if str(c).strip().lower() in ["preço unitário", "preco unitario", "preco unitário", "preço unitario"]:
                        df_prov["Preço unitário"] = df_prov[c]
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

    # Atualizar cache de Setor/Segmento (yfinance) apenas para Ações
    try:
        if os.path.normpath(path) == os.path.normpath(ACOES_PATH):
            from modules.ticker_info import atualizar_cache_por_df
            atualizar_cache_por_df(combinado)
    except Exception:
        pass
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


def padronizar_renda_fixa(df_rf: pd.DataFrame) -> pd.DataFrame:
    """
    Padroniza DataFrame de Renda Fixa para colunas:
    Produto, Código, Quantidade, Quantidade Disponível, Preço, Valor
    """
    df = df_rf.copy()
    
    # Seleciona coluna de preço (prefere MTM, depois CURVA)
    preco_col = None
    if "Preço Atualizado MTM" in df.columns and df["Preço Atualizado MTM"].notna().any():
        preco_col = "Preço Atualizado MTM"
    elif "Preço Atualizado CURVA" in df.columns:
        preco_col = "Preço Atualizado CURVA"
    
    # Monta resultado com colunas padronizadas
    resultado = pd.DataFrame()
    resultado["Produto"] = df.get("Produto")
    resultado["Código"] = df.get("Código")
    # RF normalmente vem apenas com "Quantidade Disponível"; manter ambas por compatibilidade
    resultado["Quantidade"] = df.get("Quantidade")
    if resultado["Quantidade"].isna().all():
        resultado["Quantidade"] = df.get("Quantidade Disponível")
    resultado["Quantidade Disponível"] = df.get("Quantidade Disponível")
    resultado["Preço"] = df.get(preco_col) if preco_col else None
    resultado["Valor"] = df.get("Valor")
    resultado["Usuário"] = df.get("Usuário")
    resultado["Mês/Ano"] = df.get("Mês/Ano")
    
    # Converte para numérico (tolerante a separadores)
    for col in ["Quantidade", "Quantidade Disponível", "Preço", "Valor"]:
        resultado[col] = resultado[col].apply(_parse_num_misto)
        resultado[col] = pd.to_numeric(resultado[col], errors="coerce")
    
    return resultado


def padronizar_acoes(df_acoes: pd.DataFrame) -> pd.DataFrame:
    """
    Padroniza DataFrame de Ações para colunas:
    Produto, Código, Quantidade, Quantidade Disponível, Preço, Valor
    """
    df = df_acoes.copy()
    
    # Monta resultado com colunas padronizadas
    resultado = pd.DataFrame()
    resultado["Produto"] = df.get("Produto")
    resultado["Código"] = df.get("Código de Negociação")
    # Para patrimônio, a fonte correta é "Quantidade" (não a disponível)
    resultado["Quantidade"] = df.get("Quantidade")
    if resultado["Quantidade"].isna().all():
        resultado["Quantidade"] = df.get("Quantidade Disponível")
    resultado["Quantidade Disponível"] = df.get("Quantidade Disponível")
    resultado["Preço"] = df.get("Preço de Fechamento")
    resultado["Valor"] = df.get("Valor")
    resultado["Usuário"] = df.get("Usuário")
    resultado["Mês/Ano"] = df.get("Mês/Ano")
    
    # Converte para numérico (tolerante a separadores)
    for col in ["Quantidade", "Quantidade Disponível", "Preço", "Valor"]:
        resultado[col] = resultado[col].apply(_parse_num_misto)
        resultado[col] = pd.to_numeric(resultado[col], errors="coerce")
    
    return resultado


def _is_tesouro(produto: str, codigo: str) -> bool:
    texto = " ".join([
        str(produto or ""),
        str(codigo or ""),
    ]).lower()
    return any(pat in texto for pat in ["tesouro", "ltn", "lft", "ntn", "ntnb", "ntnf", "selic", "ipca+"])


def _is_opcao(produto: str, codigo: str) -> bool:
    """Detecta se é uma opção de compra ou venda"""
    texto = " ".join([
        str(produto or ""),
        str(codigo or ""),
    ]).lower()
    return any(pat in texto for pat in ["opção de compra", "opcao de compra", "opção de venda", "opcao de venda", "opção", "opcao"])


def padronizar_tabelas(df_acoes: pd.DataFrame, df_renda_fixa: pd.DataFrame) -> pd.DataFrame:
    """
    Consolida Ações e Renda Fixa em um único DataFrame com colunas padronizadas.
    Retorna um DataFrame com colunas: Ativo, Ticker, Quantidade, Quantidade Disponível, Preço, Valor, Tipo
    """
    df_acoes_pad = padronizar_acoes(df_acoes) if not df_acoes.empty else pd.DataFrame()
    df_rf_pad = padronizar_renda_fixa(df_renda_fixa) if not df_renda_fixa.empty else pd.DataFrame()
    
    # Renomear Produto→Ativo e Código→Ticker para padronização
    if not df_acoes_pad.empty:
        df_acoes_pad = df_acoes_pad.rename(columns={"Produto": "Ativo", "Código": "Ticker"})
    if not df_rf_pad.empty:
        df_rf_pad = df_rf_pad.rename(columns={"Produto": "Ativo", "Código": "Ticker"})
    
    # Adiciona coluna de tipo
    if not df_acoes_pad.empty:
        df_acoes_pad["Tipo"] = "Ações"
        # Classificar opções primeiro
        mask_opcao = df_acoes_pad.apply(lambda r: _is_opcao(r.get("Ativo"), r.get("Ticker")), axis=1)
        df_acoes_pad.loc[mask_opcao, "Tipo"] = "Opções"
        # Depois classificar tesouro direto
        mask_td_acoes = df_acoes_pad.apply(lambda r: _is_tesouro(r.get("Ativo"), r.get("Ticker")), axis=1)
        df_acoes_pad.loc[mask_td_acoes, "Tipo"] = "Tesouro Direto"
    if not df_rf_pad.empty:
        df_rf_pad["Tipo"] = "Renda Fixa"
        mask_td_rf = df_rf_pad.apply(lambda r: _is_tesouro(r.get("Ativo"), r.get("Ticker")), axis=1)
        df_rf_pad.loc[mask_td_rf, "Tipo"] = "Tesouro Direto"
    
    # Consolida
    consolidado = pd.concat([df_acoes_pad, df_rf_pad], ignore_index=True)
    
    # Remove linhas com valores nulos ou inválidos
    consolidado = consolidado.dropna(subset=["Ativo", "Valor"])
    consolidado = consolidado[consolidado["Valor"] > 0]

    cols_out = [
        "Ativo",
        "Ticker",
        "Quantidade",
        "Quantidade Disponível",
        "Preço",
        "Valor",
        "Tipo",
        "Usuário",
        "Mês/Ano",
    ]
    cols_out = [c for c in cols_out if c in consolidado.columns]
    return consolidado[cols_out]

def padronizar_dividendos(df_proventos: pd.DataFrame) -> pd.DataFrame:
    """
    Padroniza DataFrame de Proventos/Dividendos para colunas:
    Data, Ativo, Valor Bruto, Impostos, Valor Líquido, Fonte
    
    Se não houver coluna de Valor Bruto ou Impostos, calcula com base no Valor Líquido.
    """
    if df_proventos.empty:
        return pd.DataFrame(columns=["Data", "Ativo", "Valor Bruto", "Impostos", "Valor Líquido", "Fonte"])
    
    df = df_proventos.copy()
    
    resultado = pd.DataFrame()
    
    # Data de crédito (usa Data de Pagamento ou Mês/Ano)
    resultado["Data"] = df.get("Data de Pagamento")
    if resultado["Data"].isna().all() and "Mês/Ano" in df.columns:
        resultado["Data"] = df.get("Mês/Ano")
    
    # Ativo (extrai ticker do Produto se possível)
    resultado["Ativo"] = df.get("Produto").apply(lambda x: str(x).split(" - ")[0] if pd.notna(x) else "")

    # Quantidade (quando disponível no relatório)
    if "Quantidade" in df.columns:
        resultado["Quantidade"] = df.get("Quantidade").apply(_parse_num_misto)
        resultado["Quantidade"] = pd.to_numeric(resultado["Quantidade"], errors="coerce")
    else:
        resultado["Quantidade"] = pd.NA

    # Preço unitário (quando disponível no relatório)
    if "Preço unitário" in df.columns:
        resultado["Preço unitário"] = df.get("Preço unitário").apply(_parse_num_misto)
        resultado["Preço unitário"] = pd.to_numeric(resultado["Preço unitário"], errors="coerce")
    elif "Preco unitario" in df.columns:
        resultado["Preço unitário"] = df.get("Preco unitario").apply(_parse_num_misto)
        resultado["Preço unitário"] = pd.to_numeric(resultado["Preço unitário"], errors="coerce")
    else:
        resultado["Preço unitário"] = pd.NA
    
    # Valor Bruto (se não existir, assume igual ao Valor Líquido)
    if "Valor Bruto" in df.columns:
        resultado["Valor Bruto"] = df.get("Valor Bruto").apply(_parse_num_misto)
        resultado["Valor Bruto"] = pd.to_numeric(resultado["Valor Bruto"], errors="coerce")
    else:
        resultado["Valor Bruto"] = df.get("Valor Líquido").apply(_parse_num_misto)
        resultado["Valor Bruto"] = pd.to_numeric(resultado["Valor Bruto"], errors="coerce")
    
    # Impostos (se não existir, assume 0)
    if "Impostos" in df.columns:
        resultado["Impostos"] = df.get("Impostos").apply(_parse_num_misto)
        resultado["Impostos"] = pd.to_numeric(resultado["Impostos"], errors="coerce").fillna(0)
    else:
        resultado["Impostos"] = 0.0
    
    # Valor Líquido
    resultado["Valor Líquido"] = df.get("Valor Líquido").apply(_parse_num_misto)
    resultado["Valor Líquido"] = pd.to_numeric(resultado["Valor Líquido"], errors="coerce")
    
    # Usuário
    if "Usuário" in df.columns:
        resultado["Usuário"] = df.get("Usuário")
    else:
        resultado["Usuário"] = None
    
    # Mês/Ano
    if "Mês/Ano" in df.columns:
        resultado["Mês/Ano"] = df.get("Mês/Ano")
    else:
        resultado["Mês/Ano"] = None
    
    # Fonte (mês/ano ou usuário + mês/ano)
    fonte = ""
    if "Mês/Ano" in df.columns:
        fonte = df.get("Mês/Ano").astype(str)
    if "Usuário" in df.columns:
        usuario = df.get("Usuário").astype(str)
        fonte = usuario + " (" + fonte + ")"
    
    resultado["Fonte"] = fonte
    
    # Remove linhas inválidas
    resultado = resultado.dropna(subset=["Ativo", "Valor Líquido"])
    resultado = resultado[resultado["Valor Líquido"] != 0]
    
    return resultado[["Data", "Ativo", "Quantidade", "Preço unitário", "Valor Bruto", "Impostos", "Valor Líquido", "Fonte"]]