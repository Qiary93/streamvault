import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Eye, Users, Heart, HeartBreak, CurrencyDollar, Share, Star, SpeakerHigh, SpeakerLow, SpeakerX, CornersOut, Gear } from '@phosphor-icons/react';
import { Avatar, AvatarFallback, AvatarImage } from '../components/ui/avatar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import ChatBox from '../components/ChatBox';
import { LiveKitViewer } from '../components/LiveKitPlayer';
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
  const [subscribeOpen, setSubscribeOpen] = useState(false);
  const [selectedPackage, setSelectedPackage] = useState(null);
  const [selectedTier, setSelectedTier] = useState(null);
  const [donationMessage, setDonationMessage] = useState('');
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [volume, setVolume] = useState(80);
  const [isMuted, setIsMuted] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [selectedQuality, setSelectedQuality] = useState('Auto');
  const [showQualityMenu, setShowQualityMenu] = useState(false);
  const [customDonationAmount, setCustomDonationAmount] = useState('');
  const [streamerTiers, setStreamerTiers] = useState([]);

  useEffect(() => {
    const fetchStream = async () => {
      try {
        const response = await axios.get(`${API}/api/streams/${streamId}`, {
          withCredentials: true
        });
        setStream(response.data);
        setFollowing(response.data.is_following);
        
        // Fetch streamer's custom tiers
        try {
          const tiersRes = await axios.get(`${API}/api/users/${response.data.user_id}/subscription-tiers`);
          setStreamerTiers(tiersRes.data);
        } catch (e) {
          setStreamerTiers([]);
        }
        
        // Check subscription status
        if (response.data.user_id) {
          try {
            const subRes = await axios.get(`${API}/api/subscriptions/check/${response.data.user_id}`, {
              withCredentials: true
            });
            setIsSubscribed(subRes.data.subscribed);
          } catch (e) {
            // Not logged in or error
          }
        }
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

    if (selectedPackage === 'custom' && (!customDonationAmount || parseFloat(customDonationAmount) < 1)) {
      toast.error('Please enter an amount of at least $1');
      return;
    }

    try {
      const response = await axios.post(`${API}/api/donations/checkout`, {
        streamer_id: stream.user_id,
        package_id: selectedPackage,
        custom_amount: selectedPackage === 'custom' ? parseFloat(customDonationAmount) : undefined,
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

  const handleSubscribe = async () => {
    if (!user) {
      toast.error('Please log in to subscribe');
      return;
    }
    if (!selectedTier) {
      toast.error('Please select a tier');
      return;
    }
    try {
      const response = await axios.post(`${API}/api/subscriptions/checkout`, {
        streamer_id: stream.user_id,
        tier_id: selectedTier,
        origin_url: window.location.origin
      }, { withCredentials: true });
      window.location.href = response.data.url;
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to process subscription');
    }
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
        {/* Video Player - LiveKit */}
        <div className="relative aspect-video bg-black group" data-testid="video-player" id="stream-player-container">
          {stream.is_live ? (
            <LiveKitViewer 
              roomName={stream.room_name || `stream_${stream.stream_id}`} 
              streamThumbnail={stream.thumbnail_url} 
            />
          ) : stream.thumbnail_url ? (
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

          {/* Player Controls Overlay */}
          <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 p-4">
            <div className="flex items-center justify-between">
              {/* Left: Viewers */}
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1.5 text-sm text-white">
                  <Eye className="w-4 h-4" />
                  {stream.viewer_count?.toLocaleString() || 0}
                </span>
              </div>

              {/* Right: Volume, Quality, Fullscreen */}
              <div className="flex items-center gap-2">
                {/* Volume */}
                <div className="flex items-center gap-1.5 group/vol">
                  <button
                    onClick={() => setIsMuted(!isMuted)}
                    className="p-1.5 rounded hover:bg-white/20 text-white transition-colors"
                    data-testid="volume-toggle-btn"
                  >
                    {isMuted || volume === 0 ? <SpeakerX className="w-5 h-5" /> : volume < 50 ? <SpeakerLow className="w-5 h-5" /> : <SpeakerHigh className="w-5 h-5" />}
                  </button>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={isMuted ? 0 : volume}
                    onChange={(e) => { setVolume(parseInt(e.target.value)); setIsMuted(false); }}
                    className="w-20 h-1 accent-[#00E5FF] cursor-pointer"
                    data-testid="volume-slider"
                  />
                </div>

                {/* Quality */}
                <div className="relative">
                  <button
                    onClick={() => setShowQualityMenu(!showQualityMenu)}
                    className="p-1.5 rounded hover:bg-white/20 text-white transition-colors flex items-center gap-1"
                    data-testid="quality-menu-btn"
                  >
                    <Gear className="w-5 h-5" />
                    <span className="text-xs">{selectedQuality}</span>
                  </button>
                  {showQualityMenu && (
                    <div className="absolute bottom-full right-0 mb-2 bg-[#0F0F16] border border-white/10 rounded-lg overflow-hidden shadow-xl z-10">
                      {['Auto', ...(stream.quality ? [stream.quality] : []), '1080p', '720p', '480p', '360p'].filter((v, i, a) => a.indexOf(v) === i).map((q) => (
                        <button
                          key={q}
                          onClick={() => { setSelectedQuality(q); setShowQualityMenu(false); }}
                          className={`block w-full px-4 py-2 text-left text-sm hover:bg-white/10 transition-colors ${selectedQuality === q ? 'text-[#00E5FF]' : 'text-white'}`}
                          data-testid={`quality-${q}`}
                        >
                          {q} {selectedQuality === q && '✓'}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* Fullscreen */}
                <button
                  onClick={() => {
                    const el = document.getElementById('stream-player-container');
                    if (document.fullscreenElement) {
                      document.exitFullscreen();
                      setIsFullscreen(false);
                    } else if (el) {
                      el.requestFullscreen();
                      setIsFullscreen(true);
                    }
                  }}
                  className="p-1.5 rounded hover:bg-white/20 text-white transition-colors"
                  data-testid="fullscreen-btn"
                >
                  <CornersOut className="w-5 h-5" />
                </button>
              </div>
            </div>
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
                <div className="flex items-center flex-wrap gap-4 mt-2 text-sm text-[#A0A0AB]">
                  {stream.category_name && (
                    <Link 
                      to={`/category/${stream.category_id}`}
                      className="hover:text-[#00E5FF] transition-colors"
                    >
                      {stream.category_name}
                    </Link>
                  )}
                  {stream.game_name && (
                    <Link 
                      to={`/game/${encodeURIComponent(stream.game_name)}`}
                      className="flex items-center gap-1 px-2 py-0.5 bg-[#00E5FF]/10 text-[#00E5FF] rounded-full hover:bg-[#00E5FF]/20 transition-colors text-xs font-medium"
                      data-testid="game-link"
                    >
                      <svg className="w-3 h-3" viewBox="0 0 24 24" fill="currentColor"><path d="M17 4H7a5 5 0 0 0-5 5v6a5 5 0 0 0 5 5h10a5 5 0 0 0 5-5V9a5 5 0 0 0-5-5ZM8 14H7v1a1 1 0 0 1-2 0v-1H4a1 1 0 0 1 0-2h1v-1a1 1 0 0 1 2 0v1h1a1 1 0 0 1 0 2Zm7-1a1 1 0 1 1 0-2 1 1 0 0 1 0 2Zm3 3a1 1 0 1 1 0-2 1 1 0 0 1 0 2Z"/></svg>
                      {stream.game_name}
                    </Link>
                  )}
                  <span className="flex items-center gap-1">
                    <Users className="w-4 h-4" />
                    {stream.follower_count?.toLocaleString() || 0} followers
                  </span>
                  <span className="flex items-center gap-1 text-red-400">
                    <Eye className="w-4 h-4" />
                    {stream.viewer_count?.toLocaleString() || 0} watching
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
                    <div className="grid grid-cols-3 gap-2">
                      {donationPackages.map((pkg) => (
                        <button
                          key={pkg.id}
                          onClick={() => { setSelectedPackage(pkg.id); setCustomDonationAmount(''); }}
                          className={`p-3 rounded-lg border text-center font-bold transition-colors
                            ${selectedPackage === pkg.id 
                              ? 'border-[#00E5FF] bg-[#00E5FF]/10 text-[#00E5FF]' 
                              : 'border-white/10 text-white hover:border-white/30'}`}
                          data-testid={`donate-${pkg.id}`}
                        >
                          {pkg.label}
                        </button>
                      ))}
                      <button
                        onClick={() => setSelectedPackage('custom')}
                        className={`p-3 rounded-lg border text-center font-bold transition-colors
                          ${selectedPackage === 'custom' 
                            ? 'border-[#00E5FF] bg-[#00E5FF]/10 text-[#00E5FF]' 
                            : 'border-white/10 text-white hover:border-white/30'}`}
                        data-testid="donate-custom"
                      >
                        Custom
                      </button>
                    </div>
                    {selectedPackage === 'custom' && (
                      <div className="relative">
                        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[#A0A0AB] font-bold">$</span>
                        <input
                          type="number"
                          min="1"
                          max="10000"
                          step="0.01"
                          value={customDonationAmount}
                          onChange={(e) => setCustomDonationAmount(e.target.value)}
                          placeholder="Enter amount"
                          className="w-full h-10 pl-8 pr-4 bg-[#1A1A24] border border-white/10 rounded-lg text-white placeholder-[#A0A0AB] focus:outline-none focus:border-[#00E5FF]"
                          data-testid="custom-amount-input"
                        />
                      </div>
                    )}
                    <textarea
                      placeholder="Add a message (optional)"
                      value={donationMessage}
                      onChange={(e) => setDonationMessage(e.target.value)}
                      maxLength={200}
                      className="w-full h-20 p-3 bg-[#1A1A24] border border-white/10 rounded-lg text-white placeholder-[#A0A0AB] focus:outline-none focus:border-[#00E5FF] resize-none"
                      data-testid="donate-message"
                    />
                    <Button 
                      onClick={handleDonate}
                      disabled={!selectedPackage || (selectedPackage === 'custom' && !customDonationAmount)}
                      className="w-full bg-gradient-to-r from-purple-500 to-pink-500 text-white hover:from-purple-600 hover:to-pink-600 disabled:opacity-50"
                      data-testid="donate-submit-btn"
                    >
                      Donate {selectedPackage === 'custom' && customDonationAmount ? `$${customDonationAmount}` : (selectedPackage && donationPackages.find(p => p.id === selectedPackage)?.label)}
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

              {/* Subscribe Dialog */}
              <Dialog open={subscribeOpen} onOpenChange={setSubscribeOpen}>
                <DialogTrigger asChild>
                  <Button 
                    className={isSubscribed 
                      ? "bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 hover:bg-yellow-500/30" 
                      : "bg-[#292938] text-white hover:bg-[#3D3D52]"}
                    data-testid="subscribe-btn"
                  >
                    <Star weight={isSubscribed ? "fill" : "regular"} className="w-4 h-4 mr-2" />
                    {isSubscribed ? 'Subscribed' : 'Subscribe'}
                  </Button>
                </DialogTrigger>
                <DialogContent className="bg-[#0F0F16] border-white/10 max-w-md">
                  <DialogHeader>
                    <DialogTitle className="text-white">Subscribe to {stream.display_name || stream.username}</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-3 pt-4">
                    {streamerTiers.map((tier) => (
                      <button
                        key={tier.tier_id || tier.id}
                        onClick={() => setSelectedTier(tier.tier_id || tier.id)}
                        className={`w-full p-4 rounded-lg border text-left transition-colors
                          ${selectedTier === (tier.tier_id || tier.id)
                            ? 'border-[#00E5FF] bg-[#00E5FF]/10' 
                            : 'border-white/10 hover:border-white/30'}`}
                        data-testid={`sub-${tier.tier_id || tier.id}`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-bold text-white">{tier.name}</span>
                          <span className="text-[#00E5FF] font-bold">${tier.amount}/mo</span>
                        </div>
                        <p className="text-xs text-[#A0A0AB]">{tier.perks}</p>
                      </button>
                    ))}
                    {streamerTiers.length === 0 && (
                      <p className="text-center text-[#A0A0AB] py-4">No subscription tiers available</p>
                    )}
                    <Button 
                      onClick={handleSubscribe}
                      disabled={!selectedTier}
                      className="w-full bg-[#00E5FF] text-black font-bold hover:bg-[#00B3CC] disabled:opacity-50"
                      data-testid="subscribe-submit-btn"
                    >
                      Subscribe {selectedTier && `- $${streamerTiers.find(t => (t.tier_id || t.id) === selectedTier)?.amount}/mo`}
                    </Button>
                  </div>
                </DialogContent>
              </Dialog>
            </div>
          </div>

          {/* Tags */}
          {stream.tags && stream.tags.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {stream.tags.map((tag, i) => (
                <Link 
                  key={i} 
                  to={`/tag/${encodeURIComponent(tag)}`}
                  className="px-2.5 py-1 bg-[#00E5FF]/10 text-[#00E5FF] text-xs font-medium rounded-full hover:bg-[#00E5FF]/20 transition-colors"
                  data-testid={`tag-link-${tag}`}
                >
                  #{tag}
                </Link>
              ))}
            </div>
          )}

          {/* Description (rendered as HTML) */}
          {stream.description && (
            <div className="mt-4 p-4 bg-[#0F0F16] rounded-lg">
              <div 
                className="text-[#A0A0AB] text-sm prose prose-invert prose-sm max-w-none [&_a]:text-[#00E5FF] [&_a]:underline [&_img]:max-w-full [&_img]:rounded [&_b]:text-white [&_strong]:text-white [&_i]:italic"
                dangerouslySetInnerHTML={{ __html: stream.description }}
              />
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
