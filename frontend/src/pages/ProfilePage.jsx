import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Users, Heart, HeartBreak, Broadcast, CalendarBlank, Camera } from '@phosphor-icons/react';
import { Avatar, AvatarFallback, AvatarImage } from '../components/ui/avatar';
import { Button } from '../components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import StreamCard from '../components/StreamCard';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

export default function ProfilePage() {
  const { username } = useParams();
  const { user: currentUser } = useAuth();
  const [profile, setProfile] = useState(null);
  const [streams, setStreams] = useState([]);
  const [following, setFollowing] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const response = await axios.get(`${API}/api/users/${username}`, {
          withCredentials: true
        });
        setProfile(response.data);
        setFollowing(response.data.is_following);

        // Fetch user's streams
        const streamsRes = await axios.get(`${API}/api/streams`);
        const userStreams = streamsRes.data.filter(s => s.username === username);
        setStreams(userStreams);
      } catch (error) {
        console.error('Error fetching profile:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchProfile();
  }, [username]);

  const handleFollow = async () => {
    if (!currentUser) {
      toast.error('Please log in to follow');
      return;
    }

    try {
      if (following) {
        await axios.delete(`${API}/api/users/${profile.user_id}/follow`, {
          withCredentials: true
        });
        setFollowing(false);
        setProfile(prev => ({ ...prev, follower_count: prev.follower_count - 1 }));
        toast.success('Unfollowed');
      } else {
        await axios.post(`${API}/api/users/${profile.user_id}/follow`, {}, {
          withCredentials: true
        });
        setFollowing(true);
        setProfile(prev => ({ ...prev, follower_count: prev.follower_count + 1 }));
        toast.success('Followed!');
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update follow');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="w-8 h-8 border-2 border-[#00E5FF] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh]">
        <h2 className="text-xl font-bold text-white mb-2">User not found</h2>
        <Link to="/" className="text-[#00E5FF] hover:underline">Go back home</Link>
      </div>
    );
  }

  const isOwnProfile = currentUser?.user_id === profile.user_id;

  const handleAvatarUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { toast.error('Max 10MB'); return; }
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await axios.post(`${API}/api/upload/avatar`, formData, {
        withCredentials: true, headers: { 'Content-Type': 'multipart/form-data' }
      });
      setProfile(prev => ({ ...prev, avatar_url: `${API}${res.data.url}` }));
      toast.success('Avatar updated!');
    } catch (err) {
      toast.error('Failed to upload avatar');
    }
  };

  const handleCoverUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { toast.error('Max 10MB'); return; }
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await axios.post(`${API}/api/upload/cover`, formData, {
        withCredentials: true, headers: { 'Content-Type': 'multipart/form-data' }
      });
      setProfile(prev => ({ ...prev, cover_url: `${API}${res.data.url}` }));
      toast.success('Cover photo updated!');
    } catch (err) {
      toast.error('Failed to upload cover photo');
    }
  };

  return (
    <div data-testid="profile-page">
      {/* Header Banner / Cover Photo */}
      <div className="h-32 lg:h-48 relative overflow-hidden">
        {profile.cover_url ? (
          <img src={profile.cover_url} alt="Cover" className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full bg-gradient-to-r from-[#0F0F16] via-[#00E5FF]/20 to-[#0F0F16]" />
        )}
        {isOwnProfile && (
          <label className="absolute bottom-3 right-3 flex items-center gap-2 px-3 py-1.5 bg-black/60 hover:bg-black/80 text-white text-xs font-medium rounded-lg cursor-pointer transition-colors" data-testid="upload-cover-btn">
            <Camera className="w-4 h-4" /> Change Cover
            <input type="file" accept="image/jpeg,image/png,image/webp" onChange={handleCoverUpload} className="hidden" />
          </label>
        )}
      </div>

      {/* Profile Info */}
      <div className="px-4 lg:px-6 -mt-12 lg:-mt-16 mb-6">
        <div className="flex flex-col lg:flex-row lg:items-end gap-4">
          {/* Avatar with upload */}
          <div className="relative group">
            <Avatar className={`w-24 h-24 lg:w-32 lg:h-32 border-4 border-[#05050A] ${profile.is_streaming ? 'avatar-live' : ''}`}>
              <AvatarImage src={profile.avatar_url} alt={profile.display_name || profile.username} />
              <AvatarFallback className="bg-[#292938] text-[#00E5FF] text-3xl">
                {(profile.display_name || profile.username)?.charAt(0).toUpperCase()}
              </AvatarFallback>
            </Avatar>
            {isOwnProfile && (
              <label className="absolute inset-0 flex items-center justify-center bg-black/50 rounded-full opacity-0 group-hover:opacity-100 cursor-pointer transition-opacity" data-testid="upload-avatar-btn">
                <Camera className="w-6 h-6 text-white" />
                <input type="file" accept="image/jpeg,image/png,image/webp" onChange={handleAvatarUpload} className="hidden" />
              </label>
            )}
          </div>

          <div className="flex-1">
            <div className="flex items-start justify-between">
              <div>
                <h1 className="text-2xl lg:text-3xl font-bold text-white font-['Outfit']" data-testid="profile-name">
                  {profile.display_name || profile.username}
                </h1>
                <p className="text-[#A0A0AB]">@{profile.username}</p>
              </div>

              {!isOwnProfile && (
                <Button
                  onClick={handleFollow}
                  variant={following ? 'secondary' : 'default'}
                  className={following 
                    ? 'bg-[#292938] text-white hover:bg-[#3D3D52]' 
                    : 'bg-[#00E5FF] text-black hover:bg-[#00B3CC]'}
                  data-testid="profile-follow-btn"
                >
                  {following ? (
                    <><HeartBreak className="w-4 h-4 mr-2" /> Unfollow</>
                  ) : (
                    <><Heart className="w-4 h-4 mr-2" /> Follow</>
                  )}
                </Button>
              )}
            </div>

            <div className="flex items-center gap-6 mt-4 text-sm">
              <div className="flex items-center gap-2 text-[#A0A0AB]">
                <Users className="w-4 h-4" />
                <span><strong className="text-white">{profile.follower_count?.toLocaleString() || 0}</strong> followers</span>
              </div>
              <div className="flex items-center gap-2 text-[#A0A0AB]">
                <span><strong className="text-white">{profile.following_count?.toLocaleString() || 0}</strong> following</span>
              </div>
              {profile.is_streaming && (
                <div className="flex items-center gap-2 text-red-400">
                  <Broadcast className="w-4 h-4" />
                  <span className="font-medium">LIVE NOW</span>
                </div>
              )}
            </div>

            {profile.bio && (
              <p className="mt-4 text-[#A0A0AB] max-w-2xl">{profile.bio}</p>
            )}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="px-4 lg:px-6 pb-6">
        <Tabs defaultValue="streams">
          <TabsList className="bg-[#0F0F16] border border-white/10">
            <TabsTrigger 
              value="streams" 
              className="data-[state=active]:bg-[#00E5FF] data-[state=active]:text-black"
            >
              Streams
            </TabsTrigger>
            <TabsTrigger 
              value="about" 
              className="data-[state=active]:bg-[#00E5FF] data-[state=active]:text-black"
            >
              About
            </TabsTrigger>
          </TabsList>

          <TabsContent value="streams" className="mt-6">
            {streams.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {streams.map((stream) => (
                  <StreamCard key={stream.stream_id} stream={stream} />
                ))}
              </div>
            ) : (
              <div className="text-center py-12 bg-[#0F0F16] rounded-xl">
                <Broadcast className="w-12 h-12 text-[#292938] mx-auto mb-3" />
                <p className="text-[#A0A0AB]">
                  {profile.is_streaming 
                    ? 'Currently streaming!' 
                    : 'No streams available'}
                </p>
              </div>
            )}
          </TabsContent>

          <TabsContent value="about" className="mt-6">
            <div className="bg-[#0F0F16] rounded-xl p-6 max-w-2xl">
              <h3 className="text-lg font-semibold text-white mb-4">About {profile.display_name || profile.username}</h3>
              
              {profile.bio ? (
                <p className="text-[#A0A0AB] mb-6">{profile.bio}</p>
              ) : (
                <p className="text-[#A0A0AB] mb-6 italic">No bio yet</p>
              )}

              <div className="flex items-center gap-2 text-sm text-[#A0A0AB]">
                <CalendarBlank className="w-4 h-4" />
                <span>Joined {new Date(profile.created_at).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}</span>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
