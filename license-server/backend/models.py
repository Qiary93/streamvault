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
    referral_code: Optional[str] = Field(default=None, max_length=40)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    user_id: str
    email: EmailStr
    full_name: Optional[str] = None
    is_admin: bool = False
    created_at: datetime


# ---------- products ----------

class ProductResponse(BaseModel):
    id: str
    tier: str
    name: str
    description: str
    price: float
    mode: str
    interval: Optional[str] = None
    features: List[str]
    highlight: bool


# ---------- checkout ----------

class CheckoutRequest(BaseModel):
    product_id: str
    origin_url: str
    coupon_code: Optional[str] = Field(default=None, max_length=40)
    referral_code: Optional[str] = Field(default=None, max_length=40)


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str
    discount_applied: float = 0.0
    final_amount: float


class CheckoutStatusResponse(BaseModel):
    session_id: str
    status: str
    payment_status: str
    license_key: Optional[str] = None
    product_id: Optional[str] = None


# ---------- licenses ----------

class LicenseResponse(BaseModel):
    license_id: str
    license_key: str
    product_id: str
    product_name: str
    status: str
    bound_ip: Optional[str] = None
    bound_ips: List[str] = []
    max_ips: int = 1
    expires_at: Optional[datetime] = None
    created_at: datetime
    ip_changes_remaining: int


class ChangeIpRequest(BaseModel):
    license_id: str
    new_ip: str = Field(min_length=7, max_length=45)


# ---------- license validation ----------

class ValidateRequest(BaseModel):
    license_key: str
    server_ip: str = Field(min_length=7, max_length=45)


class ValidateResponse(BaseModel):
    valid: bool
    status: str
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    expires_at: Optional[datetime] = None
    message: str


# ---------- coupons ----------

class CouponCreateRequest(BaseModel):
    code: str = Field(min_length=3, max_length=40)
    description: Optional[str] = Field(default=None, max_length=140)
    discount_type: str = Field(default="percentage")   # "percentage" | "fixed"
    discount_value: float = Field(gt=0)                # percent (1-90) or dollars
    max_uses: int = Field(default=0, ge=0)             # 0 = unlimited
    expires_at: Optional[datetime] = None
    product_ids: List[str] = []                        # empty = all
    active: bool = True


class CouponUpdateRequest(BaseModel):
    description: Optional[str] = None
    discount_value: Optional[float] = None
    max_uses: Optional[int] = None
    expires_at: Optional[datetime] = None
    product_ids: Optional[List[str]] = None
    active: Optional[bool] = None


class CouponResponse(BaseModel):
    code: str
    description: Optional[str] = None
    discount_type: str
    discount_value: float
    max_uses: int
    used_count: int
    expires_at: Optional[datetime] = None
    product_ids: List[str] = []
    active: bool
    created_at: datetime


class CouponValidateRequest(BaseModel):
    code: str
    product_id: str


class CouponValidateResponse(BaseModel):
    valid: bool
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    final_price: Optional[float] = None
    message: str


# ---------- affiliates ----------

class AffiliateResponse(BaseModel):
    user_id: str
    code: str
    commission_percent: float
    total_sales: int
    total_revenue: float
    total_commission: float
    paid_out: float
    balance_owed: float
    created_at: datetime


class AffiliateSignupRequest(BaseModel):
    code: str = Field(min_length=3, max_length=40, pattern=r"^[a-zA-Z0-9_-]+$")


class AffiliateSaleResponse(BaseModel):
    sale_id: str
    buyer_email: str
    product_id: str
    amount: float
    commission: float
    paid: bool
    created_at: datetime


# ---------- admin ----------

class AdminUserResponse(BaseModel):
    user_id: str
    email: EmailStr
    full_name: Optional[str] = None
    is_admin: bool
    license_count: int
    total_spent: float
    created_at: datetime


class AdminLicenseListItem(BaseModel):
    license_id: str
    license_key: str
    user_email: str
    product_id: str
    product_name: str
    status: str
    bound_ips: List[str]
    expires_at: Optional[datetime] = None
    created_at: datetime


class AdminRevokeRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=400)


class AdminRefundRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=400)
    revoke_license: bool = True


class AdminManualLicenseRequest(BaseModel):
    user_email: EmailStr
    product_id: str
    expires_at: Optional[datetime] = None
    note: Optional[str] = Field(default=None, max_length=400)


class AdminStatsResponse(BaseModel):
    total_users: int
    total_licenses_issued: int
    active_licenses: int
    expired_licenses: int
    revoked_licenses: int
    total_revenue: float
    revenue_last_30d: float
    mrr: float                 # monthly recurring revenue
    arr: float                 # annual recurring revenue
    active_subscriptions: int
    total_affiliates: int
    total_coupons: int
    unpaid_affiliate_commission: float
