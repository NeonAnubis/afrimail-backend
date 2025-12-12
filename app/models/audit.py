from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid

from app.db.session import Base


class AuditLog(Base):
    """Comprehensive logging of all admin actions."""
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action_type = Column(String, nullable=False, index=True)
    admin_email = Column(String, nullable=False, index=True)
    target_user_email = Column(String, nullable=True)
    details = Column(JSONB, nullable=True)
    ip_address = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self):
        return f"<AuditLog {self.action_type} by {self.admin_email}>"


class LoginActivity(Base):
    """User login tracking and security."""
    __tablename__ = "login_activity"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_email = Column(String, nullable=False, index=True)
    login_time = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)
    success = Column(Boolean, nullable=False, index=True)
    failure_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<LoginActivity {self.user_email} - {'success' if self.success else 'failed'}>"
