import React from "react";
import { Link } from "react-router-dom";
import {
  Broadcast, ChatCircle, CurrencyDollar, ShieldCheck, Cube, Lightning,
  CheckCircle, RocketLaunch,
} from "@phosphor-icons/react";

const FEATURES = [
  { Icon: Broadcast, title: "Sub-second WebRTC", body: "LiveKit-powered streaming, 400ms–1.5s glass-to-glass latency. OBS WHIP support out of the box." },
  { Icon: ChatCircle, title: "Real-time chat", body: "WebSocket chat with 60+ custom emotes per streamer, tier badges, mod tools, and chat rules sync." },
  { Icon: CurrencyDollar, title: "Built-in monetization", body: "Donations, 3-tier subscriptions, ad slots (VAST/IMA), Stripe Connect auto-payouts to streamers." },
  { Icon: Cube, title: "Self-hosted", body: "Runs on your $20/mo VPS. One-command install on Ubuntu 24.04. Zero SaaS dependency." },
  { Icon: ShieldCheck, title: "Production hardened", body: "JWT + bcrypt, IP rate limits, Stripe-grade KYC for streamers, GDPR-ready data export/delete." },
  { Icon: Lightning, title: "One-click updates", body: "Admin-panel auto-updater pulls from GitHub, with pre-update DB backups + rollback." },
];

const FAQS = [
  ["What do I actually get when I buy?", "Full source code (backend + frontend + deploy scripts), one-click VPS installer, admin panel, auto-updater. You own everything — no recurring fees to anyone."],
  ["What's the difference between Basic, Pro and Enterprise?", "Basic is a one-time lifetime license for a single VPS — perfect if you want to set it and forget it. Pro is a monthly subscription that adds auto-updates and priority support. Enterprise allows multi-server deployment, white-label rights, and onboarding assistance."],
  ["Can I run this without paying you forever?", "Yes — Basic is a one-time payment with lifetime access. Pro/Enterprise subscriptions stop the auto-updater and priority support if you cancel, but the platform keeps running."],
  ["What infrastructure do I need?", "Minimum: Ubuntu 24.04 VPS with 2 vCPU / 4 GB RAM ($10–20/mo). Plus accounts for: LiveKit (free tier covers ~1000 concurrent viewers), Stripe (free), Wasabi S3 (~$6/mo), and an SMTP provider (free)."],
  ["Can I customize the platform?", "Absolutely — you have full source code. Change branding, add features, remove what you don't need. Most admin-panel changes (site title, prices, theme) need no code."],
  ["What about updates?", "Pro and Enterprise tiers get one-click admin-panel updates with rollback. Basic gets one year of updates from purchase, then you can keep updating manually via git."],
];

