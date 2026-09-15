from abc import ABC, abstractmethod
from typing import Any


class BaseLLM(ABC):
    """Abstract base class for all LLM providers."""

    def __init__(self, model_name: str, **kwargs):
        self.model_name = model_name
        self.kwargs = kwargs

    @abstractmethod
    def call(self, prompt: str, **kwargs) -> str:
        """Single-prompt call."""
        pass

    @abstractmethod
    def chat(self, messages: list[dict], **kwargs) -> str:
        """Chat call from a messages list.

        messages format: [{"role": "user"/"assistant"/"system", "content": "..."}]
        """
        pass

    @abstractmethod
    def get_langchain_llm(self) -> Any:
        """Return a LangChain-compatible LLM object."""
        pass

    def __repr__(self):
        return f"{self.__class__.__name__}(model={self.model_name})"
