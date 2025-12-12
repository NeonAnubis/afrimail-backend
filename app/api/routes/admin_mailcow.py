"""
Admin Mailcow Management Routes

Provides admin endpoints for direct Mailcow operations:
- Health check and status
- Mailbox management (list, create, update, delete)
- Sync operations
- Logs and statistics
- DKIM management
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

from app.db.session import get_db
from app.models.admin import AdminUser
from app.models.user import User
from app.models.mailbox import MailboxMetadata
from app.api.deps.auth import get_current_admin
from app.services.mailcow import mailcow_service, MailcowError

router = APIRouter()


# ==================== Request/Response Models ====================

class MailboxCreateRequest(BaseModel):
    local_part: str
    domain: str
    password: str
    name: str = ""
    quota_gb: float = 5.0
    active: bool = True


class MailboxUpdateRequest(BaseModel):
    name: Optional[str] = None
    quota_gb: Optional[float] = None
    password: Optional[str] = None
    active: Optional[bool] = None


class QuotaUpdateRequest(BaseModel):
    quota_gb: float


class BulkMailboxAction(BaseModel):
    emails: List[str]
    action: str  # activate, deactivate, delete


# ==================== Health & Status ====================

@router.get("/health")
async def mailcow_health_check(
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Check Mailcow API health and connectivity."""
    if not mailcow_service.is_configured:
        return {
            "status": "not_configured",
            "message": "Mailcow API is not configured. Please set MAILCOW_API_URL and MAILCOW_API_KEY."
        }

    try:
        is_healthy = await mailcow_service.health_check()
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "api_url": mailcow_service.api_url,
            "connected": is_healthy
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "connected": False
        }


@router.get("/status")
async def get_mailcow_status(
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get Mailcow container status and statistics."""
    if not mailcow_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mailcow API is not configured"
        )

    try:
        container_status = await mailcow_service.get_status()
        return {
            "success": True,
            "containers": container_status
        }
    except MailcowError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Mailcow status: {e.message}"
        )


# ==================== Mailbox Management ====================

@router.get("/mailboxes")
async def list_mailboxes(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """List all mailboxes from Mailcow."""
    if not mailcow_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mailcow API is not configured"
        )

    try:
        mailboxes = await mailcow_service.get_mailboxes(domain=domain)
        return {
            "success": True,
            "count": len(mailboxes),
            "mailboxes": [
                {
                    "email": m.email,
                    "username": m.username,
                    "domain": m.domain,
                    "name": m.name,
                    "quota_bytes": m.quota,
                    "quota_used_bytes": m.quota_used,
                    "quota_percentage": m.quota_percentage,
                    "messages": m.messages,
                    "active": m.active,
                    "last_imap_login": m.last_imap_login,
                    "last_smtp_login": m.last_smtp_login,
                    "created": m.created,
                    "modified": m.modified
                }
                for m in mailboxes
            ]
        }
    except MailcowError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list mailboxes: {e.message}"
        )


@router.get("/mailboxes/{email}")
async def get_mailbox(
    email: str,
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get detailed mailbox information from Mailcow."""
    if not mailcow_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mailcow API is not configured"
        )

    try:
        mailbox = await mailcow_service.get_mailbox(email)
        if not mailbox:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mailbox not found: {email}"
            )

        return {
            "success": True,
            "mailbox": {
                "email": mailbox.email,
                "username": mailbox.username,
                "domain": mailbox.domain,
                "name": mailbox.name,
                "quota_bytes": mailbox.quota,
                "quota_used_bytes": mailbox.quota_used,
                "quota_percentage": mailbox.quota_percentage,
                "messages": mailbox.messages,
                "active": mailbox.active,
                "last_imap_login": mailbox.last_imap_login,
                "last_smtp_login": mailbox.last_smtp_login,
                "last_pop3_login": mailbox.last_pop3_login,
                "created": mailbox.created,
                "modified": mailbox.modified
            }
        }
    except MailcowError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get mailbox: {e.message}"
        )


