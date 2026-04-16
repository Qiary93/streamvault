from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends, WebSocket, WebSocketDisconnect
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt
import secrets
import asyncio
from bson import ObjectId
import json
import httpx

# Stripe integration
from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, CheckoutSessionResponse, CheckoutStatusResponse, CheckoutSessionRequest
)

ROOT_DIR = Path(__file__).parent

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Configuration
JWT_ALGORITHM = "HS256"

def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]

# Create the main app
app = FastAPI(title="StreamVault API")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============= MODELS =============

class UserBase(BaseModel):
    email: EmailStr
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    display_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str
    email: str
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    role: str = "user"
    follower_count: int = 0
    following_count: int = 0
    is_streaming: bool = False
    stream_key: Optional[str] = None
    created_at: datetime

class StreamCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category_id: str
    thumbnail_url: Optional[str] = None

class StreamUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[str] = None
    thumbnail_url: Optional[str] = None
    is_live: Optional[bool] = None

class StreamResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    stream_id: str
    user_id: str
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    title: str
    description: Optional[str] = None
    category_id: str
    category_name: Optional[str] = None
    thumbnail_url: Optional[str] = None
    viewer_count: int = 0
    is_live: bool = False
    started_at: Optional[datetime] = None
    created_at: datetime

class CategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None
    image_url: Optional[str] = None

class CategoryResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    category_id: str
    name: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    viewer_count: int = 0
    stream_count: int = 0

class ChatMessage(BaseModel):
    stream_id: str
    content: str

class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message_id: str
    stream_id: str
    user_id: str
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    content: str
    created_at: datetime

class DonationCreate(BaseModel):
    streamer_id: str
    amount: float
    message: Optional[str] = None
    origin_url: str

class DonationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    donation_id: str
    donor_id: str
    donor_username: str
    streamer_id: str
    streamer_username: str
    amount: float
    message: Optional[str] = None
    status: str
    created_at: datetime

class FollowResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    follow_id: str
    follower_id: str
    following_id: str
    created_at: datetime

# ============= PASSWORD HELPERS =============

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

# ============= JWT HELPERS =============

def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        "type": "access"
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "refresh"
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

# ============= AUTH DEPENDENCY =============

