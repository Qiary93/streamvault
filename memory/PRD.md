# StreamVault — PRD

## Original Problem Statement
Build a Kick.com-style livestream platform: real-time video (LiveKit/WebRTC), WebSocket chat, streamer profiles, VOD recording, custom tipping/donations, subscription tiers, admin panel. Plus incremental feature releases (revenue analytics, Stripe Connect payouts, ad monetization, emotes, chat moderation, achievements, streamer path, real-time chat rules sync, VAST ads, raids, auto-payouts, etc.).

## Tech Stack
- Backend: FastAPI, Motor (MongoDB, tz_aware), LiveKit SDK, Stripe 15.x (incl. Connect Custom + webhooks), emergentintegrations, aiosmtplib
- Frontend: React + Tailwind + shadcn/ui + Recharts + Phosphor icons + livekit-components-react
- Cloud: LiveKit Cloud, Stripe, Wasabi/S3, Emergent object storage

## What's Implemented

### Feb 2026 — License Server installer nginx auto-fix bugfix
- **Root cause identified & fixed** for the `install.sh` "auto-fix" failure during coexist-mode install (license server alongside StreamVault):
  - The script prepended an ACME `default_server` block to `streamvault.conf.template`, then re-rendered it via `envsubst` to **`/etc/nginx/conf.d/default.conf`**.
  - But `nginx:alpine`'s entrypoint already renders `streamvault.conf.template` → **`/etc/nginx/conf.d/streamvault.conf`** (it strips only the trailing `.template`).
  - Result: both files coexisted → duplicate `limit_req_zone "api_zone"` directives → `nginx -t` failed with `"already bound to key"` → script reverted.
- **Fix** (`/app/license-server/scripts/install.sh`): write the re-rendered config to `streamvault.conf` (overwriting the original render), so only one config exists. Added an atomic `.new` + `mv` swap, plus `nginx -t` output is now surfaced on failure for easier debugging, and the original render is restored on revert.
- Reproduced + verified locally with a Docker-less `nginx -t` harness (`/tmp/repro2/test_dup.sh` reproduces, `/tmp/repro3/test_fix.sh` validates the fix).
- Repackaged `/app/frontend/public/stream-vault-license.tar.gz` (now contains the patched installer).

### Feb 2026 — Rate-limit persistence + Raid staleness re-check
- **`_RESET_PWD_IP_HITS` migrated to MongoDB** (`db.rate_limit_hits`) for multi-worker safety. Sliding-window count + a TTL index on `expires_at` (auto-cleanup), so the 5-attempts-per-15-min limit is now consistent across all uvicorn workers / pod restarts. The helper is now async and fails open on a Mongo blip (never blocks legit users).
- **Raid staleness re-check**: `POST /api/streams/{id}/raid` re-verifies the target is still `is_live && broadcasting` immediately before inserting the raid doc + broadcasting. Returns `409 Conflict` with a friendly message when the target went offline between the initial lookup and the broadcast (instead of the old behavior of redirecting hundreds of viewers to a dead stream).
- Pytest coverage in `/app/backend/tests/test_rate_limit_and_raid.py` (4/5 passing — 5th is an env-dependent skip).

### Feb 2026 — Auto-Updater UI completion + routes/ refactor scaffold
- **Admin Auto-Updater UI** (P0 from previous session): `AdminUpdatesPanel.jsx` now renders the full feature set the user requested:
  - "You're up to date" green block with the verified full SHA when `behind === 0` (`data-testid=updates-up-to-date`).
  - Parsed CHANGELOG snippet card (`data-testid=updates-changelog`) — pulled from `/api/admin/updates/check` `.changelog` field.
  - "Recent updates" history list (`data-testid=updates-history`) populated from `/api/admin/updates/history` with per-row Rollback buttons (`data-testid=updates-rollback-btn-<sha>`).
  - Rollback flow calls `POST /api/admin/updates/rollback` with the selected `previous_sha` and surfaces a `Rollback queued — host watcher fires within ~2s.` toast (mode-aware message added in `update_manager._enqueue_request`).
  - Auto-refreshes history + check after a queued job finishes.
  - Confirm dialog explains the destructive nature of rollback (DB restored from backup taken before that update).
  - Backend & frontend verified end-to-end by testing_agent_v3_fork iteration_11 (13/13 backend, all frontend checkpoints).
- **Backend `routes/` package scaffolded** for the long-running goal of splitting the ~6k-line `server.py`:
  - `/app/backend/routes/__init__.py`, `/app/backend/routes/README.md` document the factory-based migration pattern (no circular imports).
  - `/app/backend/routes/admin_updates.py` is the first migrated module — owns all 5 `/admin/updates/*` endpoints + the `_maybe_notify_update_outcome` SMTP hook. `server.py` now mounts it via `api_router.include_router(...)`.
  - `server.py` shrunk from 5,906 → 5,834 lines as a result. Migration roadmap (auth, streams, chat, donations, raids, admin_*, payouts) tracked in `routes/README.md`.

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
- Continue the `server.py` router-split refactor (admin_updates.py is the POC; see `/app/backend/routes/README.md` for the next-up list — auth, categories, follows, raids, donations, subscriptions, chat, streams, admin_*, payouts).

### P2 (skipped per user)
- True last-30s MP4 clips via LiveKit Egress.

### P3 (nice-to-have)
- Raid preview thumbnail in outgoing banner.
- Admin audit log for sweeps + raids.
- Exponential backoff on auto-sweep errors per streamer.

## Project Health
- Broken: None
- Mocked: None (real LiveKit + Stripe + S3 + MongoDB + aiosmtplib)
- Backend tests: 13/13 passed (iteration 11, admin auto-updater suite); 25/25 passed (iteration 10, full regression)
- Frontend: Updates panel verified end-to-end (iteration 11); 14/14 UI checks passed (iteration 10)
