"""MiniMax LLM provider."""
import os
from typing import Any, Optional

from openai import AsyncOpenAI

from app.llm.base import BaseLLMProvider, LLMResponse, EmbeddingResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MiniMaxProvider(BaseLLMProvider):
    """MiniMax AI provider (compatible with abab7 / MiniMax2.7)."""

    def __init__(self, config: dict[str, Any]):
        """Initialize MiniMax provider."""
        super().__init__(config)
        api_key = config.get("api_key") or os.getenv("MINIMAX_API_KEY")
        api_base = config.get("api_base", "https://api.minimax.chat/v")

        # Group ID for MiniMax
        self.group_id = config.get("group_id") or os.getenv("MINIMAX_GROUP_ID")

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=api_base,
        )
        self.model = config.get("models", {}).get("primary", "abab7")
        self.embedding_model = config.get("models", {}).get("embedding", "embo")

    async def chat(
        self,
        messages: list[dict[str, str]],
        **kwargs,
    ) -> LLMResponse:
        """Send chat completion request to MiniMax."""
        try:
            # MiniMax uses OpenAI-compatible API
            # Add group_id to request if available
            request_kwargs = {
                "model": self.model,
                "messages": messages,
                **kwargs,
            }

            # Add bot ID for MiniMax specific features if provided
            if self.group_id:
                # MiniMax uses extra_headers for group_id
                request_kwargs["extra_headers"] = {
                    "MM-GROUP-ID": self.group_id,
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
            logger.error(f"MiniMax chat error: {e}")
            raise

    async def embed(self, text: str) -> EmbeddingResponse:
        """Generate embedding using MiniMax embedding API."""
        try:
            # MiniMax embedding endpoint
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
            logger.error(f"MiniMax embedding error: {e}")
            raise

    async def health_check(self) -> bool:
        """Check MiniMax API health."""
        try:
            # Simple models list call to check connectivity
            await self.client.models.list()
            return True
        except Exception as e:
            logger.warning(f"MiniMax health check failed: {e}")
            return False

    def supports_vision(self) -> bool:
        """MiniMax may support vision depending on model."""
        # abab7 and newer models support vision
        return True

    async def chat_with_image(
        self,
        messages: list[dict[str, Any]],
        **kwargs,
    ) -> LLMResponse:
        """Send chat with image support using MiniMax vision."""
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
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                },
                finish_reason=choice.finish_reason,
            )
        except Exception as e:
            logger.error(f"MiniMax vision chat error: {e}")
            raise
