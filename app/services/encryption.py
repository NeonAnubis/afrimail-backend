"""
Encryption service for sensitive data like recovery email and phone.
Uses Fernet symmetric encryption.
"""

from cryptography.fernet import Fernet, InvalidToken
from typing import Optional
import base64
import hashlib

from app.core.config import settings


class EncryptionService:
    """Service for encrypting/decrypting sensitive user data."""

    def __init__(self):
        self._fernet: Optional[Fernet] = None

    @property
    def is_configured(self) -> bool:
        """Check if encryption is properly configured."""
        return bool(settings.ENCRYPTION_KEY)

    def _get_fernet(self) -> Fernet:
        """Get or create Fernet instance."""
        if self._fernet is None:
            if not self.is_configured:
                raise ValueError("ENCRYPTION_KEY is not configured")
            self._fernet = Fernet(settings.ENCRYPTION_KEY.encode())
        return self._fernet

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a string and return base64-encoded ciphertext.
        Returns empty string if plaintext is empty.
        """
        if not plaintext:
            return ""

        if not self.is_configured:
            # If encryption is not configured, return plaintext
            # (for backward compatibility during migration)
            return plaintext

        try:
            fernet = self._get_fernet()
            encrypted = fernet.encrypt(plaintext.encode())
            return encrypted.decode()
        except Exception as e:
            print(f"Encryption error: {e}")
            return plaintext

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt a base64-encoded ciphertext and return plaintext.
        Returns empty string if ciphertext is empty.
        """
        if not ciphertext:
            return ""

        if not self.is_configured:
            # If encryption is not configured, return as-is
            return ciphertext

        try:
            fernet = self._get_fernet()
            decrypted = fernet.decrypt(ciphertext.encode())
            return decrypted.decode()
        except InvalidToken:
            # Data might be unencrypted (from before encryption was enabled)
            # Return as-is for backward compatibility
            return ciphertext
        except Exception as e:
            print(f"Decryption error: {e}")
            return ciphertext

    def encrypt_if_needed(self, value: Optional[str]) -> Optional[str]:
        """Encrypt value only if it's not empty."""
        if not value:
            return value
        return self.encrypt(value)

    def decrypt_if_needed(self, value: Optional[str]) -> Optional[str]:
        """Decrypt value only if it's not empty."""
        if not value:
            return value
        return self.decrypt(value)

    def is_encrypted(self, value: str) -> bool:
        """
        Check if a value appears to be encrypted (Fernet format).
        Fernet tokens start with 'gAAAAA'.
        """
        if not value:
            return False
        return value.startswith('gAAAAA')

    def hash_for_lookup(self, plaintext: str) -> str:
        """
        Create a deterministic hash of plaintext for lookup purposes.
        This allows searching for encrypted values without decrypting all records.
        """
        if not plaintext:
            return ""
        # Use SHA-256 for deterministic hashing
        return hashlib.sha256(plaintext.lower().encode()).hexdigest()


# Global service instance
encryption_service = EncryptionService()
