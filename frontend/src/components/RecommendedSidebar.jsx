import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Avatar, AvatarFallback, AvatarImage } from './ui/avatar';
import { useAuth } from '../contexts/AuthContext';
import { Broadcast } from '@phosphor-icons/react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

export default function RecommendedSidebar() {
  const { user } = useAuth();
  const [streamers, setStreamers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchRecommended = async () => {
      try {
        const res = await axios.get(`${API}/api/recommended`, {
          withCredentials: true
        });
        setStreamers(res.data);
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
    <div className="hidden xl:block w-60 flex-shrink-0" data-testid="recommended-sidebar">
      <div className="sticky top-20 p-4">
        <h3 className="text-xs font-bold uppercase tracking-[0.2em] text-[#00E5FF] mb-4">Recommended</h3>
        <div className="space-y-2">
          {streamers.slice(0, 10).map((s) => (
            <Link
              key={s.user_id}
              to={`/user/${s.username}`}
              className="flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-white/5 transition-colors group"
              data-testid={`rec-${s.user_id}`}
            >
              <Avatar className={`w-8 h-8 flex-shrink-0 ${s.is_streaming ? 'avatar-live' : ''}`}>
                <AvatarImage src={s.avatar_url} alt={s.display_name || s.username} />
                <AvatarFallback className="bg-[#292938] text-[#00E5FF] text-xs">
                  {(s.display_name || s.username)?.charAt(0).toUpperCase()}
                </AvatarFallback>
              </Avatar>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-white truncate group-hover:text-[#00E5FF] transition-colors">
                  {s.display_name || s.username}
                </p>
                <p className="text-xs text-[#A0A0AB] truncate">@{s.username}</p>
              </div>
              {s.is_streaming && (
                <Broadcast weight="fill" className="w-4 h-4 text-red-400 flex-shrink-0" />
              )}
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
