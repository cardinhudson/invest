import streamlit as st
import os
import pandas as pd
from datetime import datetime

try:
    from modules.upload_relatorio import ACOES_PATH, RENDA_FIXA_PATH, PROVENTOS_PATH
    tem_upload_relatorio = True
except:
    tem_upload_relatorio = False

st.set_page_config(page_title="Documentação - Invest", page_icon="📚", layout="wide")

# Função para obter mês atual em português
def obter_mes_atual():
    """Retorna o mês atual em português"""
    meses = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }
    agora = datetime.now()
    return meses[agora.month]

# Cabeçalho compacto
mes_atual = obter_mes_atual()
ano_atual = datetime.now().year
versao_atual = "1.0.0"

st.markdown(f"""
<div style='display: flex; justify-content: space-between; align-items: center; color: #fff; padding: 8px 10px; font-size: 0.85rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-bottom: 1px solid #5a4fcf; margin-bottom: 10px;'>
    <div style='flex: 1;'>📚 Documentação Completa do Invest | Versão {versao_atual} | {mes_atual} {ano_atual}</div>
</div>
""", unsafe_allow_html=True)

# CSS para melhorar visualização
st.markdown("""
    <style>
        h1 {
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        .stTabs [data-baseweb="tab"] {
            padding: 10px 20px;
            font-weight: 600;
        }
    </style>
""", unsafe_allow_html=True)

st.title("📚 Documentação Completa do Sistema Invest")

# Sidebar com índices
st.sidebar.markdown("## 📑 Índice")
st.sidebar.markdown("---")

# Criar índices no sidebar
indice_selecionado = st.sidebar.radio(
    "Selecione a seção:",
    [
        "🏠 Visão Geral",
        "🔁 Atualização de Cotações (Posição Atual)",
        "🧮 Cálculos e Metodologias",
        "🗄️ Cache e Persistência",
        "🏗️ Arquitetura e Estrutura",
        "📊 Módulos do Projeto",
        "💾 Banco de Dados",
        "👨‍💻 Guia de Desenvolvimento",
        "🚀 Como Começar",
        "📋 FAQ"
    ] + (["📥 Upload de Relatórios"] if tem_upload_relatorio else []),
    key="indice_documentacao"
)

st.markdown("---")

