import streamlit as st
import pandas as pd
import plotly.express as px

# --- CONFIGURAÇÃO DA PÁGINA (Deve ser a primeira linha) ---
st.set_page_config(
    page_title="Dashboard Enel",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- IMPORTS DA NOVA ARQUITETURA ---
try:
    from src.database.manager import load_data
    from src.components.taxometer import render_taxometer
    from src.components.financial_flow import render_financial_flow
    from src.components.public_lighting import render_public_lighting
    from src.components.consumption_dashboard import render_consumption_dashboard
except ImportError as e:
    st.error(f"❌ Erro Crítico de Importação: {e}")
    st.info(
        "Verifique se a pasta 'src' existe e se você rodou o script de configuração de pastas."
    )
    st.stop()


# --- FUNÇÕES AUXILIARES ---
def get_month_year_filter(df):
    """Extrai lista de Anos e Meses disponíveis para o filtro."""
    if df.empty or "Referência" not in df.columns:
        return []

    # Assume formato "MES/ANO" (ex: JAN/2025)
    # Extrai o ANO para filtro macro
    anos = sorted(
        list(
            set([x.split("/")[-1] for x in df["Referência"].unique() if "/" in str(x)])
        )
    )
    return anos


def main():
    st.title("⚡ Dashboard de Gestão Energética")
    st.markdown("---")

    # 1. Carregamento de Dados (Via Manager)
    df_faturas, df_medicao = load_data()

    # Validação Inicial
    if df_faturas.empty:
        st.warning("📭 Nenhum dado encontrado.")
        st.info(
            "👈 Use o menu lateral para acessar **'Importar Fatura'** e carregar seu primeiro PDF."
        )

        # Botão de atalho para ajudar
        if st.button("Ir para Importação"):
            st.switch_page("pages/2_📂_Importar_Fatura.py")
        return

    # 2. Sidebar de Filtros
    st.sidebar.header("🔍 Filtros Globais")

    # Filtro de Cliente (Se houver coluna e dados)
    if "Nº do Cliente" in df_faturas.columns:
        # Pega clientes únicos ignorando nulos
        clientes_unicos = sorted(
            [c for c in df_faturas["Nº do Cliente"].unique() if pd.notnull(c)]
        )

        # Só mostra o filtro se houver clientes identificados
        if len(clientes_unicos) > 0:
            cliente_selecionado = st.sidebar.selectbox(
                "👤 Cliente / Instalação", clientes_unicos
            )

            # Filtra os DataFrames Globais
            df_faturas = df_faturas[df_faturas["Nº do Cliente"] == cliente_selecionado]
            if not df_medicao.empty and "Nº do Cliente" in df_medicao.columns:
                df_medicao = df_medicao[
                    df_medicao["Nº do Cliente"] == cliente_selecionado
                ]

    # Filtro de Ano
    anos_disponiveis = get_month_year_filter(df_faturas)
    if anos_disponiveis:
        ano_selecionado = st.sidebar.selectbox(
            "📅 Selecione o Ano", anos_disponiveis, index=len(anos_disponiveis) - 1
        )
    else:
        ano_selecionado = None

    # Aplica Filtros
    if ano_selecionado:
        # Filtra onde a string de Referência contém o Ano (ex: "2025")
        mask_ano_fat = (
            df_faturas["Referência"].astype(str).str.contains(ano_selecionado, na=False)
        )
        df_fat_view = df_faturas[mask_ano_fat].copy()

        if not df_medicao.empty and "Referência" in df_medicao.columns:
            mask_ano_med = (
                df_medicao["Referência"]
                .astype(str)
                .str.contains(ano_selecionado, na=False)
            )
            df_med_view = df_medicao[mask_ano_med].copy()
        else:
            df_med_view = pd.DataFrame()
    else:
        df_fat_view = df_faturas.copy()
        df_med_view = df_medicao.copy()

    # Filtro Mês (Opcional - Multiselect)
    meses_disponiveis = df_fat_view["Referência"].unique()
    meses_selecionados = st.sidebar.multiselect(
        "📆 Filtrar Meses (Opcional)", meses_disponiveis
    )

    if meses_selecionados:
        df_fat_view = df_fat_view[df_fat_view["Referência"].isin(meses_selecionados)]
        if not df_med_view.empty:
            df_med_view = df_med_view[
                df_med_view["Referência"].isin(meses_selecionados)
            ]

    # KPI Global do Período Filtrado
    total_periodo = df_fat_view["Valor (R$)"].sum()
    st.sidebar.markdown("---")
    st.sidebar.metric("💰 Total no Período", f"R$ {total_periodo:,.2f}")

    # 3. Renderização das Abas (Componentes)
    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "💰 Taxômetro (Impostos)",
            "📉 Fluxo Financeiro",
            "⚡ Consumo (kWh)",
            "🔦 Auditoria Iluminação",
        ]
    )

    with tab1:
        # Chama o componente sem passar 'total_custo' (ele calcula sozinho agora)
        render_taxometer(df_fat_view)

    with tab2:
        render_financial_flow(df_fat_view)

    with tab3:
        render_consumption_dashboard(df_med_view, df_fat_view)

    with tab4:
        # Passa ambas as tabelas para cruzar dados financeiros com medição (kWh)
        render_public_lighting(df_fat_view, df_med_view)


if __name__ == "__main__":
    main()
