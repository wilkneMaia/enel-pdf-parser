import streamlit as st
import pandas as pd
import os
import json
import traceback
from datetime import datetime
from src.database.manager import load_data

# Importa os wrappers e factory
from src.services.llm_client import available_providers, list_models, create_adapter, ProviderUnavailable
from src.services.agent_factory import create_agent, available_backends
from src.services.logger import write_llm_log

st.set_page_config(page_title="Assistente IA", page_icon="🤖", layout="wide")

st.title("🤖 Assistente Inteligente")
st.markdown(
    """
    Use Inteligência Artificial para conversa com suas faturas.
    Peça análises, resumos ou gráficos personalizados.
    """
)

# Verificar disponibilidade de backends
backends_available = available_backends()
if not backends_available:
    st.error("⚠️ Nenhum backend de análise disponível. Instale `pandasai` ou `langchain`.")
    st.stop()

# 1. Carregar Dados
df_faturas, df_medicao = load_data()

if df_faturas.empty:
    st.warning("⚠️ Nenhum dado de fatura encontrado. Importe arquivos primeiro.")
    st.stop()

# 2. Configuração da API Key
# Nota: a configuração multi-provedor (Google/OpenAI/Anthropic) foi movida mais abaixo para suportar
# múltiplos backends. A UI colocada lá pede a chave para o provedor selecionado e realiza a listagem
# de modelos dinamicamente.

# 3. Preparação do DataFrame
# Selecionamos colunas chave para otimizar o contexto da IA
cols_relevantes = [
    "Referência",
    "Itens de Fatura",
    "Valor (R$)",
    "Quant.",
    "Unid.",
    "Nº do Cliente",
]
df_ia = df_faturas[[c for c in cols_relevantes if c in df_faturas.columns]].copy()


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
    parts = str(ref).split("/")
    return parts[-1].strip() if len(parts) > 1 else str(ref)


df_ia["Ano"] = df_ia["Referência"].apply(extrair_ano)

# 4. Configuração do Backend de Análise e LLM

# UI: seleção de backend (PandasAI vs LangChain)
all_providers = ["google", "openai", "anthropic"]
installed = set(available_providers())
providers = all_providers

