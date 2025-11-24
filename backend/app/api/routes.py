from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from .. import models, schemas

router = APIRouter()

@router.get("/sessions")
async def list_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(models.Session.__table__.select())
    return result.mappings().all()

@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        models.Message.__table__.select().where(models.Message.session_id == session_id)
    )
    return result.mappings().all()