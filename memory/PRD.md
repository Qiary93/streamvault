# StreamVault — Product Requirements Document (PRD)

## Original Problem Statement
Create a livestream website like kick.com featuring real-time video streaming (LiveKit/WebRTC), live WebSocket chat, streamer profiles, VOD recording, custom tipping/donations, subscription tiers, and an admin panel.

Latest feature set (Feb 2026):
- Revenue analytics charts (daily/weekly/monthly trends)
- Stripe Connect (Custom accounts) for automated payouts to streamers' bank accounts, with ON/OFF admin toggle
- Ad-based monetization system (pay-per-view ads on live streams + VODs) with:
  - Admin zone for ad activation + ad-code management
  - CPM pricing table per placement (live pre/mid-roll, VOD pre/mid-roll)
  - Streamer-side Monetization section showing ad earnings
  - Admin-side Monetization section showing platform + streamer earnings and top earners

## Tech Stack
- Backend: FastAPI, Motor (MongoDB), LiveKit SDK, Stripe Python SDK 15.x, emergentintegrations
- Frontend: React + Tailwind + shadcn/ui, Recharts, Phosphor icons, livekit-components-react
- Cloud: LiveKit Cloud, Stripe, Wasabi/S3, Emergent object storage

## What's Implemented

### Feb 2026 — Subscriber emotes, Streamer emote upload, Chat settings, Clips, Stripe Connect webhook, Kick categories
- **Kick-style categories** — seed_data now seeds 40+ Kick.com categories with `popularity` score, auto-cleans stale ones. `GET /api/categories?popular=true&limit=12` sorts by (live_stream_count, popularity).
- **HomePage** — section renamed to "Top 12 Popular Categories" and fetches the top 12.
- **20 subscriber-only emotes** — built-in blue :svBlueFire: / :svBlueHeart: / etc. exposed via `GET /api/emotes/subscriber` and surfaced in a new "Sub" tab inside `ChatEmojiPicker` (locked unless the viewer is subscribed to the current streamer).
- **Streamer custom emote upload** — `POST/GET/PUT/DELETE /api/my/emotes`, max 20/streamer, each with `subscribers_only` flag. UI: `EmojiUploadSection.jsx` in Dashboard.
- **Chat settings** — `GET/PUT /api/my/chat-settings` + public `GET /api/users/{id}/chat-settings`. UI: `ChatSettingsSection.jsx` (chat on/off toggle, rules textarea, Save button). ChatBox shows overlays: **chat-disabled-overlay** or **chat-rules-overlay** (accept-once, persisted via localStorage per stream).
- **Clips** — `POST /api/streams/{id}/clip` with title + timestamp + captured thumbnail dataURL. `GET /api/streams/{id}/clips` and `GET /api/my/clips`.
- **Stream player new controls** — PiP button (uses `<video>.requestPictureInPicture`), Clip button (captures frame + creates clip record), Theatre mode toggle (hides chat sidebar, expands video). Keyboard shortcuts: **C** (clip), **T** (theatre), **P** (PiP).
- **Stripe Connect webhook** — `POST /api/webhook/stripe/connect` handles `account.updated`, `payout.paid`, `payout.failed` with full signature verification when `STRIPE_CONNECT_WEBHOOK_SECRET` env var is set (dev mode accepts any JSON). Triggers streamer notifications on verification and payout events.

