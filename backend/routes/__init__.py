"""Route modules.

Each module exposes a `build_router(...)` factory that takes shared
dependencies (db, helpers, auth deps) and returns a configured
``fastapi.APIRouter`` ready to be mounted under the main /api router.

This keeps the route modules import-cycle-free with the (still large)
``server.py`` while we incrementally migrate sections out.
"""
