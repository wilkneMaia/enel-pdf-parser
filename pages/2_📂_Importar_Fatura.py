import streamlit as st
import os
import time

# --- IMPORTS DA NOVA ARQUITETURA ---
try:
    from src.services.unlocker import unlock_pdf_file, check_is_encrypted
    from src.services.extractor import extract_data_from_pdf
    from src.database.manager import save_data
except ImportError as e:
    st.error(f"Erro de configuração: {e}")
    st.stop()

st.set_page_config(page_title="Importar Fatura", page_icon="📂", layout="centered")

st.title("📂 Importar Nova Fatura")
st.markdown("Faça o upload da sua conta de energia (PDF) para alimentar os gráficos.")

# --- ÁREA DE UPLOAD ---
# Usamos key=st.session_state para poder resetar o uploader depois
if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0

uploaded_file = st.file_uploader(
    "Escolha o arquivo PDF (Enel)",
    type=["pdf"],
    key=f"uploader_{st.session_state['uploader_key']}"
)

# Senha opcional (caso o usuário saiba que precisa)
password = st.text_input("Senha do PDF (Opcional)", type="password", help="Geralmente os 5 primeiros dígitos do CPF.")

if uploaded_file is not None:
    st.divider()

    col_btn, col_status = st.columns([1, 2])

    with col_btn:
        processar = st.button("🚀 Processar Arquivo", type="primary", use_container_width=True)

    if processar:
        with st.status("Processando...", expanded=True) as status:
            temp_path = None
            try:
                # 1. Desbloqueio
                st.write("🔓 Verificando criptografia...")

                # Se o usuário digitou senha, usamos. Se não, tentamos sem.
                senha_teste = password if password else None
                temp_path = unlock_pdf_file(uploaded_file, password=senha_teste)

                if not temp_path:
                    # Se falhou, verificamos se é porque tem senha e o usuário não digitou
                    if check_is_encrypted(uploaded_file) and not password:
                        status.update(label="Erro: Arquivo Protegido", state="error")
                        st.error("🔒 Este arquivo precisa de senha. Digite-a no campo acima e tente novamente.")
                        st.stop()
                    else:
                        status.update(label="Erro no Desbloqueio", state="error")
                        st.error("❌ Falha ao abrir o PDF. Verifique se o arquivo está válido.")
                        st.stop()

                # 2. Extração
                st.write("📝 Extraindo dados inteligentes...")
                df_fin, df_med = extract_data_from_pdf(temp_path)

                if df_fin.empty:
                    status.update(label="Erro de Leitura", state="error")
                    st.error("⚠️ Não conseguimos ler os dados financeiros. O layout pode ser incompatível.")
                    st.stop()

                # Mostra o que achou (Feedback Rápido)
                ref = df_fin["Referência"].iloc[0] if "Referência" in df_fin.columns else "Desconhecido"
                total = df_fin["Valor (R$)"].sum()
                st.write(f"✅ Fatura identificada: **{ref}** (Total: R$ {total:.2f})")

                # 3. Salvamento
                st.write("💾 Salvando no banco de dados...")
                sucesso = save_data(df_fin, df_med)

                if sucesso:
                    status.update(label="Concluído!", state="complete")
                    st.balloons()
                    st.success(f"Fatura de **{ref}** importada com sucesso!")

                    # Reset do Uploader para permitir novo arquivo
                    time.sleep(2)
                    st.session_state["uploader_key"] += 1
                    st.rerun()
                else:
                    status.update(label="Erro ao Salvar", state="error")
                    st.error("Erro ao escrever no banco de dados.")

            except Exception as e:
                status.update(label="Erro Inesperado", state="error")
                st.error(f"Ocorreu um erro: {e}")

            finally:
                # Limpeza
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)

# --- DICA DE RODAPÉ ---
else:
    st.info("💡 Dica: Você pode importar várias faturas uma por uma para construir seu histórico.")