# ==========================================
# SEÇÃO 1: VISÃO GERAL
# ==========================================
if indice_selecionado == "🏠 Visão Geral":
    st.header("🏠 Visão Geral do Projeto")
    
    st.markdown("""
    **Invest** é um sistema completo de controle e análise de investimentos desenvolvido em Python com Streamlit.
    O projeto oferece funcionalidades avançadas para gerenciar portfólios, acompanhar evolução histórica,
    receber alertas e fazer projeções financeiras.
    """)
    
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📦 Versão", "1.0.0")
    
    with col2:
        st.metric("🐍 Python", "3.13+")
    
    with col3:
        st.metric("📅 Data", datetime.now().strftime("%d/%m/%Y"))
    
    st.markdown("---")
    
    st.subheader("✨ Principais Características")
    
    features = {
        "👥 Multi-Usuário": "Cadastre múltiplas pessoas com seus respectivos investimentos",
        "💰 Múltiplas Moedas": "Suporte para BRL, USD, EUR e conversão automática",
        "📈 Análise Histórica": "Acompanhe a evolução dos preços dos últimos 5 anos",
        "🎯 Alertas Inteligentes": "Receba notificações quando atingir metas de preço",
        "📊 Gráficos Interativos": "Visualize dados com Plotly em tempo real",
        "📥 Upload de CSV": "Importe dados de investimentos em lote",
        "🔮 Projeções Financeiras": "Calcule rentabilidade futura com aportes mensais",
        "🏆 Comparações": "Comparar seu portfólio com Ibovespa, Dólar e CDI"
    }
    
    cols = st.columns(2)
    for idx, (titulo, descricao) in enumerate(features.items()):
        with cols[idx % 2]:
            st.write(f"**{titulo}**")
            st.write(descricao)
    
    st.markdown("---")

    st.subheader("🧭 Abas da Interface")
    st.markdown("""
    - **📈 Ações**: Ações BR, Ações Dólar (Avenue) e Ações Consolidadas (BR + Avenue).
    - **💵 Renda Fixa**: Renda Fixa, Tesouro Direto e Renda Fixa Consolidada.
    - **💸 Proventos**: Dividendos BR, Dividendos Avenue e Dividendos Consolidados.
    - **📊 Consolidação**: Visão única com todos os investimentos combinados (BR + Avenue) com:
        - **Investimento**: Filtros, métricas e gráficos de distribuição por tipo, setor e ativo.
        - **Rentabilidade**: Análise mensal de retorno por ativo usando quantidade do mês anterior (metodologia "sem aportes").
    - **📊 Análise Fundamentalista**: Página dedicada a indicadores e demonstrativos via `yfinance`.
        - **Periodicidade**: permite visualizar indicadores em **Mensal / Trimestral / Anual**.
        - **Trimestral vs Anual (regra de prioridade)**: quando há dados trimestrais, o app usa o **relatório trimestral**; o **anual entra apenas como preenchimento** dos períodos onde não existe dado trimestral (ex.: anos antigos/linhas ausentes). Ou seja: **trimestral sempre prevalece**.
        - **Projeção do período atual**: adiciona um ponto de **projeção** (mês atual / ano atual) recalculando apenas métricas dependentes do preço (ex.: **P/L, P/VP, Dividend Yield**) usando o **preço mais recente** e o **último resultado disponível** (preferência: trimestral).
        - **Somente tickers válidos**: opção para filtrar listas/seleções e exibir somente tickers realmente existentes no Yahoo Finance (validação em lote com cache para performance).
        - **Dividendos (datas futuras)**: exibe, quando disponível, uma tabela com **Ex-Dividend Date** e **Dividend Date** do `yfinance`.
    - **⚙️ Outros**: Cadastro de usuários e Inserção Manual.
    """)
    
    st.subheader("🎯 Objetivos do Projeto")
    st.markdown("""
    1. **Centralizar Investimentos**: Gerenciar todos os investimentos em um único lugar
    2. **Análise Inteligente**: Fornecer insights sobre desempenho e comparações com benchmarks
    3. **Facilitar Decisões**: Projetar rentabilidade futura para planejamento financeiro
    4. **Monitorar Oportunidades**: Alertar quando preços-alvo são atingidos
    5. **Acompanhar Dividendos**: Registrar e acompanhar histórico de dividendos recebidos
    """)

