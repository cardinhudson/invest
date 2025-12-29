# 💰 Invest - Controle de Investimentos

![Python](https://img.shields.io/badge/Python-3.10-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-red)
![Status](https://img.shields.io/badge/Status-Em%20Desenvolvimento-yellow)

---

## 📌 Sobre o projeto
**Invest** é um sistema completo para controle de investimentos, desenvolvido em **Python** com **Streamlit**, que permite:

✅ Cadastro de pessoas (multi-CPF)  
✅ Inserção manual de investimentos  
✅ Upload de CSV com validação  
✅ Conversão automática de moedas  
✅ Gráficos interativos (Plotly)  
✅ Histórico de dividendos (via yfinance)  
✅ Evolução histórica (últimos 5 anos)  
✅ Comparações com benchmarks (Ibovespa, CDI, dólar)  
✅ Alertas e projeções financeiras avançadas  

---

## 🚀 Instalação e execução

### 1. Clone o repositório
```bash
git clone https://github.com/seuusuario/invest.git
cd invest
```

---

## 📂 Estrutura de Pastas

```
invest/
│
├── app.py                  # Interface principal do Streamlit (ponto de entrada)
├── README.md
├── requirements.txt
├── assets/                 # Imagens e ícones
├── data/                   # Arquivos Parquet e dados consolidados
├── modules/                # Módulos de backend (importados pelas páginas)
│   ├── upload_relatorio.py     # Upload e consolidação de relatórios Excel
│   ├── __init__.py
├── pages/                  # Páginas do Streamlit (aparecem no menu lateral)
│   ├── Upload_Relatorio.py     # Página de upload e download do histórico consolidado
└── venv/ ou .venv/         # Ambiente virtual Python
```

**Observações:**
- Para adicionar novas páginas, basta criar arquivos Python na pasta `pages/`.
- Para adicionar novos módulos de backend, utilize a pasta `modules/`.
- O histórico consolidado dos relatórios mensais é salvo automaticamente em `data/historico_investimentos.parquet`.
- O comando para rodar o sistema é:
	```bash
	streamlit run app.py
	```

---

## 📝 Exemplo de uso (app.py)

```python
import streamlit as st
import pandas as pd
import os
from modules.usuarios import carregar_usuarios, salvar_usuarios
from modules.upload_relatorio import carregar_historico_parquet

# =========================
# Inicialização dos dados
# =========================
df_usuarios = carregar_usuarios()
df = carregar_historico_parquet()

# =========================
# Cadastro de Usuários
# =========================
st.sidebar.header("Cadastro de Usuários")
nome = st.sidebar.text_input("Nome do usuário")
cpf = st.sidebar.text_input("CPF")
if st.sidebar.button("Adicionar Usuário"):
	if nome and cpf:
		novo_usuario = pd.DataFrame([{"Nome": nome, "CPF": cpf}])
		df_usuarios = pd.concat([df_usuarios, novo_usuario], ignore_index=True).drop_duplicates()
		salvar_usuarios(df_usuarios)
		st.sidebar.success(f"{nome} adicionado!")
	else:
		st.sidebar.error("Preencha todos os campos.")
st.sidebar.subheader("Usuários cadastrados")
st.sidebar.table(df_usuarios)

# =========================
# Filtros dos Investimentos
# =========================
st.title("💰 Invest - Controle de Investimentos")

if not df.empty:
	usuarios = ["Todos"] + sorted(df_usuarios["Nome"].unique())
	usuario_selecionado = st.selectbox("Filtrar por usuário", usuarios)

	categorias = ["Todas"] + sorted(df["Tipo"].dropna().unique())
	categoria_selecionada = st.selectbox("Filtrar por categoria", categorias)

	acoes = ["Todas"] + sorted(df["Código de Negociação"].dropna().unique())
	acao_selecionada = st.selectbox("Filtrar por ação", acoes)

	df_filtrado = df.copy()
	if usuario_selecionado != "Todos":
		df_filtrado = df_filtrado[df_filtrado["Usuário"] == usuario_selecionado]
	if categoria_selecionada != "Todas":
		df_filtrado = df_filtrado[df_filtrado["Tipo"] == categoria_selecionada]
	if acao_selecionada != "Todas":
		df_filtrado = df_filtrado[df_filtrado["Código de Negociação"] == acao_selecionada]

	st.metric("Total dos Investimentos", f"R$ {df_filtrado['Valor Atualizado'].sum():,.2f}")
	st.dataframe(df_filtrado)

	# =========================
	# Gráfico de Evolução por Período
	# =========================
	st.header("Evolução do Patrimônio")
	periodos = ["Mensal", "Bimestral", "Trimestral", "Semestral", "Anual"]
	periodo = st.selectbox("Período", periodos)

	df_filtrado["Data"] = pd.to_datetime(df_filtrado["Mês/Ano"], format="%m/%Y")
	if periodo == "Mensal":
		df_group = df_filtrado.groupby([df_filtrado["Data"].dt.to_period("M")])["Valor Atualizado"].sum()
	elif periodo == "Bimestral":
		df_group = df_filtrado.groupby([df_filtrado["Data"].dt.to_period("2M")])["Valor Atualizado"].sum()
	elif periodo == "Trimestral":
		df_group = df_filtrado.groupby([df_filtrado["Data"].dt.to_period("Q")])["Valor Atualizado"].sum()
	elif periodo == "Semestral":
		df_group = df_filtrado.groupby([df_filtrado["Data"].dt.to_period("6M")])["Valor Atualizado"].sum()
	elif periodo == "Anual":
		df_group = df_filtrado.groupby([df_filtrado["Data"].dt.year])["Valor Atualizado"].sum()

	st.line_chart(df_group)

else:
	st.info("Nenhum dado consolidado encontrado. Faça upload de relatórios na página apropriada.")

# =========================
# Busca de Tickers do Mercado
# =========================
st.header("Buscar Ticker do Mercado")
ticker_input = st.text_input("Digite o ticker para buscar (ex: PETR4.SA)")
if ticker_input:
	import yfinance as yf
	try:
		ticker = yf.Ticker(ticker_input)
		hist = ticker.history(period="5y")
		st.write(hist)
		st.line_chart(hist["Close"])
	except Exception as e:
		st.error(f"Erro ao buscar ticker: {e}")

# =========================
# Sugestões de Tickers (Autocompletar)
# =========================
if not df.empty:
	tickers = sorted(df["Código de Negociação"].dropna().unique())
	if ticker_input:
		suggestions = [t for t in tickers if ticker_input.upper() in t.upper()]
		if suggestions:
			st.write("Sugestões:", suggestions)
```

**Onde salvar os arquivos:**
- Salve o código acima como `app.py` na raiz do projeto.
- O módulo `usuarios.py` deve estar em `modules/`.
- O módulo `upload_relatorio.py` deve estar em `modules/`.
- Os arquivos Parquet serão salvos automaticamente na pasta `data/`.
