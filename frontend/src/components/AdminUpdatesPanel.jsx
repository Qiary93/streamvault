import React, { useEffect, useState, useRef } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { ArrowsClockwise, Download, GitBranch, CheckCircle, Warning, Spinner, Code } from '@phosphor-icons/react';
import { Button } from './ui/button';

const API = process.env.REACT_APP_BACKEND_URL;

const STATUS_LABELS = {
  idle:        { color: 'text-[#A0A0AB]', icon: GitBranch,    label: 'Idle' },
  queued:      { color: 'text-[#FFC75F]', icon: Spinner,      label: 'Queued' },
  running:     { color: 'text-[#FFC75F]', icon: Spinner,      label: 'Running' },
  success:     { color: 'text-[#4ADE80]', icon: CheckCircle,  label: 'Success' },
  error:       { color: 'text-red-400',   icon: Warning,      label: 'Error' },
  unsupported: { color: 'text-[#A0A0AB]', icon: Warning,      label: 'Unsupported' },
};

export default function AdminUpdatesPanel() {
  const [check, setCheck] = useState(null);
  const [status, setStatus] = useState(null);
  const [loadingCheck, setLoadingCheck] = useState(false);
  const [applying, setApplying] = useState(false);
  const pollRef = useRef(null);

  const fetchStatus = async () => {
    try {
      const res = await axios.get(`${API}/api/admin/updates/status`, { withCredentials: true });
      setStatus(res.data);
      const s = res.data?.status;
      if (s !== 'running' && s !== 'queued' && pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    } catch (e) {
      // Backend may be restarting during the build; tolerate transient errors
      setStatus(prev => prev || { status: 'running', message: 'Backend restarting after rebuild…' });
    }
  };

  const startPolling = () => {
    if (pollRef.current) return;
    pollRef.current = setInterval(fetchStatus, 3000);
  };

  useEffect(() => {
    fetchStatus();
    runCheck();
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
    if (!window.confirm('Apply update? The website will briefly go offline (~1–3 min) during the rebuild.')) return;
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
        <p className="text-xs text-[#A0A0AB] mt-2">
          {check.message}
        </p>
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
            One-click rebuild &amp; deploy from your GitHub repository.
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

      {/* Current version */}
      {check && check.supported !== false && (
        <div className="bg-[#1A1A24] rounded-lg p-4 mb-3" data-testid="updates-version-info">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div>
              <p className="text-xs text-[#A0A0AB]">Current version</p>
              <p className="text-white font-mono text-sm">
                <Code className="w-3.5 h-3.5 inline mr-1" />
                {check.current_short || '—'} <span className="text-[#A0A0AB]">on {check.branch}</span>
              </p>
            </div>
            <div className="text-right">
              <p className="text-xs text-[#A0A0AB]">Latest on origin</p>
              <p className="text-white font-mono text-sm">
                <Code className="w-3.5 h-3.5 inline mr-1" />
                {check.latest_short || '—'}
              </p>
            </div>
          </div>

          {check.behind === 0 ? (
            <div className="mt-3 flex items-center gap-2 text-sm text-[#4ADE80]">
              <CheckCircle weight="fill" className="w-4 h-4" /> You're up to date.
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

      {/* Live job status */}
      {status && status.status && status.status !== 'idle' && (
        <div className="bg-[#1A1A24] rounded-lg p-4" data-testid="updates-job-status">
          <div className={`flex items-center gap-2 text-sm ${meta.color} mb-2`}>
            <meta.icon weight="fill" className={`w-4 h-4 ${isBusy ? 'animate-spin' : ''}`} />
            <span className="font-semibold">{meta.label}</span>
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
    </div>
  );
}
