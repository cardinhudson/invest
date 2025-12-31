import pandas as pd
import os

PARQUET_PATH = "data/historico_investimentos.parquet"
ACOES_PATH = "data/acoes.parquet"
RENDA_FIXA_PATH = "data/renda_fixa.parquet"
PROVENTOS_PATH = "data/proventos.parquet"

def garantir_pasta_data():
    """Cria a pasta data/ se não existir."""
    if not os.path.exists("data"):
        os.makedirs("data")
        print("Pasta 'data/' criada com sucesso.")

def limpar_colunas_duplicadas(df):
    """Remove duplicatas de nomes de colunas renomeando-as."""
    cols = pd.Series(df.columns)
    for dup in cols[cols.duplicated()].unique():
        idxs = cols[cols == dup].index.tolist()
        for i, idx in enumerate(idxs):
            if i == 0:
                continue
            cols[idx] = f"{dup}.{i}"
    df.columns = cols
    return df

def remover_linhas_irrelevantes(df, colunas_verificar):
    """Remove linhas que contêm 'total', 'subtotal' nas colunas especificadas."""
    df = df.copy()
    for col in colunas_verificar:
        if col in df.columns:
            df = df[~df[col].astype(str).str.lower().str.contains("total|subtotal", na=False)]
    return df

def processar_renda_fixa(xls, usuario, mes_ano):
    """Processa a planilha de Renda Fixa com as regras especificadas."""
    df_rf = pd.DataFrame()
    
    for nome in xls.sheet_names:
        if "Renda Fixa" in nome or "renda fixa" in nome.lower():
            print(f"\n=== Processando Renda Fixa: {nome} ===")
            df_rf = pd.read_excel(xls, sheet_name=nome, skiprows=0)
            df_rf = limpar_colunas_duplicadas(df_rf)
            print(f"Linhas lidas: {len(df_rf)}")
            print(f"Colunas: {list(df_rf.columns)[:5]}...")  # Primeiras 5 colunas
            
            # Colunas essenciais
            colunas_essenciais = [
                "Produto", "Instituição", "Emissor", "Código", "Indexador", "Tipo de regime",
                "Data de Emissão", "Vencimento", "Quantidade", "Quantidade Disponível",
                "Quantidade Indisponível", "Motivo", "Contraparte", "Preço Atualizado MTM",
                "Valor Atualizado MTM", "Preço Atualizado CURVA", "Valor Atualizado CURVA"
            ]
            
            # Mapear colunas
            for col in colunas_essenciais:
                if col not in df_rf.columns:
                    for c in df_rf.columns:
                        if col.lower() in str(c).lower():
                            df_rf[col] = df_rf[c]
                            break
            
            # Converter colunas numéricas para float
            colunas_numericas = [
                "Preço Atualizado MTM", "Valor Atualizado MTM",
                "Preço Atualizado CURVA", "Valor Atualizado CURVA",
                "Quantidade", "Quantidade Disponível", "Quantidade Indisponível"
            ]
            for col in colunas_numericas:
                if col in df_rf.columns:
                    df_rf[col] = pd.to_numeric(df_rf[col], errors="coerce")

            # Criar coluna Valor
            df_rf["Valor"] = None
            if "Valor Atualizado MTM" in df_rf.columns:
                df_rf["Valor"] = df_rf["Valor Atualizado MTM"]
            if "Valor Atualizado CURVA" in df_rf.columns:
                mask_vazio = df_rf["Valor"].isna()
                df_rf.loc[mask_vazio, "Valor"] = df_rf.loc[mask_vazio, "Valor Atualizado CURVA"]

            # Filtros
            if "Produto" in df_rf.columns:
                df_rf = df_rf[~df_rf["Produto"].astype(str).str.lower().str.contains("total|subtotal", na=False)]
                df_rf = df_rf[df_rf["Produto"].notna() & (df_rf["Produto"].astype(str).str.strip() != "")]

            if "Valor" in df_rf.columns:
                df_rf = df_rf[df_rf["Valor"].notna() & (df_rf["Valor"] > 0)]

            # Metadados
            df_rf["Mês/Ano"] = mes_ano
            df_rf["Usuário"] = usuario

            # Colunas finais
            colunas_finais = [col for col in colunas_essenciais + ["Valor", "Mês/Ano", "Usuário"] if col in df_rf.columns]
            df_rf = df_rf[colunas_finais]

            print(f"✅ {len(df_rf)} linhas processadas")
            break
    
    return df_rf

