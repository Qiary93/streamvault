import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  ShieldCheck, ArrowsClockwise, Warning, Key, Globe, Calendar,
} from '@phosphor-icons/react';
import { Button } from './ui/button';

const API = process.env.REACT_APP_BACKEND_URL;

const STATUS_META = {
  active:             { color: 'text-[#4ADE80]', label: 'Active', desc: 'Your license is valid and your IP is bound.' },
  expired:            { color: 'text-red-400',   label: 'Expired', desc: 'Your subscription expired. Renew it to keep premium features unlocked.' },
  revoked:            { color: 'text-red-400',   label: 'Revoked', desc: 'This license was revoked. Contact support if you believe this is an error.' },
  ip_mismatch:        { color: 'text-[#FFC75F]', label: 'IP mismatch', desc: 'Your server IP is not on the allow-list. Update it from your DramaroSub dashboard.' },
  not_found:          { color: 'text-red-400',   label: 'Not found', desc: 'License key is not recognized by the license server.' },
  unconfigured:       { color: 'text-[#A0A0AB]', label: 'Not configured', desc: 'Set STREAMVAULT_LICENSE_KEY and LICENSE_SERVER_URL in your .env, then restart the backend.' },
  server_unreachable: { color: 'text-[#FFC75F]', label: 'License server unreachable', desc: 'Could not contact the license server within the offline grace period. Premium features will be locked until contact is re-established.' },
  unchecked:          { color: 'text-[#A0A0AB]', label: 'Checking…', desc: 'First validation has not completed yet.' },
};

function fmt(d) {
  if (!d) return '—';
  try { return new Date(d).toLocaleString(); } catch { return d; }
}

export default function AdminLicensePanel() {
  const [status, setStatus] = useState(null);
  const [revalidating, setRevalidating] = useState(false);

  const fetchStatus = async () => {
    try {
      const res = await axios.get(`${API}/api/admin/license/status`, { withCredentials: true });
      setStatus(res.data);
    } catch (e) {
      // swallow — backend may be restarting
    }
  };

  const revalidate = async () => {
    setRevalidating(true);
    try {
      const res = await axios.post(`${API}/api/admin/license/revalidate`, {}, { withCredentials: true });
      setStatus(res.data);
      toast.success(res.data.valid ? 'License re-validated' : `Status: ${res.data.status}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Re-validation failed');
    } finally {
      setRevalidating(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const t = setInterval(fetchStatus, 60_000);
    return () => clearInterval(t);
  }, []);

  if (!status) return null;

  const meta = STATUS_META[status.status] || STATUS_META.unchecked;
  const valid = !!status.valid;

  return (
    <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-6 mt-6" data-testid="admin-license">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-[#00E5FF]" />
            License
          </h3>
          <p className="text-sm text-[#A0A0AB] mt-1">
            Status of your DramaroSub license. Premium features (auto-updater, advanced analytics) require a valid license.
          </p>
        </div>
        <Button
          onClick={revalidate}
          disabled={revalidating}
          variant="ghost"
          className="border border-white/10 text-white hover:bg-white/5"
          data-testid="license-revalidate-btn"
        >
          <ArrowsClockwise className={`w-4 h-4 mr-2 ${revalidating ? 'animate-spin' : ''}`} />
          {revalidating ? 'Checking…' : 'Re-check now'}
        </Button>
      </div>

      <div
        className={`bg-[#1A1A24] rounded-lg p-4 mb-3 border ${
          valid ? 'border-[#4ADE80]/20' : 'border-[#FFC75F]/20'
        }`}
        data-testid="license-status-card"
      >
        <div className="flex items-center gap-2 mb-1">
          {valid
            ? <ShieldCheck weight="fill" className="w-4 h-4 text-[#4ADE80]" />
            : <Warning weight="fill" className="w-4 h-4 text-[#FFC75F]" />}
          <span className={`font-semibold text-sm ${meta.color}`}>{meta.label}</span>
        </div>
        <p className="text-xs text-[#A0A0AB]">{status.message || meta.desc}</p>
      </div>

      {valid && status.product_name && (
        <div className="bg-[#1A1A24] rounded-lg p-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <p className="text-xs text-[#A0A0AB] flex items-center gap-1.5 mb-1">
              <Key className="w-3 h-3" /> Plan
            </p>
            <p className="text-white text-sm font-semibold" data-testid="license-product">{status.product_name}</p>
          </div>
          <div>
            <p className="text-xs text-[#A0A0AB] flex items-center gap-1.5 mb-1">
              <Calendar className="w-3 h-3" /> Renews
            </p>
            <p className="text-white text-sm">{status.expires_at ? fmt(status.expires_at) : 'Lifetime'}</p>
          </div>
          <div>
            <p className="text-xs text-[#A0A0AB] flex items-center gap-1.5 mb-1">
              <Globe className="w-3 h-3" /> Last validated
            </p>
            <p className="text-white text-sm">{fmt(status.last_success_at || status.last_check_at)}</p>
          </div>
        </div>
      )}

      {!valid && status.status === 'unconfigured' && (
        <div className="text-xs text-[#A0A0AB] mt-3">
          <p className="mb-2">To configure your license, edit <code className="bg-[#1A1A24] px-1.5 py-0.5 rounded text-[#00E5FF]">/app/backend/.env</code> and add:</p>
          <pre className="bg-black/40 p-3 rounded text-[11px] leading-relaxed">
{`STREAMVAULT_LICENSE_KEY=DSB-XXXXX-XXXXX-XXXXX-XXXXX
LICENSE_SERVER_URL=https://license.stream-vault.eu`}
          </pre>
          <p className="mt-2">
            Don't have a license? <a href="https://license.stream-vault.eu/pricing" target="_blank" rel="noopener noreferrer" className="text-[#00E5FF] hover:underline">Buy one here</a>.
          </p>
        </div>
      )}
    </div>
  );
}
