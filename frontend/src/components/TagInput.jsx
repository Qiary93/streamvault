import React, { useState, useRef } from 'react';
import { X } from '@phosphor-icons/react';

export default function TagInput({ tags = [], onChange, maxTags = 5 }) {
  const [input, setInput] = useState('');
  const inputRef = useRef(null);

  const addTag = (value) => {
    const tag = value.trim().toLowerCase().replace(/[^a-z0-9\s-]/g, '').substring(0, 30);
    if (!tag || tags.includes(tag) || tags.length >= maxTags) return;
    onChange([...tags, tag]);
    setInput('');
  };

  const removeTag = (index) => {
    onChange(tags.filter((_, i) => i !== index));
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addTag(input);
    }
    if (e.key === 'Backspace' && !input && tags.length > 0) {
      removeTag(tags.length - 1);
    }
  };

  return (
    <div
      className="flex flex-wrap gap-2 p-2 bg-[#1A1A24] border border-white/10 rounded-md min-h-[42px] cursor-text"
      onClick={() => inputRef.current?.focus()}
      data-testid="tag-input-container"
    >
      {tags.map((tag, i) => (
        <span
          key={i}
          className="inline-flex items-center gap-1 px-2.5 py-1 bg-[#00E5FF]/15 text-[#00E5FF] text-xs font-medium rounded-full"
        >
          #{tag}
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); removeTag(i); }}
            className="hover:text-white transition-colors"
          >
            <X className="w-3 h-3" />
          </button>
        </span>
      ))}
      {tags.length < maxTags && (
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={() => { if (input) addTag(input); }}
          placeholder={tags.length === 0 ? "Add tags (press Enter)..." : `${maxTags - tags.length} left`}
          className="flex-1 min-w-[100px] bg-transparent text-white text-sm placeholder-[#A0A0AB] outline-none"
          data-testid="tag-input"
        />
      )}
    </div>
  );
}
