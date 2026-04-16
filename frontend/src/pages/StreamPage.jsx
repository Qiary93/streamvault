import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Eye, Users, Heart, HeartBreak, CurrencyDollar, Share } from '@phosphor-icons/react';
import { Avatar, AvatarFallback, AvatarImage } from '../components/ui/avatar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import ChatBox from '../components/ChatBox';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

const donationPackages = [
  { id: 'small', amount: 5, label: '$5' },
  { id: 'medium', amount: 10, label: '$10' },
  { id: 'large', amount: 25, label: '$25' },
  { id: 'huge', amount: 50, label: '$50' },
  { id: 'mega', amount: 100, label: '$100' },
];

export default function StreamPage() {
  const { streamId } = useParams();
  const { user } = useAuth();
  const [stream, setStream] = useState(null);
  const [loading, setLoading] = useState(true);
  const [following, setFollowing] = useState(false);
  const [donationOpen, setDonationOpen] = useState(false);
  const [selectedPackage, setSelectedPackage] = useState(null);
  const [donationMessage, setDonationMessage] = useState('');

  useEffect(() => {
    const fetchStream = async () => {
      try {
        const response = await axios.get(`${API}/api/streams/${streamId}`, {
          withCredentials: true
        });
        setStream(response.data);
        setFollowing(response.data.is_following);
      } catch (error) {
        console.error('Error fetching stream:', error);
        toast.error('Stream not found');
      } finally {
        setLoading(false);
      }
    };

    fetchStream();
  }, [streamId]);

  const handleFollow = async () => {
    if (!user) {
      toast.error('Please log in to follow');
      return;
    }

    try {
      if (following) {
        await axios.delete(`${API}/api/users/${stream.user_id}/follow`, {
          withCredentials: true
        });
        setFollowing(false);
        toast.success('Unfollowed');
      } else {
        await axios.post(`${API}/api/users/${stream.user_id}/follow`, {}, {
          withCredentials: true
        });
        setFollowing(true);
        toast.success('Followed!');
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update follow');
    }
  };

  const handleDonate = async () => {
    if (!user) {
      toast.error('Please log in to donate');
      return;
    }

    if (!selectedPackage) {
      toast.error('Please select an amount');
      return;
    }

    try {
      const response = await axios.post(`${API}/api/donations/checkout`, {
        streamer_id: stream.user_id,
        package_id: selectedPackage,
        origin_url: window.location.origin,
        message: donationMessage
      }, { withCredentials: true });

      // Redirect to Stripe checkout
      window.location.href = response.data.url;
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to process donation');
    }
  };

  const handleShare = () => {
    navigator.clipboard.writeText(window.location.href);
    toast.success('Link copied to clipboard!');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="w-8 h-8 border-2 border-[#00E5FF] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!stream) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh]">
        <h2 className="text-xl font-bold text-white mb-2">Stream not found</h2>
        <Link to="/" className="text-[#00E5FF] hover:underline">Go back home</Link>
      </div>
    );
  }

  return (
    <div className="min-h-[calc(100vh-64px)] grid grid-cols-1 lg:grid-cols-12" data-testid="stream-page">
      {/* Main Content */}
      <div className="lg:col-span-9 flex flex-col overflow-y-auto">
        {/* Video Player */}
        <div className="relative aspect-video bg-black" data-testid="video-player">
          {stream.thumbnail_url ? (
            <img 
              src={stream.thumbnail_url} 
              alt={stream.title}
              className="w-full h-full object-cover"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-[#0F0F16] to-[#1A1A24]">
              <span className="text-6xl font-black text-[#292938]">LIVE</span>
            </div>
          )}
          
          {/* Live badge */}
          {stream.is_live && (
            <div className="absolute top-4 left-4 flex items-center gap-2 px-3 py-1.5 bg-red-500 rounded text-sm font-bold text-white">
              <span className="w-2 h-2 bg-white rounded-full live-indicator" />
              LIVE
            </div>
          )}

          {/* Viewer count */}
          <div className="absolute bottom-4 left-4 flex items-center gap-2 px-3 py-1.5 bg-black/70 rounded text-sm text-white">
            <Eye className="w-4 h-4" />
            {stream.viewer_count?.toLocaleString() || 0} viewers
          </div>
        </div>

        {/* Stream Info */}
        <div className="p-4 lg:p-6 border-b border-white/5">
          <div className="flex flex-col lg:flex-row lg:items-start gap-4">
            {/* Streamer Info */}
            <div className="flex gap-4 flex-1">
              <Link to={`/user/${stream.username}`}>
                <Avatar className={`w-14 h-14 ${stream.is_live ? 'avatar-live' : ''}`}>
                  <AvatarImage src={stream.avatar_url} alt={stream.display_name || stream.username} />
                  <AvatarFallback className="bg-[#292938] text-[#00E5FF] text-xl">
                    {(stream.display_name || stream.username)?.charAt(0).toUpperCase()}
                  </AvatarFallback>
                </Avatar>
              </Link>

              <div className="min-w-0 flex-1">
                <h1 className="text-lg lg:text-xl font-bold text-white mb-1" data-testid="stream-title">
                  {stream.title}
                </h1>
                <Link 
                  to={`/user/${stream.username}`}
                  className="text-[#00E5FF] hover:underline font-medium"
                  data-testid="streamer-link"
                >
                  {stream.display_name || stream.username}
                </Link>
                <div className="flex items-center gap-4 mt-2 text-sm text-[#A0A0AB]">
                  {stream.category_name && (
                    <Link 
                      to={`/category/${stream.category_id}`}
                      className="hover:text-[#00E5FF] transition-colors"
                    >
                      {stream.category_name}
                    </Link>
                  )}
                  <span className="flex items-center gap-1">
                    <Users className="w-4 h-4" />
                    {stream.follower_count?.toLocaleString() || 0} followers
                  </span>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2">
              <Button
                onClick={handleFollow}
                variant={following ? 'secondary' : 'default'}
                className={following 
                  ? 'bg-[#292938] text-white hover:bg-[#3D3D52]' 
                  : 'bg-[#00E5FF] text-black hover:bg-[#00B3CC]'}
                data-testid="follow-btn"
              >
                {following ? (
                  <><HeartBreak className="w-4 h-4 mr-2" /> Unfollow</>
                ) : (
                  <><Heart className="w-4 h-4 mr-2" /> Follow</>
                )}
              </Button>

              <Dialog open={donationOpen} onOpenChange={setDonationOpen}>
                <DialogTrigger asChild>
                  <Button 
                    className="bg-gradient-to-r from-purple-500 to-pink-500 text-white hover:from-purple-600 hover:to-pink-600"
                    data-testid="donate-btn"
                  >
                    <CurrencyDollar className="w-4 h-4 mr-2" /> Donate
                  </Button>
                </DialogTrigger>
                <DialogContent className="bg-[#0F0F16] border-white/10">
                  <DialogHeader>
                    <DialogTitle className="text-white">Support {stream.display_name || stream.username}</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4 pt-4">
                    <div className="grid grid-cols-5 gap-2">
                      {donationPackages.map((pkg) => (
                        <button
                          key={pkg.id}
                          onClick={() => setSelectedPackage(pkg.id)}
                          className={`p-3 rounded-lg border text-center font-bold transition-colors
                            ${selectedPackage === pkg.id 
                              ? 'border-[#00E5FF] bg-[#00E5FF]/10 text-[#00E5FF]' 
                              : 'border-white/10 text-white hover:border-white/30'}`}
                          data-testid={`donate-${pkg.id}`}
                        >
                          {pkg.label}
                        </button>
                      ))}
                    </div>
                    <textarea
                      placeholder="Add a message (optional)"
                      value={donationMessage}
                      onChange={(e) => setDonationMessage(e.target.value)}
                      maxLength={200}
                      className="w-full h-24 p-3 bg-[#1A1A24] border border-white/10 rounded-lg text-white placeholder-[#A0A0AB] focus:outline-none focus:border-[#00E5FF] resize-none"
                      data-testid="donate-message"
                    />
                    <Button 
                      onClick={handleDonate}
                      disabled={!selectedPackage}
                      className="w-full bg-gradient-to-r from-purple-500 to-pink-500 text-white hover:from-purple-600 hover:to-pink-600 disabled:opacity-50"
                      data-testid="donate-submit-btn"
                    >
                      Donate {selectedPackage && donationPackages.find(p => p.id === selectedPackage)?.label}
                    </Button>
                  </div>
                </DialogContent>
              </Dialog>

              <Button
                variant="ghost"
                size="icon"
                onClick={handleShare}
                className="text-[#A0A0AB] hover:text-white hover:bg-white/10"
                data-testid="share-btn"
              >
                <Share className="w-5 h-5" />
              </Button>
            </div>
          </div>

          {/* Description */}
          {stream.description && (
            <div className="mt-4 p-4 bg-[#0F0F16] rounded-lg">
              <p className="text-[#A0A0AB] text-sm whitespace-pre-wrap">{stream.description}</p>
            </div>
          )}
        </div>
      </div>

      {/* Chat */}
      <div className="lg:col-span-3 h-[500px] lg:h-[calc(100vh-64px)] lg:sticky lg:top-16">
        <ChatBox streamId={streamId} />
      </div>
    </div>
  );
}
