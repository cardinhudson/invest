# 🎓 EXEMPLOS PRÁTICOS: Como Usar o Novo Parser de PDFs

## 1. Exemplo Básico: Extrair Ações de um PDF

```python
from modules.upload_pdf_avenue_v2 import extrair_acoes_pdf_v2
import pandas as pd

# Extrair ações de um PDF
pdf_path = r'Relatorios\Avenue\Giselle Cardin\Doc_101579_STATEMENT_6AU71559_2024_01_31_142026_74011_AM_RVE6fZSu.pdf'

df_acoes = extrair_acoes_pdf_v2(
    arquivo_pdf=pdf_path,
    usuario="Giselle Cardin",
    mes_ano="01/2025"
)

# Exibir resultados
print(f"Ações extraídas: {len(df_acoes)}")
print(df_acoes[['Ticker', 'Quantidade Disponível', 'Preço de Fechamento', 'Valor']])

# Resultado esperado:
#   Ticker  Quantidade Disponível  Preço de Fechamento    Valor
# 0   DGDV                27.97                16.952    474.18
# 1   SDIV                14.99                21.710    325.53
# 2    IVV                 2.10               485.200   1018.47  ✅ Agora funciona!
# 3    TLT                 4.93                96.660    476.21
# ... (11 mais)
```

---

## 2. Usar com Streamlit (Upload de PDF)

```python
import streamlit as st
from modules.upload_pdf_avenue_v2 import extrair_acoes_pdf_v2, extrair_dividendos_pdf_v2
import tempfile

st.title("Upload de Relatório Avenue")

# Upload do arquivo
uploaded_file = st.file_uploader("Selecione um PDF", type="pdf")

if uploaded_file:
    # Salvar temporariamente
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.getbuffer())
        tmp_path = tmp.name
    
    # Selecionar usuário
    usuario = st.selectbox("Usuário", ["Giselle Cardin", "Hudson Cardin"])
    
    # Botão para processar
    if st.button("Processar PDF"):
        try:
            # Extrair ações
            df_acoes = extrair_acoes_pdf_v2(tmp_path, usuario=usuario)
            
            st.success(f"✅ {len(df_acoes)} ações extraídas!")
            
            # Exibir tabela
            st.dataframe(df_acoes)
            
            # Mostrar resumo
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total de Ações", len(df_acoes))
            with col2:
                st.metric("Valor Total", f"R$ {df_acoes['Valor'].sum():,.2f}")
            
            # Extrair dividendos
            tickers = set(df_acoes['Ticker'].unique())
            df_divs = extrair_dividendos_pdf_v2(tmp_path, usuario=usuario, tickers_portfolio=tickers)
            
            if not df_divs.empty:
                st.subheader("Dividendos")
                st.dataframe(df_divs)
            
        except Exception as e:
            st.error(f"Erro: {str(e)}")
```

---

## 3. Processar Múltiplos PDFs em Batch

```python
from modules.upload_pdf_avenue_v2 import extrair_acoes_pdf_v2
import os
import pandas as pd

def processar_pasta_relatorios(pasta_base: str):
    """Processa todos os PDFs de uma pasta."""
    
    todos_acoes = []
    
    for usuario_folder in os.listdir(pasta_base):
        folder_path = os.path.join(pasta_base, usuario_folder)
        
        if not os.path.isdir(folder_path):
            continue
        
        for pdf_file in os.listdir(folder_path):
            if not pdf_file.endswith('.pdf'):
                continue
            
            pdf_path = os.path.join(folder_path, pdf_file)
            
            try:
                print(f"Processando: {usuario_folder}/{pdf_file}")
                
                df = extrair_acoes_pdf_v2(pdf_path, usuario=usuario_folder)
                todos_acoes.append(df)
                
                print(f"  ✓ {len(df)} ações extraídas")
                
            except Exception as e:
                print(f"  ✗ Erro: {e}")
    
    # Consolidar tudo
    df_consolidado = pd.concat(todos_acoes, ignore_index=True)
    
    # Remover duplicatas
    df_consolidado = df_consolidado.drop_duplicates(
        subset=['Mês/Ano', 'Usuário', 'Ticker', 'Quantidade Disponível'],
        keep='last'
    )
    
    return df_consolidado

# Usar
df_tudo = processar_pasta_relatorios(r'Relatorios\Avenue')
print(f"\nTotal consolidado: {len(df_tudo)} ações")
print(df_tudo.groupby('Usuário')['Ticker'].count())
```

