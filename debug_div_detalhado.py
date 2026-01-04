"""
Debug detalhado: entender quais dividendos estão sendo rejeitados
"""

import re
import pdfplumber
import pandas as pd
from typing import Dict, List, Tuple
from pathlib import Path

# Copiar o parser e adicionar debug
class ParseadorDividendosPDFV3Debug:
    """Parser melhorado para dividendos do Avenue - COM DEBUG"""

    DESCRICAO_TICKER_MAP_DIVIDENDOS = {
        "GLOBAL X FDS": "QQQS",
        "GLOBAL X FUNDS": "SRET",
        "GLOBAL X SUPERDIVIDEND": "SRET",
        "GLOBAL X NASDAQ": "QQQS",
        "ISHARES CORE": "IVV",
        "ISHARES": "IVV",
        "VANGUARD GROWTH ETF": "VUG",
        "VANGUARD DIVIDEND APPRECIATION": "VIG",
        "VANGUARD DIVIDEND": "VIG",
        "VANGUARD INDEX": "VUG",
        "VANGUARD SPECIALIZED": "VIG",
        "S&P 500 HIGH DIVID": "SPHD",
        "S&P 500 QUALITY": "SPHQ",
        "INVESCO S&P 500 QUALITY": "SPHQ",
        "HIGH YIELD EQUITY DIVID": "PEY",
        "INVESCO HIGH YIELD": "PEY",
        "KBW HIGH DIVID": "KBWD",
        "INVESCO KBW": "KBWD",
    }

    TICKERS_CONHECIDOS = {"QQQS", "SRET", "IVV", "VUG", "VIG", "SPHD", "SPHQ", "PEY", "KBWD"}

    def __init__(self, usuario_nome: str = "Hudson Cardin"):
        self.usuario_nome = usuario_nome

    def _limpar_valor(self, valor_str: str) -> float:
        if not valor_str:
            return 0.0
        valor_str = valor_str.strip()
        if "," not in valor_str and "." not in valor_str:
            try:
                return float(valor_str)
            except ValueError:
                return 0.0
        comma_count = valor_str.count(",")
        dot_count = valor_str.count(".")
        if comma_count == 0 and dot_count == 1:
            try:
                return float(valor_str)
            except ValueError:
                return 0.0
        if dot_count == 0 and comma_count == 1:
            try:
                return float(valor_str.replace(",", "."))
            except ValueError:
                return 0.0
        if comma_count > 0 and dot_count > 0:
            last_comma_pos = valor_str.rfind(",")
            last_dot_pos = valor_str.rfind(".")
            if last_dot_pos > last_comma_pos:
                valor_str = valor_str.replace(",", "")
            else:
                valor_str = valor_str.replace(".", "").replace(",", ".")
        try:
            return float(valor_str)
        except ValueError:
            return 0.0

    def _extrair_ticker_da_descricao(self, descricao: str) -> str:
        descricao_upper = descricao.upper()
        for pattern, ticker in self.DESCRICAO_TICKER_MAP_DIVIDENDOS.items():
            if pattern in descricao_upper:
                return ticker
        return ""

    def _processar_secao_dividendos(self, linhas: List[str], data_inicio: str = None) -> List[Dict]:
        dividendos = []
        i = 0
        div_num = 0

        while i < len(linhas):
            linha = linhas[i]

            if linha.strip().startswith("DIVIDEND "):
                div_num += 1
                print(f"\n--- DIVIDENDO #{div_num} ---")
                print(f"Linha: {linha}")
                
                match = re.match(
                    r"DIVIDEND\s+(\d{1,2}/\d{1,2}/\d{2})\s+([CO])\s+(.+)",
                    linha.strip(),
                )
                if not match:
                    print(f"  ❌ Regex não bateu")
                    i += 1
                    continue

                data_comex, co_tipo, resto_linha = match.groups()

                # Formata data
                partes = data_comex.split("/")
                if len(partes) == 3:
                    mes, dia, ano = partes
                    ano = f"20{ano}"
                    data_comex = f"{dia}/{mes}/{ano}"

                # Procura número na resto_linha
                numeros = re.findall(r"[\d.,]+", resto_linha)
                valor_bruto_str = numeros[-1] if numeros else "0"
                valor_bruto = self._limpar_valor(valor_bruto_str)
                print(f"  Números: {numeros}, Valor: {valor_bruto}")

                # Descrição
                descricao_parts = [resto_linha]

                # Processa próximas linhas
                valor_imposto = 0.0
                i += 1

                while i < len(linhas):
                    linha_seguinte = linhas[i].strip()

                    if "NON-QUALIFIED" in linha_seguinte or linha_seguinte.startswith("DIVIDEND "):
                        break

                    if "WH" in linha_seguinte:
                        match_wh = re.search(r"WH\s+([\d.,]+)", linha_seguinte)
                        if match_wh:
                            valor_imposto = self._limpar_valor(match_wh.group(1))
                        desc_antes_wh = linha_seguinte.split("WH")[0].strip()
                        if desc_antes_wh:
                            descricao_parts.append(desc_antes_wh)
                    else:
                        if (
                            linha_seguinte
                            and not linha_seguinte.startswith("DIVIDEND ")
                            and "NON-QUALIFIED" not in linha_seguinte
                        ):
                            descricao_parts.append(linha_seguinte)

                    i += 1

                # Junta descrição
                descricao_completa = " ".join([p for p in descricao_parts if p]).strip()

                # Extrai ticker
                ticker = self._extrair_ticker_da_descricao(descricao_completa)
                if not ticker:
                    palavras = descricao_completa.split()
                    for palavra in reversed(palavras):
                        if palavra.upper() in self.TICKERS_CONHECIDOS:
                            ticker = palavra.upper()
                            break

                print(f"  Descrição: {descricao_completa[:60]}")
                print(f"  Ticker: {ticker}")
                print(f"  Imposto: {valor_imposto}")
                print(f"  Valor Bruto: {valor_bruto}")

                # Valida
                if valor_bruto > 0 and ticker:
                    print(f"  ✅ ACEITO")
                    valor_liquido = valor_bruto - valor_imposto
                    mês_ano = f"{data_comex.split('/')[1]}/{data_comex.split('/')[2]}"

                    dividendo = {
                        "Data Comex": data_comex,
                        "Produto": descricao_completa[:50],
                        "Ticker": ticker,
                        "Valor Bruto": round(valor_bruto, 2),
                        "Imposto": round(valor_imposto, 2),
                        "Valor Líquido": round(valor_liquido, 2),
                        "Mês/Ano": mês_ano,
                        "Usuário": self.usuario_nome,
                    }
                    dividendos.append(dividendo)
                else:
                    print(f"  ❌ REJEITADO: valor_bruto={valor_bruto}, ticker={ticker}")
            else:
                i += 1

        return dividendos

    def extrair_do_pdf(self, caminho_pdf: str) -> pd.DataFrame:
        try:
            with pdfplumber.open(caminho_pdf) as pdf:
                todas_linhas = []
                for page_num, page in enumerate(pdf.pages):
                    texto = page.extract_text()
                    if texto:
                        linhas = texto.split("\n")
                        todas_linhas.extend(linhas)

                dividendos = self._processar_secao_dividendos(todas_linhas)

                if dividendos:
                    df = pd.DataFrame(dividendos)
                    return df
                else:
                    return pd.DataFrame()

        except Exception as e:
            print(f"Erro ao extrair dividendos: {e}")
            return pd.DataFrame()


# Teste
pdf_path = "Relatorios/Avenue/Hudson Cardin/Doc_101579_STATEMENT_6AV40121_2024_12_31_142026_73157_AM_eRVKImAs.pdf"

if Path(pdf_path).exists():
    parser = ParseadorDividendosPDFV3Debug()
    df = parser.extrair_do_pdf(pdf_path)

    print(f"\n\n{'='*80}")
    print(f"TOTAL EXTRAÍDO: {len(df)} dividendos")
    if len(df) > 0:
        print(df[['Data Comex', 'Ticker', 'Valor Bruto', 'Imposto']])
