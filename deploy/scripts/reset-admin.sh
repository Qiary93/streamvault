#!/usr/bin/env bash
# reset-admin.sh — reset the seeded admin account's password.
# Run on the host (as root or docker group):  sudo bash deploy/scripts/reset-admin.sh
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$DEPLOY_DIR/.env"

read -r -p "New admin email [${ADMIN_EMAIL}]: " new_email
new_email=${new_email:-$ADMIN_EMAIL}
read -r -s -p "New admin password: " new_pw; echo
[[ ${#new_pw} -ge 8 ]] || { echo "password must be ≥ 8 chars"; exit 1; }

docker exec -i sv-backend python - <<PY
import os, asyncio, bcrypt
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = client[os.environ['DB_NAME']]
    pw_hash = bcrypt.hashpw("$new_pw".encode(), bcrypt.gensalt()).decode()
    res = await db.users.update_one(
        {"email": "$new_email"},
        {"\$set": {"password_hash": pw_hash, "role": "admin", "email_verified": True}},
        upsert=True,
    )
    print("matched:", res.matched_count, "modified:", res.modified_count, "upserted:", res.upserted_id)

asyncio.run(main())
PY

echo "Admin password updated. Log in at https://${DOMAIN}/auth"
