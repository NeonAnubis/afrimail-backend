from sqlalchemy import Column, String, Boolean, DateTime, Integer, Date, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.db.session import Base


class User(Base):
    """Extended user information table."""
    __tablename__ = "users_extended"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String, nullable=True)  # male, female, non-binary, prefer-not-to-say
    # Encrypted recovery contact fields
    _recovery_email_encrypted = Column("recovery_email", String, nullable=True)
    _recovery_phone_encrypted = Column("recovery_phone", String, nullable=True)
    # Hash fields for lookup without decryption
    recovery_email_hash = Column(String(64), nullable=True, index=True)
    recovery_phone_hash = Column(String(64), nullable=True, index=True)
    is_suspended = Column(Boolean, default=False)
    last_login = Column(DateTime(timezone=True), nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Password hash (stored for authentication)
    password_hash = Column(Text, nullable=True)

    @property
    def recovery_email(self) -> str:
        """Get decrypted recovery email."""
        from app.services.encryption import encryption_service
        return encryption_service.decrypt_if_needed(self._recovery_email_encrypted) or ""

    @recovery_email.setter
    def recovery_email(self, value: str):
        """Set encrypted recovery email."""
        from app.services.encryption import encryption_service
        if value:
            self._recovery_email_encrypted = encryption_service.encrypt_if_needed(value)
            self.recovery_email_hash = encryption_service.hash_for_lookup(value)
        else:
            self._recovery_email_encrypted = None
            self.recovery_email_hash = None

    @property
    def recovery_phone(self) -> str:
        """Get decrypted recovery phone."""
        from app.services.encryption import encryption_service
        return encryption_service.decrypt_if_needed(self._recovery_phone_encrypted) or ""

    @recovery_phone.setter
    def recovery_phone(self, value: str):
        """Set encrypted recovery phone."""
        from app.services.encryption import encryption_service
        if value:
            self._recovery_phone_encrypted = encryption_service.encrypt_if_needed(value)
            self.recovery_phone_hash = encryption_service.hash_for_lookup(value)
        else:
            self._recovery_phone_encrypted = None
            self.recovery_phone_hash = None

    def __repr__(self):
        return f"<User {self.email}>"