@router.post("/mailboxes")
async def create_mailbox(
    data: MailboxCreateRequest,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a new mailbox in Mailcow (without local user account)."""
    if not mailcow_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mailcow API is not configured"
        )

    try:
        quota_bytes = int(data.quota_gb * 1024 * 1024 * 1024)
        await mailcow_service.create_mailbox(
            local_part=data.local_part,
            domain=data.domain,
            password=data.password,
            name=data.name,
            quota=quota_bytes,
            active=data.active
        )

        email = f"{data.local_part}@{data.domain}"

        # Create local mailbox metadata
        mailbox_meta = MailboxMetadata(
            email=email,
            quota_bytes=quota_bytes,
            usage_bytes=0
        )
        db.add(mailbox_meta)
        await db.commit()

        return {
            "success": True,
            "message": f"Mailbox {email} created successfully",
            "email": email
        }
    except MailcowError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create mailbox: {e.message}"
        )


@router.put("/mailboxes/{email}")
async def update_mailbox(
    email: str,
    data: MailboxUpdateRequest,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update a mailbox in Mailcow."""
    if not mailcow_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mailcow API is not configured"
        )

    try:
        quota_bytes = int(data.quota_gb * 1024 * 1024 * 1024) if data.quota_gb else None
        await mailcow_service.update_mailbox(
            email=email,
            name=data.name,
            quota=quota_bytes,
            password=data.password,
            active=data.active
        )

        # Update local mailbox metadata if quota changed
        if quota_bytes:
            result = await db.execute(
                select(MailboxMetadata).where(MailboxMetadata.email == email)
            )
            mailbox_meta = result.scalar_one_or_none()
            if mailbox_meta:
                mailbox_meta.quota_bytes = quota_bytes
                await db.commit()

        return {
            "success": True,
            "message": f"Mailbox {email} updated successfully"
        }
    except MailcowError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update mailbox: {e.message}"
        )


@router.delete("/mailboxes/{email}")
async def delete_mailbox(
    email: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete a mailbox from Mailcow."""
    if not mailcow_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mailcow API is not configured"
        )

    try:
        await mailcow_service.delete_mailbox(email)

        # Delete local mailbox metadata
        result = await db.execute(
            select(MailboxMetadata).where(MailboxMetadata.email == email)
        )
        mailbox_meta = result.scalar_one_or_none()
        if mailbox_meta:
            await db.delete(mailbox_meta)
            await db.commit()

        return {
            "success": True,
            "message": f"Mailbox {email} deleted successfully"
        }
    except MailcowError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete mailbox: {e.message}"
        )


@router.post("/mailboxes/{email}/activate")
async def activate_mailbox(
    email: str,
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Activate a mailbox in Mailcow."""
    if not mailcow_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mailcow API is not configured"
        )

    try:
        await mailcow_service.activate_mailbox(email)
        return {
            "success": True,
            "message": f"Mailbox {email} activated"
        }
    except MailcowError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate mailbox: {e.message}"
        )


@router.post("/mailboxes/{email}/deactivate")
async def deactivate_mailbox(
    email: str,
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Deactivate a mailbox in Mailcow (soft disable)."""
    if not mailcow_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mailcow API is not configured"
        )

    try:
        await mailcow_service.deactivate_mailbox(email)
        return {
            "success": True,
            "message": f"Mailbox {email} deactivated"
        }
    except MailcowError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deactivate mailbox: {e.message}"
        )


@router.put("/mailboxes/{email}/quota")
async def update_mailbox_quota(
    email: str,
    data: QuotaUpdateRequest,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update mailbox quota in Mailcow."""
    if not mailcow_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mailcow API is not configured"
        )

    try:
        quota_bytes = int(data.quota_gb * 1024 * 1024 * 1024)
        await mailcow_service.update_mailbox_quota(email, quota_bytes)

        # Update local mailbox metadata
        result = await db.execute(
            select(MailboxMetadata).where(MailboxMetadata.email == email)
        )
        mailbox_meta = result.scalar_one_or_none()
        if mailbox_meta:
            mailbox_meta.quota_bytes = quota_bytes
            await db.commit()

        return {
            "success": True,
            "message": f"Quota updated to {data.quota_gb}GB for {email}"
        }
    except MailcowError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update quota: {e.message}"
        )


