# Admin Account — Creation & Management

## How the admin account is seeded

On every backend boot, the FastAPI app runs a **seed step** that looks for a
user with the email in `ADMIN_EMAIL`. If none exists it creates one with:

- `role: "admin"`
- `email_verified: True`
- `password_hash` = bcrypt(`ADMIN_PASSWORD`)

Both values are read from `deploy/.env`:

```env
ADMIN_EMAIL=admin@streamvault.local
ADMIN_PASSWORD=CHANGE_ME_Strong_Password!
```

> ⚠️ **Change `ADMIN_PASSWORD` before the first boot.** The seed only creates
> the account once — changing `.env` after that does NOT update the password.
> Use the flow below to rotate the password on a live deployment.

## First login

1. Browse to `https://$DOMAIN/auth`.
2. Enter the `ADMIN_EMAIL` + `ADMIN_PASSWORD` you put in `.env`.
3. You'll be redirected to the home page — visit `https://$DOMAIN/admin` to
   open the admin panel.

From the admin panel you can:

- Configure **SMTP** (`Admin → Email settings`) to enable email verification,
  password reset, welcome emails, and achievement notifications.
- Customize **Email templates** (`Admin → Email templates`).
- Toggle **Automated payouts** and configure **Auto-payout scheduling**.
- Manage the **Monetization** ad network / CPM table.
- Upload and review **Withdrawal requests**.
- Review **Other settings** (achievements / streamer path toggles).

## Change the admin password on a live server

```bash
sudo bash /opt/streamvault/deploy/scripts/reset-admin.sh
```

The script prompts for a new email + password, connects to the running `sv-mongo`
container, and updates the bcrypt hash in place. No restart required.

## Promote an existing user to admin

```bash
docker exec -i sv-backend python - <<'PY'
import os, asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = client[os.environ['DB_NAME']]
    res = await db.users.update_one(
        {"email": "user@example.com"},           # ← change me
        {"$set": {"role": "admin", "email_verified": True}},
    )
    print("matched:", res.matched_count, "modified:", res.modified_count)

asyncio.run(main())
PY
```

## Revoke admin

Same command, replace `"admin"` with `"user"`.

## Losing admin access

Worst-case recovery (no shell, no valid admin):

1. SSH to the server.
2. Run `sudo bash /opt/streamvault/deploy/scripts/reset-admin.sh` — it will
   **upsert** the account, so even if the user doesn't exist it gets created.

## Security checklist

- [ ] `ADMIN_PASSWORD` is a strong password you rotated before first boot.
- [ ] `JWT_SECRET` is a fresh `openssl rand -hex 48` value (never the placeholder).
- [ ] SMTP is configured so password-reset works if you ever forget.
- [ ] `.env` is `chmod 600` (installer does not do this automatically).
- [ ] MongoDB port is **not** exposed publicly (default compose keeps it on the
      internal docker network only — don't add a `ports:` mapping to `mongo`).