# ==========================================
# SEÇÃO: ATUALIZAÇÃO DE COTAÇÕES (POSIÇÃO ATUAL)
# ==========================================
elif indice_selecionado == "🔁 Atualização de Cotações (Posição Atual)":
        st.header("🔁 Atualização de Cotações (Posição Atual)")

        st.markdown("""
        Esta seção explica **como funciona a aba 📌 Posição Atual**, o que o botão **Atualizar cotações** faz,
        e como o sistema garante que tabelas e gráficos reflitam os dados mais recentes.
        """)

        st.subheader("✅ O que o botão faz")
        st.markdown("""
        Ao clicar em **Atualizar cotações** o app:
        1. **Força** a atualização no `st.session_state`.
        2. **Limpa o cache** do Streamlit via `st.cache_data.clear()`.
        3. Executa um `st.rerun()` para reprocessar a página na mesma hora.

        Isso evita o cenário clássico do Streamlit onde o usuário clica, mas o script não reexecuta e nada muda.
        """)

        st.subheader("📦 De onde vem o preço (yfinance)")
        st.markdown("""
        A atualização utiliza o `yfinance` para buscar:
        - **Preço Atual** (preferencialmente `regularMarketPrice` / `currentPrice`).
        - **Preço Anterior** (preferencialmente `previousClose`).
        - **Variação % do dia** (preferencialmente `regularMarketChangePercent`).

        Fallbacks (quando um campo não está disponível):
        - Usa histórico de **5 dias** para estimar `Preço Atual` e `Preço Anterior` via `Close`.
        - Calcula `Variação %` como $(PreçoAtual / PreçoAnterior - 1) \times 100$.
        """)

        st.subheader("🧾 Onde está o código")
        st.markdown("""
        - Atualização e cálculo de colunas: `modules/posicao_atual.py` → `atualizar_cotacoes()`
        - Preparação da base para atualização (ticker/quantidade/valor base): `modules/posicao_atual.py` → `preparar_posicao_base()`
        - Botão e fluxo de atualização na UI: `APP.py` (aba 📌 Posição Atual)
        """)

        st.subheader("🧠 Como interpretar as colunas")
        st.markdown("""
        - **Preço Atual**: cotação atual em BRL (para Ações Dólar, converte USD→BRL com câmbio atual).
        - **Preço Anterior**: referência do dia (normalmente o fechamento anterior).
        - **Variação %**: percentual do dia (yfinance ou cálculo por fallback).
        - **Valor Atualizado**: valor atual da posição (detalhes na seção de cálculos).
        - **Fonte Preço**: indica se veio do `yfinance` ou de fallback (histórico/base).
        """)

        st.subheader("🆘 Dicas de troubleshooting")
        st.markdown("""
        Se o preço atual mudar mas a **Variação %** não:
        - Verifique se o yfinance está retornando `previousClose` / `regularMarketChangePercent`.
        - Em horários fora de pregão, é comum a variação refletir o último fechamento.
        - O botão já limpa o cache; se persistir, reinicie o Streamlit para zerar estado de sessão.
        """)

# ==========================================
# SEÇÃO: CÁLCULOS E METODOLOGIAS
# ==========================================
elif indice_selecionado == "🧮 Cálculos e Metodologias":
        st.header("🧮 Cálculos e Metodologias")

        st.markdown("""
        Esta seção centraliza as **regras de cálculo** usadas nos painéis, para facilitar manutenção e reprocessamento.
        """)

        st.subheader("💰 Valor Atualizado (Posição Atual)")
        st.markdown("""
        Para cada linha da posição atual:

        - Se o ativo é **Ações** / **Ações Dólar**:
            $$ValorAtualizado = Quantidade \times PreçoAtual$$

        - Para demais tipos (ex.: RF, TD, caixa, etc.):
            - Mantém o **Valor Base** do mês.
            - Se a moeda for USD, converte para BRL com USD/BRL atual.
        """)

        st.subheader("📈 Variação % do dia (Posição Atual)")
        st.markdown("""
        A variação do dia é priorizada da seguinte forma:
        1. Se o yfinance fornece `regularMarketChangePercent`, usa esse valor.
        2. Senão, calcula usando `Preço Atual` e `Preço Anterior`:
             $$Varia\u00e7\u00e3o\% = (PreçoAtual / PreçoAnterior - 1) \times 100$$

        Observação: isso representa a variação **do dia (D-1 → D)**, não a variação vs preço histórico mensal.
        """)

        st.subheader("🏆 Maiores Altas/Baixas (Top 10)")
        st.markdown("""
        O painel Top 10 usa os ativos com posição e ordena pela variação do dia.

        - Quando possível, também estima o **Ganho/Perda no dia (R$)** a partir do % e do valor atual da posição.
            Ideia: se um ativo subiu $p\%$ e o valor atual é $V$, então o valor base aproximado é $V/(1+p)$,
            e o ganho aproximado é $V - V/(1+p)$.
        """)

        st.subheader("📊 Distribuição")
        st.markdown("""
        Gráficos de distribuição somam valores por dimensões (Tipo/Setor/Ativo etc.) e exibem pizza/barras.
        A base normalmente é a coluna **Valor** (que no painel de Posição Atual vem de `Valor Atualizado`).
        """)

        st.subheader("📈 Gráficos de Proventos (média móvel)")
        st.markdown("""
        No gráfico de barras de proventos, existe uma opção de **média móvel** (3/6/9/12 meses).
        A média móvel é calculada com `rolling(window, min_periods=1, center=False)` para:
        - Começar desde o início (sem buracos)
        - Ir até a última barra (sem encerrar antes)
        """)

