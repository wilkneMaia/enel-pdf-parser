import streamlit as st
import pandas as pd
import plotly.express as px


def render_public_lighting(df_fin_view, df_med_view):
    """
    Renderiza a seção de Análise de Iluminação Pública (CIP).
    Cruza o valor pago (Financeiro) com o Consumo kWh (Medição) para identificar degraus.
    """
    st.subheader("🔦 Análise de Iluminação Pública (CIP)")

    # 1. Filtra itens de Iluminação Pública no Financeiro
    mask_ilum = (
        df_fin_view["Itens de Fatura"]
        .astype(str)
        .str.contains("ILUM|CIP|PUB", case=False, na=False)
    )

    if mask_ilum.any():
        # Agrupa valor pago por mês
        df_cip = (
            df_fin_view[mask_ilum]
            .groupby("Referência")["Valor (R$)"]
            .sum()
            .reset_index()
        )
        df_cip.rename(columns={"Valor (R$)": "Valor CIP"}, inplace=True)

        # 2. Prepara dados de Consumo (Medição)
        # Importante: Filtrar Injeção para pegar apenas o consumo ativo
        mask_inj = (
            df_med_view["P.Horário/Segmento"]
            .astype(str)
            .str.contains("INJ", case=False, na=False)
        )
        df_cons = (
            df_med_view[~mask_inj]
            .groupby("Referência")["Consumo kWh"]
            .sum()
            .reset_index()
        )

        # 3. Merge (Junta as duas tabelas pela Data/Referência)
        if not df_cip.empty and not df_cons.empty:
            df_analise = pd.merge(df_cip, df_cons, on="Referência", how="inner")

            # 4. Visualização
            col_chart, col_info = st.columns([2, 1])

            with col_chart:
                # Gráfico de Dispersão: Consumo (Eixo X) vs Valor Pago (Eixo Y)
                fig_scatter = px.scatter(
                    df_analise,
                    x="Consumo kWh",
                    y="Valor CIP",
                    title="Raio-X da Cobrança: Consumo vs. Taxa",
                    color="Valor CIP",
                    color_continuous_scale="Oranges",
                    hover_data=["Referência"],
                )
                fig_scatter.update_traces(
                    marker=dict(size=12, line=dict(width=1, color="DarkSlateGrey"))
                )
                fig_scatter.update_layout(height=350, margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig_scatter, use_container_width=True)

            with col_info:
                st.info(
                    """
                    **🕵️ Como investigar:**

                    Olhe para a distribuição dos pontos no gráfico:

                    1. **Linha Reta Diagonal?** A cobrança é por kWh exato.

                    2. **Forma de Escada (Degraus)?** A prefeitura cobra por **Faixa de Consumo**.

                    *Se você ver um ponto "pulando" para cima com pouco aumento de consumo, você mudou de faixa.*
                    """
                )
        else:
            st.warning(
                "Não foi possível cruzar os dados de Fatura com Medição para as mesmas datas."
            )
    else:
        st.info(
            "Não foram identificados itens de Iluminação Pública (CIP/COSIP) nas faturas deste cliente."
        )