---

## 4. Comparar Extrações (v1 vs v2)

```python
from modules.upload_pdf_avenue import extrair_acoes_pdf as extrair_acoes_v1
from modules.upload_pdf_avenue_v2 import extrair_acoes_pdf_v2 as extrair_acoes_v2
import pandas as pd

pdf_path = r'Relatorios\Avenue\Giselle Cardin\...'

# Extrair com ambas as versões
df_v1 = extrair_acoes_v1(pdf_path, usuario="Giselle")
df_v2 = extrair_acoes_v2(pdf_path, usuario="Giselle")

print(f"V1: {len(df_v1)} ações")
print(f"V2: {len(df_v2)} ações")

# Comparar tickers
print("\nTickers V1:")
print(sorted(df_v1['Ticker'].unique()))

print("\nTickers V2:")
print(sorted(df_v2['Ticker'].unique()))

# Mostrar melhorias
tickers_v2_extras = set(df_v2['Ticker']) - set(df_v1['Ticker'])
if tickers_v2_extras:
    print(f"\n✅ Novos tickers corrigidos: {tickers_v2_extras}")

# Comparar valores
comparacao = pd.merge(
    df_v1[['Ticker', 'Quantidade Disponível', 'Valor']],
    df_v2[['Ticker', 'Quantidade Disponível', 'Valor']],
    on='Ticker',
    suffixes=('_v1', '_v2')
)

print("\nComparação de Valores:")
print(comparacao)
```

---

## 5. Validar Integridade de Extração

```python
from modules.upload_pdf_avenue_v2 import extrair_acoes_pdf_v2
import pandas as pd

def validar_extracao(pdf_path: str, usuario: str) -> dict:
    """Valida extração com múltiplos critérios."""
    
    df = extrair_acoes_pdf_v2(pdf_path, usuario=usuario)
    
    validacoes = {
        "total_acoes": len(df),
        "tickers_unicos": df['Ticker'].nunique(),
        "tickers_validos": (df['Ticker'] != 'UNKNOWN').sum(),
        "tickers_nulos": df['Ticker'].isnull().sum(),
        "quantidade_positiva": (df['Quantidade Disponível'] > 0).sum(),
        "preco_positivo": (df['Preço de Fechamento'] > 0).sum(),
        "valor_positivo": (df['Valor'] > 0).sum(),
        "valor_total": df['Valor'].sum(),
        "precisao_valor": "OK",  # Verificar se Qtd * Preço ≈ Valor
    }
    
    # Verificar precisão de valores
    for idx, row in df.iterrows():
        calculado = row['Quantidade Disponível'] * row['Preço de Fechamento']
        if abs(calculado - row['Valor']) > 0.01:  # Tolerância de 1 centavo
            validacoes["precisao_valor"] = "AVISO"
            print(f"Aviso: {row['Ticker']} valor fora (calc: {calculado}, real: {row['Valor']})")
    
    # Relatório
    print(f"Validação de {usuario}")
    print("-" * 50)
    for key, value in validacoes.items():
        print(f"  {key:25}: {value}")
    
    # Verificação geral
    status = "✅ OK" if (
        validacoes["tickers_validos"] == validacoes["total_acoes"] and
        validacoes["tickers_nulos"] == 0 and
        validacoes["quantidade_positiva"] == validacoes["total_acoes"] and
        validacoes["preco_positivo"] == validacoes["total_acoes"] and
        validacoes["valor_positivo"] == validacoes["total_acoes"] and
        validacoes["precisao_valor"] == "OK"
    ) else "⚠️  AVISO"
    
    print(f"\nStatus: {status}")
    
    return validacoes

# Usar
validar_extracao(r'Relatorios\Avenue\Giselle Cardin\...pdf', "Giselle Cardin")
```

---

## 6. Exportar Dados Processados