### Feb 2026 — Feature release (Revenue analytics, Stripe Connect, Ad Monetization)
- **Revenue analytics** — backend `GET /api/my/revenue/analytics?period=daily|weekly|monthly` aggregates donations+subscriptions+ad earnings into time-bucketed series. Frontend `RevenueAnalyticsChart.jsx` renders via Recharts (Line + Bar toggle) in Dashboard.
- **Stripe Connect Custom onboarding** — backend endpoints `POST /api/my/stripe-connect/create`, `GET /api/my/stripe-connect/status`, `DELETE /api/my/stripe-connect`. Frontend `StripeConnectSection.jsx` collects name, DOB, address, bank (routing/account or IBAN) + TOS and creates a Custom account via Stripe SDK with bank account token attached as external account.
- **Admin payout settings toggle** — `GET/PUT /api/admin/payout-settings` (automated_enabled, platform_fee_percent). Toggle lives inside WithdrawRequests section. When ON, approving a withdrawal calls `stripe.Transfer.create` + `stripe.Payout.create` on the connected account; when OFF, approval stays manual.
- **Ad monetization** — `GET/PUT /api/admin/ad-settings` (enabled, revenue_share_percent, cpm_rates per placement, ad_slots with HTML/video/image creatives). `GET /api/ads/active?placement=…` (public), `POST /api/ads/impression` (30s dedupe per viewer+slot, credits streamer+platform based on CPM/1000), `GET /api/my/ad-earnings`, `GET /api/admin/ad-earnings` (top streamers).
- **Frontend Admin Panel** — `AdminMonetization.jsx` component: platform-ads on/off toggle, CPM table (4 placements), revenue share input, ad slot editor (HTML/video URL/image URL), top earners summary.
- **Frontend Dashboard** — `MonetizationSection.jsx` (impressions + earnings by placement) + `RevenueAnalyticsChart.jsx` + `StripeConnectSection.jsx`.
- **Ad playback** — `AdPlayer.jsx` renders a pre-roll overlay on StreamPage (live_pre_roll) and VODDetailPage (vod_pre_roll). Supports HTML ad codes (with script execution), video URL, or image URL with click-through. Records one impression per viewer per slot per 30s.

### Previously implemented
- LiveKit Cloud + OBS WHIP ingress
- WebSocket chat with moderation + emoji picker
- Broadcast-gating visibility
- VOD recording via Wasabi/S3
- Profile avatar & cover photo uploads
- Stream tags, HTML descriptions, thumbnail uploads
- Dynamic subscription tiers + custom donations via Stripe
- Revenue tracking + manual withdrawals
- Admin: Site settings + S3 config + Withdrawal management

## Data Models

### New collections (Feb 2026)
- `stripe_connect_accounts`: `{user_id, stripe_account_id, country, currency, holder_name, bank_last4, verification_status, payouts_enabled, charges_enabled, currently_due, …}`
- `ad_impressions`: `{impression_id, stream_id, streamer_id, slot_id, placement, cpm, streamer_earned, platform_earned, viewer_key, created_at}`
- `admin_config` with new types: `payout_settings`, `ad_settings`

### Existing
- `users`, `streams`, `donations`, `subscriptions`, `withdrawals`, `streamer_tiers`, `recordings`, `chat_messages`, `notifications`, `admin_config` (site_settings, s3_storage)

## Key API Endpoints (new)
- `GET/PUT /api/admin/payout-settings`
- `GET/PUT /api/admin/ad-settings`
- `GET /api/admin/ad-earnings`
- `GET /api/my/stripe-connect/status`
- `POST /api/my/stripe-connect/create`
- `DELETE /api/my/stripe-connect`
- `GET /api/ads/active?placement=<placement>`
- `POST /api/ads/impression`
- `GET /api/my/ad-earnings`
- `GET /api/my/revenue/analytics?period=daily|weekly|monthly`

## Test Credentials
- See `/app/memory/test_credentials.md`

## Roadmap
### P1 (next)
- Seed live streams + revenue data for fuller e2e Connect/ad tests
- Stripe webhook handler for `account.updated`, `payout.paid`, `payout.failed`
- Use IP + User-Agent hashing as a secondary dedupe key for ad impressions
- Fix weekly bucket sorting for ISO year boundaries (edge case)

### P2 (later)
- Stream sorting options (by viewers, newest)
- Autocomplete for game names
- Split `server.py` into routers (monetization, stripe, admin)
- CSP/security audit of HTML ad code injection

## Backlog
- Real ad network integration (Google Ad Manager / IMA SDK)
- Payout scheduling (daily/weekly auto-sweeps)
- Streamer-level opt-out toggle for ads
- Ad analytics dashboard (CTR, fill-rate)
