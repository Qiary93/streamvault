#!/usr/bin/env bash
# reset-admin.sh — reset the seeded admin account's password (and optionally
# its username / display name). Run on the host:
#   sudo bash deploy/scripts/reset-admin.sh
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a; . "$DEPLOY_DIR/.env"; set +a

read -r -p "Admin email [${ADMIN_EMAIL}]: " new_email
new_email=${new_email:-$ADMIN_EMAIL}
read -r -p "Admin username (blank = keep current) [${ADMIN_USERNAME:-admin}]: " new_username
new_username=${new_username:-${ADMIN_USERNAME:-admin}}
read -r -p "Admin display name (blank = keep current) [${ADMIN_DISPLAY_NAME:-Admin}]: " new_display
new_display=${new_display:-${ADMIN_DISPLAY_NAME:-Admin}}
read -r -s -p "New admin password (min 8 chars, blank to keep current): " new_pw; echo

if [[ -n "$new_pw" && ${#new_pw} -lt 8 ]]; then
    echo "password must be at least 8 chars"; exit 1
fi

docker exec -i sv-backend python - <<PY
import os, asyncio, bcrypt, uuid, secrets
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone

NEW_EMAIL    = "$new_email"
NEW_USERNAME = "$new_username".lower()
NEW_DISPLAY  = "$new_display"
NEW_PW       = "$new_pw"

async def main():
    client = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = client[os.environ['DB_NAME']]
    
    set_doc = {
        "username": NEW_USERNAME,
        "display_name": NEW_DISPLAY,
        "role": "admin",
        "email_verified": True,
    }
    if NEW_PW:
        set_doc["password_hash"] = bcrypt.hashpw(NEW_PW.encode(), bcrypt.gensalt()).decode()

    existing = await db.users.find_one({"email": NEW_EMAIL})
    if existing:
        await db.users.update_one({"user_id": existing["user_id"]}, {"\$set": set_doc})
        print(f"Updated existing admin: {NEW_EMAIL} (@{NEW_USERNAME})")
    else:
        # Create a fully-populated admin user from scratch
        if not NEW_PW:
            print("ERROR: this email doesn't exist yet — password is required to create a new admin."); return
        uid = f"user_{uuid.uuid4().hex[:12]}"
        doc = {
            "user_id": uid,
            "email": NEW_EMAIL,
            "username": NEW_USERNAME,
            "display_name": NEW_DISPLAY or NEW_USERNAME,
            "password_hash": set_doc["password_hash"],
            "avatar_url": None, "bio": "Platform Administrator",
            "role": "admin",
            "follower_count": 0, "following_count": 0,
            "is_streaming": False,
            "stream_key": f"sk_{secrets.token_hex(16)}",
            "email_verified": True,
            "verification_token": None, "verification_sent_at": None,
            "created_at": datetime.now(timezone.utc),
        }
        await db.users.insert_one(doc)
        print(f"Created new admin: {NEW_EMAIL} (@{NEW_USERNAME})")

asyncio.run(main())
PY

echo "Done. Log in at https://${DOMAIN}/auth"
