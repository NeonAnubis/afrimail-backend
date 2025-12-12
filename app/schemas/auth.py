from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Literal, Union
from datetime import date


class LoginRequest(BaseModel):
    """Login request schema."""
    email: str
    password: str


class SignupRequest(BaseModel):
    """Signup request schema."""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: str  # Will be validated as username or full email
    password: str = Field(..., min_length=8)
    date_of_birth: Optional[date] = None
    gender: Optional[Literal["male", "female", "non-binary", "prefer-not-to-say"]] = None
    recovery_email: Optional[EmailStr] = None
    recovery_phone: Optional[str] = None
    hcaptcha_token: Optional[str] = None
    honeypot: Optional[str] = None  # Should be empty


class TokenResponse(BaseModel):
    """Token response schema."""
    success: bool
    token: str
    user: dict
    message: Optional[str] = None


class PasswordResetRequest(BaseModel):
    """Password reset request schema."""
    email: str
    method: Literal["email", "sms"] = "email"


class VerifyOTPRequest(BaseModel):
    """OTP verification request schema."""
    email: str
    otp_code: str


class ResetPasswordRequest(BaseModel):
    """Reset password with OTP schema."""
    email: str
    otp_code: str
    new_password: str = Field(..., min_length=8)


class ChangePasswordRequest(BaseModel):
    """Change password request schema."""
    email: str
    old_password: str
    new_password: str = Field(..., min_length=8)


class AdminLoginRequest(BaseModel):
    """Admin login request schema."""
    email: EmailStr
    password: str