# ==========================================
# SEÇÃO: CACHE E PERSISTÊNCIA
# ==========================================
elif indice_selecionado == "🗄️ Cache e Persistência":
        st.header("🗄️ Cache e Persistência")

        st.markdown("""
        O projeto usa duas camadas de “cache”:
        - **Memória (Streamlit)**: `st.cache_data` e `st.session_state`
        - **Disco (Parquet/arquivos)**: dados persistidos em `data/` e relatórios em `Relatorios/`
        """)

        st.subheader("🧠 Cache em memória (Streamlit)")
        st.markdown("""
        - `st.session_state`: guarda dataframes e sinais de atualização para evitar recomputar em toda interação.
        - `st.cache_data`: cacheia funções puras/sem estado (ex.: leitura de parquet, requests) para performance.

        Importante: o botão **Atualizar cotações** chama `st.cache_data.clear()`.
        Isso garante que funções cacheadas não devolvam resultados antigos quando o usuário deseja atualizar.
        """)

        st.subheader("💾 Persistência em disco")
        st.markdown("""
        - Dados consolidados e caches de apoio são gravados em `data/` (principalmente `.parquet`).
        - PDFs e relatórios importados podem ficar em `uploads/` e `Relatorios/` (dependendo do fluxo).

        Boa prática: sempre que mudar a estrutura de colunas, validar se os parquets antigos ainda são compatíveis.
        """)

# ==========================================
# SEÇÃO 2: ARQUITETURA E ESTRUTURA
# ==========================================
elif indice_selecionado == "🏗️ Arquitetura e Estrutura":
    st.header("🏗️ Arquitetura e Estrutura do Projeto")
    
    st.markdown("""
    O projeto segue uma arquitetura modular bem organizada para facilitar manutenção e escalabilidade.
    """)
    
    st.markdown("---")
    
    st.subheader("📁 Estrutura de Diretórios")
    
    st.code("""
invest/
│
├── APP.py                         # Aplicação Streamlit principal (entrada)
├── requirements.txt               # Dependências do projeto
├── README.md                      # Documentação geral
├── LEIA_PRIMEIRO.txt              # Guia (PDFs Avenue e documentação associada)
│
├── pages/                         # Páginas Streamlit (multi-page)
│   ├── Upload_Relatorio.py
│   ├── Indicadores_Mercado.py
│   ├── Debug_Excel.py
│   └── Sobre_o_Projeto.py          # Esta página (documentação)
│
├── modules/                       # Backend principal (processamento, upload, cotações)
│   ├── upload_relatorio.py         # Upload/consolidação de relatórios Excel
│   ├── upload_pdf_avenue_*.py      # Parsers de PDFs Avenue
│   ├── cotacoes.py                 # USD/BRL e utilitários de câmbio
│   ├── posicao_atual.py            # Atualização em tempo real (yfinance) + cálculos
│   ├── ticker_info.py              # Cache local de informações de tickers (parquet)
│   ├── usuarios.py                 # Gestão de usuários
│   └── ...
│
├── data/                          # Persistência/cache local (parquet/json/uploads)
│   ├── uploads/
│   └── rentabilidade_base_meta.json
│
├── Relatorios/                    # Relatórios organizados por usuário/fonte
├── uploads/                       # PDFs temporários (ex.: uploads/pdf_avenue)
├── assets/                        # Recursos estáticos
└── src/                           # Código auxiliar/legado (espelho e módulos antigos)
    """, language="text")
    
    st.markdown("---")
    
    st.subheader("🔄 Fluxo de Dados")
    
    st.markdown("""
    ```
    Entrada de Dados
         ↓
    ┌─────────────────────────┐
    │ Manual | CSV | Mercado  │
    └────────────┬────────────┘
                 ↓
    ┌─────────────────────────┐
    │  data_processing.py     │ ← Normalização e conversão
    │  - Consolidação         │
    │  - Conversão de moedas  │
    │  - Cálculos             │
    └────────────┬────────────┘
                 ↓
    ┌─────────────────────────┐
    │  market_data.py         │ ← Integração com yfinance
    │  - Preços históricos    │
    │  - Benchmarks           │
    │  - Indicadores          │
    └────────────┬────────────┘
                 ↓
    ┌─────────────────────────┐
    │  alerts.py              │ ← Análise e alertas
    │  - Projeções            │
    │  - Alertas de preço     │
    │  - Notificações         │
    └────────────┬────────────┘
                 ↓
         Visualização UI
    ```
    """)

