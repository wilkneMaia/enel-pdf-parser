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
    llm: Any,
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
            from langchain.agents import create_pandas_dataframe_agent

            agent_executor = create_pandas_dataframe_agent(
                llm=llm,
                df=df,
                agent_type="openai-tools",  # tipo padrão; pode ser customizado
                verbose=config.get("verbose", False),
                allow_dangerous_code=True,  # necessário para SmartDataframe
            )
            return LangChainAgent(agent_executor)
        except ImportError:
            raise ValueError(
                "langchain packages not found. Install with: "
                "pip install langchain langchain-openai langchain-google-genai langchain-anthropic"
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
