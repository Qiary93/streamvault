import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Megaphone, Trophy, TrashSimple, PaperPlaneTilt } from '@phosphor-icons/react';
import { Button } from './ui/button';
import { formatDistanceToNow } from 'date-fns';

const API = process.env.REACT_APP_BACKEND_URL;

export default function ProfileFeed({ userId, isOwnProfile }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [content, setContent] = useState('');
  const [posting, setPosting] = useState(false);

  const fetchFeed = async () => {
    try {
      const res = await axios.get(`${API}/api/users/${userId}/feed?limit=20`);
      setItems(res.data.items || []);
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (userId) fetchFeed(); }, [userId]);

  const submit = async () => {
    const text = content.trim();
    if (!text) return;
    setPosting(true);
    try {
      await axios.post(`${API}/api/my/feed`, { content: text }, { withCredentials: true });
      setContent('');
      toast.success('Posted');
      fetchFeed();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Post failed');
    } finally {
      setPosting(false);
    }
  };

  const remove = async (postId) => {
    if (!window.confirm('Delete this post?')) return;
    try {
      await axios.delete(`${API}/api/my/feed/${postId}`, { withCredentials: true });
      setItems(prev => prev.filter(p => p.post_id !== postId));
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Delete failed');
    }
  };

  if (loading) return null;

  return (
    <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-6" data-testid="profile-feed">
      <div className="flex items-center gap-3 mb-4">
        <Megaphone className="w-6 h-6 text-[#00E5FF]" />
        <h2 className="text-lg font-semibold text-white">Feed</h2>
      </div>

      {isOwnProfile && (
        <div className="mb-4">
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={2}
            maxLength={500}
            placeholder="Share an update with your followers..."
            className="w-full p-3 bg-[#1A1A24] border border-white/10 rounded-md text-white placeholder-[#A0A0AB] focus:outline-none focus:border-[#00E5FF] resize-none text-sm"
            data-testid="feed-input"
          />
          <div className="flex items-center justify-between mt-2">
            <span className="text-xs text-[#A0A0AB]">{content.length}/500</span>
            <Button onClick={submit} disabled={posting || !content.trim()} size="sm" className="bg-[#00E5FF] text-black hover:bg-[#00B3CC] font-bold" data-testid="feed-post-btn">
              <PaperPlaneTilt className="w-4 h-4 mr-1" /> {posting ? 'Posting…' : 'Post'}
            </Button>
          </div>
        </div>
      )}

      {items.length === 0 ? (
        <p className="text-sm text-[#A0A0AB] text-center py-6">No posts yet.</p>
      ) : (
        <div className="space-y-2">
          {items.map((p) => (
            <div key={p.post_id} className="p-3 bg-[#1A1A24] rounded-lg flex items-start gap-3" data-testid={`feed-post-${p.post_id}`}>
              {p.type === 'level_up' ? (
                <Trophy className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
              ) : (
                <span className="w-2 h-2 bg-[#00E5FF] rounded-full flex-shrink-0 mt-2" />
              )}
              <div className="flex-1 min-w-0">
                <p className="text-sm text-white whitespace-pre-wrap break-words">{p.content}</p>
                <p className="text-xs text-[#A0A0AB] mt-1">
                  {p.created_at ? formatDistanceToNow(new Date(p.created_at), { addSuffix: true }) : ''}
                </p>
              </div>
              {isOwnProfile && p.type !== 'level_up' && (
                <button onClick={() => remove(p.post_id)} className="text-red-400 hover:text-red-300 flex-shrink-0" data-testid={`feed-delete-${p.post_id}`}>
                  <TrashSimple className="w-4 h-4" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
