"""Script manager for CRUD operations."""
import uuid
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.script import Script
from app.schemas.script import ScriptCreate, ScriptUpdate, ScriptResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ScriptManager:
    """Manager for script CRUD operations."""

    def __init__(self, db: AsyncSession):
        """Initialize script manager."""
        self.db = db

    async def create(self, user_id: int, script_data: ScriptCreate) -> ScriptResponse:
        """Create a new script.

        Args:
            user_id: ID of the user creating the script
            script_data: Script creation data

        Returns:
            Created script response
        """
        script = Script(
            script_id=str(uuid.uuid4()),
            user_id=user_id,
            intent=script_data.intent,
            structured_instruction=script_data.structured_instruction,
            status="active",
            version=1,
            hit_count=0,
        )

        self.db.add(script)
        await self.db.flush()
        await self.db.refresh(script)

        logger.info(f"Script created: {script.script_id}")
        return ScriptResponse.model_validate(script)

    async def get(self, script_id: str) -> Optional[Script]:
        """Get script by ID."""
        result = await self.db.execute(
            select(Script).where(Script.script_id == script_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_user(self, script_id: str, user_id: int) -> Optional[Script]:
        """Get script by ID with user validation."""
        result = await self.db.execute(
            select(Script).where(
                Script.script_id == script_id,
                Script.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        user_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> tuple[list[Script], int]:
        """List scripts with pagination.

        Args:
            user_id: Filter by user ID (optional)
            skip: Number of records to skip
            limit: Maximum number of records
            status: Filter by status (optional)

        Returns:
            Tuple of (scripts, total_count)
        """
        query = select(Script)

        if user_id:
            query = query.where(Script.user_id == user_id)
        if status:
            query = query.where(Script.status == status)

        # Get total count
        from sqlalchemy import func

        count_query = select(func.count(Script.id))
        if user_id:
            count_query = count_query.where(Script.user_id == user_id)
        if status:
            count_query = count_query.where(Script.status == status)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Get paginated results
        query = query.order_by(Script.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        scripts = result.scalars().all()

        return list(scripts), total

    async def update(
        self,
        script_id: str,
        user_id: int,
        script_data: ScriptUpdate,
    ) -> Optional[Script]:
        """Update a script.

        Args:
            script_id: Script ID
            user_id: User ID for ownership check
            script_data: Update data

        Returns:
            Updated script or None if not found
        """
        script = await self.get_by_id_with_user(script_id, user_id)
        if not script:
            return None

        update_data = script_data.model_dump(exclude_unset=True)
        if not update_data:
            return script

        # Update fields
        for field, value in update_data.items():
            setattr(script, field, value)

        # Increment version on content changes
        if any(f in update_data for f in ["pseudo_code", "maestro_yaml", "structured_instruction"]):
            script.version += 1

        await self.db.flush()
        await self.db.refresh(script)

        logger.info(f"Script updated: {script_id}, version: {script.version}")
        return script

    async def delete(self, script_id: str, user_id: int) -> bool:
        """Delete a script.

        Args:
            script_id: Script ID
            user_id: User ID for ownership check

        Returns:
            True if deleted, False if not found
        """
        script = await self.get_by_id_with_user(script_id, user_id)
        if not script:
            return False

        await self.db.delete(script)
        await self.db.flush()

        logger.info(f"Script deleted: {script_id}")
        return True

    async def increment_hit_count(self, script_id: str) -> None:
        """Increment the hit count for a script."""
        await self.db.execute(
            update(Script)
            .where(Script.script_id == script_id)
            .values(hit_count=Script.hit_count + 1)
        )

    async def save_generated(
        self,
        user_id: int,
        intent: str,
        structured_instruction: dict,
        pseudo_code: str,
        maestro_yaml: str,
    ) -> Script:
        """Save a newly generated script.

        Args:
            user_id: User ID
            intent: Intent name
            structured_instruction: Parsed instruction
            pseudo_code: Generated pseudo code
            maestro_yaml: Generated Maestro YAML

        Returns:
            Created script
        """
        script = Script(
            script_id=str(uuid.uuid4()),
            user_id=user_id,
            intent=intent,
            structured_instruction=structured_instruction,
            pseudo_code=pseudo_code,
            maestro_yaml=maestro_yaml,
            status="active",
            version=1,
            hit_count=0,
        )

        self.db.add(script)
        await self.db.flush()
        await self.db.refresh(script)

        logger.info(f"Generated script saved: {script.script_id}")
        return script
