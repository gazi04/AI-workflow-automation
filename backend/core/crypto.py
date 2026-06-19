"""Application-level encryption for OAuth tokens stored at rest.

Uses Fernet (AES-128-CBC + HMAC) with a key from settings so a DB dump does not
expose usable Google access/refresh tokens. Helpers are None-safe because the
token columns are nullable.
"""

from cryptography.fernet import Fernet

from core.config_loader import settings

_fernet = Fernet(settings.token_encryption_key.encode())


def encrypt_token(plain: str | None) -> str | None:
    if plain is None:
        return None
    return _fernet.encrypt(plain.encode()).decode()


def decrypt_token(cipher: str | None) -> str | None:
    if cipher is None:
        return None
    return _fernet.decrypt(cipher.encode()).decode()
