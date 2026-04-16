import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Gavel, Clock, Timer, UserMinus, UserPlus, ShieldCheck } from '@phosphor-icons/react';
import { Button } from './ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from './ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { toast } from 'sonner';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

export default function ModControls({ streamId, targetUserId, targetUsername }) {
  const { user } = useAuth();
  const [modStatus, setModStatus] = useState({ is_mod: false, is_streamer: false, slow_mode: 0 });
  const [bans, setBans] = useState([]);
  const [mods, setMods] = useState([]);
  const [showPanel, setShowPanel] = useState(false);

  const fetchModStatus = useCallback(async () => {
    if (!user) return;
    try {
      const response = await axios.get(`${API}/api/streams/${streamId}/mod-status`, {
        withCredentials: true
      });
      setModStatus(response.data);
    } catch (error) {
      // User not logged in or not a mod
    }
  }, [user, streamId]);

  useEffect(() => {
    fetchModStatus();
  }, [fetchModStatus]);

  const handleBan = async (userId, username) => {
    try {
      await axios.post(`${API}/api/streams/${streamId}/ban/${userId}`, 
        { reason: 'Banned by moderator' },
        { withCredentials: true, headers: { 'Content-Type': 'application/json' } }
      );
      toast.success(`${username} has been banned`);
      fetchBans();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to ban user');
    }
  };

  const handleUnban = async (userId) => {
    try {
      await axios.delete(`${API}/api/streams/${streamId}/ban/${userId}`, {
        withCredentials: true
      });
      toast.success('User unbanned');
      fetchBans();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to unban user');
    }
  };

  const handleTimeout = async (userId, username, duration) => {
    try {
      await axios.post(`${API}/api/streams/${streamId}/timeout/${userId}`,
        { duration, reason: 'Timed out by moderator' },
        { withCredentials: true, headers: { 'Content-Type': 'application/json' } }
      );
      toast.success(`${username} timed out for ${duration}s`);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to timeout user');
    }
  };

  const handleSlowMode = async (duration) => {
    try {
      await axios.put(`${API}/api/streams/${streamId}/slow-mode`,
        { duration },
        { withCredentials: true }
      );
      setModStatus(prev => ({ ...prev, slow_mode: duration }));
      toast.success(duration === 0 ? 'Slow mode disabled' : `Slow mode set to ${duration}s`);
    } catch (error) {
      toast.error('Failed to set slow mode');
    }
  };

  const handleAssignMod = async (userId) => {
    try {
      await axios.post(`${API}/api/streams/${streamId}/mod/${userId}`, {}, {
        withCredentials: true
      });
      toast.success('Mod assigned!');
      fetchMods();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to assign mod');
    }
  };

  const handleRemoveMod = async (userId) => {
    try {
      await axios.delete(`${API}/api/streams/${streamId}/mod/${userId}`, {
        withCredentials: true
      });
      toast.success('Mod removed');
      fetchMods();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to remove mod');
    }
  };

  const fetchBans = async () => {
    try {
      const response = await axios.get(`${API}/api/streams/${streamId}/bans`, {
        withCredentials: true
      });
      setBans(response.data);
    } catch (error) {
      // Not authorized
    }
  };

  const fetchMods = async () => {
    try {
      const response = await axios.get(`${API}/api/streams/${streamId}/mods`);
      setMods(response.data);
    } catch (error) {
      // Error
    }
  };

  if (!modStatus.is_mod && !modStatus.is_streamer) return null;

  // Inline mod actions for a specific user in chat
  if (targetUserId && targetUserId !== user?.user_id) {
    return (
      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={() => handleTimeout(targetUserId, targetUsername, 60)}
          className="p-1 rounded hover:bg-white/10 text-[#A0A0AB] hover:text-yellow-400"
          title="Timeout 1min"
        >
          <Clock className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={() => handleBan(targetUserId, targetUsername)}
          className="p-1 rounded hover:bg-white/10 text-[#A0A0AB] hover:text-red-400"
          title="Ban"
        >
          <Gavel className="w-3.5 h-3.5" />
        </button>
        {modStatus.is_streamer && (
          <button
            onClick={() => handleAssignMod(targetUserId)}
            className="p-1 rounded hover:bg-white/10 text-[#A0A0AB] hover:text-green-400"
            title="Make mod"
          >
            <ShieldCheck className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    );
  }

  // Full mod panel button
  return (
    <Dialog open={showPanel} onOpenChange={(open) => { setShowPanel(open); if (open) { fetchBans(); fetchMods(); } }}>
      <DialogTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="text-[#A0A0AB] hover:text-[#00E5FF] hover:bg-white/10 gap-1.5"
          data-testid="mod-panel-btn"
        >
          <ShieldCheck className="w-4 h-4" />
          <span className="text-xs">Mod</span>
        </Button>
      </DialogTrigger>
      <DialogContent className="bg-[#0F0F16] border-white/10 max-w-lg max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-white flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-[#00E5FF]" /> Moderation Panel
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-6 pt-4">
          {/* Slow Mode */}
          <div>
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <Timer className="w-4 h-4 text-yellow-400" /> Slow Mode
            </h3>
            <div className="flex flex-wrap gap-2">
              {[
                { value: 0, label: 'Off' },
                { value: 3, label: '3s' },
                { value: 5, label: '5s' },
                { value: 10, label: '10s' },
                { value: 30, label: '30s' },
              ].map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => handleSlowMode(opt.value)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors
                    ${modStatus.slow_mode === opt.value 
                      ? 'bg-[#00E5FF] text-black' 
                      : 'bg-[#1A1A24] text-[#A0A0AB] hover:text-white border border-white/10'}`}
                  data-testid={`slow-mode-${opt.value}`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            {modStatus.slow_mode > 0 && (
              <p className="text-xs text-yellow-400 mt-2">Slow mode active: {modStatus.slow_mode}s between messages</p>
            )}
          </div>

          {/* Timeout Presets */}
          <div>
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <Clock className="w-4 h-4 text-orange-400" /> Quick Timeout
            </h3>
            <p className="text-xs text-[#A0A0AB] mb-2">Hover over usernames in chat to timeout/ban individual users</p>
            <div className="flex gap-2">
              <div className="px-3 py-2 bg-[#1A1A24] rounded-lg border border-white/10 text-xs text-[#A0A0AB]">
                1 min
              </div>
              <div className="px-3 py-2 bg-[#1A1A24] rounded-lg border border-white/10 text-xs text-[#A0A0AB]">
                5 min
              </div>
              <div className="px-3 py-2 bg-[#1A1A24] rounded-lg border border-white/10 text-xs text-[#A0A0AB]">
                10 min
              </div>
            </div>
          </div>

          {/* Banned Users */}
          <div>
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <Gavel className="w-4 h-4 text-red-400" /> Banned Users ({bans.length})
            </h3>
            {bans.length > 0 ? (
              <div className="space-y-2 max-h-40 overflow-y-auto">
                {bans.map((ban) => (
                  <div key={ban.ban_id || ban.user_id} className="flex items-center justify-between p-2 bg-[#1A1A24] rounded-lg">
                    <div>
                      <span className="text-sm text-white">{ban.username}</span>
                      {ban.reason && <p className="text-xs text-[#A0A0AB]">{ban.reason}</p>}
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleUnban(ban.user_id)}
                      className="text-green-400 hover:text-green-300 hover:bg-green-500/10 text-xs"
                    >
                      Unban
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-[#A0A0AB]">No banned users</p>
            )}
          </div>

          {/* Moderators */}
          {modStatus.is_streamer && (
            <div>
              <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-green-400" /> Moderators ({mods.length})
              </h3>
              {mods.length > 0 ? (
                <div className="space-y-2 max-h-40 overflow-y-auto">
                  {mods.map((mod) => (
                    <div key={mod.mod_id || mod.user_id} className="flex items-center justify-between p-2 bg-[#1A1A24] rounded-lg">
                      <span className="text-sm text-white">{mod.username}</span>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleRemoveMod(mod.user_id)}
                        className="text-red-400 hover:text-red-300 hover:bg-red-500/10 text-xs"
                      >
                        Remove
                      </Button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-[#A0A0AB]">No moderators assigned. Hover over usernames in chat to assign.</p>
              )}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