@router.post("/mailboxes/bulk")
async def bulk_mailbox_action(
    data: BulkMailboxAction,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Perform bulk actions on mailboxes."""
    if not mailcow_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mailcow API is not configured"
        )

    results = {"success": [], "failed": []}

    for email in data.emails:
        try:
            if data.action == "activate":
                await mailcow_service.activate_mailbox(email)
            elif data.action == "deactivate":
                await mailcow_service.deactivate_mailbox(email)
            elif data.action == "delete":
                await mailcow_service.delete_mailbox(email)
                # Delete local metadata
                result = await db.execute(
                    select(MailboxMetadata).where(MailboxMetadata.email == email)
                )
                mailbox_meta = result.scalar_one_or_none()
                if mailbox_meta:
                    await db.delete(mailbox_meta)
            else:
                results["failed"].append({"email": email, "error": "Unknown action"})
                continue

            results["success"].append(email)
        except MailcowError as e:
            results["failed"].append({"email": email, "error": e.message})

    await db.commit()

    return {
        "success": True,
        "action": data.action,
        "results": results
    }


# ==================== Sync Operations ====================

@router.post("/sync/mailboxes")
async def sync_all_mailboxes(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Sync all mailbox metadata from Mailcow to local database."""
    if not mailcow_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mailcow API is not configured"
        )

    try:
        mailboxes = await mailcow_service.get_mailboxes()
        synced = 0
        created = 0

        for mb in mailboxes:
            result = await db.execute(
                select(MailboxMetadata).where(MailboxMetadata.email == mb.email)
            )
            metadata = result.scalar_one_or_none()

            if metadata:
                metadata.quota_bytes = mb.quota
                metadata.usage_bytes = mb.quota_used
                synced += 1
            else:
                metadata = MailboxMetadata(
                    email=mb.email,
                    quota_bytes=mb.quota,
                    usage_bytes=mb.quota_used
                )
                db.add(metadata)
                created += 1

        await db.commit()

        return {
            "success": True,
            "message": f"Synced {synced} mailboxes, created {created} new records",
            "total_mailboxes": len(mailboxes),
            "synced": synced,
            "created": created
        }
    except MailcowError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync mailboxes: {e.message}"
        )


@router.post("/sync/mailbox/{email}")
async def sync_single_mailbox(
    email: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Sync a single mailbox's metadata from Mailcow."""
    if not mailcow_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mailcow API is not configured"
        )

    try:
        result = await mailcow_service.sync_mailbox_to_db(email, db)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mailbox not found in Mailcow: {email}"
            )

        return {
            "success": True,
            "message": f"Mailbox {email} synced successfully",
            "data": result
        }
    except MailcowError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync mailbox: {e.message}"
        )


# ==================== DKIM Management ====================

@router.get("/dkim/{domain}")
async def get_dkim(
    domain: str,
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get DKIM key for a domain."""
    if not mailcow_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mailcow API is not configured"
        )

    try:
        dkim = await mailcow_service.get_dkim(domain)
        return {
            "success": True,
            "domain": domain,
            "dkim": dkim
        }
    except MailcowError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get DKIM: {e.message}"
        )


@router.post("/dkim/{domain}")
async def create_dkim(
    domain: str,
    key_length: int = Query(2048, description="DKIM key length (1024, 2048, 4096)"),
    selector: str = Query("dkim", description="DKIM selector"),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Generate DKIM key for a domain."""
    if not mailcow_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mailcow API is not configured"
        )

    if key_length not in [1024, 2048, 4096]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Key length must be 1024, 2048, or 4096"
        )

    try:
        result = await mailcow_service.create_dkim(domain, key_length, selector)
        return {
            "success": True,
            "message": f"DKIM key generated for {domain}",
            "result": result
        }
    except MailcowError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create DKIM: {e.message}"
        )


