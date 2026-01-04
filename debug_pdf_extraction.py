"""
Script para análise profunda da extração de dados de PDFs Avenue.
Identifica problemas com tickers e valores.
"""

import pdfplumber
import os
import re
from pathlib import Path
import pandas as pd

def analisar_pdf_completo(pdf_path):
    """Análise completa de um PDF Avenue."""
    print(f"\n{'='*80}")
    print(f"ANÁLISE: {os.path.basename(pdf_path)}")
    print(f"{'='*80}")
    
    with pdfplumber.open(pdf_path) as pdf:
        print(f"\nTotal de páginas: {len(pdf.pages)}")
        
        # Página 1: Cabeçalho
        page = pdf.pages[0]
        text = page.extract_text()
        
        # Extrair dados principais
        account_match = re.search(r'ACCOUNT NUMBER\s+(\S+)', text)
        account_holder = None
        for line in text.split('\n'):
            if any(x in line for x in ['GISELLE', 'HUDSON', 'CARDIN']):
                account_holder = line.strip()
                break
        
        print(f"\nConta: {account_match.group(1) if account_match else 'Não encontrada'}")
        print(f"Titular: {account_holder}")
        
        # Página 2-3: Portfolio Summary (AÇÕES)
        print(f"\n{'='*80}")
        print("SEÇÃO: PORTFOLIO SUMMARY (AÇÕES)")
        print(f"{'='*80}")
        
        portfolio_data = []
        for page_idx in range(1, min(4, len(pdf.pages))):
            page = pdf.pages[page_idx]
            text = page.extract_text()
            
            if "PORTFOLIO SUMMARY" in text or "EQUITIES / OPTIONS" in text:
                print(f"\n[Página {page_idx + 1}] Encontrado Portfolio Summary")
                
                # Procurar por linhas com dados de ações
                lines = text.split('\n')
                for i, line in enumerate(lines):
                    # Padrão: SYMBOL/DESCRIPTION ... QUANTITY ... PRICE ... VALUE
                    if any(x in line for x in ['IVV', 'GLOBAL X', 'TLT', 'LQD', 'EEM', 'AGG']):
                        print(f"  Linha {i}: {line[:100]}")
                        # Tentar extrair ticker, quantidade e valor
                        parts = line.split()
                        print(f"    Partes: {parts}")
        
        # Página 4: Dividendos
        print(f"\n{'='*80}")
        print("SEÇÃO: DIVIDENDOS E JUROS")
        print(f"{'='*80}")
        
        for page_idx in range(min(4, len(pdf.pages)), len(pdf.pages)):
            page = pdf.pages[page_idx]
            text = page.extract_text()
            
            if "DIVIDENDS AND INTEREST" in text or "DIVIDEND" in text:
                print(f"\n[Página {page_idx + 1}] Encontrado Dividendos")
                
                lines = text.split('\n')
                in_div_section = False
                for i, line in enumerate(lines):
                    if "DIVIDENDS AND INTEREST" in line:
                        in_div_section = True
                        continue
                    
                    if in_div_section:
                        if "Total Dividends" in line or "FUNDS PAID" in line:
                            break
                        
                        if line.strip() and any(x in line for x in ['DIVIDEND', 'INTEREST', 'CASH DIV']):
                            print(f"  Linha {i}: {line[:120]}")
                            # Procurar por ticker na próxima linha
                            if i + 1 < len(lines):
                                next_line = lines[i + 1]
                                print(f"    Próx: {next_line[:120]}")


def testar_extracao_tabelas(pdf_path):
    """Testa extração de tabelas."""
    print(f"\n{'='*80}")
    print(f"ANÁLISE DE TABELAS: {os.path.basename(pdf_path)}")
    print(f"{'='*80}")
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            if tables:
                print(f"\n[Página {page_idx + 1}] {len(tables)} tabela(s) encontrada(s)")
                for t_idx, table in enumerate(tables):
                    print(f"\nTabela {t_idx} ({len(table)} linhas x {len(table[0]) if table else 0} colunas):")
                    
                    # Primeiras 5 linhas
                    for row_idx, row in enumerate(table[:5]):
                        print(f"  [{row_idx}] {row}")
                    
                    if len(table) > 5:
                        print(f"  ... ({len(table) - 5} linhas omitidas)")


def comparar_modelos():
    """Compara diferentes modelos de PDFs."""
    base_dir = r'Relatorios\Avenue'
    
    print(f"\n{'='*80}")
    print("COMPARAÇÃO DE MODELOS DE PDFS")
    print(f"{'='*80}")
    
    for folder in os.listdir(base_dir):
        folder_path = os.path.join(base_dir, folder)
        if not os.path.isdir(folder_path):
            continue
        
        pdfs = [f for f in os.listdir(folder_path) if f.endswith('.pdf')]
        if not pdfs:
            continue
        
        print(f"\n📁 {folder}: {len(pdfs)} PDFs")
        
        # Analisar primeiro PDF de cada pasta
        pdf_path = os.path.join(folder_path, pdfs[0])
        
        with pdfplumber.open(pdf_path) as pdf:
            # Contar páginas e estrutura geral
            total_pages = len(pdf.pages)
            
            # Procurar por seções principais
            has_portfolio = False
            has_dividends = False
            has_transactions = False
            
            for page in pdf.pages:
                text = page.extract_text()
                if "PORTFOLIO SUMMARY" in text or "EQUITIES" in text:
                    has_portfolio = True
                if "DIVIDENDS" in text or "DIVIDEND" in text:
                    has_dividends = True
                if "BUY / SELL" in text or "TRANSACTION" in text:
                    has_transactions = True
            
            print(f"  ✓ Páginas: {total_pages}")
            print(f"  ✓ Portfolio: {'Sim' if has_portfolio else 'Não'}")
            print(f"  ✓ Dividendos: {'Sim' if has_dividends else 'Não'}")
            print(f"  ✓ Transações: {'Sim' if has_transactions else 'Não'}")


if __name__ == "__main__":
    # Teste com primeiro PDF
    base_dir = r'Relatorios\Avenue'
    
    for folder in os.listdir(base_dir):
        folder_path = os.path.join(base_dir, folder)
        if not os.path.isdir(folder_path):
            continue
        
        pdfs = [f for f in os.listdir(folder_path) if f.endswith('.pdf')]
        if not pdfs:
            continue
        
        pdf_path = os.path.join(folder_path, pdfs[0])
        
        # Análise completa
        analisar_pdf_completo(pdf_path)
        
        # Análise de tabelas
        testar_extracao_tabelas(pdf_path)
        
        break  # Apenas primeiro
    
    # Comparação de modelos
    comparar_modelos()
    
    print(f"\n{'='*80}")
    print("ANÁLISE CONCLUÍDA")
    print(f"{'='*80}\n")
