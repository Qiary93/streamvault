import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Megaphone, TrendUp, Eye, CurrencyDollar } from '@phosphor-icons/react';
import { toast } from 'sonner';

const API = process.env.REACT_APP_BACKEND_URL;

const PLACEMENT_LABELS = {
  live_pre_roll: 'Live Pre-roll',
  live_mid_roll: 'Live Mid-roll',
  vod_pre_roll: 'VOD Pre-roll',
  vod_mid_roll: 'VOD Mid-roll',
};

export default function MonetizationSection() {
  const [earnings, setEarnings] = useState(null);
  const [adSettings, setAdSettings] = useState(null);
  const [optOut, setOptOut] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [e, s, o] = await Promise.all([
          axios.get(`${API}/api/my/ad-earnings`, { withCredentials: true }),
          axios.get(`${API}/api/ads/active?placement=live_pre_roll`).catch(() => ({ data: { enabled: false } })),
          axios.get(`${API}/api/my/ad-opt-out`, { withCredentials: true }).catch(() => ({ data: { opt_out: false } })),
        ]);
        setEarnings(e.data);
        setAdSettings(s.data);
        setOptOut(!!o.data.opt_out);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const toggleOptOut = async () => {
    const next = !optOut;
    try {
      await axios.put(`${API}/api/my/ad-opt-out`, { opt_out: next }, { withCredentials: true });
      setOptOut(next);
      toast.success(next ? 'Ads disabled on your streams' : 'Ads re-enabled on your streams');
    } catch {
      toast.error('Failed to update preference');
    }
  };

  if (loading) return null;

  const adsEnabled = !!adSettings?.enabled;

  return (
    <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-6" data-testid="monetization-section">
      <div className="flex items-center justify-between flex-wrap gap-3 mb-5">
        <div className="flex items-center gap-3">
          <Megaphone className="w-6 h-6 text-[#00E5FF]" />
          <div>
            <h2 className="text-lg font-semibold text-white">Monetization</h2>
            <p className="text-sm text-[#A0A0AB]">Earn from ads shown on your live streams & VODs</p>
          </div>
        </div>
        <span className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold ${adsEnabled ? 'text-green-400 bg-green-500/10' : 'text-[#A0A0AB] bg-[#1A1A24]'}`} data-testid="ads-platform-status">
          Platform ads: {adsEnabled ? 'ACTIVE' : 'DISABLED'}
        </span>
      </div>

      {/* Ad opt-out toggle */}
      <label className="flex items-center gap-3 p-3 bg-[#1A1A24] rounded-lg cursor-pointer mb-4" data-testid="ad-opt-out-row">
        <input type="checkbox" checked={optOut} onChange={toggleOptOut} className="accent-red-500" data-testid="ad-opt-out-toggle" />
        <div className="flex-1">
          <p className="text-sm text-white font-medium">Disable ads on my streams</p>
          <p className="text-xs text-[#A0A0AB]">When enabled, viewers on your streams and VODs will not see ads. You will not earn from ads.</p>
        </div>
      </label>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-5">
        <div className="p-4 bg-[#1A1A24] rounded-lg" data-testid="ad-total-impressions">
          <div className="flex items-center gap-2 mb-1">
            <Eye className="w-4 h-4 text-[#A0A0AB]" />
            <p className="text-xs text-[#A0A0AB]">Total impressions</p>
          </div>
          <p className="text-xl font-bold text-white">{earnings?.total_impressions?.toLocaleString() || 0}</p>
        </div>
        <div className="p-4 bg-[#1A1A24] rounded-lg" data-testid="ad-total-earned">
          <div className="flex items-center gap-2 mb-1">
            <CurrencyDollar className="w-4 h-4 text-green-400" />
            <p className="text-xs text-[#A0A0AB]">Ad earnings</p>
          </div>
          <p className="text-xl font-bold text-green-400">${earnings?.total_earned?.toFixed(2) || '0.00'}</p>
        </div>
        <div className="p-4 bg-[#1A1A24] rounded-lg" data-testid="ad-placements">
          <div className="flex items-center gap-2 mb-1">
            <TrendUp className="w-4 h-4 text-[#00E5FF]" />
            <p className="text-xs text-[#A0A0AB]">Active placements</p>
          </div>
          <p className="text-xl font-bold text-white">{Object.keys(earnings?.by_placement || {}).length}</p>
        </div>
      </div>

      {earnings && Object.keys(earnings.by_placement || {}).length > 0 ? (
        <div>
          <h3 className="text-sm font-semibold text-white mb-2">Earnings by placement</h3>
          <div className="space-y-2">
            {Object.entries(earnings.by_placement).map(([place, v]) => (
              <div key={place} className="flex items-center justify-between p-3 bg-[#1A1A24] rounded-lg" data-testid={`placement-${place}`}>
                <div>
                  <p className="text-sm text-white font-medium">{PLACEMENT_LABELS[place] || place}</p>
                  <p className="text-xs text-[#A0A0AB]">{v.impressions.toLocaleString()} impressions</p>
                </div>
                <p className="text-lg font-bold text-green-400">${v.earned.toFixed(2)}</p>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="p-4 bg-[#1A1A24] rounded-lg text-center text-sm text-[#A0A0AB]">
          {adsEnabled ? 'Your ads will start earning as soon as viewers watch them on your streams and VODs.' : 'Platform-wide ads are currently disabled. Once admin enables them, you will start earning from every ad impression.'}
        </div>
      )}
    </div>
  );
}
