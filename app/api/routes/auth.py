from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
import secrets
import httpx

from app.db.session import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.config import settings
from app.models.user import User
from app.models.audit import LoginActivity
from app.models.signup import SignupAttempt, PasswordReset
from app.models.mailbox import MailboxMetadata
from app.schemas.auth import (
    LoginRequest, SignupRequest, TokenResponse,
    PasswordResetRequest, VerifyOTPRequest, ResetPasswordRequest
)
from app.schemas.user import UserResponse
from app.api.deps.auth import get_current_user
from app.services.mailcow import mailcow_service, MailcowError
from app.services.email import email_service

router = APIRouter()

HCAPTCHA_VERIFY_URL = "https://hcaptcha.com/siteverify"


async def verify_hcaptcha(token: str, client_ip: str) -> bool:
    """Verify hCaptcha token with hCaptcha API."""
    if not settings.HCAPTCHA_SECRET_KEY:
        # If no secret key configured, skip verification (development mode)
        return True

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                HCAPTCHA_VERIFY_URL,
                data={
                    "secret": settings.HCAPTCHA_SECRET_KEY,
                    "response": token,
                    "remoteip": client_ip
                }
            )
            result = response.json()
            return result.get("success", False)
    except Exception as e:
        print(f"hCaptcha verification error: {e}")
        return False


