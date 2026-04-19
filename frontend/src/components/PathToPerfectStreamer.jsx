import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Path, Triangle } from '@phosphor-icons/react';

const API = process.env.REACT_APP_BACKEND_URL;

export default function PathToPerfectStreamer() {
  const [data, setData] = useState(null);
  const [enabled, setEnabled] = useState(true);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [featuresRes, pathRes] = await Promise.all([
          axios.get(`${API}/api/config/features`),
          axios.get(`${API}/api/my/streamer-path`, { withCredentials: true }),
        ]);
        setEnabled(featuresRes.data.path_enabled !== false);
        setData(pathRes.data);
      } catch { /* ignore */ } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading || !enabled || !data) return null;

  const completed = data.missions.filter(m => m.done).length;
  const total = data.missions.length;
  const progressPct = Math.round((completed / total) * 100);

  return (
    <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-6" data-testid="path-to-perfect-streamer">
      <div className="flex items-center justify-between flex-wrap gap-3 mb-5">
        <div className="flex items-center gap-3">
          <Path className="w-6 h-6 text-[#00E5FF]" />
          <div>
            <h2 className="text-lg font-semibold text-white">Path to a perfect streamer</h2>
            <p className="text-sm text-[#A0A0AB]">Key milestones over the last 12 months</p>
          </div>
        </div>
        <div className="text-right">
          <div className="text-sm font-bold text-white">{completed}/{total} missions</div>
          <div className="w-32 h-1.5 bg-[#1A1A24] rounded-full overflow-hidden mt-1">
            <div className={`h-full transition-all ${progressPct === 100 ? 'bg-green-500' : 'bg-[#00E5FF]'}`} style={{ width: `${progressPct}%` }} />
          </div>
        </div>
      </div>

      <ul className="space-y-2">
        {data.missions.map((m) => (
          <li key={m.id} className="flex items-start gap-3 p-3 bg-[#1A1A24] rounded-lg" data-testid={`path-mission-${m.id}`}>
            <Triangle
              weight="fill"
              className={`w-4 h-4 mt-0.5 flex-shrink-0 ${m.done ? 'text-green-400' : 'text-red-500'}`}
              data-testid={`path-triangle-${m.id}-${m.done ? 'done' : 'pending'}`}
            />
            <div className="flex-1">
              <p className="text-sm text-white">{m.label}</p>
              <div className="flex items-center gap-2 mt-1">
                <div className="flex-1 h-1 bg-[#292938] rounded-full overflow-hidden">
                  <div
                    className={`h-full transition-all ${m.done ? 'bg-green-400' : 'bg-[#00E5FF]'}`}
                    style={{ width: `${Math.min(100, (Number(m.current) / m.required) * 100)}%` }}
                  />
                </div>
                <span className="text-xs text-[#A0A0AB] tabular-nums min-w-[80px] text-right">{m.current} / {m.required}</span>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
