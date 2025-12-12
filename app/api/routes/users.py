from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.core.security import verify_password, get_password_hash
from app.models.user import User
from app.models.mailbox import MailboxMetadata
from app.models.support import SupportTicket
from app.schemas.auth import ChangePasswordRequest
from app.schemas.user import UserUpdate, MailboxInfoResponse
from app.api.deps.auth import get_current_user
from app.services.mailcow import mailcow_service, MailcowError

router = APIRouter()


@router.get("/profile")
async def get_profile(
    current_user: User = Depends(get_current_user)
):
    """Get current user profile."""
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "date_of_birth": str(current_user.date_of_birth) if current_user.date_of_birth else None,
        "gender": current_user.gender,
        "recovery_email": current_user.recovery_email,
        "recovery_phone": current_user.recovery_phone,
        "is_suspended": current_user.is_suspended,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "updated_at": current_user.updated_at.isoformat() if current_user.updated_at else None
    }


@router.put("/profile")
async def update_profile(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user profile."""
    if data.first_name is not None:
        current_user.first_name = data.first_name
    if data.last_name is not None:
        current_user.last_name = data.last_name
    if data.date_of_birth is not None:
        current_user.date_of_birth = data.date_of_birth
    if data.gender is not None:
        current_user.gender = data.gender
    if data.recovery_email is not None:
        current_user.recovery_email = str(data.recovery_email)
    if data.recovery_phone is not None:
        current_user.recovery_phone = data.recovery_phone

    await db.commit()
    await db.refresh(current_user)

    return {
        "success": True,
        "message": "Profile updated successfully",
        "user": {
            "id": str(current_user.id),
            "email": current_user.email,
            "first_name": current_user.first_name,
            "last_name": current_user.last_name
        }
    }


@router.post("/password")
async def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change current user's password."""
    # Verify old password
    if not current_user.password_hash or not verify_password(data.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    # Update password in Mailcow first
    if mailcow_service.is_configured:
        try:
            await mailcow_service.set_mailbox_password(current_user.email, data.new_password)
        except MailcowError as e:
            print(f"Failed to update password in Mailcow: {e.message}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update password. Please try again later."
            )

    # Update password in local database
    current_user.password_hash = get_password_hash(data.new_password)
    await db.commit()

    return {"success": True, "message": "Password changed successfully"}


@router.post("/change-password")
async def change_password_alt(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change current user's password (alternative endpoint)."""
    # Verify old password
    if not current_user.password_hash or not verify_password(data.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    # Update password in Mailcow first
    if mailcow_service.is_configured:
        try:
            await mailcow_service.set_mailbox_password(current_user.email, data.new_password)
        except MailcowError as e:
            print(f"Failed to update password in Mailcow: {e.message}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update password. Please try again later."
            )

    # Update password in local database
    current_user.password_hash = get_password_hash(data.new_password)
    await db.commit()

    return {"success": True, "message": "Password changed successfully"}


from pydantic import BaseModel, EmailStr
from typing import Optional

class RecoveryInfoUpdate(BaseModel):
    recovery_email: Optional[EmailStr] = None
    recovery_phone: Optional[str] = None


@router.put("/recovery-info")
async def update_recovery_info(
    data: RecoveryInfoUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user's recovery information."""
    if data.recovery_email is not None:
        current_user.recovery_email = str(data.recovery_email)
    if data.recovery_phone is not None:
        current_user.recovery_phone = data.recovery_phone

    await db.commit()
    await db.refresh(current_user)

    return {
        "success": True,
        "message": "Recovery information updated successfully",
        "recovery_email": current_user.recovery_email,
        "recovery_phone": current_user.recovery_phone
    }


@router.get("/mailbox-info", response_model=MailboxInfoResponse)
async def get_mailbox_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's mailbox information, synced from Mailcow."""
    quota_bytes = 5368709120  # 5GB default
    usage_bytes = 0
    messages = 0

    # Try to get real-time data from Mailcow
    if mailcow_service.is_configured:
        try:
            mailcow_mailbox = await mailcow_service.get_mailbox(current_user.email)
            if mailcow_mailbox:
                quota_bytes = mailcow_mailbox.quota
                usage_bytes = mailcow_mailbox.quota_used
                messages = mailcow_mailbox.messages
        except MailcowError as e:
            # Log but continue with cached/default data
            print(f"Failed to fetch mailbox info from Mailcow: {e.message}")

    # Update local cache
    result = await db.execute(
        select(MailboxMetadata).where(MailboxMetadata.email == current_user.email)
    )
    mailbox = result.scalar_one_or_none()

    if mailbox:
        # Update with latest data from Mailcow
        mailbox.quota_bytes = quota_bytes
        mailbox.usage_bytes = usage_bytes
        await db.commit()
        await db.refresh(mailbox)
    else:
        # Create mailbox metadata record
        mailbox = MailboxMetadata(
            email=current_user.email,
            quota_bytes=quota_bytes,
            usage_bytes=usage_bytes
        )
        db.add(mailbox)
        await db.commit()
        await db.refresh(mailbox)

    return MailboxInfoResponse(
        email=mailbox.email,
        quota_bytes=mailbox.quota_bytes,
        usage_bytes=mailbox.usage_bytes,
        quota_used_percentage=mailbox.quota_used_percentage
    )


@router.post("/support/tickets")
async def create_support_ticket(
    ticket_type: str,
    description: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a support ticket."""
    ticket = SupportTicket(
        ticket_type=ticket_type,
        user_email=current_user.email,
        user_id=current_user.id,
        description=description,
        status="pending",
        priority="normal"
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)

    return {
        "success": True,
        "message": "Support ticket created successfully",
        "ticket_id": str(ticket.id)
    }


@router.get("/support/tickets")
async def get_my_tickets(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's support tickets."""
    result = await db.execute(
        select(SupportTicket)
        .where(SupportTicket.user_email == current_user.email)
        .order_by(SupportTicket.created_at.desc())
    )
    tickets = result.scalars().all()

    return [
        {
            "id": str(t.id),
            "ticket_type": t.ticket_type,
            "status": t.status,
            "priority": t.priority,
            "description": t.description,
            "resolution_notes": t.resolution_notes,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None
        }
        for t in tickets
    ]
