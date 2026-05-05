import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Check, Crown } from "@phosphor-icons/react";
import { products, checkout } from "../lib/api";
import { useAuth } from "../lib/auth";

export default function PricingPage() {
  const [items, setItems] = useState([]);
  const [buying, setBuying] = useState(null);
  const { user } = useAuth();
  const nav = useNavigate();

  useEffect(() => {
    products.list().then((r) => setItems(r.data)).catch(() => toast.error("Failed to load products"));
  }, []);

  const buy = async (id) => {
    if (!user) {
      toast.info("Please sign in or create an account first");
      nav(`/login?next=/pricing`);
      return;
    }
    setBuying(id);
    try {
      const { data } = await checkout.create(id);
      window.location.href = data.checkout_url;
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not start checkout");
      setBuying(null);
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-6 py-16">
      <div className="text-center mb-12">
        <h1 className="text-4xl sm:text-5xl font-black tracking-tight">Simple, honest pricing</h1>
        <p className="text-muted mt-4 max-w-xl mx-auto">
          Pick once and you're done. No hidden fees. Cancel subscriptions anytime.
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {items.map((p) => (
          <div
            key={p.id}
            className={`relative bg-surface rounded-2xl p-7 border transition-all ${
              p.highlight
                ? "border-accent shadow-[0_0_60px_-20px_rgba(0,229,255,0.5)] scale-[1.02]"
                : "border-border/60 hover:border-accent/40"
            }`}
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
