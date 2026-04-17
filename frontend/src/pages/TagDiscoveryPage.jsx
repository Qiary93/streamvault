import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Tag, ArrowLeft } from '@phosphor-icons/react';
import StreamCard from '../components/StreamCard';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

export default function TagDiscoveryPage() {
  const { tag } = useParams();
  const [streams, setStreams] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStreams = async () => {
      try {
        const response = await axios.get(`${API}/api/streams/by-tag/${encodeURIComponent(tag)}`);
        setStreams(response.data);
      } catch (error) {
        console.error('Error fetching tag streams:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchStreams();
  }, [tag]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="w-8 h-8 border-2 border-[#00E5FF] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-4 lg:p-6" data-testid="tag-discovery-page">
      <Link to="/browse" className="inline-flex items-center gap-2 text-[#A0A0AB] hover:text-white mb-4 transition-colors">
        <ArrowLeft className="w-4 h-4" /> Back to Browse
      </Link>

      <div className="flex items-center gap-3 mb-6">
        <Tag weight="fill" className="w-6 h-6 text-[#00E5FF]" />
        <h1 className="text-2xl lg:text-3xl font-bold text-white font-['Outfit']">#{tag}</h1>
        <span className="text-[#A0A0AB]">{streams.length} live stream{streams.length !== 1 ? 's' : ''}</span>
      </div>

      {streams.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {streams.map((stream) => (
            <StreamCard key={stream.stream_id} stream={stream} />
          ))}
        </div>
      ) : (
        <div className="text-center py-16 bg-[#0F0F16] rounded-xl">
          <Tag weight="fill" className="w-12 h-12 text-[#292938] mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-white mb-2">No live streams with #{tag}</h2>
          <p className="text-[#A0A0AB]">Check back later or browse other tags</p>
        </div>
      )}
    </div>
  );
}