async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user.pop("password_hash", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_optional_user(request: Request) -> Optional[dict]:
    try:
        return await get_current_user(request)
    except HTTPException:
        return None

# ============= AUTH ROUTES =============

@api_router.post("/auth/register")
async def register(user_data: UserCreate, request: Request):
    email = user_data.email.lower()
    username = user_data.username.lower()
    
    existing = await db.users.find_one({"$or": [{"email": email}, {"username": username}]})
    if existing:
        if existing.get("email") == email:
            raise HTTPException(status_code=400, detail="Email already registered")
        raise HTTPException(status_code=400, detail="Username already taken")
    
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    stream_key = f"sk_{secrets.token_hex(16)}"
    
    user_doc = {
        "user_id": user_id,
        "email": email,
        "username": username,
        "display_name": user_data.display_name or username,
        "password_hash": hash_password(user_data.password),
        "avatar_url": None,
        "bio": None,
        "role": "user",
        "follower_count": 0,
        "following_count": 0,
        "is_streaming": False,
        "stream_key": stream_key,
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.users.insert_one(user_doc)
    
    access_token = create_access_token(user_id, email)
    refresh_token = create_refresh_token(user_id)
    
    from fastapi.responses import JSONResponse
    response = JSONResponse(content={
        "user_id": user_id,
        "email": email,
        "username": username,
        "display_name": user_doc["display_name"],
        "role": "user"
    })
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", max_age=900, path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=False, samesite="lax", max_age=604800, path="/")
    return response

@api_router.post("/auth/login")
async def login(credentials: UserLogin, request: Request):
    email = credentials.email.lower()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    access_token = create_access_token(user["user_id"], email)
    refresh_token = create_refresh_token(user["user_id"])
    
    from fastapi.responses import JSONResponse
    response = JSONResponse(content={
        "user_id": user["user_id"],
        "email": user["email"],
        "username": user["username"],
        "display_name": user.get("display_name"),
        "avatar_url": user.get("avatar_url"),
        "role": user.get("role", "user")
    })
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", max_age=900, path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=False, samesite="lax", max_age=604800, path="/")
    return response

@api_router.post("/auth/logout")
async def logout():
    from fastapi.responses import JSONResponse
    response = JSONResponse(content={"message": "Logged out successfully"})
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")
    return response

@api_router.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    return user

@api_router.post("/auth/refresh")
async def refresh_token(request: Request):
    refresh = request.cookies.get("refresh_token")
    if not refresh:
        raise HTTPException(status_code=401, detail="No refresh token")
    
    try:
        payload = jwt.decode(refresh, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        access_token = create_access_token(user["user_id"], user["email"])
        
        from fastapi.responses import JSONResponse
        response = JSONResponse(content={"message": "Token refreshed"})
        response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", max_age=900, path="/")
        return response
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ============= GOOGLE OAUTH =============

@api_router.post("/auth/google/session")
async def google_session(request: Request):
    body = await request.json()
    session_id = body.get("session_id")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": session_id}
        )
    
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    google_data = resp.json()
    email = google_data["email"].lower()
    
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {
                "avatar_url": google_data.get("picture"),
                "display_name": google_data.get("name", existing.get("display_name"))
            }}
        )
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        stream_key = f"sk_{secrets.token_hex(16)}"
        username = email.split("@")[0] + "_" + uuid.uuid4().hex[:4]
        
        user_doc = {
            "user_id": user_id,
            "email": email,
            "username": username,
            "display_name": google_data.get("name", username),
            "password_hash": None,
            "avatar_url": google_data.get("picture"),
            "bio": None,
            "role": "user",
            "follower_count": 0,
            "following_count": 0,
            "is_streaming": False,
            "stream_key": stream_key,
            "created_at": datetime.now(timezone.utc)
        }
        await db.users.insert_one(user_doc)
    
    # Store session
    session_token = google_data.get("session_token")
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        "created_at": datetime.now(timezone.utc)
    })
    
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    
    access_token = create_access_token(user_id, email)
    refresh_token = create_refresh_token(user_id)
    
    from fastapi.responses import JSONResponse
    response = JSONResponse(content=user)
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", max_age=900, path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=False, samesite="lax", max_age=604800, path="/")
    response.set_cookie(key="session_token", value=session_token, httponly=True, secure=True, samesite="none", max_age=604800, path="/")
    return response

# ============= USER ROUTES =============

