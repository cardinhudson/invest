"""
Parser de Dividendos PDF Avenue V3 - MELHORADO
Extrai todos os dividendos do relatório com tickers e valores corretos
"""

import re
import pdfplumber
import pandas as pd
from typing import Dict, List, Tuple
from pathlib import Path


class ParseadorDividendosPDFV3:
    """Parser melhorado para dividendos do Avenue"""

    # Mapa de descrição → ticker para dividendos
    DESCRICAO_TICKER_MAP_DIVIDENDOS = {
        # Global X / Nasdaq-100 Covered Call
        "GLOBAL X FDS": "QQQS",  # First one
        "GLOBAL X FUNDS": "SRET",
        "GLOBAL X SUPERDIVIDEND": "SRET",
        "GLOBAL X NASDAQ": "QQQS",

        # iShares Core S&P 500
        "ISHARES CORE": "IVV",
        "ISHARES": "IVV",

        # Vanguard
        "VANGUARD GROWTH ETF": "VUG",
        "VANGUARD DIVIDEND APPRECIATION": "VIG",
        "VANGUARD DIVIDEND": "VIG",
        "VANGUARD INDEX": "VUG",
        "VANGUARD SPECIALIZED": "VIG",

        # Invesco S&P 500
        "S&P 500 HIGH DIVID": "SPHD",
        "S&P 500 QUALITY": "SPHQ",
        "INVESCO S&P 500 QUALITY": "SPHQ",

        # Invesco High Yield
        "HIGH YIELD EQUITY DIVID": "PEY",
        "INVESCO HIGH YIELD": "PEY",

        # KBW
        "KBW HIGH DIVID": "KBWD",
        "INVESCO KBW": "KBWD",
    }

    # Tickers conhecidos para fallback
    TICKERS_CONHECIDOS = {"QQQS", "SRET", "IVV", "VUG", "VIG", "SPHD", "SPHQ", "PEY", "KBWD"}

    def __init__(self, usuario_nome: str = "Hudson Cardin"):
        self.usuario_nome = usuario_nome
        self.dividendos_extratos = []

    def _limpar_valor(self, valor_str: str) -> float:
        """Converte string de valor para float, tratando diferentes formatos"""
        if not valor_str:
            return 0.0

        # Remove espaços
        valor_str = valor_str.strip()

        # Se não há separador decimal, tenta parse direto
        if "," not in valor_str and "." not in valor_str:
            try:
                return float(valor_str)
            except ValueError:
                return 0.0

        # Trata formato: 1,234.56 (US) ou 1.234,56 (BR)
        # Estratégia: se houver múltiplas vírgulas/pontos, o último é decimal
        comma_count = valor_str.count(",")
        dot_count = valor_str.count(".")

        if comma_count == 0 and dot_count == 1:
            # Formato US: 1234.56
            try:
                return float(valor_str)
            except ValueError:
                return 0.0

        if dot_count == 0 and comma_count == 1:
            # Formato BR: 1234,56
            try:
                return float(valor_str.replace(",", "."))
            except ValueError:
                return 0.0

        # Casos complexos: 1,234.56 (US) ou 1.234,56 (BR)
        if comma_count > 0 and dot_count > 0:
            last_comma_pos = valor_str.rfind(",")
            last_dot_pos = valor_str.rfind(".")

            if last_dot_pos > last_comma_pos:
                # Formato US: remove vírgulas
                valor_str = valor_str.replace(",", "")
            else:
                # Formato BR: troca vírgula por ponto, remove outros pontos
                valor_str = valor_str.replace(".", "").replace(",", ".")

        try:
            return float(valor_str)
        except ValueError:
            return 0.0

    def _extrair_ticker_da_descricao(self, descricao: str) -> str:
        """Extrai ticker da descrição usando mapa"""
        descricao_upper = descricao.upper()

        # Busca por matches no mapa
        for pattern, ticker in self.DESCRICAO_TICKER_MAP_DIVIDENDOS.items():
            if pattern in descricao_upper:
                return ticker

        return ""

    def _processar_secao_dividendos(self, linhas: List[str], data_inicio: str = None) -> List[Dict]:
        """Processa linhas de dividendos"""
        dividendos = []
        i = 0

        while i < len(linhas):
            linha = linhas[i]

            # Procura por linhas que começam com DIVIDEND
            if linha.strip().startswith("DIVIDEND "):
                # Parse da linha DIVIDEND
                match = re.match(
                    r"DIVIDEND\s+(\d{1,2}/\d{1,2}/\d{2})\s+([CO])\s+(.+)",
                    linha.strip(),
                )
                if not match:
                    i += 1
                    continue

                data_comex, co_tipo, resto_linha = match.groups()

                # Formata data para YYYY-MM-DD
                partes = data_comex.split("/")
                if len(partes) == 3:
                    mes, dia, ano = partes
                    ano = f"20{ano}"
                    data_comex = f"{dia}/{mes}/{ano}"

                # Procura número na resto_linha
                numeros = re.findall(r"[\d.,]+", resto_linha)
                valor_bruto_str = numeros[-1] if numeros else "0"
                valor_bruto = self._limpar_valor(valor_bruto_str)

                # Descrição da linha DIVIDEND (toda a linha)
                descricao_parts = [resto_linha]

                # Processa próximas linhas para imposto (WH) e descrição adicional
                valor_imposto = 0.0
                i += 1

                while i < len(linhas):
                    linha_seguinte = linhas[i].strip()

                    # Se encontrar NON-QUALIFIED, acabou este dividendo
                    if "NON-QUALIFIED" in linha_seguinte or linha_seguinte.startswith(
                        "DIVIDEND "
                    ):
                        break

                    # Procura por WH (withholding/imposto)
                    if "WH" in linha_seguinte:
                        # Extrai número após WH
                        match_wh = re.search(
                            r"WH\s+([\d.,]+)", linha_seguinte
                        )
                        if match_wh:
                            valor_imposto = self._limpar_valor(match_wh.group(1))
                        # Também coleta descrição antes de WH
                        desc_antes_wh = linha_seguinte.split("WH")[0].strip()
                        if desc_antes_wh:
                            descricao_parts.append(desc_antes_wh)
                    else:
                        # Linhas de descrição
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
                    # Tenta extrair ticker do final da descrição
                    palavras = descricao_completa.split()
                    for palavra in reversed(palavras):
                        if palavra.upper() in self.TICKERS_CONHECIDOS:
                            ticker = palavra.upper()
                            break

                # Valida dividendo
                if valor_bruto > 0 and ticker:
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
                i += 1

        return dividendos

    def extrair_do_pdf(self, caminho_pdf: str) -> pd.DataFrame:
        """Extrai dividendos do PDF"""
        try:
            with pdfplumber.open(caminho_pdf) as pdf:
                # Coleta texto de todas as páginas
                todas_linhas = []
                for page_num, page in enumerate(pdf.pages):
                    texto = page.extract_text()
                    if texto:
                        linhas = texto.split("\n")
                        todas_linhas.extend(linhas)

                # Processa dividendos
                dividendos = self._processar_secao_dividendos(todas_linhas)

                if dividendos:
                    df = pd.DataFrame(dividendos)
                    return df
                else:
                    return pd.DataFrame()

        except Exception as e:
            print(f"Erro ao extrair dividendos: {e}")
            return pd.DataFrame()