```python
from modules.upload_pdf_avenue_v2 import extrair_acoes_pdf_v2
import os
import pandas as pd

def exportar_acoes_para_excel(pasta_origem: str, arquivo_destino: str):
    """Exporta todas as ações para um único arquivo Excel."""
    
    todos_acoes = []
    
    for usuario in os.listdir(pasta_origem):
        usuario_path = os.path.join(pasta_origem, usuario)
        if not os.path.isdir(usuario_path):
            continue
        
        for pdf in os.listdir(usuario_path):
            if not pdf.endswith('.pdf'):
                continue
            
            try:
                df = extrair_acoes_pdf_v2(
                    os.path.join(usuario_path, pdf),
                    usuario=usuario
                )
                todos_acoes.append(df)
            except:
                pass
    
    # Consolidar
    df_final = pd.concat(todos_acoes, ignore_index=True)
    
    # Ordenar e limpar
    df_final = df_final.sort_values(['Usuário', 'Mês/Ano', 'Ticker'])
    df_final = df_final.drop_duplicates(
        subset=['Usuário', 'Mês/Ano', 'Ticker'],
        keep='last'
    )
    
    # Salvar
    with pd.ExcelWriter(arquivo_destino, engine='openpyxl') as writer:
        df_final.to_excel(writer, sheet_name='Ações', index=False)
        
        # Adicionar sheet de resumo
        resumo = df_final.groupby('Usuário').agg({
            'Ticker': 'count',
            'Valor': 'sum',
            'Quantidade Disponível': 'sum'
        }).rename(columns={'Ticker': 'Total Ativos'})
        
        resumo.to_excel(writer, sheet_name='Resumo')
    
    print(f"✓ Exportado para {arquivo_destino}")
    return df_final

# Usar
df = exportar_acoes_para_excel(
    r'Relatorios\Avenue',
    r'exports\consolidado_acoes.xlsx'
)
```

---

## 7. Atualizar Dados em Banco de Dados

```python
from modules.upload_pdf_avenue_v2 import extrair_acoes_pdf_v2
import sqlite3
import pandas as pd

def salvar_em_sqlite(pdf_path: str, usuario: str, db_path: str = 'investimentos.db'):
    """Salva dados extraídos do PDF em SQLite."""
    
    df = extrair_acoes_pdf_v2(pdf_path, usuario=usuario)
    
    if df.empty:
        print("Nenhuma ação para salvar")
        return
    
    # Conectar ao banco
    conn = sqlite3.connect(db_path)
    
    try:
        # Salvar ações
        df.to_sql('acoes', conn, if_exists='append', index=False)
        print(f"✓ {len(df)} ações salvos em {db_path}")
    
    finally:
        conn.close()

# Usar
salvar_em_sqlite(
    r'Relatorios\Avenue\Giselle Cardin\...pdf',
    'Giselle Cardin'
)
```

---

## 8. Gerar Relatório de Análise

```python
from modules.upload_pdf_avenue_v2 import extrair_acoes_pdf_v2
import pandas as pd

def gerar_relatorio_analise(pdf_path: str, usuario: str):
    """Gera relatório de análise do portfólio."""
    
    df = extrair_acoes_pdf_v2(pdf_path, usuario=usuario)
    
    print(f"\n{'='*60}")
    print(f"RELATÓRIO DE PORTFÓLIO - {usuario}")
    print(f"{'='*60}\n")
    
    # Resumo geral
    print(f"Valor Total: R$ {df['Valor'].sum():,.2f}")
    print(f"Total de Ativos: {len(df)}")
    print(f"Ativos Únicos: {df['Ticker'].nunique()}")
    
    # Top 5 maiores posições
    print(f"\nTop 5 Posições:")
    top5 = df.nlargest(5, 'Valor')[['Ticker', 'Produto', 'Quantidade Disponível', 'Valor']]
    for idx, row in top5.iterrows():
        pct = (row['Valor'] / df['Valor'].sum()) * 100
        print(f"  {row['Ticker']:6} - {row['Produto'][:30]:30} - R$ {row['Valor']:10,.2f} ({pct:5.2f}%)")
    
    # Distribuição por tipo (baseado em padrões de nome)
    print(f"\nDistribuição por Tipo:")
    etfs = df[df['Produto'].str.contains('ETF', case=False, na=False)]
    stocks = df[~df['Produto'].str.contains('ETF', case=False, na=False)]
    
    print(f"  ETFs: {len(etfs)} ativos - R$ {etfs['Valor'].sum():,.2f}")
    print(f"  Ações: {len(stocks)} ativos - R$ {stocks['Valor'].sum():,.2f}")
    
    print(f"\n{'='*60}\n")

# Usar
gerar_relatorio_analise(
    r'Relatorios\Avenue\Giselle Cardin\...pdf',
    'Giselle Cardin'
)
```

