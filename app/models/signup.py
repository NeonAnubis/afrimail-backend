from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.db.session import Base


class SignupAttempt(Base):
    """Rate limiting and spam tracking."""
    __tablename__ = "signup_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ip_address = Column(String, nullable=False, index=True)
    email_attempted = Column(String, nullable=False, index=True)
    hcaptcha_verified = Column(Boolean, default=False)
    honeypot_filled = Column(Boolean, default=False)
    success = Column(Boolean, default=False)
    failure_reason = Column(Text, nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self):
        return f"<SignupAttempt {self.email_attempted}>"


class PasswordReset(Base):
    """OTP codes for recovery."""
    __tablename__ = "password_resets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, nullable=False, index=True)
    otp_code = Column(String, nullable=False)
    otp_type = Column(String, nullable=False)  # email, sms
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<PasswordReset {self.email}>"
