"""Anthropic Claude LLM provider."""
import os
from typing import Any

from anthropic import AsyncAnthropic

from app.llm.base import BaseLLMProvider, LLMResponse, EmbeddingResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider."""

    def __init__(self, config: dict[str, Any]):
        """Initialize Anthropic provider."""
        super().__init__(config)
        api_key = config.get("api_key") or os.getenv("ANTHROPIC_API_KEY")

        self.client = AsyncAnthropic(api_key=api_key)
        self.model = config.get("models", {}).get("primary", "claude-3-5-sonnet-20241022")

    async def chat(
        self,
        messages: list[dict[str, str]],
        **kwargs,
    ) -> LLMResponse:
        """Send chat completion request to Anthropic."""
        try:
            # Convert messages format for Anthropic
            anthropic_messages = []
            for msg in messages:
                role = msg.get("role")
                content = msg.get("content", "")

                if role == "system":
                    anthropic_messages.append({"role": "user", "content": f"System: {content}"})
                elif role == "user":
                    anthropic_messages.append({"role": "user", "content": content})
                elif role == "assistant":
                    anthropic_messages.append({"role": "assistant", "content": content})

            # Extract system prompt if present
            system = kwargs.pop("system", None)

            response = await self.client.messages.create(
                model=self.model,
                max_tokens=kwargs.pop("max_tokens", 1024),
                system=system,
                messages=anthropic_messages,
                **kwargs,
            )

            return LLMResponse(
                content=response.content[0].text,
                raw_response=response.model_dump(),
                model=self.model,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
                finish_reason=response.stop_reason,
            )
        except Exception as e:
            logger.error(f"Anthropic chat error: {e}")
            raise

    async def embed(self, text: str) -> EmbeddingResponse:
        """Anthropic doesn't have embeddings, use a fallback."""
        # Anthropic doesn't provide embeddings directly
        # In production, you would use a separate embedding service
        raise NotImplementedError(
            "Anthropic provider does not support embeddings. "
            "Use OpenAI or another embedding provider."
        )

    async def health_check(self) -> bool:
        """Check Anthropic API health."""
        try:
            # Simple models list call to check connectivity
            await self.client.messages.list(limit=1)
            return True
        except Exception as e:
            logger.warning(f"Anthropic health check failed: {e}")
            return False

    def supports_vision(self) -> bool:
        """Claude 3.5+ supports vision."""
        return True

    async def chat_with_image(
        self,
        messages: list[dict[str, Any]],
        **kwargs,
    ) -> LLMResponse:
        """Send chat with image support using Claude's vision."""
        try:
            anthropic_messages = []
            for msg in messages:
                role = msg.get("role")
                content = msg.get("content")

                if isinstance(content, list):
                    # Already in Anthropic format with images
                    anthropic_messages.append({"role": role, "content": content})
                else:
                    anthropic_messages.append({"role": role, "content": content})

            system = kwargs.pop("system", None)

            response = await self.client.messages.create(
                model=self.model,
                max_tokens=kwargs.pop("max_tokens", 1024),
                system=system,
                messages=anthropic_messages,
                **kwargs,
            )

            return LLMResponse(
                content=response.content[0].text,
                raw_response=response.model_dump(),
                model=self.model,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
                finish_reason=response.stop_reason,
            )
        except Exception as e:
            logger.error(f"Anthropic vision chat error: {e}")
            raise
