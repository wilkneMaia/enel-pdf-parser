import streamlit as st
import pandas as pd
import plotly.express as px

def render_taxometer(df_fin_view, total_custo):
    """
    Renderiza a seção do Taxômetro (Comparativo Bruto vs Líquido)
    com visualização em TREEMAP (Mosaico).
    """
    st.subheader("⚖️ Taxômetro: Bruto vs. Líquido")

    # --- A. CLASSIFICAÇÃO INTELIGENTE ---
    def classificar_detalhado(row):
        nome = str(row['Itens de Fatura']).upper()
        if any(x in nome for x in ['BANDEIRA', 'AMARELA', 'VERMELHA', 'ESCASSEZ', 'ADICIONAL']):
            return '🚩 Bandeiras/Extras'
        if any(x in nome for x in ['CIP', 'ILUM', 'PUB', 'MUNICIPAL']):
            return '🔦 Iluminação Pública'
        if any(x in nome for x in ['TRIBUTO', 'IMPOSTO']):
            return '💸 Impostos (Fed/Est)'
        return '⚡ Energia & Serviços'

    df_analise = df_fin_view.copy()
    df_analise['Categoria'] = df_analise.apply(classificar_detalhado, axis=1)

    # --- B. CÁLCULOS FINANCEIROS ---
    val_icms = df_fin_view['ICMS'].sum() if 'ICMS' in df_fin_view.columns else 0
    val_pis = df_fin_view['PIS/COFINS'].sum() if 'PIS/COFINS' in df_fin_view.columns else 0
    val_outros_imp = df_analise[df_analise['Categoria'] == '💸 Impostos (Fed/Est)']['Valor (R$)'].sum()

    total_impostos_fed_est = val_icms + val_pis + val_outros_imp
    total_ilum = df_analise[df_analise['Categoria'] == '🔦 Iluminação Pública']['Valor (R$)'].sum()

    mordida_fiscal_total = total_impostos_fed_est + total_ilum
    valor_sem_imposto = total_custo - mordida_fiscal_total
    perc_mordida = (mordida_fiscal_total / total_custo * 100) if total_custo > 0 else 0

    # --- C. PREPARAÇÃO DE DADOS PARA TREEMAP (UNIFICADO) ---
    # O Treemap precisa de uma lista contendo TUDO: Energia Limpa + Cada Imposto Individual

    itens_mapa = []

    # 1. Adiciona a Energia Limpa (O bloco Azul)
    itens_mapa.append({
        'Item': 'Energia Consumida (Real)',
        'Valor (R$)': valor_sem_imposto,
        'Categoria Macro': '⚡ Produto (Energia)',
        'Cor': '#2E86C1' # Azul
    })

    # 2. Adiciona os Impostos de Coluna (ICMS/PIS)
    if val_icms > 0:
        itens_mapa.append({'Item': 'ICMS', 'Valor (R$)': val_icms, 'Categoria Macro': '💸 Impostos', 'Cor': '#C0392B'})
    if val_pis > 0:
        itens_mapa.append({'Item': 'PIS/COFINS', 'Valor (R$)': val_pis, 'Categoria Macro': '💸 Impostos', 'Cor': '#C0392B'})

    # 3. Adiciona os Impostos de Linha (Iluminação, etc) e Bandeiras
    linhas_interesse = df_analise[df_analise['Categoria'].isin(['💸 Impostos (Fed/Est)', '🔦 Iluminação Pública', '🚩 Bandeiras/Extras'])]

    for index, row in linhas_interesse.iterrows():
        nome = row['Itens de Fatura']
        # Normalização de nomes
        nome_up = str(nome).upper()
        if 'ILUM' in nome_up or 'CIP' in nome_up: nome = 'Ilum. Pública'
        if 'VERMELHA' in nome_up: nome = 'Band. Vermelha'
        if 'AMARELA' in nome_up: nome = 'Band. Amarela'

        # Define a cor baseada no tipo
        cor_item = '#C0392B' # Vermelho padrão (Imposto)
        cat_macro = '💸 Impostos'

        if 'ILUM' in nome_up or 'CIP' in nome_up:
            cor_item = '#E67E22' # Laranja (Municipal/Taxas)
            cat_macro = '🔦 Taxas'
        if 'BANDEIRA' in nome_up:
            cor_item = '#F1C40F' # Amarelo (Bandeiras)
            cat_macro = '🚩 Extras'

        itens_mapa.append({'Item': nome, 'Valor (R$)': row['Valor (R$)'], 'Categoria Macro': cat_macro, 'Cor': cor_item})

    df_treemap = pd.DataFrame(itens_mapa)

    # Agrupa itens com mesmo nome (ex: duas bandeiras vermelhas)
    if not df_treemap.empty:
        df_treemap = df_treemap.groupby(['Item', 'Categoria Macro', 'Cor'])['Valor (R$)'].sum().reset_index()

    # --- D. VISUALIZAÇÃO ---

    # Equação Visual
    col_total, col_minus, col_tax, col_equal, col_real = st.columns([2, 0.5, 2, 0.5, 2])
    with col_total: st.metric("🧾 Total Pago", f"R$ {total_custo:,.2f}")
    with col_minus: st.markdown("<h2 style='text-align: center; color: gray;'>-</h2>", unsafe_allow_html=True)
    with col_tax: st.metric("🏛️ Mordida Fiscal", f"R$ {mordida_fiscal_total:,.2f}", delta=f"-{perc_mordida:.1f}%", delta_color="inverse")
    with col_equal: st.markdown("<h2 style='text-align: center; color: gray;'>=</h2>", unsafe_allow_html=True)
    with col_real: st.metric("⚡ Energia Real", f"R$ {valor_sem_imposto:,.2f}", delta="Produto")

    st.markdown("---")

    c1, c2 = st.columns([1.5, 1]) # Coluna da esquerda um pouco maior para o gráfico

    with c1:
        st.caption("🗺️ Mapa de Custos (Proporção Real)")
        if not df_treemap.empty:
            # TREEMAP: O substituto moderno do gráfico de pizza
            fig_tree = px.treemap(
                df_treemap,
                path=['Categoria Macro', 'Item'], # Hierarquia: Primeiro separa por Macro, depois por Item
                values='Valor (R$)',
                color='Categoria Macro',
                color_discrete_map={
                    '⚡ Produto (Energia)': '#2E86C1',
                    '💸 Impostos': '#C0392B',
                    '🔦 Taxas': '#E67E22',
                    '🚩 Extras': '#F1C40F'
                }
            )
            fig_tree.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300)
            # Melhora o texto dentro dos quadrados
            fig_tree.update_traces(textinfo="label+value+percent entry")
            st.plotly_chart(fig_tree, use_container_width=True)
        else:
            st.info("Sem dados suficientes para gerar o mapa.")

    with c2:
        st.caption("🔎 Ranking Detalhado (Maiores Descontos)")
        # Filtra apenas o que não é Energia para mostrar no ranking de "vilões"
        df_ranking = df_treemap[df_treemap['Categoria Macro'] != '⚡ Produto (Energia)'].copy()

        if not df_ranking.empty:
            df_ranking = df_ranking.sort_values('Valor (R$)', ascending=True) # Crescente para o gráfico horizontal

            fig_bar = px.bar(
                df_ranking,
                x='Valor (R$)',
                y='Item',
                orientation='h',
                text_auto='.2f',
                color='Categoria Macro',
                color_discrete_map={
                    '💸 Impostos': '#C0392B',
                    '🔦 Taxas': '#E67E22',
                    '🚩 Extras': '#F1C40F'
                }
            )
            fig_bar.update_layout(
                yaxis={'categoryorder':'total ascending'},
                xaxis_title=None, yaxis_title=None,
                height=300, margin=dict(t=0,b=0,l=0,r=0),
                showlegend=False
            )
            fig_bar.update_traces(textposition="outside", cliponaxis=False)
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.success("Sua conta não possui impostos ou taxas extras identificáveis.")

    with st.expander("Ver Dados em Tabela"):
        st.dataframe(df_treemap.sort_values('Valor (R$)', ascending=False), use_container_width=True)
