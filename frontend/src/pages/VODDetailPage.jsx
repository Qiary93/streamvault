import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Play, Clock, Eye, ArrowLeft, Users } from '@phosphor-icons/react';
import { Avatar, AvatarFallback, AvatarImage } from '../components/ui/avatar';
import { ScrollArea } from '../components/ui/scroll-area';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

function formatDuration(seconds) {
  if (!seconds) return '';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${m}:${String(s).padStart(2, '0')}`;
}

const usernameColors = [
  '#00E5FF', '#FF6B6B', '#4ECDC4', '#FFE66D', '#95E1D3',
  '#F38181', '#AA96DA', '#FF9671', '#FFC75F', '#00C9A7'
];

function getUsernameColor(username) {
  let hash = 0;
  for (let i = 0; i < (username || '').length; i++) {
    hash = username.charCodeAt(i) + ((hash << 5) - hash);
  }
  return usernameColors[Math.abs(hash) % usernameColors.length];
}

export default function VODDetailPage() {
  const { streamId } = useParams();
  const [vod, setVod] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchVod = async () => {
      try {
        const response = await axios.get(`${API}/api/vods/${streamId}`);
        setVod(response.data);
      } catch (error) {
        console.error('Error fetching VOD:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchVod();
  }, [streamId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="w-8 h-8 border-2 border-[#00E5FF] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!vod) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh]">
        <h2 className="text-xl font-bold text-white mb-2">VOD not found</h2>
        <Link to="/vods" className="text-[#00E5FF] hover:underline">Browse VODs</Link>
      </div>
    );
  }

  return (
    <div className="min-h-[calc(100vh-64px)] grid grid-cols-1 lg:grid-cols-12" data-testid="vod-detail-page">
      <div className="lg:col-span-9 flex flex-col overflow-y-auto">
        {/* Video Area */}
        <div className="relative aspect-video bg-black">
          {vod.thumbnail_url ? (
            <img src={vod.thumbnail_url} alt={vod.title} className="w-full h-full object-cover opacity-60" />
          ) : (
            <div className="w-full h-full bg-gradient-to-br from-[#0F0F16] to-[#1A1A24]" />
          )}
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center">
              <div className="w-20 h-20 bg-[#00E5FF]/20 rounded-full flex items-center justify-center mx-auto mb-4 border-2 border-[#00E5FF]">
                <Play weight="fill" className="w-10 h-10 text-[#00E5FF] ml-1" />
              </div>
              <p className="text-white font-semibold">Past Stream Recording</p>
              <p className="text-[#A0A0AB] text-sm mt-1">Chat replay available</p>
            </div>
          </div>
          
          <div className="absolute top-4 left-4 px-3 py-1.5 bg-[#292938] rounded text-sm text-[#A0A0AB]">
            VOD
          </div>
        </div>

        {/* Stream Info */}
        <div className="p-4 lg:p-6 border-b border-white/5">
          <Link 
            to="/vods" 
            className="inline-flex items-center gap-2 text-[#A0A0AB] hover:text-white mb-3 transition-colors text-sm"
          >
            <ArrowLeft className="w-4 h-4" /> Back to VODs
          </Link>
          
          <div className="flex gap-4">
            <Link to={`/user/${vod.username}`}>
              <Avatar className="w-14 h-14">
                <AvatarImage src={vod.avatar_url} alt={vod.display_name || vod.username} />
                <AvatarFallback className="bg-[#292938] text-[#00E5FF] text-xl">
                  {(vod.display_name || vod.username)?.charAt(0).toUpperCase()}
                </AvatarFallback>
              </Avatar>
            </Link>
            <div className="flex-1">
              <h1 className="text-lg lg:text-xl font-bold text-white mb-1">{vod.title}</h1>
              <Link to={`/user/${vod.username}`} className="text-[#00E5FF] hover:underline font-medium">
                {vod.display_name || vod.username}
              </Link>
              <div className="flex items-center gap-4 mt-2 text-sm text-[#A0A0AB]">
                {vod.category_name && <span>{vod.category_name}</span>}
                <span className="flex items-center gap-1">
                  <Clock className="w-4 h-4" />
                  {vod.duration_seconds ? formatDuration(vod.duration_seconds) : 'Unknown duration'}
                </span>
                <span className="flex items-center gap-1">
                  <Eye className="w-4 h-4" />
                  {vod.viewer_count || 0} views
                </span>
                <span>{new Date(vod.started_at).toLocaleDateString()}</span>
              </div>
            </div>
          </div>

          {vod.description && (
            <div className="mt-4 p-4 bg-[#0F0F16] rounded-lg">
              <p className="text-[#A0A0AB] text-sm whitespace-pre-wrap">{vod.description}</p>
            </div>
          )}
        </div>
      </div>

      {/* Chat Replay */}
      <div className="lg:col-span-3 h-[500px] lg:h-[calc(100vh-64px)] lg:sticky lg:top-16 bg-[#0F0F16] border-l border-white/5 flex flex-col">
        <div className="h-12 flex items-center justify-between px-4 border-b border-white/5">
          <h3 className="font-semibold text-white">Chat Replay</h3>
          <span className="text-xs text-[#A0A0AB]">{vod.chat_replay?.length || 0} messages</span>
        </div>
        <ScrollArea className="flex-1 p-4">
          <div className="space-y-3">
            {(vod.chat_replay || []).map((msg) => (
              <div key={msg.message_id} className="flex gap-2">
                <Avatar className="w-6 h-6 flex-shrink-0">
                  <AvatarImage src={msg.avatar_url} alt={msg.username} />
                  <AvatarFallback className="bg-[#292938] text-[#00E5FF] text-xs">
                    {(msg.display_name || msg.username)?.charAt(0).toUpperCase()}
                  </AvatarFallback>
                </Avatar>
                <div className="min-w-0">
                  <span className="text-sm font-semibold mr-2" style={{ color: getUsernameColor(msg.username) }}>
                    {msg.display_name || msg.username}
                  </span>
                  <span className="text-sm text-[#A0A0AB] break-words">{msg.content}</span>
                </div>
              </div>
            ))}
            {(!vod.chat_replay || vod.chat_replay.length === 0) && (
              <p className="text-center text-[#A0A0AB] text-sm py-8">No chat messages recorded</p>
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}
