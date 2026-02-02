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
            # Multiplica por 100 para exibir bonito na tabela de consulta (ex: 20.72%)
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

        # --- CÁLCULOS DAS COLUNAS (CORRIGIDOS) ---

        # 1. Alíquota Lei (Multiplicamos por 100 para virar porcentagem de leitura humana)
        # Ex: 0.2072 vira 20.72
        df_audit["Alíquota Lei"] = df_audit["Consumo kWh"].apply(lambda x: get_law_rate(x)) * 100

        # 2. R$ Lei (Quanto deveria ter pago)
        df_audit["R$ Lei"] = df_audit["Consumo kWh"].apply(lambda x: get_cip_expected_value(x))

        # 3. Alíquota Paga (Multiplicamos por 100 aqui também)
        # Se R$ Pago for igual a R$ Lei, o resultado será igual à Alíquota Lei (ex: 20.72)
        df_audit["Alíquota paga"] = df_audit.apply(
            lambda row: (row["R$ Pago"] / row["R$ Lei"] * row["Alíquota Lei"]) if row["R$ Lei"] > 0 else 0.0,
            axis=1
        )

        # 4. Desvio (Diferença em Reais)
        df_audit["Desvio"] = df_audit["R$ Pago"] - df_audit["R$ Lei"]

        # 5. Veredito (Status)
        df_audit["Veredito"] = df_audit["Desvio"].apply(
            lambda x: "🔴 Acima" if x > 0.10 else ("🟢 Abaixo" if x < -0.10 else "✅ OK")
        )

        # --- EXIBIÇÃO ---
        col1, col2 = st.columns([1.5, 1])

        with col1:
            st.write("### 🔍 Comparativo Visual")
            # Gráfico de Barras
            df_melted = df_audit.melt(id_vars=["Referência"], value_vars=["R$ Pago", "R$ Lei"], var_name="Tipo", value_name="Valor (R$)")
            fig = px.bar(
                df_melted, x="Referência", y="Valor (R$)", color="Tipo", barmode="group",
                title="Valor Pago vs Valor da Lei",
                color_discrete_map={"R$ Pago": "#EF553B", "R$ Lei": "#00CC96"}, height=350
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.write("### 📋 Detalhamento")

            # Seleção e Ordenação das Colunas
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
                    "Referência": st.column_config.TextColumn("Referência"),
                    "Consumo kWh": st.column_config.NumberColumn("Consumo", format="%d kWh"),
                    # O formato %.2f%% apenas adiciona o símbolo %, ele não multiplica.
                    # Como já multiplicamos por 100 no código acima, agora exibirá "20.72%" corretamente.
                    "Alíquota Lei": st.column_config.NumberColumn("Alíq. Lei", format="%.2f%%"),
                    "Alíquota paga": st.column_config.NumberColumn("Alíq. Real", format="%.2f%%"),
                    "R$ Lei": st.column_config.NumberColumn("R$ Lei", format="R$ %.2f"),
                    "R$ Pago": st.column_config.NumberColumn("R$ Pago", format="R$ %.2f"),
                    "Desvio": st.column_config.NumberColumn("Desvio (R$)", format="%.2f"),
                    "Veredito": st.column_config.TextColumn("Veredito"),
                },
                hide_index=True,
                use_container_width=True
            )

            if not df_audit.empty:
                avg_diff = df_audit["Desvio"].mean()
                if abs(avg_diff) < 0.10:
                    st.success("✅ A cobrança está matematicamente correta.")
                else:
                    st.warning(f"⚠️ Diferença média de R$ {avg_diff:.2f} por fatura.")
