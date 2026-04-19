import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { EnvelopeSimple, PaperPlaneTilt } from '@phosphor-icons/react';
import { Button } from './ui/button';
import { Input } from './ui/input';

const API = process.env.REACT_APP_BACKEND_URL;

export default function AdminSmtpSettings() {
  const [cfg, setCfg] = useState({
    enabled: false, host: '', port: 587, username: '', password: '',
    from_email: '', from_name: 'StreamVault', use_tls: true, use_ssl: false,
  });
  const [testEmail, setTestEmail] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    axios.get(`${API}/api/admin/smtp-settings`, { withCredentials: true })
      .then(res => setCfg(c => ({ ...c, ...res.data })))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/api/admin/smtp-settings`, cfg, { withCredentials: true });
      toast.success('SMTP settings saved');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const sendTest = async () => {
    if (!testEmail || !testEmail.includes('@')) { toast.error('Enter a valid recipient email'); return; }
    setTesting(true);
    try {
      const res = await axios.post(`${API}/api/admin/smtp-test`, { to: testEmail }, { withCredentials: true });
      toast.success(res.data.message);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Test failed');
    } finally {
      setTesting(false);
    }
  };

  if (loading) return null;

  return (
    <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-6 mt-6" data-testid="admin-smtp-settings">
      <div className="flex items-center justify-between flex-wrap gap-3 mb-5">
        <div className="flex items-center gap-3">
          <EnvelopeSimple className="w-6 h-6 text-[#00E5FF]" />
          <div>
            <h2 className="text-lg font-semibold text-white">SMTP · Email Verification</h2>
            <p className="text-sm text-[#A0A0AB]">Configure SMTP to send verification emails on registration. When enabled, new users must verify before logging in.</p>
          </div>
        </div>
        <label className="flex items-center gap-2 cursor-pointer px-3 py-1.5 bg-[#1A1A24] rounded-lg">
          <input type="checkbox" checked={cfg.enabled} onChange={e => setCfg(p => ({ ...p, enabled: e.target.checked }))} data-testid="smtp-enabled-toggle" />
          <span className="text-sm text-white font-semibold">SMTP {cfg.enabled ? 'ON' : 'OFF'}</span>
        </label>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
        <div>
          <label className="text-xs text-[#A0A0AB] block mb-1">SMTP Host *</label>
          <Input value={cfg.host} onChange={e => setCfg(p => ({ ...p, host: e.target.value }))} placeholder="smtp.gmail.com" className="bg-[#1A1A24] border-white/10 text-white" data-testid="smtp-host" />
        </div>
        <div>
          <label className="text-xs text-[#A0A0AB] block mb-1">Port</label>
          <Input type="number" value={cfg.port} onChange={e => setCfg(p => ({ ...p, port: parseInt(e.target.value) || 587 }))} className="bg-[#1A1A24] border-white/10 text-white" data-testid="smtp-port" />
        </div>
        <div>
          <label className="text-xs text-[#A0A0AB] block mb-1">Username</label>
          <Input value={cfg.username} onChange={e => setCfg(p => ({ ...p, username: e.target.value }))} placeholder="you@domain.com" className="bg-[#1A1A24] border-white/10 text-white" data-testid="smtp-username" />
        </div>
        <div>
          <label className="text-xs text-[#A0A0AB] block mb-1">Password / App Password</label>
          <Input type="password" value={cfg.password} onChange={e => setCfg(p => ({ ...p, password: e.target.value }))} placeholder="••••••••" className="bg-[#1A1A24] border-white/10 text-white" data-testid="smtp-password" />
        </div>
        <div>
          <label className="text-xs text-[#A0A0AB] block mb-1">From Email *</label>
          <Input value={cfg.from_email} onChange={e => setCfg(p => ({ ...p, from_email: e.target.value }))} placeholder="noreply@yoursite.com" className="bg-[#1A1A24] border-white/10 text-white" data-testid="smtp-from-email" />
        </div>
        <div>
          <label className="text-xs text-[#A0A0AB] block mb-1">From Name</label>
          <Input value={cfg.from_name} onChange={e => setCfg(p => ({ ...p, from_name: e.target.value }))} placeholder="StreamVault" className="bg-[#1A1A24] border-white/10 text-white" data-testid="smtp-from-name" />
        </div>
      </div>

      <div className="flex items-center gap-4 mb-4">
        <label className="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" checked={cfg.use_tls} onChange={e => setCfg(p => ({ ...p, use_tls: e.target.checked, use_ssl: e.target.checked ? false : p.use_ssl }))} data-testid="smtp-tls" />
          <span className="text-sm text-white">STARTTLS (port 587)</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" checked={cfg.use_ssl} onChange={e => setCfg(p => ({ ...p, use_ssl: e.target.checked, use_tls: e.target.checked ? false : p.use_tls }))} data-testid="smtp-ssl" />
          <span className="text-sm text-white">SSL/TLS (port 465)</span>
        </label>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        <Button onClick={save} disabled={saving} className="bg-[#00E5FF] text-black hover:bg-[#00B3CC] font-bold" data-testid="smtp-save">
          {saving ? 'Saving…' : 'Save SMTP settings'}
        </Button>
      </div>

      {/* Test block */}
      <div className="p-3 bg-[#1A1A24] rounded-lg">
        <h4 className="text-sm font-semibold text-white mb-2 flex items-center gap-1"><PaperPlaneTilt className="w-4 h-4" /> Send test email</h4>
        <div className="flex gap-2">
          <Input value={testEmail} onChange={e => setTestEmail(e.target.value)} placeholder="you@example.com" className="bg-[#0F0F16] border-white/10 text-white" data-testid="smtp-test-to" />
          <Button onClick={sendTest} disabled={testing || !cfg.enabled} variant="ghost" className="border border-white/10 text-white hover:bg-white/5" data-testid="smtp-test-send">
            {testing ? 'Sending…' : 'Send'}
          </Button>
        </div>
        {!cfg.enabled && <p className="text-xs text-[#A0A0AB] mt-2">Enable SMTP to send a test.</p>}
      </div>
    </div>
  );
}
