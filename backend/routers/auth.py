"""
POST /auth/signup, POST /auth/login, POST /auth/logout.

Passwords are hashed with bcrypt before storage — plain text is never
written to MongoDB. Tokens are stateless JWTs, so "logout" doesn't
invalidate anything server-side (see the note on that endpoint).
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from database.connection import get_db
from database.models import new_user
from utils.auth import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["Auth"])


class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def _user_response(user_doc: dict, token: str) -> dict:
    return {
        "user_id": str(user_doc["_id"]),
        "name": user_doc["name"],
        "email": user_doc["email"],
        "token": token,
    }


@router.post("/signup")
async def signup(req: SignupRequest):
    db = get_db()

    existing = await db.users.find_one({"email": req.email})
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    user_doc = new_user(
        name=req.name,
        email=req.email,
        password_hashed=hash_password(req.password),
    )
    result = await db.users.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id

    token = create_access_token({"sub": str(user_doc["_id"])})
    return _user_response(user_doc, token)


@router.post("/login")
async def login(req: LoginRequest):
    db = get_db()

    user_doc = await db.users.find_one({"email": req.email})
    if not user_doc or not verify_password(req.password, user_doc["password_hashed"]):
        # Same error for "no such user" and "wrong password" —
        # revealing which one it was helps an attacker enumerate
        # valid emails.
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    token = create_access_token({"sub": str(user_doc["_id"])})
    return _user_response(user_doc, token)


@router.post("/logout")
async def logout():
    """
    JWTs are stateless — there's nothing stored server-side to
    invalidate. "Logout" here just confirms the request; the actual
    logout action is the frontend discarding its stored token. If you
    later need true server-side invalidation (e.g. for a compromised
    token), that requires a token blocklist collection in MongoDB —
    not built here since it adds a DB check to every authenticated
    request, and isn't needed unless you have a concrete case for it.
    """
    return {"message": "Logged out. Discard the token on the client."}
