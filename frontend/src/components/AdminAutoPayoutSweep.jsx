import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { ClockClockwise, PlayCircle } from '@phosphor-icons/react';
import { Button } from './ui/button';
import { Input } from './ui/input';

const API = process.env.REACT_APP_BACKEND_URL;

const FREQS = [
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
];

export default function AdminAutoPayoutSweep() {
  const [cfg, setCfg] = useState({
    automated_enabled: false,
    auto_sweep_enabled: false,
    auto_sweep_frequency: 'weekly',
    auto_sweep_min_amount: 10,
    platform_fee_percent: 0,
    auto_sweep_last_run_at: null,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);

  const load = async () => {
    try {
      const res = await axios.get(`${API}/api/admin/payout-settings`, { withCredentials: true });
      setCfg(prev => ({ ...prev, ...res.data }));
    } catch {}
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const save = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/api/admin/payout-settings`, {
        automated_enabled: !!cfg.automated_enabled,
        platform_fee_percent: Number(cfg.platform_fee_percent || 0),
        auto_sweep_enabled: !!cfg.auto_sweep_enabled,
        auto_sweep_frequency: cfg.auto_sweep_frequency,
        auto_sweep_min_amount: Number(cfg.auto_sweep_min_amount || 10),
      }, { withCredentials: true });
      toast.success('Auto-payout settings saved');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Save failed');
    } finally { setSaving(false); }
  };

  const runNow = async () => {
    if (!window.confirm('Run the payout sweep now? This will transfer & pay out every eligible streamer over the minimum threshold.')) return;
    setRunning(true);
    try {
      const res = await axios.post(`${API}/api/admin/payout-sweep/run`, {}, { withCredentials: true });
      toast.success(`Swept ${res.data.swept} streamer(s); skipped ${res.data.skipped}${res.data.errors?.length ? `; errors: ${res.data.errors.length}` : ''}`);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Sweep failed');
    } finally { setRunning(false); }
  };

  if (loading) return <div className="text-[#A0A0AB] text-sm p-4">Loading payout settings…</div>;

  return (
    <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-6 mt-6" data-testid="admin-auto-payout-sweep">
      <div className="flex items-center gap-2 mb-4">
        <ClockClockwise weight="fill" className="w-6 h-6 text-[#00E5FF]" />
        <h3 className="text-lg font-semibold text-white">Auto-payout scheduling</h3>
      </div>
      <p className="text-sm text-[#A0A0AB] mb-4">
        Automatically sweep every verified streamer's available balance to their Stripe Connect bank account on a recurring schedule.
        Requires "Automated payouts" to be ON.
      </p>

      {!cfg.automated_enabled && (
        <div className="rounded-lg bg-yellow-500/10 border border-yellow-500/20 text-xs text-yellow-300 px-3 py-2 mb-4" data-testid="auto-sweep-needs-automated">
          Automated payouts are currently OFF — enable them above for sweeps to actually pay out.
        </div>
      )}

      <label className="flex items-center gap-2 text-sm text-white mb-3 cursor-pointer">
        <input
          type="checkbox"
          checked={!!cfg.auto_sweep_enabled}
          onChange={e => setCfg(p => ({ ...p, auto_sweep_enabled: e.target.checked }))}
          data-testid="auto-sweep-enabled-toggle"
        />
        Enable auto-sweep
      </label>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
        <div>
          <label className="text-xs text-[#A0A0AB] block mb-1">Frequency</label>
          <div className="flex gap-2">
            {FREQS.map(f => (
              <button
                key={f.value}
                type="button"
                onClick={() => setCfg(p => ({ ...p, auto_sweep_frequency: f.value }))}
                className={`px-3 py-1.5 rounded-full text-xs font-medium ${
                  cfg.auto_sweep_frequency === f.value
                    ? 'bg-[#00E5FF] text-black'
                    : 'bg-[#1A1A24] text-[#A0A0AB] hover:text-white'
                }`}
                data-testid={`auto-sweep-freq-${f.value}`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="text-xs text-[#A0A0AB] block mb-1">Minimum balance to sweep (USD)</label>
          <Input
            type="number"
            min="1"
            step="1"
            value={cfg.auto_sweep_min_amount ?? 10}
            onChange={e => setCfg(p => ({ ...p, auto_sweep_min_amount: e.target.value }))}
            className="bg-[#1A1A24] border-white/10 text-white"
            data-testid="auto-sweep-min-amount"
          />
        </div>
      </div>

      {cfg.auto_sweep_last_run_at && (
        <p className="text-xs text-[#A0A0AB] mb-4">
          Last run: <span className="text-white">{new Date(cfg.auto_sweep_last_run_at).toLocaleString()}</span>
        </p>
      )}

      <div className="flex gap-2">
        <Button onClick={save} disabled={saving} className="bg-[#00E5FF] text-black hover:bg-[#00B3CC] font-bold" data-testid="auto-sweep-save">
          {saving ? 'Saving…' : 'Save'}
        </Button>
        <Button
          onClick={runNow}
          disabled={running || !cfg.automated_enabled}
          variant="ghost"
          className="border border-white/10 text-white hover:bg-white/5"
          data-testid="auto-sweep-run-now"
        >
          <PlayCircle className="w-4 h-4 mr-2" />
          {running ? 'Running…' : 'Run sweep now'}
        </Button>
      </div>
    </div>
  );
}
