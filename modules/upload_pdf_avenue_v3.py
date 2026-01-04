"""
Parser melhorado para PDFs Avenue que suporta:
1. Múltiplos ativos (Janeiro-Outubro 2024) - Giselle Cardin
2. Ativo único (Dezembro 2024+) - Hudson Cardin
3. Descrições em múltiplas linhas

Padrões identificados:
- Linhas com dados: DESCRIÇÃO... TICKER [CO] QUANTIDADE PREÇO VALOR...
- Linhas de continuação: Apenas texto (sem números no início)
"""

import re
from pathlib import Path
from typing import Optional, List, Dict
import pdfplumber
import pandas as pd
from dataclasses import dataclass


@dataclass
class Acao:
    """Representa uma ação extraída do PDF"""
    descricao: str
    ticker: str
    quantidade: float
    preco: float
    valor: float
    mes_ano: str
    usuario: str


class ParseadorAcoesPDFV3:
    """Parser robusto para PDFs Avenue com suporte a múltiplos formatos"""
    
    # Mapeamento de descrição para ticker (fallback)
    DESCRICAO_TICKER_MAP = {
        'GLOBAL X SUPERDIVIDEND': 'SDIV',
        'GLOBAL X FUNDS': 'DIV',  # ou SDIV conforme padrão
        'GLOBAL X SUPER DIVIDEND REIT': 'SRET',
        'ISHARES CORE S&P 500': 'IVV',
        'ISHARES 20 PLUS YEAR TREASURY': 'TLT',
        'ISHARES IBOXX': 'LQD',
        'ISHARES MSCI EMERGING': 'EEM',
        'ISHARES CORE U S AGGREGATE': 'AGG',
        'ISHARES TRUST EMERGING MARKETS': 'EMB',
        'INVESCO S&P 500 QUALITY': 'SPHQ',
        'INVESCO S&P 500 HIGH DIVID': 'SPHD',
        'INVESCO HIGH YIELD EQUITY': 'PEY',
        'INVESCO KBW HIGH DIVID YIELD FINL': 'KBWD',
        'INVESCO KBW PREMIUM YIELD': 'KBWY',
        'VANGUARD GROWTH': 'VUG',
        'VANGUARD REAL ESTATE': 'VNQ',
        'VANGUARD DIVIDEND APPRECIATION': 'VIG',
        'VANGUARD FTSE DEVELOPED': 'VNQI',
        'VANGUARD INTL EQUITY': 'VNQI',
        'VANGUARD TOTAL WORLD': 'VT',
    }
    
    # Padrão para linhas com dados (DESCRIÇÃO TICKER [CO] QTD PREÇO VALOR...)
    PADRAO_LINHA_DADOS = re.compile(
        r'^(.+?)'  # Descrição (non-greedy)
        r'\s+([A-Z]{1,6})'  # Ticker
        r'\s+([CO])'  # Account type
        r'\s+([\d.]+)'  # Quantidade
        r'\s+\$?([\d.,]+)'  # Preço
        r'\s+\$?([\d.,]+)'  # Valor
        r'\s'  # Espaço mínimo depois do valor
    )
    
    def __init__(self, mes_ano: str, usuario: str):
        self.mes_ano = mes_ano
        self.usuario = usuario
    
    def _limpar_valor(self, valor_str: str) -> Optional[float]:
        """Converte string de valor para float, lidando com múltiplos formatos"""
        if not valor_str:
            return None
        
        valor_str = str(valor_str).strip().replace("$", "").strip()
        
        # Padrão: 1,234.56 (americano)
        if "," in valor_str and "." in valor_str:
            partes = valor_str.split(".")
            if len(partes[-1]) <= 2:  # 2 casas decimais
                valor_str = valor_str.replace(",", "")  # Remove milhares
        # Padrão: 1,234 (sem decimais) ou 1,23 (decimal com vírgula)
        elif "," in valor_str and "." not in valor_str:
            partes = valor_str.split(",")
            if len(partes[-1]) == 2:  # Provavelmente decimal
                valor_str = valor_str.replace(",", ".")
            else:  # Provavelmente milhares
                valor_str = valor_str.replace(",", "")
        
        try:
            return float(valor_str)
        except ValueError:
            return None
    
    def _extrair_mes_ano_do_nome(self, nome_arquivo: str) -> str:
        """Extrai mês/ano do nome do arquivo"""
        # Padrão: ...2024_01_31... ou ...2024_12_31...
        match = re.search(r'(\d{4})_(\d{2})_\d{2}', nome_arquivo)
        if match:
            ano, mes = match.groups()
            return f"{mes}/{ano}"
        return self.mes_ano
    
    def _validar_acao(self, acao: Acao) -> bool:
        """Valida se os dados da ação fazem sentido"""
        if not acao.ticker or len(acao.ticker) > 6:
            return False
        if acao.quantidade <= 0 or acao.preco <= 0 or acao.valor <= 0:
            return False
        # Valida se valor ≈ quantidade × preço (margem de 10%)
        valor_calculado = acao.quantidade * acao.preco
        diferenca_pct = abs(valor_calculado - acao.valor) / acao.valor
        if diferenca_pct > 0.1:
            return False
        return True
    
    def _extrair_ticker_da_descricao(self, descricao: str) -> Optional[str]:
        """Tenta extrair ticker da descrição se não encontrado no padrão"""
        # Procura por ticker de 1-6 letras maiúsculas no final
        match = re.search(r'\b([A-Z]{1,6})\s*$', descricao)
        if match:
            ticker = match.group(1)
            if ticker not in ['ETF', 'BOND', 'FUND', 'TRUST', 'U', 'S', 'II', 'USD']:
                return ticker
        
        # Busca no mapa de descrições
        descricao_upper = descricao.upper()
        for descricao_chave, ticker_valor in self.DESCRICAO_TICKER_MAP.items():
            if descricao_chave in descricao_upper:
                return ticker_valor
        
        return None
    
    def _processar_texto_bruto(self, texto: str) -> List[Acao]:
        """Processa texto bruto com múltiplas linhas"""
        acoes = []
        linhas = texto.split('\n')
        
        i = 0
        while i < len(linhas):
            linha = linhas[i].strip()
            
            # Tenta casar com padrão de linha com dados
            match = self.PADRAO_LINHA_DADOS.match(linha)
            
            if match:
                descricao = match.group(1).strip()
                ticker = match.group(2).strip()
                account_type = match.group(3)
                quantidade_str = match.group(4)
                preco_str = match.group(5)
                valor_str = match.group(6)
                
                # Coleta linhas de continuação (próximas linhas sem padrão de dados)
                i += 1
                while i < len(linhas):
                    proxima_linha = linhas[i].strip()
                    if not proxima_linha:
                        i += 1
                        continue
                    
                    # Se próxima linha tem padrão de dados, para aqui
                    if self.PADRAO_LINHA_DADOS.match(proxima_linha):
                        break
                    
                    # Se é uma linha de continuação (sem números no início)
                    if not re.match(r'^\d+\s+|\s*\$', proxima_linha):
                        descricao += " " + proxima_linha
                        i += 1
                    else:
                        break
                
                # Processa valores
                quantidade = self._limpar_valor(quantidade_str)
                preco = self._limpar_valor(preco_str)
                valor = self._limpar_valor(valor_str)
                
                # Fallback para ticker se não encontrado
                if not ticker or ticker in ['C', 'O']:
                    ticker = self._extrair_ticker_da_descricao(descricao)
                
                # Cria objeto Acao
                acao = Acao(
                    descricao=descricao,
                    ticker=ticker or "UNKNOWN",
                    quantidade=quantidade or 0,
                    preco=preco or 0,
                    valor=valor or 0,
                    mes_ano=self.mes_ano,
                    usuario=self.usuario
                )
                
                # Valida e adiciona
                if self._validar_acao(acao):
                    acoes.append(acao)
            else:
                i += 1
        
        return acoes
    
    def extrair_do_pdf(self, caminho_pdf: str) -> pd.DataFrame:
        """Extrai todas as ações do PDF"""
        acoes = []
        
        with pdfplumber.open(caminho_pdf) as doc:
            # Extrai mês/ano do nome do arquivo
            nome_arquivo = Path(caminho_pdf).name
            self.mes_ano = self._extrair_mes_ano_do_nome(nome_arquivo)
            
            # Coleta TODOS os textos de EQUITIES em todas as páginas
            secao_equities_completa = ""
            
            for page_num, page in enumerate(doc.pages):
                text = page.extract_text()
                
                # Se encontrou EQUITIES nesta página, extrai tudo
                if "EQUITIES" in text:
                    # Extrai do EQUITIES até Total Equities (se existir) ou fim da página
                    match = re.search(
                        r'EQUITIES\s*/\s*OPTIONS(.*?)(?:Total Equities|$)',
                        text,
                        re.DOTALL
                    )
                    
                    if match:
                        parte = match.group(1).strip()
                        
                        # Se encontrou "Total Equities", para aqui (fim da seção)
                        if "Total Equities" in text:
                            secao_equities_completa += "\n" + parte
                            break  # Fim da seção EQUITIES
                        else:
                            # Continua para próxima página
                            secao_equities_completa += "\n" + parte
                
                # Se já encontrou EQUITIES antes mas ainda não terminou
                elif secao_equities_completa:
                    # Verifica se continua com dados de equities
                    match = re.search(r'(.*?)(?:Total Equities|$)', text, re.DOTALL)
                    if match:
                        parte = match.group(1).strip()
                        secao_equities_completa += "\n" + parte
                    
                    # Para quando encontrar Total Equities
                    if "Total Equities" in text:
                        break
            
            # Processa o texto coletado
            if secao_equities_completa:
                acoes_extraidas = self._processar_texto_bruto(secao_equities_completa)
                acoes.extend(acoes_extraidas)
        
        # Converte para DataFrame
        if acoes:
            df = pd.DataFrame([{
                'Produto': acao.descricao,
                'Ticker': acao.ticker,
                'Código de Negociação': '',  # Pode preencher depois
                'Quantidade Disponível': acao.quantidade,
                'Preço de Fechamento': acao.preco,
                'Valor': acao.valor,
                'Mês/Ano': acao.mes_ano,
                'Usuário': acao.usuario
            } for acao in acoes])
            return df
        else:
            return pd.DataFrame()


