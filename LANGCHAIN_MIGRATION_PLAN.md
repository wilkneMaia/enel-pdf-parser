# Plano de Migração: PandasAI → LangChain

## 1. Visão Geral
Migrar da orquestração simples (PandasAI SmartDataframe) para um framework de cadeia de prompts/agentes (LangChain) com suporte a:
- Histórico conversacional persistente e contextualizado
- Recuperação aumentada (RAG) sobre documentos/PDFs
- Execução de múltiplos passos (parse PDF → extrair dados → análise → gerar relatório)
- Ferramentas customizadas (queries SQL, API calls, manipulação de DataFrames)

## 2. Passos Mínimos de Migração

### Fase 1: Setup de Dependências (Semana 1)
```bash
uv add langchain langchain-community langchain-openai
uv add langchain-anthropic langchain-google-genai
uv add langchain-text-splitters pypdf python-dotenv
```

### Fase 2: Abstração LLM → LangChain (Semana 1-2)
**Novo arquivo**: `src/services/langchain_client.py`
- Wrapper unificado sobre LangChain LLMs (Google, OpenAI, Anthropic)
- Interface compatível com atual `llm_client.py` para transição gradual
- Exemplo:
  ```python
  from langchain_openai import ChatOpenAI
  from langchain_google_genai import ChatGoogleGenerativeAI
  from langchain_anthropic import ChatAnthropic

  def create_langchain_llm(provider: str, api_key: str, model: str):
      if provider == "google":
          return ChatGoogleGenerativeAI(api_key=api_key, model=model)
      elif provider == "openai":
          return ChatOpenAI(api_key=api_key, model=model)
      elif provider == "anthropic":
          return ChatAnthropic(api_key=api_key, model=model)
  ```

### Fase 3: Converter SmartDataframe → Pandas Agent (Semana 2)
**Novo arquivo**: `src/services/langchain_pandas_agent.py`
- Use `langchain.agents.create_pandas_dataframe_agent()`
- Substitui a lógica de `SmartDataframe.chat()` com mais flexibilidade
- Exemplo:
  ```python
  from langchain.agents import create_pandas_dataframe_agent
  
  agent = create_pandas_dataframe_agent(
      llm=llm,
      df=df_ia,
      agent_type="openai-tools",
      verbose=True,
  )
  result = agent.invoke({"input": "Qual é o total gasto em 2025?"})
  ```

### Fase 4: Adicionar Memory/Histórico (Semana 2-3)
**Novo arquivo**: `src/services/langchain_memory.py`
- Implementar `ConversationBufferMemory` ou `ConversationSummaryMemory`
- Persistir em SQLite/JSON para entre-sessões
- Exemplo:
  ```python
  from langchain.memory import ConversationBufferMemory
  from langchain.chains import ConversationChain
  
  memory = ConversationBufferMemory()
  chain = ConversationChain(llm=llm, memory=memory, verbose=True)
  ```

### Fase 5: Integrar em `pages/3_🤖_Assistente_IA.py` (Semana 3)
- Substituir `SmartDataframe` por `create_pandas_dataframe_agent()`
- Adicionar memory para histórico entre mensagens
- Usar novo `langchain_client.py` para LLM setup
- Testar com mesmos dados/queries existentes

### Fase 6: Adicionar RAG (Opcional, Semana 4+)
**Se decidir incluir busca em PDFs/histórico de faturas:**
- Use `langchain.document_loaders.PDFPlumberLoader` (compatível com seu `pdfplumber`)
- Integrate embedding + vector store (FAISS, Chroma, Pinecone)
- Chain: `RetrievalQA` ou `RetrievalAgentExecutor`

## 3. Riscos e Mitigação

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Quebra de compatibilidade com prompts PandasAI | Alto | Manter `llm_client.py` em paralelo; testar prompts lado-a-lado |
| Custo de tokens aumenta (histórico + memory) | Médio | Implementar `ConversationSummaryMemory`; limpar histórico antigo |
| Performance pior com DataFrames grandes | Médio | Usar `tools_for_pandas_agent` com pré-filtros; cache queries |
| Dependências adicionais inflam projeto | Baixo | Usar `extras` do LangChain; remover PandasAI quando deprecated |
| Transição quebra fluxo do usuário | Alto | Parallelizar ambos; switch via flag de env `USE_LANGCHAIN=true` |

## 4. Timeline Estimada
- **Semana 1**: Setup deps + abstração LLM + testes unitários
- **Semana 2**: Pandas agent + primeira integração UI (lado-a-lado)
- **Semana 3**: Memory + histórico persistente + testes E2E
- **Semana 4+**: RAG (se desejado) + cleanup PandasAI

## 5. Exemplo de Código (Não Aplicado — Apenas Referência)

### `src/services/langchain_client.py`
```python
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic

def create_langchain_llm(provider: str, api_key: str, model: str):
    """Create a LangChain LLM instance."""
    if provider == "google":
        return ChatGoogleGenerativeAI(api_key=api_key, model=model, temperature=0.7)
    elif provider == "openai":
        return ChatOpenAI(api_key=api_key, model=model, temperature=0.7)
    elif provider == "anthropic":
        return ChatAnthropic(api_key=api_key, model=model, temperature=0.7)
    else:
        raise ValueError(f"Unknown provider: {provider}")
```

### `src/services/langchain_pandas_agent.py`
```python
from langchain.agents import create_pandas_dataframe_agent
from langchain.memory import ConversationBufferMemory

def create_analyst_agent(llm, df, memory=None):
    """Create a PandasAI-like agent using LangChain."""
    agent = create_pandas_dataframe_agent(
        llm=llm,
        df=df,
        agent_type="openai-tools",
        verbose=True,
    )
    return agent

# Usage in Streamlit:
# agent = create_analyst_agent(llm, df_ia)
# result = agent.invoke({"input": user_prompt})
# st.write(result["output"])
```

## 6. Decisão: Continuar com PandasAI ou Migrar?

**Recomendação**: Manter PandasAI no curto prazo; preparar migração gradual se:
- ✅ Usuários pedem histórico conversacional persistente
- ✅ Necessidade de RAG (busca em faturas anteriores/contexto longo)
- ✅ Fluxos multi-step (gerar análise → exportar relatório → enviar email)
- ❌ Caso contrário, PandasAI é suficiente e mais simples

---

**Próximos Passos Recomendados:**
1. Levantar requisitos específicos de orquestração (RAG? History? Tools?)
2. Criar branch `feature/langchain-exploration` com código experimental
3. Benchmark: custo de tokens, latência, qualidade de respostas (PandasAI vs LangChain)
4. Validar com stakeholders antes de full commit
