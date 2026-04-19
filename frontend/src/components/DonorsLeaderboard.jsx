import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Trophy, Crown, Star } from '@phosphor-icons/react';
import VerifiedBadge from './VerifiedBadge';

const API = process.env.REACT_APP_BACKEND_URL;

const PERIODS = [
  { value: 'all', label: 'All time' },
  { value: 'month', label: 'Month' },
  { value: 'week', label: 'Week' },
];

export default function DonorsLeaderboard({ streamerId = null, title = 'Top Donors' }) {
  const [period, setPeriod] = useState('all');
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const q = new URLSearchParams();
    q.set('period', period);
    q.set('limit', '10');
    if (streamerId) q.set('streamer_id', streamerId);
    axios.get(`${API}/api/leaderboard/donors?${q.toString()}`)
      .then(res => setItems(res.data.items || []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [streamerId, period]);

  const rankIcon = (r) => {
    if (r === 1) return <Crown weight="fill" className="w-4 h-4 text-yellow-400" />;
    if (r === 2) return <Star weight="fill" className="w-4 h-4 text-zinc-300" />;
    if (r === 3) return <Star weight="fill" className="w-4 h-4 text-amber-600" />;
    return <span className="text-xs font-bold text-[#A0A0AB] w-4 text-center">{r}</span>;
  };

  return (
    <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-5" data-testid="donors-leaderboard">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Trophy className="w-5 h-5 text-yellow-400" />
          <h3 className="font-semibold text-white">{title}</h3>
        </div>
        <div className="flex bg-[#1A1A24] rounded-lg p-0.5">
          {PERIODS.map(p => (
            <button
              key={p.value}
              onClick={() => setPeriod(p.value)}
              className={`px-2.5 py-1 text-[10px] font-bold uppercase rounded ${period === p.value ? 'bg-[#00E5FF] text-black' : 'text-[#A0A0AB] hover:text-white'}`}
              data-testid={`lb-period-${p.value}`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="py-6 text-center text-[#A0A0AB] text-sm">Loading…</div>
      ) : items.length === 0 ? (
        <div className="py-6 text-center text-[#A0A0AB] text-sm">No donations yet.</div>
      ) : (
        <div className="space-y-1">
          {items.map((row) => (
            <div key={row.user_id} className="flex items-center gap-3 p-2 rounded-lg hover:bg-white/5" data-testid={`lb-row-${row.rank}`}>
              <div className="w-5 flex-shrink-0 flex justify-center">{rankIcon(row.rank)}</div>
              <img src={row.avatar_url || '/favicon.ico'} alt="" className="w-7 h-7 rounded-full object-cover bg-[#1A1A24]" />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-white truncate flex items-center gap-1">
                  {row.display_name || row.username}
                  {row.grade && <VerifiedBadge grade={row.grade} />}
                </p>
                <p className="text-[10px] text-[#A0A0AB]">{row.count} donation{row.count !== 1 ? 's' : ''}</p>
              </div>
              <span className="text-sm font-bold text-green-400 tabular-nums">${row.total.toFixed(2)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
