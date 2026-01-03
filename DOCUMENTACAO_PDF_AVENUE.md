# 📄 Documentação: Processamento de PDFs da Avenue

## 📋 Visão Geral

O módulo `modules/upload_pdf_avenue.py` permite processar extratos em PDF da corretora Avenue para extrair:
- **Posições em ações**: nome, ticker, quantidade, preço, valor de mercado
- **Dividendos recebidos**: data, ativo, valor bruto, impostos, valor líquido

---

## 🚀 Instalação

### Requisitos
```bash
pip install pdfplumber pandas openpyxl streamlit
```

### Estrutura de Pastas
```
project/
├── modules/
│   ├── upload_pdf_avenue.py    # Novo módulo
│   ├── upload_relatorio.py
│   └── ...
├── data/
│   ├── acoes_avenue.parquet    # Ações extraídas de PDFs
│   └── dividendos_avenue.parquet # Dividendos extraídos de PDFs
├── uploads/
│   └── pdf_avenue/             # PDFs salvos (estrutura interna)
└── APP.py
```

---

## 📚 API - Funções Disponíveis

### 1. `processar_pdf_individual(arquivo_pdf, usuario, mes_ano)`
Processa um único arquivo PDF.

**Parâmetros:**
- `arquivo_pdf` (str): Caminho completo do arquivo PDF
- `usuario` (str, opcional): Nome do usuário (padrão: "Importado")
- `mes_ano` (str, opcional): Período em formato MM/YYYY (auto-detectado do nome do arquivo)

**Retorna:**
- `(df_acoes, df_dividendos)`: Tupla com DataFrames

**Exemplo:**
```python
from modules.upload_pdf_avenue import processar_pdf_individual

df_acoes, df_dividendos = processar_pdf_individual(
    r"C:\Users\hudso\Downloads\Stmt_20251130.pdf",
    usuario="Hudson",
    mes_ano="11/2025"
)
print(f"Ações: {len(df_acoes)}, Dividendos: {len(df_dividendos)}")
```

---

### 2. `processar_pasta_pdfs(caminho_pasta, usuario)`
Processa todos os PDFs de uma pasta.

**Parâmetros:**
- `caminho_pasta` (str): Caminho da pasta com PDFs
- `usuario` (str, opcional): Nome do usuário (padrão: "Importado")

**Retorna:**
- `(df_acoes_consolidado, df_dividendos_consolidado)`: DataFrames consolidados

**Exemplo:**
```python
df_acoes, df_dividendos = processar_pasta_pdfs(
    r"C:\Users\hudso\Downloads\Statements",
    usuario="Hudson"
)
```

---

### 3. `processar_pdfs_usuario(usuario, raiz_uploads)`
Processa todos os PDFs de um usuário em `uploads/<usuario>/`.

**Parâmetros:**
- `usuario` (str): Nome do usuário
- `raiz_uploads` (str, opcional): Caminho raiz (padrão: "uploads")

**Retorna:**
- `(df_acoes, df_dividendos)`: DataFrames

**Exemplo:**
```python
df_acoes, df_dividendos = processar_pdfs_usuario("Hudson")
```

---

### 4. `salvar_acoes_pdf_parquet(df_acoes, path)`
Salva ações extraídas em formato Parquet (com deduplicação automática).

**Parâmetros:**
- `df_acoes` (pd.DataFrame): DataFrame com ações
- `path` (str): Caminho do arquivo Parquet (padrão: "data/acoes_avenue.parquet")

**Exemplo:**
```python
from modules.upload_pdf_avenue import salvar_acoes_pdf_parquet

salvar_acoes_pdf_parquet(df_acoes, "data/acoes_avenue.parquet")
```

---

### 5. `salvar_dividendos_pdf_parquet(df_dividendos, path)`
Salva dividendos extraídos em formato Parquet (com deduplicação automática).

**Parâmetros:**
- `df_dividendos` (pd.DataFrame): DataFrame com dividendos
- `path` (str): Caminho do arquivo Parquet (padrão: "data/dividendos_avenue.parquet")

---

## 📊 Estrutura de Dados

### Ações (DataFrame)
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| Produto | str | Nome completo do ativo |
| Ticker | str | Ticker da ação (ex: VALE3) |
| Código de Negociação | str | Código para negociação |
| Quantidade Disponível | float | Quantidade de ações |
| Preço de Fechamento | float | Preço unitário |
| Valor | float | Valor total de mercado |
| Mês/Ano | str | Período em MM/YYYY |
| Usuário | str | Nome do usuário proprietário |

**Exemplo:**
```
Produto: VALE3 - VALE SA
Ticker: VALE3
Quantidade: 100
Preço: 54.32
Valor: 5432.00
Mês/Ano: 11/2025
Usuário: Hudson
```

---

### Dividendos (DataFrame)
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| Produto | str | Nome do ativo que pagou |
| Data de Pagamento | str | Data do crédito |
| Tipo de Provento | str | "Dividendo" |
| Valor Líquido | float | Valor recebido após impostos |
| Mês/Ano | str | Período em MM/YYYY |
| Usuário | str | Nome do usuário beneficiário |

**Exemplo:**
```
Produto: VALE3 - VALE SA
Data: 2025-11-15
Tipo: Dividendo
Valor Líquido: 150.00
Mês/Ano: 11/2025
Usuário: Hudson
```

---

## 🔧 Integração com o Sistema

### No APP.py
Uma nova aba **"Upload PDF Avenue"** foi adicionada com 3 opções:

