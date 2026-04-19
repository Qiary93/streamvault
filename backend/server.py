from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import JSONResponse, Response
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

# LiveKit integration
from livekit.api import AccessToken, VideoGrants, LiveKitAPI
from livekit.protocol.ingress import CreateIngressRequest, IngressInput

# Stripe integration
from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, CheckoutSessionResponse, CheckoutStatusResponse, CheckoutSessionRequest
)
import stripe as stripe_sdk
stripe_sdk.api_key = os.environ.get("STRIPE_API_KEY", "")

ROOT_DIR = Path(__file__).parent

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Configuration
JWT_ALGORITHM = "HS256"

def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]

# LiveKit Configuration
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET", "")
LIVEKIT_URL = os.environ.get("LIVEKIT_URL", "")

# Create the main app
app = FastAPI(title="StreamVault API")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============= OBJECT STORAGE =============

STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
APP_NAME = "streamvault"
_storage_key = None

def init_storage():
    global _storage_key
    if _storage_key:
        return _storage_key
    import requests as req_lib
    resp = req_lib.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key

def put_object(path: str, data: bytes, content_type: str) -> dict:
    import requests as req_lib
    key = init_storage()
    resp = req_lib.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data, timeout=120
    )
    resp.raise_for_status()
    return resp.json()

def get_object(path: str):
    import requests as req_lib
    key = init_storage()
    resp = req_lib.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key}, timeout=60
    )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")

# ============= WEBSOCKET CHAT MANAGER =============

class ChatConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, stream_id: str):
        await websocket.accept()
        if stream_id not in self.active_connections:
            self.active_connections[stream_id] = []
        self.active_connections[stream_id].append(websocket)
        # Update viewer count
        await db.streams.update_one(
            {"stream_id": stream_id},
            {"$inc": {"viewer_count": 1}}
        )
    
    def disconnect(self, websocket: WebSocket, stream_id: str):
        if stream_id in self.active_connections:
            if websocket in self.active_connections[stream_id]:
                self.active_connections[stream_id].remove(websocket)
            if not self.active_connections[stream_id]:
                del self.active_connections[stream_id]
        asyncio.create_task(
            db.streams.update_one(
                {"stream_id": stream_id, "viewer_count": {"$gt": 0}},
                {"$inc": {"viewer_count": -1}}
            )
        )
    
    async def broadcast(self, stream_id: str, message: dict):
        if stream_id in self.active_connections:
            dead = []
            for conn in self.active_connections[stream_id]:
                try:
                    await conn.send_json(message)
                except Exception:
                    dead.append(conn)
            for d in dead:
                self.disconnect(d, stream_id)
    
    def get_viewer_count(self, stream_id: str) -> int:
        return len(self.active_connections.get(stream_id, []))

chat_manager = ChatConnectionManager()

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
    tags: Optional[List[str]] = None
    quality: Optional[str] = "720p"
    game_name: Optional[str] = None

class StreamUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[str] = None
    thumbnail_url: Optional[str] = None
    is_live: Optional[bool] = None
    tags: Optional[List[str]] = None
    quality: Optional[str] = None
    game_name: Optional[str] = None

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
    
    response = JSONResponse(content={
        "user_id": user_id,
        "email": email,
        "username": username,
        "display_name": user_doc["display_name"],
        "role": "user",
        "stream_key": stream_key
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
    
    response = JSONResponse(content={
        "user_id": user["user_id"],
        "email": user["email"],
        "username": user["username"],
        "display_name": user.get("display_name"),
        "avatar_url": user.get("avatar_url"),
        "role": user.get("role", "user"),
        "stream_key": user.get("stream_key")
    })
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", max_age=900, path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=False, samesite="lax", max_age=604800, path="/")
    return response

@api_router.post("/auth/logout")
async def logout():
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
    
    # Send notification
    await db.notifications.insert_one({
        "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "type": "follow",
        "message": f"{user.get('display_name') or user['username']} started following you!",
        "data": {"follower_id": user["user_id"], "follower_username": user["username"]},
        "read": False,
        "created_at": datetime.now(timezone.utc)
    })
    
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
async def get_categories(limit: Optional[int] = None, popular: bool = False):
    """Returns categories. When popular=true, sorts by (live_stream_count, popularity). limit trims results."""
    categories = await db.categories.find({}, {"_id": 0}).to_list(200)
    
    for cat in categories:
        count = await db.streams.count_documents({"category_id": cat["category_id"], "is_live": True, "broadcasting": True})
        cat["stream_count"] = count
    
    if popular:
        categories.sort(key=lambda c: (c.get("stream_count", 0), c.get("popularity", 0)), reverse=True)
    else:
        categories.sort(key=lambda c: c.get("popularity", 0), reverse=True)
    
    if limit and limit > 0:
        categories = categories[:limit]
    
    return categories

@api_router.get("/categories/{category_id}")
async def get_category(category_id: str):
    category = await db.categories.find_one({"category_id": category_id}, {"_id": 0})
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    streams = await db.streams.find(
        {"category_id": category_id, "is_live": True, "broadcasting": True}, {"_id": 0}
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
    query = {"is_live": True, "broadcasting": True}
    if category_id:
        query["category_id"] = category_id
    
    streams = await db.streams.find(query, {"_id": 0, "whip_token": 0}).sort("viewer_count", -1).skip(offset).limit(limit).to_list(limit)
    
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
    room_name = f"stream_{stream_id}"
    
    # Create LiveKit WHIP Ingress for OBS streaming
    whip_url = ""
    whip_token = ""
    ingress_id = ""
    
    if LIVEKIT_API_KEY and LIVEKIT_API_SECRET and LIVEKIT_URL:
        try:
            async with LiveKitAPI(
                url=LIVEKIT_URL,
                api_key=LIVEKIT_API_KEY,
                api_secret=LIVEKIT_API_SECRET
            ) as lkapi:
                ingress_req = CreateIngressRequest(
                    input_type=IngressInput.WHIP_INPUT,
                    name=f"stream_{stream_id}",
                    room_name=room_name,
                    participant_identity=user["user_id"],
                    participant_name=user.get("display_name") or user["username"],
                    enable_transcoding=False,
                )
                ingress_info = await lkapi.ingress.create_ingress(ingress_req)
                whip_url = ingress_info.url
                whip_token = ingress_info.stream_key
                ingress_id = ingress_info.ingress_id
                logger.info(f"Created WHIP ingress: {ingress_id} for stream {stream_id}")
        except Exception as e:
            logger.error(f"Failed to create WHIP ingress: {e}")
            # Fallback: generate manual token
            token = AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
            token = (
                token.with_identity(user["user_id"])
                .with_name(user.get("display_name") or user["username"])
                .with_grants(VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=True,
                    can_subscribe=True,
                ))
            )
            whip_token = token.to_jwt()
            whip_url = LIVEKIT_URL.replace("wss://", "https://") + "/rtc/whip"
    
    # Validate tags (max 5, sanitize)
    tags = []
    if stream_data.tags:
        tags = [t.strip()[:30] for t in stream_data.tags[:5] if t.strip()]
    
    quality = stream_data.quality or "720p"
    if quality not in ["360p", "480p", "720p", "1080p", "1440p", "4K"]:
        quality = "720p"
    
    stream_doc = {
        "stream_id": stream_id,
        "user_id": user["user_id"],
        "title": stream_data.title,
        "description": stream_data.description,
        "category_id": stream_data.category_id,
        "thumbnail_url": stream_data.thumbnail_url,
        "tags": tags,
        "quality": quality,
        "game_name": stream_data.game_name.strip()[:100] if stream_data.game_name else None,
        "viewer_count": 0,
        "is_live": True,
        "broadcasting": False,
        "room_name": room_name,
        "whip_url": whip_url,
        "whip_token": whip_token,
        "ingress_id": ingress_id,
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
    
    # Delete LiveKit ingress if exists
    ingress_id = stream.get("ingress_id")
    if ingress_id and LIVEKIT_API_KEY and LIVEKIT_API_SECRET and LIVEKIT_URL:
        try:
            from livekit.protocol.ingress import DeleteIngressRequest
            async with LiveKitAPI(
                url=LIVEKIT_URL,
                api_key=LIVEKIT_API_KEY,
                api_secret=LIVEKIT_API_SECRET
            ) as lkapi:
                await lkapi.ingress.delete_ingress(DeleteIngressRequest(ingress_id=ingress_id))
                logger.info(f"Deleted ingress {ingress_id}")
        except Exception as e:
            logger.error(f"Failed to delete ingress: {e}")
    
    await db.streams.update_one({"stream_id": stream_id}, {"$set": {"is_live": False, "broadcasting": False, "ended_at": datetime.now(timezone.utc)}})
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"is_streaming": False}})
    
    return {"message": "Stream ended"}

@api_router.get("/streams/{stream_id}/check-broadcast")
async def check_broadcast_status(stream_id: str):
    """Check if the streamer is actually broadcasting (connected via OBS)."""
    stream = await db.streams.find_one({"stream_id": stream_id}, {"_id": 0, "ingress_id": 1, "room_name": 1, "broadcasting": 1})
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    
    ingress_id = stream.get("ingress_id")
    is_broadcasting = stream.get("broadcasting", False)
    
    if not ingress_id or not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET or not LIVEKIT_URL:
        return {"broadcasting": is_broadcasting}
    
    try:
        from livekit.protocol.ingress import ListIngressRequest
        from livekit.protocol.room import ListParticipantsRequest
        
        now_broadcasting = False
        status = 0
        
        async with LiveKitAPI(
            url=LIVEKIT_URL,
            api_key=LIVEKIT_API_KEY,
            api_secret=LIVEKIT_API_SECRET
        ) as lkapi:
            # Method 1: Check ingress status
            try:
                result = await lkapi.ingress.list_ingress(ListIngressRequest(ingress_id=ingress_id))
                ingress_list = result.items if hasattr(result, 'items') else []
                
                if len(ingress_list) > 0:
                    ingress = ingress_list[0]
                    status = ingress.state.status if ingress.state else 0
                    if status >= 1:
                        now_broadcasting = True
            except Exception as ie:
                logger.warning(f"Ingress check failed: {ie}")
            
            # Method 2: Check room participants (fallback)
            if not now_broadcasting:
                room_name = stream.get("room_name", f"stream_{stream_id}")
                try:
                    participants = await lkapi.room.list_participants(ListParticipantsRequest(room=room_name))
                    p_list = participants.participants if hasattr(participants, 'participants') else []
                    # If any participant is publishing, they're broadcasting
                    for p in p_list:
                        if p.tracks and len(p.tracks) > 0:
                            now_broadcasting = True
                            status = 2
                            break
                except Exception as pe:
                    logger.debug(f"Room participants check: {pe}")
        
        logger.info(f"Broadcast check for {stream_id}: ingress_status={status}, broadcasting={now_broadcasting}")
        
        if now_broadcasting != is_broadcasting:
            await db.streams.update_one(
                {"stream_id": stream_id},
                {"$set": {"broadcasting": now_broadcasting}}
            )
            if now_broadcasting:
                logger.info(f"Stream {stream_id} is now broadcasting!")
        
        return {"broadcasting": now_broadcasting, "ingress_status": status}
    except Exception as e:
        logger.error(f"Check broadcast error: {e}")
    
    return {"broadcasting": is_broadcasting}

@api_router.get("/my/stream")
async def get_my_stream(user: dict = Depends(get_current_user)):
    stream = await db.streams.find_one({"user_id": user["user_id"], "is_live": True}, {"_id": 0})
    if not stream:
        return None
    
    # If WHIP credentials are missing, create ingress on-the-fly
    if (not stream.get("whip_url") or not stream.get("whip_token")) and LIVEKIT_API_KEY and LIVEKIT_API_SECRET and LIVEKIT_URL:
        try:
            room_name = stream.get("room_name") or f"stream_{stream['stream_id']}"
            async with LiveKitAPI(
                url=LIVEKIT_URL,
                api_key=LIVEKIT_API_KEY,
                api_secret=LIVEKIT_API_SECRET
            ) as lkapi:
                ingress_req = CreateIngressRequest(
                    input_type=IngressInput.WHIP_INPUT,
                    name=f"stream_{stream['stream_id']}",
                    room_name=room_name,
                    participant_identity=user["user_id"],
                    participant_name=user.get("display_name") or user["username"],
                    enable_transcoding=False,
                )
                ingress_info = await lkapi.ingress.create_ingress(ingress_req)
                stream["whip_url"] = ingress_info.url
                stream["whip_token"] = ingress_info.stream_key
                stream["ingress_id"] = ingress_info.ingress_id
                stream["room_name"] = room_name
                # Save for future requests
                await db.streams.update_one(
                    {"stream_id": stream["stream_id"]},
                    {"$set": {
                        "whip_url": ingress_info.url,
                        "whip_token": ingress_info.stream_key,
                        "ingress_id": ingress_info.ingress_id,
                        "room_name": room_name
                    }}
                )
                logger.info(f"Created WHIP ingress on-the-fly for stream {stream['stream_id']}")
        except Exception as e:
            logger.error(f"Failed to create ingress on-the-fly: {e}")
    
    return stream

# ============= CHAT ROUTES =============

