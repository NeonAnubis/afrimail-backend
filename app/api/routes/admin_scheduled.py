from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.db.session import get_db
from app.models.admin import AdminUser
from app.models.scheduled import ScheduledAction
from app.api.deps.auth import get_current_admin

router = APIRouter()


class ScheduledActionCreate(BaseModel):
    action_type: str
    target_type: str
    target_ids: List[str]
    scheduled_for: datetime
    action_data: Dict[str, Any] = {}


@router.get("")
async def get_scheduled_actions(
    status_filter: Optional[str] = None,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all scheduled actions."""
    query = select(ScheduledAction).order_by(ScheduledAction.scheduled_for.desc())

    if status_filter:
        query = query.where(ScheduledAction.status == status_filter)

    result = await db.execute(query)
    actions = result.scalars().all()

    return [
        {
            "id": str(a.id),
            "action_type": a.action_type,
            "target_type": a.target_type,
            "target_ids": a.target_ids,
            "scheduled_for": a.scheduled_for.isoformat() if a.scheduled_for else None,
            "status": a.status,
            "action_data": a.action_data,
            "executed_at": a.executed_at.isoformat() if a.executed_at else None,
            "created_at": a.created_at.isoformat() if a.created_at else None
        }
        for a in actions
    ]


@router.post("")
async def create_scheduled_action(
    data: ScheduledActionCreate,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a new scheduled action."""
    action = ScheduledAction(
        action_type=data.action_type,
        target_type=data.target_type,
        target_ids=data.target_ids,
        scheduled_for=data.scheduled_for,
        action_data=data.action_data,
        status="pending",
        created_by=current_admin.id
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)

    return {
        "id": str(action.id),
        "action_type": action.action_type,
        "scheduled_for": action.scheduled_for.isoformat() if action.scheduled_for else None,
        "status": action.status
    }


@router.put("/{action_id}/cancel")
async def cancel_scheduled_action(
    action_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Cancel a scheduled action."""
    result = await db.execute(
        select(ScheduledAction).where(ScheduledAction.id == action_id)
    )
    action = result.scalar_one_or_none()

    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheduled action not found"
        )

    if action.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only cancel pending actions"
        )

    action.status = "cancelled"
    await db.commit()

    return {"success": True, "message": "Action cancelled successfully"}


@router.delete("/{action_id}")
async def delete_scheduled_action(
    action_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete a scheduled action."""
    result = await db.execute(
        select(ScheduledAction).where(ScheduledAction.id == action_id)
    )
    action = result.scalar_one_or_none()

    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheduled action not found"
        )

    await db.delete(action)
    await db.commit()

    return {"success": True, "message": "Action deleted successfully"}
