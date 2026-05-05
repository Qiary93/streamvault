# DramaroSub License Server

A complete license-selling website for self-hosted software. Customers register,
buy licenses through Stripe, bind them to their server IP, and self-service their
account. The product (StreamVault) pings this server every 24 hours to validate.

**Live domain:** https://license.stream-vault.eu (configurable in `backend/config.py`)

---

## ⚙️ The single config file

**Everything you'll want to change lives in `backend/config.py`.**

Open that file and you can edit:

- ✅ **Stripe keys** — `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` (loaded from `.env`)
- ✅ **Domain** — `LICENSE_SERVER_DOMAIN` (default `license.stream-vault.eu`)
- ✅ **All prices** — `PRODUCTS` dict (Basic / Pro / Enterprise)
- ✅ **IP-change limit** — `IP_CHANGE_LIMIT_PER_MONTH` (default 3)
- ✅ **License key prefix** — `LICENSE_KEY_PREFIX` (default `DSB-`)
- ✅ **JWT lifetime** — `ACCESS_TOKEN_TTL_MINUTES`, `REFRESH_TOKEN_TTL_DAYS`
- ✅ **Admin email for revenue alerts** — `ADMIN_NOTIFY_EMAIL`
- ✅ **CORS origins** — for the marketing/customer site
- ✅ **Trial period** (if you ever want to add one) — `TRIAL_DAYS`

Edit, save, restart the backend. No database migration needed — prices update on
the fly because we use Stripe's `price_data` (dynamic prices), not Stripe Price IDs.

---

## 🚀 Quick start (one command on a fresh VPS)

```bash
# 1. Log in to your domain registrar and add this DNS record
#    (replace VPS-PUBLIC-IP with your actual server IP):
#
#       Type: A
#       Name: license                        ← the subdomain
#       Host: license.stream-vault.eu
#       Value: VPS-PUBLIC-IP
#       TTL: 300
#
# 2. SSH into your Ubuntu 24.04 VPS and clone this repo
git clone https://github.com/YOUR-USER/stream-vault-license.git
cd stream-vault-license

# 3. Run the installer (replace with your real email)
sudo bash scripts/install.sh license.stream-vault.eu you@yourmail.com
```

The installer will:
1. Install Docker + certbot if missing
2. **Verify DNS** — if `license.stream-vault.eu` doesn't resolve to this VPS, it prints the exact A record to create and exits cleanly
3. Open ports 80 / 443 in UFW
4. Generate fresh JWT + Mongo secrets into `.env`
5. Template `nginx.conf` with your domain
6. Issue a Let's Encrypt SSL cert
7. Run `docker compose up -d`

**Total time: about 3 minutes** once DNS is pointed.

After install, edit `.env` to add your Stripe keys, then:

```bash
docker compose --env-file .env restart backend
```

---

## 🌐 Changing the domain later

Just re-run `scripts/install.sh` with the new domain:

```bash
sudo bash scripts/install.sh license.newdomain.com you@yourmail.com
```

The script is idempotent — it re-templates nginx, re-issues SSL for the new domain,
preserves your database, and updates only the fields in `.env` that depend on the
domain (`FRONTEND_URL`, `SMTP_FROM`). Your prices and secrets stay put.

---

## 📁 Project layout

```
license-server/
├── backend/              FastAPI + Motor (MongoDB) — the API
│   ├── config.py         ⭐ All your knobs (prices, domain, Stripe, etc.)
│   ├── server.py         App entrypoint
│   ├── auth.py           JWT + bcrypt
│   ├── models.py         Pydantic models
│   ├── db.py             Motor client
│   ├── license_keys.py   Key generation + validation logic
│   └── routes/           One module per concern
│       ├── auth.py
│       ├── products.py
│       ├── checkout.py
│       ├── webhook.py
│       ├── licenses.py
│       └── validate.py   ← the endpoint StreamVault installs ping
├── frontend/             React 19 + Tailwind + shadcn/ui
│   ├── src/
│   │   ├── App.js
│   │   ├── pages/
│   │   │   ├── HomePage.jsx       Marketing description (the sales copy)
│   │   │   ├── PricingPage.jsx
│   │   │   ├── LoginPage.jsx
│   │   │   ├── RegisterPage.jsx
│   │   │   ├── DashboardPage.jsx  My licenses + IP binding
│   │   │   └── CheckoutSuccessPage.jsx
│   │   └── components/
│   └── package.json
├── docker-compose.yml    All-in-one: mongo + backend + frontend + nginx
├── nginx.conf            Reverse proxy + SSL
└── .env.example
```