@api_router.get("/users/{username}")
async def get_user_profile(username: str, request: Request):
    user = await db.users.find_one({"username": username.lower()}, {"_id": 0, "password_hash": 0, "stream_key": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    current_user = await get_optional_user(request)
    is_following = False
    if current_user:
        follow = await db.follows.find_one({
            "follower_id": current_user["user_id"],
            "following_id": user["user_id"]
        })
        is_following = follow is not None
    
    user["is_following"] = is_following
    return user

@api_router.put("/users/profile")
async def update_profile(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    updates = {}
    
    if "display_name" in body:
        updates["display_name"] = body["display_name"]
    if "bio" in body:
        updates["bio"] = body["bio"]
    if "avatar_url" in body:
        updates["avatar_url"] = body["avatar_url"]
    
    if updates:
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": updates})
    
    updated = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "password_hash": 0})
    return updated

# ============= FOLLOW ROUTES =============

@api_router.post("/users/{user_id}/follow")
async def follow_user(user_id: str, user: dict = Depends(get_current_user)):
    if user_id == user["user_id"]:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")
    
    target = await db.users.find_one({"user_id": user_id})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    existing = await db.follows.find_one({
        "follower_id": user["user_id"],
        "following_id": user_id
    })
    
    if existing:
        raise HTTPException(status_code=400, detail="Already following")
    
    follow_doc = {
        "follow_id": f"follow_{uuid.uuid4().hex[:12]}",
        "follower_id": user["user_id"],
        "following_id": user_id,
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.follows.insert_one(follow_doc)
    await db.users.update_one({"user_id": user["user_id"]}, {"$inc": {"following_count": 1}})
    await db.users.update_one({"user_id": user_id}, {"$inc": {"follower_count": 1}})
    
    return {"message": "Followed successfully"}

@api_router.delete("/users/{user_id}/follow")
async def unfollow_user(user_id: str, user: dict = Depends(get_current_user)):
    result = await db.follows.delete_one({
        "follower_id": user["user_id"],
        "following_id": user_id
    })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not following")
    
    await db.users.update_one({"user_id": user["user_id"]}, {"$inc": {"following_count": -1}})
    await db.users.update_one({"user_id": user_id}, {"$inc": {"follower_count": -1}})
    
    return {"message": "Unfollowed successfully"}

@api_router.get("/users/{user_id}/followers")
async def get_followers(user_id: str, limit: int = 20, offset: int = 0):
    follows = await db.follows.find(
        {"following_id": user_id}, {"_id": 0}
    ).skip(offset).limit(limit).to_list(limit)
    
    follower_ids = [f["follower_id"] for f in follows]
    users = await db.users.find(
        {"user_id": {"$in": follower_ids}},
        {"_id": 0, "password_hash": 0, "stream_key": 0}
    ).to_list(len(follower_ids))
    
    return users

@api_router.get("/users/{user_id}/following")
async def get_following(user_id: str, limit: int = 20, offset: int = 0):
    follows = await db.follows.find(
        {"follower_id": user_id}, {"_id": 0}
    ).skip(offset).limit(limit).to_list(limit)
    
    following_ids = [f["following_id"] for f in follows]
    users = await db.users.find(
        {"user_id": {"$in": following_ids}},
        {"_id": 0, "password_hash": 0, "stream_key": 0}
    ).to_list(len(following_ids))
    
    return users

# ============= CATEGORY ROUTES =============

@api_router.get("/categories")
async def get_categories():
    categories = await db.categories.find({}, {"_id": 0}).to_list(100)
    
    for cat in categories:
        count = await db.streams.count_documents({"category_id": cat["category_id"], "is_live": True})
        cat["stream_count"] = count
    
    return categories

@api_router.get("/categories/{category_id}")
async def get_category(category_id: str):
    category = await db.categories.find_one({"category_id": category_id}, {"_id": 0})
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    streams = await db.streams.find(
        {"category_id": category_id, "is_live": True}, {"_id": 0}
    ).sort("viewer_count", -1).to_list(50)
    
    for stream in streams:
        user = await db.users.find_one({"user_id": stream["user_id"]}, {"_id": 0, "username": 1, "display_name": 1, "avatar_url": 1})
        if user:
            stream["username"] = user["username"]
            stream["display_name"] = user.get("display_name")
            stream["avatar_url"] = user.get("avatar_url")
    
    category["streams"] = streams
    return category

# ============= STREAM ROUTES =============

@api_router.get("/streams")
async def get_streams(category_id: Optional[str] = None, limit: int = 20, offset: int = 0):
    query = {"is_live": True}
    if category_id:
        query["category_id"] = category_id
    
    streams = await db.streams.find(query, {"_id": 0}).sort("viewer_count", -1).skip(offset).limit(limit).to_list(limit)
    
    for stream in streams:
        user = await db.users.find_one({"user_id": stream["user_id"]}, {"_id": 0, "username": 1, "display_name": 1, "avatar_url": 1})
        if user:
            stream["username"] = user["username"]
            stream["display_name"] = user.get("display_name")
            stream["avatar_url"] = user.get("avatar_url")
        
        category = await db.categories.find_one({"category_id": stream.get("category_id")}, {"_id": 0, "name": 1})
        if category:
            stream["category_name"] = category["name"]
    
    return streams

@api_router.get("/streams/{stream_id}")
async def get_stream(stream_id: str, request: Request):
    stream = await db.streams.find_one({"stream_id": stream_id}, {"_id": 0})
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    
    user = await db.users.find_one({"user_id": stream["user_id"]}, {"_id": 0, "password_hash": 0, "stream_key": 0})
    if user:
        stream["username"] = user["username"]
        stream["display_name"] = user.get("display_name")
        stream["avatar_url"] = user.get("avatar_url")
        stream["streamer_bio"] = user.get("bio")
        stream["follower_count"] = user.get("follower_count", 0)
    
    category = await db.categories.find_one({"category_id": stream.get("category_id")}, {"_id": 0, "name": 1})
    if category:
        stream["category_name"] = category["name"]
    
    current_user = await get_optional_user(request)
    if current_user:
        follow = await db.follows.find_one({
            "follower_id": current_user["user_id"],
            "following_id": stream["user_id"]
        })
        stream["is_following"] = follow is not None
    else:
        stream["is_following"] = False
    
    return stream

@api_router.post("/streams")
async def create_stream(stream_data: StreamCreate, user: dict = Depends(get_current_user)):
    existing = await db.streams.find_one({"user_id": user["user_id"], "is_live": True})
    if existing:
        raise HTTPException(status_code=400, detail="Already have an active stream")
    
    category = await db.categories.find_one({"category_id": stream_data.category_id})
    if not category:
        raise HTTPException(status_code=400, detail="Invalid category")
    
    stream_id = f"stream_{uuid.uuid4().hex[:12]}"
    
    stream_doc = {
        "stream_id": stream_id,
        "user_id": user["user_id"],
        "title": stream_data.title,
        "description": stream_data.description,
        "category_id": stream_data.category_id,
        "thumbnail_url": stream_data.thumbnail_url,
        "viewer_count": 0,
        "is_live": True,
        "started_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.streams.insert_one(stream_doc)
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"is_streaming": True}})
    
    stream_doc.pop("_id", None)
    stream_doc["username"] = user["username"]
    stream_doc["display_name"] = user.get("display_name")
    stream_doc["avatar_url"] = user.get("avatar_url")
    stream_doc["category_name"] = category["name"]
    
    return stream_doc

