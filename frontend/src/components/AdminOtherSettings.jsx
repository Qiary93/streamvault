import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Gear, Trophy, Path } from '@phosphor-icons/react';
import { Button } from './ui/button';

const API = process.env.REACT_APP_BACKEND_URL;

export default function AdminOtherSettings() {
  const [settings, setSettings] = useState({ achievements_enabled: true, path_enabled: true });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    axios.get(`${API}/api/admin/other-settings`, { withCredentials: true })
      .then(res => setSettings({
        achievements_enabled: res.data.achievements_enabled !== false,
        path_enabled: res.data.path_enabled !== false,
      }))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/api/admin/other-settings`, settings, { withCredentials: true });
      toast.success('Other settings saved');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return null;

  const Row = ({ Icon, title, subtitle, checked, onChange, testid }) => (
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
    <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-6 mt-6" data-testid="admin-other-settings">
      <div className="flex items-center gap-3 mb-5">
        <Gear className="w-6 h-6 text-[#00E5FF]" />
        <div>
          <h2 className="text-lg font-semibold text-white">Other Settings</h2>
          <p className="text-sm text-[#A0A0AB]">Toggle platform-wide features</p>
        </div>
      </div>

      <div className="space-y-2 mb-4">
        <Row
          Icon={Trophy}
          title={`Achievements: ${settings.achievements_enabled ? 'ON' : 'OFF'}`}
          subtitle="Show the Achievements section on user profiles."
          checked={settings.achievements_enabled}
          onChange={(v) => setSettings(p => ({ ...p, achievements_enabled: v }))}
          testid="toggle-achievements"
        />
        <Row
          Icon={Path}
          title={`Path to a perfect streamer: ${settings.path_enabled ? 'ON' : 'OFF'}`}
          subtitle="Show the Path section on the streamer dashboard."
          checked={settings.path_enabled}
          onChange={(v) => setSettings(p => ({ ...p, path_enabled: v }))}
          testid="toggle-path"
        />
      </div>

      <Button onClick={save} disabled={saving} className="bg-[#00E5FF] text-black hover:bg-[#00B3CC] font-bold" data-testid="save-other-settings-btn">
        {saving ? 'Saving…' : 'Save other settings'}
      </Button>
    </div>
  );
}
