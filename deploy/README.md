# StreamVault — Ubuntu 24.04 Deployment Package

Production-ready, single-command deployment of the entire StreamVault platform
(React frontend, FastAPI backend, MongoDB, Nginx reverse proxy, Let's Encrypt
auto-renewal) on a fresh Ubuntu 24.04 server.

## Contents

| Path | Purpose |
| --- | --- |
| `docker-compose.yml`              | Orchestrates mongo, backend, frontend, nginx, certbot |
| `Dockerfile.backend`              | FastAPI image (Python 3.11) |
| `Dockerfile.frontend`             | React build → Nginx static server |
| `.env.example`                    | All environment variables, documented |
| `nginx/streamvault.conf.template` | Reverse proxy + SSL + rate limiting + WebSocket |
| `nginx/ssl-params.conf`           | Mozilla intermediate TLS profile + OCSP stapling |
| `scripts/install.sh`              | One-shot installer (Docker, certs, stack, systemd) |
| `scripts/reset-admin.sh`          | Reset the admin password on a live container |
| `scripts/backup-mongo.sh`         | Dump MongoDB to `./backups/<timestamp>/` |

---

## 1. Prerequisites

- A fresh **Ubuntu 24.04 LTS** server (≥ 2 vCPU, ≥ 4 GB RAM, ≥ 20 GB disk).
- A **domain name** with an **A record** pointing to the server's public IP.
- Ports **80** and **443** open in your provider's firewall (UFW is configured
  automatically by the installer).
- SSH root access (or a sudo-capable user).

## 2. Quick start (5 minutes)

```bash
# As root (or via sudo) on a fresh Ubuntu 24.04 box:
git clone https://github.com/YOUR-ORG/streamvault.git /opt/streamvault
cd /opt/streamvault

# 1. Create your .env from the example
cp deploy/.env.example deploy/.env

# 2. Edit .env — at minimum set DOMAIN, LETSENCRYPT_EMAIL, JWT_SECRET, ADMIN_PASSWORD
#    Generate a strong JWT secret:
openssl rand -hex 48   # copy output into JWT_SECRET=
nano deploy/.env

# 3. Run the installer (installs Docker, issues TLS cert, builds images, starts everything)
sudo bash deploy/scripts/install.sh
```

When it finishes you'll see:

```
StreamVault is live — https://your-domain.example.com
Admin panel:   https://your-domain.example.com/admin
```

That's it.

---

## 3. Environment configuration

Every knob lives in `deploy/.env`. Copy `deploy/.env.example` and fill in your
values. The `.env.example` file has inline comments for every variable; the
short version:

### Required at first boot

| Variable | Notes |
| --- | --- |
| `DOMAIN`              | Public hostname (DNS must already resolve to this server). |
| `LETSENCRYPT_EMAIL`   | Email for cert expiry notifications + ACME account. |
| `JWT_SECRET`          | Long random secret — generate with `openssl rand -hex 48`. |
| `ADMIN_EMAIL`         | Seeded admin account. |
| `ADMIN_PASSWORD`      | Seeded admin password. Change immediately after first login. |
| `DB_NAME`             | Default `streamvault`. Leave as-is. |

### Optional — third-party integrations

All of these start empty; the app boots without them and the individual feature
stays disabled until you provide a key.

| Variable | Where to get it | Unlocks |
| --- | --- | --- |
| `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `LIVEKIT_URL` | https://cloud.livekit.io → Project Settings → Keys | OBS ingest, live video, VOD recording |
| `STRIPE_API_KEY`                     | https://dashboard.stripe.com/apikeys                        | Donations, subscriptions, Connect payouts |
| `STRIPE_CONNECT_WEBHOOK_SECRET`      | Dashboard → Developers → Webhooks → endpoint signing secret | Automated payout status updates |

Other integrations (SMTP, S3, ad networks) are configured **in the Admin UI**
at `https://$DOMAIN/admin` once you're logged in — those don't need to live
in `.env`.

After editing `.env`, apply changes with:

```bash
sudo systemctl restart streamvault
```

---

## 4. What the installer does

1. Verifies Ubuntu 24.04 and installs base packages.
2. Installs **Docker Engine + Compose plugin** from Docker's official apt repo.
3. Validates your `.env` (refuses to proceed with placeholder values).
4. Configures **UFW** to allow 22/80/443.
5. Warns if DNS for `DOMAIN` doesn't resolve to this server's public IP.
6. Issues a **Let's Encrypt certificate** via the HTTP-01 challenge (bootstrap
   nginx container on :80 → certbot webroot → shutdown bootstrap).
7. Builds the backend and frontend Docker images.
8. Brings the stack up with `docker compose up -d`.
9. Installs a **systemd unit** (`streamvault.service`) so the stack auto-starts
   on reboot.

---

## 5. Common operations

```bash
# View combined logs
docker compose -f deploy/docker-compose.yml logs -f

# Tail just the backend
docker compose -f deploy/docker-compose.yml logs -f backend

# Restart the stack (picks up .env changes)
sudo systemctl restart streamvault

# Stop the stack
sudo systemctl stop streamvault

# Pull latest code + rebuild images + restart
cd /opt/streamvault
git pull
sudo systemctl reload streamvault     # triggers `docker compose up -d --build`

# Reset the admin password
sudo bash deploy/scripts/reset-admin.sh

# One-off MongoDB backup
sudo bash deploy/scripts/backup-mongo.sh
```

---

## 6. SSL certificate auto-renewal

The `certbot` service in `docker-compose.yml` runs `certbot renew` every 12 h
and reloads nginx on success. No cron job required. To check status:

```bash
docker compose -f deploy/docker-compose.yml exec certbot \
    certbot certificates
```

## 7. Admin account

See [ADMIN_SETUP.md](./ADMIN_SETUP.md) for how the admin account is seeded
and how to change it.

## 8. Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Let's Encrypt issuance failed` | Ensure port 80 is open AND DNS A record points here. Re-run `install.sh`. |
| `502 Bad Gateway` on https://$DOMAIN | Check backend: `docker compose logs backend`. Most often missing `MONGO_URL` (shouldn't happen if you didn't edit docker-compose.yml). |
| Frontend shows stale build after code change | `sudo systemctl reload streamvault` to force rebuild. |
| Admin login says "Invalid email or password" | Run `deploy/scripts/reset-admin.sh`. |
| MongoDB eating disk | `docker compose -f deploy/docker-compose.yml exec mongo mongosh` → `db.oplog.rs.stats()` → compact if needed. |

---

## 9. Uninstall

```bash
sudo systemctl disable --now streamvault
docker compose -f /opt/streamvault/deploy/docker-compose.yml --env-file /opt/streamvault/deploy/.env down -v
rm /etc/systemd/system/streamvault.service
rm -rf /opt/streamvault
systemctl daemon-reload
```

`-v` also removes the MongoDB volume — skip it if you want to keep data.
