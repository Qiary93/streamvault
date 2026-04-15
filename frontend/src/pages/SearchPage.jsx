import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { MagnifyingGlass } from '@phosphor-icons/react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import StreamCard from '../components/StreamCard';
import { Avatar, AvatarFallback, AvatarImage } from '../components/ui/avatar';
import { Link } from 'react-router-dom';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

export default function SearchPage() {
  const [searchParams] = useSearchParams();
  const query = searchParams.get('q') || '';
  const [results, setResults] = useState({ streams: [], users: [], categories: [] });
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('all');

  useEffect(() => {
    const search = async () => {
      if (!query) {
        setLoading(false);
        return;
      }

      setLoading(true);
      try {
        const response = await axios.get(`${API}/api/search`, {
          params: { q: query, type: 'all' }
        });
        setResults(response.data);
      } catch (error) {
        console.error('Search error:', error);
      } finally {
        setLoading(false);
      }
    };

    search();
  }, [query]);

  const totalResults = results.streams.length + results.users.length + results.categories.length;

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="w-8 h-8 border-2 border-[#00E5FF] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-4 lg:p-6" data-testid="search-page">
      <div className="flex items-center gap-3 mb-6">
        <MagnifyingGlass className="w-6 h-6 text-[#00E5FF]" />
        <h1 className="text-2xl lg:text-3xl font-bold text-white font-['Outfit']">
          Search results for "{query}"
        </h1>
      </div>

      {totalResults === 0 ? (
        <div className="text-center py-12 bg-[#0F0F16] rounded-xl">
          <MagnifyingGlass className="w-12 h-12 text-[#292938] mx-auto mb-3" />
          <p className="text-[#A0A0AB]">No results found for "{query}"</p>
        </div>
      ) : (
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="bg-[#0F0F16] border border-white/10">
            <TabsTrigger 
              value="all" 
              className="data-[state=active]:bg-[#00E5FF] data-[state=active]:text-black"
            >
              All ({totalResults})
            </TabsTrigger>
            <TabsTrigger 
              value="streams" 
              className="data-[state=active]:bg-[#00E5FF] data-[state=active]:text-black"
            >
              Streams ({results.streams.length})
            </TabsTrigger>
            <TabsTrigger 
              value="users" 
              className="data-[state=active]:bg-[#00E5FF] data-[state=active]:text-black"
            >
              Users ({results.users.length})
            </TabsTrigger>
            <TabsTrigger 
              value="categories" 
              className="data-[state=active]:bg-[#00E5FF] data-[state=active]:text-black"
            >
              Categories ({results.categories.length})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="all" className="mt-6 space-y-8">
            {results.streams.length > 0 && (
              <section>
                <h2 className="text-lg font-semibold text-white mb-4">Streams</h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                  {results.streams.slice(0, 4).map((stream) => (
                    <StreamCard key={stream.stream_id} stream={stream} />
                  ))}
                </div>
              </section>
            )}

            {results.users.length > 0 && (
              <section>
                <h2 className="text-lg font-semibold text-white mb-4">Users</h2>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
                  {results.users.slice(0, 5).map((user) => (
                    <Link
                      key={user.user_id}
                      to={`/user/${user.username}`}
                      className="group flex flex-col items-center p-4 bg-[#0F0F16] border border-white/5 rounded-xl hover:border-[#00E5FF]/30 transition-colors"
                    >
                      <Avatar className={`w-16 h-16 mb-3 ${user.is_streaming ? 'avatar-live' : ''}`}>
                        <AvatarImage src={user.avatar_url} alt={user.display_name || user.username} />
                        <AvatarFallback className="bg-[#292938] text-[#00E5FF] text-xl">
                          {(user.display_name || user.username)?.charAt(0).toUpperCase()}
                        </AvatarFallback>
                      </Avatar>
                      <h3 className="font-semibold text-white text-center group-hover:text-[#00E5FF] transition-colors">
                        {user.display_name || user.username}
                      </h3>
                      <p className="text-xs text-[#A0A0AB]">@{user.username}</p>
                    </Link>
                  ))}
                </div>
              </section>
            )}

            {results.categories.length > 0 && (
              <section>
                <h2 className="text-lg font-semibold text-white mb-4">Categories</h2>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
                  {results.categories.slice(0, 4).map((cat) => (
                    <Link
                      key={cat.category_id}
                      to={`/category/${cat.category_id}`}
                      className="group flex items-center gap-3 p-4 bg-[#0F0F16] border border-white/5 rounded-xl hover:border-[#00E5FF]/30 transition-colors"
                    >
                      {cat.image_url && (
                        <img 
                          src={cat.image_url} 
                          alt={cat.name}
                          className="w-12 h-16 object-cover rounded"
                        />
                      )}
                      <div>
                        <h3 className="font-semibold text-white group-hover:text-[#00E5FF] transition-colors">
                          {cat.name}
                        </h3>
                        <p className="text-xs text-[#A0A0AB]">{cat.stream_count || 0} live</p>
                      </div>
                    </Link>
                  ))}
                </div>
              </section>
            )}
          </TabsContent>

          <TabsContent value="streams" className="mt-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {results.streams.map((stream) => (
                <StreamCard key={stream.stream_id} stream={stream} />
              ))}
            </div>
          </TabsContent>

          <TabsContent value="users" className="mt-6">
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
              {results.users.map((user) => (
                <Link
                  key={user.user_id}
                  to={`/user/${user.username}`}
                  className="group flex flex-col items-center p-4 bg-[#0F0F16] border border-white/5 rounded-xl hover:border-[#00E5FF]/30 transition-colors"
                >
                  <Avatar className={`w-16 h-16 mb-3 ${user.is_streaming ? 'avatar-live' : ''}`}>
                    <AvatarImage src={user.avatar_url} alt={user.display_name || user.username} />
                    <AvatarFallback className="bg-[#292938] text-[#00E5FF] text-xl">
                      {(user.display_name || user.username)?.charAt(0).toUpperCase()}
                    </AvatarFallback>
                  </Avatar>
                  <h3 className="font-semibold text-white text-center group-hover:text-[#00E5FF] transition-colors">
                    {user.display_name || user.username}
                  </h3>
                  <p className="text-xs text-[#A0A0AB]">@{user.username}</p>
                </Link>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="categories" className="mt-6">
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
              {results.categories.map((cat) => (
                <Link
                  key={cat.category_id}
                  to={`/category/${cat.category_id}`}
                  className="group flex items-center gap-3 p-4 bg-[#0F0F16] border border-white/5 rounded-xl hover:border-[#00E5FF]/30 transition-colors"
                >
                  {cat.image_url && (
                    <img 
                      src={cat.image_url} 
                      alt={cat.name}
                      className="w-12 h-16 object-cover rounded"
                    />
                  )}
                  <div>
                    <h3 className="font-semibold text-white group-hover:text-[#00E5FF] transition-colors">
                      {cat.name}
                    </h3>
                    <p className="text-xs text-[#A0A0AB]">{cat.stream_count || 0} live</p>
                  </div>
                </Link>
              ))}
            </div>
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
