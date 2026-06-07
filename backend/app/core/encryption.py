from cryptography.fernet import Fernet

from app.config import settings


def _get_fernet() -> Fernet:
    if not settings.token_encryption_key:
        raise ValueError("TOKEN_ENCRYPTION_KEY is not configured")
    return Fernet(settings.token_encryption_key.encode())


def encrypt_value(value: str) -> str:
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt_value(value: str) -> str:
    return _get_fernet().decrypt(value.encode()).decode()