@api_router.put("/streams/{stream_id}")
async def update_stream(stream_id: str, stream_data: StreamUpdate, user: dict = Depends(get_current_user)):
    stream = await db.streams.find_one({"stream_id": stream_id})
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    
    if stream["user_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    updates = {k: v for k, v in stream_data.model_dump().items() if v is not None}
    
    if updates:
        await db.streams.update_one({"stream_id": stream_id}, {"$set": updates})
        
        if "is_live" in updates and not updates["is_live"]:
            await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"is_streaming": False}})
    
    updated = await db.streams.find_one({"stream_id": stream_id}, {"_id": 0})
    return updated

@api_router.delete("/streams/{stream_id}")
async def end_stream(stream_id: str, user: dict = Depends(get_current_user)):
    stream = await db.streams.find_one({"stream_id": stream_id})
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    
    if stream["user_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    await db.streams.update_one({"stream_id": stream_id}, {"$set": {"is_live": False}})
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"is_streaming": False}})
    
    return {"message": "Stream ended"}

@api_router.get("/my/stream")
async def get_my_stream(user: dict = Depends(get_current_user)):
    stream = await db.streams.find_one({"user_id": user["user_id"], "is_live": True}, {"_id": 0})
    if not stream:
        return None
    return stream

# ============= CHAT ROUTES =============

