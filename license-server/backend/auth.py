"""JWT + bcrypt auth helpers. Used by routes/auth.py and as a Depends() guard."""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Cookie, Depends, HTTPException, status

from config import (
    ACCESS_TOKEN_TTL_MINUTES,
    JWT_ALGORITHM,
    JWT_SECRET,
    REFRESH_TOKEN_TTL_DAYS,
)
from db import db


# ---------- password hashing ----------

def hash_password(plaintext: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plaintext.encode("utf-8"), salt).decode("utf-8")


def verify_password(plaintext: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plaintext.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ---------- JWT ----------

def _create_token(payload: dict, ttl: timedelta, token_type: str) -> str:
    to_encode = {
        **payload,
        "exp": datetime.now(timezone.utc) + ttl,
        "type": token_type,
    }
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_access_token(user_id: str, email: str) -> str:
    return _create_token(
        {"sub": user_id, "email": email},
        timedelta(minutes=ACCESS_TOKEN_TTL_MINUTES),
        "access",
    )


def create_refresh_token(user_id: str) -> str:
    return _create_token(
        {"sub": user_id},
        timedelta(days=REFRESH_TOKEN_TTL_DAYS),
        "refresh",
    )


def decode_token(token: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("type") != expected_type:
        raise HTTPException(status_code=401, detail="Wrong token type")
    return payload


# ---------- FastAPI dependency ----------

async def get_current_user(access_token: Optional[str] = Cookie(default=None)) -> dict:
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(access_token, "access")
    user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def get_admin_user(access_token: Optional[str] = Cookie(default=None)) -> dict:
    """FastAPI dependency — like get_current_user, but rejects non-admins with 403."""
    user = await get_current_user(access_token)
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ---------- IDs ----------

def new_user_id() -> str:
    return f"usr_{uuid.uuid4().hex[:12]}"


def new_session_token() -> str:
    """For email-verification / password-reset tokens."""
    return secrets.token_urlsafe(32)
