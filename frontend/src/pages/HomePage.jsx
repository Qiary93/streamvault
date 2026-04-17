import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Broadcast } from '@phosphor-icons/react';
import StreamCard from '../components/StreamCard';
import CategoryCard from '../components/CategoryCard';
import { Button } from '../components/ui/button';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

export default function HomePage() {
  const [allCategories, setAllCategories] = useState([]);
  const [liveStreams, setLiveStreams] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [categoriesRes, streamsRes] = await Promise.all([
          axios.get(`${API}/api/categories`),
          axios.get(`${API}/api/streams?limit=20`)
        ]);
        setAllCategories(categoriesRes.data);
        setLiveStreams(streamsRes.data);
      } catch (error) {
        console.error('Error fetching data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
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

      {/* Browse Categories */}
      {allCategories.length > 0 && (
        <section data-testid="categories-section">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl lg:text-2xl font-bold text-white font-['Outfit']">Browse Categories</h2>
            <Link to="/browse" className="text-[#00E5FF] text-sm hover:underline flex items-center gap-1">
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-4">
            {allCategories.map((category) => (
              <CategoryCard key={category.category_id} category={category} />
            ))}
          </div>
        </section>
      )}

      {/* Live Streams */}
      <section data-testid="live-streams-section">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-red-500 rounded-full live-indicator" />
            <h2 className="text-xl lg:text-2xl font-bold text-white font-['Outfit']">Live Streams</h2>
            <span className="text-sm text-[#A0A0AB]">({liveStreams.length})</span>
          </div>
          <Link to="/browse" className="text-[#00E5FF] text-sm hover:underline flex items-center gap-1">
            View all <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
        {liveStreams.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {liveStreams.map((stream) => (
              <StreamCard key={stream.stream_id} stream={stream} />
            ))}
          </div>
        ) : (
          <div className="text-center py-16 bg-[#0F0F16] rounded-xl">
            <Broadcast weight="fill" className="w-12 h-12 text-[#292938] mx-auto mb-4" />
            <h2 className="text-lg font-semibold text-white mb-2">No live streams right now</h2>
            <p className="text-[#A0A0AB]">Be the first to go live! Head to your <Link to="/dashboard" className="text-[#00E5FF] hover:underline">Dashboard</Link> to start streaming.</p>
          </div>
        )}
      </section>
    </div>
  );
}
