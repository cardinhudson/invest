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
    - **📊 Consolidação**: Visão única com todos os investimentos combinados (BR + Avenue) com filtros, métricas e gráficos de distribuição.
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
├── README.md                      # Documentação geral
├── requirements.txt               # Dependências do projeto
├── APP.py                         # Entrada principal (legado)
│
├── src/
│   ├── __init__.py               # Marca como pacote
│   ├── app.py                    # Aplicação Streamlit principal
│   │
│   ├── modules/
│   │   ├── __init__.py           # Marca como pacote
│   │   ├── data_processing.py    # Processamento de dados
│   │   ├── market_data.py        # Dados de mercado e benchmarks
│   │   ├── manual_input.py       # Entrada manual de investimentos
│   │   ├── alerts.py             # Sistema de alertas e projeções
│   │   └── upload.py             # Importação de CSV
│   │
│   └── pages/                    # Páginas Streamlit multi-page
│       ├── 1_📊_Dashboard.py
│       ├── 2_📈_Gráficos.py
│       ├── 6_📚_Documentacao.py
│       └── ...
│
├── data/                         # Arquivos CSV de dados
├── assets/                       # Imagens e ícones
│
└── .venv/                        # Ambiente virtual Python
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
