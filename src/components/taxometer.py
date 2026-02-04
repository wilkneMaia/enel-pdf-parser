import streamlit as st
import pandas as pd
import plotly.express as px


# --- ALTERAÇÃO 1: Removi 'total_custo' dos argumentos ---
def render_taxometer(df_fin_view):
    """
    Renderiza a seção do Taxômetro (Comparativo Bruto vs Líquido)
    com visualização em TREEMAP (Mosaico).
    """
    st.subheader("⚖️ Taxômetro: Bruto vs. Líquido")

    # --- ALTERAÇÃO 2: Adicionei verificação e cálculo interno do total ---
    if df_fin_view.empty:
        st.info("Sem dados para análise.")
        return

    total_custo = df_fin_view["Valor (R$)"].sum()
    # ---------------------------------------------------------------------

    # --- A. CLASSIFICAÇÃO INTELIGENTE (CÓDIGO ORIGINAL) ---
    def classificar_detalhado(row):
        nome = str(row["Itens de Fatura"]).upper()
        if any(
            x in nome
            for x in ["BANDEIRA", "AMARELA", "VERMELHA", "ESCASSEZ", "ADICIONAL"]
        ):
            return "🚩 Bandeiras/Extras"
        if any(x in nome for x in ["CIP", "ILUM", "PUB", "MUNICIPAL"]):
            return "🔦 Iluminação Pública"
        if any(x in nome for x in ["TRIBUTO", "IMPOSTO"]):
            return "💸 Impostos (Fed/Est)"
        return "⚡ Energia & Serviços"

    df_analise = df_fin_view.copy()
    df_analise["Categoria Macro"] = df_analise.apply(classificar_detalhado, axis=1)

    # --- B. CÁLCULOS FINANCEIROS (CÓDIGO ORIGINAL) ---
    val_icms = df_fin_view["ICMS"].sum() if "ICMS" in df_fin_view.columns else 0
    val_pis = (
        df_fin_view["PIS/COFINS"].sum() if "PIS/COFINS" in df_fin_view.columns else 0
    )

    # Pega valores das LINHAS classificadas como Taxas/Extras
    total_ilum = df_analise[df_analise["Categoria Macro"] == "🔦 Iluminação Pública"][
        "Valor (R$)"
    ].sum()
    total_extras = df_analise[df_analise["Categoria Macro"] == "🚩 Bandeiras/Extras"][
        "Valor (R$)"
    ].sum()

    # Soma de Impostos (Colunas + Linhas classificadas como imposto)
    total_impostos_fed_est = val_icms + val_pis
    if total_impostos_fed_est == 0:
        total_impostos_fed_est = df_analise[
            df_analise["Categoria Macro"] == "💸 Impostos (Fed/Est)"
        ]["Valor (R$)"].sum()

    # Total Geral de Encargos
    total_tributos = total_impostos_fed_est + total_ilum + total_extras

    pct_tributos = (total_tributos / total_custo * 100) if total_custo > 0 else 0
    val_liquido = total_custo - total_tributos

    # --- C. PREPARAÇÃO DE DADOS PARA TREEMAP E TABELA (UNIFICADO) ---
    # Cria lista com TUDO: Energia Limpa + Cada Imposto Individual
    itens_mapa = []

    # 1. Adiciona a Energia Limpa (O bloco principal)
    itens_mapa.append(
        {
            "Item": "Energia Consumida (Real)",
            "Valor (R$)": val_liquido,
            "Categoria Macro": "⚡ Produto (Energia)",
            "Cor": "#2E86C1",  # Azul
        }
    )

    # 2. Adiciona os Impostos de Coluna (ICMS/PIS)
    if val_icms > 0:
        itens_mapa.append(
            {
                "Item": "ICMS",
                "Valor (R$)": val_icms,
                "Categoria Macro": "💸 Impostos",
                "Cor": "#C0392B",
            }
        )
    if val_pis > 0:
        itens_mapa.append(
            {
                "Item": "PIS/COFINS",
                "Valor (R$)": val_pis,
                "Categoria Macro": "💸 Impostos",
                "Cor": "#C0392B",
            }
        )

    # 3. Adiciona os Impostos de Linha (Iluminação, etc) e Bandeiras
    linhas_interesse = df_analise[
        df_analise["Categoria Macro"].isin(
            ["💸 Impostos (Fed/Est)", "🔦 Iluminação Pública", "🚩 Bandeiras/Extras"]
        )
    ]

    for index, row in linhas_interesse.iterrows():
        nome = row["Itens de Fatura"]
        # Normalização de nomes
        nome_up = str(nome).upper()
        if "ILUM" in nome_up or "CIP" in nome_up:
            nome = "Ilum. Pública"
        if "VERMELHA" in nome_up:
            nome = "Band. Vermelha"
        if "AMARELA" in nome_up:
            nome = "Band. Amarela"

        # Define a cor baseada no tipo
        cor_item = "#C0392B"  # Vermelho padrão (Imposto)
        cat_macro = "💸 Impostos"

        if "ILUM" in nome_up or "CIP" in nome_up:
            cor_item = "#E67E22"  # Laranja (Municipal/Taxas)
            cat_macro = "🔦 Taxas"
        if "BANDEIRA" in nome_up:
            cor_item = "#F1C40F"  # Amarelo (Bandeiras)
            cat_macro = "🚩 Extras"

        itens_mapa.append(
            {
                "Item": nome,
                "Valor (R$)": row["Valor (R$)"],
                "Categoria Macro": cat_macro,
                "Cor": cor_item,
            }
        )

    df_treemap_unificado = pd.DataFrame(itens_mapa)

    # Agrupa itens com mesmo nome (ex: duas bandeiras vermelhas)
    if not df_treemap_unificado.empty:
        df_treemap_unificado = (
            df_treemap_unificado.groupby(["Item", "Categoria Macro", "Cor"])[
                "Valor (R$)"
            ]
            .sum()
            .reset_index()
        )

    # --- D. VISUALIZAÇÃO ---

    # 1. KPI Cards
    k1, k2, k3 = st.columns(3)
    k1.metric("Valor Total da Fatura", f"R$ {total_custo:,.2f}")
    k2.metric(
        "Energia Real Consumida",
        f"R$ {val_liquido:,.2f}",
        delta="O que você usou",
        delta_color="normal",
    )
    k3.metric(
        "Total de Encargos/Taxas",
        f"R$ {total_tributos:,.2f}",
        delta=f"-{pct_tributos:.1f}% da conta",
        delta_color="inverse",
    )

    st.divider()

    # 2. Gráfico Treemap (Mosaico)
    col_graf, col_detalhe = st.columns([1.5, 1])

    with col_graf:
        st.caption("🗺️ Mapa de Custos (Proporção Real)")

        # Usa o DataFrame unificado para o Treemap
        if not df_treemap_unificado.empty:
            # TREEMAP: O substituto moderno do gráfico de pizza
            fig_tree = px.treemap(
                df_treemap_unificado,
                path=[
                    "Categoria Macro",
                    "Item",
                ],  # Hierarquia: Primeiro separa por Macro, depois por Item
                values="Valor (R$)",
                color="Categoria Macro",
                color_discrete_map={
                    "⚡ Produto (Energia)": "#2E86C1",
                    "💸 Impostos": "#C0392B",
                    "🔦 Taxas": "#E67E22",
                    "🚩 Extras": "#F1C40F",
                },
            )
            fig_tree.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300)
            # Melhora o texto dentro dos quadrados
            fig_tree.update_traces(textinfo="label+value+percent entry")
            st.plotly_chart(fig_tree, width='stretch')
        else:
            st.info("Sem dados suficientes para gerar o mapa.")

    with col_detalhe:
        st.caption("🔎 Ranking Detalhado (Maiores Descontos)")
        # Filtra apenas o que não é Energia para mostrar no ranking de "vilões"
        df_ranking = df_treemap_unificado[
            df_treemap_unificado["Categoria Macro"] != "⚡ Produto (Energia)"
        ].copy()

        if not df_ranking.empty:
            df_ranking = df_ranking.sort_values(
                "Valor (R$)", ascending=True
            )  # Crescente para o gráfico horizontal

            fig_bar = px.bar(
                df_ranking,
                x="Valor (R$)",
                y="Item",
                orientation="h",
                text_auto=".2f",
                color="Categoria Macro",
                color_discrete_map={
                    "💸 Impostos": "#C0392B",
                    "🔦 Taxas": "#E67E22",
                    "🚩 Extras": "#F1C40F",
                },
            )
            fig_bar.update_layout(
                yaxis={"categoryorder": "total ascending"},
                xaxis_title=None,
                yaxis_title=None,
                height=300,
                margin=dict(
                    t=0, b=0, l=0, r=50
                ),  # Aumenta margem direita para evitar corte
                showlegend=False,
            )
            fig_bar.update_traces(textposition="outside", cliponaxis=False)
            st.plotly_chart(fig_bar, width='stretch')
        else:
            st.success("Sua conta não possui impostos ou taxas extras identificáveis.")

    with st.expander("Ver Dados em Tabela"):
        if not df_treemap_unificado.empty:
            st.dataframe(
                df_treemap_unificado.sort_values("Valor (R$)", ascending=False),
                width='stretch',
                hide_index=True,
            )
        else:
            st.info("Sem dados para exibir.")

    # --- E. INSIGHTS AUTOMÁTICOS ---
    st.markdown("### 🧠 Insights Tributários")
    c_i1, c_i2 = st.columns(2)

    with c_i1:
        # Insight de Proporção (Didático)
        st.info(
            f"💡 **Para onde vai seu dinheiro?**\n\n"
            f"Para cada **R$ 100,00** pagos nesta fatura, aproximadamente **R$ {pct_tributos:.2f}** "
            f"são impostos e taxas. Apenas **R$ {100 - pct_tributos:.2f}** pagam efetivamente a energia consumida."
        )

    with c_i2:
        # Insight de Bandeiras (Alerta)
        if total_extras > 0:
            st.warning(
                f"⚠️ **Impacto das Bandeiras:**\n\n"
                f"As bandeiras tarifárias (Vermelha/Amarela/Escassez) encareceram sua conta em "
                f"**R$ {total_extras:,.2f}** neste período. Isso representa custos de geração extra no país."
            )
        else:
            st.success(
                "✅ **Bandeira Verde:**\n\n"
                "Não foram detectadas cobranças extras de bandeiras tarifárias neste período. "
                "Você pagou a tarifa base de energia."
            )
