import streamlit as st
import pandas as pd
import plotly.express as px
import os

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Monitor de Execução (Logs)",
    page_icon="🔍",
    layout="wide"
)

# --- CONSTANTES ---
LOG_FILE = "logs/historico_geral.jsonl"
LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "historico_geral.jsonl")

# --- FUNÇÃO DE CARREGAMENTO ---
def load_logs():
    if not os.path.exists(LOG_FILE):
        return pd.DataFrame()

    try:
        # O Pandas lê JSON Lines nativamente (lines=True)
        df = pd.read_json(LOG_FILE, lines=True)

        # Converte timestamp para datetime
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp', ascending=False)

        return df
    except Exception as e:
        st.error(f"Erro ao ler arquivo de logs: {e}")
        return pd.DataFrame()

# --- INTERFACE ---
st.title("🔍 Monitor de Execução do Robô")

# Botão de Atualizar
if st.button("🔄 Atualizar Dados"):
    st.rerun()

df = load_logs()

if df.empty:
    st.warning("⚠️ Nenhum log encontrado. Execute o `main.py` primeiro para gerar dados.")
    st.stop()

# --- FILTROS LATERAIS ---
st.sidebar.header("Filtros")

# 1. Filtro de Status
if 'status' in df.columns:
    status_opts = df['status'].unique().tolist()
    selected_status = st.sidebar.multiselect("Status:", status_opts, default=status_opts)
else:
    selected_status = []

# 2. Filtro de Data
if 'timestamp' in df.columns:
    min_date = df['timestamp'].min().date()
    max_date = df['timestamp'].max().date()
    date_range = st.sidebar.date_input("Período:", [min_date, max_date])
else:
    date_range = []

# APLICA FILTROS
if 'status' in df.columns and selected_status:
    mask = df['status'].isin(selected_status)
    if len(date_range) == 2:
        mask &= (df['timestamp'].dt.date >= date_range[0]) & (df['timestamp'].dt.date <= date_range[1])
    df_view = df[mask]
else:
    df_view = df

# --- KPIS ---
col1, col2, col3, col4 = st.columns(4)

total_execucoes = len(df_view)
sucessos = len(df_view[df_view['status'] == 'sucesso']) if 'status' in df_view.columns else 0
erros = len(df_view[df_view['status'].str.contains('erro', case=False, na=False)]) if 'status' in df_view.columns else 0

# Soma financeira (se existir a coluna)
total_money = df_view['valor_total'].sum() if 'valor_total' in df_view.columns else 0

with col1: st.metric("📄 Arquivos Processados", total_execucoes)
with col2: st.metric("✅ Sucessos", sucessos)
with col3: st.metric("❌ Erros", erros, delta=f"-{erros}" if erros > 0 else "0", delta_color="inverse")
with col4: st.metric("💰 Valor Processado", f"R$ {total_money:,.2f}")

st.divider()

# --- GRÁFICOS ---
c1, c2 = st.columns([2, 1])

with c1:
    st.subheader("📊 Linha do Tempo")
    if 'timestamp' in df_view.columns and not df_view.empty:
        # CORREÇÃO 1: 'H' (deprecated) -> 'h'
        df_view['hora'] = df_view['timestamp'].dt.floor('h')
        timeline = df_view.groupby(['hora', 'status']).size().reset_index(name='contagem')

        fig_time = px.bar(
            timeline,
            x='hora',
            y='contagem',
            color='status',
            title="Execuções por Hora",
            color_discrete_map={'sucesso': '#00CC96', 'erro_fatal': '#EF553B', 'erro_vazio': '#FFA15A'}
        )
        # CORREÇÃO 2: use_container_width -> width='stretch'
        st.plotly_chart(fig_time, width="stretch")
    else:
        st.info("Sem dados temporais.")

with c2:
    st.subheader("⚠️ Distribuição de Status")
    if 'status' in df_view.columns and not df_view.empty:
        # CORREÇÃO 3: px.donut não existe. Usa-se px.pie com 'hole'
        fig_pie = px.pie(
            df_view,
            names='status',
            title="Taxa de Erro vs Sucesso",
            color='status',
            hole=0.4, # Isso cria o efeito Donut
            color_discrete_map={'sucesso': '#00CC96', 'erro_fatal': '#EF553B', 'erro_vazio': '#FFA15A'}
        )
        st.plotly_chart(fig_pie, width="stretch")
    else:
        st.info("Sem dados de status.")

# --- TABELA DETALHADA ---
st.subheader("📋 Detalhes da Execução")

# Seleciona e renomeia colunas para ficar bonito
cols_to_show = ['timestamp', 'status', 'arquivo', 'client_id', 'referencia', 'valor_total', 'consumo_kwh', 'detalhe']
cols_existentes = [c for c in cols_to_show if c in df_view.columns]

if not df_view.empty:
    st.dataframe(
        df_view[cols_existentes].sort_values('timestamp', ascending=False),
        column_config={
            "timestamp": st.column_config.DatetimeColumn("Data/Hora", format="DD/MM/YYYY HH:mm:ss"),
            "valor_total": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
            "consumo_kwh": st.column_config.NumberColumn("Consumo", format="%.0f kWh"),
            "status": st.column_config.Column(
                "Status",
                help="Resultado do processamento",
                width="medium",
            ),
        },
        width="stretch", # Atualizado
        hide_index=True
    )
