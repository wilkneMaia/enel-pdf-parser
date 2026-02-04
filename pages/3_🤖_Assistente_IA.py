import streamlit as st
import pandas as pd
import os
import json
import traceback
from datetime import datetime
from src.database.manager import load_data

# Tenta importar PandasAI, se não tiver, avisa o usuário
try:
    from pandasai import SmartDataframe
    from pandasai.llm import LLM
    from google import genai
    PANDASAI_AVAILABLE = True
    import_error = None
except Exception as e:
    PANDASAI_AVAILABLE = False
    import_error = e

st.set_page_config(page_title="Assistente IA", page_icon="🤖", layout="wide")

st.title("🤖 Assistente Inteligente (PandasAI)")
st.markdown(
    """
    Use Inteligência Artificial para conversar com suas faturas.
    Peça análises, resumos ou gráficos personalizados.
    """
)

if not PANDASAI_AVAILABLE:
    st.error("⚠️ A biblioteca `pandasai` foi detectada, mas falhou ao carregar.")
    st.error(f"**Erro:** `{import_error}`")
    st.info("Dica: Se estiver usando `uv`, certifique-se de rodar o streamlit dentro do ambiente correto (ex: `uv run streamlit run ...`).")
    st.stop()

# 1. Carregar Dados
df_faturas, df_medicao = load_data()

if df_faturas.empty:
    st.warning("⚠️ Nenhum dado de fatura encontrado. Importe arquivos primeiro.")
    st.stop()

# 2. Configuração da API Key
with st.expander("⚙️ Configuração da IA (Google Gemini)", expanded=not st.session_state.get("api_key_configured", False)):
    st.info("Para usar este recurso, você precisa de uma API Key do Google Gemini (gratuita).")
    api_key_input = st.text_input("Insira sua Google API Key:", type="password", help="Obtenha em: https://aistudio.google.com/")

    if api_key_input:
        st.session_state["gemini_api_key"] = api_key_input
        st.session_state["api_key_configured"] = True
        st.success("API Key configurada! Pode fechar esta aba.")

if "gemini_api_key" not in st.session_state:
    st.warning("🔒 Aguardando API Key para iniciar o cérebro da IA...")
    st.stop()

# 3. Preparação do DataFrame
# Selecionamos colunas chave para otimizar o contexto da IA
cols_relevantes = ['Referência', 'Itens de Fatura', 'Valor (R$)', 'Quant.', 'Unid.', 'Nº do Cliente']
df_ia = df_faturas[ [c for c in cols_relevantes if c in df_faturas.columns] ].copy()

# --- ENRIQUECIMENTO DE DADOS PARA IA ---
# 1. Classificação de Itens (Para a IA não se perder em nomes técnicos)
def classificar_item_ia(nome):
    nome_upper = str(nome).upper()
    if any(x in nome_upper for x in ["CIP", "ILUM", "PUB", "MUNICIPAL"]):
        return "Iluminação Pública"
    if any(x in nome_upper for x in ["BANDEIRA", "AMARELA", "VERMELHA", "ESCASSEZ"]):
        return "Bandeiras Tarifárias"
    if any(x in nome_upper for x in ["MULTA", "JUROS", "ATUALIZAÇÃO"]):
        return "Multas e Juros"
    if any(x in nome_upper for x in ["TRIBUTO", "IMPOSTO", "ICMS", "PIS", "COFINS"]):
        return "Impostos"
    return "Energia e Outros"

df_ia["Categoria"] = df_ia["Itens de Fatura"].apply(classificar_item_ia)

# 2. Extração de Ano (Para facilitar filtros de tempo)
def extrair_ano(ref):
    parts = str(ref).split('/')
    return parts[-1].strip() if len(parts) > 1 else str(ref)

df_ia["Ano"] = df_ia["Referência"].apply(extrair_ano)

# 4. Instância do PandasAI

