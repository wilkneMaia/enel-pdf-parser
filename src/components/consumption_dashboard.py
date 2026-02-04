import streamlit as st
import pandas as pd
import plotly.express as px


def render_consumption_dashboard(df_medicao, df_faturas):
    """
    Renderiza o dashboard de consumo de energia (kWh).
    Cruza dados de medição com dados financeiros para insights de eficiência.
    """
    st.subheader("🔌 Balanço Energético (Consumo vs. Geração)")

    if df_medicao.empty:
        st.warning("Sem dados de medição disponíveis para análise.")
        return

    # --- 1. PREPARAÇÃO E LIMPEZA DOS DADOS ---
    df_med = df_medicao.copy()

    # Garante que Consumo é numérico (trata strings como "1.234,00")
    if df_med["Consumo kWh"].dtype == object:
        df_med["Consumo kWh"] = pd.to_numeric(
            df_med["Consumo kWh"]
            .astype(str)
            .str.replace(".", "")
            .str.replace(",", "."),
            errors="coerce",
        ).fillna(0)

    # Garante que N° Dias é numérico para cálculo de média diária
    if "N° Dias" in df_med.columns:
        df_med["N° Dias"] = pd.to_numeric(df_med["N° Dias"], errors="coerce").fillna(30)

    # --- SEPARAÇÃO: CONSUMO vs INJEÇÃO ---
    df_cons = df_med.copy()
    df_inj = pd.DataFrame()

    if "P.Horário/Segmento" in df_med.columns:
        # Identifica linhas de Geração Solar (Injetada)
        mask_inj = (
            df_med["P.Horário/Segmento"]
            .astype(str)
            .str.contains("INJ|Gera|Injetada", case=False, na=False)
        )
        df_inj = df_med[mask_inj].copy()
        df_cons = df_med[~mask_inj].copy()

    # 1. Agrupa Consumo
    df_view_cons = (
        df_cons.groupby("Referência")
        .agg(
            {
                "Consumo kWh": "sum",
                "N° Dias": "max",  # Pega o maior número de dias registrado no mês
            }
        )
        .reset_index()
    )

    # 2. Agrupa Injeção (se houver)
    if not df_inj.empty:
        df_view_inj = df_inj.groupby("Referência")["Consumo kWh"].sum().reset_index()
        df_view_inj.rename(columns={"Consumo kWh": "Injetado kWh"}, inplace=True)
    else:
        df_view_inj = pd.DataFrame(columns=["Referência", "Injetado kWh"])

    # 3. Merge (Consumo + Injeção)
    df_merged = pd.merge(
        df_view_cons, df_view_inj, on="Referência", how="outer"
    ).fillna(0)

    # Ordenação Cronológica
    try:
        df_merged["Data_Ordenacao"] = pd.to_datetime(
            df_merged["Referência"], format="%b/%Y", errors="coerce"
        )
        df_merged = df_merged.sort_values("Data_Ordenacao")
    except:
        pass

    # Cálculos Derivados
    df_merged["Média Diária (kWh)"] = df_merged["Consumo kWh"] / df_merged["N° Dias"]
    df_merged["Saldo kWh"] = df_merged["Consumo kWh"] - df_merged["Injetado kWh"]

    # --- 2. CÁLCULO DE EFICIÊNCIA (R$/kWh) ---
    # Cruzamos com o financeiro para saber quanto custou cada kWh naquele mês
    if not df_faturas.empty:
        df_fin_agg = df_faturas.groupby("Referência")["Valor (R$)"].sum().reset_index()
        df_merged = pd.merge(df_merged, df_fin_agg, on="Referência", how="left")

        # Cálculo do Custo Efetivo (Conta Total / Total kWh)
        # Evita divisão por zero
        df_merged["Custo Médio (R$/kWh)"] = df_merged.apply(
            lambda x: x["Valor (R$)"] / x["Consumo kWh"] if x["Consumo kWh"] > 0 else 0,
            axis=1,
        )

        # --- MELHORIA: TARIFA CHEIA PARA SOLAR ---
        if "Preço unit (R$) com tributos" in df_faturas.columns:
            df_tarifa = (
                df_faturas.groupby("Referência")["Preço unit (R$) com tributos"]
                .max()
                .reset_index()
            )
            df_tarifa.rename(
                columns={"Preço unit (R$) com tributos": "Tarifa Cheia"}, inplace=True
            )
            df_merged = pd.merge(df_merged, df_tarifa, on="Referência", how="left")
            df_merged["Tarifa Cheia"] = df_merged["Tarifa Cheia"].fillna(0)
        else:
            df_merged["Tarifa Cheia"] = 0
    else:
        df_merged["Custo Médio (R$/kWh)"] = 0
        df_merged["Tarifa Cheia"] = 0

    # Define a Tarifa Base para cálculos de economia (Prioriza a Tarifa Cheia se existir)
    df_merged["Tarifa Base Calc"] = df_merged.apply(
        lambda x: x["Tarifa Cheia"]
        if x["Tarifa Cheia"] > 0.1
        else x["Custo Médio (R$/kWh)"],
        axis=1,
    )

    # --- 3. KPIs (INDICADORES) ---
    total_kwh = df_merged["Consumo kWh"].sum()
    total_inj = df_merged["Injetado kWh"].sum()
    saldo_periodo = total_kwh - total_inj

    custo_medio_periodo = df_merged["Custo Médio (R$/kWh)"].mean()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Consumo da Rede", f"{total_kwh:,.0f} kWh")
    k2.metric(
        "Geração Injetada", f"{total_inj:,.0f} kWh", delta="Solar", delta_color="normal"
    )

    # Lógica do Saldo: Se positivo (Consumiu mais), vermelho. Se negativo (Sobrou), verde.
    label_saldo = "Faltou (Pagou)" if saldo_periodo > 0 else "Sobrou (Crédito)"
    k3.metric(
        "Saldo Energético",
        f"{saldo_periodo:,.0f} kWh",
        delta=label_saldo,
        delta_color="inverse",
    )

    k4.metric(
        "Custo Médio Real",
        f"R$ {custo_medio_periodo:.2f} / kWh",
        help="Valor da conta / Consumo da Rede.",
    )

    st.divider()

    # --- 4. GRÁFICOS ---
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### 📊 Consumo vs. Geração")

        # Prepara dados para gráfico agrupado
        df_melted = df_merged.melt(
            id_vars=["Referência"],
            value_vars=["Consumo kWh", "Injetado kWh"],
            var_name="Tipo",
            value_name="kWh",
        )

        fig_bar = px.bar(
            df_melted,
            x="Referência",
            y="kWh",
            color="Tipo",
            barmode="group",  # Barras lado a lado
            text_auto=".0f",
            color_discrete_map={"Consumo kWh": "#2E86C1", "Injetado kWh": "#2ECC71"},
        )

        fig_bar.update_layout(
            legend_title=None, xaxis_title=None, legend=dict(orientation="h", y=1.1)
        )
        st.plotly_chart(fig_bar, width='stretch')

    with c2:
        st.markdown("### 💸 Eficiência (R$ por kWh)")
        st.caption(
            "Este gráfico mostra se a energia está ficando mais cara, independente do seu consumo."
        )
        fig_line = px.line(
            df_merged,
            x="Referência",
            y="Custo Médio (R$/kWh)",
            markers=True,
            line_shape="spline",
        )
        fig_line.update_traces(line_color="#EF553B", line_width=3)
        st.plotly_chart(fig_line, width='stretch')

    # --- 5. INSIGHTS INTELIGENTES (NOVO) ---
    st.markdown("### 🧠 Insights do Período")
    c_solar, c_sazonal = st.columns(2)

    # A. Economia Solar Estimada
    with c_solar:
        if total_inj > 0:
            # Estimativa: kWh Injetado * Tarifa Cheia (Custo Evitado Real)
            # Calcula mês a mês para maior precisão
            economia_estimada = (
                df_merged["Injetado kWh"] * df_merged["Tarifa Base Calc"]
            ).sum()

            # --- REALIDADE: O que veio na conta (Soma dos itens negativos) ---
            credito_real = (
                df_faturas[df_faturas["Valor (R$)"] < 0]["Valor (R$)"].abs().sum()
            )
            diff_impostos = economia_estimada - credito_real

            st.markdown("##### ☀️ Economia Solar (Geração)")

            ks1, ks2 = st.columns(2)
            ks1.metric(
                "Valor de Mercado",
                f"R$ {economia_estimada:,.2f}",
                help="Quanto custaria essa energia se comprada da Enel (Tarifa Cheia).",
            )
            ks2.metric(
                "Abatido na Conta",
                f"R$ {credito_real:,.2f}",
                delta=f"-R$ {diff_impostos:,.2f} (Taxas)",
                delta_color="inverse",
                help="Valor efetivamente descontado na fatura (Total de Economia).",
            )

            if diff_impostos > 1:
                st.caption(
                    f"⚠️ A diferença de **R$ {diff_impostos:,.2f}** refere-se a impostos cobrados sobre a energia injetada."
                )
        else:
            st.info(
                "💡 **Dica Solar:**\n\nSe você instalar painéis solares, este painel calculará automaticamente quanto dinheiro você economizou evitando comprar energia da rede."
            )

    # B. Comparativo Sazonal (Ano x Ano)
    with c_sazonal:
        if not df_merged.empty and "Data_Ordenacao" in df_merged.columns:
            last_row = df_merged.iloc[-1]
            try:
                data_atual = last_row["Data_Ordenacao"]
                if pd.notnull(data_atual):
                    # Busca mesmo mês no ano anterior
                    target_year = data_atual.year - 1
                    target_month = data_atual.month

                    # Filtra no DataFrame
                    match = df_merged[
                        (df_merged["Data_Ordenacao"].dt.year == target_year)
                        & (df_merged["Data_Ordenacao"].dt.month == target_month)
                    ]

                    if not match.empty:
                        ant_row = match.iloc[0]
                        cons_atual = last_row["Consumo kWh"]
                        cons_ant = ant_row["Consumo kWh"]
                        delta_pct = (
                            ((cons_atual - cons_ant) / cons_ant * 100)
                            if cons_ant > 0
                            else 0
                        )

                        st.metric(
                            f"📅 Comparativo Anual ({last_row['Referência']})",
                            f"{cons_atual:.0f} kWh",
                            f"{delta_pct:+.1f}% vs Ano Anterior",
                            delta_color="inverse",  # Inverte: Aumento é vermelho (ruim), Queda é verde (bom)
                            help=f"Comparado com {ant_row['Referência']} ({cons_ant:.0f} kWh)",
                        )
                    else:
                        st.info(
                            f"📅 **Sazonalidade:** Sem dados de {target_month}/{target_year} para comparação anual."
                        )
            except Exception:
                st.write("---")

    # --- 6. SIMULADOR DE ECONOMIA ---
    with st.expander("🧮 Simulador de Economia (Se eu economizar...?)"):
        st.markdown("Veja quanto dinheiro você pouparia reduzindo seu consumo.")

        col_sim_1, col_sim_2 = st.columns([1, 2])
        with col_sim_1:
            meta_reducao = st.slider("Meta de Redução (%)", 1, 50, 10)

        with col_sim_2:
            # Estimativa simples baseada na média mensal e custo médio
            kwh_economizados = (
                (total_kwh / len(df_merged)) * (meta_reducao / 100)
                if len(df_merged) > 0
                else 0
            )
            poupanca_mensal = kwh_economizados * df_merged["Tarifa Base Calc"].mean()
            poupanca_anual = poupanca_mensal * 12

            st.success(
                f"📉 Reduzindo **{meta_reducao}%**, você economizaria cerca de **R$ {poupanca_mensal:.2f} por mês** (R$ {poupanca_anual:.2f}/ano)."
            )
