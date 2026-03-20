"""Script service for API endpoints."""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.script import ScriptCreate, ScriptUpdate, ScriptResponse, ScriptListResponse
from app.core.script.manager import ScriptManager
from app.core.script.matcher import ScriptMatcher
from app.core.script.generator import ScriptGenerator
from app.core.script.template import MaestroTemplate
from app.core.script.validator import ScriptValidator
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ScriptService:
    """Service for script management API."""

    def __init__(self, db: AsyncSession):
        """Initialize script service."""
        self.db = db
        self.manager = ScriptManager(db)
        self.matcher = ScriptMatcher(db)
        self.generator = ScriptGenerator()
        self.template = MaestroTemplate()
        self.validator = ScriptValidator()

    async def create_script(self, script_data: ScriptCreate, user_id: int) -> ScriptResponse:
        """Create a new script."""
        return await self.manager.create(user_id, script_data)

    async def list_scripts(
        self, user_id: int, skip: int = 0, limit: int = 20
    ) -> tuple[list[ScriptResponse], int]:
        """List scripts for a user."""
        scripts, total = await self.manager.list(user_id=user_id, skip=skip, limit=limit)
        return [ScriptResponse.model_validate(s) for s in scripts], total

    async def get_script(self, script_id: str) -> Optional[ScriptResponse]:
        """Get script by ID."""
        script = await self.manager.get(script_id)
        if script:
            return ScriptResponse.model_validate(script)
        return None

    async def update_script(
        self, script_id: str, user_id: int, script_data: ScriptUpdate
    ) -> Optional[ScriptResponse]:
        """Update a script."""
        script = await self.manager.update(script_id, user_id, script_data)
        if script:
            return ScriptResponse.model_validate(script)
        return None

    async def delete_script(self, script_id: str, user_id: int) -> bool:
        """Delete a script."""
        return await self.manager.delete(script_id, user_id)

    async def generate_script(
        self, user_id: int, instruction: str, intent: str, entities: dict
    ) -> dict:
        """Generate a script from instruction.

        Returns:
            Dict with script_id, pseudo_code, maestro_yaml, and is_reused flag
        """
        # Try to find similar script
        similar_script = await self.matcher.find_similar(instruction, user_id)

        if similar_script:
            # Reuse existing script
            await self.manager.increment_hit_count(similar_script.script_id)
            logger.info(f"Reusing script: {similar_script.script_id}")
            return {
                "script_id": similar_script.script_id,
                "intent": similar_script.intent,
                "pseudo_code": similar_script.pseudo_code,
                "maestro_yaml": similar_script.maestro_yaml,
                "is_reused": True,
            }

        # Generate new script
        generated = await self.generator.generate(intent, entities, instruction)

        # Render Maestro YAML
        maestro_yaml = self.template.render(
            steps=generated.get("steps", []),
            app_id=entities.get("package", "com.example.app"),
            flow_name=f"Test: {intent}",
        )

        # Validate generated YAML
        is_valid, error = self.validator.validate_yaml(maestro_yaml)
        if not is_valid:
            logger.warning(f"Generated YAML validation warning: {error}")

        # Save script
        script = await self.manager.save_generated(
            user_id=user_id,
            intent=intent,
            structured_instruction={"intent": intent, "entities": entities},
            pseudo_code=str(generated),
            maestro_yaml=maestro_yaml,
        )

        # Store embedding
        await self.matcher.store_embedding(script, instruction)

        return {
            "script_id": script.script_id,
            "intent": intent,
            "pseudo_code": str(generated),
            "maestro_yaml": maestro_yaml,
            "is_reused": False,
        }
