"""Qwen LLM provider (OpenAI-compatible API)."""
import os
import re
from typing import Any, Optional

from openai import AsyncOpenAI

from app.llm.base import BaseLLMProvider, LLMResponse, EmbeddingResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)


def expand_env_var(value: Any) -> Any:
    """Expand environment variables in string values.

    Handles ${VAR} and ${VAR:-default} syntax.
    """
    if not isinstance(value, str):
        return value

    # Match ${VAR} or ${VAR:-default}
    pattern = r'\$\{([^}:]+)(?::-([^}]*))?\}'

    def replacer(match):
        var_name = match.group(1)
        default = match.group(2) or ""
        return os.environ.get(var_name, default)

    return re.sub(pattern, replacer, value)


class QwenProvider(BaseLLMProvider):
    """Qwen AI provider (Alibaba Cloud) - OpenAI-compatible API."""

    def __init__(self, config: dict[str, Any]):
        """Initialize Qwen provider."""
        super().__init__(config)

        # Expand environment variables
        api_key = expand_env_var(config.get("api_key")) or os.getenv("QWEN_API_KEY")
        api_base = expand_env_var(config.get("api_base")) or os.getenv("QWEN_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")

        if not api_key:
            raise ValueError("QWEN_API_KEY is not set")

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=api_base,
        )
        self.model = config.get("models", {}).get("primary", "qwen-plus")
        self.embedding_model = config.get("models", {}).get("embedding", "text-embedding-v3")

    async def chat(
        self,
        messages: list[dict[str, str]],
        **kwargs,
    ) -> LLMResponse:
        """Send chat completion request to Qwen."""
        try:
            request_kwargs = {
                "model": self.model,
                "messages": messages,
                **kwargs,
            }

            response = await self.client.chat.completions.create(**request_kwargs)

            choice = response.choices[0]
            return LLMResponse(
                content=choice.message.content or "",
                raw_response=response.model_dump(),
                model=self.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                },
                finish_reason=choice.finish_reason,
            )
        except Exception as e:
            logger.error(f"Qwen chat error: {e}")
            raise

    async def embed(self, text: str) -> EmbeddingResponse:
        """Generate embedding using Qwen embedding API."""
        try:
            response = await self.client.embeddings.create(
                model=self.embedding_model,
                input=text,
            )

            embedding = response.data[0].embedding
            return EmbeddingResponse(
                embedding=embedding,
                model=self.embedding_model,
                usage={
                    "tokens": len(text.split()),
                },
            )
        except Exception as e:
            logger.error(f"Qwen embedding error: {e}")
            raise

    async def health_check(self) -> bool:
        """Check Qwen API health."""
        try:
            await self.client.models.list()
            return True
        except Exception as e:
            logger.warning(f"Qwen health check failed: {e}")
            return False
