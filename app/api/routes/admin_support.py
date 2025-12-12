from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.db.session import get_db
from app.models.admin import AdminUser
from app.models.support import SupportTicket
from app.api.deps.auth import get_current_admin

router = APIRouter()


class TicketUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[str] = None
    resolution_notes: Optional[str] = None


@router.get("/tickets")
async def get_tickets(
    status_filter: Optional[str] = None,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all support tickets."""
    query = select(SupportTicket).order_by(SupportTicket.created_at.desc())

    if status_filter:
        query = query.where(SupportTicket.status == status_filter)

    result = await db.execute(query)
    tickets = result.scalars().all()

    return [
        {
            "id": str(t.id),
            "ticket_type": t.ticket_type,
            "user_email": t.user_email,
            "status": t.status,
            "priority": t.priority,
            "subject": t.subject,
            "message": t.message,
            "description": t.description,
            "resolution_notes": t.resolution_notes,
            "assigned_to": t.assigned_to,
            "resolved_by": t.resolved_by,
            "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None
        }
        for t in tickets
    ]


@router.get("/tickets/{ticket_id}")
async def get_ticket(
    ticket_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific support ticket."""
    result = await db.execute(
        select(SupportTicket).where(SupportTicket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found"
        )

    return {
        "id": str(ticket.id),
        "ticket_type": ticket.ticket_type,
        "user_email": ticket.user_email,
        "status": ticket.status,
        "priority": ticket.priority,
        "subject": ticket.subject,
        "message": ticket.message,
        "description": ticket.description,
        "resolution_notes": ticket.resolution_notes,
        "assigned_to": ticket.assigned_to,
        "resolved_by": ticket.resolved_by,
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None
    }


@router.put("/tickets/{ticket_id}")
async def update_ticket(
    ticket_id: str,
    data: TicketUpdate,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update a support ticket."""
    result = await db.execute(
        select(SupportTicket).where(SupportTicket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found"
        )

    if data.status is not None:
        ticket.status = data.status
    if data.priority is not None:
        ticket.priority = data.priority
    if data.assigned_to is not None:
        ticket.assigned_to = data.assigned_to
    if data.resolution_notes is not None:
        ticket.resolution_notes = data.resolution_notes

    await db.commit()
    await db.refresh(ticket)

    return {"success": True, "message": "Ticket updated successfully"}


@router.put("/tickets/{ticket_id}/resolve")
async def resolve_ticket(
    ticket_id: str,
    resolution_notes: str = "",
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Resolve a support ticket."""
    result = await db.execute(
        select(SupportTicket).where(SupportTicket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found"
        )

    ticket.status = "resolved"
    ticket.resolution_notes = resolution_notes
    ticket.resolved_by = current_admin.email
    ticket.resolved_at = datetime.utcnow()

    await db.commit()

    return {"success": True, "message": "Ticket resolved successfully"}


@router.put("/tickets/{ticket_id}/reject")
async def reject_ticket(
    ticket_id: str,
    reason: str = "",
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Reject a support ticket."""
    result = await db.execute(
        select(SupportTicket).where(SupportTicket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found"
        )

    ticket.status = "rejected"
    ticket.resolution_notes = reason
    ticket.resolved_by = current_admin.email
    ticket.resolved_at = datetime.utcnow()

    await db.commit()

    return {"success": True, "message": "Ticket rejected"}
