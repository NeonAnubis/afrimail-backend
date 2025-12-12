from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List

from app.db.session import get_db
from app.models.admin import AdminUser
from app.models.alias import EmailAlias
from app.api.deps.auth import get_current_admin
from app.services.mailcow import mailcow_service, MailcowError

router = APIRouter()


class AliasCreate(BaseModel):
    alias_address: str
    target_addresses: List[str]
    is_distribution_list: bool = False
    description: Optional[str] = None


class AliasUpdate(BaseModel):
    target_addresses: Optional[List[str]] = None
    description: Optional[str] = None
    is_distribution_list: Optional[bool] = None


@router.get("")
async def get_aliases(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all email aliases with Mailcow sync status."""
    result = await db.execute(
        select(EmailAlias).order_by(EmailAlias.alias_address)
    )
    aliases = result.scalars().all()

    # Get Mailcow aliases for comparison
    mailcow_aliases = {}
    if mailcow_service.is_configured:
        try:
            mc_aliases = await mailcow_service.get_aliases()
            mailcow_aliases = {a.address: a for a in mc_aliases}
        except MailcowError as e:
            print(f"Failed to fetch aliases from Mailcow: {e.message}")

    return [
        {
            "id": str(a.id),
            "alias_address": a.alias_address,
            "target_addresses": a.target_addresses,
            "is_distribution_list": a.is_distribution_list,
            "description": a.description,
            "active": a.active,
            "created_by": a.created_by,
            "mailcow_id": a.mailcow_id,
            "synced_with_mailcow": a.alias_address in mailcow_aliases,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "updated_at": a.updated_at.isoformat() if a.updated_at else None
        }
        for a in aliases
    ]


@router.post("")
async def create_alias(
    data: AliasCreate,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a new email alias in both local database and Mailcow."""
    alias_address = data.alias_address.lower()

    # Check if alias already exists locally
    existing = await db.execute(
        select(EmailAlias).where(EmailAlias.alias_address == alias_address)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alias address already exists"
        )

    # Create alias in Mailcow first
    mailcow_id = None
    if mailcow_service.is_configured:
        try:
            # Mailcow expects comma-separated targets
            goto = ",".join(data.target_addresses)
            result = await mailcow_service.create_alias(
                address=alias_address,
                goto=goto,
                active=True
            )
            # Try to extract Mailcow alias ID from response
            if isinstance(result, dict) and "items" in result:
                for item in result.get("items", []):
                    if isinstance(item, dict) and item.get("type") == "success":
                        # Mailcow returns success message, we need to fetch the ID
                        mc_aliases = await mailcow_service.get_aliases()
                        for mc_alias in mc_aliases:
                            if mc_alias.address == alias_address:
                                mailcow_id = str(mc_alias.id)
                                break
        except MailcowError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create alias in mail server: {e.message}"
            )

    # Create in local database
    alias = EmailAlias(
        alias_address=alias_address,
        target_addresses=data.target_addresses,
        is_distribution_list=data.is_distribution_list,
        description=data.description,
        active=True,
        created_by=current_admin.email,
        mailcow_id=mailcow_id
    )
    db.add(alias)
    await db.commit()
    await db.refresh(alias)

    return {
        "id": str(alias.id),
        "alias_address": alias.alias_address,
        "target_addresses": alias.target_addresses,
        "is_distribution_list": alias.is_distribution_list,
        "description": alias.description,
        "active": alias.active,
        "mailcow_id": alias.mailcow_id
    }


@router.put("/{alias_id}")
async def update_alias(
    alias_id: str,
    data: AliasUpdate,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update an email alias in both local database and Mailcow."""
    result = await db.execute(
        select(EmailAlias).where(EmailAlias.id == alias_id)
    )
    alias = result.scalar_one_or_none()

    if not alias:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alias not found"
        )

    # Update in Mailcow first if we have a mailcow_id
    if mailcow_service.is_configured and alias.mailcow_id:
        try:
            goto = ",".join(data.target_addresses) if data.target_addresses else None
            await mailcow_service.update_alias(
                alias_id=int(alias.mailcow_id),
                goto=goto
            )
        except MailcowError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update alias in mail server: {e.message}"
            )

    # Update local database
    if data.target_addresses is not None:
        alias.target_addresses = data.target_addresses
    if data.description is not None:
        alias.description = data.description
    if data.is_distribution_list is not None:
        alias.is_distribution_list = data.is_distribution_list

    await db.commit()
    await db.refresh(alias)

    return {"success": True, "message": "Alias updated successfully"}


@router.put("/{alias_id}/toggle")
async def toggle_alias(
    alias_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Toggle alias active status in both local database and Mailcow."""
    result = await db.execute(
        select(EmailAlias).where(EmailAlias.id == alias_id)
    )
    alias = result.scalar_one_or_none()

    if not alias:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alias not found"
        )

    new_status = not alias.active

    # Update in Mailcow first if we have a mailcow_id
    if mailcow_service.is_configured and alias.mailcow_id:
        try:
            await mailcow_service.update_alias(
                alias_id=int(alias.mailcow_id),
                active=new_status
            )
        except MailcowError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update alias in mail server: {e.message}"
            )

    alias.active = new_status
    await db.commit()

    return {
        "success": True,
        "message": f"Alias {'activated' if alias.active else 'deactivated'}",
        "active": alias.active
    }


@router.delete("/{alias_id}")
async def delete_alias(
    alias_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete an email alias from both local database and Mailcow."""
    result = await db.execute(
        select(EmailAlias).where(EmailAlias.id == alias_id)
    )
    alias = result.scalar_one_or_none()

    if not alias:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alias not found"
        )

    # Delete from Mailcow first if we have a mailcow_id
    if mailcow_service.is_configured and alias.mailcow_id:
        try:
            await mailcow_service.delete_alias(int(alias.mailcow_id))
        except MailcowError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete alias from mail server: {e.message}"
            )

    # Delete from local database
    await db.delete(alias)
    await db.commit()

    return {"success": True, "message": "Alias deleted successfully"}
