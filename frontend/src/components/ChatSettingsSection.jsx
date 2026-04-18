import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { ChatsCircle, Scroll } from '@phosphor-icons/react';
import { Button } from './ui/button';

const API = process.env.REACT_APP_BACKEND_URL;

export default function ChatSettingsSection() {
  const [settings, setSettings] = useState({ chat_enabled: true, rules: '' });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    axios.get(`${API}/api/my/chat-settings`, { withCredentials: true })
      .then(res => setSettings({ chat_enabled: res.data.chat_enabled !== false, rules: res.data.rules || '' }))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/api/my/chat-settings`, settings, { withCredentials: true });
      toast.success('Chat settings saved');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return null;

  return (
    <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-6" data-testid="chat-settings-section">
      <div className="flex items-center justify-between flex-wrap gap-3 mb-5">
        <div className="flex items-center gap-3">
          <ChatsCircle className="w-6 h-6 text-[#00E5FF]" />
          <div>
            <h2 className="text-lg font-semibold text-white">Chat</h2>
            <p className="text-sm text-[#A0A0AB]">Toggle chat on/off and set rules viewers accept before posting</p>
          </div>
        </div>
        <label className="flex items-center gap-2 cursor-pointer px-3 py-1.5 bg-[#1A1A24] rounded-lg" data-testid="chat-enabled-toggle-label">
          <input type="checkbox" checked={settings.chat_enabled} onChange={(e) => setSettings(p => ({ ...p, chat_enabled: e.target.checked }))} data-testid="chat-enabled-toggle" />
          <span className="text-sm text-white font-semibold">Chat {settings.chat_enabled ? 'ON' : 'OFF'}</span>
        </label>
      </div>

      <div>
        <label className="text-sm font-semibold text-white mb-2 flex items-center gap-2">
          <Scroll className="w-4 h-4" /> Chat rules
        </label>
        <p className="text-xs text-[#A0A0AB] mb-2">Viewers will see these once when they open your stream and must accept before chatting. Leave empty to show no rules.</p>
        <textarea
          value={settings.rules}
          onChange={(e) => setSettings(p => ({ ...p, rules: e.target.value }))}
          rows={8}
          placeholder={`1. No spamming.\n2. Be respectful.\n3. English only.\n4. No self-promotion.`}
          className="w-full p-3 bg-[#1A1A24] border border-white/10 rounded-md text-white placeholder-[#A0A0AB] focus:outline-none focus:border-[#00E5FF] resize-y font-mono text-sm"
          data-testid="chat-rules-textarea"
        />
        <p className="text-xs text-[#A0A0AB] mt-1">{settings.rules.length}/2000 characters</p>
      </div>

      <div className="mt-4">
        <Button onClick={save} disabled={saving} className="bg-[#00E5FF] text-black hover:bg-[#00B3CC] font-bold" data-testid="save-chat-settings-btn">
          {saving ? 'Saving…' : 'Save chat settings'}
        </Button>
      </div>
    </div>
  );
}
