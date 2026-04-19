import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Smiley, Upload, TrashSimple, Lock, UsersThree } from '@phosphor-icons/react';
import { Button } from './ui/button';
import { Input } from './ui/input';

const API = process.env.REACT_APP_BACKEND_URL;
const MAX_EMOJIS = 60;

export default function EmojiUploadSection() {
  const [emotes, setEmotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [code, setCode] = useState(':myEmote:');
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [subsOnly, setSubsOnly] = useState(true);
  const [uploading, setUploading] = useState(false);

  const fetchEmotes = async () => {
    try {
      const res = await axios.get(`${API}/api/my/emotes`, { withCredentials: true });
      setEmotes(res.data);
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchEmotes(); }, []);

  const onFile = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > 512 * 1024) {
      toast.error('Emote must be under 512KB');
      return;
    }
    setFile(f);
    setPreview(URL.createObjectURL(f));
  };

  const onUpload = async () => {
    if (!file) { toast.error('Pick an image first'); return; }
    if (!code.startsWith(':') || !code.endsWith(':') || code.length < 3) {
      toast.error('Code must look like :myEmote:');
      return;
    }
    if (emotes.length >= MAX_EMOJIS) {
      toast.error(`Max ${MAX_EMOJIS} emojis`);
      return;
    }
    const fd = new FormData();
    fd.append('file', file);
    setUploading(true);
    try {
      await axios.post(`${API}/api/my/emotes?code=${encodeURIComponent(code)}&subscribers_only=${subsOnly}`, fd, {
        withCredentials: true,
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      toast.success('Emoji uploaded');
      setFile(null); setPreview(null); setCode(':myEmote:');
      fetchEmotes();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const toggleSubsOnly = async (e) => {
    const next = !e.subscribers_only;
    try {
      await axios.put(`${API}/api/my/emotes/${e.emote_id}`, { subscribers_only: next }, { withCredentials: true });
      setEmotes(prev => prev.map(x => x.emote_id === e.emote_id ? { ...x, subscribers_only: next } : x));
    } catch { toast.error('Update failed'); }
  };

  const remove = async (e) => {
    if (!window.confirm(`Delete ${e.code}?`)) return;
    try {
      await axios.delete(`${API}/api/my/emotes/${e.emote_id}`, { withCredentials: true });
      setEmotes(prev => prev.filter(x => x.emote_id !== e.emote_id));
      toast.success('Deleted');
    } catch { toast.error('Delete failed'); }
  };

  if (loading) return null;

  return (
    <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-6" data-testid="emoji-upload-section">
      <div className="flex items-center justify-between flex-wrap gap-3 mb-5">
        <div className="flex items-center gap-3">
          <Smiley className="w-6 h-6 text-yellow-400" />
          <div>
            <h2 className="text-lg font-semibold text-white">Emoji Upload</h2>
            <p className="text-sm text-[#A0A0AB]">Upload up to {MAX_EMOJIS} custom emojis for your viewers ({emotes.length}/{MAX_EMOJIS})</p>
          </div>
        </div>
      </div>

      {/* Upload form */}
      {emotes.length < MAX_EMOJIS && (
        <div className="p-4 bg-[#1A1A24] rounded-lg mb-4">
          <div className="grid grid-cols-1 md:grid-cols-[auto_1fr_auto_auto] gap-3 items-start">
            <label className="flex items-center justify-center w-20 h-20 bg-[#0F0F16] border-2 border-dashed border-white/10 rounded-lg cursor-pointer hover:border-[#00E5FF]/50 transition-colors" data-testid="emote-file-label">
              {preview ? (
                <img src={preview} alt="preview" className="w-full h-full object-contain p-2" />
              ) : (
                <Upload className="w-6 h-6 text-[#A0A0AB]" />
              )}
              <input type="file" accept="image/*" onChange={onFile} className="hidden" data-testid="emote-file-input" />
            </label>

            <div className="space-y-2">
              <div>
                <label className="text-xs text-[#A0A0AB] block mb-1">Emote code (use like :myEmote:)</label>
                <Input value={code} onChange={(e) => setCode(e.target.value)} className="bg-[#0F0F16] border-white/10 text-white font-mono" data-testid="emote-code-input" />
              </div>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="radio" checked={subsOnly} onChange={() => setSubsOnly(true)} data-testid="emote-subs-only" />
                  <Lock className="w-4 h-4 text-[#00E5FF]" />
                  <span className="text-sm text-white">Subscribers only</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="radio" checked={!subsOnly} onChange={() => setSubsOnly(false)} data-testid="emote-all-viewers" />
                  <UsersThree className="w-4 h-4 text-green-400" />
                  <span className="text-sm text-white">All viewers</span>
                </label>
              </div>
            </div>

            <Button onClick={onUpload} disabled={uploading || !file} className="bg-[#00E5FF] text-black hover:bg-[#00B3CC] font-bold whitespace-nowrap" data-testid="emote-upload-btn">
              {uploading ? 'Uploading…' : 'Upload'}
            </Button>
          </div>
        </div>
      )}

      {/* Existing emotes grid */}
      {emotes.length > 0 ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2">
          {emotes.map((e) => (
            <div key={e.emote_id} className="p-3 bg-[#1A1A24] rounded-lg flex flex-col items-center gap-2" data-testid={`emote-card-${e.code}`}>
              <img src={e.url?.startsWith('http') ? e.url : `${API}${e.url}`} alt={e.code} className="w-12 h-12 object-contain" />
              <code className="text-xs text-[#00E5FF] font-mono truncate max-w-full">{e.code}</code>
              <button onClick={() => toggleSubsOnly(e)} className={`w-full text-[11px] font-medium px-2 py-1 rounded ${e.subscribers_only ? 'bg-[#00E5FF]/10 text-[#00E5FF]' : 'bg-green-500/10 text-green-400'}`} data-testid={`emote-toggle-${e.code}`}>
                {e.subscribers_only ? 'Subs only' : 'All viewers'}
              </button>
              <button onClick={() => remove(e)} className="text-[11px] text-red-400 hover:text-red-300 flex items-center gap-1" data-testid={`emote-delete-${e.code}`}>
                <TrashSimple className="w-3 h-3" /> Remove
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="p-6 bg-[#1A1A24] rounded-lg text-center text-sm text-[#A0A0AB]">
          No custom emojis yet. Upload PNG/GIF images (≤512KB) for your community.
        </div>
      )}
    </div>
  );
}
