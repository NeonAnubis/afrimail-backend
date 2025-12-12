from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.db.session import get_db
from app.models.admin import AdminUser
from app.models.template import UserTemplate
from app.api.deps.auth import get_current_admin

router = APIRouter()


class TemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    quota_bytes: int = 5368709120  # 5GB default
    permissions: Dict[str, Any] = {}


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    quota_bytes: Optional[int] = None
    permissions: Optional[Dict[str, Any]] = None


@router.get("")
async def get_templates(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all user templates."""
    result = await db.execute(
        select(UserTemplate).order_by(UserTemplate.name)
    )
    templates = result.scalars().all()

    return [
        {
            "id": str(t.id),
            "name": t.name,
            "description": t.description,
            "quota_bytes": t.quota_bytes,
            "permissions": t.permissions,
            "is_system_template": t.is_system_template,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None
        }
        for t in templates
    ]


@router.post("")
async def create_template(
    data: TemplateCreate,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a new user template."""
    # Check if name already exists
    existing = await db.execute(
        select(UserTemplate).where(UserTemplate.name == data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Template with this name already exists"
        )

    template = UserTemplate(
        name=data.name,
        description=data.description,
        quota_bytes=data.quota_bytes,
        permissions=data.permissions,
        is_system_template=False,
        created_by=current_admin.id
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    return {
        "id": str(template.id),
        "name": template.name,
        "description": template.description,
        "quota_bytes": template.quota_bytes,
        "permissions": template.permissions
    }


@router.put("/{template_id}")
async def update_template(
    template_id: str,
    data: TemplateUpdate,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update a user template."""
    result = await db.execute(
        select(UserTemplate).where(UserTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    if template.is_system_template:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify system templates"
        )

    if data.name is not None:
        template.name = data.name
    if data.description is not None:
        template.description = data.description
    if data.quota_bytes is not None:
        template.quota_bytes = data.quota_bytes
    if data.permissions is not None:
        template.permissions = data.permissions

    await db.commit()
    await db.refresh(template)

    return {"success": True, "message": "Template updated successfully"}


@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete a user template."""
    result = await db.execute(
        select(UserTemplate).where(UserTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    if template.is_system_template:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete system templates"
        )

    await db.delete(template)
    await db.commit()

    return {"success": True, "message": "Template deleted successfully"}
