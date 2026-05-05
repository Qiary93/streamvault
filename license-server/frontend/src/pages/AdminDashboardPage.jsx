import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  Users, CurrencyDollar, ChartLine, ShieldX, Tag, HandCoins, Plus, Trash, X,
} from "@phosphor-icons/react";
import { admin, coupons, affiliates as aff } from "../lib/api";

const fmt = (n) => `$${(Number(n) || 0).toFixed(2)}`;
const fmtDate = (d) => { try { return new Date(d).toLocaleDateString(); } catch { return "—"; } };

const TABS = [
  { id: "stats",     label: "Overview" },
  { id: "users",     label: "Users" },
  { id: "licenses",  label: "Licenses" },
  { id: "coupons",   label: "Coupons" },
  { id: "affiliates",label: "Affiliates" },
];

export default function AdminDashboardPage() {
  const [tab, setTab] = useState("stats");
  return (
    <div className="max-w-6xl mx-auto px-6 py-10">
      <h1 className="text-3xl font-black mb-2">Seller admin</h1>
      <p className="text-muted text-sm mb-6">Internal dashboard. Not visible to customers.</p>
      <div className="flex flex-wrap gap-1 border-b border-border mb-8">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2.5 text-sm font-semibold transition-colors border-b-2 -mb-px ${
              tab === t.id
                ? "text-accent border-accent"
                : "text-muted hover:text-white border-transparent"
            }`}
            data-testid={`admin-tab-${t.id}`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === "stats" && <StatsTab />}
      {tab === "users" && <UsersTab />}
      {tab === "licenses" && <LicensesTab />}
      {tab === "coupons" && <CouponsTab />}
      {tab === "affiliates" && <AffiliatesTab />}
    </div>
  );
}

function StatCard({ icon: Icon, label, value, sub }) {
  return (
    <div className="bg-surface border border-border/60 rounded-xl p-5">
      <Icon className="w-5 h-5 text-accent mb-2" />
      <p className="text-xs text-muted">{label}</p>
      <p className="font-black text-2xl">{value}</p>
      {sub && <p className="text-xs text-muted mt-1">{sub}</p>}
    </div>
  );
}

function StatsTab() {
  const [s, setS] = useState(null);
  useEffect(() => { admin.stats().then((r) => setS(r.data)).catch(() => toast.error("Stats failed")); }, []);
  if (!s) return <p className="text-muted">Loading…</p>;
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <StatCard icon={CurrencyDollar} label="Total revenue"     value={fmt(s.total_revenue)} sub={`Last 30d: ${fmt(s.revenue_last_30d)}`} />
      <StatCard icon={ChartLine}      label="MRR / ARR"         value={fmt(s.mrr)} sub={`ARR: ${fmt(s.arr)}`} />
      <StatCard icon={Users}          label="Total users"       value={s.total_users} sub={`${s.active_subscriptions} active subs`} />
      <StatCard icon={ShieldX}        label="Active licenses"   value={s.active_licenses} sub={`${s.expired_licenses} expired · ${s.revoked_licenses} revoked`} />
      <StatCard icon={Tag}            label="Active coupons"    value={s.total_coupons} />
      <StatCard icon={HandCoins}      label="Total affiliates"  value={s.total_affiliates} sub={`Owed: ${fmt(s.unpaid_affiliate_commission)}`} />
      <StatCard icon={CurrencyDollar} label="Lifetime sales"    value={s.total_licenses_issued} />
    </div>
  );
}

function UsersTab() {
  const [items, setItems] = useState([]);
  const [q, setQ] = useState("");
  const load = () => admin.users(q).then((r) => setItems(r.data));
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);
  return (
    <div>
      <div className="flex gap-2 mb-4">
        <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && load()}
          placeholder="Search email or name" className="bg-surface border border-border rounded px-3 py-2 text-sm flex-1 focus:outline-none focus:border-accent"/>
        <button onClick={load} className="bg-card hover:bg-border px-4 py-2 rounded text-sm">Search</button>
      </div>
      <div className="bg-surface border border-border/60 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-card text-xs text-muted uppercase tracking-wider">
            <tr><th className="text-left p-3">Email</th><th className="text-left p-3">Name</th><th className="text-right p-3">Licenses</th><th className="text-right p-3">Spent</th><th className="p-3">Joined</th></tr>
          </thead>
          <tbody>
            {items.map((u) => (
              <tr key={u.user_id} className="border-t border-border/40">
                <td className="p-3 font-mono text-xs">{u.email}{u.is_admin && <span className="ml-1 bg-accent/20 text-accent text-[10px] px-1 rounded">ADMIN</span>}</td>
                <td className="p-3">{u.full_name || "—"}</td>
                <td className="p-3 text-right">{u.license_count}</td>
                <td className="p-3 text-right">{fmt(u.total_spent)}</td>
                <td className="p-3 text-xs text-muted">{fmtDate(u.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function LicensesTab() {
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("");
  const load = () => admin.licenses(filter).then((r) => setItems(r.data));
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [filter]);

  const revoke = async (id) => {
    const reason = window.prompt("Reason for revocation?");
    if (reason === null) return;
    try { await admin.revoke(id, reason); toast.success("Revoked"); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };
  const refund = async (id) => {
    if (!window.confirm("Issue a Stripe refund for this license? This is irreversible.")) return;
    const reason = window.prompt("Refund reason?") || "";
    try { const { data } = await admin.refund(id, reason, true); toast.success(`Refunded (${data.refund_id})`); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Refund failed"); }
  };
  return (
    <div>
      <div className="flex gap-2 mb-4">
        {["", "active", "expired", "revoked"].map((s) => (
          <button key={s || "all"} onClick={() => setFilter(s)}
            className={`px-3 py-1.5 rounded text-xs font-semibold ${filter === s ? "bg-accent text-black" : "bg-card text-muted hover:text-white"}`}>
            {s || "All"}
          </button>
        ))}
      </div>
      <div className="bg-surface border border-border/60 rounded-xl overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-card text-xs text-muted uppercase tracking-wider">
            <tr><th className="text-left p-3">Key</th><th className="text-left p-3">User</th><th className="text-left p-3">Product</th><th className="p-3">Status</th><th className="text-left p-3">Bound IPs</th><th className="p-3">Created</th><th></th></tr>
          </thead>
          <tbody>
            {items.map((l) => (
              <tr key={l.license_id} className="border-t border-border/40">
                <td className="p-3 font-mono text-[11px] break-all">{l.license_key}</td>
                <td className="p-3 text-xs">{l.user_email}</td>
                <td className="p-3">{l.product_name}</td>
                <td className="p-3 text-center">
                  <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded ${l.status === "active" ? "bg-[#4ADE80]/20 text-[#4ADE80]" : l.status === "revoked" ? "bg-danger/20 text-danger" : "bg-muted/20 text-muted"}`}>{l.status}</span>
                </td>
                <td className="p-3 text-xs font-mono">{l.bound_ips.join(", ") || "—"}</td>
                <td className="p-3 text-xs text-muted">{fmtDate(l.created_at)}</td>
                <td className="p-3 text-right whitespace-nowrap">
                  {l.status === "active" && (<>
                    <button onClick={() => revoke(l.license_id)} className="text-xs text-danger hover:underline mr-3">Revoke</button>
                    <button onClick={() => refund(l.license_id)} className="text-xs text-accent2 hover:underline">Refund</button>
                  </>)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CouponsTab() {
  const [items, setItems] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ code: "", description: "", discount_type: "percentage", discount_value: 10, max_uses: 0 });
  const load = () => coupons.list().then((r) => setItems(r.data));
  useEffect(load, []);

  const create = async (e) => {
    e.preventDefault();
    try {
      await coupons.create({ ...form, code: form.code.toUpperCase(), discount_value: parseFloat(form.discount_value), max_uses: parseInt(form.max_uses) });
      toast.success("Created");
      setShowForm(false);
      setForm({ code: "", description: "", discount_type: "percentage", discount_value: 10, max_uses: 0 });
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };
  const remove = async (code) => {
    if (!window.confirm(`Delete coupon ${code}?`)) return;
    try { await coupons.delete(code); toast.success("Deleted"); load(); } catch { toast.error("Failed"); }
  };
  return (
    <div>
      <div className="flex justify-between mb-4">
        <h3 className="font-bold">All coupons ({items.length})</h3>
        <button onClick={() => setShowForm(!showForm)} className="bg-accent text-black hover:bg-accent/80 px-3 py-1.5 rounded text-sm font-bold flex items-center gap-1">
          {showForm ? <X className="w-3 h-3" /> : <Plus className="w-3 h-3" />}{showForm ? "Cancel" : "New coupon"}
        </button>
      </div>
      {showForm && (
        <form onSubmit={create} className="bg-surface border border-border/60 rounded-xl p-5 mb-5 grid grid-cols-1 md:grid-cols-2 gap-3">
          <input required placeholder="Code (e.g. LAUNCH30)" value={form.code} onChange={(e) => setForm({...form, code: e.target.value.toUpperCase()})} className="bg-card border border-border rounded px-3 py-2 text-sm" />
          <input placeholder="Description" value={form.description} onChange={(e) => setForm({...form, description: e.target.value})} className="bg-card border border-border rounded px-3 py-2 text-sm" />
          <select value={form.discount_type} onChange={(e) => setForm({...form, discount_type: e.target.value})} className="bg-card border border-border rounded px-3 py-2 text-sm">
            <option value="percentage">% off</option>
            <option value="fixed">Fixed $ off</option>
          </select>
          <input type="number" required placeholder="Value (e.g. 30 for 30%)" value={form.discount_value} onChange={(e) => setForm({...form, discount_value: e.target.value})} className="bg-card border border-border rounded px-3 py-2 text-sm" />
          <input type="number" placeholder="Max uses (0 = unlimited)" value={form.max_uses} onChange={(e) => setForm({...form, max_uses: e.target.value})} className="bg-card border border-border rounded px-3 py-2 text-sm" />
          <button type="submit" className="bg-accent text-black font-bold rounded px-4 py-2 text-sm">Create</button>
        </form>
      )}
      <div className="bg-surface border border-border/60 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-card text-xs text-muted uppercase tracking-wider">
            <tr><th className="text-left p-3">Code</th><th className="text-left p-3">Type</th><th className="text-right p-3">Value</th><th className="text-right p-3">Uses</th><th className="p-3">Active</th><th></th></tr>
          </thead>
          <tbody>
            {items.map((c) => (
              <tr key={c.code} className="border-t border-border/40">
                <td className="p-3 font-mono">{c.code}</td>
                <td className="p-3">{c.discount_type}</td>
                <td className="p-3 text-right">{c.discount_type === "percentage" ? `${c.discount_value}%` : fmt(c.discount_value)}</td>
                <td className="p-3 text-right">{c.used_count}{c.max_uses ? ` / ${c.max_uses}` : ""}</td>
                <td className="p-3 text-center">{c.active ? "✓" : "—"}</td>
                <td className="p-3 text-right">
                  <button onClick={() => remove(c.code)} className="text-danger hover:underline text-xs">
                    <Trash className="w-3.5 h-3.5 inline" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AffiliatesTab() {
  const [items, setItems] = useState([]);
  const load = () => aff.list().then((r) => setItems(r.data));
  useEffect(load, []);
  const markPaid = async (uid) => {
    if (!window.confirm("Mark all unpaid sales for this affiliate as paid? Make sure you've already wired the money out.")) return;
    try { const { data } = await aff.markPaid(uid); toast.success(`Marked ${data.sales_marked_paid} sale(s) — ${fmt(data.total_amount)}`); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };
  return (
    <div className="bg-surface border border-border/60 rounded-xl overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-card text-xs text-muted uppercase tracking-wider">
          <tr><th className="text-left p-3">Code</th><th className="text-right p-3">Sales</th><th className="text-right p-3">Revenue</th><th className="text-right p-3">Earned</th><th className="text-right p-3">Paid</th><th className="text-right p-3">Owed</th><th></th></tr>
        </thead>
        <tbody>
          {items.map((a) => (
            <tr key={a.user_id} className="border-t border-border/40">
              <td className="p-3 font-mono">{a.code}</td>
              <td className="p-3 text-right">{a.total_sales}</td>
              <td className="p-3 text-right">{fmt(a.total_revenue)}</td>
              <td className="p-3 text-right">{fmt(a.total_commission)}</td>
              <td className="p-3 text-right">{fmt(a.paid_out)}</td>
              <td className="p-3 text-right text-accent font-bold">{fmt(a.balance_owed)}</td>
              <td className="p-3 text-right">
                {a.balance_owed > 0 && (
                  <button onClick={() => markPaid(a.user_id)} className="text-xs text-accent hover:underline">Mark paid</button>
                )}
              </td>
            </tr>
          ))}
          {items.length === 0 && <tr><td colSpan="7" className="p-6 text-center text-muted">No affiliates yet</td></tr>}
        </tbody>
      </table>
    </div>
  );
}
