import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _fernet() -> Fernet:
    source = settings.token_encryption_key or settings.jwt_secret
    key = base64.urlsafe_b64encode(hashlib.sha256(source.encode()).digest())
    return Fernet(key)


def encrypt_token(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_token(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        # Existing development connections were stored as OAuth JSON before encryption.
        if value.lstrip().startswith("{"):
            return value
        raise