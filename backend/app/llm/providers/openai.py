"""OpenAI LLM provider."""
import os
from typing import Any

from openai import AsyncOpenAI

from app.llm.base import BaseLLMProvider, LLMResponse, EmbeddingResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT-4o provider."""

    def __init__(self, config: dict[str, Any]):
        """Initialize OpenAI provider."""
        super().__init__(config)
        api_key = config.get("api_key") or os.getenv("OPENAI_API_KEY")
        api_base = config.get("api_base", "https://api.openai.com/v1")

        self.client = AsyncOpenAI(api_key=api_key, base_url=api_base)
        self.model = config.get("models", {}).get("primary", "gpt-4o")
        self.embedding_model = config.get("models", {}).get("embedding", "text-embedding-3-small")

    async def chat(
        self,
        messages: list[dict[str, str]],
        **kwargs,
    ) -> LLMResponse:
        """Send chat completion request to OpenAI."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                **kwargs,
            )

            choice = response.choices[0]
            return LLMResponse(
                content=choice.message.content or "",
                raw_response=response.model_dump(),
                model=self.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                },
                finish_reason=choice.finish_reason,
            )
        except Exception as e:
            logger.error(f"OpenAI chat error: {e}")
            raise

    async def embed(self, text: str) -> EmbeddingResponse:
        """Generate embedding using OpenAI."""
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
                    "prompt_tokens": response.usage.prompt_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
            )
        except Exception as e:
            logger.error(f"OpenAI embedding error: {e}")
            raise

    async def health_check(self) -> bool:
        """Check OpenAI API health."""
        try:
            # Simple models list call to check connectivity
            await self.client.models.list()
            return True
        except Exception as e:
            logger.warning(f"OpenAI health check failed: {e}")
            return False

    def supports_vision(self) -> bool:
        """OpenAI supports vision with gpt-4o."""
        return "gpt-4o" in self.model

    async def chat_with_image(
        self,
        messages: list[dict[str, Any]],
        **kwargs,
    ) -> LLMResponse:
        """Send chat with image support."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                **kwargs,
            )

            choice = response.choices[0]
            return LLMResponse(
                content=choice.message.content or "",
                raw_response=response.model_dump(),
                model=self.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                },
                finish_reason=choice.finish_reason,
            )
        except Exception as e:
            logger.error(f"OpenAI vision chat error: {e}")
            raise
