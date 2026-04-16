import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Broadcast, Eye, CurrencyDollar, Users, Plus, X, Star, Copy, Check, Record, Stop } from '@phosphor-icons/react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { LiveKitStreamer } from '../components/LiveKitPlayer';
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
            {/* LiveKit Streamer Preview */}
            <div className="aspect-video rounded-lg overflow-hidden bg-black">
              <LiveKitStreamer roomName={`stream_${myStream.stream_id}`} />
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

      {/* Stream Key */}
      <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-6" data-testid="stream-key-section">
        <h2 className="text-lg font-semibold text-white mb-4">Stream Key</h2>
        <div className="p-4 bg-[#1A1A24] rounded-lg">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm text-[#A0A0AB]">Your Stream Key</p>
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
          <p className="text-xs text-[#A0A0AB] mt-3">
            Use this key in your streaming software (OBS, Streamlabs, etc.) to broadcast to StreamVault.
          </p>
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
