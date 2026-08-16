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


# ---- FastAPI dependency for protecting routes ----
# Usage: add `user_id: str = Depends(get_current_user_id)` to any
# route's parameters. FastAPI will run this first, return 401 if the
# token is missing/invalid, and hand the route the caller's user_id
# if it's valid.

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header. Expected: Bearer <token>",
        )

    payload = decode_access_token(credentials.credentials)
    if payload is None or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )

    return payload["sub"]


async def get_current_admin_user_id(
    user_id: str = Depends(get_current_user_id),
) -> str:
    """
    Same as get_current_user_id, but additionally requires the user's
    `is_admin` flag to be true. Import lives inside the function to
    avoid a circular import (database.connection doesn't need to be
    imported at module load time for the rest of this file to work).
    """
    from bson import ObjectId
    from database.connection import get_db

    db = get_db()

    try:
        object_id = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid user in token.")

    user_doc = await db.users.find_one({"_id": object_id})
    if user_doc is None:
        raise HTTPException(status_code=401, detail="User not found.")

    if not user_doc.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Admin access required.")

    return user_id
