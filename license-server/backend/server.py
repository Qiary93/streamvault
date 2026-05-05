"""DramaroSub License Server — FastAPI entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import CORS_ORIGINS
from db import ensure_indexes
from routes.auth import router as auth_router
from routes.checkout import router as checkout_router
from routes.licenses import router as licenses_router
from routes.products import router as products_router
from routes.validate import router as validate_router
from routes.webhook import router as webhook_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("server")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await ensure_indexes()
    logger.info("DramaroSub License Server ready")
    yield


app = FastAPI(title="DramaroSub License Server", version="1.0.0", lifespan=lifespan)

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


@app.get("/api/healthz")
async def healthz():
    return {"ok": True}
