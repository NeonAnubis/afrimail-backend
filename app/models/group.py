from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.db.session import Base


class UserGroup(Base):
    """User group organization."""
    __tablename__ = "user_groups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    color = Column(String, default="blue")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship
    members = relationship("UserGroupMember", back_populates="group", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<UserGroup {self.name}>"


class UserGroupMember(Base):
    """Group membership."""
    __tablename__ = "user_group_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users_extended.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id = Column(UUID(as_uuid=True), ForeignKey("user_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    added_by = Column(UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True)

    # Relationship
    group = relationship("UserGroup", back_populates="members")

    def __repr__(self):
        return f"<UserGroupMember user={self.user_id} group={self.group_id}>"
