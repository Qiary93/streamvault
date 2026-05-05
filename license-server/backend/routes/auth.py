"""Auth routes — register, login, logout, refresh, me."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException
from fastapi.responses import JSONResponse

from auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    new_user_id,
    verify_password,
)
from config import ACCESS_TOKEN_TTL_MINUTES, MIN_PASSWORD_LENGTH, REFRESH_TOKEN_TTL_DAYS
from db import db
from models import LoginRequest, RegisterRequest, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_auth_cookies(response: JSONResponse, access_token: str, refresh_token: str) -> None:
    secure = True
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=ACCESS_TOKEN_TTL_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=REFRESH_TOKEN_TTL_DAYS * 24 * 60 * 60,
        path="/",
    )


def _user_payload(user: dict) -> dict:
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "full_name": user.get("full_name"),
        "created_at": user["created_at"].isoformat() if isinstance(user["created_at"], datetime) else user["created_at"],
    }


@router.post("/register")
async def register(body: RegisterRequest):
    if len(body.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    existing = await db.users.find_one({"email": body.email.lower()})
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = {
        "user_id": new_user_id(),
        "email": body.email.lower(),
        "full_name": body.full_name,
        "password_hash": hash_password(body.password),
        "stripe_customer_id": None,
        "is_admin": False,
        "referred_by": (body.referral_code or "").strip().upper() or None,
        "created_at": datetime.now(timezone.utc),
    }
    await db.users.insert_one(user)

    access_token = create_access_token(user["user_id"], user["email"])
    refresh_token = create_refresh_token(user["user_id"])

    response = JSONResponse(content=_user_payload(user))
    _set_auth_cookies(response, access_token, refresh_token)
    return response


@router.post("/login")
async def login(body: LoginRequest):
    user = await db.users.find_one({"email": body.email.lower()})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = create_access_token(user["user_id"], user["email"])
    refresh_token = create_refresh_token(user["user_id"])

    response = JSONResponse(content=_user_payload(user))
    _set_auth_cookies(response, access_token, refresh_token)
    return response


@router.post("/logout")
async def logout():
    response = JSONResponse(content={"message": "Logged out"})
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return response


@router.post("/refresh")
async def refresh(refresh_token: str = Cookie(default=None)):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")
    payload = decode_token(refresh_token, "refresh")
    user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    new_access = create_access_token(user["user_id"], user["email"])
    response = JSONResponse(content={"message": "Refreshed"})
    response.set_cookie(
        key="access_token",
        value=new_access,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=ACCESS_TOKEN_TTL_MINUTES * 60,
        path="/",
    )
    return response


@router.get("/me", response_model=UserResponse)
async def me(user: dict = Depends(get_current_user)):
    return UserResponse(
        user_id=user["user_id"],
        email=user["email"],
        full_name=user.get("full_name"),
        is_admin=bool(user.get("is_admin")),
        created_at=user["created_at"],
    )
