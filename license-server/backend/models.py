"""Pydantic models for request/response validation."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


# ---------- auth ----------

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=80)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    user_id: str
    email: EmailStr
    full_name: Optional[str] = None
    created_at: datetime


# ---------- products ----------

class ProductResponse(BaseModel):
    id: str
    name: str
    description: str
    price: float
    mode: str             # "payment" | "subscription"
    interval: Optional[str] = None
    features: List[str]
    highlight: bool


# ---------- checkout ----------

class CheckoutRequest(BaseModel):
    product_id: str
    origin_url: str       # window.location.origin from the frontend


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


class CheckoutStatusResponse(BaseModel):
    session_id: str
    status: str           # "pending" | "paid" | "failed" | "expired"
    payment_status: str
    license_key: Optional[str] = None
    product_id: Optional[str] = None


# ---------- licenses ----------

class LicenseResponse(BaseModel):
    license_id: str
    license_key: str
    product_id: str
    product_name: str
    status: str           # "active" | "revoked" | "expired"
    bound_ip: Optional[str] = None
    bound_ips: List[str] = []
    max_ips: int = 1
    expires_at: Optional[datetime] = None
    created_at: datetime
    ip_changes_remaining: int


class ChangeIpRequest(BaseModel):
    license_id: str
    new_ip: str = Field(min_length=7, max_length=45)


# ---------- license validation (called by buyer's StreamVault install) ----------

class ValidateRequest(BaseModel):
    license_key: str
    server_ip: str = Field(min_length=7, max_length=45)


class ValidateResponse(BaseModel):
    valid: bool
    status: str           # "active" | "revoked" | "expired" | "ip_mismatch" | "not_found"
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    expires_at: Optional[datetime] = None
    message: str
