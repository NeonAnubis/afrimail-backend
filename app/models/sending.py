from sqlalchemy import Column, String, Boolean, DateTime, Integer, Numeric, Date, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.sql import func
import uuid

from app.db.session import Base


class SendingTier(Base):
    """Email sending tier configurations."""
    __tablename__ = "sending_tiers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    daily_limit = Column(Integer, nullable=False)
    hourly_limit = Column(Integer, nullable=False)
    price_monthly = Column(Numeric(10, 2), default=0)
    features = Column(JSONB, default=[])
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<SendingTier {self.name}>"


class EmailSendingLimit(Base):
    """User-specific sending configurations."""
    __tablename__ = "email_sending_limits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    tier_id = Column(UUID(as_uuid=True), ForeignKey("sending_tiers.id"), nullable=True)
    tier_name = Column(String, default="free", index=True)
    daily_limit = Column(Integer, default=50)
    hourly_limit = Column(Integer, default=10)
    emails_sent_today = Column(Integer, default=0)
    emails_sent_this_hour = Column(Integer, default=0)
    last_reset_date = Column(Date, server_default=func.current_date())
    last_reset_hour = Column(DateTime(timezone=True), server_default=func.now())
    is_sending_enabled = Column(Boolean, default=True)
    custom_limit_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<EmailSendingLimit user={self.user_id}>"

    @property
    def usage_percent(self) -> float:
        if self.daily_limit == 0:
            return 0.0
        return (self.emails_sent_today / self.daily_limit) * 100


class EmailSendLog(Base):
    """Email sending history."""
    __tablename__ = "email_send_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    recipient_email = Column(String, nullable=False)
    recipient_count = Column(Integer, default=1)
    subject = Column(String, nullable=True)
    status = Column(String, default="sent", index=True)
    failure_reason = Column(Text, nullable=True)
    blocked_reason = Column(Text, nullable=True)
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<EmailSendLog {self.id}>"


class SendingLimitViolation(Base):
    """Abuse tracking."""
    __tablename__ = "sending_limit_violations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    violation_type = Column(String, nullable=False)
    attempted_count = Column(Integer, nullable=False)
    limit_at_time = Column(Integer, nullable=False)
    violation_details = Column(JSONB, default={})
    action_taken = Column(String, default="logged")
    admin_notes = Column(Text, nullable=True)
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self):
        return f"<SendingLimitViolation {self.violation_type}>"
