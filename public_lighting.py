import streamlit as st
import pandas as pd
import plotly.express as px

# Importa as regras de cálculo
try:
    from tax_rules import get_cip_expected_value, get_law_rate, TAX_TABLES, ACTIVE_TABLE_KEY
except ImportError:
    # Fallback de segurança
    def get_cip_expected_value(c, cl): return 0.0
    def get_law_rate(c, cl): return 0.0
    TAX_TABLES = {}
    ACTIVE_TABLE_KEY = None

def render_public_lighting(df_fin_view, df_med_view):
    st.subheader("🔦 Auditoria Avançada de Iluminação Pública")

    st.markdown(
        """
        > **⚖️ Base Legal Vigente:**
        > * **Lei Aplicada:** Lei Municipal Nº 757/03.
        > * **Método:** Percentual sobre a Tarifa de Iluminação (Estimada em ~R$ 111,05).
        """
    )

    # --- EXPANDER DA LEI ---
    with st.expander("📜 Ver Tabela de Percentuais (Lei 757/03)"):
        if ACTIVE_TABLE_KEY and ACTIVE_TABLE_KEY in TAX_TABLES:
            raw_data = TAX_TABLES[ACTIVE_TABLE_KEY]
            df_lei_display = pd.DataFrame(raw_data, columns=["Min kWh", "Max kWh", "Alíquota"])

            df_lei_display["Faixa"] = df_lei_display.apply(
                lambda x: f"{int(x['Min kWh'])} a {int(x['Max kWh'])} kWh" if x['Max kWh'] < 99999 else f"Acima de {int(x['Min kWh'])}", axis=1
            )
            # Multiplica por 100 para exibir bonito na tabela de consulta
            df_lei_display["Alíquota (%)"] = df_lei_display["Alíquota"].apply(lambda x: f"{x*100:.2f}%")

            st.dataframe(df_lei_display[["Faixa", "Alíquota (%)"]], use_container_width=True, hide_index=True)
        else:
            st.warning("Tabela não carregada.")
    # -----------------------

    # Filtros e Preparação de Dados
    mask_ilum = df_fin_view["Itens de Fatura"].astype(str).str.contains("ILUM|CIP|PUB", case=False, na=False)

    if not mask_ilum.any():
        st.info("Sem dados de CIP.")
        return

    # A. Valor Pago
    df_cip = df_fin_view[mask_ilum].groupby("Referência")["Valor (R$)"].sum().reset_index()
    df_cip.rename(columns={"Valor (R$)": "R$ Pago"}, inplace=True)

    # B. Consumo
    mask_inj = df_med_view["P.Horário/Segmento"].astype(str).str.contains("INJ", case=False, na=False)
    df_cons = df_med_view[~mask_inj].groupby("Referência")["Consumo kWh"].sum().reset_index()

    if not df_cip.empty and not df_cons.empty:
        # Merge (Junta Valor Pago + Consumo)
        df_audit = pd.merge(df_cip, df_cons, on="Referência", how="inner")

        # --- CÁLCULOS PRINCIPAIS ---
        df_audit["Alíquota Lei"] = df_audit["Consumo kWh"].apply(lambda x: get_law_rate(x)) * 100
        df_audit["R$ Lei"] = df_audit["Consumo kWh"].apply(lambda x: get_cip_expected_value(x))

        # Alíquota Paga (Cálculo Reverso)
        df_audit["Alíquota paga"] = df_audit.apply(
            lambda row: (row["R$ Pago"] / row["R$ Lei"] * row["Alíquota Lei"]) if row["R$ Lei"] > 0 else 0.0,
            axis=1
        )

        df_audit["Desvio"] = df_audit["R$ Pago"] - df_audit["R$ Lei"]

        df_audit["Veredito"] = df_audit["Desvio"].apply(
            lambda x: "🔴 Acima" if x > 0.10 else ("🟢 Abaixo" if x < -0.10 else "✅ OK")
        )

        # --- KPI CARDS (RESUMO DA AUDITORIA) ---
        st.divider()
        st.markdown("### 📊 Resumo Executivo da Auditoria")

        # Cálculos de Totais
        total_pago = df_audit["R$ Pago"].sum()
        total_lei = df_audit["R$ Lei"].sum()
        diff_total = total_pago - total_lei
        media_aliquota_real = df_audit["Alíquota paga"].mean()
        media_aliquota_lei = df_audit["Alíquota Lei"].mean()

        k1, k2, k3, k4 = st.columns(4)

        k1.metric("Total Pago (Período)", f"R$ {total_pago:,.2f}")
        k2.metric("Valor Justo (Lei)", f"R$ {total_lei:,.2f}")

        # Se diferença positiva (vermelho) = pagou a mais. Negativa (verde) = pagou a menos.
        k3.metric(
            "Divergência Total",
            f"R$ {diff_total:,.2f}",
            delta=f"{diff_total:,.2f}",
            delta_color="inverse" # Inverte: Valor alto é ruim (vermelho)
        )

        k4.metric(
            "Alíquota Média Real",
            f"{media_aliquota_real:.2f}%",
            delta=f"{(media_aliquota_real - media_aliquota_lei):.2f}% vs Lei",
            delta_color="inverse"
        )

        st.divider()
        # ---------------------------------------

        # --- EXIBIÇÃO DETALHADA ---
        col1, col2 = st.columns([1.5, 1])

        with col1:
            st.write("### 🔍 Comparativo Mensal")
            df_melted = df_audit.melt(id_vars=["Referência"], value_vars=["R$ Pago", "R$ Lei"], var_name="Tipo", value_name="Valor (R$)")
            fig = px.bar(
                df_melted, x="Referência", y="Valor (R$)", color="Tipo", barmode="group",
                # title="Valor Pago vs Valor da Lei",
                color_discrete_map={"R$ Pago": "#EF553B", "R$ Lei": "#00CC96"}, height=350
            )
            fig.update_layout(margin=dict(t=10, b=0, l=0, r=0)) # Ajuste de margem
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.write("### 📋 Detalhamento")

            cols_show = [
                "Referência",
                "Consumo kWh",
                "Alíquota Lei",
                "Alíquota paga",
                "R$ Lei",
                "R$ Pago",
                "Desvio",
                "Veredito"
            ]

            st.dataframe(
                df_audit[cols_show],
                column_config={
                    "Referência": st.column_config.TextColumn("Mês"),
                    "Consumo kWh": st.column_config.NumberColumn("Consumo", format="%d"),
                    "Alíquota Lei": st.column_config.NumberColumn("Aliq. Lei", format="%.2f%%"),
                    "Alíquota paga": st.column_config.NumberColumn("Aliq. Real", format="%.2f%%"),
                    "R$ Lei": st.column_config.NumberColumn("Lei", format="R$ %.2f"),
                    "R$ Pago": st.column_config.NumberColumn("Pago", format="R$ %.2f"),
                    "Desvio": st.column_config.NumberColumn("Diff", format="%.2f"),
                    "Veredito": st.column_config.TextColumn("Status"),
                },
                hide_index=True,
                use_container_width=True
            )
