from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import secrets

from app.db.session import get_db
from app.models.admin import AdminUser
from app.models.domain import MailDomain
from app.api.deps.auth import get_current_admin
from app.services.mailcow import mailcow_service, MailcowError

router = APIRouter()


class DomainCreate(BaseModel):
    domain: str
    description: Optional[str] = None
    is_primary: bool = False
    max_aliases: int = 400
    max_mailboxes: int = 100
    max_quota_per_mailbox_gb: int = 10  # GB
    total_quota_gb: int = 100  # GB
    default_mailbox_quota_gb: int = 5  # GB


class DomainUpdate(BaseModel):
    description: Optional[str] = None
    is_active: Optional[bool] = None
    is_primary: Optional[bool] = None
    max_aliases: Optional[int] = None
    max_mailboxes: Optional[int] = None
    max_quota_per_mailbox_gb: Optional[int] = None
    total_quota_gb: Optional[int] = None


@router.get("")
async def get_domains(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all mail domains with Mailcow statistics."""
    result = await db.execute(
        select(MailDomain).order_by(MailDomain.is_primary.desc(), MailDomain.domain)
    )
    domains = result.scalars().all()

    # Get additional stats from Mailcow
    mailcow_domains = {}
    if mailcow_service.is_configured:
        try:
            mc_domains = await mailcow_service.get_domains()
            mailcow_domains = {d.domain: d for d in mc_domains}
        except MailcowError as e:
            print(f"Failed to fetch domains from Mailcow: {e.message}")

    response = []
    for d in domains:
        domain_data = {
            "id": str(d.id),
            "domain": d.domain,
            "is_primary": d.is_primary,
            "is_active": d.is_active,
            "description": d.description,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "updated_at": d.updated_at.isoformat() if d.updated_at else None
        }

        # Add Mailcow stats if available
        if d.domain in mailcow_domains:
            mc = mailcow_domains[d.domain]
            domain_data.update({
                "mailboxes_count": mc.max_mailboxes - mc.mailboxes,
                "max_mailboxes": mc.max_mailboxes,
                "aliases_count": mc.max_aliases - mc.aliases,
                "max_aliases": mc.max_aliases,
                "quota_bytes": mc.quota,
                "quota_used_bytes": mc.quota_used,
                "quota_percentage": mc.quota_percentage,
            })

        response.append(domain_data)

    return response


class DomainAddRequest(BaseModel):
    domain: str


@router.post("/add")
async def add_domain(
    data: DomainAddRequest,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Add a new mail domain (simple form)."""
    # Check if domain already exists
    existing = await db.execute(
        select(MailDomain).where(MailDomain.domain == data.domain.lower())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain already exists"
        )

    domain = MailDomain(
        domain=data.domain.lower(),
        is_primary=False,
        is_active=True
    )
    db.add(domain)
    await db.commit()
    await db.refresh(domain)

    return {
        "id": str(domain.id),
        "domain": domain.domain,
        "is_primary": domain.is_primary,
        "is_active": domain.is_active
    }


@router.post("")
async def create_domain(
    data: DomainCreate,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Add a new mail domain to both local database and Mailcow."""
    domain_name = data.domain.lower()

    # Check if domain already exists locally
    existing = await db.execute(
        select(MailDomain).where(MailDomain.domain == domain_name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain already exists"
        )

    # Create domain in Mailcow first
    if mailcow_service.is_configured:
        try:
            await mailcow_service.create_domain(
                domain=domain_name,
                description=data.description or "",
                max_aliases=data.max_aliases,
                max_mailboxes=data.max_mailboxes,
                max_quota_per_mailbox=data.max_quota_per_mailbox_gb * 1024 * 1024 * 1024,
                total_quota=data.total_quota_gb * 1024 * 1024 * 1024,
                default_mailbox_quota=data.default_mailbox_quota_gb * 1024 * 1024 * 1024,
                active=True
            )
        except MailcowError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create domain in mail server: {e.message}"
            )

    # If setting as primary, unset other primary domains
    if data.is_primary:
        result = await db.execute(select(MailDomain).where(MailDomain.is_primary == True))
        for domain in result.scalars().all():
            domain.is_primary = False

    # Create in local database
    domain = MailDomain(
        domain=domain_name,
        description=data.description,
        is_primary=data.is_primary,
        is_active=True
    )
    db.add(domain)
    await db.commit()
    await db.refresh(domain)

    return {
        "id": str(domain.id),
        "domain": domain.domain,
        "is_primary": domain.is_primary,
        "is_active": domain.is_active
    }


@router.put("/{domain_id}")
async def update_domain(
    domain_id: str,
    data: DomainUpdate,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update a mail domain in both local database and Mailcow."""
    result = await db.execute(
        select(MailDomain).where(MailDomain.id == domain_id)
    )
    domain = result.scalar_one_or_none()

    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found"
        )

    # Update in Mailcow first
    if mailcow_service.is_configured:
        try:
            await mailcow_service.update_domain(
                domain=domain.domain,
                description=data.description,
                max_aliases=data.max_aliases,
                max_mailboxes=data.max_mailboxes,
                max_quota_per_mailbox=data.max_quota_per_mailbox_gb * 1024 * 1024 * 1024 if data.max_quota_per_mailbox_gb else None,
                total_quota=data.total_quota_gb * 1024 * 1024 * 1024 if data.total_quota_gb else None,
                active=data.is_active
            )
        except MailcowError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update domain in mail server: {e.message}"
            )

    # Update local database
    if data.description is not None:
        domain.description = data.description
    if data.is_active is not None:
        domain.is_active = data.is_active
    if data.is_primary is not None and data.is_primary:
        # Unset other primary domains
        all_domains = await db.execute(select(MailDomain).where(MailDomain.is_primary == True))
        for d in all_domains.scalars().all():
            d.is_primary = False
        domain.is_primary = True

    await db.commit()
    await db.refresh(domain)

    return {"success": True, "message": "Domain updated successfully"}


@router.post("/{domain_id}/verify")
async def verify_domain(
    domain_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Verify a domain (placeholder for DNS verification)."""
    result = await db.execute(
        select(MailDomain).where(MailDomain.id == domain_id)
    )
    domain = result.scalar_one_or_none()

    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found"
        )

    # In production, this would perform actual DNS verification
    # For now, just mark as verified/active
    domain.is_active = True
    await db.commit()

    return {
        "success": True,
        "message": "Domain verified successfully",
        "is_active": domain.is_active
    }


@router.delete("/{domain_id}")
async def delete_domain(
    domain_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete a mail domain from both local database and Mailcow."""
    result = await db.execute(
        select(MailDomain).where(MailDomain.id == domain_id)
    )
    domain = result.scalar_one_or_none()

    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found"
        )

    if domain.is_primary:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete primary domain"
        )

    # Delete from Mailcow first
    if mailcow_service.is_configured:
        try:
            await mailcow_service.delete_domain(domain.domain)
        except MailcowError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete domain from mail server: {e.message}"
            )

    # Delete from local database
    await db.delete(domain)
    await db.commit()

    return {"success": True, "message": "Domain deleted successfully"}
