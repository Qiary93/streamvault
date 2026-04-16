# StreamVault - Livestream Platform PRD

## Original Problem Statement
Create a livestream website like kick.com with full streaming infrastructure, chat, profiles, categories, follows, auth, donations, subscriptions, VOD, notifications, moderation tools, and admin panel.

## Architecture
- **Backend**: FastAPI + MongoDB (Motor async)
- **Frontend**: React + Tailwind + Shadcn/UI + Phosphor Icons
- **Auth**: JWT + Emergent Google OAuth
- **Payments**: Stripe (emergentintegrations)
- **Video**: LiveKit Cloud (wss://stream-x9ltpoe7.livekit.cloud)
- **Chat**: WebSocket (native FastAPI) with moderation
- **Recording**: LiveKit Egress → Wasabi S3 (admin-configurable)

## Implemented Features (April 2026)
### Phase 1: MVP
- Auth (JWT + Google OAuth), Stream discovery, Live chat, Follow system, Donations

### Phase 2: Advanced
- LiveKit Cloud video streaming, WebSocket chat, VOD/replay, Notifications, 5 Subscription tiers

### Phase 3: Moderation & Recording
- LiveKit URL verified: wss://stream-x9ltpoe7.livekit.cloud
- Admin panel with Wasabi S3 storage configuration
- LiveKit Egress recording (start/stop per stream)
- Ban user from chat (permanent), Unban
- Timeout user (1min/5min/10min)
- Slow mode (3s/5s/10s/30s)
- Mod role assignment (streamer assigns mods)
- Moderation panel in chat UI

## Backlog
### P1
- [ ] Emotes/badges system
- [ ] User settings page  
- [ ] Mobile responsive optimizations

### P2
- [ ] Clip creation
- [ ] Channel points/loyalty system
- [ ] Analytics dashboard for streamers
- [ ] Gifted subscriptions
