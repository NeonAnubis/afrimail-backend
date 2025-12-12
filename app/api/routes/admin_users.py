from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from app.db.session import get_db
from app.core.security import get_password_hash
from app.models.admin import AdminUser
from app.models.user import User
from app.models.mailbox import MailboxMetadata
from app.models.audit import AuditLog
from app.api.deps.auth import get_current_admin
from app.services.mailcow import mailcow_service, MailcowError

router = APIRouter()


@router.get("")
async def get_users(
    search: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = 1,
    page_size: int = 50,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all users with optional filtering."""
    query = select(User)

    # Apply search filter
    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                User.email.ilike(search_term),
                User.first_name.ilike(search_term),
                User.last_name.ilike(search_term)
            )
        )

    # Apply status filter
    if status_filter == "active":
        query = query.where(User.is_suspended == False)
    elif status_filter == "suspended":
        query = query.where(User.is_suspended == True)

    # Order by created_at desc
    query = query.order_by(User.created_at.desc())

    result = await db.execute(query)
    users = result.scalars().all()

    # Get mailbox metadata for quota info
    user_emails = [u.email for u in users]
    mailbox_result = await db.execute(
        select(MailboxMetadata).where(MailboxMetadata.email.in_(user_emails))
    )
    mailboxes = {m.email: m for m in mailbox_result.scalars().all()}

    return [
        {
            "id": str(u.id),
            "email": u.email,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "date_of_birth": str(u.date_of_birth) if u.date_of_birth else None,
            "gender": u.gender,
            "recovery_email": u.recovery_email,
            "recovery_phone": u.recovery_phone,
            "is_suspended": u.is_suspended,
            "last_login": u.last_login.isoformat() if u.last_login else None,
            "failed_login_attempts": u.failed_login_attempts,
            "locked_until": u.locked_until.isoformat() if u.locked_until else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "updated_at": u.updated_at.isoformat() if u.updated_at else None,
            "quota_bytes": mailboxes.get(u.email, MailboxMetadata(quota_bytes=0)).quota_bytes,
            "usage_bytes": mailboxes.get(u.email, MailboxMetadata(usage_bytes=0)).usage_bytes
        }
        for u in users
    ]


@router.get("/{email}")
async def get_user(
    email: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific user by email."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Get mailbox info
    mailbox_result = await db.execute(
        select(MailboxMetadata).where(MailboxMetadata.email == email)
    )
    mailbox = mailbox_result.scalar_one_or_none()

    return {
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "date_of_birth": str(user.date_of_birth) if user.date_of_birth else None,
        "gender": user.gender,
        "recovery_email": user.recovery_email,
        "recovery_phone": user.recovery_phone,
        "is_suspended": user.is_suspended,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "failed_login_attempts": user.failed_login_attempts,
        "locked_until": user.locked_until.isoformat() if user.locked_until else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        "quota_bytes": mailbox.quota_bytes if mailbox else 0,
        "usage_bytes": mailbox.usage_bytes if mailbox else 0
    }


@router.put("/{email}/suspend")
async def suspend_user(
    email: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Suspend a user account."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Deactivate mailbox in Mailcow first
    if mailcow_service.is_configured:
        try:
            await mailcow_service.deactivate_mailbox(email)
        except MailcowError as e:
            print(f"Failed to deactivate mailbox in Mailcow: {e.message}")
            # Continue with local suspension even if Mailcow fails

    user.is_suspended = True

    # Log action
    log = AuditLog(
        action_type="user_suspended",
        admin_email=current_admin.email,
        target_user_email=email
    )
    db.add(log)

    await db.commit()

    return {"success": True, "message": "User suspended successfully"}


@router.put("/{email}/unsuspend")
async def unsuspend_user(
    email: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Unsuspend a user account."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Activate mailbox in Mailcow first
    if mailcow_service.is_configured:
        try:
            await mailcow_service.activate_mailbox(email)
        except MailcowError as e:
            print(f"Failed to activate mailbox in Mailcow: {e.message}")
            # Continue with local unsuspension even if Mailcow fails

    user.is_suspended = False

    # Log action
    log = AuditLog(
        action_type="user_unsuspended",
        admin_email=current_admin.email,
        target_user_email=email
    )
    db.add(log)

    await db.commit()

    return {"success": True, "message": "User unsuspended successfully"}


@router.put("/{email}/unlock")
async def unlock_user(
    email: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Unlock a locked user account."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    user.failed_login_attempts = 0
    user.locked_until = None

    # Log action
    log = AuditLog(
        action_type="user_unlocked",
        admin_email=current_admin.email,
        target_user_email=email
    )
    db.add(log)

    await db.commit()

    return {"success": True, "message": "User unlocked successfully"}


@router.post("/{email}/reset-password")
async def reset_user_password(
    email: str,
    new_password: str = None,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Reset a user's password."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Generate temporary password if none provided
    if not new_password:
        import secrets
        new_password = secrets.token_urlsafe(12)

    # Update password in Mailcow first
    if mailcow_service.is_configured:
        try:
            await mailcow_service.set_mailbox_password(email, new_password)
        except MailcowError as e:
            print(f"Failed to update password in Mailcow: {e.message}")
            # Continue with local update even if Mailcow fails

    user.password_hash = get_password_hash(new_password)
    user.failed_login_attempts = 0
    user.locked_until = None

    # Log action
    log = AuditLog(
        action_type="password_reset_by_admin",
        admin_email=current_admin.email,
        target_user_email=email
    )
    db.add(log)

    await db.commit()

    return {
        "success": True,
        "message": "Password reset successfully",
        "temporary_password": new_password
    }


class QuotaUpdateRequest(BaseModel):
    quota_bytes: int


@router.put("/{email}/quota")
async def update_user_quota(
    email: str,
    data: QuotaUpdateRequest,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update a user's storage quota."""
    # Check user exists
    user_result = await db.execute(select(User).where(User.email == email))
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    quota_bytes = data.quota_bytes
    quota_gb = quota_bytes / 1073741824  # Convert bytes to GB for logging

    # Update quota in Mailcow first
    if mailcow_service.is_configured:
        try:
            await mailcow_service.update_mailbox_quota(email, quota_bytes)
        except MailcowError as e:
            print(f"Failed to update quota in Mailcow: {e.message}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update quota in mail server: {e.message}"
            )

    # Get or create mailbox metadata
    result = await db.execute(
        select(MailboxMetadata).where(MailboxMetadata.email == email)
    )
    mailbox = result.scalar_one_or_none()

    if not mailbox:
        mailbox = MailboxMetadata(
            email=email,
            user_id=user.id,
            quota_bytes=quota_bytes,
            usage_bytes=0
        )
        db.add(mailbox)
    else:
        mailbox.quota_bytes = quota_bytes

    # Log action
    log = AuditLog(
        action_type="quota_updated",
        admin_email=current_admin.email,
        target_user_email=email,
        details={"quota_gb": quota_gb, "quota_bytes": quota_bytes}
    )
    db.add(log)

    await db.commit()

    return {"success": True, "message": f"Quota updated to {quota_gb:.2f}GB"}


@router.delete("/{email}")
async def delete_user(
    email: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete a user account."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Log action before deletion
    log = AuditLog(
        action_type="user_deleted",
        admin_email=current_admin.email,
        target_user_email=email,
        details={"user_id": str(user.id), "first_name": user.first_name, "last_name": user.last_name}
    )
    db.add(log)

    await db.delete(user)
    await db.commit()

    return {"success": True, "message": "User deleted successfully"}


class BulkUserIdsRequest(BaseModel):
    user_ids: list[str]


@router.post("/bulk/suspend")
async def bulk_suspend_users(
    data: BulkUserIdsRequest,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Bulk suspend users."""
    result = await db.execute(
        select(User).where(User.id.in_(data.user_ids))
    )
    users = result.scalars().all()

    for user in users:
        # Deactivate mailbox in Mailcow
        if mailcow_service.is_configured:
            try:
                await mailcow_service.deactivate_mailbox(user.email)
            except MailcowError as e:
                print(f"Failed to deactivate mailbox in Mailcow for {user.email}: {e.message}")

        user.is_suspended = True
        log = AuditLog(
            action_type="user_suspended",
            admin_email=current_admin.email,
            target_user_email=user.email,
            details={"bulk_action": True}
        )
        db.add(log)

    await db.commit()

    return {"success": True, "message": f"{len(users)} users suspended"}


@router.post("/bulk/unsuspend")
async def bulk_unsuspend_users(
    data: BulkUserIdsRequest,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Bulk unsuspend users."""
    result = await db.execute(
        select(User).where(User.id.in_(data.user_ids))
    )
    users = result.scalars().all()

    for user in users:
        # Activate mailbox in Mailcow
        if mailcow_service.is_configured:
            try:
                await mailcow_service.activate_mailbox(user.email)
            except MailcowError as e:
                print(f"Failed to activate mailbox in Mailcow for {user.email}: {e.message}")

        user.is_suspended = False
        log = AuditLog(
            action_type="user_unsuspended",
            admin_email=current_admin.email,
            target_user_email=user.email,
            details={"bulk_action": True}
        )
        db.add(log)

    await db.commit()

    return {"success": True, "message": f"{len(users)} users unsuspended"}


@router.post("/bulk/delete")
async def bulk_delete_users(
    data: BulkUserIdsRequest,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Bulk delete users."""
    result = await db.execute(
        select(User).where(User.id.in_(data.user_ids))
    )
    users = result.scalars().all()

    for user in users:
        log = AuditLog(
            action_type="user_deleted",
            admin_email=current_admin.email,
            target_user_email=user.email,
            details={"bulk_action": True, "user_id": str(user.id)}
        )
        db.add(log)
        await db.delete(user)

    await db.commit()

    return {"success": True, "message": f"{len(users)} users deleted"}


class BulkQuotaRequest(BaseModel):
    user_ids: list[str]
    quota_bytes: int


@router.post("/bulk/quota")
async def bulk_update_quota(
    data: BulkQuotaRequest,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Bulk update user quotas."""
    result = await db.execute(
        select(User).where(User.id.in_(data.user_ids))
    )
    users = result.scalars().all()

    quota_bytes = data.quota_bytes
    quota_gb = quota_bytes / 1073741824

    for user in users:
        # Update quota in Mailcow
        if mailcow_service.is_configured:
            try:
                await mailcow_service.update_mailbox_quota(user.email, quota_bytes)
            except MailcowError as e:
                print(f"Failed to update quota in Mailcow for {user.email}: {e.message}")

        # Get or create mailbox
        mailbox_result = await db.execute(
            select(MailboxMetadata).where(MailboxMetadata.email == user.email)
        )
        mailbox = mailbox_result.scalar_one_or_none()

        if not mailbox:
            mailbox = MailboxMetadata(
                email=user.email,
                user_id=user.id,
                quota_bytes=quota_bytes,
                usage_bytes=0
            )
            db.add(mailbox)
        else:
            mailbox.quota_bytes = quota_bytes

        log = AuditLog(
            action_type="quota_updated",
            admin_email=current_admin.email,
            target_user_email=user.email,
            details={"bulk_action": True, "quota_gb": quota_gb}
        )
        db.add(log)

    await db.commit()

    return {"success": True, "message": f"Quota updated for {len(users)} users"}


@router.get("/export/users")
async def export_users(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Export users to CSV format."""
    from fastapi.responses import PlainTextResponse

    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()

    # Get mailbox data
    mailbox_result = await db.execute(select(MailboxMetadata))
    mailboxes = {m.email: m for m in mailbox_result.scalars().all()}

    # Build CSV
    csv_lines = ["email,first_name,last_name,recovery_email,recovery_phone,is_suspended,quota_bytes,usage_bytes,last_login,created_at"]

    for user in users:
        mailbox = mailboxes.get(user.email)
        line = f'"{user.email}","{user.first_name}","{user.last_name}","{user.recovery_email or ""}","{user.recovery_phone or ""}",{user.is_suspended},{mailbox.quota_bytes if mailbox else 0},{mailbox.usage_bytes if mailbox else 0},"{user.last_login or ""}","{user.created_at or ""}"'
        csv_lines.append(line)

    csv_content = "\n".join(csv_lines)

    return PlainTextResponse(content=csv_content, media_type="text/csv")


class CSVImportRequest(BaseModel):
    filename: str
    rows: list[dict]


@router.post("/import/csv")
async def import_users_csv(
    data: CSVImportRequest,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Import users from CSV."""
    successful = 0
    failed = 0
    errors = []

    for row in data.rows:
        try:
            email = row.get("email", "").strip()
            if not email:
                errors.append({"email": "N/A", "error": "Email is required"})
                failed += 1
                continue

            # Check if user exists
            existing = await db.execute(select(User).where(User.email == email))
            if existing.scalar_one_or_none():
                errors.append({"email": email, "error": "User already exists"})
                failed += 1
                continue

            # Parse name
            name = row.get("name", "").strip()
            name_parts = name.split(" ", 1) if name else ["User", ""]
            first_name = name_parts[0] if name_parts else "User"
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            # Get password
            password = row.get("password", "changeme123")

            # Create user
            user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                password_hash=get_password_hash(password),
                is_suspended=False
            )
            db.add(user)
            await db.flush()

            # Create mailbox
            quota_bytes = int(row.get("quota_bytes", 5368709120))
            mailbox = MailboxMetadata(
                email=email,
                user_id=user.id,
                quota_bytes=quota_bytes,
                usage_bytes=0
            )
            db.add(mailbox)

            successful += 1

        except Exception as e:
            errors.append({"email": row.get("email", "N/A"), "error": str(e)})
            failed += 1

    await db.commit()

    # Log action
    log = AuditLog(
        action_type="users_imported",
        admin_email=current_admin.email,
        details={"filename": data.filename, "successful": successful, "failed": failed}
    )
    db.add(log)
    await db.commit()

    return {
        "total": successful + failed,
        "successful": successful,
        "failed": failed,
        "errors": errors
    }