---

## 9. Monitorar Novos Tickers

```python
from modules.upload_pdf_avenue_v2 import extrair_acoes_pdf_v2, DESCRICAO_TICKER_MAP
import os

def encontrar_tickers_desconhecidos(pasta_origem: str):
    """Encontra tickers não mapeados."""
    
    desconhecidos = set()
    
    for usuario in os.listdir(pasta_origem):
        usuario_path = os.path.join(pasta_origem, usuario)
        if not os.path.isdir(usuario_path):
            continue
        
        for pdf in os.listdir(usuario_path):
            if not pdf.endswith('.pdf'):
                continue
            
            try:
                df = extrair_acoes_pdf_v2(
                    os.path.join(usuario_path, pdf),
                    usuario=usuario
                )
                
                # Procurar por UNKNOWN
                unknown = df[df['Ticker'] == 'UNKNOWN']
                if not unknown.empty:
                    for _, row in unknown.iterrows():
                        desconhecidos.add(row['Produto'])
            except:
                pass
    
    if desconhecidos:
        print(f"⚠️  Tickers Desconhecidos Encontrados:")
        for ticker in sorted(desconhecidos):
            print(f"  - {ticker}")
        
        print(f"\nAdicione ao DESCRICAO_TICKER_MAP em upload_pdf_avenue_v2.py")
    else:
        print("✓ Todos os tickers estão mapeados!")

# Usar
encontrar_tickers_desconhecidos(r'Relatorios\Avenue')
```

---

## 10. Testar Performance

```python
from modules.upload_pdf_avenue_v2 import extrair_acoes_pdf_v2
import time
import os

def medir_performance(pasta_origem: str, num_pdfs: int = 10):
    """Mede o tempo de processamento."""
    
    pdfs = []
    for usuario in os.listdir(pasta_origem):
        usuario_path = os.path.join(pasta_origem, usuario)
        if os.path.isdir(usuario_path):
            for pdf in os.listdir(usuario_path):
                if pdf.endswith('.pdf'):
                    pdfs.append(os.path.join(usuario_path, pdf))
    
    pdfs = pdfs[:num_pdfs]
    
    print(f"Processando {len(pdfs)} PDFs...")
    
    tempo_total = 0
    acoes_total = 0
    
    for pdf_path in pdfs:
        inicio = time.time()
        df = extrair_acoes_pdf_v2(pdf_path)
        tempo = time.time() - inicio
        
        tempo_total += tempo
        acoes_total += len(df)
        
        print(f"  {os.path.basename(pdf_path)[:40]:40} - {tempo:.2f}s ({len(df)} ações)")
    
    print(f"\nResumo:")
    print(f"  Total de PDFs: {len(pdfs)}")
    print(f"  Total de Ações: {acoes_total}")
    print(f"  Tempo Total: {tempo_total:.2f}s")
    print(f"  Tempo Médio/PDF: {tempo_total/len(pdfs):.2f}s")
    print(f"  Ações/Segundo: {acoes_total/tempo_total:.0f}")

# Usar
medir_performance(r'Relatorios\Avenue', num_pdfs=20)
```

---

## 📚 Referência Rápida

| Função | Uso | Retorno |
|--------|-----|---------|
| `extrair_acoes_pdf_v2()` | Extrair ações de um PDF | `pd.DataFrame` |
| `extrair_dividendos_pdf_v2()` | Extrair dividendos | `pd.DataFrame` |
| `_resolve_ticker_from_description()` | Mapear descrição → ticker | `str` |
| `testar_extracao()` | Debug e testes | Imprime resultados |

---

**Dica**: Combinar esses exemplos com seu pipeline existente em `upload_ingest.py`!