with st.expander(
    "⚙️ Configuração da IA (Backend & Provedor de LLM)", expanded=not st.session_state.get("api_key_configured_any", False)
):
    st.info("Escolha o backend de análise, o provedor de IA e insira a API Key correspondente.")
    
    # Seletor de Backend
    st.subheader("Backend de Análise")
    backend_options = backends_available
    backend_labels = [f"{b.upper()} {'(disponível)' if b in backend_options else '(não instalado)'}" for b in ["pandasai", "langchain"]]
    backend_choice = st.radio(
        "Qual backend deseja usar?",
        backend_labels,
        index=0 if "pandasai" in backends_available else 1,
        key="agent_backend",
    )
    selected_backend = backend_labels.index(backend_choice)
    backend = ["pandasai", "langchain"][selected_backend]
    st.session_state["agent_backend"] = backend
    
    st.divider()
    
    # Seletor de Provedor LLM
    st.subheader("Provedor de LLM")
    # Mostra todas as opções, indicando se o SDK está presente
    provider_labels = [f"{p} {'(instalado)' if p in installed else '(SDK não instalado)'}" for p in providers]
    sel_index = 0
    provider_choice = st.selectbox("Selecione um provedor de IA:", provider_labels, index=sel_index, key="llm_provider")
    provider = providers[provider_labels.index(provider_choice)]

    api_key_label = {
        "google": "Google Gemini API Key",
        "openai": "OpenAI API Key",
        "anthropic": "Anthropic API Key (Claude)",
    }.get(provider, "API Key")

    api_key_input = st.text_input(
        f"Insira sua {api_key_label}:", type="password", key=f"llm_api_key_input_{provider}",
        help="Armazene sua chave com cuidado. Você também pode configurar via variáveis ambiente."
    )

    if api_key_input:
        # Store temporarily in session for convenience; recommend using st.secrets for persistence
        st.session_state[f"llm_api_key_{provider}"] = api_key_input
        st.session_state["api_key_configured_any"] = True
        st.success("API Key configurada para provedor selecionado! Você pode fechar esta aba.")
        st.info("Dica: para segurança, adicione sua chave em Streamlit Secrets (arquivo .streamlit/secrets.toml) ou em variáveis de ambiente. Exemplo (secrets.toml):\n[llm_api_keys]\n" + f"{provider} = \"<SUA_API_KEY>\"")

    if f"llm_api_key_{provider}" not in st.session_state:
        st.warning("🔒 Aguardando API Key para iniciar o LLM selecionado...")
        if provider not in installed:
            st.info("Observação: o SDK para este provedor não está instalado no ambiente. Você ainda pode inserir a API Key e usar a opção manual de modelo, mas algumas funcionalidades (ex: listagem automática de modelos) podem não funcionar até instalar o SDK correspondente.")
        st.stop()

    models_key = f"llm_{provider}_models"
    def get_api_key(p: str):
        # Prefer st.secrets > env var > session_state
        try:
            if hasattr(st, 'secrets') and isinstance(st.secrets, dict):
                keys = st.secrets.get('llm_api_keys') or {}
                if keys and keys.get(p):
                    return keys.get(p)
        except Exception:
            pass
        # Env var fallback
        env_key = os.environ.get(f"LLM_API_KEY_{p.upper()}") or os.environ.get(f"{p.upper()}_API_KEY")
        if env_key:
            return env_key
        return st.session_state.get(f"llm_api_key_{p}")

    if models_key not in st.session_state:
        api_key_val = get_api_key(provider)
        models, err = list_models(provider, api_key_val)
        st.session_state[models_key] = models
        st.session_state[f"{models_key}_raw"] = repr(models)
        st.session_state[f"{models_key}_last_error"] = err

    col_models1, col_models2 = st.columns([3, 1])
    with col_models1:
        if st.session_state.get(models_key):
            selected_model = st.selectbox(
                f"Selecione um modelo ({provider}):",
                st.session_state[models_key],
                index=0,
                key=f"{provider}_model_select",
            )
        else:
            st.warning(
                f"Nenhum modelo listado para {provider} — informe um modelo manualmente ou recarregue."
            )
            selected_model = st.text_input(
                f"Informe modelo manualmente (ex: gemini-1.5-flash):",
                value="",
                key=f"{provider}_manual_model",
            )

    with col_models2:
        disabled_buttons = provider not in installed
        if st.button("🔄 Recarregar modelos", disabled=disabled_buttons):
            api_key_val = get_api_key(provider)
            models, err = list_models(provider, api_key_val)
            st.session_state[models_key] = models
            st.session_state[f"{models_key}_raw"] = repr(models)
            st.session_state[f"{models_key}_last_error"] = err
            # structured log (sanitized)
            try:
                write_llm_log(f"{provider}_models_list", {"provider": provider, "models_count": len(models), "error": err, "api_key_provided": bool(api_key_val)})
            except Exception:
                pass
            st.experimental_rerun()

        if st.button("🧪 Testar conexão", disabled=disabled_buttons):
            api_key_val = get_api_key(provider)
            models, err = list_models(provider, api_key_val)
            st.session_state[models_key] = models
            st.session_state[f"{models_key}_raw"] = repr(models)
            st.session_state[f"{models_key}_last_error"] = err
            if err:
                st.error(f"Teste falhou: {err}")
            else:
                count = len(models)
                st.success(f"Conexão OK — {count} modelo(s) encontrados para {provider}.")
                if models:
                    st.info(f"Exemplo: {models[0]}")
            # structured log
            try:
                write_llm_log(f"{provider}_models_test", {"provider": provider, "models_count": len(models), "error": err, "api_key_provided": bool(api_key_val)})
            except Exception:
                pass

# Helper para (re)instanciar adapter LLM com modelo específico

def rebuild_llm_with_model(provider_name: str, model_name: str):
    try:
        api_key = st.session_state.get(f"llm_api_key_{provider_name}")
        if not api_key:
            raise ProviderUnavailable("API key não configurada para o provedor selecionado")
        return create_adapter(provider_name, api_key, model_name)
    except ProviderUnavailable as e:
        st.error(f"Erro ao construir LLM adapter: {e}")
        return None
    except Exception as e:
        st.error(f"Erro inesperado ao construir LLM adapter: {e}")
        return None

