from typing import Any
from .base import BaseLLM


class OpenAILLM(BaseLLM):
    """Wrapper for the OpenAI API (GPT family) and OpenAI-compatible endpoints.

    Setting `base_url` lets you target a HuggingFace Dedicated Endpoint, a vLLM
    server, or any other OpenAI-compatible API.
    """

    def __init__(
        self,
        model_name: str = "gpt-5.4-mini",
        api_key: str | None = None,
        base_url: str | None = None,
        **kwargs,
    ):
        super().__init__(model_name, **kwargs)
        self._setup(api_key, base_url)

    def _setup(self, api_key: str | None, base_url: str | None):
        try:
            import openai
            import os

            resolved_key = api_key or os.getenv("OPENAI_API_KEY")
            if base_url:
                self._client = openai.OpenAI(api_key=resolved_key, base_url=base_url)
            else:
                self._client = openai.OpenAI(api_key=resolved_key)
        except ImportError:
            raise ImportError("the 'openai' package is required: pip install openai")

    def call(self, prompt: str, **kwargs) -> str:
        return self.chat([{"role": "user", "content": prompt}], **kwargs)

    def chat(self, messages: list[dict], **kwargs) -> str:
        # Null bytes (\x00) cause "We could not parse the JSON body" 400 errors.
        # Strip them from all string values before serialization.
        sanitized = [
            {k: v.replace("\x00", "") if isinstance(v, str) else v for k, v in msg.items()}
            for msg in messages
        ]
        params = {**self.kwargs, **kwargs}
        response = self._client.chat.completions.create(
            model=self.model_name,
            messages=sanitized,
            **params,
        )
        return response.choices[0].message.content

    def get_langchain_llm(self) -> Any:
        try:
            from langchain_openai import ChatOpenAI
            import os

            return ChatOpenAI(
                model=self.model_name,
                api_key=self._client.api_key or os.getenv("OPENAI_API_KEY"),
                **self.kwargs,
            )
        except ImportError:
            raise ImportError("the 'langchain-openai' package is required: pip install langchain-openai")