# Adapter customizado para usar google-genai (novo SDK) com PandasAI
class GoogleGenaiAdapter(LLM):
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        self.api_key = api_key
        self.model = model
        self.client = genai.Client(api_key=api_key)

    @property
    def type(self) -> str:
        return "google-genai"

    def call(self, instruction, value, suffix="") -> str:
        # Instrução de segurança para restringir o escopo da IA
        safety_prompt = (
            "\n\n[SYSTEM INSTRUCTION]\n"
            "You are an assistant specialized in energy bill analysis (Enel PDF Parser). "
            "The dataset has been enriched with columns 'Categoria' and 'Ano' to help you.\n"
            "1. USE 'Categoria' column for filtering items. Categories are: 'Iluminação Pública', 'Bandeiras Tarifárias', 'Multas e Juros', 'Impostos', 'Energia e Outros'.\n"
            "   Example: If asked about 'Iluminação Pública', filter `df[df['Categoria'] == 'Iluminação Pública']`.\n"
            "2. USE 'Ano' column for filtering by year (it contains strings like '2024', '2025').\n"
            "You MUST ONLY answer questions related to the provided data (consumption, costs, dates, taxes) or the system. "
            "If the user asks about unrelated topics (general knowledge, sports, jokes, politics), DO NOT generate code. "
            "Instead, reply directly in Portuguese: 'Desculpe, só posso responder perguntas sobre seus dados de energia.'"
        )
        prompt = f"{instruction}\n{safety_prompt}\n{value}\n{suffix}"
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt
        )
        return response.text

# Função para listar modelos Gemini (compatível com variações do SDK)
def fetch_gemini_models():
    try:
        client = genai.Client(api_key=st.session_state["gemini_api_key"])
        resp = list(client.models.list())
        model_names = [m.name for m in resp]
        return [m for m in model_names if 'gemini' in m.lower()], str(resp), None
    except Exception as e:
        return [], None, f"Erro ao listar modelos: {str(e)}"

# Inicializa cache de modelos em sessão (faz a primeira carga automática)
if 'gemini_models' not in st.session_state:
    models, raw, err = fetch_gemini_models()
    st.session_state['gemini_models'] = models
    st.session_state['gemini_models_raw'] = repr(raw)
    st.session_state['gemini_models_last_error'] = err

# Helper para (re)instanciar GoogleGemini com um modelo específico
def rebuild_llm_with_model(model_name: str):
    return GoogleGenaiAdapter(api_key=st.session_state["gemini_api_key"], model=model_name)

# UI: seleção e recarga de modelos
col_models1, col_models2 = st.columns([3, 1])
with col_models1:
    if st.session_state.get('gemini_models'):
        selected_model = st.selectbox("Selecione um modelo Gemini:", st.session_state['gemini_models'], index=0, key="gemini_model")
    else:
        st.warning("Nenhum modelo Gemini listado — você pode informar um modelo manualmente ou recarregar.")
        selected_model = st.text_input("Informe modelo manualmente (ex: gemini-1.5-flash):", value="gemini-1.5-flash", key="gemini_manual_model")

with col_models2:
    if st.button("🔄 Recarregar modelos"):
        models, raw, err = fetch_gemini_models()
        st.session_state['gemini_models'] = models
        st.session_state['gemini_models_raw'] = repr(raw)
        st.session_state['gemini_models_last_error'] = err
        st.experimental_rerun()

    if st.button("🧪 Testar conexão"):
        models, raw, err = fetch_gemini_models()
        st.session_state['gemini_models'] = models
        st.session_state['gemini_models_raw'] = repr(raw)
        st.session_state['gemini_models_last_error'] = err
        if err:
            st.error(f"Teste falhou: {err}")
        else:
            count = len(models)
            st.success(f"Conexão OK — {count} modelo(s) Gemini encontrados.")
            if models:
                st.info(f"Exemplo: {models[0]}")
        # Grava resposta bruta em logs para auditoria
        try:
            os.makedirs('logs', exist_ok=True)
            fname = os.path.join('logs', f'gemini_models_response_{datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}.log')
            with open(fname, 'w', encoding='utf-8') as fh:
                json.dump({'models': models, 'raw': repr(raw), 'error': err}, fh, ensure_ascii=False, indent=2)
            st.info(f"Resposta bruta salva em: {fname}")
        except Exception as e:
            st.warning(f"Não foi possível salvar log: {e}")

