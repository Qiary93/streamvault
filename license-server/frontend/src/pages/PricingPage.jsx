import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Check, Crown, Tag } from "@phosphor-icons/react";
import { products, checkout, coupons } from "../lib/api";
import { useAuth } from "../lib/auth";
import { getReferralCode } from "../lib/referral";

export default function PricingPage() {
  const [items, setItems] = useState([]);
  const [billing, setBilling] = useState("monthly");          // "monthly" | "annual"
  const [coupon, setCoupon] = useState("");
  const [couponInfo, setCouponInfo] = useState(null);          // { valid, message, ... } per product
  const [buying, setBuying] = useState(null);
  const { user } = useAuth();
  const nav = useNavigate();
  const referral = getReferralCode();

  useEffect(() => {
    products.list().then((r) => setItems(r.data)).catch(() => toast.error("Failed to load products"));
  }, []);

  // Group products by tier so the annual toggle can show one card per tier.
  const byTier = useMemo(() => {
    const map = {};
    for (const p of items) {
      const t = p.tier || p.id;
      (map[t] ||= {}).all = map[t].all || [];
      map[t].all.push(p);
      if (p.mode === "payment") map[t].oneTime = p;
      if (p.mode === "subscription" && p.interval === "month") map[t].monthly = p;
      if (p.mode === "subscription" && p.interval === "year") map[t].annual = p;
    }
    return map;
  }, [items]);

  // Resolve which product to actually show per tier given the toggle state
  const visibleTiers = useMemo(() => {
    return ["basic", "pro", "enterprise"].map((tier) => {
      const t = byTier[tier];
      if (!t) return null;
      let product;
      if (tier === "basic") {
        product = t.oneTime;     // basic is always one-time
      } else {
        product = billing === "annual" ? (t.annual || t.monthly) : t.monthly;
      }
      return product || null;
    }).filter(Boolean);
  }, [byTier, billing]);

  const validateCoupon = async () => {
    if (!coupon.trim()) {
      setCouponInfo(null);
      return;
    }
    if (visibleTiers.length === 0) return;
    try {
      // Validate against the highlighted tier (Pro). The actual discount is
      // re-applied per product at checkout-create time.
      const target = visibleTiers.find((p) => p?.tier === "pro") || visibleTiers[0];
      const { data } = await coupons.validate(coupon.trim().toUpperCase(), target.id);
      setCouponInfo(data);
      if (data.valid) toast.success("Coupon applied");
      else toast.error(data.message);
    } catch {
      toast.error("Could not validate coupon");
    }
  };

  const buy = async (id) => {
    if (!user) {
      toast.info("Please sign in or create an account first");
      const next = encodeURIComponent(`/pricing?coupon=${coupon}`);
      nav(`/login?next=${next}`);
      return;
    }
    setBuying(id);
    try {
      const { data } = await checkout.create(id, coupon.trim().toUpperCase() || undefined, referral || undefined);
      window.location.href = data.checkout_url;
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not start checkout");
      setBuying(null);
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-6 py-16">
      <div className="text-center mb-10">
        <h1 className="text-4xl sm:text-5xl font-black tracking-tight">Simple, honest pricing</h1>
        <p className="text-muted mt-4 max-w-xl mx-auto">
          Pick once and you're done. No hidden fees. Cancel subscriptions anytime.
        </p>
      </div>

      {/* Annual / monthly toggle */}
      <div className="flex justify-center mb-8">
        <div className="inline-flex bg-surface border border-border rounded-full p-1" data-testid="billing-toggle">
          <button
            onClick={() => setBilling("monthly")}
            className={`px-5 py-2 rounded-full text-sm font-semibold transition-colors ${
              billing === "monthly" ? "bg-accent text-black" : "text-muted hover:text-white"
            }`}
            data-testid="billing-monthly"
          >
            Monthly
          </button>
          <button
            onClick={() => setBilling("annual")}
            className={`px-5 py-2 rounded-full text-sm font-semibold transition-colors flex items-center gap-2 ${
              billing === "annual" ? "bg-accent text-black" : "text-muted hover:text-white"
            }`}
            data-testid="billing-annual"
          >
            Annual <span className="text-[10px] bg-[#FFC75F]/20 text-[#FFC75F] rounded px-1.5 py-0.5 font-bold">SAVE 17%</span>
          </button>
        </div>
      </div>

      {/* Coupon input */}
      <div className="flex justify-center mb-10">
        <div className="bg-surface border border-border rounded-lg p-2 flex items-center gap-2 max-w-md w-full">
          <Tag className="w-4 h-4 text-muted ml-2" />
          <input
            value={coupon}
            onChange={(e) => setCoupon(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && validateCoupon()}
            placeholder="Have a coupon code?"
            className="bg-transparent flex-1 px-2 py-1 text-sm focus:outline-none"
            data-testid="coupon-input"
          />
          <button
            onClick={validateCoupon}
            className="bg-accent text-black hover:bg-accent/80 px-4 py-1.5 rounded text-sm font-bold"
            data-testid="coupon-apply"
          >
            Apply
          </button>
        </div>
      </div>
      {couponInfo?.valid && (
        <p className="text-center text-sm text-[#4ADE80] mb-6 -mt-4" data-testid="coupon-valid">
          ✓ Coupon valid — discount applies at checkout
        </p>
      )}
      {referral && (
        <p className="text-center text-xs text-muted mb-6">
          Referred by <span className="text-accent font-mono">{referral}</span>
        </p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {visibleTiers.map((p) => (
          <div
            key={p.id}
            className={`relative bg-surface rounded-2xl p-7 border transition-all ${
              p.highlight
                ? "border-accent shadow-[0_0_60px_-20px_rgba(0,229,255,0.5)] scale-[1.02]"
                : "border-border/60 hover:border-accent/40"
            }`}
            data-testid={`pricing-card-${p.tier}`}
          >
            {p.highlight && (
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-accent text-black text-xs font-bold px-3 py-1 rounded-full flex items-center gap-1">
                <Crown weight="fill" className="w-3 h-3" /> Most popular
              </div>
            )}
            <h3 className="font-bold text-xl">{p.name}</h3>
            <p className="text-sm text-muted mt-1 mb-5 leading-relaxed">{p.description}</p>
            <div className="flex items-baseline gap-1 mb-1">
              <span className="text-4xl font-black">${p.price.toFixed(0)}</span>
              <span className="text-muted text-sm">
                {p.mode === "subscription" ? `/${p.interval}` : "one-time"}
              </span>
            </div>
            <button
              onClick={() => buy(p.id)}
              disabled={buying === p.id}
              className={`mt-5 w-full py-2.5 rounded-lg font-bold transition-colors ${
                p.highlight
                  ? "bg-accent text-black hover:bg-accent/80"
                  : "bg-card text-white hover:bg-border"
              } disabled:opacity-50`}
              data-testid={`buy-${p.id}`}
            >
              {buying === p.id ? "Redirecting…" : p.mode === "payment" ? "Buy lifetime" : "Subscribe"}
            </button>
            <ul className="mt-6 space-y-2.5">
              {p.features.map((f) => (
                <li key={f} className="flex items-start gap-2.5 text-sm">
                  <Check weight="bold" className="w-4 h-4 text-accent shrink-0 mt-0.5" />
                  <span>{f}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <p className="text-center text-xs text-muted mt-12">
        Secure checkout via Stripe. We never see or store your card details.
      </p>
    </div>
  );
}
