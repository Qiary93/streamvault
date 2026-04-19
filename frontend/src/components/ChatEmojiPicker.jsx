import React, { useState, useEffect, useRef } from 'react';
import EmojiPicker from 'emoji-picker-react';
import { Smiley, Lock } from '@phosphor-icons/react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

export default function ChatEmojiPicker({ onSelect, streamerId, isSubscribed = false }) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState('custom'); // 'custom' | 'streamer' | 'standard'
  const [emotes, setEmotes] = useState([]);
  const [streamerEmotes, setStreamerEmotes] = useState([]);
  const pickerRef = useRef(null);

  useEffect(() => {
    axios.get(`${API}/api/emotes`).then(r => setEmotes(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!streamerId) { setStreamerEmotes([]); return; }
    axios.get(`${API}/api/users/${streamerId}/emotes`).then(r => setStreamerEmotes(r.data)).catch(() => setStreamerEmotes([]));
  }, [streamerId]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (pickerRef.current && !pickerRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    if (open) document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  const TabBtn = ({ id, label }) => (
    <button
      onClick={() => setTab(id)}
      className={`flex-1 py-2 text-[10px] font-bold uppercase tracking-wider transition-colors ${tab === id ? 'text-[#00E5FF] border-b-2 border-[#00E5FF]' : 'text-[#A0A0AB] hover:text-white'}`}
      data-testid={`emoji-tab-${id}`}
    >
      {label}
    </button>
  );

  // Filter streamer emotes by subscription
  const visibleStreamerEmotes = streamerEmotes.filter(e => !e.subscribers_only || isSubscribed);

  return (
    <div className="relative" ref={pickerRef}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="p-2 rounded hover:bg-white/10 text-[#A0A0AB] hover:text-[#00E5FF] transition-colors"
        data-testid="emoji-picker-btn"
      >
        <Smiley className="w-5 h-5" />
      </button>

      {open && (
        <div className="absolute bottom-12 right-0 z-50 w-80 bg-[#0F0F16] border border-white/10 rounded-xl shadow-2xl overflow-hidden" data-testid="emoji-picker-panel">
          {/* Tabs */}
          <div className="flex border-b border-white/10">
            <TabBtn id="custom" label="SV" />
            {streamerEmotes.length > 0 && <TabBtn id="streamer" label="Streamer" />}
            <TabBtn id="standard" label="Emoji" />
          </div>

          {tab === 'custom' && (
            <div className="p-3 grid grid-cols-8 gap-1.5 max-h-48 overflow-y-auto">
              {emotes.map((emote) => (
                <button
                  key={emote.code}
                  onClick={() => { onSelect(emote.code); setOpen(false); }}
                  className="w-8 h-8 flex items-center justify-center rounded hover:bg-white/10 transition-colors"
                  title={emote.name}
                  data-testid={`emote-${emote.code}`}
                >
                  <img src={emote.url} alt={emote.name} className="w-6 h-6" />
                </button>
              ))}
            </div>
          )}

          {tab === 'streamer' && (
            <div className="p-3 grid grid-cols-8 gap-1.5 max-h-48 overflow-y-auto" data-testid="streamer-emotes-grid">
              {visibleStreamerEmotes.length === 0 ? (
                <p className="col-span-8 text-xs text-[#A0A0AB] text-center py-4">No emotes available — subscribe to unlock.</p>
              ) : visibleStreamerEmotes.map((emote) => (
                <button
                  key={emote.emote_id}
                  onClick={() => { onSelect(emote.code); setOpen(false); }}
                  className="w-8 h-8 flex items-center justify-center rounded hover:bg-white/10 transition-colors"
                  title={emote.code}
                  data-testid={`streamer-emote-${emote.code}`}
                >
                  <img src={emote.url?.startsWith('http') ? emote.url : `${API}${emote.url}`} alt={emote.code} className="w-7 h-7 object-contain" />
                </button>
              ))}
            </div>
          )}

          {tab === 'standard' && (
            <div className="h-[300px]">
              <EmojiPicker
                onEmojiClick={(emoji) => { onSelect(emoji.emoji); setOpen(false); }}
                theme="dark"
                width="100%"
                height={300}
                searchDisabled={false}
                skinTonesDisabled
                previewConfig={{ showPreview: false }}
                lazyLoadEmojis
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
