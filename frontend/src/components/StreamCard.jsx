import React from 'react';
import { Link } from 'react-router-dom';
import { Eye } from '@phosphor-icons/react';
import { Avatar, AvatarFallback, AvatarImage } from './ui/avatar';

export default function StreamCard({ stream }) {
  const formatViewers = (count) => {
    if (count >= 1000) {
      return `${(count / 1000).toFixed(1)}K`;
    }
    return count.toString();
  };

  return (
    <Link 
      to={`/stream/${stream.stream_id}`}
      className="group stream-card block bg-[#0F0F16] border border-white/5 rounded-xl overflow-hidden"
      data-testid={`stream-card-${stream.stream_id}`}
    >
      {/* Thumbnail */}
      <div className="relative aspect-video bg-[#1A1A24]">
        {stream.thumbnail_url ? (
          <img 
            src={stream.thumbnail_url} 
            alt={stream.title}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-[#0F0F16] to-[#1A1A24]">
            <span className="text-4xl font-bold text-[#292938]">LIVE</span>
          </div>
        )}
        
        {/* Live badge */}
        {stream.is_live && (
          <div className="absolute top-2 left-2 flex items-center gap-1.5 px-2 py-1 bg-red-500 rounded text-xs font-bold text-white">
            <span className="w-2 h-2 bg-white rounded-full live-indicator" />
            LIVE
          </div>
        )}

        {/* Viewer count */}
        <div className="absolute bottom-2 left-2 flex items-center gap-1 px-2 py-1 bg-black/70 rounded text-xs text-white">
          <Eye className="w-3.5 h-3.5" />
          {formatViewers(stream.viewer_count || 0)}
        </div>
      </div>

      {/* Info */}
      <div className="p-3 flex gap-3">
        <Avatar className={`w-10 h-10 flex-shrink-0 ${stream.is_live ? 'avatar-live' : ''}`}>
          <AvatarImage src={stream.avatar_url} alt={stream.display_name || stream.username} />
          <AvatarFallback className="bg-[#292938] text-[#00E5FF]">
            {(stream.display_name || stream.username)?.charAt(0).toUpperCase()}
          </AvatarFallback>
        </Avatar>

        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-white truncate group-hover:text-[#00E5FF] transition-colors">
            {stream.title}
          </h3>
          <p className="text-xs text-[#A0A0AB] truncate">{stream.display_name || stream.username}</p>
          {stream.category_name && (
            <p className="text-xs text-[#00E5FF] truncate mt-0.5">{stream.category_name}</p>
          )}
        </div>
      </div>
    </Link>
  );
}
