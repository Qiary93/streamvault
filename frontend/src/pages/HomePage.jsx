import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, TrendUp } from '@phosphor-icons/react';
import StreamCard from '../components/StreamCard';
import CategoryCard from '../components/CategoryCard';
import { Avatar, AvatarFallback, AvatarImage } from '../components/ui/avatar';
import { Button } from '../components/ui/button';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

export default function HomePage() {
  const [featured, setFeatured] = useState({ top_streams: [], categories: [], recommended_streamers: [] });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchFeatured = async () => {
      try {
        const response = await axios.get(`${API}/api/featured`);
        setFeatured(response.data);
      } catch (error) {
        console.error('Error fetching featured:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchFeatured();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="w-8 h-8 border-2 border-[#00E5FF] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-4 lg:p-6 space-y-8" data-testid="home-page">
      {/* Hero Section */}
      <section className="relative h-64 lg:h-80 rounded-2xl overflow-hidden" data-testid="hero-section">
        <div 
          className="absolute inset-0 bg-cover bg-center"
          style={{ backgroundImage: 'url(https://images.pexels.com/photos/9072205/pexels-photo-9072205.jpeg)' }}
        />
        <div className="absolute inset-0 bg-gradient-to-r from-[#05050A] via-[#05050A]/70 to-transparent" />
        <div className="relative h-full flex flex-col justify-center px-6 lg:px-10 max-w-xl">
          <span className="text-xs font-bold uppercase tracking-[0.2em] text-[#00E5FF] mb-2">Welcome to</span>
          <h1 className="text-4xl lg:text-5xl font-black tracking-tighter text-white mb-3 font-['Outfit']">
            StreamVault
          </h1>
          <p className="text-[#A0A0AB] text-sm lg:text-base mb-6">
            Watch live streams, connect with creators, and join a community of millions.
          </p>
          <Link to="/browse">
            <Button className="bg-[#00E5FF] text-black font-bold hover:bg-[#00B3CC] gap-2" data-testid="browse-btn">
              Start Watching <ArrowRight className="w-4 h-4" />
            </Button>
          </Link>
        </div>
      </section>

      {/* Live Now */}
      {featured.top_streams.length > 0 && (
        <section data-testid="live-streams-section">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-red-500 rounded-full live-indicator" />
              <h2 className="text-xl lg:text-2xl font-bold text-white font-['Outfit']">Live Now</h2>
            </div>
            <Link to="/browse" className="text-[#00E5FF] text-sm hover:underline flex items-center gap-1">
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {featured.top_streams.map((stream) => (
              <StreamCard key={stream.stream_id} stream={stream} />
            ))}
          </div>
        </section>
      )}

      {/* Categories */}
      {featured.categories.length > 0 && (
        <section data-testid="categories-section">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl lg:text-2xl font-bold text-white font-['Outfit']">Browse Categories</h2>
            <Link to="/browse" className="text-[#00E5FF] text-sm hover:underline flex items-center gap-1">
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-4">
            {featured.categories.map((category) => (
              <CategoryCard key={category.category_id} category={category} />
            ))}
          </div>
        </section>
      )}

      {/* Recommended Streamers */}
      {featured.recommended_streamers.length > 0 && (
        <section data-testid="recommended-section">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <TrendUp className="w-5 h-5 text-[#00E5FF]" />
              <h2 className="text-xl lg:text-2xl font-bold text-white font-['Outfit']">Recommended Streamers</h2>
            </div>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
            {featured.recommended_streamers.map((streamer) => (
              <Link
                key={streamer.user_id}
                to={`/user/${streamer.username}`}
                className="group flex flex-col items-center p-4 bg-[#0F0F16] border border-white/5 rounded-xl hover:border-[#00E5FF]/30 transition-colors"
                data-testid={`streamer-card-${streamer.user_id}`}
              >
                <Avatar className={`w-16 h-16 mb-3 ${streamer.is_streaming ? 'avatar-live' : ''}`}>
                  <AvatarImage src={streamer.avatar_url} alt={streamer.display_name || streamer.username} />
                  <AvatarFallback className="bg-[#292938] text-[#00E5FF] text-xl">
                    {(streamer.display_name || streamer.username)?.charAt(0).toUpperCase()}
                  </AvatarFallback>
                </Avatar>
                <h3 className="font-semibold text-white text-center group-hover:text-[#00E5FF] transition-colors">
                  {streamer.display_name || streamer.username}
                </h3>
                <p className="text-xs text-[#A0A0AB]">@{streamer.username}</p>
                {streamer.is_streaming && (
                  <span className="mt-2 px-2 py-0.5 bg-red-500/20 text-red-400 text-xs font-medium rounded">
                    LIVE
                  </span>
                )}
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
