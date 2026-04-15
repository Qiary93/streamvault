import React, { useState, useEffect } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import StreamCard from '../components/StreamCard';
import CategoryCard from '../components/CategoryCard';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

export default function BrowsePage() {
  const [streams, setStreams] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('streams');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [streamsRes, categoriesRes] = await Promise.all([
          axios.get(`${API}/api/streams`),
          axios.get(`${API}/api/categories`)
        ]);
        setStreams(streamsRes.data);
        setCategories(categoriesRes.data);
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
    <div className="p-4 lg:p-6" data-testid="browse-page">
      <h1 className="text-2xl lg:text-3xl font-bold text-white mb-6 font-['Outfit']">Browse</h1>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="bg-[#0F0F16] border border-white/10">
          <TabsTrigger 
            value="streams" 
            className="data-[state=active]:bg-[#00E5FF] data-[state=active]:text-black"
            data-testid="tab-streams"
          >
            Live Streams
          </TabsTrigger>
          <TabsTrigger 
            value="categories" 
            className="data-[state=active]:bg-[#00E5FF] data-[state=active]:text-black"
            data-testid="tab-categories"
          >
            Categories
          </TabsTrigger>
        </TabsList>

        <TabsContent value="streams" className="mt-6">
          {streams.length > 0 ? (
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