def processar_acoes(xls, usuario, mes_ano):
    """Processa a planilha de Ações com as regras especificadas."""
    df_acoes = pd.DataFrame()
    
    for nome in xls.sheet_names:
        if "Ações" in nome or "Acoes" in nome or "ações" in nome.lower() or "acoes" in nome.lower():
            print(f"\n=== Processando Ações: {nome} ===")
            df_acoes = pd.read_excel(xls, sheet_name=nome, skiprows=0)
            df_acoes = limpar_colunas_duplicadas(df_acoes)
            print(f"Linhas lidas: {len(df_acoes)}")
            print(f"Colunas: {list(df_acoes.columns)[:5]}...")  # Primeiras 5 colunas
            
            # Colunas essenciais
            colunas_essenciais = [
                "Produto", "Instituição", "Conta", "Código de Negociação", "CNPJ da Empresa",
                "Código ISIN / Distribuição", "Tipo", "Escriturador", "Quantidade",
                "Quantidade Disponível", "Quantidade Indisponível", "Motivo",
                "Preço de Fechamento", "Valor Atualizado"
            ]
            
            # Mapear colunas
            for col in colunas_essenciais:
                if col not in df_acoes.columns:
                    for c in df_acoes.columns:
                        if col.lower() in str(c).lower():
                            df_acoes[col] = df_acoes[c]
                            break
            
            # Criar coluna Valor
            if "Valor Atualizado" in df_acoes.columns:
                df_acoes["Valor"] = pd.to_numeric(df_acoes["Valor Atualizado"], errors="coerce")
                df_acoes = df_acoes.drop(columns=["Valor Atualizado"])
            else:
                df_acoes["Valor"] = None
            
            # Filtros
            if "Produto" in df_acoes.columns:
                df_acoes = df_acoes[~df_acoes["Produto"].astype(str).str.lower().str.contains("total|subtotal", na=False)]
                df_acoes = df_acoes[df_acoes["Produto"].notna() & (df_acoes["Produto"].astype(str).str.strip() != "")]
            
            if "Valor" in df_acoes.columns:
                df_acoes = df_acoes[df_acoes["Valor"].notna() & (df_acoes["Valor"] > 0)]
            
            # Metadados
            df_acoes["Mês/Ano"] = mes_ano
            df_acoes["Usuário"] = usuario
            
            # Colunas finais
            colunas_finais = [col for col in colunas_essenciais + ["Valor", "Mês/Ano", "Usuário"] if col in df_acoes.columns]
            colunas_finais = [col for col in colunas_finais if col != "Valor Atualizado"]
            df_acoes = df_acoes[colunas_finais]
            
            print(f"✅ {len(df_acoes)} linhas processadas")
            break
    
    return df_acoes