@api_router.get("/streams/{stream_id}/chat")
async def get_chat_messages(stream_id: str, limit: int = 50):
    messages = await db.chat_messages.find(
        {"stream_id": stream_id}, {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    messages.reverse()
    return messages

@api_router.post("/streams/{stream_id}/chat")
async def send_chat_message(stream_id: str, message: ChatMessage, user: dict = Depends(get_current_user)):
    stream = await db.streams.find_one({"stream_id": stream_id})
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    
    message_doc = {
        "message_id": f"msg_{uuid.uuid4().hex[:12]}",
        "stream_id": stream_id,
        "user_id": user["user_id"],
        "username": user["username"],
        "display_name": user.get("display_name"),
        "avatar_url": user.get("avatar_url"),
        "content": message.content[:500],
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.chat_messages.insert_one(message_doc)
    message_doc.pop("_id", None)
    
    return message_doc

# ============= DONATION ROUTES =============

DONATION_AMOUNTS = {
    "small": 5.00,
    "medium": 10.00,
    "large": 25.00,
    "huge": 50.00,
    "mega": 100.00
}

@api_router.post("/donations/checkout")
async def create_donation_checkout(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    streamer_id = body.get("streamer_id")
    package_id = body.get("package_id")
    origin_url = body.get("origin_url")
    message = body.get("message", "")
    
    if package_id not in DONATION_AMOUNTS:
        raise HTTPException(status_code=400, detail="Invalid donation package")
    
    amount = DONATION_AMOUNTS[package_id]
    
    streamer = await db.users.find_one({"user_id": streamer_id})
    if not streamer:
        raise HTTPException(status_code=404, detail="Streamer not found")
    
    api_key = os.environ.get("STRIPE_API_KEY")
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    
    stripe_checkout = StripeCheckout(api_key=api_key, webhook_url=webhook_url)
    
    success_url = f"{origin_url}/donation/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin_url}/donation/cancel"
    
    donation_id = f"donation_{uuid.uuid4().hex[:12]}"
    
    checkout_request = CheckoutSessionRequest(
        amount=amount,
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "donation_id": donation_id,
            "donor_id": user["user_id"],
            "streamer_id": streamer_id,
            "message": message[:200]
        }
    )
    
    session = await stripe_checkout.create_checkout_session(checkout_request)
    
    await db.payment_transactions.insert_one({
        "transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
        "donation_id": donation_id,
        "session_id": session.session_id,
        "donor_id": user["user_id"],
        "donor_username": user["username"],
        "streamer_id": streamer_id,
        "streamer_username": streamer["username"],
        "amount": amount,
        "currency": "usd",
        "message": message[:200],
        "payment_status": "pending",
        "created_at": datetime.now(timezone.utc)
    })
    
    return {"url": session.url, "session_id": session.session_id}

@api_router.get("/donations/status/{session_id}")
async def get_donation_status(session_id: str, user: dict = Depends(get_current_user)):
    api_key = os.environ.get("STRIPE_API_KEY")
    stripe_checkout = StripeCheckout(api_key=api_key, webhook_url="")
    
    status = await stripe_checkout.get_checkout_status(session_id)
    
    if status.payment_status == "paid":
        txn = await db.payment_transactions.find_one({"session_id": session_id})
        if txn and txn.get("payment_status") != "completed":
            await db.payment_transactions.update_one(
                {"session_id": session_id},
                {"$set": {"payment_status": "completed"}}
            )
            
            await db.donations.insert_one({
                "donation_id": txn["donation_id"],
                "donor_id": txn["donor_id"],
                "donor_username": txn["donor_username"],
                "streamer_id": txn["streamer_id"],
                "streamer_username": txn["streamer_username"],
                "amount": txn["amount"],
                "message": txn.get("message"),
                "created_at": datetime.now(timezone.utc)
            })
    
    return {
        "status": status.status,
        "payment_status": status.payment_status,
        "amount": status.amount_total / 100
    }

@api_router.get("/donations/received")
async def get_received_donations(user: dict = Depends(get_current_user), limit: int = 20):
    donations = await db.donations.find(
        {"streamer_id": user["user_id"]}, {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    return donations

@api_router.get("/donations/sent")
async def get_sent_donations(user: dict = Depends(get_current_user), limit: int = 20):
    donations = await db.donations.find(
        {"donor_id": user["user_id"]}, {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    return donations

@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("Stripe-Signature")
    
    api_key = os.environ.get("STRIPE_API_KEY")
    stripe_checkout = StripeCheckout(api_key=api_key, webhook_url="")
    
    try:
        webhook_response = await stripe_checkout.handle_webhook(body, signature)
        
        if webhook_response.payment_status == "paid":
            await db.payment_transactions.update_one(
                {"session_id": webhook_response.session_id},
                {"$set": {"payment_status": "completed"}}
            )
        
        return {"received": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"received": True}

# ============= SEARCH =============

@api_router.get("/search")
async def search(q: str, type: str = "all", limit: int = 20):
    results = {"streams": [], "users": [], "categories": []}
    
    if type in ["all", "streams"]:
        # Find matching category IDs
        matching_cats = await db.categories.find(
            {"name": {"$regex": q, "$options": "i"}}, {"_id": 0, "category_id": 1}
        ).to_list(100)
        matching_cat_ids = [c["category_id"] for c in matching_cats]
        
        stream_query = {"is_live": True, "$or": [
            {"title": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
            {"category_id": {"$in": matching_cat_ids}} if matching_cat_ids else {"_never": True}
        ]}
        # Clean up impossible conditions
        stream_query["$or"] = [c for c in stream_query["$or"] if "_never" not in c]
        if not stream_query["$or"]:
            stream_query.pop("$or")
            stream_query["title"] = {"$regex": q, "$options": "i"}
        
        streams = await db.streams.find(stream_query, {"_id": 0}).limit(limit).to_list(limit)
        for stream in streams:
            user = await db.users.find_one({"user_id": stream["user_id"]}, {"_id": 0, "username": 1, "display_name": 1, "avatar_url": 1})
            if user:
                stream.update(user)
            category = await db.categories.find_one({"category_id": stream.get("category_id")}, {"_id": 0, "name": 1})
            if category:
                stream["category_name"] = category["name"]
        results["streams"] = streams
    
    if type in ["all", "users"]:
        users = await db.users.find(
            {"$or": [
                {"username": {"$regex": q, "$options": "i"}},
                {"display_name": {"$regex": q, "$options": "i"}}
            ]}, {"_id": 0, "password_hash": 0, "stream_key": 0}
        ).limit(limit).to_list(limit)
        results["users"] = users
    
    if type in ["all", "categories"]:
        categories = await db.categories.find(
            {"name": {"$regex": q, "$options": "i"}}, {"_id": 0}
        ).limit(limit).to_list(limit)
        results["categories"] = categories
    
    return results

# ============= FEATURED / DISCOVER =============

@api_router.get("/featured")
async def get_featured():
    top_streams = await db.streams.find(
        {"is_live": True}, {"_id": 0}
    ).sort("viewer_count", -1).limit(6).to_list(6)
    
    for stream in top_streams:
        user = await db.users.find_one({"user_id": stream["user_id"]}, {"_id": 0, "username": 1, "display_name": 1, "avatar_url": 1})
        if user:
            stream.update(user)
        category = await db.categories.find_one({"category_id": stream.get("category_id")}, {"_id": 0, "name": 1})
        if category:
            stream["category_name"] = category["name"]
    
    categories = await db.categories.find({}, {"_id": 0}).limit(8).to_list(8)
    
    recommended_users = await db.users.find(
        {"is_streaming": True}, {"_id": 0, "password_hash": 0, "stream_key": 0}
    ).sort("follower_count", -1).limit(10).to_list(10)
    
    return {
        "top_streams": top_streams,
        "categories": categories,
        "recommended_streamers": recommended_users
    }

# ============= SEED DATA =============

async def seed_data():
    # Seed admin
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@streamvault.com")
    admin_password = os.environ.get("ADMIN_PASSWORD", "Admin123!")
    
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        admin_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": admin_id,
            "email": admin_email,
            "username": "admin",
            "display_name": "Admin",
            "password_hash": hash_password(admin_password),
            "avatar_url": None,
            "bio": "Platform Administrator",
            "role": "admin",
            "follower_count": 0,
            "following_count": 0,
            "is_streaming": False,
            "stream_key": f"sk_{secrets.token_hex(16)}",
            "created_at": datetime.now(timezone.utc)
        })
        logger.info("Admin user created")
    
    # Seed categories
    categories = [
        {"category_id": "cat_gaming", "name": "Gaming", "description": "Live gaming streams", "image_url": "https://images.pexels.com/photos/9072304/pexels-photo-9072304.jpeg"},
        {"category_id": "cat_justchatting", "name": "Just Chatting", "description": "Casual conversations and hangouts", "image_url": "https://images.pexels.com/photos/1718758/pexels-photo-1718758.jpeg"},
        {"category_id": "cat_music", "name": "Music", "description": "Live music performances", "image_url": "https://images.pexels.com/photos/6301776/pexels-photo-6301776.jpeg"},
        {"category_id": "cat_esports", "name": "Esports", "description": "Competitive gaming tournaments", "image_url": "https://images.pexels.com/photos/14266493/pexels-photo-14266493.jpeg"},
        {"category_id": "cat_creative", "name": "Creative", "description": "Art, crafts, and creative content", "image_url": "https://images.pexels.com/photos/3094230/pexels-photo-3094230.jpeg"},
        {"category_id": "cat_irl", "name": "IRL", "description": "In real life streams", "image_url": "https://images.pexels.com/photos/2774556/pexels-photo-2774556.jpeg"},
        {"category_id": "cat_sports", "name": "Sports", "description": "Sports and fitness content", "image_url": "https://images.pexels.com/photos/3621104/pexels-photo-3621104.jpeg"},
        {"category_id": "cat_tech", "name": "Technology", "description": "Tech talks and coding", "image_url": "https://images.pexels.com/photos/546819/pexels-photo-546819.jpeg"}
    ]
    
    for cat in categories:
        existing = await db.categories.find_one({"category_id": cat["category_id"]})
        if not existing:
            cat["viewer_count"] = 0
            cat["stream_count"] = 0
            await db.categories.insert_one(cat)
    
    logger.info("Categories seeded")
    
    # Seed demo streamers
    demo_streamers = [
        {"username": "progamer", "display_name": "ProGamer_X", "avatar_url": "https://images.pexels.com/photos/9072304/pexels-photo-9072304.jpeg", "bio": "Professional gamer and streamer"},
        {"username": "musicqueen", "display_name": "MusicQueen", "avatar_url": "https://images.pexels.com/photos/30083578/pexels-photo-30083578.jpeg", "bio": "Singer and musician"},
        {"username": "chatmaster", "display_name": "ChatMaster", "avatar_url": "https://images.pexels.com/photos/2774556/pexels-photo-2774556.jpeg", "bio": "Your daily dose of fun conversations"}
    ]
    
    for streamer in demo_streamers:
        existing = await db.users.find_one({"username": streamer["username"]})
        if not existing:
            user_id = f"user_{uuid.uuid4().hex[:12]}"
            await db.users.insert_one({
                "user_id": user_id,
                "email": f"{streamer['username']}@demo.com",
                "username": streamer["username"],
                "display_name": streamer["display_name"],
                "password_hash": hash_password("Demo123!"),
                "avatar_url": streamer["avatar_url"],
                "bio": streamer["bio"],
                "role": "user",
                "follower_count": 1000 + hash(streamer["username"]) % 9000,
                "following_count": 50,
                "is_streaming": True,
                "stream_key": f"sk_{secrets.token_hex(16)}",
                "created_at": datetime.now(timezone.utc)
            })
            
            user = await db.users.find_one({"username": streamer["username"]})
            category = categories[hash(streamer["username"]) % len(categories)]
            
            stream_doc = {
                "stream_id": f"stream_{uuid.uuid4().hex[:12]}",
                "user_id": user["user_id"],
                "title": f"{streamer['display_name']}'s Live Stream",
                "description": f"Welcome to my stream! {streamer['bio']}",
                "category_id": category["category_id"],
                "thumbnail_url": "https://images.unsplash.com/photo-1757774636742-0a5dc7e5a07a",
                "viewer_count": 100 + hash(streamer["username"]) % 900,
                "is_live": True,
                "started_at": datetime.now(timezone.utc),
                "created_at": datetime.now(timezone.utc)
            }
            await db.streams.insert_one(stream_doc)
    
    logger.info("Demo data seeded")
    
    # Write test credentials
    os.makedirs("/app/memory", exist_ok=True)
    with open("/app/memory/test_credentials.md", "w") as f:
        f.write("# Test Credentials\n\n")
        f.write("## Admin Account\n")
        f.write(f"- Email: {admin_email}\n")
        f.write(f"- Password: {admin_password}\n")
        f.write("- Role: admin\n\n")
        f.write("## Demo Accounts\n")
        f.write("- Email: progamer@demo.com, Password: Demo123!\n")
        f.write("- Email: musicqueen@demo.com, Password: Demo123!\n")
        f.write("- Email: chatmaster@demo.com, Password: Demo123!\n\n")
        f.write("## Auth Endpoints\n")
        f.write("- POST /api/auth/register\n")
        f.write("- POST /api/auth/login\n")
        f.write("- POST /api/auth/logout\n")
        f.write("- GET /api/auth/me\n")
        f.write("- POST /api/auth/refresh\n")
        f.write("- POST /api/auth/google/session\n")
    
    # Create indexes
    await db.users.create_index("email", unique=True)
    await db.users.create_index("username", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.streams.create_index("stream_id", unique=True)
    await db.streams.create_index([("is_live", 1), ("viewer_count", -1)])
    await db.follows.create_index([("follower_id", 1), ("following_id", 1)], unique=True)
    await db.chat_messages.create_index([("stream_id", 1), ("created_at", -1)])
    await db.categories.create_index("category_id", unique=True)
    
    logger.info("Indexes created")

# Include the router
app.include_router(api_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[os.environ.get('FRONTEND_URL', '*')],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await seed_data()

@app.on_event("shutdown")
async def shutdown():
    client.close()
