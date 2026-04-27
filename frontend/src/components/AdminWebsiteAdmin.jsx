import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Globe, ShieldWarning, Broadcast, FloppyDisk, Trash, PushPin, ArrowsClockwise } from '@phosphor-icons/react';
import { Button } from './ui/button';
import { Input } from './ui/input';

const API = process.env.REACT_APP_BACKEND_URL;

const TABS = [
  { id: 'branding',  label: 'Branding',         icon: Globe },
  { id: 'users',     label: 'User control',     icon: ShieldWarning },
  { id: 'streamers', label: 'Streamer control', icon: Broadcast },
];

const DURATION_PRESETS = [
  { label: '1 hour',    seconds: 3600 },
  { label: '24 hours',  seconds: 86400 },
  { label: '7 days',    seconds: 604800 },
  { label: '30 days',   seconds: 2592000 },
  { label: 'Permanent', seconds: 0 },
];

export default function AdminWebsiteAdmin() {
  const [active, setActive] = useState('branding');

  return (
    <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-6 mt-6" data-testid="admin-website-admin">
      <h3 className="text-lg font-semibold text-white mb-4">Website Administration</h3>

      <div className="flex gap-2 mb-4 border-b border-white/5 overflow-x-auto">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setActive(t.id)}
            className={`px-3 py-2 text-sm border-b-2 transition flex items-center gap-2 whitespace-nowrap ${
              active === t.id ? 'border-[#00E5FF] text-white' : 'border-transparent text-[#A0A0AB] hover:text-white'
            }`}
            data-testid={`website-admin-tab-${t.id}`}
          >
            <t.icon className="w-4 h-4" />
            {t.label}
          </button>
        ))}
      </div>

      {active === 'branding' && <BrandingPanel />}
      {active === 'users' && <UserControlPanel />}
      {active === 'streamers' && <StreamerControlPanel />}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  BRANDING                                                                  */
