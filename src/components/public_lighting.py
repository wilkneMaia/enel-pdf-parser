import streamlit as st
import pandas as pd
import plotly.express as px

# --- IMPORTAÇÃO DE REGRAS (Com Fallback) ---
try:
    from src.config.tax_rules import (
        get_cip_expected_value,
        get_law_rate,
        TAX_TABLES,
        ACTIVE_TABLE_KEY,
        CURRENT_BASE_RATE,
    )
except ImportError:
    # Caso rode fora da estrutura (debug), define mocks
    def get_cip_expected_value(c, cl):
        return 0.0

    def get_law_rate(c, cl):
        return 0.0

    TAX_TABLES = {}
    ACTIVE_TABLE_KEY = None
    CURRENT_BASE_RATE = 111.05


def render_public_lighting(df_fin_view, df_med_view):
    st.subheader("🔦 Auditoria Avançada de Iluminação Pública")

    # 1. Cabeçalho Legal
    st.markdown(
        """
        > **⚖️ Base Legal Vigente:**
        > * **Lei Aplicada:** Lei Municipal Nº 757/03.
        > * **Método:** Percentual sobre a Tarifa de Iluminação (Estimada em R$ {:.2f}).
        """.format(CURRENT_BASE_RATE)
    )

    # 2. Expander com a Tabela da Lei
    with st.expander("📜 Ver Tabela de Percentuais (Lei 757/03)"):
        if ACTIVE_TABLE_KEY and ACTIVE_TABLE_KEY in TAX_TABLES:
            raw_data = TAX_TABLES[ACTIVE_TABLE_KEY]
            df_lei_display = pd.DataFrame(
                raw_data, columns=["Min kWh", "Max kWh", "Alíquota"]
            )

            df_lei_display["Faixa"] = df_lei_display.apply(
                lambda x: f"{int(x['Min kWh'])} a {int(x['Max kWh'])} kWh"
                if x["Max kWh"] < 99999
                else f"Acima de {int(x['Min kWh'])}",
                axis=1,
            )
            df_lei_display["Alíquota (%)"] = df_lei_display["Alíquota"].apply(
                lambda x: f"{x * 100:.2f}%"
            )
            st.dataframe(
                df_lei_display[["Faixa", "Alíquota (%)"]],
                width='stretch',
                hide_index=True,
            )
        else:
            st.warning("⚠️ Tabela de legislação não carregada.")

    # 3. Validação de Dados (Crucial para não quebrar)
    if df_fin_view.empty:
        st.info("Sem dados financeiros para analisar.")
        return

    # Filtra CIP
    mask_ilum = (
        df_fin_view["Itens de Fatura"]
        .astype(str)
        .str.contains("ILUM|CIP|PUB", case=False, na=False)
    )
    if not mask_ilum.any():
        st.warning(
            "⚠️ Não foram encontradas cobranças de Iluminação Pública (CIP) nas faturas filtradas."
        )
        return

    # Prepara Dados Financeiros
    df_cip = (
        df_fin_view[mask_ilum].groupby("Referência")["Valor (R$)"].sum().reset_index()
    )
    df_cip.rename(columns={"Valor (R$)": "R$ Pago"}, inplace=True)

    # Prepara Dados de Consumo (Resiliência)
    if df_med_view.empty or "Consumo kWh" not in df_med_view.columns:
        st.error(
            "❌ Dados de Medição (Consumo) não encontrados. Verifique se o extrator capturou a tabela de leitura."
        )
        return

    # Filtra Injetada se houver (para não somar geração solar como consumo)
    if "P.Horário/Segmento" in df_med_view.columns:
        mask_inj = (
            df_med_view["P.Horário/Segmento"]
            .astype(str)
            .str.contains("INJ|Gera|Injetada", case=False, na=False)
        )
        df_cons = (
            df_med_view[~mask_inj]
            .groupby("Referência")["Consumo kWh"]
            .sum()
            .reset_index()
        )
    else:
        df_cons = df_med_view.groupby("Referência")["Consumo kWh"].sum().reset_index()

    # Merge (Cruzamento)
    df_audit = pd.merge(df_cip, df_cons, on="Referência", how="inner")

    if df_audit.empty:
        st.warning(
            "Não foi possível cruzar os dados Financeiros com os de Medição. Verifique se as datas de Referência coincidem."
        )
        return

    # --- CÁLCULOS ---
    df_audit["Alíquota Lei"] = (
        df_audit["Consumo kWh"].apply(lambda x: get_law_rate(x)) * 100
    )
    df_audit["R$ Lei"] = df_audit["Consumo kWh"].apply(
        lambda x: get_cip_expected_value(x)
    )

    # Alíquota Real (Reversa)
    df_audit["Alíquota paga"] = df_audit.apply(
        lambda row: (row["R$ Pago"] / row["R$ Lei"] * row["Alíquota Lei"])
        if row["R$ Lei"] > 0
        else 0.0,
        axis=1,
    )

    df_audit["Desvio"] = df_audit["R$ Pago"] - df_audit["R$ Lei"]
    df_audit["Veredito"] = df_audit["Desvio"].apply(
        lambda x: "🔴 Acima" if x > 0.10 else ("🟢 Abaixo" if x < -0.10 else "✅ OK")
    )

    # Diferença de Alíquota para análise
    df_audit["Diff Alíquota"] = df_audit["Alíquota paga"] - df_audit["Alíquota Lei"]

    # --- VISUALIZAÇÃO ---

    # 1. KPIs
    st.divider()
    st.markdown("### 📊 Resumo Executivo")
    k1, k2, k3, k4 = st.columns(4)

    total_pago = df_audit["R$ Pago"].sum()
    total_lei = df_audit["R$ Lei"].sum()
    diff = total_pago - total_lei
    media_aliq = df_audit["Alíquota paga"].mean()
    media_lei = df_audit["Alíquota Lei"].mean()

    k1.metric("Total Pago", f"R$ {total_pago:,.2f}")
    k2.metric("Valor Justo (Lei)", f"R$ {total_lei:,.2f}")
    k3.metric(
        "Divergência", f"R$ {diff:,.2f}", delta=f"{-diff:,.2f}", delta_color="normal"
    )  # Verde se negativo (economia), vermelho se positivo (gasto extra)
    k4.metric(
        "Alíquota Real Média",
        f"{media_aliq:.2f}%",
        delta=f"{media_aliq - media_lei:.2f}% vs Lei",
        delta_color="inverse",
    )

    # Explicação Matemática
    with st.expander("🧮 Entenda o Cálculo (Engenharia Reversa)"):
        st.markdown(f"""
        $$
        \\text{{Alíquota Real}} = \\left( \\frac{{\\text{{Valor Pago}}}}{{\\text{{Tarifa Base ({CURRENT_BASE_RATE:.2f})}}}} \\right) \\times 100
        $$
        """)

    st.divider()

    # 2. Análise Integrada (Métricas + Tabela + Gráfico)
    st.markdown("### 🧠 Análise de Divergências & Disparidade")

    # Filtra divergências significativas (> 0.1% para ignorar arredondamentos)
    threshold = 0.1
    divergencias = df_audit[df_audit["Diff Alíquota"].abs() > threshold].copy()

    # Impacto Financeiro Total
    total_desvio_rs = df_audit["Desvio"].sum()

    # --- A. Métricas (Topo) ---
    if not divergencias.empty:
        # Lógica para o 3º Insight (Pior/Melhor Caso)
        if total_desvio_rs > 0:
            # Cenário de Prejuízo: Mostra o mês com maior cobrança indevida
            idx_destaque = divergencias["Desvio"].idxmax()
            lbl_destaque = "Pior Mês (Pico)"
            cor_destaque = "inverse"
        else:
            # Cenário de Economia: Mostra o mês com maior desconto
            idx_destaque = divergencias["Desvio"].idxmin()
            lbl_destaque = "Melhor Mês"
            cor_destaque = "normal"

        row_destaque = divergencias.loc[idx_destaque]

        k_qtd, k_val, k_max = st.columns(3)
        k_qtd.metric("Meses c/ Erro", len(divergencias))
        k_val.metric(
            "Impacto R$",
            f"{total_desvio_rs:,.2f}",
            delta="Pago a Maior" if total_desvio_rs > 0 else "Economia",
            delta_color="inverse",
        )
        k_max.metric(
            lbl_destaque,
            f"R$ {abs(row_destaque['Desvio']):,.2f}",
            delta=f"Em {row_destaque['Referência']}",
            delta_color=cor_destaque,
        )
    else:
        st.success("✅ **Tudo Certo!**\n\nTodas as faturas seguiram a alíquota da Lei Municipal.")

    # st.divider()

    # --- B. Visualização Lado a Lado (Gráfico + Tabela) ---
    c_chart, c_table = st.columns([2, 1.2])

    with c_chart:
        st.caption("📈 Evolução: Alíquota Legal vs. Real Cobrada")
        df_melted_aliq = df_audit.melt(
            id_vars=["Referência"],
            value_vars=["Alíquota Lei", "Alíquota paga"],
            var_name="Tipo",
            value_name="Alíquota (%)",
        )

        # Ordenação Cronológica
        try:
            df_melted_aliq["Data_Ordenacao"] = pd.to_datetime(
                df_melted_aliq["Referência"], format="%b/%Y", errors="coerce"
            )
            df_melted_aliq = df_melted_aliq.sort_values("Data_Ordenacao")
        except Exception:
            pass

        fig_aliq = px.line(
            df_melted_aliq,
            x="Referência",
            y="Alíquota (%)",
            color="Tipo",
            markers=True,
            line_shape="spline",
            color_discrete_map={"Alíquota Lei": "#00CC96", "Alíquota paga": "#EF553B"},
        )
        fig_aliq.update_layout(
            legend_title=None,
            margin=dict(t=10, b=0, l=0, r=0),
            height=400,
            legend=dict(orientation="h", y=1.1),
        )
        st.plotly_chart(fig_aliq, width='stretch')

    with c_table:
        if not divergencias.empty:
            st.caption("📋 Lista de Inconsistências (Lei vs Real)")
            # Formatação para exibição
            out_df = divergencias.copy()
            out_df["Consumo"] = out_df["Consumo kWh"].astype(int).astype(str) + " kWh"
            out_df["Lei"] = out_df["Alíquota Lei"].map("{:.2f}%".format)
            out_df["Real"] = out_df["Alíquota paga"].map("{:.2f}%".format)
            out_df["Diff"] = out_df["Diff Alíquota"].map("{:+.2f}%".format)

            # Ordenação
            try:
                out_df["_dt"] = pd.to_datetime(out_df["Referência"], format="%b/%Y", errors="coerce")
                out_df = out_df.sort_values("_dt")
            except:
                pass

            st.dataframe(
                out_df[["Referência", "Consumo", "Lei", "Real", "Diff"]],
                width='stretch',
                hide_index=True,
                height=400,  # Altura sincronizada com o gráfico
            )
        else:
            st.info("Nenhuma inconsistência encontrada.")

    st.divider()

    # 3. Gráficos Financeiros e Tabela
    col1, col2 = st.columns([1.5, 1])

    with col1:
        st.write("### 🔍 Comparativo Mensal")
        df_melted = df_audit.melt(
            id_vars=["Referência"],
            value_vars=["R$ Pago", "R$ Lei"],
            var_name="Tipo",
            value_name="Valor (R$)",
        )
        fig = px.bar(
            df_melted,
            x="Referência",
            y="Valor (R$)",
            color="Tipo",
            barmode="group",
            color_discrete_map={"R$ Pago": "#EF553B", "R$ Lei": "#00CC96"},
            height=350,
        )
        st.plotly_chart(fig, width='stretch')

    with col2:
        st.write("### 📋 Detalhamento")
        st.dataframe(
            df_audit[
                [
                    "Referência",
                    "Consumo kWh",
                    "Alíquota Lei",
                    "Alíquota paga",
                    "R$ Lei",
                    "R$ Pago",
                    "Desvio",
                    "Veredito",
                ]
            ],
            column_config={
                "Consumo kWh": st.column_config.NumberColumn(
                    "Consumo", format="%d kWh"
                ),
                "Alíquota Lei": st.column_config.NumberColumn(
                    "Aliq. Lei", format="%.2f%%"
                ),
                "Alíquota paga": st.column_config.NumberColumn(
                    "Aliq. Real", format="%.2f%%"
                ),
                "R$ Lei": st.column_config.NumberColumn("Lei", format="R$ %.2f"),
                "R$ Pago": st.column_config.NumberColumn("Pago", format="R$ %.2f"),
                "Desvio": st.column_config.NumberColumn("Diff", format="%.2f"),
            },
            hide_index=True,
            width='stretch',
        )
