"""Instruction parser for preprocessing."""
import re
from typing import Optional
from dataclasses import dataclass

from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ParsedInstruction:
    """Structured parsed instruction."""

    original: str
    cleaned: str
    app_name: Optional[str] = None
    credentials: dict[str, str] = {}
    sensitive_data: list[str] = []


class InstructionParser:
    """Parser for preprocessing natural language instructions."""

    # Patterns for common app names
    APP_PATTERNS = {
        "wechat": [r"微信", r"wechat", r"weixin"],
        "alipay": [r"支付宝", r"alipay"],
        "taobao": [r"淘宝", r"taobao"],
        "jd": [r"京东", r"jd\.com", r"jingdong"],
        "douyin": [r"抖音", r"douyin", r"tiktok"],
        "instagram": [r"instagram", r"ins", r"照片墙"],
        "whatsapp": [r"whatsapp"],
        "telegram": [r"telegram", r"tg", r"电报"],
        "twitter": [r"twitter", r"x\.com", r"推特"],
        "facebook": [r"facebook", r"fb", r"脸书"],
        "sina": [r"新浪", r"weibo", r"微博"],
    }

    # Patterns for credentials
    CREDENTIAL_PATTERNS = {
        "phone": [r"1[3-9]\d{9}"],
        "email": [r"[\w.-]+@[\w.-]+\.\w+"],
        "id_card": [r"\d{17}[\dXx]"],
    }

    # Sensitive data patterns to redact
    SENSITIVE_PATTERNS = {
        "password": [r"password[:\s]*\S+", r"密码[:\s]*\S+", r"pass[:\s]*\S+"],
        "bank_card": [r"\d{16,19}"],
    }

    def parse(self, instruction: str) -> ParsedInstruction:
        """Parse and clean instruction.

        Args:
            instruction: Raw user instruction

        Returns:
            ParsedInstruction with structured data
        """
        logger.debug(f"Parsing instruction: {instruction}")

        # Step 1: Basic cleaning
        cleaned = self._clean_text(instruction)

        # Step 2: Extract app name
        app_name = self._extract_app_name(cleaned)

        # Step 3: Extract credentials (mark as sensitive)
        credentials = self._extract_credentials(cleaned)

        # Step 4: Detect sensitive data
        sensitive = self._detect_sensitive(cleaned)

        # Step 5: Redact sensitive info from cleaned text
        cleaned = self._redact_sensitive(cleaned, sensitive)

        result = ParsedInstruction(
            original=instruction,
            cleaned=cleaned,
            app_name=app_name,
            credentials=credentials,
            sensitive_data=sensitive,
        )

        logger.debug(f"Parsed result: app={app_name}, sensitive={len(sensitive)} items")
        return result

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text)
        # Remove special characters but keep Chinese, alphanumeric, and basic punctuation
        text = re.sub(r"[^\w\s\u4e00-\u9fff@.-:,。，、；;]", "", text)
        return text.strip()

    def _extract_app_name(self, text: str) -> Optional[str]:
        """Extract app name from instruction."""
        text_lower = text.lower()
        for app_name, patterns in self.APP_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    logger.debug(f"Found app: {app_name}")
                    return app_name
        return None

    def _extract_credentials(self, text: str) -> dict[str, str]:
        """Extract credentials from text."""
        credentials = {}

        # Extract email
        for pattern in self.CREDENTIAL_PATTERNS["email"]:
            matches = re.findall(pattern, text)
            if matches:
                credentials["email"] = matches[0]

        # Extract phone
        for pattern in self.CREDENTIAL_PATTERNS["phone"]:
            matches = re.findall(pattern, text)
            if matches:
                credentials["phone"] = matches[0]

        return credentials

    def _detect_sensitive(self, text: str) -> list[str]:
        """Detect sensitive data in text."""
        detected = []

        for data_type, patterns in self.SENSITIVE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    detected.append(data_type)
                    break

        # Also check for any detected credentials
        if "email" in text:
            detected.append("email")
        if "phone" in text:
            detected.append("phone")

        return list(set(detected))

    def _redact_sensitive(self, text: str, sensitive_types: list[str]) -> str:
        """Redact sensitive data from text."""
        redacted = text

        if "password" in sensitive_types:
            redacted = re.sub(r"password[:\s]*\S+", "[REDACTED_PASSWORD]", redacted, flags=re.IGNORECASE)
            redacted = re.sub(r"密码[:\s]*\S+", "[REDACTED_PASSWORD]", redacted)
            redacted = re.sub(r"pass[:\s]*\S+", "[REDACTED_PASSWORD]", redacted, flags=re.IGNORECASE)

        if "bank_card" in sensitive_types:
            redacted = re.sub(r"\d{16,19}", "[REDACTED_BANK_CARD]", redacted)

        return redacted

    def validate(self, instruction: str) -> tuple[bool, Optional[str]]:
        """Validate instruction format.

        Returns:
            (is_valid, error_message)
        """
        if not instruction or not instruction.strip():
            return False, "Instruction cannot be empty"

        if len(instruction) > 2000:
            return False, "Instruction too long (max 2000 characters)"

        return True, None