@api_router.get("/streams/{stream_id}/chat")
async def get_chat_messages(stream_id: str, limit: int = 50):

    messages = await db.chat_messages.find(
        {"stream_id": stream_id}, {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    messages.reverse()
    return messages

@api_router.put("/streams/{stream_id}/set-broadcasting")
async def set_broadcasting(stream_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Manual toggle for broadcasting status - streamer can confirm they're live."""
    stream = await db.streams.find_one({"stream_id": stream_id})
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    if stream["user_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    body = await request.json()
    broadcasting = bool(body.get("broadcasting", False))
    
    await db.streams.update_one(
        {"stream_id": stream_id},
        {"$set": {"broadcasting": broadcasting}}
    )
    
    logger.info(f"Stream {stream_id} broadcasting manually set to {broadcasting}")
    return {"broadcasting": broadcasting}

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
    custom_amount = body.get("custom_amount")
    origin_url = body.get("origin_url")
    message = body.get("message", "")
    
    if package_id == "custom" and custom_amount:
        amount = round(float(custom_amount), 2)
        if amount < 1 or amount > 10000:
            raise HTTPException(status_code=400, detail="Custom amount must be between $1 and $10,000")
    elif package_id in DONATION_AMOUNTS:
        amount = DONATION_AMOUNTS[package_id]
    else:
        raise HTTPException(status_code=400, detail="Invalid donation package")
    
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
            
            # Notify streamer of donation
            await db.notifications.insert_one({
                "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
                "user_id": txn["streamer_id"],
                "type": "donation",
                "message": f"{txn['donor_username']} donated ${txn['amount']:.2f}!",
                "data": {"donor_id": txn["donor_id"], "amount": txn["amount"], "message": txn.get("message")},
                "read": False,
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
        
        stream_query = {"is_live": True, "broadcasting": True, "$or": [
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
        {"is_live": True, "broadcasting": True}, {"_id": 0, "whip_token": 0}
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
    
    # Attach active stream_id for live streamers
    for u in recommended_users:
        stream = await db.streams.find_one(
            {"user_id": u["user_id"], "is_live": True},
            {"_id": 0, "stream_id": 1, "broadcasting": 1}
        )
        if stream:
            u["active_stream_id"] = stream["stream_id"]
            u["broadcasting"] = stream.get("broadcasting", False)
    
    return {
        "top_streams": top_streams,
        "categories": categories,
        "recommended_streamers": recommended_users
    }

# ============= FILE UPLOADS (THUMBNAILS, AVATARS, COVERS) =============

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

async def upload_file(file: UploadFile, user_id: str, file_type: str):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, WebP, and GIF images are allowed")
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")
    ext = file.filename.split(".")[-1] if "." in file.filename else "png"
    path = f"{APP_NAME}/{file_type}/{user_id}/{uuid.uuid4().hex}.{ext}"
    result = put_object(path, data, file.content_type or "image/png")
    await db.files.insert_one({
        "file_id": f"file_{uuid.uuid4().hex[:12]}",
        "storage_path": result["path"],
        "original_filename": file.filename,
        "content_type": file.content_type,
        "size": result.get("size", len(data)),
        "user_id": user_id,
        "type": file_type,
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc)
    })
    return result["path"]

@api_router.post("/upload/thumbnail")
async def upload_thumbnail(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    try:
        path = await upload_file(file, user["user_id"], "thumbnails")
        return {"path": path, "url": f"/api/files/{path}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Thumbnail upload error: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload thumbnail")

@api_router.post("/upload/avatar")
async def upload_avatar(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    try:
        path = await upload_file(file, user["user_id"], "avatars")
        avatar_url = f"/api/files/{path}"
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"avatar_url": avatar_url}})
        return {"path": path, "url": avatar_url}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Avatar upload error: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload avatar")

@api_router.post("/upload/cover")
async def upload_cover(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    try:
        path = await upload_file(file, user["user_id"], "covers")
        cover_url = f"/api/files/{path}"
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"cover_url": cover_url}})
        return {"path": path, "url": cover_url}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cover upload error: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload cover")

@api_router.get("/files/{path:path}")
async def serve_file(path: str):
    record = await db.files.find_one({"storage_path": path, "is_deleted": False})
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        data, content_type = get_object(path)
        return Response(
            content=data,
            media_type=record.get("content_type", content_type),
            headers={"Cache-Control": "public, max-age=86400"}
        )
    except Exception as e:
        logger.error(f"File serve error: {e}")
        raise HTTPException(status_code=404, detail="File not found")

# ============= TAG & GAME DISCOVERY =============

@api_router.get("/streams/by-tag/{tag}")
async def get_streams_by_tag(tag: str, limit: int = 20):
    streams = await db.streams.find(
        {"is_live": True, "broadcasting": True, "tags": tag.lower()},
        {"_id": 0, "whip_token": 0}
    ).sort("viewer_count", -1).limit(limit).to_list(limit)
    
    for stream in streams:
        user = await db.users.find_one({"user_id": stream["user_id"]}, {"_id": 0, "username": 1, "display_name": 1, "avatar_url": 1})
        if user:
            stream.update(user)
        category = await db.categories.find_one({"category_id": stream.get("category_id")}, {"_id": 0, "name": 1})
        if category:
            stream["category_name"] = category["name"]
    
    return streams

@api_router.get("/streams/by-game/{game_name}")
async def get_streams_by_game(game_name: str, limit: int = 20):
    streams = await db.streams.find(
        {"is_live": True, "broadcasting": True, "game_name": {"$regex": f"^{game_name}$", "$options": "i"}},
        {"_id": 0, "whip_token": 0}
    ).sort("viewer_count", -1).limit(limit).to_list(limit)
    
    for stream in streams:
        user = await db.users.find_one({"user_id": stream["user_id"]}, {"_id": 0, "username": 1, "display_name": 1, "avatar_url": 1})
        if user:
            stream.update(user)
        category = await db.categories.find_one({"category_id": stream.get("category_id")}, {"_id": 0, "name": 1})
        if category:
            stream["category_name"] = category["name"]
    
    return streams

# ============= RECOMMENDED STREAMERS =============

@api_router.get("/recommended")
async def get_recommended(request: Request):
    """Returns streamers broadcasting LIVE via OBS (broadcasting=true) with current stream info."""
    current_user = await get_optional_user(request)
    
    # Find LIVE streams (broadcasting + is_live)
    stream_pipeline = [
        {"$match": {"is_live": True, "broadcasting": True}},
        {"$sort": {"viewer_count": -1}},
        {"$limit": 20},
    ]
    live_streams = await db.streams.aggregate(stream_pipeline).to_list(20)
    
    results = []
    for stream in live_streams:
        # exclude current user from recommendations
        if current_user and stream.get("user_id") == current_user.get("user_id"):
            continue
        streamer = await db.users.find_one({"user_id": stream["user_id"]}, {"_id": 0, "password_hash": 0, "stream_key": 0})
        if not streamer or streamer.get("role") == "admin":
            continue
        results.append({
            **streamer,
            "active_stream_id": stream.get("stream_id"),
            "viewer_count": stream.get("viewer_count", 0),
            "game_name": stream.get("game_name") or "",
            "stream_title": stream.get("title") or "",
            "is_streaming": True,
            "broadcasting": True,
        })
        if len(results) >= 10:
            break
    
    return results

# ============= EMOTES =============

PLATFORM_EMOTES = [
    {"code": ":vault:", "name": "Vault", "url": "https://api.iconify.design/twemoji:star-struck.svg"},
    {"code": ":fire:", "name": "Fire", "url": "https://api.iconify.design/twemoji:fire.svg"},
    {"code": ":heart:", "name": "Heart", "url": "https://api.iconify.design/twemoji:red-heart.svg"},
    {"code": ":gg:", "name": "GG", "url": "https://api.iconify.design/twemoji:trophy.svg"},
    {"code": ":pog:", "name": "Pog", "url": "https://api.iconify.design/twemoji:face-with-open-mouth.svg"},
    {"code": ":lol:", "name": "LOL", "url": "https://api.iconify.design/twemoji:face-with-tears-of-joy.svg"},
    {"code": ":cry:", "name": "Cry", "url": "https://api.iconify.design/twemoji:loudly-crying-face.svg"},
    {"code": ":rage:", "name": "Rage", "url": "https://api.iconify.design/twemoji:angry-face.svg"},
    {"code": ":cool:", "name": "Cool", "url": "https://api.iconify.design/twemoji:smiling-face-with-sunglasses.svg"},
    {"code": ":wave:", "name": "Wave", "url": "https://api.iconify.design/twemoji:waving-hand.svg"},
    {"code": ":clap:", "name": "Clap", "url": "https://api.iconify.design/twemoji:clapping-hands.svg"},
    {"code": ":hype:", "name": "Hype", "url": "https://api.iconify.design/twemoji:rocket.svg"},
    {"code": ":love:", "name": "Love", "url": "https://api.iconify.design/twemoji:smiling-face-with-heart-eyes.svg"},
    {"code": ":think:", "name": "Think", "url": "https://api.iconify.design/twemoji:thinking-face.svg"},
    {"code": ":skull:", "name": "Skull", "url": "https://api.iconify.design/twemoji:skull.svg"},
    {"code": ":crown:", "name": "Crown", "url": "https://api.iconify.design/twemoji:crown.svg"},
]

@api_router.get("/emotes")
async def get_emotes():
    return PLATFORM_EMOTES

# ============= STREAM QUALITY OPTIONS =============

QUALITY_OPTIONS = ["360p", "480p", "720p", "1080p", "1440p", "4K"]

@api_router.get("/quality-options")
async def get_quality_options():
    return QUALITY_OPTIONS

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
    
    # Seed categories — full Kick.com category list (~40)
    categories = [
        # Top tier
        {"category_id": "cat_just_chatting", "name": "Just Chatting", "description": "Casual conversations and hangouts", "image_url": "https://images.pexels.com/photos/1718758/pexels-photo-1718758.jpeg", "popularity": 100},
        {"category_id": "cat_slots_casino", "name": "Slots & Casino", "description": "Live casino and slots action", "image_url": "https://images.pexels.com/photos/1871508/pexels-photo-1871508.jpeg", "popularity": 95},
        {"category_id": "cat_gta_v", "name": "Grand Theft Auto V", "description": "GTA V gameplay and RP", "image_url": "https://images.pexels.com/photos/9072304/pexels-photo-9072304.jpeg", "popularity": 94},
        {"category_id": "cat_league_of_legends", "name": "League of Legends", "description": "LoL matches and coaching", "image_url": "https://images.pexels.com/photos/14266493/pexels-photo-14266493.jpeg", "popularity": 93},
        {"category_id": "cat_valorant", "name": "VALORANT", "description": "Valorant ranked and tournaments", "image_url": "https://images.pexels.com/photos/275033/pexels-photo-275033.jpeg", "popularity": 92},
        {"category_id": "cat_fortnite", "name": "Fortnite", "description": "Fortnite battle royale", "image_url": "https://images.pexels.com/photos/1293261/pexels-photo-1293261.jpeg", "popularity": 91},
        {"category_id": "cat_counter_strike", "name": "Counter-Strike 2", "description": "CS2 competitive gameplay", "image_url": "https://images.pexels.com/photos/442576/pexels-photo-442576.jpeg", "popularity": 90},
        {"category_id": "cat_minecraft", "name": "Minecraft", "description": "Minecraft survival and creative", "image_url": "https://images.pexels.com/photos/1294020/pexels-photo-1294020.jpeg", "popularity": 88},
        {"category_id": "cat_call_of_duty_warzone", "name": "Call of Duty: Warzone", "description": "Warzone battle royale", "image_url": "https://images.pexels.com/photos/163064/play-stone-network-networked-interactive-163064.jpeg", "popularity": 87},
        {"category_id": "cat_world_of_warcraft", "name": "World of Warcraft", "description": "WoW raids and PvP", "image_url": "https://images.pexels.com/photos/371924/pexels-photo-371924.jpeg", "popularity": 85},
        {"category_id": "cat_ea_fc", "name": "EA Sports FC 25", "description": "FC 25 Ultimate Team and Rivals", "image_url": "https://images.pexels.com/photos/47730/the-ball-stadion-football-the-pitch-47730.jpeg", "popularity": 84},
        {"category_id": "cat_dota2", "name": "Dota 2", "description": "Dota 2 matches and coaching", "image_url": "https://images.pexels.com/photos/596750/pexels-photo-596750.jpeg", "popularity": 82},
        # Mid tier
        {"category_id": "cat_music", "name": "Music", "description": "Live music performances", "image_url": "https://images.pexels.com/photos/6301776/pexels-photo-6301776.jpeg", "popularity": 80},
        {"category_id": "cat_irl", "name": "IRL", "description": "In real life streams", "image_url": "https://images.pexels.com/photos/2774556/pexels-photo-2774556.jpeg", "popularity": 78},
        {"category_id": "cat_sports", "name": "Sports", "description": "Sports and live events", "image_url": "https://images.pexels.com/photos/3621104/pexels-photo-3621104.jpeg", "popularity": 77},
        {"category_id": "cat_poker", "name": "Poker", "description": "Live poker and tournaments", "image_url": "https://images.pexels.com/photos/1871508/pexels-photo-1871508.jpeg", "popularity": 75},
        {"category_id": "cat_hot_tubs", "name": "Hot Tubs", "description": "Pools, hot tubs and beaches", "image_url": "https://images.pexels.com/photos/261403/pexels-photo-261403.jpeg", "popularity": 72},
        {"category_id": "cat_esports", "name": "Esports", "description": "Competitive gaming tournaments", "image_url": "https://images.pexels.com/photos/7915437/pexels-photo-7915437.jpeg", "popularity": 70},
        {"category_id": "cat_chess", "name": "Chess", "description": "Chess games and tournaments", "image_url": "https://images.pexels.com/photos/260024/pexels-photo-260024.jpeg", "popularity": 68},
        {"category_id": "cat_pools_camping", "name": "Travel & Outdoors", "description": "Travel, camping, and outdoors", "image_url": "https://images.pexels.com/photos/2422265/pexels-photo-2422265.jpeg", "popularity": 66},
        {"category_id": "cat_creative", "name": "Creative", "description": "Art, crafts, and creative content", "image_url": "https://images.pexels.com/photos/3094230/pexels-photo-3094230.jpeg", "popularity": 65},
        {"category_id": "cat_tech", "name": "Science & Technology", "description": "Tech talks, coding, and science", "image_url": "https://images.pexels.com/photos/546819/pexels-photo-546819.jpeg", "popularity": 64},
        {"category_id": "cat_food_drink", "name": "Food & Drink", "description": "Cooking and tasting streams", "image_url": "https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg", "popularity": 62},
        {"category_id": "cat_makers", "name": "Makers & Crafting", "description": "DIY, woodworking and handcrafts", "image_url": "https://images.pexels.com/photos/3965545/pexels-photo-3965545.jpeg", "popularity": 60},
        # Additional games / niches
        {"category_id": "cat_apex_legends", "name": "Apex Legends", "description": "Apex Legends ranked", "image_url": "https://images.pexels.com/photos/2007647/pexels-photo-2007647.jpeg", "popularity": 58},
        {"category_id": "cat_rocket_league", "name": "Rocket League", "description": "Rocket League ranked and tournaments", "image_url": "https://images.pexels.com/photos/1093646/pexels-photo-1093646.jpeg", "popularity": 55},
        {"category_id": "cat_rust", "name": "Rust", "description": "Rust survival gameplay", "image_url": "https://images.pexels.com/photos/2801278/pexels-photo-2801278.jpeg", "popularity": 54},
        {"category_id": "cat_overwatch_2", "name": "Overwatch 2", "description": "Overwatch 2 ranked and arcade", "image_url": "https://images.pexels.com/photos/442576/pexels-photo-442576.jpeg", "popularity": 52},
        {"category_id": "cat_elden_ring", "name": "Elden Ring", "description": "Elden Ring PvE and PvP", "image_url": "https://images.pexels.com/photos/371924/pexels-photo-371924.jpeg", "popularity": 50},
        {"category_id": "cat_pokemon", "name": "Pokémon", "description": "Pokémon games and cards", "image_url": "https://images.pexels.com/photos/163064/play-stone-network-networked-interactive-163064.jpeg", "popularity": 48},
        {"category_id": "cat_dark_and_darker", "name": "Dark and Darker", "description": "Dark and Darker dungeons", "image_url": "https://images.pexels.com/photos/4009402/pexels-photo-4009402.jpeg", "popularity": 46},
        {"category_id": "cat_marvel_rivals", "name": "Marvel Rivals", "description": "Marvel Rivals competitive", "image_url": "https://images.pexels.com/photos/9072304/pexels-photo-9072304.jpeg", "popularity": 44},
        {"category_id": "cat_pubg", "name": "PUBG: Battlegrounds", "description": "PUBG battle royale", "image_url": "https://images.pexels.com/photos/1293261/pexels-photo-1293261.jpeg", "popularity": 42},
        {"category_id": "cat_tarkov", "name": "Escape From Tarkov", "description": "Tarkov raids", "image_url": "https://images.pexels.com/photos/1796795/pexels-photo-1796795.jpeg", "popularity": 40},
        {"category_id": "cat_path_of_exile", "name": "Path of Exile", "description": "PoE ARPG gameplay", "image_url": "https://images.pexels.com/photos/371924/pexels-photo-371924.jpeg", "popularity": 38},
        {"category_id": "cat_stellar_blade", "name": "Stellar Blade", "description": "Stellar Blade action", "image_url": "https://images.pexels.com/photos/163036/mario-luigi-yoschi-figures-163036.jpeg", "popularity": 36},
        # Niche / evergreen
        {"category_id": "cat_asmr", "name": "ASMR", "description": "Relaxing ASMR streams", "image_url": "https://images.pexels.com/photos/4041392/pexels-photo-4041392.jpeg", "popularity": 34},
        {"category_id": "cat_talk_shows", "name": "Talk Shows & Podcasts", "description": "Live podcasts and interviews", "image_url": "https://images.pexels.com/photos/3784424/pexels-photo-3784424.jpeg", "popularity": 32},
        {"category_id": "cat_special_events", "name": "Special Events", "description": "One-off live events", "image_url": "https://images.pexels.com/photos/270637/pexels-photo-270637.jpeg", "popularity": 30},
        {"category_id": "cat_software", "name": "Software & Game Development", "description": "Programming live", "image_url": "https://images.pexels.com/photos/546819/pexels-photo-546819.jpeg", "popularity": 28},
        {"category_id": "cat_crypto", "name": "Crypto", "description": "Crypto markets and news", "image_url": "https://images.pexels.com/photos/844124/pexels-photo-844124.jpeg", "popularity": 26},
        {"category_id": "cat_pets_animals", "name": "Pets & Animals", "description": "Live pet cams and care", "image_url": "https://images.pexels.com/photos/45201/kitty-cat-kitten-pet-45201.jpeg", "popularity": 24},
        {"category_id": "cat_fitness_health", "name": "Fitness & Health", "description": "Workouts and wellness", "image_url": "https://images.pexels.com/photos/4753986/pexels-photo-4753986.jpeg", "popularity": 22},
        {"category_id": "cat_kick_originals", "name": "Kick Originals", "description": "Platform original programming", "image_url": "https://images.pexels.com/photos/2774556/pexels-photo-2774556.jpeg", "popularity": 20},
    ]
    
    for cat in categories:
        existing = await db.categories.find_one({"category_id": cat["category_id"]})
        if not existing:
            cat["viewer_count"] = 0
            cat["stream_count"] = 0
            await db.categories.insert_one(cat)
        else:
            # Keep image/description in sync (but not counts)
            await db.categories.update_one(
                {"category_id": cat["category_id"]},
                {"$set": {
                    "name": cat["name"],
                    "description": cat["description"],
                    "image_url": cat["image_url"],
                    "popularity": cat["popularity"],
                }}
            )
    
    # Remove stale categories not in the canonical seed list
    canonical_ids = [c["category_id"] for c in categories]
    stale_cats = await db.categories.find({"category_id": {"$nin": canonical_ids}}, {"_id": 0, "category_id": 1}).to_list(50)
    if stale_cats:
        stale_ids = [c["category_id"] for c in stale_cats]
        # Migrate any streams using stale categories to Just Chatting
        await db.streams.update_many({"category_id": {"$in": stale_ids}}, {"$set": {"category_id": "cat_just_chatting"}})
        await db.categories.delete_many({"category_id": {"$in": stale_ids}})
        logger.info(f"Removed {len(stale_ids)} stale categories")
    
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
    await db.notifications.create_index([("user_id", 1), ("created_at", -1)])
    await db.subscriptions.create_index([("subscriber_id", 1), ("streamer_id", 1)])
    await db.subscriptions.create_index("expires_at")
    await db.chat_bans.create_index([("stream_id", 1), ("user_id", 1)])
    await db.chat_timeouts.create_index([("stream_id", 1), ("user_id", 1)])
    await db.chat_timeouts.create_index("expires_at", expireAfterSeconds=0)
    await db.chat_mods.create_index([("stream_id", 1), ("user_id", 1)])
    
    logger.info("Indexes created")

# ============= LIVEKIT TOKEN ENDPOINTS =============

@api_router.post("/livekit/token/streamer")
async def get_streamer_livekit_token(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    room_name = body.get("room_name")
    
    if not room_name:
        raise HTTPException(status_code=400, detail="room_name required")
    
    if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
        raise HTTPException(status_code=500, detail="LiveKit not configured")
    
    token = AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    token = (
        token.with_identity(user["user_id"])
        .with_name(user.get("display_name") or user["username"])
        .with_grants(VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
        ))
    )
    
    return {
        "token": token.to_jwt(),
        "server_url": LIVEKIT_URL
    }

@api_router.post("/livekit/token/viewer")
async def get_viewer_livekit_token(request: Request):
    body = await request.json()
    room_name = body.get("room_name")
    viewer_id = body.get("viewer_id", f"viewer_{uuid.uuid4().hex[:8]}")
    viewer_name = body.get("viewer_name", "Viewer")
    
    if not room_name:
        raise HTTPException(status_code=400, detail="room_name required")
    
    if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
        raise HTTPException(status_code=500, detail="LiveKit not configured")
    
    token = AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    token = (
        token.with_identity(viewer_id)
        .with_name(viewer_name)
        .with_grants(VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=False,
            can_subscribe=True,
        ))
    )
    
    return {
        "token": token.to_jwt(),
        "server_url": LIVEKIT_URL
    }

# ============= WEBSOCKET CHAT ENDPOINT =============

@app.websocket("/api/ws/chat/{stream_id}")
async def websocket_chat(websocket: WebSocket, stream_id: str):
    await chat_manager.connect(websocket, stream_id)
    try:
        while True:
            data = await websocket.receive_json()
            user_id = data.get("user_id", "anonymous")
            
            # Check if user is banned
            ban = await db.chat_bans.find_one({
                "stream_id": stream_id,
                "user_id": user_id,
                "active": True
            })
            if ban:
                await websocket.send_json({"type": "system", "content": "You are banned from this chat."})
                continue
            
            # Check if user is timed out
            timeout = await db.chat_timeouts.find_one({
                "stream_id": stream_id,
                "user_id": user_id,
                "expires_at": {"$gt": datetime.now(timezone.utc)}
            })
            if timeout:
                remaining = int((timeout["expires_at"] - datetime.now(timezone.utc)).total_seconds())
                await websocket.send_json({"type": "system", "content": f"You are timed out for {remaining}s."})
                continue
            
            # Determine streamer_id for this stream
            stream_info = await db.streams.find_one({"stream_id": stream_id}, {"_id": 0, "user_id": 1, "slow_mode": 1})
            streamer_id = stream_info.get("user_id") if stream_info else None
            
            # Fetch streamer chat settings
            chat_cfg = await db.chat_settings.find_one({"user_id": streamer_id}, {"_id": 0}) if streamer_id else {}
            chat_cfg = chat_cfg or {}
            
            # Chat disabled
            if chat_cfg.get("chat_enabled") is False:
                await websocket.send_json({"type": "system", "content": "Chat is disabled for this stream."})
                continue
            
            # Followers-only
            if chat_cfg.get("followers_only") and user_id not in ("anonymous", streamer_id):
                following = await db.follows.find_one({"follower_id": user_id, "following_id": streamer_id})
                if not following:
                    await websocket.send_json({"type": "system", "content": "Followers-only chat. Follow the streamer to chat."})
                    continue
            
            # Subscribers-only
            if chat_cfg.get("subscribers_only") and user_id not in ("anonymous", streamer_id):
                active_sub = await db.subscriptions.find_one({
                    "user_id": user_id,
                    "streamer_id": streamer_id,
                    "status": "active"
                })
                if not active_sub:
                    await websocket.send_json({"type": "system", "content": "Subscribers-only chat. Subscribe to chat."})
                    continue
            
            # Check slow mode
            slow_mode = stream_info.get("slow_mode", 0) if stream_info else 0
            if slow_mode > 0 and user_id != "anonymous":
                last_msg = await db.chat_messages.find_one(
                    {"stream_id": stream_id, "user_id": user_id},
                    sort=[("created_at", -1)]
                )
                if last_msg:
                    last_time = last_msg.get("created_at")
                    if isinstance(last_time, str):
                        last_time = datetime.fromisoformat(last_time)
                    if last_time and last_time.tzinfo is None:
                        last_time = last_time.replace(tzinfo=timezone.utc)
                    diff = (datetime.now(timezone.utc) - last_time).total_seconds() if last_time else slow_mode + 1
                    if diff < slow_mode:
                        await websocket.send_json({"type": "system", "content": f"Slow mode active. Wait {int(slow_mode - diff)}s."})
                        continue
            
            raw_content = str(data.get("content", ""))[:500]
            final_content = raw_content
            
            # Restricted words check
            restricted_words = chat_cfg.get("restricted_words") or []
            rw_mode = chat_cfg.get("restricted_words_mode", "filter")
            if restricted_words and user_id != streamer_id:
                import re
                lowered = raw_content.lower()
                hits = [w for w in restricted_words if w and w in lowered]
                if hits:
                    if rw_mode == "block":
                        await websocket.send_json({"type": "system", "content": f"Message blocked — contains restricted word."})
                        continue
                    else:
                        for w in hits:
                            pattern = re.compile(re.escape(w), re.IGNORECASE)
                            final_content = pattern.sub("***", final_content)
            
            message_doc = {
                "message_id": f"msg_{uuid.uuid4().hex[:12]}",
                "stream_id": stream_id,
                "user_id": user_id,
                "username": data.get("username", "Anonymous"),
                "display_name": data.get("display_name"),
                "avatar_url": data.get("avatar_url"),
                "content": final_content,
                "type": data.get("type", "message"),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            await db.chat_messages.insert_one({**message_doc})
            message_doc.pop("_id", None)
            
            # Track unique chatters (for streamer "Path" achievement)
            if user_id and user_id != "anonymous" and streamer_id:
                await db.stream_chatters.update_one(
                    {"streamer_id": streamer_id, "user_id": user_id},
                    {"$setOnInsert": {"first_seen": datetime.now(timezone.utc)}, "$set": {"last_seen": datetime.now(timezone.utc)}},
                    upsert=True,
                )
            
            await chat_manager.broadcast(stream_id, message_doc)
    except WebSocketDisconnect:
        chat_manager.disconnect(websocket, stream_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        chat_manager.disconnect(websocket, stream_id)

# ============= SUBSCRIPTION TIERS =============

SUBSCRIPTION_TIERS = {
    "tier1": {"name": "Tier 1", "amount": 4.99, "perks": "Ad-free viewing, custom badge"},
    "tier2": {"name": "Tier 2", "amount": 9.99, "perks": "Tier 1 + Custom emotes, priority chat"},
    "tier3": {"name": "Tier 3", "amount": 24.99, "perks": "Tier 2 + VIP access, exclusive streams"},
    "tier4": {"name": "Tier 4", "amount": 49.99, "perks": "Tier 3 + Personal shoutout, mod access"},
    "tier5": {"name": "Tier 5", "amount": 100.00, "perks": "All perks + Direct streamer contact"},
}

@api_router.get("/subscriptions/tiers")
async def get_subscription_tiers():
    return [{"tier_id": k, **v} for k, v in SUBSCRIPTION_TIERS.items()]

@api_router.post("/subscriptions/checkout")
async def create_subscription_checkout(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    streamer_id = body.get("streamer_id")
    tier_id = body.get("tier_id")
    origin_url = body.get("origin_url")
    
    if tier_id not in SUBSCRIPTION_TIERS:
        # Check streamer custom tiers
        custom_tier = await db.streamer_tiers.find_one({"tier_id": tier_id, "user_id": streamer_id, "active": True})
        if not custom_tier:
            raise HTTPException(status_code=400, detail="Invalid subscription tier")
        tier = {"name": custom_tier["name"], "amount": custom_tier["amount"], "perks": custom_tier.get("perks", "")}
    else:
        tier = SUBSCRIPTION_TIERS[tier_id]
    amount = tier["amount"]
    
    streamer = await db.users.find_one({"user_id": streamer_id})
    if not streamer:
        raise HTTPException(status_code=404, detail="Streamer not found")
    
    # Check if already subscribed
    existing_sub = await db.subscriptions.find_one({
        "subscriber_id": user["user_id"],
        "streamer_id": streamer_id,
        "status": "active",
        "expires_at": {"$gt": datetime.now(timezone.utc)}
    })
    if existing_sub:
        raise HTTPException(status_code=400, detail="Already subscribed to this streamer")
    
    api_key = os.environ.get("STRIPE_API_KEY")
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    
    stripe_checkout = StripeCheckout(api_key=api_key, webhook_url=webhook_url)
    
    sub_id = f"sub_{uuid.uuid4().hex[:12]}"
    success_url = f"{origin_url}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin_url}/subscription/cancel"
    
    checkout_request = CheckoutSessionRequest(
        amount=amount,
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "subscription_id": sub_id,
            "subscriber_id": user["user_id"],
            "streamer_id": streamer_id,
            "tier_id": tier_id
        }
    )
    
    session = await stripe_checkout.create_checkout_session(checkout_request)
    
    await db.payment_transactions.insert_one({
        "transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
        "subscription_id": sub_id,
        "session_id": session.session_id,
        "subscriber_id": user["user_id"],
        "streamer_id": streamer_id,
        "tier_id": tier_id,
        "amount": amount,
        "currency": "usd",
        "payment_status": "pending",
        "type": "subscription",
        "created_at": datetime.now(timezone.utc)
    })
    
    return {"url": session.url, "session_id": session.session_id}

@api_router.get("/subscriptions/status/{session_id}")
async def get_subscription_status(session_id: str, user: dict = Depends(get_current_user)):
    api_key = os.environ.get("STRIPE_API_KEY")
    stripe_checkout = StripeCheckout(api_key=api_key, webhook_url="")
    
    status = await stripe_checkout.get_checkout_status(session_id)
    
    if status.payment_status == "paid":
        txn = await db.payment_transactions.find_one({"session_id": session_id, "type": "subscription"})
        if txn and txn.get("payment_status") != "completed":
            await db.payment_transactions.update_one(
                {"session_id": session_id},
                {"$set": {"payment_status": "completed"}}
            )
            
            # Create active subscription (30 days)
            await db.subscriptions.insert_one({
                "subscription_id": txn["subscription_id"],
                "subscriber_id": txn["subscriber_id"],
                "streamer_id": txn["streamer_id"],
                "tier_id": txn["tier_id"],
                "amount": txn["amount"],
                "status": "active",
                "starts_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc) + timedelta(days=30),
                "created_at": datetime.now(timezone.utc)
            })
            
            # Notify streamer
            await db.notifications.insert_one({
                "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
                "user_id": txn["streamer_id"],
                "type": "subscription",
                "message": f"New {SUBSCRIPTION_TIERS[txn['tier_id']]['name']} subscriber!",
                "data": {"subscriber_id": txn["subscriber_id"], "tier_id": txn["tier_id"]},
                "read": False,
                "created_at": datetime.now(timezone.utc)
            })
    
    return {
        "status": status.status,
        "payment_status": status.payment_status,
        "amount": status.amount_total / 100
    }

@api_router.get("/subscriptions/my")
async def get_my_subscriptions(user: dict = Depends(get_current_user)):
    subs = await db.subscriptions.find(
        {"subscriber_id": user["user_id"], "status": "active", "expires_at": {"$gt": datetime.now(timezone.utc)}},
        {"_id": 0}
    ).to_list(100)
    return subs

@api_router.get("/subscriptions/check/{streamer_id}")
async def check_subscription(streamer_id: str, user: dict = Depends(get_current_user)):
    sub = await db.subscriptions.find_one({
        "subscriber_id": user["user_id"],
        "streamer_id": streamer_id,
        "status": "active",
        "expires_at": {"$gt": datetime.now(timezone.utc)}
    }, {"_id": 0})
    return {"subscribed": sub is not None, "subscription": sub}

@api_router.get("/subscriptions/subscribers")
async def get_my_subscribers(user: dict = Depends(get_current_user)):
    subs = await db.subscriptions.find(
        {"streamer_id": user["user_id"], "status": "active", "expires_at": {"$gt": datetime.now(timezone.utc)}},
        {"_id": 0}
    ).to_list(100)
    return subs

# ============= NOTIFICATION ENDPOINTS =============

@api_router.get("/notifications")
async def get_notifications(user: dict = Depends(get_current_user), limit: int = 20):
    notifs = await db.notifications.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    return notifs

@api_router.get("/notifications/unread-count")
async def get_unread_count(user: dict = Depends(get_current_user)):
    count = await db.notifications.count_documents({
        "user_id": user["user_id"],
        "read": False
    })
    return {"count": count}

@api_router.put("/notifications/read-all")
async def mark_all_read(user: dict = Depends(get_current_user)):
    await db.notifications.update_many(
        {"user_id": user["user_id"], "read": False},
        {"$set": {"read": True}}
    )
    return {"message": "All notifications marked as read"}

@api_router.put("/notifications/{notification_id}/read")
async def mark_read(notification_id: str, user: dict = Depends(get_current_user)):
    await db.notifications.update_one(
        {"notification_id": notification_id, "user_id": user["user_id"]},
        {"$set": {"read": True}}
    )
    return {"message": "Notification marked as read"}

# ============= VOD (PAST STREAMS) =============

@api_router.get("/vods")
async def get_vods(limit: int = 20, offset: int = 0):
    vods = await db.streams.find(
        {"is_live": False, "started_at": {"$exists": True}}, {"_id": 0}
    ).sort("started_at", -1).skip(offset).limit(limit).to_list(limit)
    
    for vod in vods:
        user = await db.users.find_one({"user_id": vod["user_id"]}, {"_id": 0, "username": 1, "display_name": 1, "avatar_url": 1})
        if user:
            vod.update(user)
        category = await db.categories.find_one({"category_id": vod.get("category_id")}, {"_id": 0, "name": 1})
        if category:
            vod["category_name"] = category["name"]
        # Calculate duration
        if vod.get("started_at") and vod.get("ended_at"):
            if isinstance(vod["started_at"], str):
                vod["started_at"] = datetime.fromisoformat(vod["started_at"])
            if isinstance(vod["ended_at"], str):
                vod["ended_at"] = datetime.fromisoformat(vod["ended_at"])
            duration = (vod["ended_at"] - vod["started_at"]).total_seconds()
            vod["duration_seconds"] = int(duration)
    
    return vods

@api_router.get("/vods/{stream_id}")
async def get_vod(stream_id: str):
    vod = await db.streams.find_one({"stream_id": stream_id}, {"_id": 0})
    if not vod:
        raise HTTPException(status_code=404, detail="VOD not found")
    
    user = await db.users.find_one({"user_id": vod["user_id"]}, {"_id": 0, "username": 1, "display_name": 1, "avatar_url": 1, "bio": 1, "follower_count": 1})
    if user:
        vod.update(user)
    category = await db.categories.find_one({"category_id": vod.get("category_id")}, {"_id": 0, "name": 1})
    if category:
        vod["category_name"] = category["name"]
    
    # Get chat replay
    chat = await db.chat_messages.find(
        {"stream_id": stream_id}, {"_id": 0}
    ).sort("created_at", 1).to_list(500)
    vod["chat_replay"] = chat
    
    return vod

@api_router.get("/users/{username}/vods")
async def get_user_vods(username: str, limit: int = 20):
    user = await db.users.find_one({"username": username.lower()}, {"_id": 0, "user_id": 1})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    vods = await db.streams.find(
        {"user_id": user["user_id"], "is_live": False, "started_at": {"$exists": True}}, {"_id": 0}
    ).sort("started_at", -1).limit(limit).to_list(limit)
    
    for vod in vods:
        category = await db.categories.find_one({"category_id": vod.get("category_id")}, {"_id": 0, "name": 1})
        if category:
            vod["category_name"] = category["name"]
    
    return vods

# ============= MODERATION ENDPOINTS =============

async def is_mod_or_streamer(user: dict, stream_id: str) -> bool:
    """Check if user is the streamer or a moderator for this stream."""
    stream = await db.streams.find_one({"stream_id": stream_id})
    if not stream:
        return False
    if stream["user_id"] == user["user_id"]:
        return True
    if user.get("role") == "admin":
        return True
    mod = await db.chat_mods.find_one({
        "stream_id": stream_id,
        "user_id": user["user_id"],
        "active": True
    })
    return mod is not None

@api_router.post("/streams/{stream_id}/mod/{target_user_id}")
async def assign_mod(stream_id: str, target_user_id: str, user: dict = Depends(get_current_user)):
    stream = await db.streams.find_one({"stream_id": stream_id})
    if not stream or stream["user_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Only the streamer can assign mods")
    
    target = await db.users.find_one({"user_id": target_user_id})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    existing = await db.chat_mods.find_one({"stream_id": stream_id, "user_id": target_user_id, "active": True})
    if existing:
        raise HTTPException(status_code=400, detail="User is already a mod")
    
    await db.chat_mods.insert_one({
        "mod_id": f"mod_{uuid.uuid4().hex[:12]}",
        "stream_id": stream_id,
        "user_id": target_user_id,
        "username": target["username"],
        "assigned_by": user["user_id"],
        "active": True,
        "created_at": datetime.now(timezone.utc)
    })
    
    await db.notifications.insert_one({
        "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
        "user_id": target_user_id,
        "type": "mod",
        "message": f"You've been made a moderator by {user.get('display_name') or user['username']}!",
        "data": {"stream_id": stream_id},
        "read": False,
        "created_at": datetime.now(timezone.utc)
    })
    
    return {"message": f"User {target['username']} is now a mod"}

@api_router.delete("/streams/{stream_id}/mod/{target_user_id}")
async def remove_mod(stream_id: str, target_user_id: str, user: dict = Depends(get_current_user)):
    stream = await db.streams.find_one({"stream_id": stream_id})
    if not stream or stream["user_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Only the streamer can remove mods")
    
    result = await db.chat_mods.update_one(
        {"stream_id": stream_id, "user_id": target_user_id, "active": True},
        {"$set": {"active": False}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Mod not found")
    
    return {"message": "Mod removed"}

@api_router.get("/streams/{stream_id}/mods")
async def get_mods(stream_id: str):
    mods = await db.chat_mods.find(
        {"stream_id": stream_id, "active": True}, {"_id": 0}
    ).to_list(50)
    return mods

@api_router.post("/streams/{stream_id}/ban/{target_user_id}")
async def ban_user(stream_id: str, target_user_id: str, request: Request, user: dict = Depends(get_current_user)):
    if not await is_mod_or_streamer(user, stream_id):
        raise HTTPException(status_code=403, detail="Not authorized to ban users")
    
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    reason = body.get("reason", "No reason provided")
    
    existing = await db.chat_bans.find_one({"stream_id": stream_id, "user_id": target_user_id, "active": True})
    if existing:
        raise HTTPException(status_code=400, detail="User already banned")
    
    target = await db.users.find_one({"user_id": target_user_id}, {"_id": 0, "username": 1})
    
    await db.chat_bans.insert_one({
        "ban_id": f"ban_{uuid.uuid4().hex[:12]}",
        "stream_id": stream_id,
        "user_id": target_user_id,
        "username": target["username"] if target else "unknown",
        "banned_by": user["user_id"],
        "reason": reason,
        "active": True,
        "created_at": datetime.now(timezone.utc)
    })
    
    # Broadcast ban event
    await chat_manager.broadcast(stream_id, {
        "type": "moderation",
        "action": "ban",
        "target_user_id": target_user_id,
        "target_username": target["username"] if target else "unknown",
        "moderator": user.get("display_name") or user["username"]
    })
    
    return {"message": "User banned from chat"}

@api_router.delete("/streams/{stream_id}/ban/{target_user_id}")
async def unban_user(stream_id: str, target_user_id: str, user: dict = Depends(get_current_user)):
    if not await is_mod_or_streamer(user, stream_id):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    result = await db.chat_bans.update_one(
        {"stream_id": stream_id, "user_id": target_user_id, "active": True},
        {"$set": {"active": False}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Ban not found")
    
    return {"message": "User unbanned"}

@api_router.get("/streams/{stream_id}/bans")
async def get_bans(stream_id: str, user: dict = Depends(get_current_user)):
    if not await is_mod_or_streamer(user, stream_id):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    bans = await db.chat_bans.find(
        {"stream_id": stream_id, "active": True}, {"_id": 0}
    ).to_list(100)
    return bans

@api_router.post("/streams/{stream_id}/timeout/{target_user_id}")
async def timeout_user(stream_id: str, target_user_id: str, request: Request, user: dict = Depends(get_current_user)):
    if not await is_mod_or_streamer(user, stream_id):
        raise HTTPException(status_code=403, detail="Not authorized to timeout users")
    
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    duration = body.get("duration", 60)  # Default 1 min
    reason = body.get("reason", "")
    
    if duration not in [60, 300, 600]:
        duration = 60
    
    target = await db.users.find_one({"user_id": target_user_id}, {"_id": 0, "username": 1})
    
    await db.chat_timeouts.update_one(
        {"stream_id": stream_id, "user_id": target_user_id},
        {"$set": {
            "timeout_id": f"to_{uuid.uuid4().hex[:12]}",
            "stream_id": stream_id,
            "user_id": target_user_id,
            "username": target["username"] if target else "unknown",
            "timed_out_by": user["user_id"],
            "duration": duration,
            "reason": reason,
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=duration),
            "created_at": datetime.now(timezone.utc)
        }},
        upsert=True
    )
    
    await chat_manager.broadcast(stream_id, {
        "type": "moderation",
        "action": "timeout",
        "target_user_id": target_user_id,
        "target_username": target["username"] if target else "unknown",
        "duration": duration,
        "moderator": user.get("display_name") or user["username"]
    })
    
    return {"message": f"User timed out for {duration}s"}

@api_router.put("/streams/{stream_id}/slow-mode")
async def set_slow_mode(stream_id: str, request: Request, user: dict = Depends(get_current_user)):
    if not await is_mod_or_streamer(user, stream_id):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    body = await request.json()
    duration = body.get("duration", 0)  # 0 = off, 3/5/10/30 seconds
    
    if duration not in [0, 3, 5, 10, 30]:
        raise HTTPException(status_code=400, detail="Invalid slow mode duration")
    
    await db.streams.update_one(
        {"stream_id": stream_id},
        {"$set": {"slow_mode": duration}}
    )
    
    await chat_manager.broadcast(stream_id, {
        "type": "moderation",
        "action": "slow_mode",
        "duration": duration,
        "moderator": user.get("display_name") or user["username"]
    })
    
    return {"message": f"Slow mode {'disabled' if duration == 0 else f'set to {duration}s'}"}

@api_router.get("/streams/{stream_id}/mod-status")
async def get_mod_status(stream_id: str, user: dict = Depends(get_current_user)):
    """Check if current user is a mod/streamer for this stream."""
    is_mod = await is_mod_or_streamer(user, stream_id)
    stream = await db.streams.find_one({"stream_id": stream_id}, {"_id": 0, "slow_mode": 1, "user_id": 1})
    return {
        "is_mod": is_mod,
        "is_streamer": stream["user_id"] == user["user_id"] if stream else False,
        "slow_mode": stream.get("slow_mode", 0) if stream else 0
    }

# ============= ADMIN - S3 STORAGE CONFIG =============

@api_router.get("/admin/storage-config")
async def get_storage_config(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    config = await db.admin_config.find_one({"type": "s3_storage"}, {"_id": 0})
    if config:
        # Mask the secret key
        if config.get("secret_key"):
            config["secret_key"] = config["secret_key"][:4] + "***" + config["secret_key"][-4:]
    return config or {"type": "s3_storage", "configured": False}

@api_router.post("/admin/storage-config")
async def save_storage_config(request: Request, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    body = await request.json()
    
    config = {
        "type": "s3_storage",
        "provider": body.get("provider", "wasabi"),
        "endpoint": body.get("endpoint", ""),
        "bucket": body.get("bucket", ""),
        "region": body.get("region", ""),
        "access_key": body.get("access_key", ""),
        "secret_key": body.get("secret_key", ""),
        "force_path_style": body.get("force_path_style", True),
        "configured": True,
        "updated_at": datetime.now(timezone.utc)
    }
    
    await db.admin_config.update_one(
        {"type": "s3_storage"},
        {"$set": config},
        upsert=True
    )
    
    return {"message": "Storage configuration saved successfully"}

@api_router.delete("/admin/storage-config")
async def delete_storage_config(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    await db.admin_config.delete_one({"type": "s3_storage"})
    return {"message": "Storage configuration deleted"}

# ============= ADMIN - SITE SETTINGS =============

@api_router.get("/admin/site-settings")
async def get_site_settings(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    config = await db.admin_config.find_one({"type": "site_settings"}, {"_id": 0})
    return config or {"type": "site_settings", "title": "StreamVault", "description": "Live streaming platform", "icon_url": "", "configured": False}

@api_router.post("/admin/site-settings")
async def save_site_settings(request: Request, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    body = await request.json()
    config = {
        "type": "site_settings",
        "title": body.get("title", "StreamVault"),
        "description": body.get("description", ""),
        "icon_url": body.get("icon_url", ""),
        "configured": True,
        "updated_at": datetime.now(timezone.utc)
    }
    await db.admin_config.update_one({"type": "site_settings"}, {"$set": config}, upsert=True)
    return {"message": "Site settings saved"}

@api_router.get("/site-settings")
async def get_public_site_settings():
    """Public endpoint - no auth required."""
    config = await db.admin_config.find_one({"type": "site_settings"}, {"_id": 0})
    return config or {"title": "StreamVault", "description": "Live streaming platform", "icon_url": ""}

# ============= STREAMER SUBSCRIPTION TIERS =============

@api_router.get("/users/{user_id}/subscription-tiers")
async def get_user_sub_tiers(user_id: str):
    tiers = await db.streamer_tiers.find({"user_id": user_id, "active": True}, {"_id": 0}).sort("amount", 1).to_list(10)
    if not tiers:
        return [{"tier_id": k, **v} for k, v in SUBSCRIPTION_TIERS.items()]
    return tiers

@api_router.post("/my/subscription-tiers")
async def save_my_sub_tiers(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    tiers = body.get("tiers", [])
    
    await db.streamer_tiers.delete_many({"user_id": user["user_id"]})
    
    for t in tiers[:5]:
        name = str(t.get("name", ""))[:50]
        amount = float(t.get("amount", 0))
        perks = str(t.get("perks", ""))[:200]
        if name and amount > 0:
            await db.streamer_tiers.insert_one({
                "tier_id": f"tier_{uuid.uuid4().hex[:8]}",
                "user_id": user["user_id"],
                "name": name,
                "amount": round(amount, 2),
                "perks": perks,
                "active": True,
                "created_at": datetime.now(timezone.utc)
            })
    
    return {"message": "Subscription tiers saved"}

@api_router.get("/my/subscription-tiers")
async def get_my_sub_tiers(user: dict = Depends(get_current_user)):
    tiers = await db.streamer_tiers.find({"user_id": user["user_id"], "active": True}, {"_id": 0}).sort("amount", 1).to_list(10)
    return tiers

# ============= USER BIO EDIT =============

@api_router.put("/users/bio")
async def update_bio(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    bio = str(body.get("bio", ""))[:500]
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"bio": bio}})
    return {"message": "Bio updated", "bio": bio}

# ============= CUSTOM DONATION =============

# ============= REVENUE & WITHDRAWALS =============

@api_router.get("/my/revenue")
async def get_my_revenue(user: dict = Depends(get_current_user)):
    """Get streamer's revenue summary."""
    donations = await db.donations.find({"streamer_id": user["user_id"]}, {"_id": 0, "amount": 1}).to_list(10000)
    subs = await db.subscriptions.find({"streamer_id": user["user_id"]}, {"_id": 0, "amount": 1}).to_list(10000)
    ads = await db.ad_impressions.find({"streamer_id": user["user_id"]}, {"_id": 0, "streamer_earned": 1}).to_list(100000)
    
    total_donations = sum(d.get("amount", 0) for d in donations)
    total_subs = sum(s.get("amount", 0) for s in subs)
    total_ads = sum(a.get("streamer_earned", 0) for a in ads)
    total_earned = total_donations + total_subs + total_ads
    
    # Get total withdrawn (completed)
    withdrawals = await db.withdrawals.find(
        {"user_id": user["user_id"], "status": "completed"}, {"_id": 0, "amount": 1}
    ).to_list(10000)
    total_withdrawn = sum(w.get("amount", 0) for w in withdrawals)
    
    # Pending withdrawals
    pending = await db.withdrawals.find(
        {"user_id": user["user_id"], "status": "pending"}, {"_id": 0, "amount": 1}
    ).to_list(100)
    total_pending = sum(w.get("amount", 0) for w in pending)
    
    available = round(total_earned - total_withdrawn - total_pending, 2)
    
    return {
        "total_donations": round(total_donations, 2),
        "total_subscriptions": round(total_subs, 2),
        "total_ads": round(total_ads, 2),
        "total_earned": round(total_earned, 2),
        "total_withdrawn": round(total_withdrawn, 2),
        "total_pending": round(total_pending, 2),
        "available_balance": max(available, 0)
    }

@api_router.post("/my/withdraw")
async def request_withdrawal(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    
    first_name = str(body.get("first_name", "")).strip()
    last_name = str(body.get("last_name", "")).strip()
    amount = float(body.get("amount", 0))
    iban = str(body.get("iban", "")).strip()
    paypal_email = str(body.get("paypal_email", "")).strip()
    
    if not first_name or not last_name:
        raise HTTPException(status_code=400, detail="First and last name required")
    if amount < 50:
        raise HTTPException(status_code=400, detail="Minimum withdrawal is $50")
    if not iban:
        raise HTTPException(status_code=400, detail="IBAN is required")
    
    # Check available balance
    revenue = await get_my_revenue.__wrapped__(request, user) if hasattr(get_my_revenue, '__wrapped__') else None
    if not revenue:
        # Manually calculate
        donations = await db.donations.find({"streamer_id": user["user_id"]}, {"_id": 0, "amount": 1}).to_list(10000)
        subs = await db.subscriptions.find({"streamer_id": user["user_id"]}, {"_id": 0, "amount": 1}).to_list(10000)
        total_earned = sum(d.get("amount", 0) for d in donations) + sum(s.get("amount", 0) for s in subs)
        withdrawn = await db.withdrawals.find({"user_id": user["user_id"], "status": {"$in": ["completed", "pending"]}}, {"_id": 0, "amount": 1}).to_list(10000)
        total_used = sum(w.get("amount", 0) for w in withdrawn)
        available = round(total_earned - total_used, 2)
    else:
        available = revenue["available_balance"]
    
    if amount > available:
        raise HTTPException(status_code=400, detail=f"Insufficient balance. Available: ${available:.2f}")
    
    withdrawal_id = f"wd_{uuid.uuid4().hex[:12]}"
    
    await db.withdrawals.insert_one({
        "withdrawal_id": withdrawal_id,
        "user_id": user["user_id"],
        "username": user["username"],
        "display_name": user.get("display_name"),
        "first_name": first_name,
        "last_name": last_name,
        "amount": round(amount, 2),
        "iban": iban,
        "paypal_email": paypal_email or None,
        "status": "pending",
        "created_at": datetime.now(timezone.utc)
    })
    
    # Notify admin
    admins = await db.users.find({"role": "admin"}, {"_id": 0, "user_id": 1}).to_list(20)
    for admin in admins:
        await db.notifications.insert_one({
            "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
            "user_id": admin["user_id"],
            "type": "withdrawal",
            "message": f"New withdrawal request: ${amount:.2f} from {user.get('display_name') or user['username']}",
            "data": {"withdrawal_id": withdrawal_id},
            "read": False,
            "created_at": datetime.now(timezone.utc)
        })
    
    return {"message": "Withdrawal request submitted", "withdrawal_id": withdrawal_id}

@api_router.get("/my/withdrawals")
async def get_my_withdrawals(user: dict = Depends(get_current_user)):
    withdrawals = await db.withdrawals.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return withdrawals

# ============= ADMIN WITHDRAWAL MANAGEMENT =============

@api_router.get("/admin/withdrawals")
async def get_withdrawal_requests(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    withdrawals = await db.withdrawals.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return withdrawals

@api_router.put("/admin/withdrawals/{withdrawal_id}/approve")
async def approve_withdrawal(withdrawal_id: str, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    wd = await db.withdrawals.find_one({"withdrawal_id": withdrawal_id})
    if not wd:
        raise HTTPException(status_code=404, detail="Withdrawal not found")
    if wd["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Withdrawal is already {wd['status']}")
    
    try:
        # Check if automated payouts are enabled
        payout_cfg = await db.admin_config.find_one({"type": "payout_settings"}, {"_id": 0})
        automated = bool(payout_cfg and payout_cfg.get("automated_enabled"))
        
        payout_info = {"method": "manual"}
        
        if automated:
            # Try Stripe Connect transfer + payout
            connect = await db.stripe_connect_accounts.find_one({"user_id": wd["user_id"]}, {"_id": 0})
            if not connect:
                raise HTTPException(status_code=400, detail="Automated payouts enabled but streamer has no Stripe Connect account")
            if not connect.get("payouts_enabled"):
                raise HTTPException(status_code=400, detail="Streamer's Stripe Connect account is not yet verified for payouts")
            
            amount_cents = int(round(float(wd["amount"]) * 100))
            
            # Transfer funds from platform → connected account, then create payout on connected account
            try:
                transfer = stripe_sdk.Transfer.create(
                    amount=amount_cents,
                    currency=connect.get("currency", "usd"),
                    destination=connect["stripe_account_id"],
                    description=f"Withdrawal {withdrawal_id}",
                )
                payout = stripe_sdk.Payout.create(
                    amount=amount_cents,
                    currency=connect.get("currency", "usd"),
                    stripe_account=connect["stripe_account_id"],
                    description=f"StreamVault payout {withdrawal_id}",
                )
                payout_info = {
                    "method": "stripe_connect",
                    "transfer_id": transfer["id"],
                    "payout_id": payout["id"],
                    "stripe_account_id": connect["stripe_account_id"],
                }
            except stripe_sdk.error.StripeError as se:
                logger.error(f"Stripe payout error: {se}")
                raise HTTPException(status_code=502, detail=f"Stripe payout failed: {str(se.user_message or se)}")
        
        await db.withdrawals.update_one(
            {"withdrawal_id": withdrawal_id},
            {"$set": {
                "status": "completed",
                "approved_by": user["user_id"],
                "approved_at": datetime.now(timezone.utc),
                "payout_info": payout_info,
            }}
        )
        
        # Notify streamer
        await db.notifications.insert_one({
            "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
            "user_id": wd["user_id"],
            "type": "withdrawal",
            "message": f"Your withdrawal of ${wd['amount']:.2f} has been approved!" + (" Payout on its way." if payout_info["method"] == "stripe_connect" else ""),
            "data": {"withdrawal_id": withdrawal_id},
            "read": False,
            "created_at": datetime.now(timezone.utc)
        })
        
        return {"message": "Withdrawal approved", "withdrawal_id": withdrawal_id, "payout_info": payout_info}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Withdrawal approval error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process withdrawal")

@api_router.put("/admin/withdrawals/{withdrawal_id}/reject")
async def reject_withdrawal(withdrawal_id: str, request: Request, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    reason = body.get("reason", "Request rejected by admin")
    
    wd = await db.withdrawals.find_one({"withdrawal_id": withdrawal_id})
    if not wd:
        raise HTTPException(status_code=404, detail="Withdrawal not found")
    if wd["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Withdrawal is already {wd['status']}")
    
    await db.withdrawals.update_one(
        {"withdrawal_id": withdrawal_id},
        {"$set": {
            "status": "rejected",
            "rejected_by": user["user_id"],
            "rejected_at": datetime.now(timezone.utc),
            "reject_reason": reason
        }}
    )
    
    # Notify streamer
    await db.notifications.insert_one({
        "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
        "user_id": wd["user_id"],
        "type": "withdrawal",
        "message": f"Your withdrawal of ${wd['amount']:.2f} was rejected: {reason}",
        "data": {"withdrawal_id": withdrawal_id},
        "read": False,
        "created_at": datetime.now(timezone.utc)
    })
    
    return {"message": "Withdrawal rejected"}

# ============= LIVEKIT EGRESS (RECORDING) =============

@api_router.post("/streams/{stream_id}/record/start")
async def start_recording(stream_id: str, user: dict = Depends(get_current_user)):
    stream = await db.streams.find_one({"stream_id": stream_id})
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    if stream["user_id"] != user["user_id"] and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Get S3 config
    s3_config = await db.admin_config.find_one({"type": "s3_storage"}, {"_id": 0})
    if not s3_config or not s3_config.get("configured"):
        raise HTTPException(status_code=400, detail="S3 storage not configured. Ask admin to set up storage in Admin panel.")
    
    if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
        raise HTTPException(status_code=500, detail="LiveKit not configured")
    
    from livekit.api import LiveKitAPI, RoomCompositeEgressRequest, SegmentedFileOutput, S3Upload, EncodingOptionsPreset
    
    try:
        room_name = f"stream_{stream_id}"
        
        s3_upload = S3Upload(
            bucket=s3_config["bucket"],
            region=s3_config["region"],
            access_key=s3_config["access_key"],
            secret=s3_config["secret_key"],
            force_path_style=s3_config.get("force_path_style", True),
            endpoint=s3_config["endpoint"],
        )
        
        egress_req = RoomCompositeEgressRequest(
            room_name=room_name,
            layout="speaker",
            segment_outputs=[
                SegmentedFileOutput(
                    filename_prefix=f"recordings/{stream_id}/{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                    playlist_name="playlist.m3u8",
                    segment_duration=4,
                    s3=s3_upload,
                ),
            ],
        )
        
        async with LiveKitAPI(url=LIVEKIT_URL, api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET) as lkapi:
            res = await lkapi.egress.start_room_composite_egress(egress_req)
        
        egress_id = res.egress_id
        
        await db.streams.update_one(
            {"stream_id": stream_id},
            {"$set": {"recording": True, "egress_id": egress_id}}
        )
        
        await db.recordings.insert_one({
            "recording_id": f"rec_{uuid.uuid4().hex[:12]}",
            "stream_id": stream_id,
            "egress_id": egress_id,
            "status": "recording",
            "storage_path": f"recordings/{stream_id}/",
            "started_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        })
        
        return {"message": "Recording started", "egress_id": egress_id}
    
    except Exception as e:
        logger.error(f"Egress start error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start recording: {str(e)}")

@api_router.post("/streams/{stream_id}/record/stop")
async def stop_recording(stream_id: str, user: dict = Depends(get_current_user)):
    stream = await db.streams.find_one({"stream_id": stream_id})
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    if stream["user_id"] != user["user_id"] and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    egress_id = stream.get("egress_id")
    if not egress_id:
        raise HTTPException(status_code=400, detail="No active recording")
    
    from livekit.api import LiveKitAPI, StopEgressRequest
    
    try:
        async with LiveKitAPI(url=LIVEKIT_URL, api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET) as lkapi:
            await lkapi.egress.stop_egress(StopEgressRequest(egress_id=egress_id))
        
        await db.streams.update_one(
            {"stream_id": stream_id},
            {"$set": {"recording": False}, "$unset": {"egress_id": ""}}
        )
        
        s3_config = await db.admin_config.find_one({"type": "s3_storage"}, {"_id": 0})
        storage_url = ""
        if s3_config:
            endpoint = s3_config.get("endpoint", "").rstrip("/")
            bucket = s3_config.get("bucket", "")
            storage_url = f"https://{bucket}.{endpoint}/recordings/{stream_id}/playlist.m3u8"
        
        await db.recordings.update_one(
            {"stream_id": stream_id, "egress_id": egress_id},
            {"$set": {
                "status": "completed",
                "playback_url": storage_url,
                "ended_at": datetime.now(timezone.utc)
            }}
        )
        
        # Update stream with VOD URL
        await db.streams.update_one(
            {"stream_id": stream_id},
            {"$set": {"vod_url": storage_url}}
        )
        
        return {"message": "Recording stopped", "playback_url": storage_url}
    
    except Exception as e:
        logger.error(f"Egress stop error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop recording: {str(e)}")

@api_router.get("/streams/{stream_id}/recordings")
async def get_stream_recordings(stream_id: str):
    recordings = await db.recordings.find(
        {"stream_id": stream_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(20)
    return recordings

# ============= STRIPE CONNECT (AUTOMATED PAYOUTS) =============

@api_router.get("/my/stripe-connect/status")
async def get_my_stripe_connect_status(user: dict = Depends(get_current_user)):
    """Returns current Stripe Connect account status for a streamer."""
    account = await db.stripe_connect_accounts.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if not account:
        return {"connected": False, "verification_status": "not_started"}
    
    # Try to refresh status from Stripe
    try:
        acc = stripe_sdk.Account.retrieve(account["stripe_account_id"])
        caps = acc.get("capabilities", {})
        req = acc.get("requirements", {}) or {}
        currently_due = req.get("currently_due", []) or []
        transfers_active = caps.get("transfers") == "active"
        payouts_active = bool(acc.get("payouts_enabled"))
        charges_active = bool(acc.get("charges_enabled"))
        verified = not currently_due and transfers_active and payouts_active
        
        new_status = "verified" if verified else ("pending" if not currently_due else "action_required")
        await db.stripe_connect_accounts.update_one(
            {"user_id": user["user_id"]},
            {"$set": {
                "verification_status": new_status,
                "payouts_enabled": payouts_active,
                "charges_enabled": charges_active,
                "currently_due": currently_due,
                "updated_at": datetime.now(timezone.utc),
            }}
        )
        
        return {
            "connected": True,
            "stripe_account_id": account["stripe_account_id"],
            "verification_status": new_status,
            "payouts_enabled": payouts_active,
            "charges_enabled": charges_active,
            "currently_due": currently_due,
            "bank_last4": account.get("bank_last4"),
            "country": account.get("country", "US"),
            "holder_name": account.get("holder_name"),
        }
    except Exception as e:
        logger.warning(f"Stripe account retrieve failed: {e}")
        return {
            "connected": True,
            "stripe_account_id": account["stripe_account_id"],
            "verification_status": account.get("verification_status", "pending"),
            "payouts_enabled": account.get("payouts_enabled", False),
            "charges_enabled": account.get("charges_enabled", False),
            "currently_due": account.get("currently_due", []),
            "bank_last4": account.get("bank_last4"),
            "country": account.get("country", "US"),
            "holder_name": account.get("holder_name"),
            "error": "Could not sync with Stripe — showing cached status.",
        }


@api_router.post("/my/stripe-connect/create")
async def create_my_stripe_connect(request: Request, user: dict = Depends(get_current_user)):
    """Creates (or updates) a Stripe Connect Custom account + attached bank account for the current user."""
    body = await request.json()
    
    first_name = str(body.get("first_name", "")).strip()
    last_name = str(body.get("last_name", "")).strip()
    dob = str(body.get("dob", "")).strip()  # YYYY-MM-DD
    country = str(body.get("country", "US")).strip().upper()
    currency = str(body.get("currency", "usd")).lower()
    address_line1 = str(body.get("address_line1", "")).strip()
    city = str(body.get("city", "")).strip()
    state = str(body.get("state", "")).strip()
    postal_code = str(body.get("postal_code", "")).strip()
    phone = str(body.get("phone", "")).strip()
    routing_number = str(body.get("routing_number", "")).strip()
    account_number = str(body.get("account_number", "")).strip()
    holder_name = str(body.get("holder_name", "")).strip() or f"{first_name} {last_name}".strip()
    tos_accepted = bool(body.get("tos_accepted", False))
    
    if not (first_name and last_name and dob and address_line1 and city and postal_code and account_number):
        raise HTTPException(status_code=400, detail="Missing required fields")
    if not tos_accepted:
        raise HTTPException(status_code=400, detail="You must accept the Stripe Services Agreement")
    
    try:
        dob_parts = dob.split("-")
        dob_dict = {"year": int(dob_parts[0]), "month": int(dob_parts[1]), "day": int(dob_parts[2])}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date of birth (use YYYY-MM-DD)")
    
    existing = await db.stripe_connect_accounts.find_one({"user_id": user["user_id"]})
    
    try:
        if existing:
            # Update existing account
            acc = stripe_sdk.Account.modify(
                existing["stripe_account_id"],
                individual={
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": user.get("email"),
                    "dob": dob_dict,
                    "phone": phone or None,
                    "address": {
                        "line1": address_line1,
                        "city": city,
                        "state": state,
                        "postal_code": postal_code,
                        "country": country,
                    },
                },
                tos_acceptance={
                    "date": int(datetime.now(timezone.utc).timestamp()),
                    "ip": request.client.host if request.client else "0.0.0.0",
                },
                business_profile={
                    "mcc": "7299",  # Services - other
                    "product_description": "Live streaming content creator on StreamVault",
                    "url": os.environ.get("FRONTEND_URL", "https://streamvault.com"),
                },
            )
            stripe_account_id = acc["id"]
        else:
            acc = stripe_sdk.Account.create(
                type="custom",
                country=country,
                email=user.get("email"),
                capabilities={
                    "transfers": {"requested": True},
                    "card_payments": {"requested": True},
                },
                business_type="individual",
                individual={
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": user.get("email"),
                    "dob": dob_dict,
                    "phone": phone or None,
                    "address": {
                        "line1": address_line1,
                        "city": city,
                        "state": state,
                        "postal_code": postal_code,
                        "country": country,
                    },
                },
                tos_acceptance={
                    "date": int(datetime.now(timezone.utc).timestamp()),
                    "ip": request.client.host if request.client else "0.0.0.0",
                },
                business_profile={
                    "mcc": "7299",
                    "product_description": "Live streaming content creator on StreamVault",
                    "url": os.environ.get("FRONTEND_URL", "https://streamvault.com"),
                },
            )
            stripe_account_id = acc["id"]
        
        # Create bank account token and attach as external account
        bank_params = {
            "country": country,
            "currency": currency,
            "account_holder_name": holder_name,
            "account_holder_type": "individual",
            "account_number": account_number,
        }
        # Routing number required for US/CA; for EU/UK accounts, account_number alone (IBAN) works.
        if routing_number:
            bank_params["routing_number"] = routing_number
        
        bank_token = stripe_sdk.Token.create(bank_account=bank_params)
        stripe_sdk.Account.create_external_account(
            stripe_account_id,
            external_account=bank_token["id"],
            default_for_currency=True,
        )
        
        # Refresh account to get final state
        final_acc = stripe_sdk.Account.retrieve(stripe_account_id)
        req = final_acc.get("requirements", {}) or {}
        currently_due = req.get("currently_due", []) or []
        transfers_active = final_acc.get("capabilities", {}).get("transfers") == "active"
        verified = not currently_due and transfers_active and bool(final_acc.get("payouts_enabled"))
        
        account_doc = {
            "user_id": user["user_id"],
            "stripe_account_id": stripe_account_id,
            "country": country,
            "currency": currency,
            "holder_name": holder_name,
            "bank_last4": account_number[-4:] if account_number else None,
            "verification_status": "verified" if verified else ("pending" if not currently_due else "action_required"),
            "payouts_enabled": bool(final_acc.get("payouts_enabled")),
            "charges_enabled": bool(final_acc.get("charges_enabled")),
            "currently_due": currently_due,
            "created_at": existing.get("created_at") if existing else datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        
        await db.stripe_connect_accounts.update_one(
            {"user_id": user["user_id"]},
            {"$set": account_doc},
            upsert=True,
        )
        
        return {
            "message": "Stripe Connect account saved",
            "stripe_account_id": stripe_account_id,
            "verification_status": account_doc["verification_status"],
            "payouts_enabled": account_doc["payouts_enabled"],
            "currently_due": currently_due,
        }
    
    except stripe_sdk.error.StripeError as e:
        logger.error(f"Stripe Connect error: {e}")
        raise HTTPException(status_code=400, detail=f"Stripe error: {str(e.user_message or e)}")
    except Exception as e:
        logger.error(f"Connect create error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create Stripe Connect account: {str(e)}")


@api_router.delete("/my/stripe-connect")
async def delete_my_stripe_connect(user: dict = Depends(get_current_user)):
    """Disconnect Stripe Connect account (does not delete on Stripe side)."""
    await db.stripe_connect_accounts.delete_one({"user_id": user["user_id"]})
    return {"message": "Disconnected"}


# ============= ADMIN PAYOUT SETTINGS =============

@api_router.get("/admin/payout-settings")
async def get_payout_settings(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    cfg = await db.admin_config.find_one({"type": "payout_settings"}, {"_id": 0})
    return cfg or {"type": "payout_settings", "automated_enabled": False, "platform_fee_percent": 0}


@api_router.put("/admin/payout-settings")
async def update_payout_settings(request: Request, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    body = await request.json()
    doc = {
        "type": "payout_settings",
        "automated_enabled": bool(body.get("automated_enabled", False)),
        "platform_fee_percent": float(body.get("platform_fee_percent", 0)),
        "updated_at": datetime.now(timezone.utc),
    }
    await db.admin_config.update_one({"type": "payout_settings"}, {"$set": doc}, upsert=True)
    return {"message": "Payout settings saved", **{k: v for k, v in doc.items() if k != "updated_at"}}


# ============= AD MONETIZATION =============

DEFAULT_AD_CPM = {
    "live_pre_roll": 2.0,
    "live_mid_roll": 3.0,
    "vod_pre_roll": 2.0,
    "vod_mid_roll": 2.5,
}

@api_router.get("/admin/ad-settings")
async def admin_get_ad_settings(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    cfg = await db.admin_config.find_one({"type": "ad_settings"}, {"_id": 0})
    if not cfg:
        return {
            "type": "ad_settings",
            "enabled": False,
            "revenue_share_percent": 70.0,
            "cpm_rates": DEFAULT_AD_CPM,
            "ad_slots": [],
        }
    return cfg


@api_router.put("/admin/ad-settings")
async def admin_update_ad_settings(request: Request, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    body = await request.json()
    
    # ad_slots: list of {slot_id, name, placement (live_pre_roll|live_mid_roll|vod_pre_roll|vod_mid_roll), ad_type (html|video|image|vast), ad_code, image_url, video_url, vast_url, click_url, duration_sec, active}
    slots_in = body.get("ad_slots", []) or []
    slots = []
    for s in slots_in[:50]:
        slots.append({
            "slot_id": s.get("slot_id") or f"slot_{uuid.uuid4().hex[:10]}",
            "name": str(s.get("name", ""))[:100],
            "placement": str(s.get("placement", "live_pre_roll")),
            "ad_type": str(s.get("ad_type", "html")),
            "ad_code": str(s.get("ad_code", ""))[:10000],
            "image_url": str(s.get("image_url", ""))[:500],
            "video_url": str(s.get("video_url", ""))[:500],
            "vast_url": str(s.get("vast_url", ""))[:500],
            "click_url": str(s.get("click_url", ""))[:500],
            "duration_sec": max(1, min(60, int(s.get("duration_sec") or 15))),
            "active": bool(s.get("active", True)),
        })
    
    cpm_in = body.get("cpm_rates") or {}
    cpm_rates = {k: max(0.0, float(cpm_in.get(k, DEFAULT_AD_CPM[k]))) for k in DEFAULT_AD_CPM}
    
    doc = {
        "type": "ad_settings",
        "enabled": bool(body.get("enabled", False)),
        "revenue_share_percent": max(0.0, min(100.0, float(body.get("revenue_share_percent", 70.0)))),
        "cpm_rates": cpm_rates,
        "ad_slots": slots,
        "updated_at": datetime.now(timezone.utc),
    }
    await db.admin_config.update_one({"type": "ad_settings"}, {"$set": doc}, upsert=True)
    return {"message": "Ad settings saved", **{k: v for k, v in doc.items() if k != "updated_at"}}


@api_router.get("/ads/vast/resolve")
async def resolve_vast(url: str):
    """Fetches a VAST tag URL and returns the first MediaFile URL + duration (basic VAST 2/3/4 support)."""
    if not url or not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid VAST URL")
    try:
        import httpx
        import xml.etree.ElementTree as ET
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            res = await client.get(url)
        if res.status_code != 200:
            raise HTTPException(status_code=502, detail=f"VAST fetch failed: {res.status_code}")
        
        root = ET.fromstring(res.text)
        # Find first MediaFile
        media_url = None
        mime_type = None
        for mf in root.iter():
            if mf.tag.split("}")[-1] == "MediaFile":
                media_url = (mf.text or "").strip()
                mime_type = mf.attrib.get("type") or mf.attrib.get("mimeType")
                if media_url:
                    break
        
        # Find Duration
        duration_sec = 15
        for d in root.iter():
            if d.tag.split("}")[-1] == "Duration" and d.text:
                try:
                    parts = d.text.strip().split(":")
                    if len(parts) == 3:
                        h, m, s = parts
                        duration_sec = int(float(h)) * 3600 + int(float(m)) * 60 + int(float(s))
                except Exception:
                    pass
                break
        
        # Find ClickThrough
        click_url = ""
        for c in root.iter():
            if c.tag.split("}")[-1] == "ClickThrough" and c.text:
                click_url = c.text.strip()
                break
        
        if not media_url:
            return {"ok": False, "error": "No MediaFile found in VAST response"}
        
        return {
            "ok": True,
            "media_url": media_url,
            "mime_type": mime_type,
            "duration_sec": max(1, min(60, duration_sec)),
            "click_url": click_url,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"VAST resolve error: {e}")
        raise HTTPException(status_code=502, detail=f"VAST parse error: {str(e)}")


@api_router.get("/ads/active")
async def get_active_ad(placement: str = "live_pre_roll", stream_id: Optional[str] = None):
    """Public endpoint — returns one active ad slot for the given placement. Respects streamer opt-out."""
    cfg = await db.admin_config.find_one({"type": "ad_settings"}, {"_id": 0})
    if not cfg or not cfg.get("enabled"):
        return {"enabled": False, "ad": None}
    
    # If a stream is specified, check streamer ad opt-out
    if stream_id:
        stream = await db.streams.find_one({"stream_id": stream_id}, {"_id": 0, "user_id": 1})
        if stream and stream.get("user_id"):
            opt = await db.streamer_ad_prefs.find_one({"user_id": stream["user_id"]}, {"_id": 0, "opt_out": 1})
            if opt and opt.get("opt_out"):
                return {"enabled": True, "ad": None, "reason": "streamer_opt_out"}
    
    slots = [s for s in cfg.get("ad_slots", []) if s.get("active") and s.get("placement") == placement]
    if not slots:
        return {"enabled": True, "ad": None}
    
    import random
    slot = random.choice(slots)
    cpm = (cfg.get("cpm_rates") or {}).get(placement, 0)
    return {"enabled": True, "ad": slot, "cpm": cpm}


@api_router.post("/ads/impression")
async def record_ad_impression(request: Request, user: Optional[dict] = Depends(get_optional_user)):
    """Record an ad impression. Streamers earn revenue_share_percent of CPM-derived cents."""
    body = await request.json()
    stream_id = str(body.get("stream_id", "")).strip()
    slot_id = str(body.get("slot_id", "")).strip()
    placement = str(body.get("placement", "live_pre_roll"))
    
    if not stream_id or not slot_id:
        raise HTTPException(status_code=400, detail="stream_id and slot_id required")
    
    cfg = await db.admin_config.find_one({"type": "ad_settings"}, {"_id": 0})
    if not cfg or not cfg.get("enabled"):
        return {"credited": False}
    
    slot = next((s for s in cfg.get("ad_slots", []) if s.get("slot_id") == slot_id), None)
    if not slot or not slot.get("active"):
        return {"credited": False}
    
    cpm = (cfg.get("cpm_rates") or {}).get(placement, 0) or 0.0
    revshare = float(cfg.get("revenue_share_percent", 70.0)) / 100.0
    # One impression = CPM / 1000
    per_impression_gross = cpm / 1000.0
    streamer_earned = round(per_impression_gross * revshare, 6)
    platform_earned = round(per_impression_gross - streamer_earned, 6)
    
    # Resolve streamer_id from stream
    stream = await db.streams.find_one({"stream_id": stream_id}, {"_id": 0, "user_id": 1})
    streamer_id = stream.get("user_id") if stream else None
    
    # Dedupe rapid-fire impressions (same viewer + slot within 30s)
    viewer_key = user.get("user_id") if user else str(body.get("viewer_id", "")).strip()
    if viewer_key:
        recent = await db.ad_impressions.find_one({
            "stream_id": stream_id,
            "slot_id": slot_id,
            "viewer_key": viewer_key,
            "created_at": {"$gte": datetime.now(timezone.utc) - timedelta(seconds=30)},
        })
        if recent:
            return {"credited": False, "reason": "duplicate"}
    
    impression_id = f"imp_{uuid.uuid4().hex[:14]}"
    await db.ad_impressions.insert_one({
        "impression_id": impression_id,
        "stream_id": stream_id,
        "streamer_id": streamer_id,
        "slot_id": slot_id,
        "placement": placement,
        "cpm": cpm,
        "streamer_earned": streamer_earned,
        "platform_earned": platform_earned,
        "viewer_key": viewer_key or None,
        "created_at": datetime.now(timezone.utc),
    })
    return {"credited": True, "impression_id": impression_id, "streamer_earned": streamer_earned}


@api_router.get("/my/ad-earnings")
async def get_my_ad_earnings(user: dict = Depends(get_current_user)):
    pipeline = [
        {"$match": {"streamer_id": user["user_id"]}},
        {"$group": {
            "_id": "$placement",
            "impressions": {"$sum": 1},
            "earned": {"$sum": "$streamer_earned"},
        }},
    ]
    rows = await db.ad_impressions.aggregate(pipeline).to_list(100)
    total_impressions = sum(r["impressions"] for r in rows)
    total_earned = round(sum(r["earned"] for r in rows), 2)
    by_placement = {r["_id"]: {"impressions": r["impressions"], "earned": round(r["earned"], 2)} for r in rows}
    return {
        "total_impressions": total_impressions,
        "total_earned": total_earned,
        "by_placement": by_placement,
    }


@api_router.get("/admin/ad-earnings")
async def admin_get_ad_earnings(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    total_imp = await db.ad_impressions.count_documents({})
    pipeline = [{"$group": {
        "_id": None,
        "platform_earned": {"$sum": "$platform_earned"},
        "streamer_earned": {"$sum": "$streamer_earned"},
    }}]
    agg = await db.ad_impressions.aggregate(pipeline).to_list(1)
    platform_earned = round(agg[0]["platform_earned"], 2) if agg else 0.0
    streamer_earned = round(agg[0]["streamer_earned"], 2) if agg else 0.0
    
    # Top streamers
    top_pipeline = [
        {"$group": {"_id": "$streamer_id", "impressions": {"$sum": 1}, "earned": {"$sum": "$streamer_earned"}}},
        {"$sort": {"earned": -1}},
        {"$limit": 10},
    ]
    top = await db.ad_impressions.aggregate(top_pipeline).to_list(10)
    top_streamers = []
    for t in top:
        if not t.get("_id"):
            continue
        u = await db.users.find_one({"user_id": t["_id"]}, {"_id": 0, "username": 1, "display_name": 1})
        top_streamers.append({
            "user_id": t["_id"],
            "username": u.get("username") if u else "unknown",
            "display_name": u.get("display_name") if u else None,
            "impressions": t["impressions"],
            "earned": round(t["earned"], 2),
        })
    
    return {
        "total_impressions": total_imp,
        "platform_earned": platform_earned,
        "streamer_earned": streamer_earned,
        "top_streamers": top_streamers,
    }


# ============= REVENUE ANALYTICS =============

@api_router.get("/my/revenue/analytics")
async def get_my_revenue_analytics(period: str = "daily", user: dict = Depends(get_current_user)):
    """Aggregate donations + subscriptions + ad earnings into time-bucketed trends."""
    now = datetime.now(timezone.utc)
    
    if period == "weekly":
        start = now - timedelta(weeks=12)
        date_fmt = "%Y-W%V"
    elif period == "monthly":
        start = now - timedelta(days=365)
        date_fmt = "%Y-%m"
    else:
        period = "daily"
        start = now - timedelta(days=30)
        date_fmt = "%Y-%m-%d"
    
    async def bucket(collection, match_field, amount_field="amount"):
        pipeline = [
            {"$match": {match_field: user["user_id"], "created_at": {"$gte": start}}},
            {"$group": {
                "_id": {"$dateToString": {"format": date_fmt, "date": "$created_at"}},
                "amount": {"$sum": f"${amount_field}"},
            }},
            {"$sort": {"_id": 1}},
        ]
        rows = await collection.aggregate(pipeline).to_list(500)
        return {r["_id"]: round(r["amount"], 2) for r in rows}
    
    donations_map = await bucket(db.donations, "streamer_id", "amount")
    subs_map = await bucket(db.subscriptions, "streamer_id", "amount")
    ads_map = await bucket(db.ad_impressions, "streamer_id", "streamer_earned")
    
    all_keys = sorted(set(donations_map) | set(subs_map) | set(ads_map))
    series = []
    for k in all_keys:
        d = donations_map.get(k, 0)
        s = subs_map.get(k, 0)
        a = ads_map.get(k, 0)
        series.append({
            "period": k,
            "donations": round(d, 2),
            "subscriptions": round(s, 2),
            "ads": round(a, 2),
            "total": round(d + s + a, 2),
        })
    
    return {"period": period, "series": series}


# ============= SUBSCRIBER EMOTES (built-in blue set, 20) =============

SUBSCRIBER_EMOTES = [
    {"code": ":svBlueFire:",   "name": "Blue Fire",    "url": "https://api.iconify.design/twemoji:fire.svg?color=%2300A3FF"},
    {"code": ":svBlueHeart:",  "name": "Blue Heart",   "url": "https://api.iconify.design/twemoji:blue-heart.svg"},
    {"code": ":svBlueStar:",   "name": "Blue Star",    "url": "https://api.iconify.design/twemoji:star.svg?color=%2300A3FF"},
    {"code": ":svBlueHype:",   "name": "Blue Hype",    "url": "https://api.iconify.design/twemoji:rocket.svg?color=%2300A3FF"},
    {"code": ":svBlueLaugh:",  "name": "Blue Laugh",   "url": "https://api.iconify.design/twemoji:face-with-tears-of-joy.svg?color=%2300A3FF"},
    {"code": ":svBlueCry:",    "name": "Blue Cry",     "url": "https://api.iconify.design/twemoji:loudly-crying-face.svg?color=%2300A3FF"},
    {"code": ":svBlueCool:",   "name": "Blue Cool",    "url": "https://api.iconify.design/twemoji:smiling-face-with-sunglasses.svg?color=%2300A3FF"},
    {"code": ":svBlueLove:",   "name": "Blue Love",    "url": "https://api.iconify.design/twemoji:smiling-face-with-heart-eyes.svg?color=%2300A3FF"},
    {"code": ":svBlueClap:",   "name": "Blue Clap",    "url": "https://api.iconify.design/twemoji:clapping-hands.svg?color=%2300A3FF"},
    {"code": ":svBlueWave:",   "name": "Blue Wave",    "url": "https://api.iconify.design/twemoji:waving-hand.svg?color=%2300A3FF"},
    {"code": ":svBlueCrown:",  "name": "Blue Crown",   "url": "https://api.iconify.design/twemoji:crown.svg?color=%2300A3FF"},
    {"code": ":svBlueGem:",    "name": "Blue Gem",     "url": "https://api.iconify.design/twemoji:gem-stone.svg?color=%2300A3FF"},
    {"code": ":svBlueThink:",  "name": "Blue Think",   "url": "https://api.iconify.design/twemoji:thinking-face.svg?color=%2300A3FF"},
    {"code": ":svBlueShock:",  "name": "Blue Shock",   "url": "https://api.iconify.design/twemoji:face-with-open-mouth.svg?color=%2300A3FF"},
    {"code": ":svBlueRage:",   "name": "Blue Rage",    "url": "https://api.iconify.design/twemoji:angry-face.svg?color=%2300A3FF"},
    {"code": ":svBlueSkull:",  "name": "Blue Skull",   "url": "https://api.iconify.design/twemoji:skull.svg?color=%2300A3FF"},
    {"code": ":svBlueKiss:",   "name": "Blue Kiss",    "url": "https://api.iconify.design/twemoji:kissing-face-with-smiling-eyes.svg?color=%2300A3FF"},
    {"code": ":svBluePartying:","name": "Blue Party",   "url": "https://api.iconify.design/twemoji:partying-face.svg?color=%2300A3FF"},
    {"code": ":svBlueCheck:",  "name": "Blue Check",   "url": "https://api.iconify.design/twemoji:check-mark-button.svg?color=%2300A3FF"},
    {"code": ":svBlueLightning:","name": "Blue Bolt",   "url": "https://api.iconify.design/twemoji:high-voltage.svg?color=%2300A3FF"},
]


@api_router.get("/emotes/subscriber")
async def get_subscriber_emotes():
    """Built-in 20 blue emotes (subscriber-only across platform)."""
    return SUBSCRIBER_EMOTES


# ============= STREAMER CUSTOM EMOTES =============

@api_router.get("/my/emotes")
async def get_my_emotes(user: dict = Depends(get_current_user)):
    emotes = await db.streamer_emotes.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", 1).to_list(50)
    return emotes


@api_router.get("/users/{user_id}/emotes")
async def get_user_emotes(user_id: str):
    """Public — returns emotes for a streamer (subscribers_only enforced client-side)."""
    emotes = await db.streamer_emotes.find({"user_id": user_id}, {"_id": 0}).sort("created_at", 1).to_list(50)
    return emotes


@api_router.post("/my/emotes")
async def upload_my_emote(
    file: UploadFile = File(...),
    code: str = "",
    subscribers_only: bool = False,
    user: dict = Depends(get_current_user),
):
    """Upload one emote. Max 20 per streamer. subscribers_only flag per emote."""
    count = await db.streamer_emotes.count_documents({"user_id": user["user_id"]})
    if count >= 20:
        raise HTTPException(status_code=400, detail="Maximum 20 emotes per streamer")
    
    code = (code or "").strip()
    if not code or not code.startswith(":") or not code.endswith(":") or len(code) < 3 or len(code) > 30:
        raise HTTPException(status_code=400, detail="Emote code must be formatted like :myEmote: (3–30 chars)")
    
    existing = await db.streamer_emotes.find_one({"user_id": user["user_id"], "code": code})
    if existing:
        raise HTTPException(status_code=400, detail=f"Emote code {code} already used")
    
    content = await file.read()
    if len(content) > 512 * 1024:
        raise HTTPException(status_code=400, detail="Emote must be ≤ 512KB")
    
    content_type = file.content_type or "image/png"
    ext = content_type.split("/")[-1]
    emote_id = f"emt_{uuid.uuid4().hex[:12]}"
    path = f"emotes/{user['user_id']}/{emote_id}.{ext}"
    put_object(path, content, content_type)
    
    doc = {
        "emote_id": emote_id,
        "user_id": user["user_id"],
        "code": code,
        "url": f"/api/files/{path}",
        "subscribers_only": bool(subscribers_only),
        "created_at": datetime.now(timezone.utc),
    }
    await db.streamer_emotes.insert_one(doc)
    return {k: (v.isoformat() if k == "created_at" else v) for k, v in doc.items() if k != "_id"}


@api_router.put("/my/emotes/{emote_id}")
async def update_my_emote(emote_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    patch = {}
    if "subscribers_only" in body:
        patch["subscribers_only"] = bool(body["subscribers_only"])
    if "code" in body:
        code = str(body["code"]).strip()
        if not code.startswith(":") or not code.endswith(":") or len(code) < 3 or len(code) > 30:
            raise HTTPException(status_code=400, detail="Invalid emote code")
        patch["code"] = code
    if not patch:
        return {"message": "No changes"}
    res = await db.streamer_emotes.update_one(
        {"emote_id": emote_id, "user_id": user["user_id"]},
        {"$set": patch}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Emote not found")
    return {"message": "Updated"}


@api_router.delete("/my/emotes/{emote_id}")
async def delete_my_emote(emote_id: str, user: dict = Depends(get_current_user)):
    res = await db.streamer_emotes.delete_one({"emote_id": emote_id, "user_id": user["user_id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Emote not found")
    return {"message": "Deleted"}


# ============= STREAMER CHAT SETTINGS =============

@api_router.get("/my/chat-settings")
async def get_my_chat_settings(user: dict = Depends(get_current_user)):
    cfg = await db.chat_settings.find_one({"user_id": user["user_id"]}, {"_id": 0})
    defaults = {
        "user_id": user["user_id"],
        "chat_enabled": True,
        "rules": "",
        "followers_only": False,
        "subscribers_only": False,
        "restricted_words": [],
        "restricted_words_mode": "filter",  # 'filter' or 'block'
    }
    if not cfg:
        return defaults
    return {**defaults, **cfg}


@api_router.put("/my/chat-settings")
async def save_my_chat_settings(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    restricted_words_in = body.get("restricted_words", []) or []
    if isinstance(restricted_words_in, str):
        restricted_words_in = [w.strip() for w in restricted_words_in.split(",") if w.strip()]
    restricted_words = [str(w).strip().lower() for w in restricted_words_in if str(w).strip()][:100]
    
    mode = str(body.get("restricted_words_mode", "filter"))
    if mode not in ("filter", "block"):
        mode = "filter"
    
    doc = {
        "user_id": user["user_id"],
        "chat_enabled": bool(body.get("chat_enabled", True)),
        "rules": str(body.get("rules", ""))[:2000],
        "followers_only": bool(body.get("followers_only", False)),
        "subscribers_only": bool(body.get("subscribers_only", False)),
        "restricted_words": restricted_words,
        "restricted_words_mode": mode,
        "updated_at": datetime.now(timezone.utc),
    }
    await db.chat_settings.update_one({"user_id": user["user_id"]}, {"$set": doc}, upsert=True)
    
    # Broadcast to connected chat viewers so they re-fetch rules / apply changes instantly
    live_stream = await db.streams.find_one({"user_id": user["user_id"], "is_live": True}, {"_id": 0, "stream_id": 1})
    if live_stream:
        await chat_manager.broadcast(live_stream["stream_id"], {
            "type": "chat_settings_updated",
            "chat_enabled": doc["chat_enabled"],
            "rules": doc["rules"],
            "followers_only": doc["followers_only"],
            "subscribers_only": doc["subscribers_only"],
        })
    
    return {"message": "Chat settings saved", **{k: v for k, v in doc.items() if k != "updated_at"}}


@api_router.get("/users/{user_id}/chat-settings")
async def get_user_chat_settings(user_id: str):
    """Public — returns chat_enabled + rules + modes for a streamer (excludes restricted_words list from public reveal)."""
    cfg = await db.chat_settings.find_one({"user_id": user_id}, {"_id": 0})
    if not cfg:
        return {"user_id": user_id, "chat_enabled": True, "rules": "", "followers_only": False, "subscribers_only": False}
    return {
        "user_id": user_id,
        "chat_enabled": cfg.get("chat_enabled", True),
        "rules": cfg.get("rules", ""),
        "followers_only": cfg.get("followers_only", False),
        "subscribers_only": cfg.get("subscribers_only", False),
    }


# ============= CLIPS =============

@api_router.post("/streams/{stream_id}/clip")
async def create_clip(stream_id: str, request: Request, user: Optional[dict] = Depends(get_optional_user)):
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    title = str(body.get("title", ""))[:120] or "Untitled clip"
    timestamp = int(body.get("timestamp", 0))  # seconds from stream start
    thumbnail_data_url = str(body.get("thumbnail_data_url", ""))
    
    stream = await db.streams.find_one({"stream_id": stream_id}, {"_id": 0})
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    
    clip_id = f"clip_{uuid.uuid4().hex[:12]}"
    thumb_url = ""
    
    # Optional: save thumbnail data URL as a small asset
    if thumbnail_data_url.startswith("data:image/"):
        try:
            import base64
            header, b64 = thumbnail_data_url.split(",", 1)
            content_type = header.split(";")[0].replace("data:", "") or "image/jpeg"
            data = base64.b64decode(b64)
            if len(data) <= 512 * 1024:
                ext = content_type.split("/")[-1]
                path = f"clips/{stream_id}/{clip_id}.{ext}"
                put_object(path, data, content_type)
                thumb_url = f"/api/files/{path}"
        except Exception as e:
            logger.warning(f"Clip thumb save failed: {e}")
    
    doc = {
        "clip_id": clip_id,
        "stream_id": stream_id,
        "streamer_id": stream.get("user_id"),
        "clipper_user_id": user.get("user_id") if user else None,
        "title": title,
        "timestamp_sec": timestamp,
        "thumbnail_url": thumb_url,
        "created_at": datetime.now(timezone.utc),
    }
    await db.clips.insert_one(doc)
    return {k: (v.isoformat() if k == "created_at" else v) for k, v in doc.items() if k != "_id"}


@api_router.get("/streams/{stream_id}/clips")
async def list_stream_clips(stream_id: str, limit: int = 20):
    clips = await db.clips.find({"stream_id": stream_id}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return clips


@api_router.get("/my/clips")
async def get_my_clips(user: dict = Depends(get_current_user), limit: int = 50):
    clips = await db.clips.find({"streamer_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return clips


# ============= STRIPE CONNECT WEBHOOK =============

@api_router.post("/webhook/stripe/connect")
async def stripe_connect_webhook(request: Request):
    """Handles account.updated, payout.paid, payout.failed events from Stripe Connect."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    webhook_secret = os.environ.get("STRIPE_CONNECT_WEBHOOK_SECRET", "")
    
    try:
        if webhook_secret:
            event = stripe_sdk.Webhook.construct_event(payload, sig, webhook_secret)
        else:
            # No secret configured — log & parse anyway (dev mode)
            logger.warning("STRIPE_CONNECT_WEBHOOK_SECRET not set; skipping signature check")
            event = json.loads(payload.decode("utf-8"))
    except stripe_sdk.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Connect webhook parse error: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    
    event_type = event.get("type")
    data_obj = (event.get("data") or {}).get("object") or {}
    connected_account_id = event.get("account") or data_obj.get("account") or data_obj.get("id")
    
    try:
        if event_type == "account.updated":
            account_id = data_obj.get("id")
            if account_id:
                caps = data_obj.get("capabilities", {}) or {}
                req = data_obj.get("requirements", {}) or {}
                currently_due = req.get("currently_due", []) or []
                payouts_enabled = bool(data_obj.get("payouts_enabled"))
                charges_enabled = bool(data_obj.get("charges_enabled"))
                verified = not currently_due and caps.get("transfers") == "active" and payouts_enabled
                await db.stripe_connect_accounts.update_one(
                    {"stripe_account_id": account_id},
                    {"$set": {
                        "payouts_enabled": payouts_enabled,
                        "charges_enabled": charges_enabled,
                        "currently_due": currently_due,
                        "verification_status": "verified" if verified else ("pending" if not currently_due else "action_required"),
                        "updated_at": datetime.now(timezone.utc),
                    }}
                )
                # Notify streamer if fully verified
                if verified:
                    acc = await db.stripe_connect_accounts.find_one({"stripe_account_id": account_id}, {"_id": 0, "user_id": 1})
                    if acc:
                        await db.notifications.insert_one({
                            "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
                            "user_id": acc["user_id"],
                            "type": "stripe_connect",
                            "message": "Your Stripe payout account is fully verified. Automated payouts are now possible.",
                            "data": {"stripe_account_id": account_id},
                            "read": False,
                            "created_at": datetime.now(timezone.utc),
                        })
        
        elif event_type in ("payout.paid", "payout.failed"):
            payout_id = data_obj.get("id")
            status = "paid" if event_type == "payout.paid" else "failed"
            await db.withdrawals.update_many(
                {"payout_info.payout_id": payout_id},
                {"$set": {
                    "payout_info.stripe_status": status,
                    "payout_status_updated_at": datetime.now(timezone.utc),
                    **({"status": "failed"} if status == "failed" else {}),
                }}
            )
            wd = await db.withdrawals.find_one({"payout_info.payout_id": payout_id}, {"_id": 0, "user_id": 1, "amount": 1, "withdrawal_id": 1})
            if wd:
                msg = (f"Your payout of ${wd['amount']:.2f} was paid out successfully!"
                       if status == "paid" else
                       f"Your payout of ${wd['amount']:.2f} failed at Stripe. Please review your bank details and try again.")
                await db.notifications.insert_one({
                    "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
                    "user_id": wd["user_id"],
                    "type": "withdrawal",
                    "message": msg,
                    "data": {"withdrawal_id": wd["withdrawal_id"]},
                    "read": False,
                    "created_at": datetime.now(timezone.utc),
                })
        else:
            # Silently accept other Connect events (account.application.*, capability.*, etc.)
            pass
    except Exception as e:
        logger.error(f"Connect webhook handle error for {event_type}: {e}")
        # Still 200 to ack — failed DB writes will retry elsewhere
    
    return {"received": True, "event": event_type, "account": connected_account_id}


# ============= ACHIEVEMENTS =============

ACHIEVEMENT_GRADES = [
    {"grade": "Expert",       "min_subs_5m": 5, "min_max_donation": 50, "min_follows": 20},
    {"grade": "Advanced",     "min_subs_5m": 3, "min_max_donation": 30, "min_follows": 10},
    {"grade": "Intermediate", "min_subs_5m": 2, "min_max_donation": 20, "min_follows": 5},
    {"grade": "Beginner",     "min_subs_5m": 1, "min_max_donation": 0,  "min_follows": 2, "min_donations_count": 5},
]


async def compute_user_achievements(user_id: str):
    """Compute mission status + current grade for a user."""
    now = datetime.now(timezone.utc)
    five_months_ago = now - timedelta(days=30 * 5)
    
    # Subscribers for 5+ months — count unique streamer_id where the subscription started ≥5mo ago
    subs = await db.subscriptions.find(
        {"user_id": user_id},
        {"_id": 0, "streamer_id": 1, "status": 1, "created_at": 1, "started_at": 1}
    ).to_list(1000)
    long_sub_channels = set()
    total_donation = 0.0
    max_donation = 0.0
    donations_count = 0
    for s in subs:
        start = s.get("started_at") or s.get("created_at")
        if isinstance(start, str):
            try:
                start = datetime.fromisoformat(start.replace("Z", "+00:00"))
            except Exception:
                start = None
        if start and start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if start and start <= five_months_ago:
            long_sub_channels.add(s.get("streamer_id"))
    
    subs_5m_count = len(long_sub_channels)
    
    # Donations
    donations = await db.donations.find({"user_id": user_id}, {"_id": 0, "amount": 1}).to_list(2000)
    donations_count = len(donations)
    for d in donations:
        amt = float(d.get("amount", 0) or 0)
        total_donation += amt
        if amt > max_donation:
            max_donation = amt
    
    # Follows
    follows_count = await db.follows.count_documents({"follower_id": user_id})
    
    # Determine highest grade achieved
    grade = None
    for g in ACHIEVEMENT_GRADES:
        ok = subs_5m_count >= g["min_subs_5m"] and max_donation >= g["min_max_donation"] and follows_count >= g["min_follows"]
        if g.get("min_donations_count"):
            ok = ok and donations_count >= g["min_donations_count"]
        if ok:
            grade = g["grade"]
            break
    
    # Build per-grade mission results
    grades_with_status = []
    for g in ACHIEVEMENT_GRADES:
        missions = [
            {
                "id": "subs_5m",
                "label": f"Be subscribed to {g['min_subs_5m']} streamer channel(s) for 5+ months",
                "required": g["min_subs_5m"],
                "current": subs_5m_count,
                "done": subs_5m_count >= g["min_subs_5m"],
            },
        ]
        if g.get("min_donations_count"):
            missions.append({
                "id": "donations_count",
                "label": f"Make {g['min_donations_count']} donations",
                "required": g["min_donations_count"],
                "current": donations_count,
                "done": donations_count >= g["min_donations_count"],
            })
        if g["min_max_donation"] > 0:
            missions.append({
                "id": "max_donation",
                "label": f"Make a single donation of ${g['min_max_donation']}+",
                "required": g["min_max_donation"],
                "current": round(max_donation, 2),
                "done": max_donation >= g["min_max_donation"],
            })
        missions.append({
            "id": "follows",
            "label": f"Follow {g['min_follows']} streamers",
            "required": g["min_follows"],
            "current": follows_count,
            "done": follows_count >= g["min_follows"],
        })
        grades_with_status.append({
            "grade": g["grade"],
            "achieved": all(m["done"] for m in missions),
            "missions": missions,
        })
    
    # Reverse so Beginner is shown first
    grades_with_status.reverse()
    
    return {
        "grade": grade,
        "verified": bool(grade),
        "stats": {
            "long_term_subscriptions": subs_5m_count,
            "donations_count": donations_count,
            "max_donation": round(max_donation, 2),
            "total_donation": round(total_donation, 2),
            "follows_count": follows_count,
        },
        "grades": grades_with_status,
    }


@api_router.get("/my/achievements")
async def my_achievements(user: dict = Depends(get_current_user)):
    return await compute_user_achievements(user["user_id"])


@api_router.get("/users/{user_id}/achievements")
async def public_achievements(user_id: str):
    return await compute_user_achievements(user_id)


# ============= STREAMER "PATH TO A PERFECT STREAMER" =============

async def compute_streamer_path(user_id: str):
    now = datetime.now(timezone.utc)
    twelve_mo = now - timedelta(days=365)
    
    # 1. Total subscribers count (last 12 months)
    subs_count = await db.subscriptions.count_documents({"streamer_id": user_id, "created_at": {"$gte": twelve_mo}})
    
    # 2. Total followers (last 12 months)
    followers_count = await db.follows.count_documents({"following_id": user_id, "created_at": {"$gte": twelve_mo}})
    # If no created_at on follows, count all
    if followers_count == 0:
        followers_count = await db.follows.count_documents({"following_id": user_id})
    
    # 3. Total broadcasting hours (sum duration across streams in last 12 months)
    total_hours = 0.0
    streams = await db.streams.find(
        {"user_id": user_id, "broadcasting_started_at": {"$exists": True}},
        {"_id": 0, "broadcasting_started_at": 1, "broadcasting_ended_at": 1, "started_at": 1, "ended_at": 1, "duration_seconds": 1}
    ).to_list(5000)
    for s in streams:
        dur = s.get("duration_seconds")
        if dur:
            total_hours += float(dur) / 3600.0
            continue
        start = s.get("broadcasting_started_at") or s.get("started_at")
        end = s.get("broadcasting_ended_at") or s.get("ended_at")
        if isinstance(start, str):
            try: start = datetime.fromisoformat(start.replace("Z", "+00:00"))
            except: start = None
        if isinstance(end, str):
            try: end = datetime.fromisoformat(end.replace("Z", "+00:00"))
            except: end = None
        if start and end:
            if start.tzinfo is None: start = start.replace(tzinfo=timezone.utc)
            if end.tzinfo is None: end = end.replace(tzinfo=timezone.utc)
            if start >= twelve_mo:
                total_hours += max(0, (end - start).total_seconds() / 3600.0)
    
    # 4. Unique chatters (last 12 months) — from stream_chatters collection
    unique_chatters = await db.stream_chatters.count_documents({"streamer_id": user_id, "last_seen": {"$gte": twelve_mo}})
    if unique_chatters == 0:
        # fallback: distinct user_ids from chat_messages on their streams
        stream_ids = [s.get("stream_id") for s in await db.streams.find({"user_id": user_id}, {"_id": 0, "stream_id": 1}).to_list(2000) if s.get("stream_id")]
        if stream_ids:
            distinct = await db.chat_messages.distinct("user_id", {"stream_id": {"$in": stream_ids}, "created_at": {"$gte": twelve_mo}})
            unique_chatters = len([u for u in distinct if u and u != "anonymous"])
    
    missions = [
        {"id": "subs_50",       "label": "Reach 50 subscribers in the last 12 months",         "required": 50,  "current": subs_count,      "done": subs_count >= 50},
        {"id": "followers_500", "label": "Reach 500 followers in the last 12 months",          "required": 500, "current": followers_count, "done": followers_count >= 500},
        {"id": "hours_300",     "label": "Stream 300 hours connected with OBS in the last 12 months", "required": 300, "current": round(total_hours, 1), "done": total_hours >= 300},
        {"id": "chatters_500",  "label": "500 unique users have written in your chat in the last 12 months", "required": 500, "current": unique_chatters, "done": unique_chatters >= 500},
    ]
    return {"missions": missions, "all_done": all(m["done"] for m in missions)}


@api_router.get("/my/streamer-path")
async def my_streamer_path(user: dict = Depends(get_current_user)):
    return await compute_streamer_path(user["user_id"])


# ============= FOLLOWERS SIDEBAR =============

@api_router.get("/my/following")
async def list_my_following(limit: int = 20, offset: int = 0, user: dict = Depends(get_current_user)):
    """Who the current user follows, live streamers first."""
    follows = await db.follows.find({"follower_id": user["user_id"]}, {"_id": 0, "following_id": 1}).to_list(1000)
    ids = [f["following_id"] for f in follows]
    if not ids:
        return {"total": 0, "items": []}
    
    users_docs = await db.users.find(
        {"user_id": {"$in": ids}},
        {"_id": 0, "password_hash": 0, "stream_key": 0}
    ).to_list(1000)
    
    # Enrich with live stream info
    for u in users_docs:
        stream = await db.streams.find_one(
            {"user_id": u["user_id"], "is_live": True, "broadcasting": True},
            {"_id": 0, "stream_id": 1, "game_name": 1, "title": 1, "viewer_count": 1}
        )
        if stream:
            u["is_live"] = True
            u["active_stream_id"] = stream.get("stream_id")
            u["game_name"] = stream.get("game_name") or ""
            u["viewer_count"] = stream.get("viewer_count", 0)
        else:
            u["is_live"] = False
    
    # Live first, then alphabetical
    users_docs.sort(key=lambda x: (not x.get("is_live"), (x.get("display_name") or x.get("username") or "").lower()))
    total = len(users_docs)
    paged = users_docs[offset: offset + limit]
    return {"total": total, "items": paged, "offset": offset, "limit": limit}


# ============= ADMIN OTHER SETTINGS =============

@api_router.get("/admin/other-settings")
async def admin_get_other_settings(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    cfg = await db.admin_config.find_one({"type": "other_settings"}, {"_id": 0})
    if not cfg:
        return {"type": "other_settings", "achievements_enabled": True, "path_enabled": True}
    return cfg


@api_router.put("/admin/other-settings")
async def admin_save_other_settings(request: Request, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    body = await request.json()
    doc = {
        "type": "other_settings",
        "achievements_enabled": bool(body.get("achievements_enabled", True)),
        "path_enabled": bool(body.get("path_enabled", True)),
        "updated_at": datetime.now(timezone.utc),
    }
    await db.admin_config.update_one({"type": "other_settings"}, {"$set": doc}, upsert=True)
    return {"message": "Other settings saved", **{k: v for k, v in doc.items() if k != "updated_at"}}


@api_router.get("/config/features")
async def public_feature_flags():
    """Public — exposes feature toggles to frontend."""
    cfg = await db.admin_config.find_one({"type": "other_settings"}, {"_id": 0})
    if not cfg:
        return {"achievements_enabled": True, "path_enabled": True}
    return {
        "achievements_enabled": cfg.get("achievements_enabled", True),
        "path_enabled": cfg.get("path_enabled", True),
    }


# ============= STREAMER AD OPT-OUT =============

@api_router.get("/my/ad-opt-out")
async def get_my_ad_opt_out(user: dict = Depends(get_current_user)):
    cfg = await db.streamer_ad_prefs.find_one({"user_id": user["user_id"]}, {"_id": 0})
    return {"opt_out": bool(cfg and cfg.get("opt_out"))}


@api_router.put("/my/ad-opt-out")
async def put_my_ad_opt_out(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    await db.streamer_ad_prefs.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"user_id": user["user_id"], "opt_out": bool(body.get("opt_out", False)), "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return {"message": "Updated", "opt_out": bool(body.get("opt_out", False))}


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
    try:
        init_storage()
        logger.info("Object storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed: {e}")

@app.on_event("shutdown")
async def shutdown():
    client.close()
