import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Megaphone, Plus, TrashSimple, Code, CurrencyDollar, ToggleRight, ChartBar } from '@phosphor-icons/react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';

const API = process.env.REACT_APP_BACKEND_URL;

const PLACEMENTS = [
  { value: 'live_pre_roll', label: 'Live Pre-roll' },
  { value: 'live_mid_roll', label: 'Live Mid-roll' },
  { value: 'vod_pre_roll', label: 'VOD Pre-roll' },
  { value: 'vod_mid_roll', label: 'VOD Mid-roll' },
];

const AD_TYPES = [
  { value: 'html', label: 'HTML / ad-network code' },
  { value: 'video', label: 'Video file (URL)' },
  { value: 'image', label: 'Image banner (URL)' },
];

export default function AdminMonetization() {
  const [settings, setSettings] = useState(null);
  const [earnings, setEarnings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [s, e] = await Promise.all([
          axios.get(`${API}/api/admin/ad-settings`, { withCredentials: true }),
          axios.get(`${API}/api/admin/ad-earnings`, { withCredentials: true }),
        ]);
        setSettings(s.data);
        setEarnings(e.data);
      } catch (err) {
        toast.error('Failed to load monetization settings');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const updateSlot = (idx, patch) => {
    setSettings(prev => ({
      ...prev,
      ad_slots: prev.ad_slots.map((s, i) => i === idx ? { ...s, ...patch } : s),
    }));
  };

  const addSlot = () => {
    setSettings(prev => ({
      ...prev,
      ad_slots: [...(prev.ad_slots || []), {
        slot_id: `slot_${Math.random().toString(36).slice(2, 10)}`,
        name: 'New ad',
        placement: 'live_pre_roll',
        ad_type: 'html',
        ad_code: '',
        image_url: '',
        video_url: '',
        click_url: '',
        duration_sec: 15,
        active: true,
      }],
    }));
  };

  const removeSlot = (idx) => {
    setSettings(prev => ({ ...prev, ad_slots: prev.ad_slots.filter((_, i) => i !== idx) }));
  };

  const save = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/api/admin/ad-settings`, settings, { withCredentials: true });
      toast.success('Monetization settings saved');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  if (loading || !settings) return null;

  return (
    <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-6 mb-6" data-testid="admin-monetization">
      <div className="flex items-center justify-between flex-wrap gap-3 mb-5">
        <div className="flex items-center gap-3">
          <Megaphone className="w-6 h-6 text-[#00E5FF]" />
          <div>
            <h2 className="text-lg font-semibold text-white">Monetization</h2>
            <p className="text-sm text-[#A0A0AB]">Enable ads, manage ad creatives and pricing per view</p>
          </div>
        </div>
        <label className="flex items-center gap-2 cursor-pointer px-3 py-1.5 bg-[#1A1A24] rounded-lg" data-testid="ads-enabled-toggle">
          <input type="checkbox" checked={settings.enabled} onChange={e => setSettings(p => ({ ...p, enabled: e.target.checked }))} />
          <ToggleRight className="w-5 h-5 text-[#00E5FF]" />
          <span className="text-sm text-white font-semibold">Platform ads {settings.enabled ? 'ON' : 'OFF'}</span>
        </label>
      </div>

      {/* Earnings summary */}
      {earnings && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
          <div className="p-3 bg-[#1A1A24] rounded-lg" data-testid="admin-ad-impressions">
            <p className="text-xs text-[#A0A0AB]">Total impressions</p>
            <p className="text-lg font-bold text-white">{earnings.total_impressions.toLocaleString()}</p>
          </div>
          <div className="p-3 bg-[#1A1A24] rounded-lg" data-testid="admin-ad-platform-earned">
            <p className="text-xs text-[#A0A0AB]">Platform earned</p>
            <p className="text-lg font-bold text-[#00E5FF]">${earnings.platform_earned.toFixed(2)}</p>
          </div>
          <div className="p-3 bg-[#1A1A24] rounded-lg" data-testid="admin-ad-streamer-earned">
            <p className="text-xs text-[#A0A0AB]">Paid to streamers</p>
            <p className="text-lg font-bold text-green-400">${earnings.streamer_earned.toFixed(2)}</p>
          </div>
          <div className="p-3 bg-[#1A1A24] rounded-lg" data-testid="admin-ad-revshare">
            <p className="text-xs text-[#A0A0AB]">Revenue share</p>
            <div className="flex items-center gap-1">
              <Input type="number" min="0" max="100" step="1" value={settings.revenue_share_percent} onChange={e => setSettings(p => ({ ...p, revenue_share_percent: parseFloat(e.target.value) || 0 }))} className="bg-[#0F0F16] border-white/10 text-white h-8 w-16 text-sm" data-testid="revshare-input" />
              <span className="text-white text-sm">%</span>
            </div>
          </div>
        </div>
      )}

      {/* CPM pricing table */}
      <div className="mb-5">
        <h3 className="text-sm font-semibold text-white mb-2 flex items-center gap-2">
          <CurrencyDollar className="w-4 h-4" /> CPM pricing per 1000 views
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2" data-testid="cpm-table">
          {PLACEMENTS.map(p => (
            <div key={p.value} className="p-3 bg-[#1A1A24] rounded-lg">
              <p className="text-xs text-[#A0A0AB] mb-1">{p.label}</p>
              <div className="flex items-center gap-1">
                <span className="text-[#A0A0AB] text-sm">$</span>
                <Input
                  type="number"
                  min="0"
                  step="0.1"
                  value={settings.cpm_rates?.[p.value] ?? 0}
                  onChange={e => setSettings(prev => ({ ...prev, cpm_rates: { ...prev.cpm_rates, [p.value]: parseFloat(e.target.value) || 0 } }))}
                  className="bg-[#0F0F16] border-white/10 text-white h-8"
                  data-testid={`cpm-${p.value}`}
                />
              </div>
            </div>
          ))}
        </div>
        <p className="text-xs text-[#A0A0AB] mt-2">One impression pays CPM / 1000. Streamers receive {settings.revenue_share_percent}% of each impression.</p>
      </div>

      {/* Ad slots */}
      <div className="mb-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <Code className="w-4 h-4" /> Ad creatives & codes
          </h3>
          <Button onClick={addSlot} size="sm" className="bg-[#00E5FF] text-black hover:bg-[#00B3CC] font-bold" data-testid="add-ad-slot-btn">
            <Plus className="w-4 h-4 mr-1" /> Add ad
          </Button>
        </div>

        {(!settings.ad_slots || settings.ad_slots.length === 0) ? (
          <div className="p-4 bg-[#1A1A24] rounded-lg text-center text-sm text-[#A0A0AB]">
            No ads configured. Add an ad creative or paste a third-party ad code (e.g. Google Ad Manager VAST tag).
          </div>
        ) : (
          <div className="space-y-3">
            {settings.ad_slots.map((slot, i) => (
              <div key={slot.slot_id} className="p-4 bg-[#1A1A24] border border-white/5 rounded-lg" data-testid={`ad-slot-${i}`}>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
                  <div>
                    <label className="text-xs text-[#A0A0AB] block mb-1">Name</label>
                    <Input value={slot.name} onChange={e => updateSlot(i, { name: e.target.value })} className="bg-[#0F0F16] border-white/10 text-white" data-testid={`slot-name-${i}`} />
                  </div>
                  <div>
                    <label className="text-xs text-[#A0A0AB] block mb-1">Placement</label>
                    <Select value={slot.placement} onValueChange={v => updateSlot(i, { placement: v })}>
                      <SelectTrigger className="bg-[#0F0F16] border-white/10 text-white" data-testid={`slot-placement-${i}`}><SelectValue /></SelectTrigger>
                      <SelectContent className="bg-[#0F0F16] border-white/10">
                        {PLACEMENTS.map(p => <SelectItem key={p.value} value={p.value} className="text-white">{p.label}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <label className="text-xs text-[#A0A0AB] block mb-1">Ad type</label>
                    <Select value={slot.ad_type} onValueChange={v => updateSlot(i, { ad_type: v })}>
                      <SelectTrigger className="bg-[#0F0F16] border-white/10 text-white" data-testid={`slot-type-${i}`}><SelectValue /></SelectTrigger>
                      <SelectContent className="bg-[#0F0F16] border-white/10">
                        {AD_TYPES.map(t => <SelectItem key={t.value} value={t.value} className="text-white">{t.label}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                {slot.ad_type === 'html' && (
                  <div className="mb-3">
                    <label className="text-xs text-[#A0A0AB] block mb-1">Ad code (HTML, VAST iframe, Google Ad Manager tag, etc.)</label>
                    <textarea value={slot.ad_code} onChange={e => updateSlot(i, { ad_code: e.target.value })} rows={4} className="w-full p-3 bg-[#0F0F16] border border-white/10 rounded-md text-white text-xs font-mono" placeholder='<iframe src="..."></iframe> or <script src="..."></script>' data-testid={`slot-code-${i}`} />
                  </div>
                )}
                {slot.ad_type === 'video' && (
                  <div className="grid grid-cols-2 gap-3 mb-3">
                    <div>
                      <label className="text-xs text-[#A0A0AB] block mb-1">Video URL (mp4)</label>
                      <Input value={slot.video_url} onChange={e => updateSlot(i, { video_url: e.target.value })} placeholder="https://..." className="bg-[#0F0F16] border-white/10 text-white" data-testid={`slot-video-${i}`} />
                    </div>
                    <div>
                      <label className="text-xs text-[#A0A0AB] block mb-1">Click URL (optional)</label>
                      <Input value={slot.click_url} onChange={e => updateSlot(i, { click_url: e.target.value })} placeholder="https://advertiser.com" className="bg-[#0F0F16] border-white/10 text-white" data-testid={`slot-click-${i}`} />
                    </div>
                  </div>
                )}
                {slot.ad_type === 'image' && (
                  <div className="grid grid-cols-2 gap-3 mb-3">
                    <div>
                      <label className="text-xs text-[#A0A0AB] block mb-1">Image URL</label>
                      <Input value={slot.image_url} onChange={e => updateSlot(i, { image_url: e.target.value })} placeholder="https://..." className="bg-[#0F0F16] border-white/10 text-white" data-testid={`slot-img-${i}`} />
                    </div>
                    <div>
                      <label className="text-xs text-[#A0A0AB] block mb-1">Click URL</label>
                      <Input value={slot.click_url} onChange={e => updateSlot(i, { click_url: e.target.value })} placeholder="https://advertiser.com" className="bg-[#0F0F16] border-white/10 text-white" data-testid={`slot-click-img-${i}`} />
                    </div>
                  </div>
                )}

                <div className="flex items-center justify-between flex-wrap gap-3">
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-1">
                      <span className="text-xs text-[#A0A0AB]">Duration:</span>
                      <Input type="number" min="1" max="60" value={slot.duration_sec} onChange={e => updateSlot(i, { duration_sec: parseInt(e.target.value) || 15 })} className="bg-[#0F0F16] border-white/10 text-white h-8 w-16 text-xs" data-testid={`slot-duration-${i}`} />
                      <span className="text-xs text-[#A0A0AB]">s</span>
                    </div>
                    <label className="flex items-center gap-1 cursor-pointer">
                      <input type="checkbox" checked={slot.active} onChange={e => updateSlot(i, { active: e.target.checked })} data-testid={`slot-active-${i}`} />
                      <span className="text-xs text-white">Active</span>
                    </label>
                  </div>
                  <Button onClick={() => removeSlot(i)} variant="ghost" size="sm" className="text-red-400 hover:bg-red-500/10" data-testid={`slot-remove-${i}`}>
                    <TrashSimple className="w-4 h-4 mr-1" /> Remove
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Top earners */}
      {earnings?.top_streamers?.length > 0 && (
        <div className="mb-5">
          <h3 className="text-sm font-semibold text-white mb-2 flex items-center gap-2">
            <ChartBar className="w-4 h-4" /> Top earning streamers
          </h3>
          <div className="space-y-1">
            {earnings.top_streamers.map((s, i) => (
              <div key={s.user_id} className="flex items-center justify-between p-2 bg-[#1A1A24] rounded-lg text-sm">
                <span className="text-white">#{i + 1} {s.display_name || s.username}</span>
                <span className="text-[#A0A0AB]">{s.impressions.toLocaleString()} imps</span>
                <span className="text-green-400 font-bold">${s.earned.toFixed(2)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <Button onClick={save} disabled={saving} className="bg-[#00E5FF] text-black font-bold hover:bg-[#00B3CC]" data-testid="save-monetization-btn">
        {saving ? 'Saving…' : 'Save monetization settings'}
      </Button>
    </div>
  );
}
