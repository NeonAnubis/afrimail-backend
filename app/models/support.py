from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.db.session import Base


class SupportTicket(Base):
    """User support request management."""
    __tablename__ = "support_tickets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_type = Column(String, nullable=False)  # password_reset, account_unlock, quota_increase, general
    user_email = Column(String, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users_extended.id", ondelete="SET NULL"), nullable=True)
    status = Column(String, default="pending", index=True)  # pending, in_progress, resolved, rejected
    priority = Column(String, default="normal")  # low, normal, high, urgent
    subject = Column(String, nullable=True)
    message = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    assigned_to = Column(String, nullable=True)
    resolved_by = Column(String, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<SupportTicket {self.id} - {self.ticket_type}>"


class Announcement(Base):
    """System-wide announcements."""
    __tablename__ = "announcements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    target_group = Column(String, default="all")
    priority = Column(String, default="normal")  # low, normal, high, urgent
    published = Column(Boolean, default=False, index=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self):
        return f"<Announcement {self.title}>"