def extrair_dividendos_pdf_v3(caminho_pdf: str, usuario_nome: str = "Hudson Cardin") -> pd.DataFrame:
    """Função wrapper para extrair dividendos"""
    parser = ParseadorDividendosPDFV3(usuario_nome=usuario_nome)
    return parser.extrair_do_pdf(caminho_pdf)


# Teste
if __name__ == "__main__":
    from pathlib import Path

    print("Testando parser de dividendos v3 MELHORADO...\n")

    # PDF de teste
    pdf_path = "Relatorios/Avenue/Hudson Cardin/Doc_101579_STATEMENT_6AV40121_2024_12_31_142026_73157_AM_eRVKImAs.pdf"

    if Path(pdf_path).exists():
        df = extrair_dividendos_pdf_v3(pdf_path)

        print(f"Dividendos extraídos: {len(df)}")
        print(f"\nTodos os dividendos:\n{df}")

        print("\n" + "=" * 80)
        print("Resumo:")
        print(f"  Total Bruto: ${df['Valor Bruto'].sum():.2f}")
        print(f"  Total Imposto: ${df['Imposto'].sum():.2f}")
        print(f"  Total Líquido: ${df['Valor Líquido'].sum():.2f}")
        print(f"  Tickers: {sorted(df['Ticker'].unique().tolist())}")
    else:
        print(f"PDF não encontrado: {pdf_path}")
