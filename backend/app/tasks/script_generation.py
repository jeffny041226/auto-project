"""Script generation async tasks."""
import asyncio
from typing import Any

from app.tasks.celery_app import celery_app
from app.core.intention.parser import InstructionParser
from app.core.intention.intent_classifier import IntentClassifier
from app.core.script.generator import ScriptGenerator
from app.core.script.template import MaestroTemplate
from app.core.script.validator import ScriptValidator
from app.db.database import get_db_context
from app.core.script.manager import ScriptManager
from app.core.script.matcher import ScriptMatcher
from app.utils.logger import get_logger

logger = get_logger(__name__)


@celery_app.task(bind=True, name="app.tasks.script_generation.generate_script")
def generate_script(
    self,
    user_id: int,
    instruction: str,
) -> dict[str, Any]:
    """Generate script from instruction asynchronously.

    Args:
        user_id: User ID
        instruction: Natural language instruction

    Returns:
        Generation result dict
    """
    logger.info(f"Starting script generation for user {user_id}")

    async def _generate():
        # Parse instruction
        parser = InstructionParser()
        parsed = parser.parse(instruction)

        # Validate
        is_valid, error = parser.validate(instruction)
        if not is_valid:
            return {"success": False, "error": error}

        # Classify intent
        classifier = IntentClassifier()
        intent_result = await classifier.classify(parsed.cleaned)

        intent = intent_result.get("intent", "tap")
        entities = intent_result.get("entities", {})

        # Generate script
        generator = ScriptGenerator()
        template = MaestroTemplate()
        validator = ScriptValidator()

        generated = await generator.generate(intent, entities, instruction)
        steps = generated.get("steps", [])

        # Render YAML
        maestro_yaml = template.render(
            steps=steps,
            app_id=entities.get("package", "com.example.app"),
            flow_name=f"Test: {intent}",
        )

        # Validate
        is_valid, error = validator.validate_yaml(maestro_yaml)
        if not is_valid:
            logger.warning(f"Generated YAML validation warning: {error}")

        # Save to database
        async with get_db_context() as db:
            manager = ScriptManager(db)
            matcher = ScriptMatcher(db)

            script = await manager.save_generated(
                user_id=user_id,
                intent=intent,
                structured_instruction={"intent": intent, "entities": entities},
                pseudo_code=str(generated),
                maestro_yaml=maestro_yaml,
            )

            # Store embedding
            await matcher.store_embedding(script, instruction)

            return {
                "success": True,
                "script_id": script.script_id,
                "intent": intent,
                "entities": entities,
                "steps_count": len(steps),
            }

    # Run async code in event loop
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(_generate())
    logger.info(f"Script generation completed: {result.get('script_id')}")
    return result


@celery_app.task(bind=True, name="app.tasks.script_generation.match_script")
def match_script(
    self,
    user_id: int,
    instruction: str,
) -> dict[str, Any]:
    """Find matching script from instruction.

    Args:
        user_id: User ID
        instruction: Instruction to match

    Returns:
        Match result with script_id or None
    """
    logger.info(f"Finding matching script for user {user_id}")

    async def _match():
        async with get_db_context() as db:
            matcher = ScriptMatcher(db)
            script = await matcher.find_similar(instruction, user_id)

            if script:
                # Increment hit count
                manager = ScriptManager(db)
                await manager.increment_hit_count(script.script_id)

                return {
                    "found": True,
                    "script_id": script.script_id,
                    "intent": script.intent,
                    "hit_count": script.hit_count + 1,
                }

            return {"found": False}

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(_match())
    return result
