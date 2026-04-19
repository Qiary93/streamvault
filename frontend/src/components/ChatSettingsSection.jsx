import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { ChatsCircle, Scroll, UsersThree, LockKey, Prohibit } from '@phosphor-icons/react';
import { Button } from './ui/button';

const API = process.env.REACT_APP_BACKEND_URL;

export default function ChatSettingsSection() {
  const [settings, setSettings] = useState({
    chat_enabled: true,
    rules: '',
    followers_only: false,
    subscribers_only: false,
    restricted_words: [],
    restricted_words_mode: 'filter',
  });
  const [wordsInput, setWordsInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    axios.get(`${API}/api/my/chat-settings`, { withCredentials: true })
      .then(res => {
        setSettings({
          chat_enabled: res.data.chat_enabled !== false,
          rules: res.data.rules || '',
          followers_only: !!res.data.followers_only,
          subscribers_only: !!res.data.subscribers_only,
          restricted_words: res.data.restricted_words || [],
          restricted_words_mode: res.data.restricted_words_mode || 'filter',
        });
        setWordsInput((res.data.restricted_words || []).join(', '));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      const words = wordsInput.split(',').map(w => w.trim().toLowerCase()).filter(Boolean);
      const payload = { ...settings, restricted_words: words };
      await axios.put(`${API}/api/my/chat-settings`, payload, { withCredentials: true });
      setSettings(payload);
      toast.success('Chat settings saved');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return null;

  const ToggleRow = ({ id, Icon, title, subtitle, checked, onChange, testid }) => (
    <label className="flex items-center gap-3 p-3 bg-[#1A1A24] rounded-lg cursor-pointer hover:bg-[#1E1E2A]">
      <Icon className="w-5 h-5 text-[#00E5FF]" />
      <div className="flex-1">
        <p className="text-sm font-medium text-white">{title}</p>
        <p className="text-xs text-[#A0A0AB]">{subtitle}</p>
      </div>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} data-testid={testid} className="accent-[#00E5FF]" />
    </label>
  );

  return (
    <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-6" data-testid="chat-settings-section">
      <div className="flex items-center gap-3 mb-5">
        <ChatsCircle className="w-6 h-6 text-[#00E5FF]" />
        <div>
          <h2 className="text-lg font-semibold text-white">Chat</h2>
          <p className="text-sm text-[#A0A0AB]">Control who can chat, set rules, and filter restricted words</p>
        </div>
      </div>

      <div className="space-y-2 mb-5">
        <ToggleRow
          Icon={ChatsCircle}
          title={`Chat is ${settings.chat_enabled ? 'ON' : 'OFF'}`}
          subtitle="When OFF, viewers see a chat disabled message."
          checked={settings.chat_enabled}
          onChange={(v) => setSettings(p => ({ ...p, chat_enabled: v }))}
          testid="chat-enabled-toggle"
        />
        <ToggleRow
          Icon={UsersThree}
          title="Followers-only chat"
          subtitle="Only viewers who follow you can send messages."
          checked={settings.followers_only}
          onChange={(v) => setSettings(p => ({ ...p, followers_only: v }))}
          testid="followers-only-toggle"
        />
        <ToggleRow
          Icon={LockKey}
          title="Subscribers-only chat"
          subtitle="Only active subscribers can send messages."
          checked={settings.subscribers_only}
          onChange={(v) => setSettings(p => ({ ...p, subscribers_only: v }))}
          testid="subscribers-only-toggle"
        />
      </div>

      {/* Rules */}
      <div className="mb-5">
        <label className="text-sm font-semibold text-white mb-2 flex items-center gap-2">
          <Scroll className="w-4 h-4" /> Chat rules
        </label>
        <p className="text-xs text-[#A0A0AB] mb-2">Viewers see these once and must accept before chatting. Empty = no rules shown.</p>
        <textarea
          value={settings.rules}
          onChange={(e) => setSettings(p => ({ ...p, rules: e.target.value }))}
          rows={6}
          placeholder={`1. No spamming.\n2. Be respectful.\n3. English only.`}
          className="w-full p-3 bg-[#1A1A24] border border-white/10 rounded-md text-white placeholder-[#A0A0AB] focus:outline-none focus:border-[#00E5FF] resize-y font-mono text-sm"
          data-testid="chat-rules-textarea"
        />
        <p className="text-xs text-[#A0A0AB] mt-1">{settings.rules.length}/2000 characters</p>
      </div>

      {/* Restricted words */}
      <div className="mb-5">
        <label className="text-sm font-semibold text-white mb-2 flex items-center gap-2">
          <Prohibit className="w-4 h-4 text-red-400" /> Restricted words
        </label>
        <p className="text-xs text-[#A0A0AB] mb-2">Comma-separated list of words to filter or block in chat.</p>
        <textarea
          value={wordsInput}
          onChange={(e) => setWordsInput(e.target.value)}
          rows={3}
          placeholder="word1, word2, phrase three"
          className="w-full p-3 bg-[#1A1A24] border border-white/10 rounded-md text-white placeholder-[#A0A0AB] focus:outline-none focus:border-[#00E5FF] resize-y text-sm"
          data-testid="restricted-words-input"
        />
        <div className="flex items-center gap-4 mt-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="rw_mode"
              checked={settings.restricted_words_mode === 'filter'}
              onChange={() => setSettings(p => ({ ...p, restricted_words_mode: 'filter' }))}
              data-testid="rw-mode-filter"
            />
            <span className="text-sm text-white">Filter (replace with ***)</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="rw_mode"
              checked={settings.restricted_words_mode === 'block'}
              onChange={() => setSettings(p => ({ ...p, restricted_words_mode: 'block' }))}
              data-testid="rw-mode-block"
            />
            <span className="text-sm text-white">Block entire message</span>
          </label>
        </div>
      </div>

      <Button onClick={save} disabled={saving} className="bg-[#00E5FF] text-black hover:bg-[#00B3CC] font-bold" data-testid="save-chat-settings-btn">
        {saving ? 'Saving…' : 'Save chat settings'}
      </Button>
    </div>
  );
}
