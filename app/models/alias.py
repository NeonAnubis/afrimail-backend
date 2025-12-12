from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.sql import func
import uuid

from app.db.session import Base


class EmailAlias(Base):
    """Email alias and distribution list management."""
    __tablename__ = "email_aliases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alias_address = Column(String, unique=True, nullable=False, index=True)
    target_addresses = Column(ARRAY(String), nullable=False)
    is_distribution_list = Column(Boolean, default=False)
    description = Column(Text, nullable=True)
    active = Column(Boolean, default=True, index=True)
    created_by = Column(String, nullable=True)
    mailcow_id = Column(String, nullable=True, index=True)  # Mailcow alias ID for sync
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<EmailAlias {self.alias_address}>"