# Função pública
def extrair_acoes_pdf_v3(arquivo_pdf: str, usuario: str, mes_ano: str = "12/2024") -> pd.DataFrame:
    """
    Extrai ações de um PDF Avenue
    
    Args:
        arquivo_pdf: Caminho para o PDF
        usuario: Nome do usuário (ex: "Giselle Cardin")
        mes_ano: Mês/ano no formato MM/YYYY (extraído automaticamente)
    
    Returns:
        DataFrame com colunas: Produto, Ticker, Código de Negociação, 
        Quantidade Disponível, Preço de Fechamento, Valor, Mês/Ano, Usuário
    """
    parser = ParseadorAcoesPDFV3(mes_ano, usuario)
    return parser.extrair_do_pdf(arquivo_pdf)


# Testes
if __name__ == "__main__":
    # Teste com PDF de múltiplos ativos
    pdf_janeiro = "Relatorios/Avenue/Giselle Cardin/Doc_101579_STATEMENT_6AU71559_2024_01_31_142026_74011_AM_RVE6fZSu.pdf"
    
    print("Testando com PDF de Janeiro (múltiplos ativos)...\n")
    df = extrair_acoes_pdf_v3(pdf_janeiro, "Giselle Cardin")
    
    print(f"Ações extraídas: {len(df)}")
    print(f"\nPrimeiras 5 linhas:")
    print(df.head())
    print(f"\nDetalhes:")
    print(df.to_string())
    
    print(f"\n\nTickers únicos: {df['Ticker'].unique().tolist()}")
    print(f"Total em valores: ${df['Valor'].sum():.2f}")
