import streamlit as st
import pandas as pd
import plotly.express as px
import os
import plotly.graph_objects as go

# --- IMPORTAÇÃO DOS MÓDULOS ---
# Certifique-se de que os arquivos .py estão na mesma pasta
from taxometer import render_taxometer
from public_lighting import render_public_lighting
from financial_flow import render_financial_flow

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Enel Dashboard", page_icon="⚡", layout="wide")

# --- CONSTANTES ---
PATH_FINANCEIRO = "output/faturas.parquet"
PATH_MEDICAO = "output/medicao.parquet"

# --- FUNÇÃO DE CARREGAMENTO E TRATAMENTO ---
@st.cache_data
def load_data():
    if not os.path.exists(PATH_FINANCEIRO) or not os.path.exists(PATH_MEDICAO):
        return None, None
    try:
        df_fin = pd.read_parquet(PATH_FINANCEIRO)
        df_med = pd.read_parquet(PATH_MEDICAO)

        # 1. Tratamento de Datas
        df_fin['Data_Ref'] = pd.to_datetime(df_fin['Referência'], format='%m/%Y', errors='coerce')
        df_med['Data_Ref'] = pd.to_datetime(df_med['Referência'], format='%m/%Y', errors='coerce')

        # 2. Ordenação Cronológica (Fundamental para o MoM)
        df_fin = df_fin.sort_values('Data_Ref', ascending=False) # Do mais recente para o mais antigo
        df_med = df_med.sort_values('Data_Ref', ascending=False)

        return df_fin, df_med
    except Exception as e:
        st.error(f"Erro no processamento de dados: {str(e)}")
        return None, None

df_fin, df_med = load_data()

st.title("⚡ Dashboard de Energia (Enel)")

if df_fin is None:
    st.warning("⚠️ Dados não encontrados. Execute `python main.py`.")
    st.stop()

# --- FILTROS LATERAIS ---
st.sidebar.header("Filtros")

# 1. Filtro de Cliente
clientes = df_fin['Nº do Cliente'].unique()
# Mapeamento de Apelidos (Opcional - Ajuste conforme seus IDs reais)
apelidos = {"52217494": "🏠 Casa Principal", "12345678": "🏖️ Casa de Praia"}

selected_client = st.sidebar.selectbox(
    "Unidade:", clientes,
    format_func=lambda x: apelidos.get(str(x), f"Cliente {x}")
)

df_fin_client = df_fin[df_fin['Nº do Cliente'] == selected_client]
df_med_client = df_med[df_med['Nº do Cliente'] == selected_client]

# 2. Filtro de Período
# Ordena os meses disponíveis do mais recente para o antigo
available_months = df_fin_client['Referência'].unique()

selected_months = st.sidebar.multiselect(
    "Período (Mês/Ano):",
    options=available_months,
    default=available_months, # Seleciona todos por padrão
    help="Selecione meses para análise."
)

if not selected_months:
    st.warning("Selecione pelo menos um mês no filtro lateral.")
    st.stop()

# Aplica filtros
df_fin_view = df_fin_client[df_fin_client['Referência'].isin(selected_months)]
df_med_view = df_med_client[df_med_client['Referência'].isin(selected_months)]

# --- KPIS (MÊS CONTRA MÊS) ---
col1, col2, col3 = st.columns(3)

# KPI 1: Custo Total (Soma da Seleção)
total_custo = df_fin_view['Valor (R$)'].sum()

# KPI 2: Consumo Ativo (Soma da Seleção - Remove Injeção)
mask_injetada = df_med_view['P.Horário/Segmento'].astype(str).str.contains("INJ", case=False, na=False)
consumo_real = df_med_view[~mask_injetada]['Consumo kWh'].sum()

# KPI 3: TENDÊNCIA (MoM - Month over Month)
# Lógica: Pega os 2 meses mais recentes DENTRO da seleção atual
df_sorted = df_fin_view.sort_values('Data_Ref', ascending=False)
meses_na_visao = df_sorted['Referência'].unique()

delta_label = "Média Mensal"
delta_value = None
metric_label = "Tendência"
metric_value = 0.0

if len(meses_na_visao) >= 2:
    # Cenário Ideal: Tem pelo menos 2 meses para comparar
    mes_atual = meses_na_visao[0]    # Mês mais recente
    mes_anterior = meses_na_visao[1] # Mês anterior

    custo_atual = df_sorted[df_sorted['Referência'] == mes_atual]['Valor (R$)'].sum()
    custo_anterior = df_sorted[df_sorted['Referência'] == mes_anterior]['Valor (R$)'].sum()

    diff = custo_atual - custo_anterior
    pct = (diff / custo_anterior * 100) if custo_anterior > 0 else 0

    metric_label = f"📅 Fechamento {mes_atual}"
    metric_value = custo_atual
    delta_value = f"{pct:+.1f}% vs {mes_anterior}"

elif len(meses_na_visao) == 1:
    # Cenário: Só selecionou 1 mês
    mes_atual = meses_na_visao[0]
    custo_atual = df_sorted['Valor (R$)'].sum()

    metric_label = f"📅 Fechamento {mes_atual}"
    metric_value = custo_atual
    delta_value = "Mês único selecionado"
else:
    # Fallback
    metric_value = df_fin_view.groupby('Referência')['Valor (R$)'].sum().mean()

# Renderiza KPIs
with col1: st.metric("💰 Custo Total (Período)", f"R$ {total_custo:,.2f}")
with col2: st.metric("⚡ Consumo Total", f"{consumo_real:,.0f} kWh")

# Renderiza o KPI Inteligente na Coluna 3
with col3:
    if delta_value:
        st.metric(
            metric_label,
            f"R$ {metric_value:,.2f}",
            delta_value,
            delta_color="inverse" # Vermelho se subiu (ruim), Verde se caiu (bom)
        )
    else:
        st.metric("📅 Média Mensal", f"R$ {metric_value:,.2f}")

st.markdown("---")

# --- ABAS DE ANÁLISE ---
tab1, tab2, tab3 = st.tabs(["Financeiro", "Físico", "Dados"])

with tab1:
    # 1. FLUXO FINANCEIRO
    render_financial_flow(df_fin_view, total_custo)
    st.divider()

    # 2. TAXÔMETRO
    render_taxometer(df_fin_view, total_custo)
    st.divider()

    # 3. ILUMINAÇÃO PÚBLICA
    render_public_lighting(df_fin_view, df_med_view)

with tab2:
    st.subheader("Consumo Ativo (kWh)")
    df_cons = df_med_view[~mask_injetada].copy()

    if not df_cons.empty:
        # Se tiver mais de 1 mês, mostra gráfico
        if len(meses_na_visao) > 1:
            # Ordena cronologicamente para o gráfico (Jan -> Fev -> Mar)
            df_cons = df_cons.sort_values('Data_Ref', ascending=True)

            fig_bar = px.bar(
                df_cons, x='Referência', y='Consumo kWh', text_auto='.0f',
                title="Histórico de Consumo",
                color_discrete_sequence=['#2E86C1']
            )
            st.plotly_chart(fig_bar, width="stretch")
        else:
            st.info(f"Visualizando apenas o consumo de {meses_na_visao[0]}.")
    else:
        st.info("Sem dados de consumo ativo.")

with tab3:
    col_a, col_b = st.columns(2)
    with col_a:
        st.caption("Faturas Detalhadas")
        st.dataframe(df_fin_view, width="stretch")
    with col_b:
        st.caption("Medições Técnicas")
        st.dataframe(df_med_view, width="stretch")
