# Backend Routes Package

This package is the staging area for the gradual migration of the
~6,000-line monolithic `server.py` into focused router modules.

## Migration pattern (factory-based, no circular imports)

Each route module exposes a `build_router(...)` factory that takes shared
dependencies as keyword arguments and returns a configured
`fastapi.APIRouter`. The main `server.py` then wires the router up:

```python
# routes/foo.py
from fastapi import APIRouter, Depends

def build_router(*, db, get_current_user, ...):
    router = APIRouter()

    @router.get("/foo")
    async def get_foo(user: dict = Depends(get_current_user)):
        return await db.foo.find_one({"_id": 0})

    return router
```

```python
# server.py
from routes.foo import build_router as _build_foo_router

api_router.include_router(
    _build_foo_router(db=db, get_current_user=get_current_user)
)
```

If a route module needs a helper that is defined later in `server.py`
(e.g. `_send_email`), pass it lazily as a `lambda *a, **kw: helper(*a, **kw)`.

## Already migrated

| Module                  | Endpoints                                                      |
| ----------------------- | -------------------------------------------------------------- |
| `admin_updates.py`      | `/admin/updates/{check,apply,rollback,status,history}`         |

## Suggested next migrations (P1)

In rough order of independence (least coupled first):

1. `auth.py`        — `/auth/*` (~600 lines in server.py)
2. `categories.py`  — `/categories/*`
3. `follows.py`     — `/follows/*`
4. `raids.py`       — `/streams/{id}/raid`, `/raids/recent`
5. `donations.py`   — `/donations/*`
6. `subscriptions.py` — `/subscriptions/*`, `/streamers/{id}/tiers`
7. `chat.py`        — `/streams/{id}/chat/*`
8. `streams.py`     — `/streams/*`
9. `admin_*.py`     — split the admin sections by domain
10. `payouts.py`    — Stripe Connect + payout settings + sweep

Common shared deps to thread through factories: `db`, `chat_manager`,
`logger`, `get_current_user`, plus a handful of helpers
(`_send_email`, `_get_admin_config`, `_to_iso`, etc.).
