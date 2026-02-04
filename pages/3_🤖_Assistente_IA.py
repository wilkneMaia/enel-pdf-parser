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
    from pandasai.llm import GoogleGemini
    import google.generativeai as genai
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

# 4. Instância do PandasAI
# Configura a biblioteca base do Google diretamente para evitar defaults antigos
genai.configure(api_key=st.session_state["gemini_api_key"])

# Função para listar modelos Gemini (compatível com variações do SDK)
def fetch_gemini_models():
    try:
        model_names = []
        try:
            resp = genai.list_models()
            if hasattr(resp, 'models'):
                model_names = [m.name for m in resp.models]
            else:
                model_names = [getattr(m, 'name', str(m)) for m in resp]
            return [m for m in model_names if 'gemini' in m.lower()], resp, None
        except Exception:
            resp = genai.models.list()
            model_names = [m.name for m in resp.models]
            return [m for m in model_names if 'gemini' in m.lower()], resp, None
    except NameError as ne:
        return [], None, f"SDK google.generativeai não encontrado: {ne}"
    except Exception as e:
        return [], None, str(e)

# Inicializa cache de modelos em sessão (faz a primeira carga automática)
if 'gemini_models' not in st.session_state:
    models, raw, err = fetch_gemini_models()
    st.session_state['gemini_models'] = models
    st.session_state['gemini_models_raw'] = repr(raw)
    st.session_state['gemini_models_last_error'] = err

# Helper para (re)instanciar GoogleGemini com um modelo específico
def rebuild_llm_with_model(model_name: str):
    new_llm = GoogleGemini(api_key=st.session_state["gemini_api_key"])
    try:
        new_llm.model = model_name
    except Exception:
        pass
    if hasattr(new_llm, '_model'):
        try:
            new_llm._model = model_name
        except Exception:
            pass
    # Alguns wrappers internos podem manter referência ao cliente; tenta atualizar também
    try:
        if hasattr(new_llm, 'google_gemini') and hasattr(new_llm.google_gemini, '_client'):
            try:
                setattr(new_llm.google_gemini, 'model', model_name)
            except Exception:
                pass
    except Exception:
        pass
    return new_llm

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
llm = GoogleGemini(api_key=st.session_state["gemini_api_key"], model=selected_model)

# Retorna o modelo efetivo usado nas chamadas (prefixa com 'models/' quando necessário)
def get_effective_model():
    m = st.session_state.get('gemini_model') or st.session_state.get('gemini_manual_model') or selected_model or "gemini-1.5-flash"
    if m and not str(m).startswith("models/"):
        return f"models/{m}"
    return m

# Aplica um wrapper em genai.generate_content (e tentativas em classes internas) para garantir que o modelo usado seja o selecionado
def patch_genai_generate_content():
    try:
        patched = False
        if hasattr(genai, 'generate_content'):
            orig = genai.generate_content
            def wrapped(*args, **kwargs):
                model = get_effective_model()
                if model:
                    kwargs.setdefault('model', model)
                return orig(*args, **kwargs)
            genai.generate_content = wrapped
            patched = True

        if hasattr(genai, 'generative_models'):
            gm = genai.generative_models
            for attr_name in dir(gm):
                attr = getattr(gm, attr_name)
                try:
                    if isinstance(attr, type) and hasattr(attr, 'generate_content'):
                        orig2 = attr.generate_content
                        def make_wrapped(orig_method):
                            def wrapped_method(self, *args, **kwargs):
                                model = get_effective_model()
                                if model:
                                    kwargs.setdefault('model', model)
                                return orig_method(self, *args, **kwargs)
                            return wrapped_method
                        setattr(attr, 'generate_content', make_wrapped(orig2))
                        patched = True
                except Exception:
                    continue

        st.session_state['genai_patched'] = patched
        return patched
    except Exception as e:
        st.session_state['genai_patched'] = False
        st.warning(f"Falha ao aplicar patch em genai.generate_content: {e}")
        return False

# Aplica o patch imediatamente para interceptar chamadas internas
patch_genai_generate_content()

