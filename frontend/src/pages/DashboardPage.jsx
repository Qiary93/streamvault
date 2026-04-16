import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Broadcast, Eye, CurrencyDollar, Users, Plus, X, Star, Copy, Check, Record, Stop, Link as LinkIcon } from '@phosphor-icons/react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { toast } from 'sonner';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

export default function DashboardPage() {
  const { user } = useAuth();
  const [myStream, setMyStream] = useState(null);
  const [categories, setCategories] = useState([]);
  const [donations, setDonations] = useState([]);
  const [subscribers, setSubscribers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [streamKeyCopied, setStreamKeyCopied] = useState(false);
  const [whipUrlCopied, setWhipUrlCopied] = useState(false);
  const [whipTokenCopied, setWhipTokenCopied] = useState(false);
  const [recording, setRecording] = useState(false);
  const [streamForm, setStreamForm] = useState({
    title: '',
    description: '',
    category_id: ''
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [streamRes, categoriesRes, donationsRes, subsRes] = await Promise.all([
        axios.get(`${API}/api/my/stream`, { withCredentials: true }).catch(() => ({ data: null })),
        axios.get(`${API}/api/categories`),
        axios.get(`${API}/api/donations/received`, { withCredentials: true }).catch(() => ({ data: [] })),
        axios.get(`${API}/api/subscriptions/subscribers`, { withCredentials: true }).catch(() => ({ data: [] }))
      ]);
      
      setMyStream(streamRes.data);
      setCategories(categoriesRes.data);
      setDonations(donationsRes.data);
      setSubscribers(subsRes.data);
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const copyStreamKey = () => {
    if (user?.stream_key) {
      navigator.clipboard.writeText(user.stream_key);
      setStreamKeyCopied(true);
      toast.success('Stream key copied!');
      setTimeout(() => setStreamKeyCopied(false), 2000);
    }
  };

  const handleCreateStream = async (e) => {
    e.preventDefault();
    
    if (!streamForm.title || !streamForm.category_id) {
      toast.error('Please fill in all required fields');
      return;
    }

    try {
      const response = await axios.post(`${API}/api/streams`, streamForm, {
        withCredentials: true
      });
      setMyStream(response.data);
      setCreateOpen(false);
      toast.success('Stream started!');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create stream');
    }
  };

  const handleEndStream = async () => {
    if (!myStream) return;

    try {
      await axios.delete(`${API}/api/streams/${myStream.stream_id}`, {
        withCredentials: true
      });
      setMyStream(null);
      toast.success('Stream ended');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to end stream');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="w-8 h-8 border-2 border-[#00E5FF] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const totalDonations = donations.reduce((sum, d) => sum + (d.amount || 0), 0);

  return (
    <div className="p-4 lg:p-6 space-y-6" data-testid="dashboard-page">
      <h1 className="text-2xl lg:text-3xl font-bold text-white font-['Outfit']">Dashboard</h1>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-[#00E5FF]/10 rounded-lg">
              <Users className="w-5 h-5 text-[#00E5FF]" />
            </div>
            <div>
              <p className="text-sm text-[#A0A0AB]">Followers</p>
              <p className="text-xl font-bold text-white">{user?.follower_count?.toLocaleString() || 0}</p>
            </div>
          </div>
        </div>

        <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-500/10 rounded-lg">
              <CurrencyDollar className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <p className="text-sm text-[#A0A0AB]">Total Donations</p>
              <p className="text-xl font-bold text-white">${totalDonations.toFixed(2)}</p>
            </div>
          </div>
        </div>

        <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-yellow-500/10 rounded-lg">
              <Star className="w-5 h-5 text-yellow-400" />
            </div>
            <div>
              <p className="text-sm text-[#A0A0AB]">Subscribers</p>
              <p className="text-xl font-bold text-white">{subscribers.length}</p>
            </div>
          </div>
        </div>

        <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-red-500/10 rounded-lg">
              <Eye className="w-5 h-5 text-red-400" />
            </div>
            <div>
              <p className="text-sm text-[#A0A0AB]">Current Viewers</p>
              <p className="text-xl font-bold text-white">{myStream?.viewer_count?.toLocaleString() || 0}</p>
            </div>
          </div>
        </div>

        <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-4">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${myStream ? 'bg-green-500/10' : 'bg-[#292938]'}`}>
              <Broadcast className={`w-5 h-5 ${myStream ? 'text-green-400' : 'text-[#A0A0AB]'}`} />
            </div>
            <div>
              <p className="text-sm text-[#A0A0AB]">Stream Status</p>
              <p className={`text-xl font-bold ${myStream ? 'text-green-400' : 'text-white'}`}>
                {myStream ? 'LIVE' : 'Offline'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Stream Controls */}
      <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Stream Controls</h2>
        
        {myStream ? (
          <div className="space-y-4">
            {/* Stream Status Preview */}
            <div className="aspect-video rounded-lg overflow-hidden bg-black flex items-center justify-center relative">
              <div className="text-center p-6">
                <Broadcast weight="fill" className="w-16 h-16 text-[#00E5FF]/30 mx-auto mb-4" />
                <p className="text-white font-semibold text-lg mb-1">Stream is Active</p>
                <p className="text-[#A0A0AB] text-sm mb-4">
                  Use OBS or your preferred streaming software to broadcast.
                </p>
                <div className="inline-flex items-center gap-2 px-4 py-2 bg-[#1A1A24] rounded-lg border border-white/10">
                  <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
                  <span className="text-sm text-green-400 font-medium">Waiting for stream input...</span>
                </div>
              </div>
              <div className="absolute top-3 left-3 flex items-center gap-1.5 px-2 py-1 bg-red-500 rounded text-xs font-bold text-white">
                <span className="w-2 h-2 bg-white rounded-full live-indicator" />
                LIVE
              </div>
            </div>

            <div className="flex items-center justify-between p-4 bg-[#1A1A24] rounded-lg">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="w-2 h-2 bg-red-500 rounded-full live-indicator" />
                  <span className="text-sm font-medium text-red-400">LIVE</span>
                </div>
                <h3 className="text-white font-semibold">{myStream.title}</h3>
                <p className="text-sm text-[#A0A0AB]">{myStream.category_name}</p>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  onClick={async () => {
                    try {
                      if (recording) {
                        await axios.post(`${API}/api/streams/${myStream.stream_id}/record/stop`, {}, { withCredentials: true });
                        setRecording(false);
                        toast.success('Recording stopped');
                      } else {
                        await axios.post(`${API}/api/streams/${myStream.stream_id}/record/start`, {}, { withCredentials: true });
                        setRecording(true);
                        toast.success('Recording started');
                      }
                    } catch (error) {
                      toast.error(error.response?.data?.detail || 'Recording error');
                    }
                  }}
                  className={recording 
                    ? 'bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30' 
                    : 'bg-[#292938] text-white hover:bg-[#3D3D52]'}
                  data-testid="record-btn"
                >
                  {recording ? <><Stop className="w-4 h-4 mr-2" /> Stop Recording</> : <><Record className="w-4 h-4 mr-2" /> Record</>}
                </Button>
                <Button
                  onClick={handleEndStream}
                  variant="destructive"
                  className="bg-red-500 hover:bg-red-600 text-white"
                  data-testid="end-stream-btn"
                >
                  <X className="w-4 h-4 mr-2" /> End Stream
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger asChild>
              <Button 
                className="bg-[#00E5FF] text-black font-bold hover:bg-[#00B3CC]"
                data-testid="start-stream-btn"
              >
                <Plus className="w-4 h-4 mr-2" /> Start Streaming
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-[#0F0F16] border-white/10">
              <DialogHeader>
                <DialogTitle className="text-white">Start a Stream</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleCreateStream} className="space-y-4 pt-4">
                <div>
                  <label className="text-sm text-[#A0A0AB] block mb-1.5">Title *</label>
                  <Input
                    value={streamForm.title}
                    onChange={(e) => setStreamForm(prev => ({ ...prev, title: e.target.value }))}
                    placeholder="My awesome stream"
                    className="bg-[#1A1A24] border-white/10 text-white"
                    data-testid="stream-title-input"
                  />
                </div>

                <div>
                  <label className="text-sm text-[#A0A0AB] block mb-1.5">Category *</label>
                  <Select 
                    value={streamForm.category_id}
                    onValueChange={(value) => setStreamForm(prev => ({ ...prev, category_id: value }))}
                  >
                    <SelectTrigger className="bg-[#1A1A24] border-white/10 text-white" data-testid="stream-category-select">
                      <SelectValue placeholder="Select a category" />
                    </SelectTrigger>
                    <SelectContent className="bg-[#0F0F16] border-white/10">
                      {categories.map((cat) => (
                        <SelectItem key={cat.category_id} value={cat.category_id} className="text-white">
                          {cat.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <label className="text-sm text-[#A0A0AB] block mb-1.5">Description</label>
                  <textarea
                    value={streamForm.description}
                    onChange={(e) => setStreamForm(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="What's your stream about?"
                    rows={3}
                    className="w-full p-3 bg-[#1A1A24] border border-white/10 rounded-md text-white placeholder-[#A0A0AB] focus:outline-none focus:border-[#00E5FF] resize-none"
                    data-testid="stream-description-input"
                  />
                </div>

                <Button 
                  type="submit"
                  className="w-full bg-[#00E5FF] text-black font-bold hover:bg-[#00B3CC]"
                  data-testid="create-stream-submit-btn"
                >
                  Go Live
                </Button>
              </form>
            </DialogContent>
          </Dialog>
        )}
      </div>

      {/* OBS Setup & Stream Credentials */}
      <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-6" data-testid="obs-setup-section">
        <div className="flex items-center gap-3 mb-6">
          <LinkIcon className="w-6 h-6 text-[#00E5FF]" />
          <div>
            <h2 className="text-lg font-semibold text-white">OBS Setup</h2>
            <p className="text-sm text-[#A0A0AB]">Connect your streaming software to StreamVault</p>
          </div>
        </div>

        {/* Step-by-step instructions */}
        <div className="mb-6 p-4 bg-[#1A1A24] rounded-lg border border-[#00E5FF]/20">
          <h3 className="text-sm font-bold text-[#00E5FF] uppercase tracking-wider mb-3">Quick Setup Guide</h3>
          <ol className="text-sm text-[#A0A0AB] space-y-2 list-decimal pl-5">
            <li>Open <span className="text-white font-medium">OBS Studio</span> &rarr; Settings &rarr; Stream</li>
            <li>Set Service to <span className="text-white font-medium">WHIP</span></li>
            <li>Paste the <span className="text-white font-medium">Server URL</span> below into the "Server" field</li>
            <li>Paste the <span className="text-white font-medium">Bearer Token</span> below into the "Bearer Token" field</li>
            <li>Click <span className="text-white font-medium">Apply</span>, then <span className="text-white font-medium">Start Streaming</span> in OBS</li>
          </ol>
        </div>

        <div className="space-y-4">
          {/* WHIP Server URL */}
          <div className="p-4 bg-[#1A1A24] rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium text-white">Server URL (WHIP)</p>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  const url = myStream?.whip_url || '';
                  if (url) {
                    navigator.clipboard.writeText(url);
                    setWhipUrlCopied(true);
                    toast.success('Server URL copied!');
                    setTimeout(() => setWhipUrlCopied(false), 2000);
                  }
                }}
                className="text-[#00E5FF] hover:text-[#00B3CC] hover:bg-white/10 gap-2"
                data-testid="copy-whip-url-btn"
              >
                {whipUrlCopied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                {whipUrlCopied ? 'Copied!' : 'Copy'}
              </Button>
            </div>
            <code className="text-sm text-[#00E5FF] bg-[#292938] px-4 py-3 rounded-lg block font-mono break-all" data-testid="whip-url-display">
              {myStream?.whip_url || 'Start a stream to generate URL'}
            </code>
            <p className="text-xs text-[#A0A0AB] mt-2">Same URL for all streams. Paste into OBS &rarr; Settings &rarr; Stream &rarr; Server</p>
          </div>

          {/* Bearer Token */}
          <div className="p-4 bg-[#1A1A24] rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium text-white">Bearer Token</p>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  const token = myStream?.whip_token || '';
                  if (token) {
                    navigator.clipboard.writeText(token);
                    setWhipTokenCopied(true);
                    toast.success('Bearer Token copied!');
                    setTimeout(() => setWhipTokenCopied(false), 2000);
                  }
                }}
                className="text-[#00E5FF] hover:text-[#00B3CC] hover:bg-white/10 gap-2"
                data-testid="copy-whip-token-btn"
              >
                {whipTokenCopied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                {whipTokenCopied ? 'Copied!' : 'Copy'}
              </Button>
            </div>
            <code className="text-sm text-[#00E5FF] bg-[#292938] px-4 py-3 rounded-lg block font-mono break-all max-h-20 overflow-hidden" data-testid="whip-token-display">
              {myStream?.whip_token 
                ? myStream.whip_token.substring(0, 60) + '...' 
                : 'Start a stream to generate token'}
            </code>
            <p className="text-xs text-[#A0A0AB] mt-2">Unique per stream session. Paste into OBS &rarr; Bearer Token field</p>
          </div>

          {/* Legacy Stream Key */}
          <details className="group">
            <summary className="text-sm text-[#A0A0AB] cursor-pointer hover:text-white transition-colors">
              Show legacy stream key (advanced)
            </summary>
            <div className="mt-3 p-4 bg-[#1A1A24] rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm text-[#A0A0AB]">Stream Key</p>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={copyStreamKey}
                  className="text-[#00E5FF] hover:text-[#00B3CC] hover:bg-white/10 gap-2"
                  data-testid="copy-stream-key-btn"
                >
                  {streamKeyCopied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                  {streamKeyCopied ? 'Copied!' : 'Copy'}
                </Button>
              </div>
              <code className="text-sm text-[#00E5FF] bg-[#292938] px-4 py-3 rounded-lg block font-mono break-all" data-testid="stream-key-display">
                {user?.stream_key || 'Loading...'}
              </code>
            </div>
          </details>
        </div>
      </div>

      {/* Recent Donations */}
      <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Recent Donations</h2>
        
        {donations.length > 0 ? (
          <div className="space-y-3">
            {donations.slice(0, 5).map((donation) => (
              <div 
                key={donation.donation_id}
                className="flex items-center justify-between p-3 bg-[#1A1A24] rounded-lg"
              >
                <div>
                  <p className="text-white font-medium">{donation.donor_username}</p>
                  {donation.message && (
                    <p className="text-sm text-[#A0A0AB] truncate max-w-xs">{donation.message}</p>
                  )}
                </div>
                <span className="text-[#00E5FF] font-bold">${donation.amount?.toFixed(2)}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-[#A0A0AB] text-center py-8">No donations yet</p>
        )}
      </div>
    </div>
  );
}
