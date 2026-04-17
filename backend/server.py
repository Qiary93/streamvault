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
async def get_categories():
    categories = await db.categories.find({}, {"_id": 0}).to_list(100)
    
    for cat in categories:
        count = await db.streams.count_documents({"category_id": cat["category_id"], "is_live": True, "broadcasting": True})
        cat["stream_count"] = count
    
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
    """Get 10 recommended streamers based on user interests or random."""
    current_user = await get_optional_user(request)
    
    streamers = []
    
    if current_user:
        # Get categories the user follows/watches
        follows = await db.follows.find({"follower_id": current_user["user_id"]}, {"_id": 0, "following_id": 1}).to_list(100)
        following_ids = [f["following_id"] for f in follows]
        
        # Get streamers the user doesn't follow yet, preferring active ones
        pipeline = [
            {"$match": {
                "user_id": {"$nin": following_ids + [current_user["user_id"]]},
                "role": {"$ne": "admin"}
            }},
            {"$sample": {"size": 10}},
            {"$project": {"_id": 0, "password_hash": 0, "stream_key": 0}}
        ]
        streamers = await db.users.aggregate(pipeline).to_list(10)
    
    if len(streamers) < 10:
        # Fill with random streamers
        existing_ids = [s["user_id"] for s in streamers]
        if current_user:
            existing_ids.append(current_user["user_id"])
        
        pipeline = [
            {"$match": {"user_id": {"$nin": existing_ids}, "role": {"$ne": "admin"}}},
            {"$sample": {"size": 10 - len(streamers)}},
            {"$project": {"_id": 0, "password_hash": 0, "stream_key": 0}}
        ]
        more = await db.users.aggregate(pipeline).to_list(10 - len(streamers))
        streamers.extend(more)
    
    # Attach active stream_id for live streamers
    for s in streamers:
        if s.get("is_streaming"):
            stream = await db.streams.find_one(
                {"user_id": s["user_id"], "is_live": True},
                {"_id": 0, "stream_id": 1}
            )
            if stream:
                s["active_stream_id"] = stream["stream_id"]
    
    return streamers

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
            
            # Check slow mode
            stream = await db.streams.find_one({"stream_id": stream_id}, {"_id": 0, "slow_mode": 1})
            slow_mode = stream.get("slow_mode", 0) if stream else 0
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
            
            message_doc = {
                "message_id": f"msg_{uuid.uuid4().hex[:12]}",
                "stream_id": stream_id,
                "user_id": user_id,
                "username": data.get("username", "Anonymous"),
                "display_name": data.get("display_name"),
                "avatar_url": data.get("avatar_url"),
                "content": str(data.get("content", ""))[:500],
                "type": data.get("type", "message"),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            await db.chat_messages.insert_one({**message_doc})
            message_doc.pop("_id", None)
            
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
