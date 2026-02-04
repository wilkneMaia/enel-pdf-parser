import streamlit as st
import pandas as pd
import plotly.express as px
from src.database.manager import load_data

st.set_page_config(
    page_title="Histórico de Faturas",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Histórico de Importações")
st.markdown("Visualize todas as faturas que já foram processadas e salvas no banco de dados.")

# 1. Carrega Dados Reais do Banco
df_faturas, df_medicao = load_data()

if df_faturas.empty:
    st.warning("📭 O banco de dados está vazio. Importe sua primeira fatura.")
    st.stop()

# 2. Resumo Geral
total_faturas = df_faturas["Referência"].nunique()
ultimo_mes = df_faturas["Referência"].iloc[-1] if not df_faturas.empty else "-"
total_gasto = df_faturas["Valor (R$)"].sum()

k1, k2, k3 = st.columns(3)
k1.metric("Faturas no Sistema", total_faturas)
k2.metric("Última Referência", ultimo_mes)
k3.metric("Total Acumulado (R$)", f"R$ {total_gasto:,.2f}")

st.divider()

# 3. Gráfico de Evolução do Valor Total
st.subheader("📈 Evolução do Valor da Conta")

# Agrupa por Referência (Mês) para ter o valor total da fatura
df_agrupado = df_faturas.groupby("Referência")["Valor (R$)"].sum().reset_index()

# Tenta ordenar cronologicamente (Truque simples para JAN/2025 vir antes de FEV/2025)
# Se o formato for MES/ANO, a ordenação alfabética falha (ABR vem antes de JAN).
# Vamos tentar converter para data real apenas para ordenar o gráfico
try:
    df_agrupado["Data_Ordenacao"] = pd.to_datetime(df_agrupado["Referência"], format="%b/%Y", errors="coerce")
    # Mapeamento PT-BR se necessário, ou assumir EN se o extrator salvou JAN/FEB
    # Se falhar, ordena pelo índice mesmo
    df_agrupado = df_agrupado.sort_values("Data_Ordenacao")
except:
    pass

fig_evolucao = px.line(
    df_agrupado,
    x="Referência",
    y="Valor (R$)",
    markers=True,
    title="Histórico de Pagamentos (R$)",
    line_shape="spline" # Linha suave
)
fig_evolucao.update_traces(line_color="#00CC96", line_width=3)
st.plotly_chart(fig_evolucao, use_container_width=True)

# 4. Tabela de Detalhes (Faturas Importadas)
st.subheader("📋 Faturas Cadastradas")

# Mostra uma tabela limpa, sem mostrar cada item individual da fatura (que são muitos)
# Apenas um resumo por mês
df_resumo_mes = df_faturas.groupby("Referência").agg({
    "Valor (R$)": "sum",
    "Itens de Fatura": "count" # Conta quantos itens tem na fatura
}).reset_index()

df_resumo_mes.rename(columns={"Itens de Fatura": "Qtd. Itens"}, inplace=True)

# Tenta juntar com medição se existir
if not df_medicao.empty:
    if "P.Horário/Segmento" in df_medicao.columns:
        # Filtra injetada para pegar consumo real
        mask_inj = df_medicao["P.Horário/Segmento"].astype(str).str.contains("INJ", case=False, na=False)
        df_med_agg = df_medicao[~mask_inj].groupby("Referência")["Consumo kWh"].sum().reset_index()
    else:
        df_med_agg = df_medicao.groupby("Referência")["Consumo kWh"].sum().reset_index()

    df_resumo_mes = pd.merge(df_resumo_mes, df_med_agg, on="Referência", how="left")

st.dataframe(
    df_resumo_mes,
    column_config={
        "Valor (R$)": st.column_config.NumberColumn("Valor Total", format="R$ %.2f"),
        "Consumo kWh": st.column_config.NumberColumn("Consumo", format="%d kWh"),
        "Qtd. Itens": st.column_config.NumberColumn("Itens Extraídos"),
    },
    use_container_width=True,
    hide_index=True
)

# Botão de Reset (Perigo)
with st.expander("🗑️ Zona de Perigo"):
    st.warning("Isso apagará todo o histórico de faturas.")
    if st.button("Limpar Banco de Dados Completo"):
        import os
        try:
            os.remove("data/database/faturas.parquet")
            os.remove("data/database/medicao.parquet")
            st.success("Banco de dados limpo! Recarregue a página.")
        except Exception as e:
            st.error(f"Erro ao limpar: {e}")
