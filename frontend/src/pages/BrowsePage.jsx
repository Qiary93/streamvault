import React, { useState, useEffect } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import StreamCard from '../components/StreamCard';
import CategoryCard from '../components/CategoryCard';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

const SORT_OPTIONS = [
  { value: 'viewers', label: 'Most viewers' },
  { value: 'newest', label: 'Newest' },
  { value: 'oldest', label: 'Oldest' },
];

export default function BrowsePage() {
  const [streams, setStreams] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('streams');
  const [sort, setSort] = useState('viewers');

  useEffect(() => {
    axios.get(`${API}/api/categories`)
      .then(res => setCategories(res.data))
      .catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    axios.get(`${API}/api/streams?sort=${sort}&limit=40`)
      .then(res => setStreams(res.data))
      .catch(err => console.error('Error fetching streams:', err))
      .finally(() => setLoading(false));
  }, [sort]);

  return (
    <div className="p-4 lg:p-6" data-testid="browse-page">
      <h1 className="text-2xl lg:text-3xl font-bold text-white mb-6 font-['Outfit']">Browse</h1>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="bg-[#0F0F16] border border-white/10">
          <TabsTrigger value="streams" className="data-[state=active]:bg-[#00E5FF] data-[state=active]:text-black" data-testid="tab-streams">
            Live Streams
          </TabsTrigger>
          <TabsTrigger value="categories" className="data-[state=active]:bg-[#00E5FF] data-[state=active]:text-black" data-testid="tab-categories">
            Categories
          </TabsTrigger>
        </TabsList>

        <TabsContent value="streams" className="mt-6">
          {/* Sort bar */}
          <div className="flex items-center gap-2 mb-4" data-testid="stream-sort-bar">
            <span className="text-xs text-[#A0A0AB]">Sort by:</span>
            {SORT_OPTIONS.map(opt => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setSort(opt.value)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition ${
                  sort === opt.value
                    ? 'bg-[#00E5FF] text-black'
                    : 'bg-[#1A1A24] text-[#A0A0AB] hover:text-white hover:bg-[#242433]'
                }`}
                data-testid={`sort-${opt.value}`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-20">
              <div className="w-8 h-8 border-2 border-[#00E5FF] border-t-transparent rounded-full animate-spin" />
            </div>
          ) : streams.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {streams.map((stream) => (
                <StreamCard key={stream.stream_id} stream={stream} />
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <p className="text-[#A0A0AB]">No live streams at the moment</p>
            </div>
          )}
        </TabsContent>

        <TabsContent value="categories" className="mt-6">
          {categories.length > 0 ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-4">
              {categories.map((category) => (
                <CategoryCard key={category.category_id} category={category} />
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <p className="text-[#A0A0AB]">No categories available</p>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