# ==========================================
# SEÇÃO 3: MÓDULOS DO PROJETO
# ==========================================
elif indice_selecionado == "📊 Módulos do Projeto":
    st.header("📊 Módulos do Projeto")
    
    st.markdown("""
    Cada módulo é responsável por uma funcionalidade específica do sistema.
    """)
    
    st.markdown("---")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 data_processing",
        "💹 market_data",
        "🎯 alerts",
        "📥 upload",
        "✏️ manual_input"
    ])
    
    with tab1:
        st.subheader("📈 data_processing.py")
        st.markdown("""
        **Responsabilidades:**
        - Consolidação de investimentos
        - Conversão de moedas (BRL, USD, EUR)
        - Cálculo de evolução histórica
        - Cálculo de dividendos acumulados
        - Projeções simples com juros compostos
        
        **Principais Funções:**
        """)
        
        functions_data = {
            "consolidar_investimentos()": "Converte lista de investimentos em DataFrame com valores em BRL",
            "converter_para_brl()": "Converte valores de outras moedas para Real",
            "calcular_evolucao_historica()": "Retorna evolução de preços dos últimos 5 anos",
            "calcular_dividendos()": "Retorna histórico de dividendos de um ativo",
            "calcular_projecao()": "Calcula valor futuro com aportes mensais"
        }
        
        for func, desc in functions_data.items():
            st.write(f"**`{func}`** - {desc}")
    
    with tab2:
        st.subheader("💹 market_data.py")
        st.markdown("""
        **Responsabilidades:**
        - Integração com yfinance
        - Busca de preços históricos
        - Obtenção de dados do Ibovespa
        - Cotação do Dólar
        - Taxa CDI
        
        **Principais Funções:**
        """)
        
        functions_market = {
            "buscar_precos_historicos()": "Retorna preços ajustados dos últimos X anos",
            "buscar_ibovespa()": "Retorna histórico do índice Ibovespa",
            "buscar_dolar()": "Retorna histórico da cotação USD/BRL",
            "buscar_cdi()": "Retorna taxa CDI anual simulada"
        }
        
        for func, desc in functions_market.items():
            st.write(f"**`{func}`** - {desc}")
    
    with tab3:
        st.subheader("🎯 alerts.py")
        st.markdown("""
        **Responsabilidades:**
        - Verificação de preço-alvo
        - Detecção de pagamento de dividendos
        - Cálculo de projeção avançada
        - Geração de alertas
        
        **Principais Funções:**
        """)
        
        functions_alerts = {
            "verificar_preco_alvo()": "Verifica se preço atual atingiu o alvo",
            "verificar_dividendos()": "Detecta se houve pagamento recente de dividendos",
            "calcular_projecao_avancada()": "Calcula projeção com aportes mensais e juros compostos"
        }
        
        for func, desc in functions_alerts.items():
            st.write(f"**`{func}`** - {desc}")
    
    with tab4:
        st.subheader("📥 upload.py")
        st.markdown("""
        **Responsabilidades:**
        - Validação de arquivos CSV
        - Verificação de colunas obrigatórias
        - Importação em lote de investimentos
        
        **Principais Funções:**
        """)
        
        functions_upload = {
            "validar_csv()": "Verifica se CSV contém colunas obrigatórias",
            "importar_csv()": "Lê CSV e retorna lista de dicionários"
        }
        
        for func, desc in functions_upload.items():
            st.write(f"**`{func}`** - {desc}")
        
        st.markdown("**Formato esperado do CSV:**")
        df_exemplo = pd.DataFrame({
            "Pessoa": ["João", "Maria"],
            "Produto": ["PETR4", "VALE3"],
            "Categoria": ["Ações", "Ações"],
            "Valor": [1000.00, 2000.00],
            "Moeda": ["BRL", "BRL"]
        })
        st.dataframe(df_exemplo, use_container_width=True)
    
    with tab5:
        st.subheader("✏️ manual_input.py")
        st.markdown("""
        **Responsabilidades:**
        - Entrada manual de investimentos
        - Validação de dados
        - Armazenamento em cache
        
        **Status:** Módulo a ser implementado
        """)

