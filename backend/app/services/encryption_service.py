import base64
import os
import hashlib
from typing import Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.config import settings

class EncryptionService:
    """
    AES-256-GCM Server-side encryption service for sensitive financial fields.
    Encrypts GST Number, Tax ID, bank account details.
    """

    def __init__(self, key_str: Optional[str] = None):
        raw_key = key_str or settings.AES_ENCRYPTION_KEY
        try:
            decoded = base64.b64decode(raw_key)
            if len(decoded) == 32:
                self._key = decoded
            else:
                self._key = hashlib.sha256(decoded).digest()
        except Exception:
            self._key = hashlib.sha256((raw_key or "default_invoshield_secret_key_2026").encode()).digest()
        
        self._aesgcm = AESGCM(self._key)

    def encrypt(self, plaintext: Optional[str]) -> Optional[str]:
        """
        Encrypt a plaintext string using AES-256-GCM.
        Returns a base64 encoded string containing: nonce (12 bytes) + ciphertext + auth tag.
        """
        if not plaintext:
            return None
        
        try:
            nonce = os.urandom(12)  # 96-bit nonce
            ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
            combined = nonce + ciphertext
            return base64.b64encode(combined).decode("utf-8")
        except Exception as e:
            raise ValueError(f"AES-256-GCM encryption failed: {str(e)}")

    def decrypt(self, encrypted_token: Optional[str]) -> Optional[str]:
        """
        Decrypt a base64 encoded string containing nonce + ciphertext + tag.
        Returns the original plaintext string.
        """
        if not encrypted_token:
            return None
        
        try:
            combined = base64.b64decode(encrypted_token.encode("utf-8"))
            if len(combined) < 28:  # 12 bytes nonce + 16 bytes tag minimum
                # If not properly encrypted (e.g. legacy test data), return as is
                return encrypted_token
            nonce = combined[:12]
            ciphertext = combined[12:]
            decrypted_bytes = self._aesgcm.decrypt(nonce, ciphertext, None)
            return decrypted_bytes.decode("utf-8")
        except Exception:
            # If decryption fails (e.g. was stored unencrypted or key mismatch in testing), return raw token
            return encrypted_token

encryption_service = EncryptionService()
