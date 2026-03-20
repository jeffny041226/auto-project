"""Script matcher using vector similarity."""
import numpy as np
from typing import Optional, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base import BaseLLMProvider, EmbeddingResponse
from app.llm.factory import LLMFactory
from app.models.script import Script
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ScriptMatcher:
    """Matches instructions to existing scripts using embeddings."""

    SIMILARITY_THRESHOLD = 0.85

    def __init__(self, db: AsyncSession, llm_provider: BaseLLMProvider = None):
        """Initialize script matcher."""
        self.db = db
        if llm_provider:
            self.llm = llm_provider
        else:
            self.llm = LLMFactory.get_default(settings.llm_config)

    async def find_similar(
        self,
        instruction: str,
        user_id: int,
        threshold: float = SIMILARITY_THRESHOLD,
    ) -> Optional[Script]:
        """Find a similar script based on instruction.

        Args:
            instruction: User instruction text
            user_id: User ID to scope search
            threshold: Minimum similarity threshold (0-1)

        Returns:
            Most similar script or None
        """
        # Generate embedding for instruction
        embedding_response = await self.llm.embed(instruction)
        query_embedding = np.array(embedding_response.embedding, dtype=np.float32)

        # Get all active scripts for user
        result = await self.db.execute(
            select(Script).where(
                Script.user_id == user_id,
                Script.status == "active",
                Script.instruction_embedding.isnot(None),
            )
        )
        scripts = result.scalars().all()

        if not scripts:
            logger.debug("No scripts with embeddings found")
            return None

        # Calculate similarities
        best_script = None
        best_similarity = 0.0

        for script in scripts:
            if not script.instruction_embedding:
                continue

            # Deserialize embedding
            script_embedding = np.frombuffer(
                script.instruction_embedding, dtype=np.float32
            )

            # Calculate cosine similarity
            similarity = self._cosine_similarity(query_embedding, script_embedding)

            logger.debug(f"Script {script.script_id}: similarity={similarity:.4f}")

            if similarity > best_similarity:
                best_similarity = similarity
                best_script = script

        if best_similarity >= threshold:
            logger.info(
                f"Found similar script: {best_script.script_id}, "
                f"similarity={best_similarity:.4f}"
            )
            return best_script
        else:
            logger.info(
                f"No similar script found. Best similarity: {best_similarity:.4f} "
                f"(threshold: {threshold})"
            )
            return None

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(dot_product / (norm_a * norm_b))

    async def store_embedding(self, script: Script, instruction: str) -> None:
        """Generate and store embedding for a script.

        Args:
            script: Script to store embedding for
            instruction: Instruction text to embed
        """
        embedding_response = await self.llm.embed(instruction)
        embedding = np.array(embedding_response.embedding, dtype=np.float32)

        # Store as bytes
        script.instruction_embedding = embedding.tobytes()

        logger.debug(f"Stored embedding for script: {script.script_id}")
