import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Avatar, AvatarFallback, AvatarImage } from './ui/avatar';
import { useAuth } from '../contexts/AuthContext';
import { Eye } from '@phosphor-icons/react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

export default function RecommendedSidebar() {
  const { user } = useAuth();
  const [streamers, setStreamers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchRecommended = async () => {
      try {
        const res = await axios.get(`${API}/api/recommended`, { withCredentials: true });
        setStreamers(res.data || []);
      } catch (e) {
        console.error('Error fetching recommended:', e);
      } finally {
        setLoading(false);
      }
    };
    fetchRecommended();
  }, [user?.user_id]);

  if (loading || streamers.length === 0) return null;

  return (
    <div className="hidden xl:block w-64 flex-shrink-0" data-testid="recommended-sidebar">
      <div className="sticky top-20 p-4">
        <h3 className="text-xs font-bold uppercase tracking-[0.2em] text-[#00E5FF] mb-4">Recommended · Live</h3>
        <div className="space-y-1.5">
          {streamers.slice(0, 10).map((s) => (
            <Link
              key={s.user_id}
              to={s.active_stream_id ? `/stream/${s.active_stream_id}` : `/user/${s.username}`}
              className="flex items-center gap-2.5 px-2 py-2 rounded-lg hover:bg-white/5 transition-colors group"
              data-testid={`rec-${s.user_id}`}
            >
              <Avatar className="w-9 h-9 flex-shrink-0">
                <AvatarImage src={s.avatar_url} alt={s.display_name || s.username} />
                <AvatarFallback className="bg-[#292938] text-[#00E5FF] text-xs">
                  {(s.display_name || s.username)?.charAt(0).toUpperCase()}
                </AvatarFallback>
              </Avatar>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-white truncate group-hover:text-[#00E5FF] transition-colors">
                  {s.display_name || s.username}
                </p>
                <p className="text-xs text-[#A0A0AB] truncate" data-testid={`rec-game-${s.user_id}`}>
                  {s.game_name || s.stream_title || ''}
                </p>
              </div>
              <div className="flex-shrink-0 flex items-center gap-1" data-testid={`rec-live-${s.user_id}`}>
                <span className="w-2 h-2 bg-green-500 rounded-full flex-shrink-0 animate-pulse" data-testid={`rec-green-dot-${s.user_id}`} />
                <span className="text-[11px] text-white font-medium tabular-nums" data-testid={`rec-viewers-${s.user_id}`}>
                  {(s.viewer_count || 0).toLocaleString()}
                </span>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
