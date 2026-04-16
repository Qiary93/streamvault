# StreamVault - Livestream Platform PRD

## Original Problem Statement
Create a livestream website like kick.com with live streaming + chat functionality, streamer profiles, categories, follow system, real streaming infrastructure, both JWT auth and Google social login, and a donations/tipping system.

## Architecture
- **Backend**: FastAPI (Python) with MongoDB (Motor async driver)
- **Frontend**: React with Tailwind CSS, Shadcn/UI, Phosphor Icons
- **Auth**: JWT (email/password) + Emergent Google OAuth
- **Payments**: Stripe via emergentintegrations library
- **Theme**: Electric Blue (#00E5FF) on Void Black (#05050A)

## User Personas
1. **Viewer**: Browses streams, follows streamers, chats, donates
2. **Streamer**: Creates streams, manages dashboard, receives donations
3. **Admin**: Platform administrator

## Core Requirements
- User registration & login (JWT + Google OAuth)
- Stream discovery (home, browse, categories, search)
- Live stream viewing with real-time chat
- Follow/unfollow system
- Streamer dashboard (start/end stream, view stats)
- Donation system via Stripe
- User profiles

## What's Been Implemented (April 2026)
- Full backend API: auth, users, streams, categories, chat, donations, search, featured
- Full frontend: 10 pages (Home, Stream, Browse, Category, Profile, Auth, Dashboard, Search, DonationSuccess, AuthCallback)
- Components: Layout, Sidebar, Header, StreamCard, CategoryCard, ChatBox
- Auth context with JWT + Google OAuth
- Stripe donation checkout flow
- Seed data: 3 demo streamers, 8 categories, admin account
- Electric Blue dark theme with Outfit/Manrope fonts

## Prioritized Backlog
### P0 (Critical)
- [x] Authentication (JWT + Google)
- [x] Stream discovery & browsing
- [x] Live chat
- [x] Follow system
- [x] Donation system

### P1 (Important)
- [ ] Real-time chat via WebSocket (currently polling)
- [ ] Video streaming integration (WebRTC/HLS via LiveKit or similar)
- [ ] Stream recording/VOD system
- [ ] Notification system
- [ ] User settings page

### P2 (Nice to have)
- [ ] Emotes/badges in chat
- [ ] Stream tags/topics
- [ ] Clip creation
- [ ] Channel points/loyalty system
- [ ] Moderation tools
- [ ] Analytics dashboard for streamers

## Next Tasks
1. Integrate real video streaming (LiveKit/WebRTC)
2. WebSocket-based real-time chat
3. VOD/replay system
4. Notification system for follows and donations