/* -------------------------------------------------------------------------- */
function BrandingPanel() {
  const [data, setData] = useState({ site_name: '', tagline: '', description: '' });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    axios.get(`${API}/api/admin/branding`, { withCredentials: true })
      .then(res => setData(res.data))
      .catch(() => {});
  }, []);

  const save = async () => {
    if (!data.site_name?.trim()) { toast.error('Site name is required'); return; }
    setSaving(true);
    try {
      await axios.put(`${API}/api/admin/branding`, data, { withCredentials: true });
      toast.success('Branding saved — refresh to see the new tab title.');
      // Eagerly update the current tab title
      document.title = data.tagline ? `${data.site_name} — ${data.tagline}` : data.site_name;
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Save failed');
    } finally { setSaving(false); }
  };

  return (
    <div className="space-y-3">
      <p className="text-sm text-[#A0A0AB]">
        These values are used as the browser tab title, the SEO meta description, and anywhere the site name is rendered.
      </p>
      <div>
        <label className="text-xs text-[#A0A0AB] block mb-1">Site name</label>
        <Input
          value={data.site_name || ''}
          onChange={e => setData(d => ({ ...d, site_name: e.target.value }))}
          placeholder="StreamVault"
          maxLength={80}
          className="bg-[#1A1A24] border-white/10 text-white"
          data-testid="branding-site-name"
        />
      </div>
      <div>
        <label className="text-xs text-[#A0A0AB] block mb-1">Tagline (shown in tab title after the site name)</label>
        <Input
          value={data.tagline || ''}
          onChange={e => setData(d => ({ ...d, tagline: e.target.value }))}
          placeholder="Live streaming for everyone"
          maxLength={160}
          className="bg-[#1A1A24] border-white/10 text-white"
          data-testid="branding-tagline"
        />
      </div>
      <div>
        <label className="text-xs text-[#A0A0AB] block mb-1">Meta description (SEO)</label>
        <Input
          value={data.description || ''}
          onChange={e => setData(d => ({ ...d, description: e.target.value }))}
          placeholder="StreamVault — live streaming platform"
          maxLength={300}
          className="bg-[#1A1A24] border-white/10 text-white"
          data-testid="branding-description"
        />
      </div>
      <Button onClick={save} disabled={saving} className="bg-[#00E5FF] text-black hover:bg-[#00B3CC] font-bold" data-testid="branding-save">
        <FloppyDisk className="w-4 h-4 mr-2" /> {saving ? 'Saving…' : 'Save branding'}
      </Button>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  USER CONTROL — bans                                                       */
/* -------------------------------------------------------------------------- */
function UserControlPanel() {
  const [form, setForm] = useState({ identifier: '', ip: '', reason: '', duration: 0 });
  const [bans, setBans] = useState([]);
  const [loading, setLoading] = useState(false);

  const refresh = async () => {
    try {
      const res = await axios.get(`${API}/api/admin/bans?only_active=true`, { withCredentials: true });
      setBans(res.data || []);
    } catch {}
  };
  useEffect(() => { refresh(); }, []);

  const submit = async () => {
    const id = form.identifier.trim();
    const ip = form.ip.trim();
    if (!id && !ip) { toast.error('Provide email/username/user_id and/or IP'); return; }
    setLoading(true);
    try {
      const body = { reason: form.reason, duration_seconds: form.duration };
      if (id.includes('@')) body.email = id;
      else if (id.startsWith('user_')) body.user_id = id;
      else if (id) body.username = id;
      if (ip) body.ip = ip;
      await axios.post(`${API}/api/admin/bans`, body, { withCredentials: true });
      toast.success('User banned');
      setForm({ identifier: '', ip: '', reason: '', duration: 0 });
      refresh();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Ban failed');
    } finally { setLoading(false); }
  };

  const lift = async (banId) => {
    if (!window.confirm('Lift this ban?')) return;
    try {
      await axios.delete(`${API}/api/admin/bans/${banId}`, { withCredentials: true });
      toast.success('Ban lifted');
      refresh();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed');
    }
  };

  return (
    <div className="space-y-4">
      <div className="bg-[#1A1A24] rounded-lg p-4 space-y-3">
        <h4 className="text-sm font-semibold text-white">Ban a user</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-[#A0A0AB] block mb-1">Email, username, or user_id</label>
            <Input
              value={form.identifier}
              onChange={e => setForm(f => ({ ...f, identifier: e.target.value }))}
              placeholder="someone@example.com"
              className="bg-[#0F0F16] border-white/10 text-white"
              data-testid="ban-identifier"
            />
          </div>
          <div>
            <label className="text-xs text-[#A0A0AB] block mb-1">IP address (optional)</label>
            <Input
              value={form.ip}
              onChange={e => setForm(f => ({ ...f, ip: e.target.value }))}
              placeholder="203.0.113.42"
              className="bg-[#0F0F16] border-white/10 text-white"
              data-testid="ban-ip"
            />
          </div>
        </div>
        <div>
          <label className="text-xs text-[#A0A0AB] block mb-1">Reason (visible to the banned user on login)</label>
          <Input
            value={form.reason}
            onChange={e => setForm(f => ({ ...f, reason: e.target.value }))}
            placeholder="Spam / abuse / etc."
            className="bg-[#0F0F16] border-white/10 text-white"
            data-testid="ban-reason"
          />
        </div>
        <div>
          <label className="text-xs text-[#A0A0AB] block mb-1">Duration</label>
          <div className="flex flex-wrap gap-2">
            {DURATION_PRESETS.map(p => (
              <button
                key={p.seconds}
                type="button"
                onClick={() => setForm(f => ({ ...f, duration: p.seconds }))}
                className={`px-3 py-1.5 rounded-full text-xs font-medium transition ${
                  form.duration === p.seconds ? 'bg-red-500 text-white' : 'bg-[#0F0F16] text-[#A0A0AB] hover:text-white'
                }`}
                data-testid={`ban-duration-${p.seconds}`}
              >
                {p.label}
              </button>
            ))}
            <Input
              type="number"
              min="0"
              value={form.duration || ''}
              onChange={e => setForm(f => ({ ...f, duration: Number(e.target.value || 0) }))}
              placeholder="custom seconds"
              className="bg-[#0F0F16] border-white/10 text-white max-w-[180px]"
              data-testid="ban-duration-custom"
            />
          </div>
        </div>
        <Button onClick={submit} disabled={loading} className="bg-red-500 hover:bg-red-600 text-white font-bold" data-testid="ban-submit">
          <ShieldWarning className="w-4 h-4 mr-2" /> {loading ? 'Banning…' : 'Ban user'}
        </Button>
      </div>

      <div>
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-sm font-semibold text-white">Active bans ({bans.length})</h4>
          <button onClick={refresh} className="text-xs text-[#A0A0AB] hover:text-white inline-flex items-center gap-1">
            <ArrowsClockwise className="w-3.5 h-3.5" /> refresh
          </button>
        </div>
        {bans.length === 0 ? (
          <p className="text-xs text-[#A0A0AB]">No active bans.</p>
        ) : (
          <div className="space-y-2">
            {bans.map(b => (
              <div key={b.ban_id} className="flex items-start justify-between bg-[#1A1A24] rounded-lg p-3 text-xs" data-testid={`ban-row-${b.ban_id}`}>
                <div className="space-y-0.5">
                  <p className="text-white font-medium">
                    {b.username || b.email || b.user_id || b.ip || 'unknown'} {b.ip && b.username ? <span className="text-[#A0A0AB]">— {b.ip}</span> : null}
                  </p>
                  <p className="text-[#A0A0AB]">{b.reason || 'no reason'}</p>
                  <p className="text-[#A0A0AB]">
                    {b.permanent ? 'Permanent' : (b.expires_at ? `Until ${new Date(b.expires_at).toLocaleString()}` : '—')}
                  </p>
                </div>
                <button onClick={() => lift(b.ban_id)} className="text-red-400 hover:text-red-300" title="Lift ban" data-testid={`ban-lift-${b.ban_id}`}>
                  <Trash className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  STREAMER CONTROL                                                          */
/* -------------------------------------------------------------------------- */
function StreamerControlPanel() {
  const [form, setForm] = useState({ identifier: '', reason: '', duration: 0 });
  const [restrictions, setRestrictions] = useState([]);
  const [streams, setStreams] = useState([]);

  const refresh = async () => {
    try {
      const [r, s] = await Promise.all([
        axios.get(`${API}/api/admin/streamer-restrictions`, { withCredentials: true }),
        axios.get(`${API}/api/streams?limit=40`),
      ]);
      setRestrictions(r.data || []);
      setStreams(s.data || []);
    } catch {}
  };
  useEffect(() => { refresh(); }, []);

  const restrict = async () => {
    const id = form.identifier.trim();
    if (!id) { toast.error('Provide email/username/user_id'); return; }
    try {
      const body = { reason: form.reason, duration_seconds: form.duration };
      if (id.includes('@')) body.email = id;
      else if (id.startsWith('user_')) body.user_id = id;
      else body.username = id;
      await axios.post(`${API}/api/admin/streamer-restrictions`, body, { withCredentials: true });
      toast.success('Streamer restricted');
      setForm({ identifier: '', reason: '', duration: 0 });
      refresh();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed');
    }
  };

  const lift = async (userId) => {
    if (!window.confirm('Lift restriction?')) return;
    try {
      await axios.delete(`${API}/api/admin/streamer-restrictions/${userId}`, { withCredentials: true });
      toast.success('Restriction lifted');
      refresh();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed');
    }
  };

  const togglePin = async (stream) => {
    try {
      if (stream.pinned) {
        await axios.delete(`${API}/api/admin/streams/${stream.stream_id}/pin`, { withCredentials: true });
        toast.success('Stream unpinned');
      } else {
        await axios.post(`${API}/api/admin/streams/${stream.stream_id}/pin`, {}, { withCredentials: true });
        toast.success('Stream pinned to top');
      }
      refresh();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed');
    }
  };

  return (
    <div className="space-y-4">
      {/* Restrict streamer form */}
      <div className="bg-[#1A1A24] rounded-lg p-4 space-y-3">
        <h4 className="text-sm font-semibold text-white">Restrict a streamer from going live</h4>
        <div>
          <label className="text-xs text-[#A0A0AB] block mb-1">Email, username, or user_id</label>
          <Input
            value={form.identifier}
            onChange={e => setForm(f => ({ ...f, identifier: e.target.value }))}
            placeholder="streamer@example.com"
            className="bg-[#0F0F16] border-white/10 text-white"
            data-testid="restrict-identifier"
          />
        </div>
        <div>
          <label className="text-xs text-[#A0A0AB] block mb-1">Reason</label>
          <Input
            value={form.reason}
            onChange={e => setForm(f => ({ ...f, reason: e.target.value }))}
            placeholder="Violation of community guidelines"
            className="bg-[#0F0F16] border-white/10 text-white"
            data-testid="restrict-reason"
          />
        </div>
        <div>
          <label className="text-xs text-[#A0A0AB] block mb-1">Duration</label>
          <div className="flex flex-wrap gap-2">
            {DURATION_PRESETS.map(p => (
              <button
                key={p.seconds}
                type="button"
                onClick={() => setForm(f => ({ ...f, duration: p.seconds }))}
                className={`px-3 py-1.5 rounded-full text-xs font-medium transition ${
                  form.duration === p.seconds ? 'bg-orange-500 text-white' : 'bg-[#0F0F16] text-[#A0A0AB] hover:text-white'
                }`}
                data-testid={`restrict-duration-${p.seconds}`}
              >
                {p.label}
              </button>
            ))}
            <Input
              type="number" min="0"
              value={form.duration || ''}
              onChange={e => setForm(f => ({ ...f, duration: Number(e.target.value || 0) }))}
              placeholder="custom seconds"
              className="bg-[#0F0F16] border-white/10 text-white max-w-[180px]"
              data-testid="restrict-duration-custom"
            />
          </div>
        </div>
        <Button onClick={restrict} className="bg-orange-500 hover:bg-orange-600 text-white font-bold" data-testid="restrict-submit">
          <Broadcast className="w-4 h-4 mr-2" /> Restrict streamer
        </Button>
      </div>

      {/* Active restrictions list */}
      <div>
        <h4 className="text-sm font-semibold text-white mb-2">Active streamer restrictions ({restrictions.length})</h4>
        {restrictions.length === 0 ? (
          <p className="text-xs text-[#A0A0AB]">None.</p>
        ) : (
          <div className="space-y-2">
            {restrictions.map(r => (
              <div key={r.user_id} className="flex items-start justify-between bg-[#1A1A24] rounded-lg p-3 text-xs" data-testid={`restriction-row-${r.user_id}`}>
                <div className="space-y-0.5">
                  <p className="text-white font-medium">@{r.username} <span className="text-[#A0A0AB]">— {r.email}</span></p>
                  <p className="text-[#A0A0AB]">{r.stream_restriction_reason || 'no reason'}</p>
                  <p className="text-[#A0A0AB]">
                    {r.stream_restriction_expires_at ? `Until ${new Date(r.stream_restriction_expires_at).toLocaleString()}` : 'Permanent'}
                  </p>
                </div>
                <button onClick={() => lift(r.user_id)} className="text-orange-400 hover:text-orange-300" title="Lift restriction" data-testid={`restriction-lift-${r.user_id}`}>
                  <Trash className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Pin streams */}
      <div>
        <h4 className="text-sm font-semibold text-white mb-2">Pin a live stream to the top of the list</h4>
        {streams.length === 0 ? (
          <p className="text-xs text-[#A0A0AB]">No live streams right now.</p>
        ) : (
          <div className="space-y-2">
            {streams.map(s => (
              <div key={s.stream_id} className="flex items-center justify-between bg-[#1A1A24] rounded-lg p-3 text-xs" data-testid={`pin-row-${s.stream_id}`}>
                <div>
                  <p className="text-white font-medium">{s.title || s.stream_id}</p>
                  <p className="text-[#A0A0AB]">@{s.username} • {s.viewer_count || 0} viewers {s.pinned && <span className="text-[#00E5FF] ml-2">📌 pinned</span>}</p>
                </div>
                <Button
                  size="sm"
                  onClick={() => togglePin(s)}
                  className={s.pinned
                    ? 'bg-white/10 text-white hover:bg-white/20'
                    : 'bg-[#00E5FF] text-black hover:bg-[#00B3CC] font-bold'}
                  data-testid={`pin-toggle-${s.stream_id}`}
                >
                  <PushPin className="w-4 h-4 mr-2" weight={s.pinned ? 'fill' : 'regular'} />
                  {s.pinned ? 'Unpin' : 'Pin to top'}
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
