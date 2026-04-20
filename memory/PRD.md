# StreamVault — PRD

## Original Problem Statement
Build a Kick.com-style livestream platform: real-time video (LiveKit/WebRTC), WebSocket chat, streamer profiles, VOD recording, custom tipping/donations, subscription tiers, admin panel. Plus incremental feature releases (revenue analytics, Stripe Connect payouts, ad monetization, emotes, chat moderation, achievements, streamer path, real-time chat rules sync, VAST ads, etc.).

## Tech Stack
- Backend: FastAPI, Motor (MongoDB, tz_aware), LiveKit SDK, Stripe 15.x (incl. Connect Custom + webhooks), emergentintegrations
- Frontend: React + Tailwind + shadcn/ui + Recharts + Phosphor icons + livekit-components-react
- Cloud: LiveKit Cloud, Stripe, Wasabi/S3, Emergent object storage

## What's Implemented

### Feb 2026 — Global broadcasting sync, Timer TZ fix, Chat enhancements, SMTP expansion, Top Donors move
- **Global broadcasting sync** — new background task `broadcasting_sync_loop` polls LiveKit every 30s for *every* `is_live` stream and updates `broadcasting` / `broadcasting_started_at` / `broadcasting_ended_at` globally. Viewers now see streams in Recommended even when the streamer's dashboard is closed. Probe logic extracted to `_probe_livekit_broadcasting` (used by both the background loop and the existing `/check-broadcast` endpoint).
- **Live Timer TZ fix** — `AsyncIOMotorClient` now uses `tz_aware=True, tzinfo=timezone.utc`, so MongoDB datetimes return with UTC tzinfo and FastAPI serializes them with `+00:00`. Fixes the "Time Live" timer starting at 3h on clients in non-UTC zones.
- **Chat enhancements**
  - Inline subscriber tier badges in chat (custom `badge_url` if uploaded, otherwise a star icon).
  - Random per-user color for subscriber usernames (20-color palette, deterministic hash of user_id).
  - Donation announcement messages (`donation_alert`) with heart/like reactions (`POST /api/streams/{stream_id}/chat/{message_id}/heart`) and realtime `reaction_update` WS events.
  - Subscription announcement messages (`subscription_alert`) rendered as a purple banner with tier name + badge.
- **SMTP expansion**
  - **Password reset flow**: `POST /api/auth/forgot-password` + `POST /api/auth/reset-password` (60-minute token, enumeration-safe). New `/forgot-password` and `/reset-password` pages; "Forgot password?" link on login.
  - **Welcome email** sent on successful `POST /api/auth/verify-email` (first-time verification).
  - **Rate limit on `/auth/resend-verification`** (60-second cooldown, HTTP 429).
  - **Configurable email templates** via `admin_config` `type: "email_templates"` doc (`verification`, `welcome`, `password_reset`), with subject/html/text and `{display_name}`, `{verify_url}`, `{reset_url}`, `{site_url}`, `{email}` variables. New `GET/PUT /api/admin/email-templates` and `AdminEmailTemplates` panel inside AdminPage.
- **Top Donors moved** from `ProfilePage` to `DashboardPage` (now under "Recent Donations" section).

### Feb 2026 — SMTP / Email verification, Tier badges, Live Timer, 60 emote limit
- **Admin SMTP Settings** — `/api/admin/smtp-settings` GET/PUT + `/api/admin/smtp-test` endpoints.
- **Email verification flow** — register → verification token email → `/verify-email` → account active.
- **Subscription Tier Badges** — `POST/DELETE /api/my/tiers/{tier_id}/badge` (max 256KB). Badge shown in subscribe modal.
- **Emote limit raised** — 20 → 60 per streamer.
- **Dashboard "Time Live"** & **Stream Player broadcasting timer** — `LiveTimer.jsx`, resets when OBS disconnects.

### Feb 2026 — IMA SDK, Level-up confetti, Profile feed, Leaderboards, Game autocomplete, SSRF hardening
- SSRF-hardened VAST resolver.
- Google IMA SDK ad type, level-up confetti + notifications + auto-post to profile feed.
- Profile feed, top-donor leaderboards, games autocomplete.

### Earlier
- Achievements, Path, Followers sidebar, Real-time chat sync, VAST ads, Ad opt-out, Admin Other Settings, Stripe Connect automated payouts, IMA/VAST ad monetization, chat moderation (followers-only, subs-only, restricted words), custom emotes, PiP/Clip/Theatre controls, VOD recording, Category seed (40+).

## Key API Endpoints — Feb 2026 (this release)
- `POST /api/auth/forgot-password`, `POST /api/auth/reset-password`
- `GET /api/admin/email-templates`, `PUT /api/admin/email-templates`
- `POST /api/streams/{stream_id}/chat/{message_id}/heart` (toggle heart on a donation/chat message)
- Background task: `broadcasting_sync_loop` (no HTTP endpoint)

## Data Models — new/updated
- `users`: `password_reset_token`, `password_reset_expires`, `password_reset_sent_at`
- `admin_config` type `email_templates`: `{templates: {verification|welcome|password_reset: {subject, html, text}}}`
- `chat_messages` types: `donation_alert`, `subscription_alert`, `reaction_update` (WS only) — `donation_alert` has `amount`, `content`, `hearts`
- `chat_hearts`: `{message_id, stream_id, user_id, created_at}` (reaction ledger)

## Test Credentials
See `/app/memory/test_credentials.md`

## Roadmap

### P1
- Stream sorting (viewers, newest)
- Split `server.py` (now ~4900 lines) into routers

### P2
- True last-30s MP4 clips via LiveKit Egress
- Achievement progression notifications + email
- Payout scheduling (daily/weekly auto-sweeps)

## Project Health
- Broken: None
- Mocked: None (real LiveKit + Stripe + S3 + MongoDB)
