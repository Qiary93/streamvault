import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Play, Clock, Eye } from '@phosphor-icons/react';
import { Avatar, AvatarFallback, AvatarImage } from '../components/ui/avatar';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

function formatDuration(seconds) {
  if (!seconds) return '';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  });
}

function VODCard({ vod }) {
  return (
    <Link
      to={`/vod/${vod.stream_id}`}
      className="group stream-card block bg-[#0F0F16] border border-white/5 rounded-xl overflow-hidden"
      data-testid={`vod-card-${vod.stream_id}`}
    >
      <div className="relative aspect-video bg-[#1A1A24]">
        {vod.thumbnail_url ? (
          <img src={vod.thumbnail_url} alt={vod.title} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-[#0F0F16] to-[#1A1A24]">
            <Play weight="fill" className="w-12 h-12 text-[#292938]" />
          </div>
        )}
        
        {/* Duration badge */}
        {vod.duration_seconds && (
          <div className="absolute bottom-2 right-2 flex items-center gap-1 px-2 py-1 bg-black/80 rounded text-xs text-white">
            <Clock className="w-3 h-3" />
            {formatDuration(vod.duration_seconds)}
          </div>
        )}

        {/* Play overlay */}
        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/30">
          <div className="w-12 h-12 bg-[#00E5FF] rounded-full flex items-center justify-center">
            <Play weight="fill" className="w-6 h-6 text-black ml-1" />
          </div>
        </div>

        {/* Viewer count */}
        <div className="absolute bottom-2 left-2 flex items-center gap-1 px-2 py-1 bg-black/70 rounded text-xs text-white">
          <Eye className="w-3.5 h-3.5" />
          {vod.viewer_count || 0} views
        </div>
      </div>

      <div className="p-3 flex gap-3">
        <Avatar className="w-10 h-10 flex-shrink-0">
          <AvatarImage src={vod.avatar_url} alt={vod.display_name || vod.username} />
          <AvatarFallback className="bg-[#292938] text-[#00E5FF]">
            {(vod.display_name || vod.username)?.charAt(0).toUpperCase()}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-white truncate group-hover:text-[#00E5FF] transition-colors">
            {vod.title}
          </h3>
          <p className="text-xs text-[#A0A0AB] truncate">{vod.display_name || vod.username}</p>
          <div className="flex items-center gap-2 mt-0.5">
            {vod.category_name && (
              <p className="text-xs text-[#00E5FF]">{vod.category_name}</p>
            )}
            <p className="text-xs text-[#A0A0AB]">{formatDate(vod.started_at)}</p>
          </div>
        </div>
      </div>
    </Link>
  );
}

export default function VODPage() {
  const [vods, setVods] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchVods = async () => {
      try {
        const response = await axios.get(`${API}/api/vods`);
        setVods(response.data);
      } catch (error) {
        console.error('Error fetching VODs:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchVods();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="w-8 h-8 border-2 border-[#00E5FF] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-4 lg:p-6" data-testid="vod-page">
      <h1 className="text-2xl lg:text-3xl font-bold text-white mb-6 font-['Outfit']">Past Streams</h1>
      
      {vods.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {vods.map((vod) => (
            <VODCard key={vod.stream_id} vod={vod} />
          ))}
        </div>
      ) : (
        <div className="text-center py-16 bg-[#0F0F16] rounded-xl">
          <Play weight="fill" className="w-16 h-16 text-[#292938] mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-white mb-2">No past streams yet</h2>
          <p className="text-[#A0A0AB]">Past streams will appear here after they end</p>
        </div>
      )}
    </div>
  );
}
