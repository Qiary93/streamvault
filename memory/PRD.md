# StreamVault — PRD

## Original Problem Statement
Build a Kick.com-style livestream platform: real-time video (LiveKit/WebRTC), WebSocket chat, streamer profiles, VOD recording, custom tipping/donations, subscription tiers, admin panel. Plus incremental feature releases (revenue analytics, Stripe Connect payouts, ad monetization, emotes, chat moderation, achievements, streamer path, real-time chat rules sync, VAST ads, raids, auto-payouts, etc.).

## Tech Stack
- Backend: FastAPI, Motor (MongoDB, tz_aware), LiveKit SDK, Stripe 15.x (incl. Connect Custom + webhooks), emergentintegrations, aiosmtplib
- Frontend: React + Tailwind + shadcn/ui + Recharts + Phosphor icons + livekit-components-react
- Cloud: LiveKit Cloud, Stripe, Wasabi/S3, Emergent object storage

## What's Implemented

### Feb 2026 — Raid, Sort, Auto-payouts, Achievement email, Rate-limit hardening, RichTextEditor fix
- **Bug fix — RichTextEditor typing backward**: removed `dangerouslySetInnerHTML` (which reset caret to pos 0 on every keystroke). Content is now synced imperatively via a `useEffect` guarded by `isInternalUpdateRef` so user typing isn't overwritten.
- **Stream sorting**: `GET /api/streams?sort=viewers|newest|oldest`. Browse page exposes 3 sort pills.
- **Raid feature (Twitch-style)**:
  - `POST /api/streams/{id}/raid` with `{target_username}`. Source streamer must be live+broadcasting; target must be live.
  - Emits WS `raid_outgoing` to source chat (10s countdown banner, logged-in viewers auto-redirect) and `raid_incoming` to target chat (welcome banner with raider count).
  - `GET /api/raids/recent` lists incoming/outgoing raids.
  - `RaidSection` on streamer Dashboard (disabled while offline).
- **Auto-payout scheduling**:
  - `auto_payout_sweep_loop` background task (checks every 30 min, runs per configured frequency).
  - `PUT /api/admin/payout-settings` extended with `auto_sweep_enabled`, `auto_sweep_frequency` (daily/weekly/monthly), `auto_sweep_min_amount`.
  - `POST /api/admin/payout-sweep/run` manual admin trigger. Sweeps every verified Stripe Connect account with balance ≥ min via `Transfer.create` + `Payout.create`.
  - New `AdminAutoPayoutSweep` panel in admin.
- **Achievement progression emails**: grade-up detection now dispatches `send_achievement_email` (uses new `achievement` template). Admin `AdminEmailTemplates` gained a 4th tab. Available vars: `display_name, new_grade, previous_grade, previous_from, site_url, email`.
- **Rate-limit hardening**:
  - `*_sent_at` timestamps for `/auth/resend-verification` and `/auth/forgot-password` now persisted BEFORE SMTP-enabled check — rate window enforced consistently across SMTP enable/disable toggles.
  - `/auth/reset-password` now enforces IP-based rate limit (5 attempts / 15 min, process-local dict).

### Feb 2026 — Global broadcasting sync, Timer TZ fix, Chat enhancements, SMTP expansion, Top Donors move
- Background task `broadcasting_sync_loop` syncs LiveKit broadcasting state globally every 30s.
- `Motor tz_aware=True` fixes the LiveTimer 3h offset (datetimes serialize with +00:00).
- Chat: inline tier badges, random subscriber username colors, `donation_alert` / `subscription_alert` WS events, heart reactions via `POST /api/streams/{id}/chat/{msg_id}/heart`.
- SMTP: password reset (`/auth/forgot-password`, `/auth/reset-password`), welcome email on verify, rate-limited resend, configurable email templates admin UI.
- Top Donors moved from ProfilePage → DashboardPage.

### Earlier (Jan–Feb 2026)
- SMTP email verification, tier badge uploads, 60-emote limit, Dashboard/Player LiveTimer.
- IMA SDK, level-up confetti, profile feed, top-donor leaderboards, game autocomplete, SSRF hardening.
- Achievements, Path, Followers sidebar, real-time chat sync, VAST ads, ad opt-out.
- Stripe Connect automated payouts, ad monetization, revenue analytics, gamification.
- LiveKit WebRTC + OBS WHIP, VOD recording, subscription tiers, donations, Picture-in-Picture / Clip / Theatre controls, chat moderation.

## Key API Endpoints (new this release)
- `GET /api/streams?sort=viewers|newest|oldest`
- `POST /api/streams/{stream_id}/raid`, `GET /api/raids/recent`
- `POST /api/admin/payout-sweep/run`
- `GET/PUT /api/admin/payout-settings` (new fields)

## Data Models (new/updated)
- `raids`: `{raid_id, source_user_id, source_stream_id, source_viewer_count, target_user_id, target_stream_id, created_at}`
- `admin_config` type `payout_settings`: adds `auto_sweep_enabled, auto_sweep_frequency, auto_sweep_min_amount, auto_sweep_last_run_at`
- `admin_config` type `email_templates`: adds `achievement` template
- `withdrawals` docs may have `source: "auto_sweep"` for sweep-created entries

## Test Credentials
See `/app/memory/test_credentials.md`

## Roadmap

### P1 (backlog)
- Split `server.py` (~5300 lines) into routers (auth, streams, chat, donations, subscriptions, raids, admin, email, payouts).
- Persist `_RESET_PWD_IP_HITS` in Redis/Mongo for multi-worker deployments.
- Raid staleness re-check before broadcasting to target.

### P2 (skipped per user)
- True last-30s MP4 clips via LiveKit Egress.

### P3 (nice-to-have)
- Raid preview thumbnail in outgoing banner.
- Admin audit log for sweeps + raids.
- Exponential backoff on auto-sweep errors per streamer.

## Project Health
- Broken: None
- Mocked: None (real LiveKit + Stripe + S3 + MongoDB + aiosmtplib)
- Backend tests: 25/25 passed (iteration 10)
- Frontend: 14/14 UI checks passed (iteration 10)
