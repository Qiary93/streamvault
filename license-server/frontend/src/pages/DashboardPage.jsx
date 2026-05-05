import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Copy, Pencil, Check, Globe, Calendar } from "@phosphor-icons/react";
import { licenses } from "../lib/api";
import { useAuth } from "../lib/auth";

const STATUS_COLOR = {
  active: "text-[#4ADE80]",
  expired: "text-danger",
  revoked: "text-danger",
};

function fmt(d) {
  if (!d) return "—";
  try { return new Date(d).toLocaleDateString(); } catch { return "—"; }
}

function LicenseCard({ lic, onIpChanged }) {
  const [editing, setEditing] = useState(false);
  const [newIp, setNewIp] = useState("");
  const [busy, setBusy] = useState(false);

  const copyKey = () => {
    navigator.clipboard.writeText(lic.license_key);
    toast.success("License key copied");
  };

  const saveIp = async () => {
    if (!newIp.trim()) return;
    setBusy(true);
    try {
      const { data } = await licenses.changeIp(lic.license_id, newIp.trim());
      toast.success("IP updated");
      onIpChanged(data);
      setEditing(false);
      setNewIp("");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Could not change IP");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="bg-surface border border-border/60 rounded-xl p-6">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-bold text-lg">{lic.product_name}</h3>
            <span className={`text-xs font-semibold uppercase ${STATUS_COLOR[lic.status] || "text-muted"}`}>
              {lic.status}
            </span>
          </div>
          <p className="text-xs text-muted flex items-center gap-3">
            <span className="flex items-center gap-1"><Calendar className="w-3 h-3" /> Issued {fmt(lic.created_at)}</span>
            {lic.expires_at && <span>Renews {fmt(lic.expires_at)}</span>}
          </p>
        </div>
      </div>

      <div className="bg-card rounded-lg p-3 mt-4 flex items-center justify-between gap-2">
        <code className="font-mono text-sm break-all">{lic.license_key}</code>
        <button onClick={copyKey} className="text-muted hover:text-accent shrink-0 p-1.5" title="Copy">
          <Copy className="w-4 h-4" />
        </button>
      </div>

      <div className="mt-4">
        <p className="text-xs text-muted mb-1.5 flex items-center gap-1.5">
          <Globe className="w-3 h-3" />
          Bound IP{lic.max_ips > 1 ? "s" : ""} ({lic.bound_ips.length}/{lic.max_ips})
          <span className="ml-auto">{lic.ip_changes_remaining} change{lic.ip_changes_remaining === 1 ? "" : "s"} left this month</span>
        </p>
        {editing ? (
          <div className="flex gap-2">
            <input
              autoFocus
              placeholder="e.g. 198.51.100.42"
              value={newIp}
              onChange={(e) => setNewIp(e.target.value)}
              className="flex-1 bg-card border border-border rounded px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
            />
            <button onClick={saveIp} disabled={busy} className="bg-accent text-black px-3 py-1.5 rounded text-sm font-semibold disabled:opacity-50">
              {busy ? "…" : <Check className="w-4 h-4" />}
            </button>
            <button onClick={() => { setEditing(false); setNewIp(""); }} className="text-muted hover:text-white px-3 py-1.5 rounded text-sm">
              Cancel
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <code className="text-sm bg-card px-3 py-1.5 rounded flex-1">
              {lic.bound_ips.length ? lic.bound_ips.join(", ") : <span className="text-muted">Not yet bound — first validation auto-binds</span>}
            </code>
            {lic.status === "active" && lic.ip_changes_remaining > 0 && (
              <button onClick={() => setEditing(true)} className="text-muted hover:text-accent p-1.5" title="Change IP">
                <Pencil className="w-4 h-4" />
              </button>
            )}
          </div>
        )}
      </div>

      <div className="mt-4 pt-4 border-t border-border/40">
        <details className="text-xs text-muted">
          <summary className="cursor-pointer hover:text-white">How to install on my server</summary>
          <pre className="mt-2 bg-card p-3 rounded text-[11px] leading-relaxed overflow-x-auto">
{`# Add to /app/backend/.env on your StreamVault VPS:
STREAMVAULT_LICENSE_KEY=${lic.license_key}
LICENSE_SERVER_URL=https://dramarosub.ro

# Then restart the backend:
sudo supervisorctl restart backend`}
          </pre>
        </details>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  const refresh = () => {
    licenses
      .list()
      .then((r) => setItems(r.data))
      .catch(() => toast.error("Could not load licenses"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { refresh(); }, []);

  const onIpChanged = (updated) =>
    setItems((curr) => curr.map((l) => (l.license_id === updated.license_id ? updated : l)));

  return (
    <div className="max-w-4xl mx-auto px-6 py-12">
      <div className="flex items-end justify-between flex-wrap gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-black">Your dashboard</h1>
          <p className="text-muted text-sm mt-1">Signed in as {user?.email}</p>
        </div>
        <Link to="/pricing" className="bg-accent text-black hover:bg-accent/80 px-4 py-2 rounded-lg font-bold text-sm">
          + New license
        </Link>
      </div>

      {loading ? (
        <p className="text-muted">Loading…</p>
      ) : items.length === 0 ? (
        <div className="bg-surface border border-border/60 rounded-xl p-10 text-center">
          <p className="text-lg font-bold mb-1">No licenses yet</p>
          <p className="text-muted text-sm mb-5">Pick a tier and get up and running in under a minute.</p>
          <Link to="/pricing" className="bg-accent text-black hover:bg-accent/80 px-5 py-2.5 rounded-lg font-bold inline-block">
            Browse pricing
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          {items.map((lic) => (
            <LicenseCard key={lic.license_id} lic={lic} onIpChanged={onIpChanged} />
          ))}
        </div>
      )}
    </div>
  );
}
