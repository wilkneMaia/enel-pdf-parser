"""
Agent Factory: Abstração para suportar múltiplos backends de análise (PandasAI, LangChain).
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
import pandas as pd


class Agent(ABC):
    """Interface abstrata para agentes de análise."""

    @abstractmethod
    def chat(self, prompt: str) -> str:
        """
        Processa uma pergunta e retorna uma resposta.

        Args:
            prompt: Pergunta do usuário

        Returns:
            Resposta textual (ou representação de gráfico, etc.)
        """
        pass


class PandasAIAgent(Agent):
    """Wrapper para PandasAI SmartDataframe."""

    def __init__(self, sdf: "SmartDataframe"):  # type: ignore
        """
        Inicializa com instância SmartDataframe.

        Args:
            sdf: Instância do SmartDataframe do PandasAI
        """
        self.sdf = sdf

    def chat(self, prompt: str) -> str:
        """Delega para SmartDataframe.chat()."""
        try:
            result = self.sdf.chat(prompt)
            return str(result)
        except Exception as e:
            raise RuntimeError(f"PandasAI error: {e}")


class LangChainAgent(Agent):
    """Wrapper para LangChain Pandas DataFrame Agent."""

    def __init__(self, agent_executor: Any):
        """
        Inicializa com executor de agente LangChain.

        Args:
            agent_executor: Resultado de create_pandas_dataframe_agent()
        """
        self.agent = agent_executor

    def chat(self, prompt: str) -> str:
        """Invoca o agente LangChain e retorna resultado."""
        try:
            result = self.agent.invoke({"input": prompt})
            # LangChain retorna dict com chave "output"
            if isinstance(result, dict):
                return str(result.get("output", result))
            return str(result)
        except Exception as e:
            raise RuntimeError(f"LangChain error: {e}")


def create_agent(
    backend: str,
    df: pd.DataFrame,
    llm: Any = None,
    *,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    config: Optional[dict] = None,
) -> Agent:
    """
    Factory function para criar agente baseado no backend selecionado.

    Args:
        backend: "pandasai" ou "langchain"
        df: DataFrame para análise
        llm: Instância LLM (compatível com PandasAI e LangChain)
        config: Configuração adicional (opcional)

    Returns:
        Instância de Agent (PandasAIAgent ou LangChainAgent)

    Raises:
        ValueError: Se backend inválido ou dependência faltando
    """
    config = config or {}

    if backend.lower() == "pandasai":
        try:
            from pandasai import SmartDataframe

            field_descriptions = config.get("field_descriptions", {})
            sdf = SmartDataframe(
                df,
                config={
                    "llm": llm,
                    "verbose": config.get("verbose", False),
                    "custom_whitelisted_dependencies": ["locale"],
                    "field_descriptions": field_descriptions,
                },
            )
            return PandasAIAgent(sdf)
        except ImportError:
            raise ValueError("pandasai package not found. Install with: pip install pandasai")

    elif backend.lower() == "langchain":
        try:
            # Tenta importar a fábrica de agentes (várias localizações possíveis)
            try:
                from langchain.agents import create_pandas_dataframe_agent
            except Exception:
                try:
                    from langchain_experimental.agents import create_pandas_dataframe_agent  # type: ignore
                except Exception as e:
                    raise

            # If caller already passed a LangChain-native LLM (supports bind), use it
            native_llm = None
            if llm is not None and hasattr(llm, "bind"):
                native_llm = llm

            # Otherwise, build a LangChain-native LLM from provider/api_key/model
            if native_llm is None:
                if not provider or not api_key:
                    raise ValueError("provider and api_key are required to create a LangChain LLM")

                # OpenAI
                if provider == "openai":
                    try:
                        from langchain.chat_models import ChatOpenAI

                        native_llm = ChatOpenAI(model_name=model or "gpt-4o", openai_api_key=api_key)
                    except Exception:
                        try:
                            # alternative import path
                            from langchain_openai import ChatOpenAI  # type: ignore

                            native_llm = ChatOpenAI(model_name=model or "gpt-4o", openai_api_key=api_key)
                        except Exception as e:
                            raise ImportError(f"OpenAI LangChain class import failed: {e}")

                # Anthropic
                elif provider == "anthropic":
                    try:
                        from langchain.chat_models import ChatAnthropic  # type: ignore

                        native_llm = ChatAnthropic(model=model or "claude-2", anthropic_api_key=api_key)
                    except Exception:
                        try:
                            from langchain_anthropic import ChatAnthropic  # type: ignore

                            native_llm = ChatAnthropic(model=model or "claude-2", anthropic_api_key=api_key)
                        except Exception as e:
                            raise ImportError(f"Anthropic LangChain class import failed: {e}")

                # Google Genie / GenAI
                elif provider == "google":
                    try:
                        # try canonical langchain chat model
                        from langchain.chat_models import ChatGoogleGemini  # type: ignore

                        native_llm = ChatGoogleGemini(model=model or "gemini-1.5-flash", google_api_key=api_key)
                    except Exception:
                        try:
                            # fallback to langchain-google-genai package
                            from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore

                            native_llm = ChatGoogleGenerativeAI(model=model or "gemini-1.5-flash", api_key=api_key)
                        except Exception as e:
                            raise ImportError(f"Google LangChain class import failed: {e}")

                else:
                    raise ValueError(f"Unsupported provider for LangChain: {provider}")

            agent_executor = create_pandas_dataframe_agent(
                llm=native_llm,
                df=df,
                agent_type=config.get("agent_type", "openai-tools"),  # tipo padrão; pode ser customizado
                verbose=config.get("verbose", False),
                allow_dangerous_code=config.get("allow_dangerous_code", False),
                max_iterations=config.get("max_iterations", 2),
            )
            return LangChainAgent(agent_executor)
        except Exception as e:
            raise ValueError(
                f"LangChain setup error: {e}. Instale com: pip install langchain langchain-experimental langchain-openai langchain-google-genai langchain-anthropic"
            )

    else:
        raise ValueError(
            f"Unknown backend: {backend}. Supported: 'pandasai', 'langchain'"
        )


def available_backends() -> list[str]:
    """Retorna lista de backends disponíveis no ambiente."""
    backends = []

    try:
        import pandasai  # noqa: F401
        backends.append("pandasai")
    except ImportError:
        pass

    try:
        import langchain  # noqa: F401
        backends.append("langchain")
    except ImportError:
        pass

    return backends
