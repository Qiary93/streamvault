"""License-key generation + lookup helpers."""
from __future__ import annotations

import secrets
import string
import uuid

from config import LICENSE_KEY_GROUP_LEN, LICENSE_KEY_GROUPS, LICENSE_KEY_PREFIX

# Crockford's base32 — no I/L/O/U to avoid visual ambiguity in keys.
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _group(n: int) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(n))


def generate_license_key() -> str:
    """Return e.g. 'DSB-A2K9F-7XW3R-PQM4D-NHJV8'."""
    parts = [LICENSE_KEY_PREFIX] + [
        _group(LICENSE_KEY_GROUP_LEN) for _ in range(LICENSE_KEY_GROUPS)
    ]
    return "-".join(parts)


def new_license_id() -> str:
    return f"lic_{uuid.uuid4().hex[:12]}"
