# StreamVault — PRD

## Original Problem Statement
Build a Kick.com-style livestream platform: real-time video (LiveKit/WebRTC), WebSocket chat, streamer profiles, VOD recording, custom tipping/donations, subscription tiers, admin panel. Plus incremental feature releases (revenue analytics, Stripe Connect payouts, ad monetization, emotes, chat moderation, achievements, streamer path, real-time chat rules sync, VAST ads, etc.).

## Tech Stack
- Backend: FastAPI, Motor (MongoDB), LiveKit SDK, Stripe 15.x (incl. Connect Custom + webhooks), emergentintegrations
- Frontend: React + Tailwind + shadcn/ui + Recharts + Phosphor icons + livekit-components-react
- Cloud: LiveKit Cloud, Stripe, Wasabi/S3, Emergent object storage

## What's Implemented

### Feb 2026 — IMA SDK, Level-up confetti, Profile feed, Leaderboards, Game autocomplete, SSRF hardening
- **SSRF-hardened VAST resolver** — `/api/ads/vast/resolve` now blocks private / loopback / link-local / multicast / reserved IP addresses (including metadata `169.254.169.254`), rejects non-http(s) schemes, and revalidates redirect targets.
- **Google IMA SDK ad type** — new `ad_type='ima'` in admin monetization. `AdPlayer.jsx` lazy-loads `ima3.js` and uses `AdsLoader` + `AdsManager` for full VAST/VPAID/adaptive-streaming/companion support.
- **Level-up confetti + notifications + auto-post to profile feed** — Backend helper `_detect_and_notify_grade_change` detects grade improvements via a `user_grade_cache` collection, inserts a `level_up` notification, and auto-posts to `profile_feed`. Frontend `LevelUpListener` (mounted globally) polls achievements + unread notifications every 15s and fires `canvas-confetti` + a sonner toast when a new grade unlocks.
- **Profile Feed** — `GET /api/users/{id}/feed` (public), `POST /api/my/feed`, `DELETE /api/my/feed/{id}`. Own-profile input on `ProfilePage`. Level-up posts render with a trophy icon.
- **Top-donor leaderboards** — `GET /api/leaderboard/donors?streamer_id=X&period=all|month|week` with rank, avatar, verified grade badge, total amount, donation count. Streamer profile pages show a `DonorsLeaderboard` panel. Also `/leaderboard/subscribers` for top streamers/subscribers.
- **Games autocomplete** — `GET /api/games/search?q=...` from a curated 70+ popular titles list. Dashboard stream-setup Game Name field now uses `GameNameAutocomplete` with keyboard navigation.
- **Notifications endpoint** — now supports `?unread=true` filter for efficient polling.

### Feb 2026 — Achievements, Path, Followers sidebar, Real-time chat sync, VAST ads, Ad opt-out, Admin Other Settings
- **Achievements** — 4 grades (Beginner/Intermediate/Advanced/Expert) with 3 missions each. Public `GET /api/users/{id}/achievements` + `GET /api/my/achievements`. Green triangle = done, red triangle = pending. Earning any grade awards a **Verified** badge next to the user's display name on profile.
- **Path to a perfect streamer** — Dashboard section (under Recent Donations) showing 4 streamer missions (50 subs, 500 followers, 300 OBS hours, 500 unique chatters) over last 12 months. `GET /api/my/streamer-path`.
- **Recommended sidebar (home)** — filters to `broadcasting=true` + `is_live=true` only, shows a green dot, viewer count, and game name below the streamer name. `GET /api/recommended` returns enriched objects.
- **Left sidebar** — "Categories" section replaced with "Followers (N)" listing users you follow. Show more / Show less (+10 / reset to 10). Live followers are sorted first with green dot + viewer count + game name. `GET /api/my/following`.
- **Real-time chat rules sync** — when a streamer saves chat settings, the backend broadcasts `chat_settings_updated` to the live chat WebSocket. ChatBox re-fetches rules and forces re-acceptance on rule change.
- **Chat moderation additions** — `followers_only`, `subscribers_only` toggles enforce in the WS chat path. `restricted_words` list with `restricted_words_mode` = `filter` (replace with `***`) or `block` (reject the message entirely).
- **VAST ads** — new ad type `vast` with `vast_url` field. Platform fetches the VAST XML server-side via `GET /api/ads/vast/resolve` (basic VAST 2/3/4 MediaFile + Duration + ClickThrough parsing) and plays the returned creative.
- **Streamer ad opt-out** — `GET/PUT /api/my/ad-opt-out`. When `opt_out=true`, `GET /api/ads/active?stream_id=X` returns no ad for that streamer's streams/VODs.
- **Admin "Other Settings"** — above Monetization: toggles for `achievements_enabled` + `path_enabled`. Public `GET /api/config/features` exposes the toggles so frontend hides sections accordingly.
- **Category images** — replaced broken Pexels URLs (VALORANT, Slots & Casino, Rust, Dark and Darker, Tarkov, Stellar Blade).
- **Stripe Connect webhook** (previously added) — `/api/webhook/stripe/connect` handles `account.updated`, `payout.paid`, `payout.failed`.