def get_client_ip(request: Request) -> str:
    """Get client IP address from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/signup", response_model=TokenResponse)
async def signup(
    request: Request,
    data: SignupRequest,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user account."""
    ip_address = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")

    # Check honeypot (should be empty)
    if data.honeypot:
        # Log as bot attempt
        attempt = SignupAttempt(
            ip_address=ip_address,
            email_attempted=data.email,
            honeypot_filled=True,
            success=False,
            failure_reason="Honeypot filled",
            user_agent=user_agent
        )
        db.add(attempt)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request"
        )

    # Verify hCaptcha token
    if settings.HCAPTCHA_SECRET_KEY:
        if not data.hcaptcha_token:
            attempt = SignupAttempt(
                ip_address=ip_address,
                email_attempted=data.email,
                success=False,
                failure_reason="Missing captcha token",
                user_agent=user_agent
            )
            db.add(attempt)
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please complete the captcha verification"
            )

        is_valid_captcha = await verify_hcaptcha(data.hcaptcha_token, ip_address)
        if not is_valid_captcha:
            attempt = SignupAttempt(
                ip_address=ip_address,
                email_attempted=data.email,
                success=False,
                failure_reason="Invalid captcha",
                user_agent=user_agent
            )
            db.add(attempt)
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Captcha verification failed. Please try again."
            )

    # Check rate limiting
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    one_day_ago = datetime.utcnow() - timedelta(days=1)

    hourly_count = await db.execute(
        select(func.count(SignupAttempt.id))
        .where(SignupAttempt.ip_address == ip_address)
        .where(SignupAttempt.created_at > one_hour_ago)
    )
    hourly_attempts = hourly_count.scalar() or 0

    daily_count = await db.execute(
        select(func.count(SignupAttempt.id))
        .where(SignupAttempt.ip_address == ip_address)
        .where(SignupAttempt.created_at > one_day_ago)
    )
    daily_attempts = daily_count.scalar() or 0

    if hourly_attempts >= settings.RATE_LIMIT_SIGNUPS_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many signup attempts. Please try again later."
        )

    if daily_attempts >= settings.RATE_LIMIT_SIGNUPS_PER_DAY:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily signup limit reached. Please try again tomorrow."
        )

    # Normalize email (add @afrimail.com if no domain)
    email = data.email.lower().strip()
    if "@" not in email:
        email = f"{email}@afrimail.com"

    # Check if user already exists
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        attempt = SignupAttempt(
            ip_address=ip_address,
            email_attempted=email,
            success=False,
            failure_reason="Email already exists",
            user_agent=user_agent
        )
        db.add(attempt)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists"
        )

    # Validate age (minimum 8 years)
    if data.date_of_birth:
        today = datetime.now().date()
        age = today.year - data.date_of_birth.year
        if (today.month, today.day) < (data.date_of_birth.month, data.date_of_birth.day):
            age -= 1
        if age < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You must be at least 8 years old to create an account"
            )

    # Create mailbox in Mailcow first
    local_part = email.split("@")[0]
    domain_part = email.split("@")[1]
    default_quota = 5368709120  # 5GB in bytes
    display_name = f"{data.first_name} {data.last_name}".strip()

    if mailcow_service.is_configured:
        try:
            await mailcow_service.create_mailbox(
                local_part=local_part,
                domain=domain_part,
                password=data.password,
                name=display_name,
                quota=default_quota,
                active=True
            )
        except MailcowError as e:
            # Log the error but don't expose internal details
            print(f"Mailcow mailbox creation failed for {email}: {e.message}")
            attempt = SignupAttempt(
                ip_address=ip_address,
                email_attempted=email,
                success=False,
                failure_reason=f"Mailcow error: {e.message}",
                user_agent=user_agent
            )
            db.add(attempt)
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create email account. Please try again later."
            )

    # Create user in local database
    user = User(
        email=email,
        first_name=data.first_name,
        last_name=data.last_name,
        date_of_birth=data.date_of_birth,
        gender=data.gender,
        recovery_email=str(data.recovery_email) if data.recovery_email else None,
        recovery_phone=data.recovery_phone,
        password_hash=get_password_hash(data.password),
        is_suspended=False,
        failed_login_attempts=0
    )
    db.add(user)

    # Create mailbox metadata with default quota (5GB)
    mailbox = MailboxMetadata(
        email=email,
        quota_bytes=default_quota,
        usage_bytes=0
    )
    db.add(mailbox)

    # Log successful signup
    attempt = SignupAttempt(
        ip_address=ip_address,
        email_attempted=email,
        success=True,
        user_agent=user_agent
    )
    db.add(attempt)

    await db.commit()
    await db.refresh(user)

    # Generate token
    token = create_access_token(data={"sub": user.email}, is_admin=False)

    return TokenResponse(
        success=True,
        token=token,
        user={
            "id": str(user.id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_suspended": user.is_suspended
        },
        message="Account created successfully"
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Authenticate a user."""
    ip_address = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")

    # Normalize email
    email = data.email.lower().strip()
    if "@" not in email:
        email = f"{email}@afrimail.com"

    # Get user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        # Log failed attempt
        activity = LoginActivity(
            user_email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            failure_reason="User not found"
        )
        db.add(activity)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Check if account is locked
    if user.locked_until and user.locked_until > datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is locked. Try again later."
        )

    # Check if suspended
    if user.is_suspended:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended. Please contact support."
        )

    # Verify password
    if not user.password_hash or not verify_password(data.password, user.password_hash):
        # Increment failed attempts
        user.failed_login_attempts += 1

        # Lock after 5 failed attempts
        if user.failed_login_attempts >= 5:
            user.locked_until = datetime.utcnow() + timedelta(minutes=15)

        activity = LoginActivity(
            user_email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            failure_reason="Invalid password"
        )
        db.add(activity)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Reset failed attempts and update last login
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.utcnow()

    # Log successful login
    activity = LoginActivity(
        user_email=email,
        ip_address=ip_address,
        user_agent=user_agent,
        success=True
    )
    db.add(activity)
    await db.commit()

    # Generate token
    token = create_access_token(data={"sub": user.email}, is_admin=False)

    return TokenResponse(
        success=True,
        token=token,
        user={
            "id": str(user.id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_suspended": user.is_suspended
        }
    )


@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user)
):
    """Get current authenticated user info."""
    return {
        "user": {
            "id": str(current_user.id),
            "email": current_user.email,
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "date_of_birth": str(current_user.date_of_birth) if current_user.date_of_birth else None,
            "gender": current_user.gender,
            "recovery_email": current_user.recovery_email,
            "recovery_phone": current_user.recovery_phone,
            "is_suspended": current_user.is_suspended,
            "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
            "updated_at": current_user.updated_at.isoformat() if current_user.updated_at else None
        },
        "isAdmin": False
    }


@router.get("/check-username/{username}")
async def check_username(
    username: str,
    db: AsyncSession = Depends(get_db)
):
    """Check if a username is available."""
    email = f"{username.lower().strip()}@afrimail.com"
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    return {
        "available": user is None,
        "email": email
    }


@router.post("/forgot-password")
async def forgot_password(
    data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db)
):
    """Request password reset OTP."""
    email = data.email.lower().strip()
    if "@" not in email:
        email = f"{email}@afrimail.com"

    # Get user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        # Don't reveal if user exists
        return {"success": True, "message": "If the account exists, a reset code has been sent."}

    # Generate OTP
    otp_code = "".join([str(secrets.randbelow(10)) for _ in range(6)])

    # Store OTP
    reset = PasswordReset(
        email=email,
        otp_code=otp_code,
        otp_type=data.method,
        expires_at=datetime.utcnow() + timedelta(minutes=15)
    )
    db.add(reset)
    await db.commit()

    # Send OTP based on method
    if data.method == "email":
        # Send to recovery email if available, otherwise to the main email
        target_email = user.recovery_email if user.recovery_email else email
        user_name = f"{user.first_name} {user.last_name}".strip()

        if email_service.is_configured:
            sent = await email_service.send_otp_email(target_email, otp_code, user_name)
            if not sent:
                print(f"Failed to send OTP email to {target_email}, OTP: {otp_code}")
        else:
            # Log for development when email is not configured
            print(f"[DEV] OTP for {email} (sent to {target_email}): {otp_code}")
    elif data.method == "sms":
        # SMS implementation would go here (e.g., Twilio)
        # For now, log the OTP
        print(f"[DEV] SMS OTP for {email}: {otp_code}")
    else:
        # Default: log the OTP
        print(f"[DEV] OTP for {email}: {otp_code}")

    return {"success": True, "message": "If the account exists, a reset code has been sent."}


@router.post("/verify-otp")
async def verify_otp(
    data: VerifyOTPRequest,
    db: AsyncSession = Depends(get_db)
):
    """Verify OTP code."""
    email = data.email.lower().strip()
    if "@" not in email:
        email = f"{email}@afrimail.com"

    # Find valid OTP
    result = await db.execute(
        select(PasswordReset)
        .where(PasswordReset.email == email)
        .where(PasswordReset.otp_code == data.otp_code)
        .where(PasswordReset.used == False)
        .where(PasswordReset.expires_at > datetime.utcnow())
        .order_by(PasswordReset.created_at.desc())
    )
    reset = result.scalar_one_or_none()

    if not reset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired code"
        )

    return {"success": True, "message": "Code verified successfully"}


@router.post("/reset-password")
async def reset_password(
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """Reset password using OTP."""
    email = data.email.lower().strip()
    if "@" not in email:
        email = f"{email}@afrimail.com"

    # Find valid OTP
    result = await db.execute(
        select(PasswordReset)
        .where(PasswordReset.email == email)
        .where(PasswordReset.otp_code == data.otp_code)
        .where(PasswordReset.used == False)
        .where(PasswordReset.expires_at > datetime.utcnow())
        .order_by(PasswordReset.created_at.desc())
    )
    reset = result.scalar_one_or_none()

    if not reset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired code"
        )

    # Get user
    user_result = await db.execute(select(User).where(User.email == email))
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Update password in Mailcow first
    if mailcow_service.is_configured:
        try:
            await mailcow_service.set_mailbox_password(email, data.new_password)
        except MailcowError as e:
            print(f"Failed to update password in Mailcow: {e.message}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update password. Please try again later."
            )

    # Update password in local database
    user.password_hash = get_password_hash(data.new_password)
    user.failed_login_attempts = 0
    user.locked_until = None

    # Mark OTP as used
    reset.used = True

    await db.commit()

    return {"success": True, "message": "Password reset successfully"}
