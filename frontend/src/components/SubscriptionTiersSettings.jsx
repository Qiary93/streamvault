import React, { useState, useEffect } from 'react';
import { X, Upload } from '@phosphor-icons/react';
import { toast } from 'sonner';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

export default function SubscriptionTiersSettings() {
  const [tiers, setTiers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const fetchTiers = async () => {
    try {
      const res = await axios.get(`${API}/api/my/subscription-tiers`, { withCredentials: true });
      if (res.data && res.data.length > 0) {
        setTiers(res.data.map(t => ({ tier_id: t.tier_id, name: t.name, amount: t.amount, perks: t.perks || '', badge_url: t.badge_url || '' })));
      } else {
        setTiers([{ name: 'Tier 1', amount: 4.99, perks: '', badge_url: '' }]);
      }
    } catch (e) {
      setTiers([{ name: 'Tier 1', amount: 4.99, perks: '', badge_url: '' }]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchTiers(); }, []);

  const addTier = () => {
    if (tiers.length >= 5) return;
    setTiers(prev => [...prev, { name: `Tier ${prev.length + 1}`, amount: 0, perks: '', badge_url: '' }]);
  };

  const removeTier = (i) => setTiers(prev => prev.filter((_, idx) => idx !== i));

  const updateTier = (i, field, value) => {
    setTiers(prev => prev.map((t, idx) => idx === i ? { ...t, [field]: value } : t));
  };

  const uploadBadge = async (i, file) => {
    const tier = tiers[i];
    if (!tier.tier_id) {
      toast.info('Save tiers first, then upload a badge');
      return;
    }
    if (file.size > 256 * 1024) { toast.error('Badge must be under 256KB'); return; }
    const fd = new FormData();
    fd.append('file', file);
    try {
      const res = await axios.post(`${API}/api/my/tiers/${tier.tier_id}/badge`, fd, {
        withCredentials: true,
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      updateTier(i, 'badge_url', res.data.badge_url);
      toast.success('Badge uploaded');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Upload failed');
    }
  };

  const removeBadge = async (i) => {
    const tier = tiers[i];
    if (!tier.tier_id || !tier.badge_url) return;
    try {
      await axios.delete(`${API}/api/my/tiers/${tier.tier_id}/badge`, { withCredentials: true });
      updateTier(i, 'badge_url', '');
      toast.success('Badge removed');
    } catch {
      toast.error('Remove failed');
    }
  };

  const saveTiers = async () => {
    setSaving(true);
    try {
      await axios.post(`${API}/api/my/subscription-tiers`, { tiers }, { withCredentials: true });
      toast.success('Subscription tiers saved!');
      // Re-fetch to get tier_ids
      fetchTiers();
    } catch (e) {
      toast.error('Failed to save tiers');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return null;

  return (
    <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-6" data-testid="sub-tiers-settings">
      <h2 className="text-lg font-semibold text-white mb-1">Subscription Tiers</h2>
      <p className="text-sm text-[#A0A0AB] mb-4">Customize subscription tiers for your channel (max 5). Each tier supports a 32×32 badge.</p>
      <div className="space-y-3">
        {tiers.map((tier, i) => (
          <div key={i} className="flex items-start gap-3 p-3 bg-[#1A1A24] rounded-lg" data-testid={`tier-row-${i}`}>
            <div className="flex-1 grid grid-cols-1 md:grid-cols-[1fr_110px_1fr_auto] gap-3 items-center">
              <input
                value={tier.name}
                onChange={(e) => updateTier(i, 'name', e.target.value)}
                placeholder="Tier name"
                className="px-3 py-2 bg-[#292938] border border-white/10 rounded text-white text-sm focus:outline-none focus:border-[#00E5FF]"
                data-testid={`tier-name-${i}`}
              />
              <div className="relative">
                <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#A0A0AB] text-sm">$</span>
                <input
                  type="number" min="0.99" step="0.01" value={tier.amount}
                  onChange={(e) => updateTier(i, 'amount', parseFloat(e.target.value) || 0)}
                  className="w-full pl-7 pr-3 py-2 bg-[#292938] border border-white/10 rounded text-white text-sm focus:outline-none focus:border-[#00E5FF]"
                  data-testid={`tier-amount-${i}`}
                />
              </div>
              <input
                value={tier.perks}
                onChange={(e) => updateTier(i, 'perks', e.target.value)}
                placeholder="Perks description"
                className="px-3 py-2 bg-[#292938] border border-white/10 rounded text-white text-sm focus:outline-none focus:border-[#00E5FF]"
                data-testid={`tier-perks-${i}`}
              />
              {/* Badge */}
              <div className="flex items-center gap-2">
                {tier.badge_url ? (
                  <div className="flex items-center gap-1">
                    <img src={tier.badge_url.startsWith('http') ? tier.badge_url : `${API}${tier.badge_url}`} alt="badge" className="w-8 h-8 rounded bg-[#292938] object-contain border border-white/10" data-testid={`tier-badge-img-${i}`} />
                    <button onClick={() => removeBadge(i)} className="text-[10px] text-red-400 hover:text-red-300 whitespace-nowrap" data-testid={`tier-badge-remove-${i}`}>Remove</button>
                  </div>
                ) : (
                  <label className="flex items-center gap-1 px-2 py-1.5 bg-[#292938] border border-white/10 rounded text-xs text-[#A0A0AB] hover:text-white cursor-pointer whitespace-nowrap" data-testid={`tier-badge-upload-${i}`}>
                    <Upload className="w-3.5 h-3.5" /> Badge 32×32
                    <input type="file" accept="image/*" onChange={(e) => e.target.files?.[0] && uploadBadge(i, e.target.files[0])} className="hidden" />
                  </label>
                )}
              </div>
            </div>
            <button onClick={() => removeTier(i)} className="p-2 text-red-400 hover:text-red-300 hover:bg-red-500/10 rounded" data-testid={`tier-remove-${i}`}>
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>
      <div className="flex items-center gap-3 mt-4">
        {tiers.length < 5 && (
          <button onClick={addTier} className="px-4 py-2 bg-[#292938] text-[#A0A0AB] hover:text-white border border-white/10 rounded-lg text-sm transition-colors" data-testid="add-tier-btn">
            + Add Tier
          </button>
        )}
        <button onClick={saveTiers} disabled={saving} className="px-4 py-2 bg-[#00E5FF] text-black font-bold rounded-lg hover:bg-[#00B3CC] disabled:opacity-50 text-sm" data-testid="save-tiers-btn">
          {saving ? 'Saving...' : 'Save Tiers'}
        </button>
      </div>
    </div>
  );
}
