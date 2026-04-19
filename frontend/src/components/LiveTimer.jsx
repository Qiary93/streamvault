import React, { useEffect, useState, useRef } from 'react';
import { Clock } from '@phosphor-icons/react';

function fmt(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
  return `${m}:${String(sec).padStart(2, '0')}`;
}

/**
 * Live broadcasting timer. Reads `startedAt` (ISO string or null) and counts up in real time.
 * When `startedAt` is null/undefined, shows "--:--".
 */
export default function LiveTimer({ startedAt, compact = false, testid = 'live-timer' }) {
  const [now, setNow] = useState(Date.now());
  const intervalRef = useRef(null);

  useEffect(() => {
    if (!startedAt) return;
    setNow(Date.now());
    intervalRef.current = setInterval(() => setNow(Date.now()), 1000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [startedAt]);

  if (!startedAt) {
    return (
      <div className={`inline-flex items-center gap-1.5 ${compact ? 'text-xs' : 'text-sm'} text-[#A0A0AB]`} data-testid={testid}>
        <Clock className={compact ? 'w-3.5 h-3.5' : 'w-4 h-4'} /> --:--
      </div>
    );
  }

  let startMs;
  try { startMs = new Date(startedAt).getTime(); } catch { startMs = Date.now(); }
  const elapsed = Math.max(0, (now - startMs) / 1000);

  return (
    <div
      className={`inline-flex items-center gap-1.5 font-mono tabular-nums ${compact ? 'text-xs' : 'text-sm'} text-green-400`}
      title="Broadcasting time (OBS connected)"
      data-testid={testid}
    >
      <Clock className={compact ? 'w-3.5 h-3.5' : 'w-4 h-4'} /> {fmt(elapsed)}
    </div>
  );
}
