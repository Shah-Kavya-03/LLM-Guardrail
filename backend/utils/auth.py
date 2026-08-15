"""
JWT token creation/verification and password hashing helpers.

Used by routers/auth.py, and importable by any future router that
needs to identify the logged-in user (e.g. admin.py checking who's
making a request).
"""

import os
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    """
    Create a signed JWT. `data` typically contains at least
    {"sub": user_id} — "sub" (subject) is the standard JWT claim for
    "who this token is about".
    """
    secret_key = os.getenv("SECRET_KEY")
    algorithm = os.getenv("ALGORITHM", "HS256")
    expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

    if not secret_key or secret_key == "your_secret_key_here":
        raise RuntimeError(
            "SECRET_KEY is not set (or still the placeholder) in .env. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )

    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, secret_key, algorithm=algorithm)


def decode_access_token(token: str) -> dict | None:
    """Returns the token's payload dict if valid, or None if invalid/expired."""
    secret_key = os.getenv("SECRET_KEY")
    algorithm = os.getenv("ALGORITHM", "HS256")

    try:
        return jwt.decode(token, secret_key, algorithms=[algorithm])
    except JWTError:
        return None
