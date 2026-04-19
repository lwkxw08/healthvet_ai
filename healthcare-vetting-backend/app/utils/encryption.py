"""
Fernet symmetric encryption for sensitive data at rest (e.g. payment provider API keys).

Set ENCRYPTION_KEY env var in production (base64-url-safe 32-byte key).
Generate one with:  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

If ENCRYPTION_KEY is not set, a random key is generated at startup with a warning.
This means encrypted values will NOT survive server restarts in dev mode.
"""
import logging
import os

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "")
if not _ENCRYPTION_KEY:
    import warnings
    _ENCRYPTION_KEY = Fernet.generate_key().decode()
    warnings.warn(
        "ENCRYPTION_KEY not set — using an auto-generated key. "
        "Encrypted data will NOT survive restarts. Set ENCRYPTION_KEY in production!",
        stacklevel=2,
    )

_fernet = Fernet(_ENCRYPTION_KEY.encode() if isinstance(_ENCRYPTION_KEY, str) else _ENCRYPTION_KEY)


def encrypt_value(plaintext: str) -> str:
    """Encrypt a plaintext string. Returns a base64-encoded ciphertext string."""
    if not plaintext:
        return ""
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a ciphertext string. Returns the original plaintext.
    If decryption fails (wrong key or plaintext stored), returns the value as-is
    to support migration from unencrypted data."""
    if not ciphertext:
        return ""
    try:
        return _fernet.decrypt(ciphertext.encode()).decode()
    except (InvalidToken, Exception):
        # Value was likely stored as plaintext before encryption was added
        logger.debug("Decryption failed — returning value as-is (likely pre-encryption plaintext)")
        return ciphertext
