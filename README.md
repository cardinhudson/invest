# 💰 Invest - Controle de Investimentos

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-red)
![Status](https://img.shields.io/badge/Status-Em%20Desenvolvimento-yellow)

---

## 📌 Sobre o projeto

**Invest** é um sistema completo e robusto para controle de investimentos, desenvolvido em **Python** com **Streamlit**, que consolida investimentos brasileiros e internacionais (Avenue) em uma única plataforma.

### ✨ Funcionalidades Principais

#### 📊 **Gestão de Ações**
- ✅ Ações brasileiras (B3)
- ✅ Ações internacionais via Avenue (USD convertido para BRL)
- ✅ Ações consolidadas (Brasil + Avenue)
- ✅ Classificação automática de opções
- ✅ Conversão automática USD → BRL com cotações mensais via yfinance

#### 💵 **Renda Fixa e Tesouro Direto**
- ✅ Gestão de Renda Fixa
- ✅ Gestão de Tesouro Direto
- ✅ Consolidação automática (RF + TD)
- ✅ Classificação automática por tipo de ativo

#### 💸 **Proventos e Dividendos**
- ✅ Dividendos brasileiros com extração de PDF
- ✅ Dividendos Avenue (USD) com conversão automática para BRL
- ✅ Consolidação de dividendos com separação por fonte
- ✅ Extração automática de usuário da coluna Fonte
- ✅ Gráficos de evolução (mensal, bimestral, trimestral, semestral, anual)
- ✅ Top pagadores com filtros avançados
- ✅ Cálculo automático: Valor Líquido = Valor Bruto - Impostos
- ✅ Garantia de impostos sempre negativos

#### 📈 **Análises e Gráficos**
- ✅ Gráficos de distribuição por tipo (pizza)
- ✅ Top 10 ativos por valor (barras)
- ✅ Evolução temporal com múltiplos períodos
- ✅ Crescimento percentual período a período
- ✅ Métricas resumidas por tipo de ativo
- ✅ Filtros padronizados (Mês/Ano, Usuário, Tipo)

#### 🌍 **Integração Avenue Securities**
- ✅ Extração automática de PDFs Avenue (ações e dividendos)
- ✅ Conversão USD → BRL usando cotações mensais do yfinance
- ✅ Cache local de cotações em Parquet
- ✅ Fallback para cotação padrão (5.80) em caso de erro
- ✅ Identificação de data do relatório via nome do arquivo (Stmt_YYYYMMDD.pdf)

#### 🔧 **Recursos Técnicos**
- ✅ Upload e processamento de relatórios Excel/PDF
- ✅ Armazenamento em Parquet para performance
- ✅ Cadastro multiusuário com CPF
- ✅ Interface reorganizada com tabs e subtabs
- ✅ Tabelas em expanders para melhor UX
- ✅ Keys únicas para elementos Streamlit (evita IDs duplicados)  

---

## 🚀 Instalação e execução

### 1. Pré-requisitos
- Python 3.10 ou superior
- pip (gerenciador de pacotes Python)

### 2. Clone o repositório
```bash
git clone https://github.com/seuusuario/invest.git
cd invest
```

### 3. Crie e ative o ambiente virtual
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux/Mac
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Instale as dependências
```bash
pip install -r requirements.txt
```

### 5. Execute o aplicativo
```bash
streamlit run APP.py
```

O aplicativo será aberto automaticamente no navegador em `http://localhost:8501`

---

## 📂 Estrutura do Projeto

```
invest/
│
├── APP.py                      # Aplicação principal reorganizada com tabs
├── APP_BACKUP.py               # Backup automático da versão anterior
├── README.md                   # Documentação do projeto
├── requirements.txt            # Dependências Python
│
├── assets/                     # Recursos estáticos
│   └── (imagens, ícones, etc)
│
├── data/                       # Dados persistidos em Parquet
│   ├── acoes.parquet                   # Ações brasileiras
│   ├── renda_fixa.parquet              # Renda fixa
│   ├── proventos.parquet               # Proventos brasileiros
│   ├── acoes_avenue.parquet            # Ações Avenue
│   ├── dividendos_avenue.parquet       # Dividendos Avenue
│   ├── cotacoes_usd_brl.parquet        # Cache de cotações
│   └── historico_investimentos.parquet # Consolidado
│
├── modules/                    # Módulos de backend
│   ├── __init__.py
│   ├── alerts.py                      # Alertas e projeções financeiras
│   ├── data_processing.py             # Processamento de dados
│   ├── manual_input.py                # Inserção manual
│   ├── market_data.py                 # Dados de mercado
│   ├── upload.py                      # Upload genérico
│   ├── upload_relatorio.py            # Upload e consolidação de relatórios Excel
│   ├── upload_pdf_avenue.py           # Extração de PDFs Avenue
│   ├── avenue_views.py                # Views específicas Avenue
│   ├── cotacoes.py                    # Conversão USD/BRL
│   └── usuarios.py                    # Gestão de usuários
│
├── src/
│   └── modules/
│       └── alerts.py                  # Alertas avançados
│
└── uploads/                    # PDFs temporários (ignorado no git)
```

---

## 🎯 Organização da Interface (APP.py)

A interface possui **5 tabs principais** com **subtabs**:

### 📈 **1. Ações**
- **Ações BR**: Ações brasileiras (B3)
- **Ações Dólar (Avenue)**: Ações internacionais
- **Ações Consolidadas**: Brasil + Avenue unificados

### 💵 **2. Renda Fixa**
- **Renda Fixa**: Investimentos de renda fixa
- **Tesouro Direto**: Títulos do Tesouro
- **Renda Fixa Consolidada**: RF + TD unificados

### 💸 **3. Proventos**
- **Dividendos BR**: Proventos brasileiros
- **Dividendos Avenue**: Proventos Avenue
- **Dividendos Consolidados**: Todos os proventos unificados

### 📊 **4. Consolidação**
- **Consolidação Geral**: Une todos os investimentos (BR + Avenue) em uma visão única com filtros, métricas e gráficos de distribuição.

### ⚙️ **5. Outros**
- **Cadastro**: Gestão de usuários
- **Inserção Manual**: Entrada manual de dados

---

## 🔑 Funcionalidades Detalhadas

### 📊 Filtros Padronizados

Todas as tabelas possuem filtros consistentes:
- **Mês/Ano**: Selecionar período específico
- **Usuário**: Filtrar por investidor
- **Tipo**: Filtrar por categoria de ativo (quando aplicável)

### 💱 Conversão de Moedas (USD → BRL)

O sistema implementa conversão automática usando:
1. **yfinance**: Busca cotação USD/BRL do mês específico
2. **Cache local**: Armazena cotações em `cotacoes_usd_brl.parquet`
3. **Fallback**: Usa cotação padrão (5.80) em caso de erro
4. **Granularidade**: Cotação específica por mês/ano

**Aplicado em:**
- Ações Avenue (Valor e Preço)
- Dividendos Avenue (Valor Bruto, Impostos, Valor Líquido)

### 📄 Extração de PDFs Avenue

**Padrão de arquivo**: `Stmt_YYYYMMDD.pdf` (ex: `Stmt_20251130.pdf`)

**Dados extraídos de Ações:**
- Produto (Nome do ativo)
- Ticker
- Quantidade Disponível
- Preço de Fechamento
- Valor de Mercado
- Mês/Ano (extraído do nome do arquivo)

**Dados extraídos de Dividendos:**
- Data de Pagamento
- Ticker
- Valor Bruto
- Impostos (sempre negativos)
- Valor Líquido (Bruto - Impostos)
- Mês/Ano (extraído do nome do arquivo)

### 📊 Gráficos Disponíveis

**1. Distribuição por Tipo (Pizza)**
- Mostra percentual por tipo de ativo
- Valores em R$ e percentual
- Cores temáticas por categoria

**2. Top 10 Ativos (Barras)**
- Maiores posições por valor
- Ordenado decrescente
- Rótulos com valores formatados

**3. Evolução de Proventos**
- Períodos: Mensal, Bimestral, Trimestral, Semestral, Anual
- Gráfico de barras com valores
- Gráfico de linha com tendência
- Gráfico de crescimento percentual

**4. Top Pagadores de Dividendos**
- Seleção de período (Mensal/Anual)
- Top 5, 10, 15, 20 ou 25
- Tabela detalhada com valores

---

## 🗂️ Padronização de Colunas

### Ações (Brasil e Avenue)
| Coluna Original | Coluna Padronizada |
|----------------|-------------------|
| Produto | Ativo |
| Código de Negociação | Ticker |
| Quantidade | Quantidade Disponível |
| Preço de Fechamento | Preço |
| Valor Atualizado / Valor de Mercado | Valor |

### Dividendos (Brasil e Avenue)
| Coluna | Descrição |
|--------|-----------|
| Data | Data de pagamento |
| Ativo | Nome do ativo/ticker |
| Valor Bruto | Valor antes de impostos |
| Impostos | Impostos retidos (sempre negativo) |
| Valor Líquido | Valor Bruto - Impostos |
| Fonte Provento | "Proventos Gerais" ou "Proventos Avenue" |
| Usuário | Extraído da coluna Fonte (sem data) |
| Mês/Ano | Período de referência |

### Classificação Automática

**Opções de Compra/Venda:**
- Detecta por palavras-chave: "opção de compra", "opcao", etc
- Tipo: "Opções"
- Excluídas automaticamente da consolidação

**Tesouro Direto:**
- Detecta por palavras-chave: "tesouro", "ltn", "ntn", "selic", "ipca+", etc
- Tipo: "Tesouro Direto"

**Ações Dólar (Avenue):**
- Tipo: "Ações Dólar"
- Fonte: "Avenue"

---

## 🛠️ Módulos Principais

### `upload_relatorio.py`
- Processamento de relatórios Excel mensais
- Detecção automática de sheets (Ações, Renda Fixa, Proventos)
- Padronização de colunas
- Extração de Mês/Ano do nome do arquivo
- Classificação automática por tipo

### `upload_pdf_avenue.py`
- Extração de dados de PDFs Avenue
- Parsing de tabelas com pdfplumber
- Extração de data do nome do arquivo
- Processamento em lote de múltiplos PDFs

### `cotacoes.py`
- Conversão USD → BRL
- Cache de cotações em Parquet
- Integração com yfinance
- Sistema de fallback para erros

### `avenue_views.py`
- Funções de padronização Avenue
- Abas específicas de Ações e Proventos Avenue
- Interface de upload de PDFs
- Visualizações e métricas

### `usuarios.py`
- Cadastro de investidores
- Armazenamento em Parquet
- Gestão de CPFs

---

## 📝 Dependências Principais

```txt
streamlit>=1.28.0
pandas>=2.0.0
plotly>=5.14.0
yfinance>=0.2.0
pdfplumber>=0.10.0
openpyxl>=3.1.0
```

---

## 🎨 Boas Práticas Implementadas

1. **Keys únicas em elementos Streamlit** - Evita IDs duplicados
2. **Funções reutilizáveis** - `aplicar_filtros_padrao()`, `gerar_graficos_distribuicao()`
3. **Expanders para tabelas** - Melhor UX, menos rolagem
4. **Métricas resumidas** - Informações rápidas no topo
5. **Conversão de moedas confiável** - Cache + fallback
6. **Processamento robusto** - Tratamento de erros e validações
7. **Backup automático** - APP_BACKUP.py criado antes de mudanças
8. **Documentação inline** - Docstrings em todas as funções

---

## 🔄 Fluxo de Dados

```
1. Upload Excel/PDF → 2. Extração/Parsing → 3. Padronização
                                                       ↓
6. Exibição ← 5. Filtros ← 4. Armazenamento Parquet ←
```

**Detalhamento:**
1. Usuário faz upload de arquivos
2. Sistema extrai dados (pdfplumber para PDF, pandas para Excel)
3. Padronização de colunas e classificação automática
4. Salva em arquivos Parquet para performance
5. Aplica filtros selecionados pelo usuário
6. Exibe tabelas, gráficos e métricas

---

## 🚧 Desenvolvimento Futuro

- [ ] Integração com mais corretoras
- [ ] Alertas por e-mail/WhatsApp
- [ ] Análise de performance por ativo
- [ ] Comparação com benchmarks (Ibovespa, CDI)
- [ ] Projeções de dividendos futuros
- [ ] Export de relatórios em PDF
- [ ] Dashboard executivo
- [ ] Análise de concentração de carteira
- [ ] Cálculo de IR automático

---

## 📞 Suporte e Contribuições

Para reportar bugs ou sugerir melhorias, abra uma issue no repositório.

---

## 📄 Licença

Este projeto está sob licença MIT. Veja o arquivo LICENSE para mais detalhes.

---

**Desenvolvido com ❤️ usando Python + Streamlit**
