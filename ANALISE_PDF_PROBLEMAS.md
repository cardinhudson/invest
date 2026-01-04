# Análise Profunda da Extração de PDFs Avenue

## Problemas Identificados

### 1. **Estrutura dos PDFs Avenue**
Os PDFs Avenue seguem um formato específico:
- **Página 1**: Cabeçalho com dados da conta e saldo total
- **Páginas 2-3**: PORTFOLIO SUMMARY com layout em colunas: SYMBOL/DESCRIPTION | ACCOUNT TYPE | QUANTITY | PRICE | VALUE | etc.
- **Página 4**: Continuação do portfolio e resumo
- **Página 5+**: Dividendos e transações

### 2. **Problemas Críticos Identificados**

#### 2.1 Extração de Tickers em Ações
**Problema**: Os tickers estão na mesma linha que a descrição, mas o layout é COMPLEXO
- Exemplo: `GLOBAL X FDS DIV C 27.9718 $16.952 $474.18 $480.56 -1% $34 7.226%`
  - Descrição: "GLOBAL X FDS DIV"
  - Account Type: "C" (Custody/Margin)
  - Ticker: Não está explicitamente listado!

**Causa**: O ticket está implícito na descrição. Precisamos MAPEAR a descrição para o ticker correto.

#### 2.2 Extração de Dividendos
**Problema**: Ticker não está localizado facilmente
- Formato atual é confuso e multi-linha
- Linhas seguem padrão: `DIVIDEND 01/26/24 C INVESCO EXCHANGE TRADED FD TR $0.14255 $3.71`
- Descrição do ativo continua em linhas subsequentes

**Causa**: O código tenta encontrar ticker pela próxima linha isolada, mas isso é unreliável.

#### 2.3 Dois Modelos de PDFs
**Diferença**: Hudson Cardin tem 13 páginas vs Giselle com 12
- Mesma estrutura geral
- Possível variação em holdings diferentes (mais ações em Hudson)

### 3. **Valores Incorretos**

#### 3.1 Quantidade
- Alguns valores como `0.2561` (EEM) aparecem corretos na tabela
- Mas podem ser truncados ou mal formatados após extração

#### 3.2 Preço
- Formatação com "$" e "," complica parsing
- Exemplo: `$16.952` vs `21.71` (com/sem $)

#### 3.3 Valor Total
- Calculado como Quantidade × Preço
- Pode divergir da tabela se quantidades estiverem erradas

### 4. **Estrutura de Colunas Esperada**

As colunas que o projeto mantém são:
```
- Produto (nome do ativo)
- Ticker (código da ação/ETF)
- Código de Negociação (duplicado do Ticker)
- Quantidade Disponível
- Preço de Fechamento
- Valor
- Mês/Ano (extraído do nome do arquivo)
- Usuário
- Data de Pagamento (para dividendos)
- Tipo de Provento
- Valor Líquido
```

---

## Solução Proposta

### 1. **Mapper de Descrição para Ticker**
Criar um mapeamento baseado em nomenclatura padrão:
```
GLOBAL X FDS DIV → DGDV (ou SCHD para dividendos globais)
GLOBAL X FDS SDIV → SDIV (superdividendo)
ISHARES CORE S&P 500 ETF → IVV
ISHARES 20 PLUS YEAR TREASURY → TLT
ISHARES IBOXX $ INVESTMENT → LQD
```

### 2. **Melhorar Extração de Tabelas**
- Usar `pdfplumber` com `table_settings` ajustados
- Parser mais robusto para linhas multi-linha
- Identificar colunas por header: SYMBOL, DESCRIPTION, QUANTITY, PRICE, VALUE

### 3. **Estratégia de Divisão por Modelo**
Detectar modelo por:
- Número de páginas
- Estrutura de headers
- Tipo de holding

### 4. **Validação em Tempo Real**
- Verificar se ticker é válido (1-6 caracteres, apenas letras)
- Validar valores numéricos
- Cross-check com portfolio histórico

---

## Arquitetura Proposta

```
upload_pdf_avenue.py (refatorado)
├── Parser Base
│   ├── extract_account_info()
│   ├── extract_date_from_filename()
│   └── normalize_text()
├── Portfolio Parser (Ações)
│   ├── AcoesPdfParser (classe base)
│   ├── PortfolioTableParser (modelo com tabelas)
│   └── PortfolioTextParser (modelo com texto)
├── Dividends Parser
│   ├── DividendoPdfParser (classe base)
│   ├── DividendTableParser
│   └── DividendTextParser
├── Ticker Resolver
│   ├── DescriptionToTickerMapper (mapeamento por descrição)
│   ├── PortfolioLookup (lookup no histórico)
│   └── FuzzyMatcher (matching aproximado)
└── Validators
    ├── validate_ticker()
    ├── validate_quantity()
    └── validate_value()
```

---

## Exemplos de Problemas Específicos

### Linha confusa de ações:
```
ISHARES CORE U S AGGREGATE BD AGG C 3.259 99.10 322.97 323.46 <-1 10 4.922
[    DESCRIÇÃO DO ATIVO    ] [TKR] [ACCOUNT TYPE] [QTD] [PRICE] [VALUE] [...]
```
→ Precisamos extrair: Ticker=AGG, Quantidade=3.259, Preço=99.10, Valor=322.97

### Linha de dividendo sem ticker claro:
```
DIVIDEND 01/26/24 C INVESCO EXCHANGE TRADED FD TR $0.14255 $3.71
II KBW HIGH DIVID YIELD FINL WH 1.11
```
→ O ticker "KBWD" deveria estar isolado em alguma linha ou mapeado pela descrição

