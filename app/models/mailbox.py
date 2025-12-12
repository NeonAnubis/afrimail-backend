from sqlalchemy import Column, String, BigInteger, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.db.session import Base


class MailboxMetadata(Base):
    """Cached mailbox quota information from Mailcow."""
    __tablename__ = "mailbox_metadata"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users_extended.id", ondelete="CASCADE"), nullable=True)
    quota_bytes = Column(BigInteger, default=0)
    usage_bytes = Column(BigInteger, default=0)
    last_synced = Column(DateTime(timezone=True), server_default=func.now())
    last_sync = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<MailboxMetadata {self.email}>"

    @property
    def quota_used_percentage(self) -> float:
        if self.quota_bytes == 0:
            return 0.0
        return (self.usage_bytes / self.quota_bytes) * 100