# Instancia o LLM com o modelo selecionado
llm = rebuild_llm_with_model(provider, selected_model)

# Debug info para exibir no expander

with st.expander("🔧 Debug: listagem de modelos (mostrar/ocultar)"):
    st.write("Backend selecionado:", backend)
    st.write("Provedor selecionado:", provider)
    st.write("Modelos encontrados:", st.session_state.get(f"llm_{provider}_models"))
    st.write("Modelo Selecionado para Uso:", selected_model)
    st.write("Erro:", st.session_state.get(f"llm_{provider}_models_last_error"))
    st.write("Resposta bruta:", st.session_state.get(f"llm_{provider}_models_raw"))

# Dicionário de metadados para ajudar a IA a entender o contexto das colunas
field_descriptions = {
    "Referência": "Mês e ano de referência da fatura (ex: JAN/2024). Use para filtrar datas.",
    "Itens de Fatura": "Descrição detalhada do item cobrado (ex: Consumo Energia, Contrib Ilum Publica).",
    "Valor (R$)": "Valor monetário do item. Valores negativos indicam descontos, devoluções ou injeção de energia solar.",
    "Quant.": "Quantidade consumida ou medida (geralmente em kWh).",
    "Unid.": "Unidade de medida (kWh, dias, un).",
    "Nº do Cliente": "Identificador único da instalação/cliente.",
    "Categoria": "Categoria agrupada do item (Iluminação Pública, Impostos, Energia, Bandeiras, etc).",
    "Ano": "Ano da fatura extraído da referência (ex: 2024, 2025).",
}

# Instancia o agente (PandasAI ou LangChain) via factory
try:
    agent = create_agent(
        backend=backend,
        df=df_ia,
        llm=llm,
        config={
            "verbose": True,
            "field_descriptions": field_descriptions,
        },
    )
except ValueError as e:
    st.error(f"Erro ao criar agente: {e}")
    st.stop()

# 5. Interface de Chat
st.divider()

with st.sidebar:
    st.divider()
    st.markdown("### 💡 Sugestões")
    st.markdown("- *Qual foi o total gasto em 2025?*")
    st.markdown("- *Qual o mês com a fatura mais cara?*")
    st.markdown("- *Quanto paguei de Iluminação Pública no total?*")
    # st.markdown("- *Faça um gráfico de barras dos gastos por mês.*")

    st.divider()
    if st.button("🗑️ Limpar Conversa", use_container_width=True):
        st.session_state["messages"] = []
        st.rerun()

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
                response = agent.chat(prompt)
            except Exception as e:
                err_str = str(e)
                # Log silencioso
                try:
                    os.makedirs("logs", exist_ok=True)
                    fname = os.path.join(
                        "logs",
                        f"agent_error_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.log",
                    )
                    with open(fname, "w", encoding="utf-8") as fh:
                        fh.write(traceback.format_exc())
                except:
                    pass

                # Lógica de Retry (Modelo não encontrado)
                if "No code found" in err_str:
                    st.warning(
                        "⚠️ Desculpe, só posso responder perguntas relacionadas aos seus dados de energia ou ao funcionamento do sistema."
                    )

                elif "404" in err_str or "not found" in err_str.lower():
                    st.warning("Modelo indisponível. Tentando alternativo...")
                    api_key = st.session_state.get(f"llm_api_key_{provider}")
                    models, err = list_models(provider, api_key)
                    if models:
                        new_model = models[0]
                        st.session_state[f"llm_{provider}_selected_model"] = new_model
                        new_llm = rebuild_llm_with_model(provider, new_model)
                        if new_llm is not None:
                            try:
                                new_agent = create_agent(
                                    backend=backend,
                                    df=df_ia,
                                    llm=new_llm,
                                    config={"verbose": True, "field_descriptions": field_descriptions},
                                )
                                response = new_agent.chat(prompt)
                            except Exception as e2:
                                st.error(f"Falha no reenvio: {e2}")
                        else:
                            st.error("Não foi possível instanciar o adapter para o novo modelo.")
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
                    st.session_state["messages"].append(
                        {"role": "assistant", "content": friendly_msg}
                    )
                else:
                    st.write(response)
                    st.session_state["messages"].append(
                        {"role": "assistant", "content": response}
                    )