1. **Upload Individual**
   - Upload de um arquivo PDF por vez
   - Auto-detecção do mês/ano do nome do arquivo
   - Opção de salvar os dados extraídos

2. **Processar Pasta**
   - Seleciona uma pasta com múltiplos PDFs
   - Processa todos os arquivos recursivamente
   - Consolida resultados

3. **Processar por Usuário**
   - Processa automaticamente todos os PDFs do usuário
   - Busca em `uploads/<usuario>/` ou `uploads/<usuario>/pdfs/`

### Fluxo de Salvamento
```
PDF → Processamento → DataFrame → Deduplica → Salva em Parquet
                                    ↓
                          data/acoes_avenue.parquet
                          data/dividendos_avenue.parquet
```

---

## 📝 Formatos de Nome de Arquivo Suportados

O módulo auto-detecta o mês/ano do nome do arquivo:
- ✅ `Stmt_20251130.pdf` → 11/2025
- ✅ `statement_20251115.pdf` → 11/2025
- ✅ `extrato_2025_11.pdf` → 11/2025 (se contiver padrão YYYYMM)

Se não conseguir auto-detectar, o usuário pode informar manualmente na interface.

---

## ⚙️ Processamento de PDFs

### Lógica de Extração de Ações
1. Identifica tabelas no PDF usando `pdfplumber`
2. Localiza o header (linha com "ativo", "quantidade", "preço", etc.)
3. Para cada linha de dados:
   - Ignora linhas vazias
   - Ignora totais/subtotais
   - Extrai: Ativo, Ticker, Quantidade, Preço
   - Calcula Valor = Quantidade × Preço
   - Ignora valores nulos ou zerados

### Lógica de Extração de Dividendos
1. Identifica tabelas no PDF
2. Localiza o header (linha com "data", "ativo", "valor", etc.)
3. Para cada linha de dados:
   - Ignora linhas vazias ou de total
   - Extrai: Data, Ativo, Valor
   - Ignora valores zerados

### Deduplicação Automática
- **Ações**: Remove duplicatas por `(Mês/Ano, Usuário, Ticker)`
- **Dividendos**: Remove duplicatas por `(Mês/Ano, Usuário, Produto, Data, Valor Líquido)`
- Mantém a versão mais recente em caso de duplicatas

---

## 🎯 Casos de Uso

### Caso 1: Importar um extrato mensal
```python
# Importar PDF individual
df_a, df_d = processar_pdf_individual(
    r"C:\Users\hudson\Downloads\Stmt_20251115.pdf",
    usuario="Hudson"
)

# Salvar dados
salvar_acoes_pdf_parquet(df_a)
salvar_dividendos_pdf_parquet(df_d)
```

### Caso 2: Importar todos os extratos de uma pasta
```python
# Processar pasta inteira
df_a, df_d = processar_pasta_pdfs(
    r"C:\Users\hudson\Documents\Statements\2025",
    usuario="Hudson"
)

# Salvar consolidado
salvar_acoes_pdf_parquet(df_a)
salvar_dividendos_pdf_parquet(df_d)
```

### Caso 3: Integração via interface Streamlit
Acessar a aba "Upload PDF Avenue" no app:
1. Selecionar a opção desejada (Individual/Pasta/Usuário)
2. Fornecer as informações necessárias
3. Clicar em "Processar"
4. Revisar os dados extraídos
5. Clicar em "Salvar em Parquet"

---

## 🔍 Troubleshooting

### Problema: "pdfplumber não instalado"
```bash
pip install pdfplumber
```

### Problema: Nenhum dado extraído do PDF
- Verifique se o PDF contém tabelas estruturadas
- Alguns PDFs podem ter layout diferente (fale com o suporte)
- Teste com o arquivo de exemplo primeiro

### Problema: Dados incorretos/incompletos
- Verifique o layout do PDF da Avenue
- Pode ser necessário ajustar a lógica de extração para versões novas

---

## 📄 Constantes e Caminhos

```python
# Caminhos padrão
PDF_UPLOADS_DIR = "uploads/pdf_avenue"
ACOES_PDF_PATH = "data/acoes_avenue.parquet"
DIVIDENDOS_PDF_PATH = "data/dividendos_avenue.parquet"
```

---

## 🧪 Teste com Dados Fictícios

```python
import pandas as pd
from modules.upload_pdf_avenue import salvar_acoes_pdf_parquet

# Criar DataFrame fictício
df_teste = pd.DataFrame({
    "Produto": ["VALE3", "PETR4"],
    "Ticker": ["VALE3", "PETR4"],
    "Código de Negociação": ["VALE3", "PETR4"],
    "Quantidade Disponível": [100, 50],
    "Preço de Fechamento": [54.32, 28.15],
    "Valor": [5432.0, 1407.5],
    "Mês/Ano": ["11/2025", "11/2025"],
    "Usuário": ["Hudson", "Hudson"]
})

# Salvar
salvar_acoes_pdf_parquet(df_teste)
print("✅ Dados de teste salvos!")
```

---

## 📞 Suporte

Para dúvidas ou problemas, consulte o arquivo [modules/upload_pdf_avenue.py](modules/upload_pdf_avenue.py) que contém exemplos adicionais no final do arquivo.

---

## ✅ Status Atual

✅ Módulo criado e testado
✅ Integração ao APP.py realizada
✅ Aba "Upload PDF Avenue" funcionando
✅ Salvamento em Parquet implementado
✅ Deduplicação automática ativa

**Data de Criação:** 3 de janeiro de 2026
