import React, { useState, useEffect, useRef } from 'react';
import EmojiPicker from 'emoji-picker-react';
import { Smiley } from '@phosphor-icons/react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

export default function ChatEmojiPicker({ onSelect }) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState('custom'); // 'custom' or 'standard'
  const [emotes, setEmotes] = useState([]);
  const pickerRef = useRef(null);

  useEffect(() => {
    const fetchEmotes = async () => {
      try {
        const res = await axios.get(`${API}/api/emotes`);
        setEmotes(res.data);
      } catch (e) {
        console.error('Error fetching emotes:', e);
      }
    };
    fetchEmotes();
  }, []);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (pickerRef.current && !pickerRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    if (open) document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

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
            <button
              onClick={() => setTab('custom')}
              className={`flex-1 py-2.5 text-xs font-bold uppercase tracking-wider transition-colors ${tab === 'custom' ? 'text-[#00E5FF] border-b-2 border-[#00E5FF]' : 'text-[#A0A0AB] hover:text-white'}`}
            >
              StreamVault
            </button>
            <button
              onClick={() => setTab('standard')}
              className={`flex-1 py-2.5 text-xs font-bold uppercase tracking-wider transition-colors ${tab === 'standard' ? 'text-[#00E5FF] border-b-2 border-[#00E5FF]' : 'text-[#A0A0AB] hover:text-white'}`}
            >
              Emoji
            </button>
          </div>

          {tab === 'custom' ? (
            <div className="p-3 grid grid-cols-8 gap-1.5 max-h-48 overflow-y-auto">
              {emotes.map((emote) => (
                <button
                  key={emote.code}
                  onClick={() => { onSelect(emote.code); setOpen(false); }}
                  className="w-8 h-8 flex items-center justify-center rounded hover:bg-white/10 transition-colors group relative"
                  title={emote.name}
                >
                  <img src={emote.url} alt={emote.name} className="w-6 h-6" />
                </button>
              ))}
            </div>
          ) : (
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
