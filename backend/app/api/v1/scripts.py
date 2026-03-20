"""Scripts API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.script import ScriptCreate, ScriptUpdate, ScriptResponse, ScriptListResponse
from app.services.script import ScriptService

router = APIRouter()


@router.post("/", response_model=ScriptResponse, status_code=status.HTTP_201_CREATED)
async def create_script(script_data: ScriptCreate, db: AsyncSession = Depends(get_db)):
    """Create a new script."""
    service = ScriptService(db)
    script = await service.create_script(script_data)
    return script


@router.get("/", response_model=ScriptListResponse)
async def list_scripts(skip: int = 0, limit: int = 20, db: AsyncSession = Depends(get_db)):
    """List all scripts."""
    service = ScriptService(db)
    scripts, total = await service.list_scripts(skip, limit)
    return {"items": scripts, "total": total}


@router.get("/{script_id}", response_model=ScriptResponse)
async def get_script(script_id: str, db: AsyncSession = Depends(get_db)):
    """Get script by ID."""
    service = ScriptService(db)
    script = await service.get_script(script_id)
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")
    return script


@router.put("/{script_id}", response_model=ScriptResponse)
async def update_script(script_id: str, script_data: ScriptUpdate, db: AsyncSession = Depends(get_db)):
    """Update a script."""
    service = ScriptService(db)
    script = await service.update_script(script_id, script_data)
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")
    return script


@router.delete("/{script_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_script(script_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a script."""
    service = ScriptService(db)
    success = await service.delete_script(script_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")