# ==========================================
# SEÇÃO 4: BANCO DE DADOS
# ==========================================
elif indice_selecionado == "💾 Banco de Dados":
    st.header("💾 Armazenamento de Dados")
    
    st.markdown("""
    O projeto utiliza diferentes formas de armazenamento de dados.
    """)
    
    st.markdown("---")
    
    st.subheader("📂 Tipos de Armazenamento")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Em Desenvolvimento (Session State)**")
        st.markdown("""
        - Pessoas cadastradas
        - Investimentos adicionados
        - Estado temporário da UI
        - Dados em memória durante a sessão
        """)
    
    with col2:
        st.markdown("**Externos (APIs)**")
        st.markdown("""
        - Preços: Yahoo Finance (yfinance)
        - Dividendos: yfinance
        - Câmbio: forex-python
        - Moedas: Conversão em tempo real
        """)
    
    st.markdown("---")
    
    st.subheader("🗂️ Estrutura de Dados")
    
    st.markdown("**Investimento (Dicionário)**")
    st.code("""
{
    "Pessoa": "João Silva",
    "Produto": "PETR4",
    "Categoria": "Ações",
    "Valor": 1500.00,
    "Moeda": "BRL"
}
    """, language="python")
    
    st.markdown("**Pessoa (Dicionário)**")
    st.code("""
{
    "Nome": "João Silva",
    "CPF": "123.456.789-00"
}
    """, language="python")

# ==========================================
# SEÇÃO 5: GUIA DE DESENVOLVIMENTO
# ==========================================
elif indice_selecionado == "👨‍💻 Guia de Desenvolvimento":
    st.header("👨‍💻 Guia de Desenvolvimento")
    
    st.markdown("""
    Instruções para desenvolvedores que desejam contribuir ou modificar o projeto.
    """)
    
    st.markdown("---")
    
    st.subheader("🔧 Ferramentas Necessárias")
    
    tools = {
        "Python": "3.13 ou superior",
        "pip": "Gerenciador de pacotes",
        "Virtual Environment": "Isolamento de dependências",
        "Git": "Controle de versão"
    }
    
    for tool, desc in tools.items():
        st.write(f"- **{tool}**: {desc}")
    
    st.markdown("---")
    
    st.subheader("📦 Dependências Principais")
    
    deps = {
        "streamlit": "Framework web para UI",
        "pandas": "Manipulação de dados",
        "numpy": "Cálculos numéricos",
        "yfinance": "Dados de mercado",
        "plotly": "Gráficos interativos",
        "forex-python": "Conversão de moedas",
        "requests": "Requisições HTTP"
    }
    
    for dep, desc in deps.items():
        st.write(f"- **{dep}**: {desc}")
    
    st.markdown("---")
    
    st.subheader("🛠️ Padrões de Código")
    
    st.markdown("""
    **Imports:**
    - Agrupe imports padrão, depois packages, depois módulos locais
    
    **Nomeação:**
    - Funções: `snake_case`
    - Classes: `PascalCase`
    - Constantes: `UPPER_SNAKE_CASE`
    
    **Documentação:**
    - Adicione docstrings em todas as funções
    - Use comentários para lógica complexa
    
    **Tratamento de Erros:**
    - Use try/except para APIs externas
    - Retorne valores seguros em caso de falha
    """)

