import React, { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Broadcast, PaperPlaneTilt } from '@phosphor-icons/react';
import { Button } from './ui/button';
import { Input } from './ui/input';

const API = process.env.REACT_APP_BACKEND_URL;

export default function RaidSection({ stream }) {
  const [target, setTarget] = useState('');
  const [sending, setSending] = useState(false);
  const [lastRaid, setLastRaid] = useState(null);

  if (!stream || !stream.stream_id) return null;
  const canRaid = !!(stream.is_live && stream.broadcasting);

  const startRaid = async () => {
    const cleaned = target.trim().replace(/^@/, '');
    if (!cleaned) {
      toast.error('Enter a target username');
      return;
    }
    setSending(true);
    try {
      const res = await axios.post(
        `${API}/api/streams/${stream.stream_id}/raid`,
        { target_username: cleaned },
        { withCredentials: true }
      );
      setLastRaid(res.data);
      setTarget('');
      toast.success(`Raid started! Sending ${res.data.viewer_count} viewer(s) to ${res.data.target_username} in ${res.data.countdown_seconds}s.`);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Raid failed');
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-6" data-testid="raid-section">
      <div className="flex items-center gap-2 mb-2">
        <Broadcast weight="fill" className="w-5 h-5 text-[#AA96DA]" />
        <h2 className="text-lg font-semibold text-white">Raid another streamer</h2>
      </div>
      <p className="text-sm text-[#A0A0AB] mb-4">
        Send all your current viewers to another live streamer. A 10-second countdown banner appears in your chat before auto-redirecting logged-in viewers.
      </p>

      {!canRaid && (
        <div className="rounded-lg bg-yellow-500/10 border border-yellow-500/20 text-xs text-yellow-300 px-3 py-2 mb-3" data-testid="raid-disabled-notice">
          You can only start a raid while your stream is live and broadcasting via OBS.
        </div>
      )}

      <div className="flex gap-2">
        <Input
          type="text"
          value={target}
          onChange={e => setTarget(e.target.value)}
          placeholder="@username (must be live)"
          disabled={!canRaid || sending}
          className="bg-[#1A1A24] border-white/10 text-white placeholder-[#A0A0AB] focus:border-[#AA96DA] disabled:opacity-50"
          data-testid="raid-target-input"
        />
        <Button
          type="button"
          onClick={startRaid}
          disabled={!canRaid || sending || !target.trim()}
          className="bg-[#AA96DA] text-black hover:bg-[#8B7AC4] font-bold disabled:opacity-50"
          data-testid="raid-start-btn"
        >
          <PaperPlaneTilt weight="fill" className="w-4 h-4 mr-2" />
          {sending ? 'Starting…' : 'Raid'}
        </Button>
      </div>

      {lastRaid && (
        <div className="mt-4 p-3 rounded-lg bg-[#AA96DA]/10 border border-[#AA96DA]/30 text-sm text-white" data-testid="raid-last-result">
          Raiding <span className="font-bold text-[#AA96DA]">@{lastRaid.target_username}</span> with{' '}
          <span className="font-bold">{lastRaid.viewer_count}</span> viewer(s).
        </div>
      )}
    </div>
  );
}
