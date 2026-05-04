import React, { useEffect, useState, useRef } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  ArrowsClockwise, Download, GitBranch, CheckCircle, Warning, Spinner,
  Code, ClockCounterClockwise, Notebook, Heart,
} from '@phosphor-icons/react';
import { Button } from './ui/button';

const API = process.env.REACT_APP_BACKEND_URL;

const PAYPAL_EMAIL = 'stancu.daniel1993@gmail.com';

function DonateSection() {
  const [amount, setAmount] = useState('10');

  const donate = (e) => {
    e.preventDefault();
    const n = parseFloat(amount);
    if (!n || n <= 0) {
      toast.error('Please enter a valid amount');
      return;
    }
    // PayPal donation URL — opens PayPal checkout with the email + amount
    // pre-filled. Donor can still change currency / amount on the PayPal page.
    const params = new URLSearchParams({
      business: PAYPAL_EMAIL,
      cmd: '_donations',
      currency_code: 'USD',
      item_name: 'StreamVault project support',
      amount: n.toFixed(2),
    });
    const url = `https://www.paypal.com/cgi-bin/webscr?${params.toString()}`;
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  const preset = (v) => setAmount(String(v));

  return (
    <div
      className="bg-[#1A1A24] rounded-lg p-4 mt-3 border border-[#00E5FF]/10"
      data-testid="admin-updates-donate"
    >
      <div className="flex items-center gap-2 mb-3">
        <Heart weight="fill" className="w-4 h-4 text-[#EE5A6F]" />
        <h4 className="text-sm font-semibold text-white">Support the project</h4>
      </div>

      <form onSubmit={donate} className="flex flex-wrap items-center gap-2 mb-3">
        <div className="flex items-center gap-1">
          {[5, 10, 25, 50, 100].map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => preset(v)}
              className={`h-8 px-2.5 rounded text-xs font-semibold transition-colors border ${
                Number(amount) === v
                  ? 'bg-[#00E5FF] text-black border-[#00E5FF]'
                  : 'bg-transparent text-white border-white/10 hover:bg-white/5'
              }`}
              data-testid={`donate-preset-${v}`}
            >
              ${v}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1">
          <span className="text-[#A0A0AB] text-sm pl-1">$</span>
          <input
            type="number"
            min="1"
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="h-8 w-24 bg-[#0F0F16] border border-white/10 rounded px-2 text-white text-sm focus:border-[#00E5FF] focus:outline-none"
            placeholder="Amount"
            data-testid="donate-amount-input"
          />
        </div>

        <Button
          type="submit"
          className="bg-[#0070BA] hover:bg-[#005EA6] text-white font-bold h-8"
          data-testid="donate-paypal-btn"
        >
          <Heart weight="fill" className="w-3.5 h-3.5 mr-1.5" />
          Donate with PayPal
        </Button>
      </form>

      <p className="text-xs text-[#A0A0AB] leading-relaxed" data-testid="donate-message">
        This is a free project made by <span className="text-white font-semibold">Qiary93</span>. Please Donate for the project to evolve further. If you have any ideas how this project can be improved, please send an email to:{' '}
        <a
          href={`mailto:${PAYPAL_EMAIL}`}
          className="text-[#00E5FF] hover:underline font-mono"
        >
          {PAYPAL_EMAIL}
        </a>{' '}
        with your ideas.
      </p>
    </div>
  );
}

const STATUS_LABELS = {
  idle:        { color: 'text-[#A0A0AB]', icon: GitBranch,    label: 'Idle' },
  queued:      { color: 'text-[#FFC75F]', icon: Spinner,      label: 'Queued' },
  running:     { color: 'text-[#FFC75F]', icon: Spinner,      label: 'Running' },
  success:     { color: 'text-[#4ADE80]', icon: CheckCircle,  label: 'Success' },
  error:       { color: 'text-red-400',   icon: Warning,      label: 'Error' },
  unsupported: { color: 'text-[#A0A0AB]', icon: Warning,      label: 'Unsupported' },
};

const formatTime = (iso) => {
  if (!iso) return '';
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
};

export default function AdminUpdatesPanel() {
  const [check, setCheck] = useState(null);
  const [status, setStatus] = useState(null);
  const [history, setHistory] = useState([]);
  const [loadingCheck, setLoadingCheck] = useState(false);
  const [applying, setApplying] = useState(false);
  const [rollingBackSha, setRollingBackSha] = useState(null);
  const pollRef = useRef(null);

  const fetchStatus = async () => {
    try {
      const res = await axios.get(`${API}/api/admin/updates/status`, { withCredentials: true });
      setStatus(res.data);
      const s = res.data?.status;
      if (s !== 'running' && s !== 'queued' && pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
        // Job ended — refresh history + version info.
        fetchHistory();
        runCheck();
      }
    } catch (e) {
      setStatus(prev => prev || { status: 'running', message: 'Backend restarting after rebuild…' });
    }
  };

  const fetchHistory = async () => {
    try {
      const res = await axios.get(`${API}/api/admin/updates/history`, { withCredentials: true });
      setHistory(Array.isArray(res.data) ? res.data : []);
    } catch (e) {
      // Non-fatal; auto-update may not be supported on this install.
    }
  };

  const startPolling = () => {
    if (pollRef.current) return;
    pollRef.current = setInterval(fetchStatus, 3000);
  };

  useEffect(() => {
    fetchStatus();
    runCheck();
    fetchHistory();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runCheck = async () => {
    setLoadingCheck(true);
    try {
      const res = await axios.get(`${API}/api/admin/updates/check`, { withCredentials: true });
      setCheck(res.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Check failed');
    } finally { setLoadingCheck(false); }
  };

  const applyUpdate = async () => {
    if (!window.confirm('Apply update?\n\nA pre-update database backup will be taken automatically. The website will briefly go offline (~1–3 min) during the rebuild.')) return;
    setApplying(true);
    try {
      const res = await axios.post(`${API}/api/admin/updates/apply`, {}, { withCredentials: true });
      if (!res.data.ok) {
        toast.error(res.data.message || 'Update could not be queued');
      } else {
        toast.success(res.data.message);
        startPolling();
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Apply failed');
    } finally { setApplying(false); }
  };

  const rollbackTo = async (sha) => {
    if (!sha) return;
    if (!window.confirm(`Roll back to ${sha.slice(0, 7)}?\n\nThe database will be restored from the backup taken before that update, and the site will rebuild on the previous code. This is destructive — any data created since that backup will be lost.`)) return;
    setRollingBackSha(sha);
    try {
      const res = await axios.post(
        `${API}/api/admin/updates/rollback`,
        { target_sha: sha },
        { withCredentials: true }
      );
      if (!res.data.ok) {
        toast.error(res.data.message || 'Rollback could not be queued');
      } else {
        toast.success(res.data.message || 'Rollback queued');
        startPolling();
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Rollback failed');
    } finally { setRollingBackSha(null); }
  };

  // Unsupported install (e.g. running inside the Emergent sandbox).
  if (check && check.supported === false) {
    return (
      <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-6 mt-6" data-testid="admin-updates">
        <h3 className="text-lg font-semibold text-white mb-2 flex items-center gap-2">
          <ArrowsClockwise className="w-5 h-5 text-[#00E5FF]" /> Updates
        </h3>
        <p className="text-sm text-[#A0A0AB]">
          Auto-update is not available on this install. To enable it on a future deploy,
          re-run <code className="bg-[#1A1A24] px-1.5 py-0.5 rounded text-[#00E5FF]">deploy/scripts/install.sh</code>{' '}
          on your VPS.
        </p>
        <p className="text-xs text-[#A0A0AB] mt-2">{check.message}</p>
        <DonateSection />
      </div>
    );
  }

  const statusKey = status?.status || 'idle';
  const meta = STATUS_LABELS[statusKey] || STATUS_LABELS.idle;
  const isBusy = statusKey === 'running' || statusKey === 'queued';

  return (
    <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-6 mt-6" data-testid="admin-updates">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <ArrowsClockwise className="w-5 h-5 text-[#00E5FF]" />
            Updates
          </h3>
          <p className="text-sm text-[#A0A0AB] mt-1">
            Automatic Updates, please make a backup of everything before proceeding. Pre-update DB backups + rollback included.
          </p>
        </div>
        <Button
          onClick={runCheck}
          disabled={loadingCheck}
          variant="ghost"
          className="border border-white/10 text-white hover:bg-white/5"
          data-testid="updates-check-btn"
        >
          <ArrowsClockwise className={`w-4 h-4 mr-2 ${loadingCheck ? 'animate-spin' : ''}`} />
          {loadingCheck ? 'Checking…' : 'Check for updates'}
        </Button>
      </div>

      {/* Current / latest version */}
      {check && check.supported !== false && (
        <div className="bg-[#1A1A24] rounded-lg p-4 mb-3" data-testid="updates-version-info">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div>
              <p className="text-xs text-[#A0A0AB]">Current version</p>
              <p className="text-white font-mono text-sm" data-testid="updates-current-sha">
                <Code className="w-3.5 h-3.5 inline mr-1" />
                {check.current_short || '—'} <span className="text-[#A0A0AB]">on {check.branch}</span>
              </p>
            </div>
            <div className="text-right">
              <p className="text-xs text-[#A0A0AB]">Latest on origin</p>
              <p className="text-white font-mono text-sm" data-testid="updates-latest-sha">
                <Code className="w-3.5 h-3.5 inline mr-1" />
                {check.latest_short || '—'}
              </p>
            </div>
          </div>

          {check.behind === 0 ? (
            <div className="mt-3 p-3 rounded bg-[#4ADE80]/10 border border-[#4ADE80]/20" data-testid="updates-up-to-date">
              <div className="flex items-center gap-2 text-sm text-[#4ADE80] font-semibold">
                <CheckCircle weight="fill" className="w-4 h-4" /> You're up to date
              </div>
              {check.current_sha && (
                <p className="text-xs text-[#A0A0AB] mt-1 font-mono break-all">
                  Verified at SHA <span className="text-white">{check.current_sha}</span>
                </p>
              )}
            </div>
          ) : (
            <div className="mt-3">
              <div className="flex items-center gap-2 text-sm text-[#FFC75F] mb-2">
                <Download weight="fill" className="w-4 h-4" />
                {check.behind} new commit{check.behind === 1 ? '' : 's'} available
              </div>
              {check.commits?.length > 0 && (
                <div className="space-y-1.5 max-h-48 overflow-y-auto pl-1 mb-3" data-testid="updates-commits-list">
                  {check.commits.map(c => (
                    <div key={c.sha} className="text-xs border-l-2 border-[#00E5FF]/30 pl-2">
                      <span className="font-mono text-[#00E5FF]">{c.sha}</span>{' '}
                      <span className="text-white">{c.subject}</span>
                      <div className="text-[#A0A0AB]">— {c.author}, {c.when}</div>
                    </div>
                  ))}
                </div>
              )}
              <Button
                onClick={applyUpdate}
                disabled={applying || isBusy}
                className="bg-[#00E5FF] text-black hover:bg-[#00B3CC] font-bold"
                data-testid="updates-apply-btn"
              >
                <Download weight="fill" className="w-4 h-4 mr-2" />
                {applying ? 'Queuing…' : isBusy ? 'Update in progress…' : 'Update now'}
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Changelog */}
      {check?.changelog && (
        <div className="bg-[#1A1A24] rounded-lg p-4 mb-3" data-testid="updates-changelog">
          <div className="flex items-center gap-2 mb-2">
            <Notebook className="w-4 h-4 text-[#00E5FF]" />
            <h4 className="text-sm font-semibold text-white">Latest changelog</h4>
          </div>
          <pre className="text-xs text-[#D0D0DB] whitespace-pre-wrap font-sans leading-relaxed max-h-72 overflow-auto">
{check.changelog}
          </pre>
        </div>
      )}

      {/* Live job status */}
      {status && status.status && status.status !== 'idle' && status.status !== 'unsupported' && (
        <div className="bg-[#1A1A24] rounded-lg p-4 mb-3" data-testid="updates-job-status">
          <div className={`flex items-center gap-2 text-sm ${meta.color} mb-2`}>
            <meta.icon weight="fill" className={`w-4 h-4 ${isBusy ? 'animate-spin' : ''}`} />
            <span className="font-semibold">{meta.label}</span>
            {status.mode === 'rollback' && <span className="text-[#FFC75F]">— rollback</span>}
            {status.stage && <span className="text-[#A0A0AB]">— {status.stage}</span>}
          </div>
          {status.message && <p className="text-sm text-[#A0A0AB] mb-2">{status.message}</p>}
          {status.started_at && (
            <p className="text-xs text-[#A0A0AB]">
              Started {new Date(status.started_at).toLocaleTimeString()}{' '}
              {status.finished_at && `• finished ${new Date(status.finished_at).toLocaleTimeString()}`}
            </p>
          )}
          {status.log_tail && (
            <pre className="mt-3 bg-black/40 text-[#A0A0AB] text-xs p-3 rounded max-h-64 overflow-auto whitespace-pre-wrap" data-testid="updates-log-tail">
{status.log_tail}
            </pre>
          )}
        </div>
      )}

      {/* History + Rollback */}
      {history.length > 0 && (
        <div className="bg-[#1A1A24] rounded-lg p-4" data-testid="updates-history">
          <div className="flex items-center gap-2 mb-3">
            <ClockCounterClockwise className="w-4 h-4 text-[#00E5FF]" />
            <h4 className="text-sm font-semibold text-white">Recent updates</h4>
            <span className="text-xs text-[#A0A0AB]">({history.length})</span>
          </div>

          <div className="space-y-2 max-h-72 overflow-auto">
            {history.map((item, idx) => {
              const sha = item.previous_sha || item.from_sha || item.rollback_to || item.target_sha;
              const newSha = item.new_sha || item.to_sha || item.applied_sha;
              const ts = item.finished_at || item.started_at || item.requested_at;
              const ok = (item.status || '').toLowerCase() === 'success';
              const mode = item.mode || (item.rollback_to ? 'rollback' : 'update');
              const canRollback = !!sha && ok && !isBusy && mode !== 'rollback';

              return (
                <div
                  key={`${ts}-${idx}`}
                  className="flex items-center justify-between gap-3 border border-white/5 rounded p-2 text-xs"
                  data-testid="updates-history-row"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`font-semibold ${ok ? 'text-[#4ADE80]' : 'text-red-400'}`}>
                        {ok ? '✓' : '✗'} {mode === 'rollback' ? 'Rollback' : 'Update'}
                      </span>
                      {sha && (
                        <span className="font-mono text-[#A0A0AB]">
                          from <span className="text-white">{sha.slice(0, 7)}</span>
                        </span>
                      )}
                      {newSha && (
                        <span className="font-mono text-[#A0A0AB]">
                          → <span className="text-[#00E5FF]">{newSha.slice(0, 7)}</span>
                        </span>
                      )}
                    </div>
                    <div className="text-[#A0A0AB] mt-0.5">{formatTime(ts)}</div>
                    {item.message && (
                      <div className="text-[#A0A0AB] truncate mt-0.5" title={item.message}>{item.message}</div>
                    )}
                  </div>
                  {canRollback && (
                    <Button
                      onClick={() => rollbackTo(sha)}
                      disabled={!!rollingBackSha}
                      variant="ghost"
                      className="border border-white/10 text-white hover:bg-white/5 shrink-0 h-8 px-3"
                      data-testid={`updates-rollback-btn-${sha.slice(0, 7)}`}
                    >
                      <ArrowsClockwise className={`w-3.5 h-3.5 mr-1 ${rollingBackSha === sha ? 'animate-spin' : ''}`} />
                      {rollingBackSha === sha ? 'Queuing…' : 'Rollback'}
                    </Button>
                  )}
                </div>
              );
            })}
          </div>
          <p className="text-[10px] text-[#A0A0AB] mt-3">
            Rollback restores both the code (git) and the database backup taken before that update.
          </p>
        </div>
      )}

      <DonateSection />
    </div>
  );
}
