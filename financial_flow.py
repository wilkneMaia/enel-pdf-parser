import streamlit as st
import pandas as pd
import plotly.express as px


def render_financial_flow(df_fin_view, total_custo):
    """
    Renderiza a seção de Fluxo Financeiro com visual CLEAN.
    Substitui Waterfall/Tornado por Barras Comparativas e Ranking Simples.
    """
    st.subheader("Fluxo Financeiro: Entradas e Saídas")

    # --- PREPARAÇÃO DOS DADOS ---
    # 1. Agrupa por Item
    df_fat = df_fin_view.groupby("Itens de Fatura")["Valor (R$)"].sum().reset_index()

    # 2. Define Tipo e Cores
    df_fat["Tipo"] = df_fat["Valor (R$)"].apply(
        lambda x: "Despesa" if x > 0 else "Economia"
    )
    df_fat["Cor"] = df_fat["Valor (R$)"].apply(
        lambda x: "#EF553B" if x > 0 else "#00CC96"
    )  # Vermelho vs Verde

    # 3. Cria Valor Absoluto para os gráficos (para a barra verde crescer pra direita também)
    df_fat["Valor_Abs"] = df_fat["Valor (R$)"].abs()

    # 4. Dados para o Balanço (Totais)
    total_despesas = df_fat[df_fat["Valor (R$)"] > 0]["Valor (R$)"].sum()
    total_economia = df_fat[df_fat["Valor (R$)"] < 0]["Valor_Abs"].sum()

    df_balanco = pd.DataFrame(
        {
            "Categoria": ["Total Despesas", "Total Economia"],
            "Valor": [total_despesas, total_economia],
            "Cor": ["#EF553B", "#00CC96"],  # Vermelho, Verde
        }
    )

    # --- VISUALIZAÇÃO ---
    col_balanco, col_ranking = st.columns([1, 2])  # Ranking ganha mais espaço

    with col_balanco:
        st.caption("⚖️ Balanço Geral")
        # Gráfico de Colunas Simples (Side-by-Side)
        fig_bal = px.bar(
            df_balanco,
            x="Categoria",
            y="Valor",
            color="Categoria",
            color_discrete_map={
                "Total Despesas": "#EF553B",
                "Total Economia": "#00CC96",
            },
            text_auto=".2f",
        )
        fig_bal.update_layout(
            showlegend=False,
            xaxis_title=None,
            yaxis_title=None,
            height=300,
            margin=dict(t=0, b=0, l=0, r=0),
        )
        # Oculta linhas de grade para ficar clean
        fig_bal.update_xaxes(showgrid=False)
        fig_bal.update_yaxes(showgrid=False, visible=False)
        st.plotly_chart(fig_bal, use_container_width=True)

    with col_ranking:
        st.caption("📋 Ranking de Itens (O que pesou mais?)")

        # Ordena pelo maior valor ABSOLUTO (seja custo ou desconto)
        df_fat = df_fat.sort_values(
            "Valor_Abs", ascending=True
        )  # Crescente para plotar de cima pra baixo

        # Gráfico de Barras Horizontais (Clean)
        fig_rank = px.bar(
            df_fat,
            x="Valor_Abs",
            y="Itens de Fatura",
            orientation="h",
            color="Tipo",
            text="Valor (R$)",  # Mostra o valor real (com negativo) no texto
            color_discrete_map={"Despesa": "#EF553B", "Economia": "#00CC96"},
        )

        fig_rank.update_traces(texttemplate="%{text:.2f}", textposition="outside")
        fig_rank.update_layout(
            showlegend=True,
            legend_title=None,
            legend=dict(orientation="h", y=1.1),  # Legenda no topo
            xaxis_title=None,
            yaxis_title=None,
            height=300,
            margin=dict(t=0, b=0, l=0, r=0),
        )
        fig_rank.update_xaxes(visible=False)  # Remove eixo X (números em baixo)
        st.plotly_chart(fig_rank, use_container_width=True)

    # Pequeno resumo em texto
    saldo_cobertura = (
        (total_economia / total_despesas * 100) if total_despesas > 0 else 0
    )
    if total_economia > 0:
        st.info(
            f"💡 A sua economia (Injeção/Descontos) abateu **{saldo_cobertura:.1f}%** das despesas brutas."
        )
