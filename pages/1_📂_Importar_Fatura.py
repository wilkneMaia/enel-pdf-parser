import streamlit as st
import os
import time
import pandas as pd
import plotly.express as px

# --- IMPORTS DA NOVA ARQUITETURA ---
try:
    from src.services.unlocker import unlock_pdf_file, check_is_encrypted
    from src.services.extractor import extract_data_from_pdf
    from src.database.manager import save_data, load_data
except ImportError as e:
    st.error(f"Erro de configuração: {e}")
    st.stop()

st.set_page_config(page_title="Importar Fatura", page_icon="📂", layout="wide")

st.title("📂 Importar Nova Fatura")
st.markdown("Faça o upload da sua conta de energia (PDF) para alimentar os gráficos.")

# --- ÁREA DE UPLOAD ---
# Usamos key=st.session_state para poder resetar o uploader depois
if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0

if "preview_data" not in st.session_state:
    st.session_state["preview_data"] = None

uploaded_file = st.file_uploader(
    "Escolha o arquivo PDF (Enel)",
    type=["pdf"],
    key=f"uploader_{st.session_state['uploader_key']}",
)

# Senha opcional (caso o usuário saiba que precisa)
password = st.text_input(
    "Senha do PDF (Opcional)",
    type="password",
    help="Geralmente os 5 primeiros dígitos do CPF.",
)

if uploaded_file is not None:
    st.divider()

    # 1. Verifica se o arquivo mudou (limpa preview antigo)
    if (
        st.session_state["preview_data"]
        and st.session_state["preview_data"]["filename"] != uploaded_file.name
    ):
        st.session_state["preview_data"] = None

    # 2. Se não tem preview, processa automaticamente
    if st.session_state["preview_data"] is None:
        with st.status("Lendo arquivo...", expanded=True) as status:
            temp_path = None
            try:
                # A. Desbloqueio
                st.write("🔓 Verificando criptografia...")
                senha_teste = password if password else None
                temp_path = unlock_pdf_file(uploaded_file, password=senha_teste)

                if not temp_path:
                    if check_is_encrypted(uploaded_file) and not password:
                        status.update(label="Erro: Senha Necessária", state="error")
                        st.error("🔒 Arquivo protegido. Informe a senha acima.")
                        st.stop()
                    else:
                        status.update(label="Erro no Desbloqueio", state="error")
                        st.error("❌ Falha ao abrir o PDF.")
                        st.stop()

                # B. Extração
                st.write("📝 Extraindo dados...")
                df_fin, df_med = extract_data_from_pdf(temp_path)

                if df_fin.empty:
                    status.update(label="Erro de Leitura", state="error")
                    st.error("⚠️ Nenhum dado financeiro encontrado.")
                    st.stop()

                # C. Sucesso -> Salva no Estado
                ref = (
                    df_fin["Referência"].iloc[0]
                    if "Referência" in df_fin.columns
                    else "Desconhecido"
                )
                st.session_state["preview_data"] = {
                    "filename": uploaded_file.name,
                    "fin": df_fin,
                    "med": df_med,
                    "ref": ref,
                }
                status.update(label="Leitura Concluída!", state="complete")
                st.rerun()

            except Exception as e:
                status.update(label="Erro Inesperado", state="error")
                st.error(f"Ocorreu um erro: {e}")
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)

    # 3. Se TEM preview, mostra tabela e confirmação
    else:
        data = st.session_state["preview_data"]
        st.info(f"✅ Fatura identificada: **{data['ref']}**")

        st.markdown("### 📝 Conferência dos Dados")
        st.dataframe(data["fin"], use_container_width=True, hide_index=True)

        c_save, c_cancel = st.columns([1, 1])

        with c_save:
            if st.button("💾 Confirmar e Salvar", type="primary", use_container_width=True):
                if save_data(data["fin"], data["med"]):
                    st.success(f"Fatura **{data['ref']}** salva com sucesso!")

                    # Reset total para próxima importação
                    st.session_state["preview_data"] = None
                    st.session_state["uploader_key"] += 1
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error("Erro ao escrever no banco de dados.")

        with c_cancel:
            if st.button("❌ Cancelar", use_container_width=True):
                st.session_state["preview_data"] = None
                st.session_state["uploader_key"] += 1
                st.rerun()

# --- DICA DE RODAPÉ ---
else:
    st.info(
        "💡 Dica: Você pode importar várias faturas uma por uma para construir seu histórico."
    )

# --- HISTÓRICO DE IMPORTAÇÕES (Movido de Monitor de Logs) ---
st.divider()
st.subheader("📊 Histórico de Importações")

# 1. Carrega Dados Reais do Banco
df_faturas, df_medicao = load_data()

if not df_faturas.empty:
    # 2. Resumo Geral
    total_faturas = df_faturas["Referência"].nunique()
    ultimo_mes = df_faturas["Referência"].iloc[-1] if not df_faturas.empty else "-"
    total_gasto = df_faturas["Valor (R$)"].sum()

    k1, k2, k3 = st.columns(3)
    k1.metric("Faturas no Sistema", total_faturas)
    k2.metric("Última Referência", ultimo_mes)
    k3.metric("Total Acumulado (R$)", f"R$ {total_gasto:,.2f}")

    # 3. Tabela de Detalhes
    st.markdown("### 📋 Faturas Cadastradas")
    df_resumo_mes = (
        df_faturas.groupby("Referência")
        .agg({"Valor (R$)": "sum", "Itens de Fatura": "count"})
        .reset_index()
    )
    df_resumo_mes.rename(columns={"Itens de Fatura": "Qtd. Itens"}, inplace=True)

    if not df_medicao.empty and "P.Horário/Segmento" in df_medicao.columns:
        mask_inj = (
            df_medicao["P.Horário/Segmento"]
            .astype(str)
            .str.contains("INJ", case=False, na=False)
        )
        df_med_agg = (
            df_medicao[~mask_inj]
            .groupby("Referência")["Consumo kWh"]
            .sum()
            .reset_index()
        )
        df_resumo_mes = pd.merge(df_resumo_mes, df_med_agg, on="Referência", how="left")

    st.dataframe(
        df_resumo_mes,
        column_config={
            "Valor (R$)": st.column_config.NumberColumn(
                "Valor Total", format="R$ %.2f"
            ),
            "Consumo kWh": st.column_config.NumberColumn("Consumo", format="%d kWh"),
            "Qtd. Itens": st.column_config.NumberColumn("Itens Extraídos"),
        },
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("🗑️ Zona de Perigo"):
        st.warning("Isso apagará todo o histórico de faturas.")
        if st.button("Limpar Banco de Dados Completo"):
            if os.path.exists("data/database/faturas.parquet"):
                os.remove("data/database/faturas.parquet")
            if os.path.exists("data/database/medicao.parquet"):
                os.remove("data/database/medicao.parquet")
            st.success("Banco de dados limpo com sucesso!")
            time.sleep(1)
            st.rerun()