# ==========================================
# SEÇÃO 6: COMO COMEÇAR
# ==========================================
elif indice_selecionado == "🚀 Como Começar":
    st.header("🚀 Como Começar")
    
    st.subheader("1️⃣ Instalação")
    
    st.code("""
# Clone o repositório
git clone https://github.com/seuusuario/invest.git
cd invest

# Crie um ambiente virtual
python -m venv .venv

# Ative o ambiente
# No Windows:
.venv\\Scripts\\activate
# No macOS/Linux:
source .venv/bin/activate

# Instale as dependências
pip install -r requirements.txt
    """, language="bash")
    
    st.subheader("2️⃣ Execução")
    
    st.code("""
# Rode a aplicação
streamlit run src/app.py

# A aplicação abrirá em http://localhost:8501
    """, language="bash")
    
    st.subheader("3️⃣ Primeiro Uso")
    
    st.markdown("""
    1. **Cadastre uma Pessoa**: Vá para a aba "Cadastro" e adicione uma pessoa
    2. **Adicione Investimentos**: Na aba "Inserção Manual", cadastre seus investimentos
    3. **Veja Resumo**: Volte para "Resumo" e acompanhe o consolidado
    4. **Explore Gráficos**: Use as abas de gráficos para visualizar distribuição
    5. **Configure Alertas**: Na aba "Alertas", defina preços-alvo para monitorar
    """)
    
    st.subheader("4️⃣ Próximos Passos")
    
    st.markdown("""
    - 📥 Importe dados históricos via CSV
    - 📊 Compare seu portfólio com benchmarks
    - 🔮 Simule projeções futuras com aportes
    - 🎯 Configure alertas para oportunidades
    """)

# ==========================================
# SEÇÃO 7: FAQ
# ==========================================
elif indice_selecionado == "📋 FAQ":
    st.header("📋 Perguntas Frequentes")
    
    faqs = {
        "Como faço para importar dados históricos?": """
        Prepare um arquivo CSV com as colunas: Pessoa, Produto, Categoria, Valor, Moeda.
        Vá para a aba "Upload CSV", selecione o arquivo e ele será importado automaticamente.
        """,
        
        "Qual é a precisão dos dados de mercado?": """
        Os dados vêm do Yahoo Finance via yfinance. São atualizados em tempo real durante
        o horário de funcionamento do mercado.
        """,
        
        "Posso rastrear múltiplas pessoas?": """
        Sim! O sistema suporta múltiplos usuários. Cada pessoa pode ter seus próprios
        investimentos e projeções.
        """,
        
        "Como funciona a conversão de moedas?": """
        Usamos a API forex-python para conversão em tempo real. Os valores são convertidos
        para BRL automaticamente no consolidado.
        """,
        
        "Os alertas funcionam em tempo real?": """
        Os alertas são verificados sob demanda. Clique em "Verificar Alerta" para checar
        se o preço-alvo foi atingido.
        """,
        
        "Posso exportar os dados?": """
        Atualmente, você pode copiar os dados das tabelas. Futuras versões incluirão
        exportação em Excel e PDF.
        """
    }
    
    for pergunta, resposta in faqs.items():
        with st.expander(f"❓ {pergunta}"):
            st.write(resposta)