---

## 🔑 What customers see

### 1. Homepage (`/`)
Full marketing description of StreamVault — features, pricing teaser, FAQ.

### 2. Pricing (`/pricing`)
Three tiers (Basic one-time, Pro monthly, Enterprise monthly). Click → checkout.

### 3. Register / Login (`/register`, `/login`)
Standard email + password auth (JWT in httpOnly cookie).

### 4. Dashboard (`/dashboard`)
- All licenses they own
- Current bound IP per license
- "Change IP" button (max 3 changes per 30 days, configurable)
- Subscription status (active / cancelled / past_due)
- Download / copy license key
- Manage Stripe subscription (cancel, update card)

### 5. Checkout (`/checkout/:product_id`)
Redirects to Stripe Checkout (hosted page). Returns to `/checkout/success?session_id=…`
which polls payment status and shows the new license key.

---

## 🔐 What StreamVault installs do

Every StreamVault install has this in `/app/backend/.env`:

```
STREAMVAULT_LICENSE_KEY=DSB-XXXXX-XXXXX-XXXXX-XXXXX
LICENSE_SERVER_URL=https://license.stream-vault.eu
```

The buyer-side module `/app/backend/license_manager.py` (in the StreamVault repo,
**not** this repo) pings `POST /api/license/validate` every 24 hours.

If the license is valid → site runs normally. If it's revoked / expired / IP
mismatched → admin panel locks down with a "Renew your license" banner. Streaming
keeps working — we never break the live product, only gate paid features.

---

## 💵 How money flows

1. Customer clicks "Buy Pro" on `/pricing`
2. Backend creates a Stripe Checkout Session (subscription mode, dynamic price)
3. Customer pays on Stripe's hosted page
4. Stripe sends a webhook to `POST /api/webhook/stripe`
5. Backend's webhook handler:
   - Verifies the Stripe signature
   - Creates a `licenses` record with a fresh key
   - Updates `payment_transactions` to `paid`
6. Customer is redirected to `/checkout/success?session_id=...`
7. Frontend polls `/api/checkout/status/{session_id}` until `paid`
8. License key is shown — customer copies it into their StreamVault `.env`

The money lands directly in **your** Stripe account (the one whose secret key is
in `.env`). You never touch the cash flow.

---

## 🛡️ Security notes

- All prices are server-side. Frontend cannot manipulate amount.
- Stripe webhook signature is verified on every event.
- Passwords are bcrypt-hashed, never logged.
- JWT in httpOnly cookies (no localStorage tokens).
- `payment_transactions` is the source of truth — webhook + polling both write to it.
- License keys are 25-char base32, prefixed (e.g. `DSB-A2K9F-7XW3R-PQM4D-NHJV8`),
  generated with `secrets.token_hex` (cryptographically random).

---

## 📦 Pushing to your own GitHub repo

```bash
cd /app/license-server
git init
git add .
git commit -m "Initial commit — DramaroSub license server"
git branch -M main
git remote add origin git@github.com:YOUR-USER/stream-vault-license.git
git push -u origin main
```

This folder is fully self-contained — no imports from outside it.

---

## 🧪 Run locally for development

```bash
# Backend
cd backend
pip install -r requirements.txt
cp .env.example .env  # edit
uvicorn server:app --reload --port 8002

# Frontend
cd frontend
yarn install
yarn start
```

Frontend runs on `:3001`, backend on `:8002`. Edit `frontend/.env` to point at
the backend URL.

---

## 🚦 Roadmap (post-MVP)

- [ ] Email notifications on license issued / expired / IP changed
- [ ] Admin panel for you (refunds, license revocation, customer support)
- [ ] Coupon codes (`?coupon=BLACKFRIDAY30`)
- [ ] Affiliate program with referral tracking
- [ ] Annual subscription tier with 2-month discount
- [ ] Self-service refund request (within 14 days)
- [ ] Webhooks out (Discord/Slack on every sale)

---

Built by Qiary93. License: All rights reserved (this is your business — keep it private).