@router.delete("/dkim/{domain}")
async def delete_dkim(
    domain: str,
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Delete DKIM key for a domain."""
    if not mailcow_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mailcow API is not configured"
        )

    try:
        await mailcow_service.delete_dkim(domain)
        return {
            "success": True,
            "message": f"DKIM key deleted for {domain}"
        }
    except MailcowError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete DKIM: {e.message}"
        )


# ==================== Logs & Statistics ====================

@router.get("/logs/{log_type}")
async def get_logs(
    log_type: str,
    count: int = Query(100, ge=1, le=1000, description="Number of log entries"),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """
    Get logs from Mailcow.

    Log types: dovecot, postfix, rspamd-history, sogo, watchdog, acme, api, autodiscover, netfilter
    """
    if not mailcow_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mailcow API is not configured"
        )

    valid_log_types = [
        "dovecot", "postfix", "rspamd-history", "sogo",
        "watchdog", "acme", "api", "autodiscover", "netfilter"
    ]

    if log_type not in valid_log_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid log type. Valid types: {', '.join(valid_log_types)}"
        )

    try:
        logs = await mailcow_service.get_logs(log_type, count)
        return {
            "success": True,
            "log_type": log_type,
            "count": count,
            "logs": logs
        }
    except MailcowError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get logs: {e.message}"
        )


@router.get("/stats/rspamd")
async def get_rspamd_stats(
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get Rspamd spam filter statistics."""
    if not mailcow_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mailcow API is not configured"
        )

    try:
        stats = await mailcow_service.get_rspamd_stats()
        return {
            "success": True,
            "stats": stats
        }
    except MailcowError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Rspamd stats: {e.message}"
        )


@router.get("/quarantine")
async def get_quarantine(
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get quarantined messages."""
    if not mailcow_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mailcow API is not configured"
        )

    try:
        quarantine = await mailcow_service.get_quarantine()
        return {
            "success": True,
            "quarantine": quarantine
        }
    except MailcowError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get quarantine: {e.message}"
        )


@router.get("/mail-queue")
async def get_mail_queue(
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get mail queue."""
    if not mailcow_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mailcow API is not configured"
        )

    try:
        queue = await mailcow_service.get_mail_queue()
        return {
            "success": True,
            "queue": queue
        }
    except MailcowError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get mail queue: {e.message}"
        )


# ==================== Rate Limiting ====================

@router.get("/ratelimits")
async def get_ratelimits(
    mailbox: Optional[str] = Query(None, description="Filter by mailbox email"),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get rate limits for mailboxes."""
    if not mailcow_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mailcow API is not configured"
        )

    try:
        ratelimits = await mailcow_service.get_ratelimits(mailbox)
        return {
            "success": True,
            "ratelimits": ratelimits
        }
    except MailcowError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get rate limits: {e.message}"
        )


class RateLimitUpdate(BaseModel):
    rate_limit_value: int = 0  # 0 = unlimited
    rate_limit_frame: str = "h"  # s=second, m=minute, h=hour, d=day


@router.put("/ratelimits/{mailbox}")
async def set_ratelimit(
    mailbox: str,
    data: RateLimitUpdate,
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Set rate limit for a mailbox."""
    if not mailcow_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mailcow API is not configured"
        )

    if data.rate_limit_frame not in ["s", "m", "h", "d"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rate limit frame must be s, m, h, or d"
        )

    try:
        await mailcow_service.set_ratelimit(
            mailbox,
            data.rate_limit_value,
            data.rate_limit_frame
        )
        return {
            "success": True,
            "message": f"Rate limit set for {mailbox}",
            "rate_limit_value": data.rate_limit_value,
            "rate_limit_frame": data.rate_limit_frame
        }
    except MailcowError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set rate limit: {e.message}"
        )