export default function HomePage() {
  return (
    <div>
      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 pt-20 pb-24">
        <p className="text-accent text-xs font-bold tracking-widest uppercase mb-4">
          Self-hosted livestreaming platform
        </p>
        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black tracking-tight max-w-4xl leading-[1.05]">
          Launch your own Twitch in <span className="text-accent">60 minutes</span>.
        </h1>
        <p className="text-muted text-lg mt-6 max-w-2xl leading-relaxed">
          StreamVault is a complete Kick.com / Twitch alternative — WebRTC streaming,
          real-time chat, Stripe-powered monetization, and a comprehensive admin panel.
          One license, one VPS, total control.
        </p>
        <div className="flex flex-wrap gap-3 mt-10">
          <Link
            to="/pricing"
            className="bg-accent text-black hover:bg-accent/80 transition-colors px-6 py-3 rounded-lg font-bold inline-flex items-center gap-2"
          >
            <RocketLaunch weight="fill" className="w-4 h-4" />
            See pricing
          </Link>
          <a
            href="#features"
            className="border border-border hover:border-accent transition-colors px-6 py-3 rounded-lg font-semibold"
          >
            What's included →
          </a>
        </div>
        <p className="text-xs text-muted mt-6">
          Used in production by independent streaming communities. No SaaS lock-in. No revenue share.
        </p>
      </section>

      {/* Features grid */}
      <section id="features" className="border-t border-border/60">
        <div className="max-w-6xl mx-auto px-6 py-20">
          <h2 className="text-3xl font-black mb-3">Everything you need to run a streaming platform</h2>
          <p className="text-muted mb-10 max-w-2xl">200+ features across viewer, streamer, and admin roles. Built by people who actually shipped a competitor to Twitch.</p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {FEATURES.map(({ Icon, title, body }) => (
              <div key={title} className="bg-surface border border-border/60 rounded-xl p-6 hover:border-accent/50 transition-colors">
                <Icon weight="duotone" className="w-7 h-7 text-accent mb-3" />
                <h3 className="font-bold mb-2">{title}</h3>
                <p className="text-sm text-muted leading-relaxed">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* What's inside long-form */}
      <section className="border-t border-border/60">
        <div className="max-w-4xl mx-auto px-6 py-20">
          <h2 className="text-3xl font-black mb-10">What's inside the box</h2>
          {[
            ["Streaming infrastructure", [
              "Sub-second WebRTC powered by LiveKit (400ms–1.5s latency)",
              "Browser broadcasting + OBS WHIP ingest with RTMP fallback",
              "VOD recording (LiveKit Egress) stored in your S3 bucket",
              "Picture-in-picture, theatre mode, clip button, 30s rewind",
              "Live timer, viewer count, stream-quality auto-adapt",
            ]],
            ["Real-time chat & engagement", [
              "WebSocket chat (sub-100ms message delivery)",
              "60 custom emotes per streamer + 20 built-in subscriber emotes",
              "Tier badges, random subscriber colors, heart reactions",
              "Bans, timeouts, slow mode, follower-only, sub-only modes",
              "Real-time chat-rules sync (change rules, viewers see immediately)",
            ]],
            ["Monetization", [
              "Custom donations with on-screen alerts and top-donor leaderboards",
              "3 subscription tiers per streamer (auto-renewing via Stripe)",
              "Gift subscriptions",
              "VAST 4.0 / IMA SDK ad serving (pre/mid/post-roll)",
              "Stripe Connect Custom — automated streamer payouts on a schedule",
              "Configurable platform fee (you keep X%, streamer keeps the rest)",
            ]],
            ["Admin control", [
              "Site branding (title, tagline, logo, colors)",
              "Ban / restrict users by ID, email, or IP — with expiry",
              "Pin streams to the top of Browse",
              "One-click GitHub auto-updater with pre-update DB backups + rollback",
              "Customizable email templates (verification, welcome, achievements)",
              "Storage, LiveKit, Stripe, SMTP all configurable from the UI",
            ]],
            ["Engagement & retention", [
              "Achievement / XP system with grade-up emails",
              "Streamer Path (Rookie → Pro → Veteran → Legend) gamification",
              "Profile feed (Twitter-style) for streamer updates",
              "Twitch-style raids with countdown banner + viewer auto-redirect",
              "Email notifications (live alerts, follower events, raids)",
            ]],
          ].map(([title, items]) => (
            <div key={title} className="mb-10">
              <h3 className="font-bold text-xl mb-4">{title}</h3>
              <ul className="space-y-2">
                {items.map((it) => (
                  <li key={it} className="flex items-start gap-3 text-sm text-muted">
                    <CheckCircle weight="fill" className="w-4 h-4 text-accent shrink-0 mt-0.5" />
                    <span>{it}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="border-t border-border/60">
        <div className="max-w-3xl mx-auto px-6 py-20">
          <h2 className="text-3xl font-black mb-10">Frequently asked</h2>
          <div className="space-y-3">
            {FAQS.map(([q, a]) => (
              <details key={q} className="group bg-surface border border-border/60 rounded-lg p-5">
                <summary className="cursor-pointer font-semibold list-none flex items-start justify-between gap-3">
                  <span>{q}</span>
                  <span className="text-accent group-open:rotate-45 transition-transform">+</span>
                </summary>
                <p className="text-sm text-muted mt-3 leading-relaxed">{a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-border/60">
        <div className="max-w-4xl mx-auto px-6 py-20 text-center">
          <h2 className="text-3xl sm:text-4xl font-black">Ready to own your platform?</h2>
          <p className="text-muted mt-4 mb-8 max-w-xl mx-auto">
            Pick a tier, complete checkout, and you'll have your license key in under a minute.
          </p>
          <Link
            to="/pricing"
            className="bg-accent text-black hover:bg-accent/80 transition-colors px-8 py-3.5 rounded-lg font-bold inline-block"
          >
            See pricing →
          </Link>
        </div>
      </section>
    </div>
  );
}
