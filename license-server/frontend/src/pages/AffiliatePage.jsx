import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { Copy, HandCoins, ChartBar, Check } from "@phosphor-icons/react";
import { affiliates } from "../lib/api";

function fmt(n) { return `$${(Number(n) || 0).toFixed(2)}`; }
function fmtDate(d) { try { return new Date(d).toLocaleDateString(); } catch { return "—"; } }

export default function AffiliatePage() {
  const [me, setMe] = useState(null);
  const [loading, setLoading] = useState(true);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [sales, setSales] = useState([]);

  const load = async () => {
    try {
      const { data } = await affiliates.me();
      setMe(data);
      if (data) {
        const s = await affiliates.mySales();
        setSales(s.data);
      }
    } catch {
      // not enrolled yet
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  const signup = async (e) => {
    e.preventDefault();
    if (!/^[A-Za-z0-9_-]{3,40}$/.test(code)) {
      toast.error("Code must be 3-40 chars, letters/digits/dash/underscore only");
      return;
    }
    setBusy(true);
    try {
      const { data } = await affiliates.signup(code.toUpperCase());
      setMe(data);
      toast.success("Affiliate account created");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Could not create");
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <div className="max-w-3xl mx-auto p-12 text-center text-muted">Loading…</div>;

  if (!me) {
    return (
      <div className="max-w-2xl mx-auto px-6 py-16">
        <h1 className="text-3xl font-black mb-2">Become an affiliate</h1>
        <p className="text-muted mb-8">
          Earn 20% commission on every purchase made through your referral link.
          Pick a code, share your link, and we track every sale automatically.
        </p>
        <form onSubmit={signup} className="space-y-4">
          <input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="Pick a referral code (e.g. ALEX2026)"
            className="w-full bg-surface border border-border rounded-lg px-4 py-3 focus:border-accent focus:outline-none uppercase"
            data-testid="affiliate-code-input"
          />
          <button
            type="submit"
            disabled={busy}
            className="w-full bg-accent text-black font-bold py-3 rounded-lg hover:bg-accent/80 disabled:opacity-50"
            data-testid="affiliate-signup-btn"
          >
            {busy ? "Creating…" : "Become an affiliate"}
          </button>
        </form>
      </div>
    );
  }

  const refLink = `${window.location.origin}/?ref=${me.code}`;
  const copy = (txt) => { navigator.clipboard.writeText(txt); toast.success("Copied"); };

  return (
    <div className="max-w-4xl mx-auto px-6 py-12">
      <h1 className="text-3xl font-black mb-2">Affiliate dashboard</h1>
      <p className="text-muted mb-8">Code <span className="font-mono text-accent">{me.code}</span> · {me.commission_percent}% commission</p>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <Stat icon={ChartBar} label="Total sales"   value={me.total_sales} />
        <Stat icon={HandCoins} label="Earned"       value={fmt(me.total_commission)} />
        <Stat icon={Check}     label="Paid out"     value={fmt(me.paid_out)} />
        <Stat icon={HandCoins} label="Owed to you"  value={fmt(me.balance_owed)} highlight />
      </div>

      <div className="bg-surface border border-border/60 rounded-xl p-6 mb-8">
        <p className="text-xs text-muted mb-2">Your referral link</p>
        <div className="bg-card rounded-lg p-3 flex items-center justify-between gap-2">
          <code className="text-sm break-all flex-1">{refLink}</code>
          <button onClick={() => copy(refLink)} className="text-muted hover:text-accent shrink-0 p-1.5">
            <Copy className="w-4 h-4" />
          </button>
        </div>
        <p className="text-xs text-muted mt-3">
          Share this anywhere. Anyone who clicks gets a 30-day cookie — if they buy in that window, you earn commission.
        </p>
      </div>

      <h2 className="font-bold text-lg mb-3">Recent sales</h2>
      {sales.length === 0 ? (
        <p className="text-muted text-sm bg-surface border border-border/60 rounded-lg p-6 text-center">
          No sales yet. Share your link to get going.
        </p>
      ) : (
        <div className="bg-surface border border-border/60 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-card text-xs text-muted uppercase tracking-wider">
              <tr>
                <th className="text-left p-3">Date</th>
                <th className="text-left p-3">Buyer</th>
                <th className="text-left p-3">Product</th>
                <th className="text-right p-3">Amount</th>
                <th className="text-right p-3">Commission</th>
                <th className="text-center p-3">Paid</th>
              </tr>
            </thead>
            <tbody>
              {sales.map((s) => (
                <tr key={s.sale_id} className="border-t border-border/40">
                  <td className="p-3">{fmtDate(s.created_at)}</td>
                  <td className="p-3 font-mono text-xs">{s.buyer_email}</td>
                  <td className="p-3">{s.product_id}</td>
                  <td className="p-3 text-right">{fmt(s.amount)}</td>
                  <td className="p-3 text-right text-accent font-semibold">{fmt(s.commission)}</td>
                  <td className="p-3 text-center">{s.paid ? "✓" : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Stat({ icon: Icon, label, value, highlight }) {
  return (
    <div className={`bg-surface border rounded-xl p-4 ${highlight ? "border-accent" : "border-border/60"}`}>
      <Icon className={`w-5 h-5 mb-2 ${highlight ? "text-accent" : "text-muted"}`} />
      <p className="text-xs text-muted">{label}</p>
      <p className="font-black text-xl">{value}</p>
    </div>
  );
}
