import streamlit as st
import pandas as pd
import os
import sys
from dotenv import load_dotenv
import time

# --- BLOCO DE IMPORTAÇÃO (Mantido) ---
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

try:
    from extractor import extract_invoice_data
except ImportError:
    from src.extractor import extract_invoice_data

try:
    from database_manager import save_invoice_data
except ImportError:
    st.error("❌ Arquivo 'database_manager.py' não encontrado na raiz.")
    st.stop()

load_dotenv()
PDF_PASSWORD = os.getenv("PDF_PASSWORD")

st.set_page_config(page_title="Importar Fatura", page_icon="📂")
st.title("📂 Importação Manual de Faturas")


# --- FUNÇÃO AUXILIAR DE CONVERSÃO ---
def universal_converter(val):
    if pd.isna(val) or str(val).strip() == "":
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().upper().replace("R$", "").replace(" ", "").replace("-", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        sign = -1.0 if "-" in str(val) else 1.0
        return float(s) * sign
    except ValueError:
        return 0.0


# --- GERENCIAMENTO DE ESTADO (O SEGREDO DO RESET) ---
if "dados_processados" not in st.session_state:
    st.session_state["dados_processados"] = None
if "ultimo_arquivo" not in st.session_state:
    st.session_state["ultimo_arquivo"] = None

# Esta chave controla o reset do widget de upload
if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0

# --- WIDGET DE UPLOAD (Com chave dinâmica) ---
# Toda vez que uploader_key muda, este componente é recriado do zero (limpo)
uploaded_file = st.file_uploader(
    "Arraste ou Selecione o PDF aqui",
    type=["pdf"],
    key=f"pdf_uploader_{st.session_state['uploader_key']}",
)

# --- LÓGICA DE PROCESSAMENTO ---
if uploaded_file:
    # Verifica se é um arquivo novo
    arquivo_novo = st.session_state["ultimo_arquivo"] != uploaded_file.name

    # Processa se for novo ou se a memória estiver vazia
    if arquivo_novo or st.session_state["dados_processados"] is None:
        with st.spinner("⚡ Processando PDF automaticamente..."):
            try:
                uploaded_file.seek(0)
                data = extract_invoice_data(uploaded_file, password=PDF_PASSWORD)

                if data and data.get("items"):
                    # Processamento
                    client_id = data.get("client_id", "N/A")
                    ref = data.get("reference", "N/A")
                    items = data.get("items", [])
                    meas = data.get("measurement", [])

                    # Conversão Numérica
                    final_items = []
                    cols_num = [
                        "Quant.",
                        "Preço unit (R$) com tributos",
                        "Valor (R$)",
                        "PIS/COFINS",
                        "Base Calc ICMS (R$)",
                        "Alíquota ICMS",
                        "ICMS",
                        "Tarifa unit (R$)",
                    ]

                    for i in items:
                        item_clean = i.copy()
                        item_clean["Nº do Cliente"] = client_id
                        item_clean["Referência"] = ref
                        for col in cols_num:
                            if col in item_clean:
                                item_clean[col] = universal_converter(item_clean[col])
                        item_clean["Valor (R$)"] = universal_converter(
                            item_clean.get("Valor (R$)")
                        )
                        final_items.append(item_clean)

                    final_meas = []
                    for m in meas:
                        m_clean = m.copy()
                        m_clean["Nº do Cliente"] = client_id
                        m_clean["Referência"] = ref
                        for col in [
                            "Leitura (Anterior)",
                            "Leitura (Atual)",
                            "Fator Multiplicador",
                            "Consumo kWh",
                        ]:
                            if col in m_clean:
                                m_clean[col] = universal_converter(m_clean[col])
                        final_meas.append(m_clean)

                    st.session_state["dados_processados"] = {
                        "filename": uploaded_file.name,
                        "client_id": client_id,
                        "reference": ref,
                        "items": final_items,
                        "meas": final_meas,
                    }
                    st.session_state["ultimo_arquivo"] = uploaded_file.name
                    st.rerun()
                else:
                    st.error(
                        "⚠️ O PDF foi lido, mas não encontramos dados. Verifique o arquivo."
                    )
                    st.session_state["dados_processados"] = None
                    st.session_state["ultimo_arquivo"] = uploaded_file.name
            except Exception as e:
                st.error(f"Erro ao processar: {e}")
                st.session_state["dados_processados"] = None

# --- EXIBIÇÃO E AÇÃO ---
if uploaded_file and st.session_state["dados_processados"]:
    if st.session_state["dados_processados"]["filename"] == uploaded_file.name:
        dados = st.session_state["dados_processados"]

        st.divider()
        st.info("✅ Arquivo processado. Confira os dados abaixo:")

        # Resumo Compacto
        c1, c2, c3 = st.columns(3)
        total = sum(i["Valor (R$)"] for i in dados["items"])
        c1.metric("Cliente", dados["client_id"])
        c2.metric("Referência", dados["reference"])
        c3.metric("Total", f"R$ {total:,.2f}")

        # Tabela (Expansível para economizar espaço)
        with st.expander("Ver Detalhes dos Itens"):
            st.dataframe(pd.DataFrame(dados["items"]), use_container_width=True)

        st.markdown("---")

        # --- BOTÃO DE SALVAR E LIMPAR ---
        if st.button(
            "💾 Salvar e Limpar Tela", type="primary", use_container_width=True
        ):
            try:
                # 1. Salva no Disco
                status_inv, status_meas = save_invoice_data(
                    dados["items"], dados["meas"]
                )

                # 2. Limpa o Cache da Home (Importante!)
                st.cache_data.clear()

                # 3. Notificação Bonita
                st.toast(f"Sucesso! Fatura de {dados['reference']} salva.", icon="🎉")

                # --- O TRUQUE DO RESET ---
                st.session_state["dados_processados"] = None  # Limpa dados
                st.session_state["ultimo_arquivo"] = None  # Limpa referência
                st.session_state["uploader_key"] += 1  # FORÇA O RESET DO UPLOADER

                # 4. Mensagem Final e Recarregamento
                time.sleep(1)  # Dá um tempinho para ver o Toast
                st.rerun()  # Recarrega a página (que virá limpa)

            except Exception as e:
                st.error(f"Erro ao gravar: {e}")

# --- MENSAGEM DE BOAS VINDAS (Quando a tela está vazia) ---
elif not uploaded_file:
    # Se acabamos de salvar e limpar, mostramos uma confirmação
    if "uploader_key" in st.session_state and st.session_state["uploader_key"] > 0:
        st.success("✨ Arquivo salvo com sucesso! Pronto para o próximo.")
