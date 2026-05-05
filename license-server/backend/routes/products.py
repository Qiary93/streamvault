"""Public products endpoint — driven by config.PRODUCTS."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException

from config import PRODUCTS
from models import ProductResponse

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=List[ProductResponse])
async def list_products():
    return [ProductResponse(**p) for p in PRODUCTS.values()]


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str):
    p = PRODUCTS.get(product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductResponse(**p)
