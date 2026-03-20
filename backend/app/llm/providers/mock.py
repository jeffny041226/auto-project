"""Mock LLM provider for development and testing."""
import json
import random
from typing import Any

from app.llm.base import BaseLLMProvider, LLMResponse, EmbeddingResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MockProvider(BaseLLMProvider):
    """Mock LLM provider that returns predefined responses."""

    # Predefined intent classifications
    INTENT_RESPONSES = {
        "app_open": {
            "intent": "app_open",
            "entities": {"app_name": "WeChat", "package": "com.tencent.mm"},
            "confidence": 0.95,
        },
        "login": {
            "intent": "login",
            "entities": {
                "app_name": "WeChat",
                "username": "user@example.com",
                "password_field": "password",
            },
            "confidence": 0.92,
        },
        "logout": {"intent": "logout", "entities": {"app_name": "WeChat"}, "confidence": 0.93},
        "swipe": {
            "intent": "swipe",
            "entities": {"direction": "up", "start_x": 0.5, "start_y": 0.8, "end_x": 0.5, "end_y": 0.2},
            "confidence": 0.88,
        },
        "tap": {
            "intent": "tap",
            "entities": {"element": "login_button", "text": "Login"},
            "confidence": 0.91,
        },
        "input": {
            "intent": "input",
            "entities": {"element": "username_field", "text": "test_user"},
            "confidence": 0.89,
        },
        "assert": {
            "intent": "assert",
            "entities": {"element": "welcome_message", "expected": "Welcome"},
            "confidence": 0.94,
        },
        "scroll": {
            "intent": "scroll",
            "entities": {"direction": "down", "amount": 1},
            "confidence": 0.87,
        },
        "capture": {"intent": "capture", "entities": {"name": "screenshot"}, "confidence": 0.96},
    }

    def __init__(self, config: dict[str, Any]):
        """Initialize mock provider."""
        super().__init__(config)
        self._health = True

    async def chat(
        self,
        messages: list[dict[str, str]],
        **kwargs,
    ) -> LLMResponse:
        """Return mock chat response based on intent in messages."""
        # Extract the last user message
        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "").lower()
                break

        # Determine intent from message content
        intent = self._classify_intent(user_message)
        response_content = json.dumps(intent)

        logger.debug(f"Mock provider returning intent: {intent['intent']}")

        return LLMResponse(
            content=response_content,
            raw_response=intent,
            model=self.model,
            usage={"prompt_tokens": 50, "completion_tokens": 30},
            finish_reason="stop",
        )

    async def embed(self, text: str) -> EmbeddingResponse:
        """Generate mock embedding vector."""
        # Generate a random but deterministic embedding based on text
        import hashlib

        hash_digest = hashlib.md5(text.encode()).digest()
        random.seed(int.from_bytes(hash_digest[:4], "big"))

        embedding = [random.uniform(-1, 1) for _ in range(1536)]
        # Normalize
        norm = sum(x**2 for x in embedding) ** 0.5
        embedding = [x / norm for x in embedding]

        return EmbeddingResponse(
            embedding=embedding,
            model=self.model,
            usage={"tokens": len(text.split())},
        )

    async def health_check(self) -> bool:
        """Mock health check always returns True."""
        return self._health

    def _classify_intent(self, text: str) -> dict:
        """Classify intent from text."""
        text_lower = text.lower()

        if any(word in text_lower for word in ["open", "launch", "start", "打开", "启动"]):
            if "wechat" in text_lower or "微信" in text_lower:
                return self.INTENT_RESPONSES["app_open"]
            return {**self.INTENT_RESPONSES["app_open"], "entities": {"app_name": "Unknown"}}

        if any(word in text_lower for word in ["login", "登录", "sign in", "登陆"]):
            return self.INTENT_RESPONSES["login"]

        if any(word in text_lower for word in ["logout", "退出", "sign out", "登出"]):
            return self.INTENT_RESPONSES["logout"]

        if any(word in text_lower for word in ["swipe", "滑动", "滑"]):
            return self.INTENT_RESPONSES["swipe"]

        if any(word in text_lower for word in ["tap", "click", "点击", "点击"]):
            return self.INTENT_RESPONSES["tap"]

        if any(word in text_lower for word in ["input", "type", "enter", "输入"]):
            return self.INTENT_RESPONSES["input"]

        if any(word in text_lower for word in ["assert", "verify", "check", "验证", "检查"]):
            return self.INTENT_RESPONSES["assert"]

        if any(word in text_lower for word in ["scroll", "滚动"]):
            return self.INTENT_RESPONSES["scroll"]

        if any(word in text_lower for word in ["screenshot", "capture", "截图", "截屏"]):
            return self.INTENT_RESPONSES["capture"]

        # Default to tap
        return self.INTENT_RESPONSES["tap"]

    def set_health(self, healthy: bool) -> None:
        """Set mock health state for testing."""
        self._health = healthy
