import streamlit as st
import pandas as pd
import plotly.express as px
import os
import plotly.graph_objects as go

# --- IMPORTAÇÃO DOS MÓDULOS ---
from taxometer import render_taxometer  # Módulo Impostos
from public_lighting import render_public_lighting  # Módulo Iluminação
from financial_flow import render_financial_flow  # Módulo Fluxo Financeiro

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
        df_fin["Data_Ref"] = pd.to_datetime(
            df_fin["Referência"], format="%m/%Y", errors="coerce"
        )
        df_med["Data_Ref"] = pd.to_datetime(
            df_med["Referência"], format="%m/%Y", errors="coerce"
        )

        # 2. Tratamento Numérico (Faturas)
        cols_impostos = ["ICMS", "PIS/COFINS", "Valor (R$)"]
        for col in cols_impostos:
            if col in df_fin.columns:
                if df_fin[col].dtype == "object":
                    df_fin[col] = (
                        df_fin[col]
                        .astype(str)
                        .str.replace("R$", "", regex=False)
                        .str.replace(".", "", regex=False)
                        .str.replace(",", ".", regex=False)
                    )
                df_fin[col] = pd.to_numeric(df_fin[col], errors="coerce").fillna(0)

        # 3. Tratamento Numérico (Medição)
        df_med["Consumo kWh"] = pd.to_numeric(
            df_med["Consumo kWh"], errors="coerce"
        ).fillna(0)

        # Retorna ordenado por data para que os filtros apareçam na ordem certa
        return df_fin.sort_values("Data_Ref"), df_med.sort_values("Data_Ref")
    except Exception as e:
        st.error(f"Erro no processamento de dados: {str(e)}")
        return None, None


df_fin, df_med = load_data()

st.title("⚡ Dashboard de Energia (Enel)")

if df_fin is None:
    st.warning("⚠️ Dados não encontrados. Execute `python main.py`.")
    st.stop()

# --- BARRA LATERAL (FILTROS) ---
st.sidebar.header("Filtros")

# 1. Filtro de Cliente (Unidade Consumidora)
clientes = df_fin["Nº do Cliente"].unique()
apelidos = {"52217494": "🏠 Casa Principal", "12345678": "🏖️ Casa de Praia"}

selected_client = st.sidebar.selectbox(
    "Unidade:", clientes, format_func=lambda x: apelidos.get(str(x), f"Cliente {x}")
)

# Filtra preliminarmente pelo cliente para carregar os meses dele
df_fin_client = df_fin[df_fin["Nº do Cliente"] == selected_client]
df_med_client = df_med[df_med["Nº do Cliente"] == selected_client]

# 2. Filtro de Período (NOVO)
# Pega os meses únicos e garante a ordem cronológica
available_months = df_fin_client.sort_values("Data_Ref")["Referência"].unique()

selected_months = st.sidebar.multiselect(
    "Período (Mês/Ano):",
    options=available_months,
    default=available_months,  # Por padrão, seleciona todos
    help="Selecione um ou mais meses para análise.",
)

# Aplica o filtro de período
if not selected_months:
    st.warning("Selecione pelo menos um mês no filtro lateral.")
    st.stop()

df_fin_view = df_fin_client[df_fin_client["Referência"].isin(selected_months)]
df_med_view = df_med_client[df_med_client["Referência"].isin(selected_months)]

# --- KPIS ---
col1, col2, col3 = st.columns(3)

# KPI 1: Custo Total (Soma do período selecionado)
total_custo = df_fin_view["Valor (R$)"].sum()

# KPI 2: Consumo Ativo (Remove Injeção)
mask_injetada = (
    df_med_view["P.Horário/Segmento"]
    .astype(str)
    .str.contains("INJ", case=False, na=False)
)
consumo_real = df_med_view[~mask_injetada]["Consumo kWh"].sum()

# KPI 3: Média (Do período selecionado)
media_mensal = df_fin_view.groupby("Referência")["Valor (R$)"].sum().mean()

with col1:
    st.metric("💰 Custo Total", f"R$ {total_custo:,.2f}")
with col2:
    st.metric("⚡ Consumo Ativo", f"{consumo_real:,.0f} kWh")
with col3:
    st.metric("📅 Média Mensal", f"R$ {media_mensal:,.2f}")

st.markdown("---")

# --- ABAS ---
tab1, tab2, tab3 = st.tabs(["Financeiro", "Físico", "Dados"])

with tab1:
    # 1. FLUXO FINANCEIRO (MÓDULO EXTERNO)
    render_financial_flow(df_fin_view, total_custo)

    st.divider()

    # 2. TAXÔMETRO (MÓDULO EXTERNO)
    render_taxometer(df_fin_view, total_custo)

    st.divider()

    # 3. ILUMINAÇÃO PÚBLICA (MÓDULO EXTERNO)
    render_public_lighting(df_fin_view, df_med_view)

with tab2:
    st.subheader("Consumo Ativo (kWh)")
    df_cons = df_med_view[~mask_injetada].copy()

    if not df_cons.empty:
        # Se tiver mais de 1 mês, mostra gráfico de barras por mês
        if len(selected_months) > 1:
            fig_bar = px.bar(
                df_cons,
                x="Referência",
                y="Consumo kWh",
                text_auto=".0f",
                title="Histórico de Consumo",
            )
            st.plotly_chart(fig_bar, width="stretch")
        else:
            # Se for apenas 1 mês, mostra um indicador grande
            st.metric(
                label=f"Consumo em {selected_months[0]}",
                value=f"{df_cons['Consumo kWh'].sum():.0f} kWh",
            )
    else:
        st.info("Sem dados de consumo ativo para o período selecionado.")

with tab3:
    col_a, col_b = st.columns(2)
    with col_a:
        st.caption("Faturas Detalhadas")
        st.dataframe(df_fin_view, width="stretch")
    with col_b:
        st.caption("Medições Técnicas")
        st.dataframe(df_med_view, width="stretch")