def processar_proventos(xls, usuario, mes_ano):
    """Processa a planilha de Proventos com as regras especificadas."""
    df_prov = pd.DataFrame()
    
    for nome in xls.sheet_names:
        if "Proventos" in nome:
            print(f"\n=== Processando Proventos: {nome} ===")
            
            # Detectar linha de header
            df_tmp = pd.read_excel(xls, sheet_name=nome, header=None)
            header_row = 0
            for i in range(min(10, len(df_tmp))):
                row = df_tmp.iloc[i].astype(str).str.lower().tolist()
                if any(term in " ".join(row) for term in ["valor liquido", "valor do provento"]):
                    header_row = i
                    break
            
            df_prov = pd.read_excel(xls, sheet_name=nome, header=header_row)
            df_prov = limpar_colunas_duplicadas(df_prov)
            print(f"Linhas lidas: {len(df_prov)}")
            
            # Colunas essenciais
            colunas_essenciais = ["Produto", "Data de Pagamento", "Tipo de Provento", "Valor Líquido"]
            
            # Mapear colunas
            for col in colunas_essenciais:
                if col not in df_prov.columns:
                    for c in df_prov.columns:
                        if col.lower() in str(c).lower():
                            df_prov[col] = df_prov[c]
                            break
            
            # Converter Valor Líquido
            if "Valor Líquido" in df_prov.columns:
                df_prov["Valor Líquido"] = pd.to_numeric(df_prov["Valor Líquido"], errors="coerce")
            
            # Filtros
            df_prov = remover_linhas_irrelevantes(df_prov, colunas_essenciais)
            
            # Remover última linha se for total
            if len(df_prov) > 0:
                ultima = df_prov.iloc[-1]
                if (any(str(ultima[col]).lower().strip() in ["total", "subtotal"] for col in colunas_essenciais if col in df_prov.columns)
                    or pd.isna(ultima.get("Produto")) or str(ultima.get("Produto", "")).strip() == ""):
                    df_prov = df_prov.iloc[:-1]
            
            # Filtrar por Produto e Valor válidos
            if "Produto" in df_prov.columns:
                if "Valor Líquido" in df_prov.columns:
                    df_prov = df_prov[(df_prov["Produto"].notna()) & (df_prov["Valor Líquido"].notna()) & (df_prov["Valor Líquido"] > 0)]
                else:
                    df_prov = df_prov[df_prov["Produto"].notna()]
            
            # Metadados
            df_prov["Mês/Ano"] = mes_ano
            df_prov["Usuário"] = usuario
            
            # Colunas finais
            colunas_finais = [col for col in colunas_essenciais + ["Mês/Ano", "Usuário"] if col in df_prov.columns]
            df_prov = df_prov[colunas_finais]
            
            print(f"✅ {len(df_prov)} linhas processadas")
            break
    
    return df_prov

def ler_relatorio_excel(file, usuario, mes_ano):
    """Lê e processa o arquivo Excel completo."""
    xls = pd.ExcelFile(file)
    
    print(f"\n{'='*80}")
    print(f"INICIANDO PROCESSAMENTO")
    print(f"Usuário: {usuario} | Período: {mes_ano}")
    print(f"Abas disponíveis: {xls.sheet_names}")
    print(f"{'='*80}")
    
    df_acoes = processar_acoes(xls, usuario, mes_ano)
    df_rf = processar_renda_fixa(xls, usuario, mes_ano)
    df_prov = processar_proventos(xls, usuario, mes_ano)
    
    print(f"\n{'='*80}")
    print(f"RESULTADO FINAL")
    print(f"Ações: {len(df_acoes)} linhas | Renda Fixa: {len(df_rf)} linhas | Proventos: {len(df_prov)} linhas")
    print(f"{'='*80}\n")
    
    return df_acoes, df_rf, df_prov

def salvar_tipo_parquet(df_tipo, path):
    """Salva DataFrame em formato Parquet com lógica cumulativa."""
    garantir_pasta_data()
    
    if df_tipo.empty or len(df_tipo) == 0:
        print(f"⚠ Nenhuma linha para salvar em {path}")
        return df_tipo
    
    # Carregar dados existentes
    if os.path.exists(path):
        df_existente = pd.read_parquet(path)
        
        # Remover dados do mesmo usuário/mês (overwrite)
        if "Usuário" in df_tipo.columns and "Mês/Ano" in df_tipo.columns:
            usuario = df_tipo["Usuário"].iloc[0]
            mes_ano = df_tipo["Mês/Ano"].iloc[0]
            df_existente = df_existente[
                ~((df_existente["Usuário"] == usuario) & (df_existente["Mês/Ano"] == mes_ano))
            ]
        
        df_final = pd.concat([df_existente, df_tipo], ignore_index=True)
    else:
        df_final = df_tipo
    
    # Salvar
    df_final.to_parquet(path, index=False)
    print(f"✅ Salvo: {path} ({len(df_final)} linhas totais, {len(df_tipo)} novas)")
    
    return df_final

def carregar_historico_parquet():
    if os.path.exists(PARQUET_PATH):
        return pd.read_parquet(PARQUET_PATH)
    else:
        return pd.DataFrame()
