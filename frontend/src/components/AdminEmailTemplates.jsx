import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Envelope, FloppyDisk, Info } from '@phosphor-icons/react';
import { Button } from './ui/button';
import { Input } from './ui/input';

const API = process.env.REACT_APP_BACKEND_URL;

const TEMPLATE_KEYS = [
  { key: 'verification', label: 'Email verification' },
  { key: 'welcome', label: 'Welcome (after verification)' },
  { key: 'password_reset', label: 'Password reset' },
];

export default function AdminEmailTemplates() {
  const [templates, setTemplates] = useState({});
  const [vars, setVars] = useState({});
  const [active, setActive] = useState('verification');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');

  useEffect(() => {
    axios.get(`${API}/api/admin/email-templates`, { withCredentials: true })
      .then(res => {
        setTemplates(res.data.templates || {});
        setVars(res.data.available_vars || {});
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true);
    setMsg('');
    try {
      await axios.put(`${API}/api/admin/email-templates`, { templates }, { withCredentials: true });
      setMsg('Saved ✓');
      setTimeout(() => setMsg(''), 2500);
    } catch (e) {
      setMsg(e.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const update = (key, field, value) => {
    setTemplates(prev => ({
      ...prev,
      [key]: { ...(prev[key] || {}), [field]: value },
    }));
  };

  if (loading) return <div className="text-[#A0A0AB] text-sm p-4">Loading email templates…</div>;

  const current = templates[active] || { subject: '', html: '', text: '' };
  const availableVars = vars[active] || [];

  return (
    <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-6 mt-6" data-testid="admin-email-templates">
      <div className="flex items-center gap-2 mb-4">
        <Envelope className="w-6 h-6 text-[#00E5FF]" weight="fill" />
        <h3 className="text-lg font-semibold text-white">Email templates</h3>
      </div>
      <p className="text-sm text-[#A0A0AB] mb-4">Customize the subject, HTML, and plaintext body for system emails. Leave fields blank to use defaults.</p>

      {/* Tabs */}
      <div className="flex gap-2 mb-4 border-b border-white/5">
        {TEMPLATE_KEYS.map(t => (
          <button
            key={t.key}
            onClick={() => setActive(t.key)}
            className={`px-3 py-2 text-sm border-b-2 transition ${
              active === t.key ? 'border-[#00E5FF] text-white' : 'border-transparent text-[#A0A0AB] hover:text-white'
            }`}
            data-testid={`email-tpl-tab-${t.key}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Available variables */}
      {availableVars.length > 0 && (
        <div className="flex items-start gap-2 bg-[#1A1A24] rounded-lg px-3 py-2 mb-4 text-xs text-[#A0A0AB]">
          <Info className="w-4 h-4 text-[#00E5FF] mt-0.5" />
          <div>
            Available variables:
            {' '}
            {availableVars.map(v => (
              <code key={v} className="inline-block bg-black/30 text-[#00E5FF] px-1.5 py-0.5 rounded mx-1">{`{${v}}`}</code>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-3">
        <div>
          <label className="text-xs text-[#A0A0AB] block mb-1">Subject</label>
          <Input
            value={current.subject || ''}
            onChange={e => update(active, 'subject', e.target.value)}
            className="bg-[#1A1A24] border-white/10 text-white"
            data-testid={`email-tpl-${active}-subject`}
          />
        </div>
        <div>
          <label className="text-xs text-[#A0A0AB] block mb-1">HTML body</label>
          <textarea
            value={current.html || ''}
            onChange={e => update(active, 'html', e.target.value)}
            rows={12}
            spellCheck={false}
            className="w-full bg-[#1A1A24] border border-white/10 rounded-lg p-3 text-xs text-white font-mono"
            data-testid={`email-tpl-${active}-html`}
          />
        </div>
        <div>
          <label className="text-xs text-[#A0A0AB] block mb-1">Plaintext body (fallback)</label>
          <textarea
            value={current.text || ''}
            onChange={e => update(active, 'text', e.target.value)}
            rows={3}
            spellCheck={false}
            className="w-full bg-[#1A1A24] border border-white/10 rounded-lg p-3 text-xs text-white font-mono"
            data-testid={`email-tpl-${active}-text`}
          />
        </div>
      </div>

      <div className="mt-4 flex items-center gap-3">
        <Button
          onClick={save}
          disabled={saving}
          className="bg-[#00E5FF] text-black hover:bg-[#00B3CC] font-bold"
          data-testid="email-tpl-save"
        >
          <FloppyDisk className="w-4 h-4 mr-2" /> {saving ? 'Saving…' : 'Save templates'}
        </Button>
        {msg && <span className="text-xs text-[#A0A0AB]">{msg}</span>}
      </div>
    </div>
  );
}
