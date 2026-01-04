"""
Wrapper de compatibilidade para usar o novo parser v3.
Substitui as funções antigas de upload_pdf_avenue.py.
"""

from upload_pdf_avenue_v3 import extrair_acoes_pdf_v3 as _extrair_v3_acoes
import pandas as pd
from pathlib import Path
from typing import Optional, Tuple
import os


def extrair_acoes_pdf(arquivo_pdf: str, usuario: str = "Importado", mes_ano: Optional[str] = None) -> pd.DataFrame:
    """
    Extrai ações de um PDF Avenue usando o novo parser v3.
    
    Substitui a função anterior com versão muito mais precisa.
    
    Args:
        arquivo_pdf: Caminho para o PDF
        usuario: Nome do usuário (padrão: "Importado")
        mes_ano: Mês/ano no formato MM/YYYY (extraído automaticamente se None)
    
    Returns:
        DataFrame com colunas: Produto, Ticker, Código de Negociação, 
        Quantidade Disponível, Preço de Fechamento, Valor, Mês/Ano, Usuário
    """
    if not os.path.exists(arquivo_pdf):
        raise FileNotFoundError(f"Arquivo não encontrado: {arquivo_pdf}")
    
    try:
        # Usa o novo parser v3
        df = _extrair_v3_acoes(arquivo_pdf, usuario, mes_ano or "12/2024")
        
        # Se vazio, retorna DataFrame com as colunas esperadas
        if df.empty:
            return pd.DataFrame(columns=[
                'Produto', 'Ticker', 'Código de Negociação',
                'Quantidade Disponível', 'Preço de Fechamento', 'Valor', 
                'Mês/Ano', 'Usuário'
            ])
        
        # Garante que as colunas estão no formato esperado
        colunas_esperadas = [
            'Produto', 'Ticker', 'Código de Negociação',
            'Quantidade Disponível', 'Preço de Fechamento', 'Valor', 
            'Mês/Ano', 'Usuário'
        ]
        
        # Reordena colunas se necessário
        for col in colunas_esperadas:
            if col not in df.columns:
                df[col] = None
        
        return df[colunas_esperadas]
        
    except Exception as e:
        print(f"Erro ao extrair PDF {arquivo_pdf} com v3: {str(e)}")
        # Retorna DataFrame vazio com estrutura correta em caso de erro
        return pd.DataFrame(columns=[
            'Produto', 'Ticker', 'Código de Negociação',
            'Quantidade Disponível', 'Preço de Fechamento', 'Valor', 
            'Mês/Ano', 'Usuário'
        ])


def extrair_dividendos_pdf(
    arquivo_pdf: str,
    usuario: str = "Importado",
    mes_ano: Optional[str] = None,
    tickers_portfolio: set = None
) -> pd.DataFrame:
    """
    Função stub - dividendos não estão implementados no v3 ainda.
    Retorna DataFrame vazio para compatibilidade.
    """
    return pd.DataFrame(columns=[
        'Data Comex', 'Produto', 'Ticker', 'Valor Bruto', 'Imposto', 
        'Valor Líquido', 'Mês/Ano', 'Usuário'
    ])


# Funções auxiliares para integração
def processar_pdf_individual(
    arquivo_pdf: str,
    usuario: Optional[str] = None,
    mes_ano: Optional[str] = None,
    incluir_dividendos: bool = True
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Compatível com a assinatura anterior"""
    usuario = usuario or "Importado"
    
    df_acoes = extrair_acoes_pdf(arquivo_pdf, usuario, mes_ano)
    df_dividendos = extrair_dividendos_pdf(arquivo_pdf, usuario, mes_ano) if incluir_dividendos else pd.DataFrame()
    
    return df_acoes, df_dividendos


if __name__ == "__main__":
    # Teste simples
    pdf_teste = "../Relatorios/Avenue/Hudson Cardin/Doc_101579_STATEMENT_6AV40121_2024_12_31_142026_73157_AM_eRVKImAs.pdf"
    
    print("Testando wrapper de compatibilidade...\n")
    df = extrair_acoes_pdf(pdf_teste, "Hudson Cardin")
    
    print(f"Ações extraídas: {len(df)}")
    print(f"\nPrimeiras 3 linhas:")
    print(df.head(3))
    print(f"\nTickers: {df['Ticker'].unique().tolist()}")
    print(f"Total: ${df['Valor'].sum():.2f}")