with st.expander("🔧 Debug: listagem de modelos (mostrar/ocultar)"):
    st.write("Modelos encontrados:", st.session_state.get('gemini_models'))
    st.write("Modelo Selecionado para Uso:", selected_model)
    st.write("Modelo efetivo (para SDK):", get_effective_model())
    st.write("genai patched:", st.session_state.get('genai_patched'))
    st.write("Erro:", st.session_state.get('gemini_models_last_error'))
    st.write("Resposta bruta:", st.session_state.get('gemini_models_raw'))

sdf = SmartDataframe(df_ia, config={"llm": llm, "verbose": True})

# 5. Interface de Chat
st.divider()

col_chat, col_tips = st.columns([2, 1])

with col_tips:
    st.markdown("### 💡 Sugestões")
    st.markdown("- *Qual foi o total gasto em 2024?*")
    st.markdown("- *Qual o mês com a fatura mais cara?*")
    st.markdown("- *Quanto paguei de Iluminação Pública no total?*")
    st.markdown("- *Faça um gráfico de barras dos gastos por mês.*")

with col_chat:
    prompt = st.text_area("💬 Pergunte aos seus dados:", placeholder="Ex: Qual a média de gastos nos últimos 3 meses?")

    if st.button("🚀 Analisar"):
        if prompt:
            with st.spinner("🤖 A IA está analisando seus dados..."):
                try:
                    response = sdf.chat(prompt)
                except Exception as e:
                    err_str = str(e)
                    st.error(f"Erro ao processar: {e}")
                    st.info(f"Modelo efetivo usado na requisição: {get_effective_model()}")
                    # Salva log com stacktrace
                    try:
                        os.makedirs('logs', exist_ok=True)
                        fname = os.path.join('logs', f'pandasai_error_{datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}.log')
                        with open(fname, 'w', encoding='utf-8') as fh:
                            fh.write(traceback.format_exc())
                        st.info(f"Detalhes do erro salvos em {fname}")
                    except Exception as log_e:
                        st.warning(f"Falha ao salvar log de erro: {log_e}")

                    # Tenta recuperar de erros relacionados a modelos indisponíveis
                    if '404' in err_str or 'models/gemini-pro' in err_str or ('not found' in err_str.lower() and 'model' in err_str.lower()) or ('model' in err_str.lower() and 'not found' in err_str.lower()):
                        st.info("Erro relacionado a modelo detectado. Tentando trocar para um modelo disponível e reenviar a requisição...")
                        models, raw, errm = fetch_gemini_models()
                        st.session_state['gemini_models'] = models
                        st.session_state['gemini_models_raw'] = repr(raw)
                        st.session_state['gemini_models_last_error'] = errm
                        if models:
                            new_model = models[0]
                            st.success(f"Tentando novo modelo: {new_model}")
                            # Atualiza seleção em sessão e reaplica o patch para garantir que o SDK use esse modelo
                            st.session_state['gemini_model'] = new_model
                            patch_genai_generate_content()
                            new_llm = rebuild_llm_with_model(new_model)
                            new_sdf = SmartDataframe(df_ia, config={"llm": new_llm, "verbose": True})
                            try:
                                response = new_sdf.chat(prompt)
                                # Atualiza referências para seguintes interações
                                sdf = new_sdf
                                llm = new_llm
                            except Exception as e2:
                                st.error(f"Reenvio com novo modelo falhou: {e2}")
                                with st.expander("📄 Detalhes do erro (mostrar/ocultar)"):
                                    st.exception(e2)
                                response = None
                        else:
                            st.warning("Nenhum modelo alternativo disponível.")
                            response = None
                    else:
                        # Mostrar detalhes para debug
                        with st.expander("📄 Detalhes do erro (mostrar/ocultar)"):
                            st.exception(e)
                        response = None

                # Se houve resposta, mostrar
                if 'response' in locals() and response is not None:
                    st.markdown("### 📝 Resposta:")
                    st.write(response)
        else:
            st.warning("Digite uma pergunta para começar.")
