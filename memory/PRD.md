# StreamVault - Livestream Platform PRD

## Original Problem Statement
Create a livestream website like kick.com with live streaming + chat functionality, streamer profiles, categories, follow system, real streaming infrastructure, both JWT auth and Google social login, donations/tipping system, subscription tiers, VOD replay, and notifications.

## Architecture
- **Backend**: FastAPI (Python) with MongoDB (Motor async driver)
- **Frontend**: React with Tailwind CSS, Shadcn/UI, Phosphor Icons
- **Auth**: JWT (email/password) + Emergent Google OAuth
- **Payments**: Stripe via emergentintegrations library
- **Video Streaming**: LiveKit Cloud (WebRTC)
- **Real-time Chat**: WebSocket (native FastAPI)
- **Theme**: Electric Blue (#00E5FF) on Void Black (#05050A)

## What's Implemented (April 2026)
### Phase 1 (MVP)
- Full auth system (JWT + Google OAuth)
- Stream discovery (home, browse, categories, search)
- Live stream viewing with chat
- Follow/unfollow system with notifications
- Streamer dashboard (start/end stream)
- Stripe donation system (5 packages)
- User profiles, 8 categories, demo data

### Phase 2 (Current)
- LiveKit Cloud integration (token generation for streamer/viewer)
- WebSocket real-time chat (replaced polling)
- VOD/replay system with chat replay
- Notification system (follows, donations, subscriptions)
- 5 Subscription tiers ($4.99, $9.99, $24.99, $49.99, $100)
- Stream key display fix (now visible in dashboard)
- LiveKit streamer controls (camera, mic, screen share)

## Environment Variables
- LIVEKIT_API_KEY, LIVEKIT_API_SECRET, LIVEKIT_URL
- STRIPE_API_KEY (user provided)
- JWT_SECRET, ADMIN_EMAIL, ADMIN_PASSWORD
- MONGO_URL, DB_NAME

## Note on LiveKit URL
The LIVEKIT_URL is set to `wss://streamvault.livekit.cloud` as placeholder.
User needs to verify this matches their LiveKit Cloud project URL for video to connect.
Token generation works independently of the URL.

## Prioritized Backlog
### P1
- [ ] Verify/update correct LiveKit Cloud URL for video streaming
- [ ] Stream recording via LiveKit Egress
- [ ] Emotes/badges in chat
- [ ] User settings page

### P2
- [ ] Clip creation system
- [ ] Channel points/loyalty system
- [ ] Moderation tools (ban, timeout, slow mode)
- [ ] Analytics dashboard for streamers
- [ ] Mobile responsive optimizations
