import { useEffect, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import confetti from 'canvas-confetti';

const API = process.env.REACT_APP_BACKEND_URL;
const POLL_INTERVAL = 15000;
const SEEN_KEY = 'sv_seen_level_up_notifs';

const GRADE_COLORS = {
  Beginner: ['#10B981', '#34D399'],
  Intermediate: ['#3B82F6', '#60A5FA'],
  Advanced: ['#A855F7', '#C084FC'],
  Expert: ['#F59E0B', '#FBBF24'],
};

function fireConfetti(grade) {
  const colors = GRADE_COLORS[grade] || ['#00E5FF', '#FFFFFF'];
  const duration = 3000;
  const end = Date.now() + duration;
  (function frame() {
    confetti({ particleCount: 4, angle: 60, spread: 55, origin: { x: 0, y: 0.7 }, colors });
    confetti({ particleCount: 4, angle: 120, spread: 55, origin: { x: 1, y: 0.7 }, colors });
    if (Date.now() < end) requestAnimationFrame(frame);
  })();
}

/** Hidden component that polls for level_up notifications and triggers confetti + toast. */
export default function LevelUpListener() {
  const { user } = useAuth();
  const pollRef = useRef(null);
  const seenRef = useRef(new Set());

  useEffect(() => {
    if (!user) return;
    try {
      const stored = JSON.parse(localStorage.getItem(SEEN_KEY) || '[]');
      seenRef.current = new Set(stored);
    } catch {
      seenRef.current = new Set();
    }

    const check = async () => {
      try {
        // Refresh achievements to trigger grade change detection on backend
        await axios.get(`${API}/api/my/achievements`, { withCredentials: true });
        const res = await axios.get(`${API}/api/notifications?unread=true&limit=20`, { withCredentials: true });
        const unread = Array.isArray(res.data) ? res.data : (res.data.items || []);
        for (const n of unread) {
          if (n.type === 'level_up' && !seenRef.current.has(n.notification_id)) {
            seenRef.current.add(n.notification_id);
            const grade = n.data?.grade;
            fireConfetti(grade);
            toast.success(`🎉 Level up — ${grade}!`, { duration: 6000, description: 'Your grade badge is now visible on your profile.' });
          }
        }
        try { localStorage.setItem(SEEN_KEY, JSON.stringify([...seenRef.current].slice(-200))); } catch {}
      } catch { /* ignore */ }
    };

    check();
    pollRef.current = setInterval(check, POLL_INTERVAL);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [user?.user_id]);

  return null;
}
