from typing import Any
from .base import BaseLLM


class HuggingFaceLLM(BaseLLM):
    """HuggingFace model wrapper (local pipeline or Inference API)."""

    def __init__(
        self,
        model_name: str = "mistralai/Mistral-7B-Instruct-v0.2",
        use_inference_api: bool = False,
        api_key: str | None = None,
        device: str = "auto",
        **kwargs,
    ):
        super().__init__(model_name, **kwargs)
        self.use_inference_api = use_inference_api
        self.api_key = api_key
        self.device = device
        self._setup()

    def _setup(self):
        if self.use_inference_api:
            self._setup_inference_api()
        else:
            self._setup_local()

    def _setup_inference_api(self):
        try:
            from huggingface_hub import InferenceClient
            import os

            self._client = InferenceClient(
                model=self.model_name,
                token=self.api_key or os.getenv("HF_TOKEN"),
            )
        except ImportError:
            raise ImportError("the 'huggingface_hub' package is required: pip install huggingface_hub")

    def _setup_local(self):
        try:
            from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
            import torch

            tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._pipeline = pipeline(
                "text-generation",
                model=self.model_name,
                tokenizer=tokenizer,
                device_map=self.device,
                torch_dtype=torch.float16,
            )
        except ImportError:
            raise ImportError("the 'transformers' and 'torch' packages are required: pip install transformers torch")

    def call(self, prompt: str, **kwargs) -> str:
        return self.chat([{"role": "user", "content": prompt}], **kwargs)

    def chat(self, messages: list[dict], **kwargs) -> str:
        params = {**self.kwargs, **kwargs}

        if self.use_inference_api:
            response = self._client.chat_completion(messages=messages, **params)
            return response.choices[0].message.content
        else:
            # Local pipeline: flatten the messages into a single text prompt.
            prompt = self._messages_to_prompt(messages)
            max_new_tokens = params.pop("max_new_tokens", 512)
            output = self._pipeline(prompt, max_new_tokens=max_new_tokens, **params)
            generated = output[0]["generated_text"]
            # Strip the original prompt from the generated text.
            return generated[len(prompt):].strip()

    def _messages_to_prompt(self, messages: list[dict]) -> str:
        parts = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                parts.append(f"[INST] <<SYS>>\n{content}\n<</SYS>>\n\n")
            elif role == "user":
                parts.append(f"[INST] {content} [/INST]")
            elif role == "assistant":
                parts.append(f" {content} </s>")
        return "".join(parts)

    def get_langchain_llm(self) -> Any:
        try:
            if self.use_inference_api:
                from langchain_huggingface import HuggingFaceEndpoint
                import os

                return HuggingFaceEndpoint(
                    repo_id=self.model_name,
                    huggingfacehub_api_token=self.api_key or os.getenv("HF_TOKEN"),
                    **self.kwargs,
                )
            else:
                from langchain_huggingface import HuggingFacePipeline

                return HuggingFacePipeline(pipeline=self._pipeline)
        except ImportError:
            raise ImportError("the 'langchain-huggingface' package is required: pip install langchain-huggingface")
