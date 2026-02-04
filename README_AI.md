Assistente IA — Configuração e Segurança

Este documento descreve como configurar chaves de API para provedores de LLM (Google Gemini, OpenAI, Anthropic) de forma segura.

1) Usar `st.secrets` (recomendado)
- Crie um arquivo `.streamlit/secrets.toml` no diretório do projeto.
- Adicione as chaves no formato:

[llm_api_keys]
google = "GEMINI_API_KEY"
openai = "OPENAI_API_KEY"
anthropic = "ANTHROPIC_API_KEY"

- Reinicie o Streamlit. A aplicação lerá automaticamente as chaves via `st.secrets['llm_api_keys']`.

2) Alternativa: variáveis de ambiente
- Exportar variável de ambiente, exemplo:

export LLM_API_KEY_GOOGLE=GEMINI_API_KEY
export LLM_API_KEY_OPENAI=OPENAI_API_KEY
export LLM_API_KEY_ANTHROPIC=ANTHROPIC_API_KEY

3) Segurança
- Nunca compartilhe suas chaves em repositórios públicos.
- Para produção, prefira serviços de gerenciamento de segredos (AWS Secrets Manager, Google Secret Manager, etc.).

4) Migração Google
- Prefira `google-genai`. Consulte o README do SDK para diferenças de API.

5) Logs
- Logs de modelos/erros são salvos em `logs/` em formato JSON e são sanitizados (chaves mascaradas).
