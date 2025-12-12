from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID

from app.db.session import get_db
from app.models.admin import AdminUser
from app.models.user import User
from app.models.group import UserGroup, UserGroupMember
from app.api.deps.auth import get_current_admin

router = APIRouter()


class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    color: str = "blue"


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None


@router.get("")
async def get_groups(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all user groups with member counts."""
    # Get groups with member counts
    result = await db.execute(
        select(
            UserGroup,
            func.count(UserGroupMember.id).label("member_count")
        )
        .outerjoin(UserGroupMember, UserGroup.id == UserGroupMember.group_id)
        .group_by(UserGroup.id)
        .order_by(UserGroup.name)
    )
    groups = result.all()

    return [
        {
            "id": str(g.UserGroup.id),
            "name": g.UserGroup.name,
            "description": g.UserGroup.description,
            "color": g.UserGroup.color,
            "member_count": g.member_count,
            "created_at": g.UserGroup.created_at.isoformat() if g.UserGroup.created_at else None
        }
        for g in groups
    ]


@router.post("")
async def create_group(
    data: GroupCreate,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a new user group."""
    # Check if name already exists
    existing = await db.execute(
        select(UserGroup).where(UserGroup.name == data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Group with this name already exists"
        )

    group = UserGroup(
        name=data.name,
        description=data.description,
        color=data.color
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)

    return {
        "id": str(group.id),
        "name": group.name,
        "description": group.description,
        "color": group.color,
        "member_count": 0,
        "created_at": group.created_at.isoformat() if group.created_at else None
    }


@router.put("/{group_id}")
async def update_group(
    group_id: str,
    data: GroupUpdate,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update a user group."""
    result = await db.execute(
        select(UserGroup).where(UserGroup.id == group_id)
    )
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )

    if data.name is not None:
        group.name = data.name
    if data.description is not None:
        group.description = data.description
    if data.color is not None:
        group.color = data.color

    await db.commit()
    await db.refresh(group)

    return {
        "id": str(group.id),
        "name": group.name,
        "description": group.description,
        "color": group.color
    }


@router.delete("/{group_id}")
async def delete_group(
    group_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete a user group."""
    result = await db.execute(
        select(UserGroup).where(UserGroup.id == group_id)
    )
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )

    await db.delete(group)
    await db.commit()

    return {"success": True, "message": "Group deleted successfully"}


@router.get("/{group_id}/members")
async def get_group_members(
    group_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get members of a group."""
    # Verify group exists
    group_result = await db.execute(
        select(UserGroup).where(UserGroup.id == group_id)
    )
    group = group_result.scalar_one_or_none()

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )

    # Get members with user info
    result = await db.execute(
        select(UserGroupMember, User)
        .join(User, UserGroupMember.user_id == User.id)
        .where(UserGroupMember.group_id == group_id)
        .order_by(User.email)
    )
    members = result.all()

    return [
        {
            "id": str(m.User.id),
            "email": m.User.email,
            "name": f"{m.User.first_name} {m.User.last_name}",
            "first_name": m.User.first_name,
            "last_name": m.User.last_name,
            "is_suspended": m.User.is_suspended,
            "added_at": m.UserGroupMember.added_at.isoformat() if m.UserGroupMember.added_at else None,
            "created_at": m.User.created_at.isoformat() if m.User.created_at else None
        }
        for m in members
    ]


@router.post("/{group_id}/members")
async def add_group_member(
    group_id: str,
    user_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Add a user to a group."""
    # Verify group exists
    group_result = await db.execute(
        select(UserGroup).where(UserGroup.id == group_id)
    )
    if not group_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )

    # Verify user exists
    user_result = await db.execute(
        select(User).where(User.id == user_id)
    )
    if not user_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check if already a member
    existing = await db.execute(
        select(UserGroupMember)
        .where(UserGroupMember.group_id == group_id)
        .where(UserGroupMember.user_id == user_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this group"
        )

    member = UserGroupMember(
        user_id=user_id,
        group_id=group_id,
        added_by=current_admin.id
    )
    db.add(member)
    await db.commit()

    return {"success": True, "message": "Member added successfully"}


class AddMembersRequest(BaseModel):
    user_ids: List[str]


@router.post("/{group_id}/members/add")
async def add_group_members(
    group_id: str,
    data: AddMembersRequest,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Add multiple users to a group."""
    # Verify group exists
    group_result = await db.execute(
        select(UserGroup).where(UserGroup.id == group_id)
    )
    if not group_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )

    # Get existing members
    existing_result = await db.execute(
        select(UserGroupMember.user_id)
        .where(UserGroupMember.group_id == group_id)
    )
    existing_user_ids = {str(r[0]) for r in existing_result.all()}

    added = 0
    for user_id in data.user_ids:
        if user_id not in existing_user_ids:
            member = UserGroupMember(
                user_id=user_id,
                group_id=group_id,
                added_by=current_admin.id
            )
            db.add(member)
            added += 1

    await db.commit()

    return {"success": True, "message": f"{added} members added successfully"}


@router.post("/{group_id}/bulk-add")
async def bulk_add_members(
    group_id: str,
    user_ids: List[str],
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Bulk add users to a group."""
    # Verify group exists
    group_result = await db.execute(
        select(UserGroup).where(UserGroup.id == group_id)
    )
    if not group_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )

    # Get existing members
    existing_result = await db.execute(
        select(UserGroupMember.user_id)
        .where(UserGroupMember.group_id == group_id)
    )
    existing_user_ids = {str(r[0]) for r in existing_result.all()}

    added = 0
    for user_id in user_ids:
        if user_id not in existing_user_ids:
            member = UserGroupMember(
                user_id=user_id,
                group_id=group_id,
                added_by=current_admin.id
            )
            db.add(member)
            added += 1

    await db.commit()

    return {"success": True, "message": f"{added} members added successfully"}


@router.delete("/{group_id}/members/{user_id}")
async def remove_group_member(
    group_id: str,
    user_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Remove a user from a group."""
    result = await db.execute(
        select(UserGroupMember)
        .where(UserGroupMember.group_id == group_id)
        .where(UserGroupMember.user_id == user_id)
    )
    member = result.scalar_one_or_none()

    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found in group"
        )

    await db.delete(member)
    await db.commit()

    return {"success": True, "message": "Member removed successfully"}
