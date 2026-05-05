"""DramaroSub License Server — FastAPI entrypoint."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import ADMIN_EMAIL, CORS_ORIGINS
from db import db, ensure_indexes
from expiry_worker import run_loop as expiry_loop
from routes.admin import router as admin_router
from routes.affiliates import router as affiliates_router
from routes.auth import router as auth_router
from routes.checkout import router as checkout_router
from routes.coupons import router as coupons_router
from routes.licenses import router as licenses_router
from routes.products import router as products_router
from routes.validate import router as validate_router
from routes.webhook import router as webhook_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("server")


async def _seed_admin() -> None:
    """If config.ADMIN_EMAIL matches an existing user, promote them to admin."""
    if not ADMIN_EMAIL:
        return
    res = await db.users.update_one(
        {"email": ADMIN_EMAIL.lower()},
        {"$set": {"is_admin": True}},
    )
    if res.modified_count:
        logger.info(f"Promoted {ADMIN_EMAIL} to admin")
    elif res.matched_count:
        logger.info(f"Admin {ADMIN_EMAIL} already promoted")
    else:
        logger.info(f"No user yet for ADMIN_EMAIL={ADMIN_EMAIL} — register that account, then restart.")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await ensure_indexes()
    await _seed_admin()
    asyncio.create_task(expiry_loop())
    logger.info("DramaroSub License Server ready")
    yield


app = FastAPI(title="StreamVault License Server", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(products_router)
app.include_router(checkout_router)
app.include_router(webhook_router)
app.include_router(licenses_router)
app.include_router(validate_router)
app.include_router(coupons_router)
app.include_router(affiliates_router)
app.include_router(admin_router)


@app.get("/api/healthz")
async def healthz():
    return {"ok": True}
