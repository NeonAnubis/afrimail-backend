"""
Email sending service for OTP and notifications.
Uses SMTP to send emails.
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via SMTP."""

    @property
    def is_configured(self) -> bool:
        """Check if email service is properly configured."""
        return bool(
            settings.SMTP_HOST and
            settings.SMTP_USER and
            settings.SMTP_PASSWORD and
            settings.SMTP_FROM_EMAIL
        )

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None
    ) -> bool:
        """
        Send an email.

        Args:
            to_email: Recipient email address
            subject: Email subject
            body_text: Plain text body
            body_html: Optional HTML body

        Returns:
            True if email was sent successfully, False otherwise
        """
        if not self.is_configured:
            logger.warning("Email service not configured, skipping send")
            return False

        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
            message["To"] = to_email

            # Add plain text part
            part1 = MIMEText(body_text, "plain")
            message.attach(part1)

            # Add HTML part if provided
            if body_html:
                part2 = MIMEText(body_html, "html")
                message.attach(part2)

            # Create SSL context
            context = ssl.create_default_context()

            # Send email
            if settings.SMTP_USE_TLS:
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                    server.ehlo()
                    server.starttls(context=context)
                    server.ehlo()
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    server.sendmail(
                        settings.SMTP_FROM_EMAIL,
                        to_email,
                        message.as_string()
                    )
            else:
                with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=context) as server:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    server.sendmail(
                        settings.SMTP_FROM_EMAIL,
                        to_email,
                        message.as_string()
                    )

            logger.info(f"Email sent successfully to {to_email}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error sending email to {to_email}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email to {to_email}: {e}")
            return False

    async def send_otp_email(self, to_email: str, otp_code: str, user_name: str = "") -> bool:
        """
        Send OTP verification email for password reset.

        Args:
            to_email: Recipient email address
            otp_code: The 6-digit OTP code
            user_name: Optional user name for personalization

        Returns:
            True if email was sent successfully
        """
        greeting = f"Hi {user_name}," if user_name else "Hi,"

        subject = "Your Afrimail Password Reset Code"

        body_text = f"""
{greeting}

You requested to reset your Afrimail password.

Your verification code is: {otp_code}

This code will expire in 15 minutes.

If you didn't request this, please ignore this email or contact support if you have concerns.

Best regards,
The Afrimail Team
"""

        body_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
        <h1 style="color: white; margin: 0; font-size: 28px;">Afrimail</h1>
        <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0;">Password Reset</p>
    </div>

    <div style="background: #ffffff; padding: 30px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 10px 10px;">
        <p style="margin-top: 0;">{greeting}</p>

        <p>You requested to reset your Afrimail password.</p>

        <div style="background: #f5f5f5; border-radius: 8px; padding: 20px; text-align: center; margin: 25px 0;">
            <p style="margin: 0 0 10px 0; color: #666; font-size: 14px;">Your verification code is:</p>
            <div style="font-size: 36px; font-weight: bold; letter-spacing: 8px; color: #667eea;">
                {otp_code}
            </div>
        </div>

        <p style="color: #888; font-size: 14px;">
            <strong>This code will expire in 15 minutes.</strong>
        </p>

        <p style="color: #888; font-size: 14px;">
            If you didn't request this password reset, please ignore this email or contact support if you have concerns.
        </p>

        <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 25px 0;">

        <p style="color: #888; font-size: 12px; margin-bottom: 0;">
            Best regards,<br>
            The Afrimail Team
        </p>
    </div>

    <div style="text-align: center; padding: 20px; color: #888; font-size: 12px;">
        <p style="margin: 0;">
            This email was sent by Afrimail. Please do not reply to this email.
        </p>
    </div>
</body>
</html>
"""

        return await self.send_email(to_email, subject, body_text, body_html)

    async def send_welcome_email(self, to_email: str, user_name: str) -> bool:
        """
        Send welcome email to new users.

        Args:
            to_email: Recipient email address
            user_name: User's name

        Returns:
            True if email was sent successfully
        """
        subject = "Welcome to Afrimail!"

        body_text = f"""
Hi {user_name},

Welcome to Afrimail - Africa's Continental Email Platform!

Your email account has been successfully created. You can now:

- Send and receive emails
- Access your mailbox from any device
- Enjoy secure, reliable email service

If you have any questions, our support team is here to help.

Best regards,
The Afrimail Team
"""

        body_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
        <h1 style="color: white; margin: 0; font-size: 28px;">Welcome to Afrimail!</h1>
        <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0;">Africa's Continental Email Platform</p>
    </div>

    <div style="background: #ffffff; padding: 30px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 10px 10px;">
        <p style="margin-top: 0;">Hi {user_name},</p>

        <p>Your email account has been successfully created. You can now:</p>

        <ul style="padding-left: 20px;">
            <li>Send and receive emails</li>
            <li>Access your mailbox from any device</li>
            <li>Enjoy secure, reliable email service</li>
        </ul>

        <p>If you have any questions, our support team is here to help.</p>

        <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 25px 0;">

        <p style="color: #888; font-size: 12px; margin-bottom: 0;">
            Best regards,<br>
            The Afrimail Team
        </p>
    </div>
</body>
</html>
"""

        return await self.send_email(to_email, subject, body_text, body_html)


# Global service instance
email_service = EmailService()
