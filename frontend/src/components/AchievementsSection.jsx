import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Trophy, Triangle } from '@phosphor-icons/react';
import VerifiedBadge from './VerifiedBadge';

const API = process.env.REACT_APP_BACKEND_URL;

const GRADE_COLORS = {
  Beginner: 'from-emerald-500/20 to-emerald-500/5 border-emerald-500/30 text-emerald-400',
  Intermediate: 'from-blue-500/20 to-blue-500/5 border-blue-500/30 text-blue-400',
  Advanced: 'from-purple-500/20 to-purple-500/5 border-purple-500/30 text-purple-400',
  Expert: 'from-yellow-500/20 to-yellow-500/5 border-yellow-500/30 text-yellow-400',
};

export default function AchievementsSection({ userId }) {
  const [data, setData] = useState(null);
  const [enabled, setEnabled] = useState(true);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [featuresRes, achRes] = await Promise.all([
          axios.get(`${API}/api/config/features`),
          axios.get(`${API}/api/users/${userId}/achievements`),
        ]);
        setEnabled(featuresRes.data.achievements_enabled !== false);
        setData(achRes.data);
      } catch { /* ignore */ } finally {
        setLoading(false);
      }
    })();
  }, [userId]);

  if (loading || !enabled || !data) return null;

  return (
    <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-6" data-testid="achievements-section">
      <div className="flex items-center gap-3 mb-5">
        <Trophy className="w-6 h-6 text-yellow-400" />
        <div>
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            Achievements
            {data.grade && <VerifiedBadge grade={data.grade} size="md" />}
          </h2>
          <p className="text-sm text-[#A0A0AB]">
            {data.grade ? <>Current grade: <span className="font-bold text-white">{data.grade}</span></> : 'Complete missions to earn your first grade'}
          </p>
        </div>
      </div>

      <div className="space-y-3">
        {data.grades.map((g) => (
          <div
            key={g.grade}
            className={`p-4 rounded-lg border bg-gradient-to-br ${GRADE_COLORS[g.grade] || ''}`}
            data-testid={`grade-${g.grade}`}
          >
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-white flex items-center gap-2">
                {g.grade}
                {g.achieved && <VerifiedBadge grade={g.grade} />}
              </h3>
              <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${g.achieved ? 'bg-green-500/20 text-green-400' : 'bg-white/5 text-[#A0A0AB]'}`}>
                {g.achieved ? 'ACHIEVED' : `${g.missions.filter(m => m.done).length}/${g.missions.length}`}
              </span>
            </div>
            <ul className="space-y-1.5">
              {g.missions.map((m) => (
                <li key={m.id} className="flex items-start gap-2 text-sm" data-testid={`mission-${g.grade}-${m.id}`}>
                  <Triangle
                    weight="fill"
                    className={`w-3 h-3 mt-0.5 flex-shrink-0 ${m.done ? 'text-green-400' : 'text-red-500'}`}
                    data-testid={`mission-triangle-${g.grade}-${m.id}-${m.done ? 'done' : 'pending'}`}
                  />
                  <span className="text-white/90 flex-1">{m.label}</span>
                  <span className="text-[#A0A0AB] text-xs tabular-nums">{m.current} / {m.required}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
