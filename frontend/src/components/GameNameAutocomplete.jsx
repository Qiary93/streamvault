import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { GameController } from '@phosphor-icons/react';
import { Input } from './ui/input';

const API = process.env.REACT_APP_BACKEND_URL;

export default function GameNameAutocomplete({ value, onChange, placeholder = 'Type a game…', testid = 'game-autocomplete' }) {
  const [input, setInput] = useState(value || '');
  const [suggestions, setSuggestions] = useState([]);
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(-1);
  const boxRef = useRef(null);

  useEffect(() => { setInput(value || ''); }, [value]);

  useEffect(() => {
    let active = true;
    const t = setTimeout(async () => {
      try {
        const res = await axios.get(`${API}/api/games/search?q=${encodeURIComponent(input)}&limit=12`);
        if (active) setSuggestions(res.data.items || []);
      } catch { if (active) setSuggestions([]); }
    }, 120);
    return () => { active = false; clearTimeout(t); };
  }, [input]);

  useEffect(() => {
    const onClick = (e) => {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const pick = (v) => {
    setInput(v);
    onChange && onChange(v);
    setOpen(false);
  };

  const onKey = (e) => {
    if (!open) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); setHighlight(h => Math.min(suggestions.length - 1, h + 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setHighlight(h => Math.max(0, h - 1)); }
    else if (e.key === 'Enter' && highlight >= 0) { e.preventDefault(); pick(suggestions[highlight]); }
    else if (e.key === 'Escape') setOpen(false);
  };

  return (
    <div ref={boxRef} className="relative" data-testid={testid}>
      <div className="relative">
        <GameController className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#A0A0AB]" />
        <Input
          value={input}
          onChange={(e) => { setInput(e.target.value); onChange && onChange(e.target.value); setOpen(true); setHighlight(-1); }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKey}
          placeholder={placeholder}
          className="bg-[#1A1A24] border-white/10 text-white pl-10"
          data-testid={`${testid}-input`}
        />
      </div>
      {open && suggestions.length > 0 && (
        <div className="absolute left-0 right-0 mt-1 bg-[#0F0F16] border border-white/10 rounded-md shadow-2xl z-50 max-h-64 overflow-y-auto" data-testid={`${testid}-dropdown`}>
          {suggestions.map((s, i) => (
            <button
              key={s}
              type="button"
              onMouseEnter={() => setHighlight(i)}
              onClick={() => pick(s)}
              className={`w-full text-left px-3 py-2 text-sm text-white flex items-center gap-2 ${highlight === i ? 'bg-[#00E5FF]/10' : 'hover:bg-white/5'}`}
              data-testid={`${testid}-opt-${i}`}
            >
              <GameController className="w-3.5 h-3.5 text-[#A0A0AB]" />
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