### Earlier feature releases
- Revenue analytics charts (Recharts line/bar, daily/weekly/monthly)
- Stripe Connect Custom onboarding + automated payouts toggle in admin
- Ad monetization (CPM table, ad creatives admin editor, streamer dashboard Monetization section, ad impression tracking with 30s dedup)
- 20 blue subscriber-only emotes + streamer custom emote upload (max 20, subs-only flag)
- Per-streamer chat settings + rules accept-gate
- Clips (still-frame + marker MVP)
- Stream player Picture-in-Picture / Clip (C) / Theatre (T) controls + keyboard shortcuts
- LiveKit WebRTC, OBS WHIP ingress, VOD recording, subscription tiers, donations, revenue tracker + manual withdrawals
- Full Kick-style category seed (40+)
- HomePage "Top 12 Popular Categories"

## Key API Endpoints
### Newest (Feb 2026 — this release)
- `GET /api/recommended` (now returns only `broadcasting=true` live streams with viewer_count + game_name)
- `GET /api/my/following`
- `GET /api/my/achievements`, `GET /api/users/{id}/achievements`
- `GET /api/my/streamer-path`
- `GET/PUT /api/my/ad-opt-out`
- `GET /api/ads/active?placement=X&stream_id=Y` (respects streamer opt-out)
- `GET /api/ads/vast/resolve?url=X`
- `GET/PUT /api/admin/other-settings`
- `GET /api/config/features`
- `GET/PUT /api/my/chat-settings` (now with followers_only, subscribers_only, restricted_words, restricted_words_mode)

## Data Models — new/updated
- `chat_settings`: adds `followers_only`, `subscribers_only`, `restricted_words`, `restricted_words_mode`
- `admin_config` type `other_settings`: `{achievements_enabled, path_enabled}`
- `streamer_ad_prefs`: `{user_id, opt_out}`
- `stream_chatters`: `{streamer_id, user_id, first_seen, last_seen}` (tracks unique chatters for streamer Path mission)

## Test Credentials
See `/app/memory/test_credentials.md`

## Roadmap
### P1 (next)
- Rename minor admin/monetization testids to match spec
- Seed `broadcasting=true` demo streams so live-only UI flows are easier to demo
- SSRF hardening on `/ads/vast/resolve` (allow-list domains + block private IP ranges)
- Ensure `created_at` is always set on `follows` documents

### P2 (later)
- Split `server.py` (now 4000+ lines) into routers (achievements, streamer_path, followers, admin_other_settings, ad_optout, vast_resolver, chat, emotes, clips, monetization, webhooks)
- True last-30s MP4 clips via LiveKit Egress
- Full IMA SDK / Google Ad Manager integration (current VAST resolver covers most tags)
- Achievement progression notifications + email
- Leaderboards for top donators / subscribers

### Backlog
- Stream sorting (viewers, newest), game name autocomplete
- Payout scheduling (daily/weekly auto-sweeps)
- CSP review of HTML ad code injection surface

## Project Health
- Broken: None
- Mocked: None (real LiveKit + Stripe + S3 + MongoDB)
- Backend: 20/20 tests passed (iteration 6)
- Frontend: all UI sections rendered correctly (iteration 6)