# ==========================================
# SEÇÃO 8: UPLOAD DE RELATÓRIOS (se disponível)
# ==========================================
elif tem_upload_relatorio and indice_selecionado == "📥 Upload de Relatórios":
    st.header("📥 Upload de Relatórios Mensais")
    
    st.markdown("""
    Esta seção é dedicada ao upload e processamento de relatórios mensais de investimentos
    da B3 e corretoras.
    """)
    
    st.markdown("---")
    
    st.subheader("🔢 Cálculo de Rentabilidade Mensal")
    
    st.markdown("""
    A aba de **Rentabilidade** dentro de **Consolidação** calcula o retorno mensal de cada ativo
    usando a metodologia "sem aportes", que considera apenas a variação de preço e dividendos
    sobre a quantidade **do mês anterior**.
    
    **Fórmula Aplicada (Linha a Linha):**
    ```
    Para cada Ativo no Mês:
        1. QuantidadeBase = Quantidade do Mês Anterior
        2. ValorInicial = QuantidadeBase × Preço do Mês Anterior
        3. ValorFinal = QuantidadeBase × Preço do Mês Atual
        4. Dividendos = Soma total de dividendos recebidos do ativo no mês
        5. Retorno% = ((ValorFinal + Dividendos) - ValorInicial) / ValorInicial × 100
    ```
    
    **Exemplo Prático (SAPR4 - Giselle - 06/2024):**
    - Quantidade em 05/2024: **14 ações**
    - Preço em 05/2024: **R$ 5,59**
    - Preço em 06/2024: **R$ 5,59**
    - Dividendos recebidos em 06/2024: **R$ 396,50**
    
    **Cálculo:**
    ```
    ValorInicial = 14 × 5,59 = R$ 78,26
    ValorFinal = 14 × 5,59 = R$ 78,26
    Retorno% = ((78,26 + 396,50) - 78,26) / 78,26 × 100 = 506,64%
    ```
    
    O retorno de **506%** reflete o impacto dos dividendos (R$ 396,50) sobre uma base pequena
    (14 ações = R$ 78,26). Isso ocorre quando há dividendos de posições maiores em outras instituições,
    mas a posição de fim de mês registrada é menor.
    
    **Agregações Maiores (Trimestral, Anual):**
    - Para períodos maiores, o retorno é calculado usando **juros compostos** (produto dos fatores mensais).
    - Fórmula: `RetornoTotal = [(1 + R1/100) × (1 + R2/100) × ... - 1] × 100`
    
    **Persistência e Cache:**
    - A base de rentabilidade é salva em `data/rentabilidade_base.parquet` para performance.
    - Rebuild automático quando há mudança nos arquivos de posições ou proventos.
    """)
    
    st.markdown("---")
    
    st.subheader("Funcionalidades de Upload")
    
    st.markdown("""
    - **Upload de relatórios Excel**: Processa arquivos com abas de Ações, Renda Fixa e Proventos
    - **Acúmulo histórico**: Cada upload substitui apenas o snapshot do mesmo mês/usuário
    - **Filtros por mês**: Visualização de posição patrimonial e proventos por mês
    - **Proventos acumulados**: Gráfico de proventos recebidos mês a mês
    - **Robustez**: O sistema detecta automaticamente cabeçalhos e tipos de abas
    """)
    
    st.markdown("---")
    
    st.subheader("Status dos dados atuais")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if os.path.exists(ACOES_PATH):
            df = pd.read_parquet(ACOES_PATH)
            st.metric("Snapshots de Ações", len(df["Mês/Ano"].unique()))
            st.info(f"Linhas totais: {len(df)}")
        else:
            st.warning("Sem dados de Ações")
    with col2:
        if os.path.exists(RENDA_FIXA_PATH):
            df = pd.read_parquet(RENDA_FIXA_PATH)
            st.metric("Snapshots de Renda Fixa", len(df["Mês/Ano"].unique()))
            st.info(f"Linhas totais: {len(df)}")
        else:
            st.warning("Sem dados de Renda Fixa")
    with col3:
        if os.path.exists(PROVENTOS_PATH):
            df = pd.read_parquet(PROVENTOS_PATH)
            st.metric("Meses de Proventos", len(df["Mês/Ano"].unique()))
            st.info(f"Linhas totais: {len(df)}")
        else:
            st.warning("Sem dados de Proventos")

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #888; font-size: 0.85rem; padding: 20px;'>
    📚 Documentação do Sistema Invest | Versão 1.0.0 | Atualizada em {} {}
</div>
""".format(datetime.now().strftime("%d/%m/%Y"), datetime.now().strftime("%H:%M")), unsafe_allow_html=True)