# Instancia o LLM com o modelo selecionado (CRUCIAL: passar o modelo no construtor)
llm = GoogleGenaiAdapter(api_key=st.session_state["gemini_api_key"], model=selected_model)

# Retorna o modelo efetivo usado nas chamadas (prefixa com 'models/' quando necessário)
def get_effective_model():
    m = st.session_state.get('gemini_model') or st.session_state.get('gemini_manual_model') or selected_model or "gemini-1.5-flash"
    if m and not str(m).startswith("models/"):
        return f"models/{m}"
    return m

with st.expander("🔧 Debug: listagem de modelos (mostrar/ocultar)"):
    st.write("Modelos encontrados:", st.session_state.get('gemini_models'))
    st.write("Modelo Selecionado para Uso:", selected_model)
    st.write("Modelo efetivo (para SDK):", get_effective_model())
    st.write("Erro:", st.session_state.get('gemini_models_last_error'))
    st.write("Resposta bruta:", st.session_state.get('gemini_models_raw'))

sdf = SmartDataframe(df_ia, config={
    "llm": llm,
    "verbose": True,
    "custom_whitelisted_dependencies": ["locale"]
})

# 5. Interface de Chat
st.divider()

with st.sidebar:
    st.divider()
    st.markdown("### 💡 Sugestões")
    st.markdown("- *Qual foi o total gasto em 2024?*")
    st.markdown("- *Qual o mês com a fatura mais cara?*")
    st.markdown("- *Quanto paguei de Iluminação Pública no total?*")
    # st.markdown("- *Faça um gráfico de barras dos gastos por mês.*")

# Inicializa histórico de mensagens
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# Exibe mensagens anteriores
for msg in st.session_state["messages"]:
    avatar = "👤" if msg["role"] == "user" else "🤖"
    with st.chat_message(msg["role"], avatar=avatar):
        st.write(msg["content"])

# Input de Chat (Fixo na parte inferior)
if prompt := st.chat_input("💬 Pergunte aos seus dados (Ex: Qual a média de gastos?)"):
    # 1. Exibe mensagem do usuário
    st.chat_message("user", avatar="👤").write(prompt)
    st.session_state["messages"].append({"role": "user", "content": prompt})

    # 2. Processamento da IA
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("🤖 Analisando..."):
            response = None
            try:
                response = sdf.chat(prompt)
            except Exception as e:
                err_str = str(e)
                # Log silencioso
                try:
                    os.makedirs('logs', exist_ok=True)
                    fname = os.path.join('logs', f'pandasai_error_{datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}.log')
                    with open(fname, 'w', encoding='utf-8') as fh:
                        fh.write(traceback.format_exc())
                except: pass

                # Lógica de Retry (Modelo não encontrado)
                if "No code found" in err_str:
                    st.warning("⚠️ Desculpe, só posso responder perguntas relacionadas aos seus dados de energia ou ao funcionamento do sistema.")

                elif '404' in err_str or 'not found' in err_str.lower():
                    st.warning("Modelo indisponível. Tentando alternativo...")
                    models, _, _ = fetch_gemini_models()
                    if models:
                        new_model = models[0]
                        st.session_state['gemini_model'] = new_model
                        new_llm = rebuild_llm_with_model(new_model)
                        new_sdf = SmartDataframe(df_ia, config={
                            "llm": new_llm,
                            "verbose": True,
                            "custom_whitelisted_dependencies": ["locale"]
                        })
                        try:
                            response = new_sdf.chat(prompt)
                        except Exception as e2:
                            st.error(f"Falha no reenvio: {e2}")
                    else:
                        st.error(f"Erro: {e}")
                else:
                    st.error(f"Erro ao processar: {e}")

            # 3. Exibe e salva resposta
            if response is not None:
                # Intercepta erro de "No code found" retornado como texto pelo PandasAI
                if isinstance(response, str) and "No code found" in response:
                    friendly_msg = "⚠️ Desculpe, só posso responder perguntas relacionadas aos seus dados de energia ou ao funcionamento do sistema."
                    st.warning(friendly_msg)
                    st.session_state["messages"].append({"role": "assistant", "content": friendly_msg})
                else:
                    st.write(response)
                    st.session_state["messages"].append({"role": "assistant", "content": response})
