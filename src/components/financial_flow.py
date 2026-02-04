import streamlit as st
import pandas as pd
import plotly.express as px

def render_financial_flow(df_fin_view):
    """
    Renderiza a seção de Fluxo Financeiro com visual CLEAN.
    Recebe apenas o DataFrame filtrado e calcula os totais internamente.
    """
    st.subheader("📉 Fluxo Financeiro: Entradas e Saídas")

    if df_fin_view.empty:
        st.info("Sem dados financeiros para exibir.")
        return

    # --- PREPARAÇÃO DOS DADOS ---
    # 1. Agrupa por Item de Fatura incluindo ICMS e PIS/COFINS
    agg_dict = {"Valor (R$)": "sum"}
    if "ICMS" in df_fin_view.columns:
        agg_dict["ICMS"] = "sum"
    if "PIS/COFINS" in df_fin_view.columns:
        agg_dict["PIS/COFINS"] = "sum"

    df_fat = df_fin_view.groupby("Itens de Fatura").agg(agg_dict).reset_index()

    # 2. Define Tipo (Despesa vs Economia) e Cores
    # Valores positivos são Cobranças (Despesa) -> Vermelho
    # Valores negativos são Devoluções/Créditos (Economia) -> Verde
    df_fat["Tipo"] = df_fat["Valor (R$)"].apply(lambda x: "Despesa" if x > 0 else "Economia")

    # Mapeamento de Cores
    color_map = {"Despesa": "#EF553B", "Economia": "#00CC96"}

    # 3. Cria Valor Absoluto para os gráficos (para a barra verde crescer pra direita também)
    df_fat["Valor_Abs"] = df_fat["Valor (R$)"].abs()

    # 4. Dados para o Balanço (Totais)
    total_despesas = df_fat[df_fat["Valor (R$)"] > 0]["Valor (R$)"].sum()
    total_economia = df_fat[df_fat["Valor (R$)"] < 0]["Valor_Abs"].sum()
    saldo_final = total_despesas - total_economia

    # --- VISUALIZAÇÃO ---

    # 1. Cartões de Resumo (KPIs)
    k1, k2, k3 = st.columns(3)
    k1.metric("Total de Despesas", f"R$ {total_despesas:,.2f}", delta="-Saídas", delta_color="inverse")
    k2.metric("Total de Economia/Créditos", f"R$ {total_economia:,.2f}", delta="+Entradas", delta_color="normal")
    k3.metric("Saldo Final (A Pagar)", f"R$ {saldo_final:,.2f}")

    st.divider()

    col_balanco, col_ranking = st.columns([1, 1.5])

    # 2. Gráfico de Rosca (Donut Chart) - Proporção
    with col_balanco:
        st.caption("🍩 Proporção: Onde foi o dinheiro?")

        # Cria um mini dataframe para o gráfico de pizza
        df_pie = pd.DataFrame([
            {"Tipo": "Despesa", "Valor": total_despesas},
            {"Tipo": "Economia", "Valor": total_economia}
        ])

        fig_pie = px.pie(
            df_pie,
            values="Valor",
            names="Tipo",
            color="Tipo",
            color_discrete_map=color_map,
            hole=0.6 # Faz virar um Donut
        )
        fig_pie.update_traces(textinfo='percent+label')
        fig_pie.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0), height=300)
        st.plotly_chart(fig_pie, use_container_width=True)

    # 3. Gráfico de Barras Horizontais (Ranking)
    with col_ranking:
        st.caption("📋 Ranking de Itens (O que pesou mais?)")

        # Ordena pelo maior valor ABSOLUTO (seja custo ou desconto)
        df_fat = df_fat.sort_values("Valor_Abs", ascending=True)

        # Cria texto customizado com ICMS e PIS/COFINS
        def criar_texto_detalhado(row):
            partes = [f"R$ {row['Valor (R$)']:,.2f}"]
            if "ICMS" in df_fat.columns:
                icms_val = row.get("ICMS", 0) or 0
                if icms_val != 0:
                    partes.append(f"ICMS: {icms_val:,.2f}")
            if "PIS/COFINS" in df_fat.columns:
                pis_val = row.get("PIS/COFINS", 0) or 0
                if pis_val != 0:
                    partes.append(f"PIS: {pis_val:,.2f}")
            return " | ".join(partes) if len(partes) > 1 else partes[0]

        df_fat["Texto_Detalhado"] = df_fat.apply(criar_texto_detalhado, axis=1)

        # Prepara hover_data com ICMS e PIS/COFINS
        hover_data_dict = {}
        if "ICMS" in df_fat.columns:
            hover_data_dict["ICMS"] = ":,.2f"
        if "PIS/COFINS" in df_fat.columns:
            hover_data_dict["PIS/COFINS"] = ":,.2f"

        fig_rank = px.bar(
            df_fat,
            x="Valor_Abs",
            y="Itens de Fatura",
            orientation="h",
            color="Tipo",
            text="Texto_Detalhado", # Mostra valor + impostos no texto
            hover_data={
                "Valor (R$)": ":,.2f",
                **hover_data_dict,
            },
            color_discrete_map=color_map
        )

        fig_rank.update_traces(textposition='outside', textfont_size=9)
        fig_rank.update_layout(
            showlegend=True,
            legend_title=None,
            legend=dict(orientation="h", y=1.1), # Legenda no topo
            xaxis_title=None,
            yaxis_title=None,
            height=400,
            margin=dict(t=0, b=0, l=0, r=0)
        )
        fig_rank.update_xaxes(visible=False) # Remove eixo X (números em baixo) para limpar
        st.plotly_chart(fig_rank, use_container_width=True)
